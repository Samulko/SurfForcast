# test_windy_api.py
import os
import httpx
import json
import asyncio # Added for gathering multiple requests

# --- Configuration ---
# Get API key from environment variable
WINDY_API_KEY = os.environ.get("WINDY_API_KEY")
WINDY_API_URL = "https://api.windy.com/api/point-forecast/v2"

# --- Test Parameters ---
# Example coordinates (e.g., Pipeline, Hawaii)
test_latitude = 21.6649
test_longitude = -158.0539

# Parameters for the 'gfsWave' model
wave_parameters = [
    "waves",      # Includes height, period, direction
    "windWaves",  # Includes height, period, direction
    "swell1",     # Includes height, period, direction
    # "swell2" is also available if needed
]
wave_model = "gfsWave"

# Parameters for the 'gfs' model
wind_parameters = [
    "wind",       # u/v components for wind speed/direction
    "windGust"    # Gust speed
]
wind_model = "gfs"

async def make_api_call(client, model, parameters, latitude, longitude, api_key):
    """Helper function to make a single API call and handle response."""
    request_body = {
        "lat": latitude,
        "lon": longitude,
        "model": model,
        "parameters": parameters,
        "levels": ["surface"], # Surf/wind data is surface level
        "key": api_key
    }
    print(f"\n--- Sending Request for model: {model} ---")
    print(f"Request Body:\n{json.dumps(request_body, indent=2)}")

    try:
        response = await client.post(WINDY_API_URL, json=request_body)
        print(f"--- Received Response for model: {model} ---")
        print(f"Status Code: {response.status_code}")

        response_data = None
        try:
            response_data = response.json()
            print("Response JSON Body:")
            print(json.dumps(response_data, indent=2))
        except json.JSONDecodeError:
            print("Response Body (Non-JSON):")
            print(response.text)

        response.raise_for_status() # Raise exception for bad status codes
        print(f"--- Call Successful for model: {model} ---")
        return response_data # Return parsed data on success

    except httpx.HTTPStatusError as e:
        print(f"--- Call Failed for model: {model} (HTTP Error) ---")
        print(f"Error: {e}")
        # Error details might already be printed above
        return None # Indicate failure
    except httpx.RequestError as e:
        print(f"--- Call Failed for model: {model} (Request Error) ---")
        print(f"Error connecting to Windy API: {e}")
        return None # Indicate failure
    except Exception as e:
        print(f"--- Call Failed for model: {model} (Unexpected Error) ---")
        print(f"An unexpected error occurred: {e}")
        return None # Indicate failure


async def test_windy_calls():
    print("--- Starting Windy API Test (Two Calls) ---")

    if not WINDY_API_KEY:
        print("Error: WINDY_API_KEY environment variable not set.")
        print("Please set the WINDY_API_KEY environment variable before running.")
        return

    print(f"Using API Key ending with: ...{WINDY_API_KEY[-4:]}")

    async with httpx.AsyncClient() as client:
        # Create tasks for both API calls to run concurrently
        wave_task = make_api_call(client, wave_model, wave_parameters, test_latitude, test_longitude, WINDY_API_KEY)
        wind_task = make_api_call(client, wind_model, wind_parameters, test_latitude, test_longitude, WINDY_API_KEY)

        # Wait for both tasks to complete
        wave_results, wind_results = await asyncio.gather(wave_task, wind_task)

        print("\n--- Overall Test Summary ---")
        if wave_results:
            print("Wave data retrieved successfully.")
        else:
            print("Failed to retrieve wave data.")

        if wind_results:
            print("Wind data retrieved successfully.")
        else:
            print("Failed to retrieve wind data.")

        if wave_results and wind_results:
            print("\n--- Combined Data (Example) ---")
            # Here you would typically merge the relevant parts of
            # wave_results and wind_results based on timestamps ('ts')
            # For this test, we just confirm both were received.
            print("Test successful: Both wave and wind data API calls succeeded.")
        else:
            print("\nTest failed: One or both API calls did not succeed.")


if __name__ == "__main__":
    asyncio.run(test_windy_calls())
