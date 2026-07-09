"""Entry point for the MCPB (Claude Desktop one-click) bundle.

The bundle vendors the package and its dependencies under `server/lib` (see
build.sh). We make sure that directory is importable, then hand off to the
normal CLI entry point, which reads PEXIP_* from the environment the host sets
from the user_config prompts (see manifest.json).
"""
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "lib"))

from pexip_mcp.__main__ import main  # noqa: E402

if __name__ == "__main__":
    main()
