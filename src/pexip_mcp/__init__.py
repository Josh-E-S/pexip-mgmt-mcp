"""MCP server for the Pexip Infinity Management API.

Pexip Infinity is a self-hosted video conferencing platform; its Management API
is the admin REST API exposed by the Management Node at /api/admin/. MCP (Model
Context Protocol) is the JSON-RPC protocol an LLM client (Claude Desktop, etc.)
speaks to call our tools. This package wraps the former so the latter can drive it.
"""

__version__ = "0.1.0"
