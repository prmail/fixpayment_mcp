"""
mcp/server.py – FastMCP server entry point.

Creates the shared `mcp` instance, then imports all tool modules so their
@mcp.tool decorators fire and register the tools.

Run directly:
    python -m mcp.server
    # or
    fastmcp run mcp/server.py:mcp
"""

from dotenv import load_dotenv

load_dotenv()  # Load .env file before anything accesses env-vars

from fastmcp import FastMCP  # noqa: E402

mcp = FastMCP("fixpayment-cred-portal")

# Import tool modules AFTER `mcp` is defined so decorators can reference it.
import mcp.tools.basic     # noqa: F401, E402
import mcp.tools.reports   # noqa: F401, E402
import mcp.tools.accounts  # noqa: F401, E402


if __name__ == "__main__":
    mcp.run()
