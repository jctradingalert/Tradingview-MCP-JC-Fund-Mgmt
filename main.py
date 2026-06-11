from fastmcp import FastMCP

mcp = FastMCP("tradingview-mcp")

# Add your tools/resources here

if __name__ == "__main__":
    mcp.run(transport="streamable-http")
