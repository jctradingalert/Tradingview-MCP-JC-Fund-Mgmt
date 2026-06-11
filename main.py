import os
from fastmcp import FastMCP

mcp = FastMCP("tradingview-mcp")

# Add your tools/resources here

if __name__ == "__main__":
    mcp.run(
        transport="streamable-http",
        host="0.0.0.0",
        port=int(os.environ.get("PORT", 8000))
    )
