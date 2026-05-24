"""
MCP server configuration (Task 1 — infrastructure).

This defines HOW to launch the official, ready-made MCP server.
The Task 2 client reads this config to spawn and connect to the server.

Server: @modelcontextprotocol/server-filesystem (official Anthropic MCP server)
Transport: stdio — the server runs as a subprocess; the client talks to it
           over stdin/stdout.
Scope: the server is sandboxed to the documents/ folder, so it can access
       both policies/ and contracts/ but nothing else on disk.
"""

import os
from backend.config import PROJECT_ROOT

DOCUMENTS_DIR = os.path.join(PROJECT_ROOT, "documents")

# Launch parameters for the official MCP filesystem server.
# A client spawns it with: command + args, then speaks MCP over stdio.
MCP_FILESYSTEM_SERVER = {
    "command": "npx",
    "args": ["-y", "@modelcontextprotocol/server-filesystem", DOCUMENTS_DIR],
}
