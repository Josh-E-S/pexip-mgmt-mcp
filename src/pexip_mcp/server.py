"""MCP server entry point. Importing this module is what wires up every tool.

Each module under `pexip_mcp.tools.*` calls `@mcp.tool(...)` at import time, which
registers that function with the FastMCP server instance. So just importing them
here (even though we never reference the names) is what makes the server know
about them — that's why the F401 noqa is needed.
"""
from pexip_mcp.mcp_app import mcp

# Use these imports for their side effect only: each module's @mcp.tool() decorators
# register its tools onto the shared `mcp` instance when Python loads the module.
from pexip_mcp.tools import (  # noqa: F401
    alias,
    automatic_participant,
    command,
    conference,
    device,
    end_user,
    gateway_rule,
    global_settings,
    history,
    infrastructure,
    ivr_theme,
    ldap,
    resource_crud,
    schema,
    status,
)

__all__ = ["mcp"]
