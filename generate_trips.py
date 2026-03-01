import os
import sys
import json
import argparse
import re
import urllib.parse
from datetime import datetime, timedelta
import difflib
import requests
from dotenv import load_dotenv
from jinja2 import Environment, FileSystemLoader

# Load environment variables
load_dotenv()

GOOGLE_MAPS_API_KEY = os.getenv("GOOGLE_MAPS_API_KEY")

def validate_military_time(time_str):
    """Validates 4-digit time and converts to HH:MM format internally."""
    if not re.match(r"^\d{4}$", time_str):
        raise argparse.ArgumentTypeError(f"Time '{time_str}' must be exactly 4 digits (e.g., 0830).")
    
    hours = int(time_str[0:2])
    minutes = int(time_str[2:4])
    
    if hours < 0 or hours > 23:
        raise argparse.ArgumentTypeError(f"Hours in '{time_str}' must be between 00 and 23.")
    if minutes < 0 or minutes > 59:
        raise argparse.ArgumentTypeError(f"Minutes in '{time_str}' must be between 00 and 59.")
        
    return f"{time_str[0:2]}:{time_str[2:4]}"

def validate_date(date_str):
    if not re.match(r"^\d{4}-\d{2}-\d{2}$", date_str):
        raise argparse.ArgumentTypeError(f"Date '{date_str}' must be YYYY-MM-DD.")
    try:
        dt = datetime.strptime(date_str, "%Y-%m-%d")
        if dt.date() < datetime.now().date():
            raise argparse.ArgumentTypeError("Date must be in the future.")
        return date_str
    except ValueError:
        raise argparse.ArgumentTypeError(f"Invalid date: {date_str}")

def get_crs_code(station_name, stations_db):
    """Attempts to match a Google Maps station name to a 3-letter CRS code."""
    if not station_name:
        return None
        
    # Clean up the Google Maps name
    name_clean = station_name.lower().replace('railway station', '').replace('station', '').replace('underground', '').strip()
    
    # 1. Exact match attempt
    for s in stations_db:
        if s.get('stationName', '').lower() == name_clean:
            return s.get('crsCode')
            
    # 2. Fuzzy match attempt
    db_names = [s.get('stationName', '').lower() for s in stations_db if 'stationName' in s]
    matches = difflib.get_close_matches(name_clean, db_names, n=1, cutoff=0.7)
    
    if matches:
        match_name = matches[0]
        for s in stations_db:
            if s.get('stationName', '').lower() == match_name:
                return s.get('crsCode')
                
    return None

def get_journey_info_google(origin, destination, departure_time_unix):
    url = "https://maps.googleapis.com/maps/api/directions/json"
    params = {
        "origin": origin,
        "destination": destination,
        "mode": "transit",
        "departure_time": departure_time_unix,
        "key": GOOGLE_MAPS_API_KEY
    }
    
    resp = requests.get(url, params=params)
    if resp.status_code == 200:
        data = resp.json()
        if data.get("routes"):
            leg = data["routes"][0]["legs"][0]
            duration_mins = int(leg["duration"]["value"] / 60)
            
            steps = leg.get("steps", [])
            transit_lines = []
            transit_legs_count = 0
            
            heavy_rail_steps = []
            for s in steps:
                if s.get("travel_mode") == "TRANSIT":
                    td = s.get("transit_details", {})
                    line = td.get("line", {})
                    if line.get("vehicle", {}).get("type") == "HEAVY_RAIL":
                        line_name = (line.get("name") or "").lower()
                        agency_name = ""
                        if line.get("agencies"):
                            agency_name = (line["agencies"][0].get("name") or "").lower()
                        
                        # Ignore Elizabeth line, London Overground, and generic TfL rail
                        is_tfl = any(x in line_name or x in agency_name for x in ["elizabeth line", "london overground", "transport for london"])
                        
                        if not is_tfl:
                            heavy_rail_steps.append(s)
            
            heavy_rail_info = None
            if heavy_rail_steps:
                first_s = heavy_rail_steps[0]["transit_details"]
                last_s = heavy_rail_steps[-1]["transit_details"]
                
                # Standardize common terminal names
                origin_name = first_s["departure_stop"]["name"]
                if origin_name in ["Waterloo", "Euston", "Victoria", "Paddington", "Liverpool Street", "St Pancras", "Marylebone", "Fenchurch Street", "Cannon Street", "London Bridge", "Blackfriars", "Charing Cross"]:
                    origin_name = f"London {origin_name}"
                
                heavy_rail_info = {
                    "origin": origin_name,
                    "destination": last_s["arrival_stop"]["name"],
                    "departure_timestamp": first_s["departure_time"]["value"]
                }

            for step in steps:
                if step["travel_mode"] == "TRANSIT":
                    transit_legs_count += 1
                    td = step["transit_details"]
                    line = td["line"]
                    line_name = line.get("short_name") or line.get("name") or "Train"
                    transit_lines.append(line_name)
                    
            route_str = " -> ".join(transit_lines) if transit_lines else "Direct route"
            return duration_mins, transit_legs_count, route_str, heavy_rail_info
            
    return None, None, "Could not calculate route", None

def format_time(minutes):
    h = minutes // 60
    m = minutes % 60
    if h > 0:
        return f"{h}h {m}m"
    return f"{m}m"

def generate_google_maps_url(origin, destination, date_str, time_str):
    base_url = "https://www.google.com/maps/dir/?api=1"
    parts = date_str.split('-')
    formatted_date = f"{parts[2]}/{parts[1]}/{parts[0]}"
    formatted_time = f"{time_str[:2]}:{time_str[2:4]}" if len(time_str) == 4 else time_str
    params = {"origin": origin, "destination": destination, "travelmode": "transit", "ttype": "dep", "date": formatted_date, "time": formatted_time}
    return base_url + "&" + urllib.parse.urlencode(params)

def generate_nre_url(origin_crs, dest_crs, departure_dt):
    if not origin_crs or not dest_crs:
        return ""
    nre_date = departure_dt.strftime("%d%m%y")
    hour = departure_dt.strftime("%H")
    minute = "00"
    return_dt = departure_dt + timedelta(hours=10)
    base_url = 'https://www.nationalrail.co.uk/journey-planner/?'
    params = {
        'type': 'return', 'origin': origin_crs, 'destination': dest_crs,
        'leavingType': 'departing', 'leavingDate': nre_date, 'leavingHour': hour, 'leavingMin': minute,
        'returnType': 'departing', 'returnDate': return_dt.strftime("%d%m%y"), 'returnHour': return_dt.strftime("%H"), 'returnMin': "00",
        'adults': '1', 'extraTime': '0'
    }
    return base_url + urllib.parse.urlencode(params) + '#O'

def main():
    parser = argparse.ArgumentParser(description="Escape London: Go Adventure - 40 Trips CLI")
    parser.add_argument("--postcode", required=True, help="UK Postcode (e.g. 'SW1A 1AA')")
    parser.add_argument("--date", required=True, type=validate_date, help="Date YYYY-MM-DD")
    parser.add_argument("--time", required=True, type=validate_military_time, help="Time HHMM (e.g. 0830)")
    args = parser.parse_args()

    base_dt_str = f"{args.date} {args.time}"
    base_dt = datetime.strptime(base_dt_str, "%Y-%m-%d %H:%M")
    unix_timestamp = int(base_dt.timestamp())

    script_dir = os.path.dirname(os.path.abspath(__file__))
    with open(os.path.join(script_dir, "destinations.json"), "r") as f:
        destinations = json.load(f)
    with open(os.path.join(script_dir, "uk_stations.json"), "r") as f:
        uk_stations = json.load(f)

    final_trips = []
    print(f"Escape London: Routing from {args.postcode} on {args.date} at {args.time}")
    print("Fetching live routes via Google Maps. This will take roughly 15-20 seconds...")
    
    for index, dest in enumerate(destinations):
        print(f"[{index+1}/40] Calculating route to {dest['name']}...")
        duration, legs, route_string, heavy_rail_info = get_journey_info_google(args.postcode, dest["search_query"], unix_timestamp)
        google_maps_url = generate_google_maps_url(args.postcode, dest["search_query"], args.date, args.time)
        
        nre_url = ""
        if duration is not None:
            if not dest.get("is_tfl_network", False):
                if heavy_rail_info:
                    o_crs = get_crs_code(heavy_rail_info["origin"], uk_stations)
                    d_crs = get_crs_code(heavy_rail_info["destination"], uk_stations)
                    train_dep_dt = datetime.fromtimestamp(heavy_rail_info["departure_timestamp"])
                    nre_url = generate_nre_url(o_crs, d_crs, train_dep_dt)
                else:
                    nre_url = generate_nre_url(dest.get("departure_hub_crs"), dest.get("destination_crs"), base_dt + timedelta(minutes=45))
            formatted_time = format_time(duration)
        else:
            formatted_time, legs = "N/A", "N/A"
        
        final_trips.append({
            "name": dest["name"], "type": dest["type"], "length": dest["length"], "details": dest["details"],
            "formatted_time": formatted_time, "legs": legs, "route_details": route_string,
            "google_maps_url": google_maps_url, "nre_url": nre_url
        })

    env = Environment(loader=FileSystemLoader(script_dir))
    template = env.get_template("template.html")
    html_output = template.render(user_postcode=args.postcode, user_date=args.date, user_time=args.time, current_time=datetime.now().strftime("%Y-%m-%d %H:%M"), trips=final_trips)
    
    safe_postcode = args.postcode.replace(' ', '')
    output_filename = os.path.join(script_dir, f"escape_london_{safe_postcode}.html")
    with open(output_filename, "w") as f:
        f.write(html_output)
    print(f"Success! Saved to {output_filename}")

if __name__ == "__main__":
    main()