# London Trip Generator

A Python command-line utility that generates an interactive and personalized HTML dashboard of 40 curated day trips (hiking and cultural) accessible via public transport from London.

The script uses the **Google Maps Directions API** to calculate true door-to-door transit times (including Tube connections) based on your specific starting postcode and departure time. It then automatically generates clickable deep-links to **National Rail** for live ticket checking.

## Features
*   **Dynamic Routing:** Calculates exact transit times and the number of transport changes based on your exact UK postcode and departure time.
*   **Deep Linking:** Generates one-click URLs that pre-populate Google Maps (for directions) and National Rail (for live train ticket prices) using exact station codes.
*   **Zero-Dependency Output:** The output is a single, self-contained HTML file (CSS and JS included) that you can open locally or share with friends.

## Setup & Installation

### 1. Prerequisites
You must have Python 3 installed. 
Clone the repository and install the required packages:
```bash
pip install -r requirements.txt
```

### 2. Configure Google Maps API
To calculate transit times, the script requires a free Google Maps API key.
1. Go to the [Google Cloud Console](https://console.cloud.google.com/).
2. Create a new project.
3. Enable the **Directions API** for that project.
4. Generate an API Key under "APIs & Services" > "Credentials".
*Note: Google provides $200 of free credit per month, which covers thousands of transit requests, so this tool will cost nothing to run for personal use.*

### 3. Environment Variables
Create a file named `.env` in the root of the project directory and paste your Google API key inside it:

```env
GOOGLE_MAPS_API_KEY=your_api_key_here
```
*(Note: Do not commit this file to GitHub! The `.gitignore` is already set up to protect it).*

## Usage

Run the script via the command line, providing your home postcode, the date you want to travel, and the time you want to leave your house (in 24-hour format).

```bash
python generate_trips.py --postcode "SW1A 1AA" --date "2026-04-18" --time 0800
```

### Arguments:
*   `--postcode`: Your UK postcode (e.g., `"SW1A 1AA"`). Ensure it is wrapped in quotes if it contains a space.
*   `--date`: The date of travel, strictly formatted as `YYYY-MM-DD`. Must be a future date.
*   `--time`: Your departure time, strictly formatted as 4 digits in military time without a colon (e.g., `0930` for 9:30 AM).

### Output
The script will print its progress to the console (taking roughly 10-15 seconds to query the routes) and save a file named `london_trips_[POSTCODE].html` in the same directory. Double-click this file to view your personalized dashboard in your browser.

## Customizing Destinations
The 40 trips are stored in `destinations.json`. You can easily add your own trips by adding new JSON objects to the array. Ensure you provide a precise `search_query` (e.g., "Seaford Railway Station, UK") so Google Maps knows exactly where to route the transit request.
