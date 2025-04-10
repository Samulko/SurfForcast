import sys
# Print to stderr immediately to check execution start

try:
    # --- Inside main try block --- # Removed print statement
    import os
    import httpx # Library to make HTTP requests
    import asyncio # For concurrent API calls
    import json # For formatting the output
    import traceback # For better error logging
    import math # For wind calculations
    from datetime import datetime, timezone # For timestamp formatting
    from typing import Optional, List, Dict # For type hinting
    from pydantic import BaseModel, Field, ValidationError # For data validation
    from mcp.server.fastmcp import FastMCP, Context
    from dotenv import load_dotenv # Import load_dotenv
    # --- Imports potentially successful --- # Removed print statement

    # Load environment variables from .env file
    load_dotenv()

    # --- Configuration ---
    # It's best practice to load your API key from environment variables
    # You will configure this in Cursor's MCP settings later
    WINDY_API_KEY = os.environ.get("WINDY_API_KEY") # Removed default key, rely on .env or actual env var
    WINDY_API_URL = "https://api.windy.com/api/point-forecast/v2"
    # --- Configuration loaded --- # Removed comment

    # --- Helper Functions ---
    def calculate_wind_speed(u: float, v: float) -> float:
        """Calculates wind speed from u and v components."""
        return math.sqrt(u**2 + v**2)

    def calculate_wind_direction(u: float, v: float) -> str:
        """Calculates cardinal/ordinal wind direction from u and v components."""
        angle_rad = math.atan2(u, v) # Meteorological convention (0 deg = North wind)
        angle_deg = math.degrees(angle_rad)
        wind_dir_corrected = (angle_deg + 360) % 360

        directions = ["N", "NNE", "NE", "ENE", "E", "ESE", "SE", "SSE", "S", "SSW", "SW", "WSW", "W", "WNW", "NW", "NNW"]
        index = round(wind_dir_corrected / 22.5) % 16
        return directions[index]

    def format_timestamp_iso(timestamp_ms: int) -> str:
        """Formats a millisecond timestamp into an ISO 8601 string (UTC)."""
        try:
            dt_object = datetime.fromtimestamp(timestamp_ms / 1000, tz=timezone.utc)
            # Format to ISO 8601, ensuring 'Z' for UTC
            return dt_object.isoformat(timespec='seconds').replace('+00:00', 'Z')
        except (ValueError, TypeError):
            # Handle potential issues with the timestamp value
            return "Invalid Timestamp"

    # --- Pydantic Models ---
    class TimePointData(BaseModel):
        # Define the structure for a single forecast time point
        # Use Field(alias=...) to handle keys with hyphens
        timestamp: int
        timestamp_iso: Optional[str] = None # Added: ISO 8601 formatted timestamp (UTC)
        waves_height_surface: Optional[float] = Field(None, alias="waves_height-surface")
        waves_period_surface: Optional[float] = Field(None, alias="waves_period-surface")
        waves_direction_surface: Optional[float] = Field(None, alias="waves_direction-surface")
        windWaves_height_surface: Optional[float] = Field(None, alias="windWaves_height-surface")
        windWaves_period_surface: Optional[float] = Field(None, alias="windWaves_period-surface")
        windWaves_direction_surface: Optional[float] = Field(None, alias="windWaves_direction-surface")
        swell1_height_surface: Optional[float] = Field(None, alias="swell1_height-surface")
        swell1_period_surface: Optional[float] = Field(None, alias="swell1_period-surface")
        swell1_direction_surface: Optional[float] = Field(None, alias="swell1_direction-surface")
        swell2_height_surface: Optional[float] = Field(None, alias="swell2_height-surface")
        swell2_period_surface: Optional[float] = Field(None, alias="swell2_period-surface")
        swell2_direction_surface: Optional[float] = Field(None, alias="swell2_direction-surface")
        wind_u_surface: Optional[float] = Field(None, alias="wind_u-surface")
        wind_v_surface: Optional[float] = Field(None, alias="wind_v-surface")
        wind_speed_surface: Optional[float] = None # Added: Derived wind speed (m/s)
        wind_direction_cardinal: Optional[str] = None # Added: Derived wind direction (e.g., N, SW)
        gust_surface: Optional[float] = Field(None, alias="gust-surface")
        temp_surface: Optional[float] = Field(None, alias="temp-surface")
        precip_surface: Optional[float] = Field(None, alias="past3hprecip-surface")
        ptype_surface: Optional[int] = Field(None, alias="ptype-surface")

        class Config:
            populate_by_name = True # Allows using both alias and field name

    class WindyForecastResponse(BaseModel):
        # Define the overall structure of the successful response
        units: Dict[str, Optional[str]]
        forecast: List[TimePointData]

    # --- MCP Server Setup ---
    # Create an MCP server instance
    mcp = FastMCP("Windy Surfing Forecast")
    # --- FastMCP instance created ---

    # --- Helper for API Call ---
    async def _make_windy_api_call(client: httpx.AsyncClient, model: str, parameters: list[str], latitude: float, longitude: float, api_key: str, ctx: Context) -> dict | None:
        """Makes a single call to the Windy API and handles errors."""
        request_body = {
            "lat": latitude,
            "lon": longitude,
            "model": model,
            "parameters": parameters,
            "levels": ["surface"], # Surf/wind data is surface level
            "key": api_key
        }
        try:
            await ctx.info(f"Sending request to Windy for model: {model}, params: {parameters}")
            response = await client.post(WINDY_API_URL, json=request_body)
            await ctx.info(f"Received response status {response.status_code} for model: {model}")
            response.raise_for_status() # Raise an exception for bad status codes (4xx or 5xx)
            return response.json()
        except httpx.HTTPStatusError as e:
            error_detail = "(Could not decode response text)"
            try:
                error_detail = e.response.text
            except Exception:
                pass # Keep default error detail
            error_message = f"HTTP Error for model {model}: {e.response.status_code} - {error_detail}"
            await ctx.error(error_message)
            return None # Indicate failure
        except httpx.RequestError as e:
            error_message = f"Request Error for model {model}: {e}"
            await ctx.error(error_message)
            return None # Indicate failure
        except Exception as e:
            error_message = f"Unexpected error during API call for model {model}: {str(e)}"
            await ctx.error(error_message)
            return None # Indicate failure

    # --- MCP Tool Definition ---
    @mcp.tool() # Decorator to define an MCP tool
    async def get_surfing_conditions(latitude: float, longitude: float, ctx: Context) -> str:
        """
        Fetches surfing conditions (waves, swells, wind, temp, precip) for a given latitude and longitude.
        Uses the Windy API with gfsWave (waves) and gfs (wind/weather) models.
        Returns a JSON object with 'units' and a 'forecast' list.
        Each item in 'forecast' represents a time point (typically 3-hour intervals) 
        containing various parameters and a 'timestamp' (UTC milliseconds since epoch).
        The client should handle timezone conversion for local display.
        Provide latitude and longitude coordinates.
        """
        # --- Tool get_surfing_conditions called ---
        if not WINDY_API_KEY or WINDY_API_KEY == "YOUR_DEFAULT_KEY_IF_ANY":
            await ctx.error("WINDY_API_KEY not set") # Use ctx.error for logging issues
            return "Error: WINDY_API_KEY environment variable not set."

        await ctx.info(f"Fetching forecast for Lat: {latitude}, Lon: {longitude}") # Log progress

        # Define parameters for each model
        wave_parameters = ["waves", "windWaves", "swell1", "swell2"]
        wave_model = "gfsWave"
        wind_parameters = ["wind", "windGust", "temp", "precip", "ptype"]
        wind_model = "gfs"

        combined_data = {}
        error_messages = []
        has_wave_data = False
        has_wind_data = False

        async with httpx.AsyncClient() as client:
            # --- Sending requests concurrently ---
            wave_task = _make_windy_api_call(client, wave_model, wave_parameters, latitude, longitude, WINDY_API_KEY, ctx)
            wind_task = _make_windy_api_call(client, wind_model, wind_parameters, latitude, longitude, WINDY_API_KEY, ctx)

            wave_results, wind_results = await asyncio.gather(wave_task, wind_task)
            # --- Responses received ---

            all_units = {}
            forecast_data = []
            ts_list = None

            # Process Wave Data & Units
            if wave_results and 'ts' in wave_results and 'units' in wave_results:
                has_wave_data = True
                ts_list = wave_results['ts'] # Prioritize wave timestamps
                all_units.update(wave_results['units'])
                await ctx.info("Wave data seems valid.")
            elif wave_results is None:
                 error_messages.append(f"Failed to retrieve wave data ({wave_model}).")
            else:
                 error_messages.append(f"Retrieved wave data ({wave_model}) is incomplete or malformed.")
                 # await ctx.warning(f"Malformed wave data: {wave_results}")

            # Process Wind Data & Units
            if wind_results and 'ts' in wind_results and 'units' in wind_results:
                has_wind_data = True
                all_units.update(wind_results['units'])
                if ts_list is None: # Use wind timestamps if wave data failed
                     ts_list = wind_results['ts']
                     await ctx.info("Using wind timestamps as primary.")
                elif ts_list != wind_results['ts']:
                     # This case requires more complex handling (interpolation/alignment)
                     # For now, we log a warning and proceed, potentially with misaligned data
                     await ctx.warning("Timestamps between wave and wind data do not match! Data might be misaligned.")
                await ctx.info("Wind data seems valid.")
            elif wind_results is None:
                 error_messages.append(f"Failed to retrieve wind data ({wind_model}).")
            else:
                 error_messages.append(f"Retrieved wind data ({wind_model}) is incomplete or malformed.")
                 # await ctx.warning(f"Malformed wind data: {wind_results}")

            # Combine data chronologically if we have timestamps
            if ts_list:
                await ctx.info(f"Processing data for {len(ts_list)} timestamps.")
                for i, timestamp in enumerate(ts_list):
                    # Initialize with original timestamp and derived ISO format
                    time_point_data = {
                        "timestamp": timestamp,
                        "timestamp_iso": format_timestamp_iso(timestamp)
                    }

                    # Add wave data for this timestamp
                    if has_wave_data:
                        for param_base in wave_parameters:
                            for suffix in ['height', 'period', 'direction']:
                                key = f"{param_base}_{suffix}-surface"
                                if key in wave_results and i < len(wave_results[key]):
                                    time_point_data[key] = wave_results[key][i]
                                elif key in wave_results: # Handle case where array might be shorter than ts list
                                     await ctx.warning(f"Missing data for {key} at index {i}")

                    # Add wind data for this timestamp
                    # Ensure wind data aligns with the timestamp index, especially if ts lists differed
                    wind_data_index = i # Assume alignment for now
                    # If ts lists differed, a more robust index lookup might be needed,
                    # but we'll assume the API provides corresponding data for simplicity.

                    if has_wind_data:
                         # Find the corresponding index in wind_results['ts'] if necessary
                         # This simple approach assumes the lengths are the same even if contents differ slightly
                         if 'ts' in wind_results and i < len(wind_results['ts']):
                            # Check if wind timestamps actually match the main ts_list index
                            if ts_list == wind_results['ts'] or wind_results['ts'][i] == timestamp:
                                wind_data_index = i
                            else:
                                # Attempt to find matching timestamp - potential performance hit
                                try:
                                    wind_data_index = wind_results['ts'].index(timestamp)
                                except ValueError:
                                    await ctx.warning(f"Timestamp {timestamp} not found in wind data timestamps. Skipping wind data for this point.")
                                    wind_data_index = -1 # Indicate not found

                            if wind_data_index != -1:
                                u_comp, v_comp = None, None # Store components for derived values
                                for param in wind_parameters:
                                    if param == "wind":
                                        for comp in ['u', 'v']:
                                            key = f"wind_{comp}-surface"
                                            if key in wind_results and wind_data_index < len(wind_results[key]):
                                                value = wind_results[key][wind_data_index]
                                                time_point_data[key] = value
                                                if comp == 'u': u_comp = value
                                                if comp == 'v': v_comp = value
                                            elif key in wind_results:
                                                await ctx.warning(f"Missing data for {key} at index {wind_data_index}")

                                # Calculate and add derived wind data if components exist
                                if u_comp is not None and v_comp is not None:
                                    time_point_data["wind_speed_surface"] = calculate_wind_speed(u_comp, v_comp)
                                    time_point_data["wind_direction_cardinal"] = calculate_wind_direction(u_comp, v_comp)
                                else:
                                    await ctx.warning(f"Missing wind u/v components at index {wind_data_index}, cannot calculate derived wind info.")
                         else:
                            await ctx.warning(f"Wind timestamp array missing or too short at index {i}")


                    forecast_data.append(time_point_data)
                await ctx.info("Finished combining data chronologically.")
            else:
                await ctx.error("No valid timestamp list available to structure the forecast.")
                error_messages.append("Could not determine forecast timestamps.")


        # --- Format and return results ---
        final_result_dict = {}
        if forecast_data:
            try:
                # Validate the processed data against the Pydantic models
                validated_response = WindyForecastResponse(units=all_units, forecast=forecast_data)
                # Convert the Pydantic model back to a dict for JSON serialization
                # Use by_alias=True to ensure hyphens are used in the output keys
                final_result_dict = validated_response.model_dump(by_alias=True, exclude_none=True) # Exclude None values for cleaner output
                await ctx.info("Successfully processed and validated forecast data.")

                # Log warnings separately if they exist
                if error_messages:
                    warning_message = "Warnings during data retrieval/processing:\n" + "\n".join(error_messages)
                    await ctx.warning(warning_message)

                # Return the structured, validated data as JSON
                return json.dumps(final_result_dict, indent=2)

            except ValidationError as e:
                error_summary = "\n".join(error_messages) if error_messages else ""
                validation_error_msg = f"Error: Forecast data failed validation.\nDetails: {e}\n{error_summary}"
                await ctx.error(validation_error_msg)
                return validation_error_msg
            except Exception as e:
                # Catch any other unexpected errors during validation/serialization
                # Log warnings if they exist
                if error_messages:
                    warning_message = "Warnings prior to unexpected error:\n" + "\n".join(error_messages)
                    await ctx.warning(warning_message)
                unexpected_error_msg = f"Error: An unexpected error occurred during final processing.\nDetails: {str(e)}"
                await ctx.error(unexpected_error_msg)
                return unexpected_error_msg

        else:
            # Only errors occurred or no data could be processed
             error_summary = "\n".join(error_messages) if error_messages else "An unknown issue occurred structuring the data."
             final_message = f"Error fetching or processing forecast data:\n{error_summary}"
             await ctx.error(final_message)
             return final_message

    # --- Tool defined ---
    # --- Tool definition complete, before final except block ---

except Exception as e:
    # Catch any exceptions during import or initial setup
    # Log to stderr so it doesn't interfere with MCP stdio, but still visible in logs
    print(f"FATAL ERROR during script setup: {e}", file=sys.stderr, flush=True)
    traceback.print_exc(file=sys.stderr) # Print full traceback for debugging
    sys.exit(1) # Exit with an error code

# --- Run the server (for direct testing, not needed for Cursor stdio) ---
# This part is useful for testing the server directly but not required
# when running via Cursor's stdio transport.
if __name__ == "__main__":
    # Use stderr for prints during direct execution testing
    mcp.run() # --- 