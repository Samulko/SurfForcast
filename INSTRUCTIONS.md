# INSTRUCTIONS.md: Setting up a Windy Surfing Forecast MCP Server for Cursor

This guide walks you through creating a simple Model Context Protocol (MCP) server in Python. This server will act as a tool within Cursor, allowing you to ask for surfing conditions at a specific location (latitude/longitude) and get a forecast using the Windy API.

**Prerequisites:**

1.  **Python:** Ensure you have Python installed.
2.  **Cursor:** You need Cursor installed.
3.  **Windy API Key:** Obtain an API key for the Windy Point Forecast API[cite: 48, 49]. You'll need this to make requests.
4.  **uv (Recommended):** The MCP Python SDK documentation recommends using `uv` for managing Python projects[cite: 5].

## 1. Set up the Python Project

a.  **Create a project directory:**
    ```bash
    mkdir windy-mcp-server
    cd windy-mcp-server
    ```

b.  **Initialize a Python environment (using uv):**
    ```bash
    uv init
    ```

c.  **Install MCP SDK and HTTP library:** You need the MCP library and a library to make HTTP requests (like `httpx`).
    ```bash
    uv add "mcp[cli]" httpx
    ```
    (If not using `uv`, use `pip install "mcp[cli]" httpx`) [cite: 6]

## 2. Create the MCP Server Code

Create a file named `windy_server.py` in your project directory and add the following code:

```python
import os
import httpx # Library to make HTTP requests
from mcp.server.fastmcp import FastMCP, Context

# --- Configuration ---
# It's best practice to load your API key from environment variables
# You will configure this in Cursor's MCP settings later [cite: 102]
WINDY_API_KEY = os.environ.get("WINDY_API_KEY", "YOUR_DEFAULT_KEY_IF_ANY")
WINDY_API_URL = "[https://api.windy.com/api/point-forecast/v2](https://api.windy.com/api/point-forecast/v2)" # [cite: 40]

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


## 3. Configure Cursor to Use the MCP Server


Cursor needs to know how to run your Python script as an MCP server. You'll use the stdio transport for local execution.  

a.  Create the configuration file:
* Project-specific: Create a file named mcp.json inside a .cursor directory within your windy-mcp-server project folder (windy-mcp-server/.cursor/mcp.json).
* Global (optional): Alternatively, for use across all projects, create ~/.cursor/mcp.json.  

b.  Add the server configuration to mcp.json:
```json
{
  "mcpServers": {
    "windy-surf-forecast": { // Choose a unique name for your server
      "command": "uv",     // Command to run (use "python" if not using uv)
      "args": [
         "run",            // Argument for uv (remove if using python)
         "python",         // Argument for uv (remove if using python)
         "windy_server.py" // The script to run
        ],
      "env": {
        "WINDY_API_KEY": "YOUR_ACTUAL_WINDY_API_KEY" // <-- IMPORTANT: Replace this! [cite: 102]
      }
    }
  }
}
```
* **`command`**: Set to `uv` if you initialized with `uv`, otherwise `python`.
* **`args`**: If using `uv`, include `run` and `python` before your script name. If using `python`, just include the script name `windy_server.py`.
* **`env`**: This is crucial. Set `WINDY_API_KEY` to your actual Windy API key[cite: 102]. **Never commit your API key directly into version control.** For better security practices, consider loading keys from a more secure location or environment management system, though this `mcp.json` method is functional for local use.

## 4. Using the Tool in Cursor

a.  Restart Cursor: Ensure Cursor picks up the new configuration.
b.  Check MCP Settings: Go to Cursor's settings, find the Model Context Protocol (MCP) section, and verify your "windy-surf-forecast" server is listed and active.
c.  Chat with the Agent: You can now ask Cursor's agent to use your tool. Refer to it by name or describe its function:
* "Use the windy-surf-forecast tool to get the conditions for latitude 34.05, longitude -118.25."
* "What are the surfing conditions at latitude 49.8, longitude 16.7?" (The agent should recognize the tool is relevant)  

d.  Approve Tool Use: By default, Cursor will ask for your approval before running the tool. You can inspect the latitude and longitude arguments before confirming.  

You now have a basic MCP server running locally, integrated with Cursor, that can fetch surfing forecast data from the Windy API! You can expand this by adding more specific parameter requests, better error handling, and more sophisticated parsing of the Windy response.   
