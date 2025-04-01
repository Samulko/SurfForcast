import os
from datetime import datetime
import httpx
from dotenv import load_dotenv

load_dotenv()

async def get_surf_prediction(location: str, date: str = None) -> dict:
    """
    Get surf conditions prediction for a specific location and date.
    If no date is provided, returns current conditions.
    """
    # If no date provided, use today
    if not date:
        date = datetime.now().strftime("%Y-%m-%d")
    
    # Check if we have a Windy API key
    windy_api_key = os.getenv("WINDY_API_KEY")
    
    if windy_api_key:
        # Use Windy API for real data
        async with httpx.AsyncClient() as client:
            # Note: This is a placeholder URL - you'll need to replace with actual Windy API endpoint
            response = await client.get(
                f"https://api.windy.com/api/point-forecast/v2",
                params={
                    "lat": 0,  # You'll need to geocode the location
                    "lon": 0,  # You'll need to geocode the location
                    "model": "gfs",
                    "parameters": ["waves"],
                    "key": windy_api_key,
                    "start": date,
                    "end": date
                }
            )
            data = response.json()
            
            # Process the API response and return formatted data
            return {
                "location": location,
                "date": date,
                "wave_height": "2-3ft",  # Replace with actual data from API
                "conditions": "Fair",
                "source": "Windy API"
            }
    else:
        # Return static data if no API key is available
        return {
            "location": location,
            "date": date,
            "wave_height": "2-3ft",
            "conditions": "Fair",
            "source": "Static Data"
        } 