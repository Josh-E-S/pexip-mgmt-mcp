"""Tool modules — one per Pexip resource family.

Each module decorates async functions with `@mcp.tool(...)`; importing the module
is what registers those tools with the shared FastMCP server. `server.py` does
that wiring by importing every module in this package.
"""
