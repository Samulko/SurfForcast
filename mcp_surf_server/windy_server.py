import os
import httpx # Library to make HTTP requests
from mcp.server.fastmcp import FastMCP, Context

# --- Configuration ---
# It's best practice to load your API key from environment variables
# You will configure this in Cursor's MCP settings later [cite: 102]
WINDY_API_KEY = os.environ.get("WINDY_API_KEY", "YOUR_DEFAULT_KEY_IF_ANY")
WINDY_API_URL = "https://api.windy.com/api/point-forecast/v2" # [cite: 40]

# --- MCP Server Setup ---
# Create an MCP server instance [cite: 6]
mcp = FastMCP("Windy Surfing Forecast")

# --- MCP Tool Definition ---
@mcp.tool() # Decorator to define an MCP tool [cite: 16]
async def get_surfing_conditions(latitude: float, longitude: float, ctx: Context) -> str:
    """
    Fetches surfing conditions (waves, wind) for a given latitude and longitude using the Windy API.
    Provide latitude and longitude coordinates.
    """
    if not WINDY_API_KEY or WINDY_API_KEY == "YOUR_DEFAULT_KEY_IF_ANY":
        return "Error: WINDY_API_KEY environment variable not set."

    ctx.info(f"Fetching forecast for Lat: {latitude}, Lon: {longitude}") # Log progress [cite: 19]

    # Define desired parameters and model for Windy API [cite: 40, 42, 72, 74, 79, 65, 67]
    request_body = {
        "lat": latitude, # [cite: 41]
        "lon": longitude, # [cite: 41]
        "model": "gfs", # Using GFS as an example global model [cite: 42]
        "parameters": [
            "waves",      # Includes height, period, direction [cite: 72]
            "windWaves",  # Includes height, period, direction [cite: 74]
            "swell1",     # Includes height, period, direction [cite: 79]
            "wind",       # u/v components for wind speed/direction [cite: 65]
            "windGust"    # Gust speed [cite: 67]
        ],
        "levels": ["surface"], # Most surf data is surface level [cite: 45, 46, 47]
        "key": WINDY_API_KEY
    }

    try:
        async with httpx.AsyncClient() as client:
            response = await client.post(WINDY_API_URL, json=request_body)
            response.raise_for_status() # Raise an exception for bad status codes (4xx or 5xx) [cite: 50]

            # Process the response data [cite: 51, 52, 54]
            data = response.json()

            # Basic formatting example (you can customize this much more)
            # This example just returns the raw JSON string for simplicity.
            # A real application would parse and format this nicely.
            forecast_summary = f"Forecast received from Windy:\n{data}"
            ctx.info("Successfully fetched and processed forecast.")
            return forecast_summary

    except httpx.HTTPStatusError as e:
        error_message = f"HTTP Error fetching data from Windy: {e.response.status_code} - {e.response.text}"
        ctx.error(error_message) # Log the error
        return error_message
    except Exception as e:
        error_message = f"An error occurred: {str(e)}"
        ctx.error(error_message) # Log the error
        return error_message

# --- Run the server (for direct testing, not needed for Cursor stdio) ---
# This part is useful for testing the server directly but not required
# when running via Cursor's stdio transport[cite: 20].
# if __name__ == "__main__":
#     print("Starting Windy MCP server directly for testing...")
#     mcp.run() --- 