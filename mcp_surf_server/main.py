import os
from pathlib import Path
from mcp.server.fastmcp import FastMCP
from tools.get_surf_prediction import get_surf_prediction

# Initialize FastMCP server
app = FastMCP()

# Get the path to the schema file
schema_path = Path(__file__).parent / "zod_schemas" / "get_surf_prediction.json"

# Register the surf prediction tool
app.register_tool(
    name="get_surf_prediction",
    handler=get_surf_prediction,
    schema_path=schema_path,
    description="Get surf conditions prediction for a specific location and date"
)

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000) 