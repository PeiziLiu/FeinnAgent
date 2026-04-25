"""FeinnAgent built-in tools package.

Importing this module triggers registration of all built-in tools.
"""

from . import builtins, diagnostics, browser  # noqa: F401 — triggers registration
from .tmux import register_tmux_tools

# Register tmux tools if tmux binary is available on the system.
register_tmux_tools()
