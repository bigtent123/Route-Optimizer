# Route Optimizer App

A Streamlit-based route optimization application that helps plan efficient delivery routes for multiple locations.

## Features

- 📍 Multi-stop route optimization
- 📅 Time window constraints for deliveries
- 🗓️ Working days configuration (Monday-Friday by default)
- 🚫 Blackout dates support
- 📊 Excel/CSV data import
- 🗺️ Interactive map visualization
- 📋 Detailed route instructions
- 📄 PDF report generation

## Live Demo

Visit the app at: [Your Streamlit App URL]

## Installation

1. Clone the repository:
```bash
git clone https://github.com/yourusername/route-optimizer-app.git
cd route-optimizer-app
```

2. Create a virtual environment:
```bash
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate
```

3. Install dependencies:
```bash
pip install -r requirements.txt
```

4. Set up your Google Maps API key:
```bash
export GOOGLE_MAPS_API_KEY='your-api-key-here'
```

## Usage

1. Run the app locally:
```bash
streamlit run app.py
```

2. Configure your settings in the sidebar:
   - Work hours (default: 8 AM - 5 PM)
   - Working days (default: Monday-Friday)
   - Service duration per stop
   - Depot address (required)

3. Upload your visit data:
   - Use the provided Excel template
   - Or enter addresses manually

4. Click "Run Optimization" to generate the optimal route

## Data Format

The app accepts Excel/CSV files with the following columns:
- Address (required)
- Window Start (optional, format: HH:MM AM/PM)
- Window End (optional, format: HH:MM AM/PM)
- Allowed Days (optional, comma-separated)
- Blackout Dates (optional, comma-separated MM/DD/YYYY)

## Environment Variables

- `GOOGLE_MAPS_API_KEY`: Your Google Maps API key (required for route optimization)

## Technologies Used

- Streamlit
- Google OR-Tools for route optimization
- Google Maps API for geocoding and distance calculations
- Folium for map visualization
- Pandas for data processing

## License

MIT License 