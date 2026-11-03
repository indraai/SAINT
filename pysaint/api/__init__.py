"""Web API and browser UI for pySAINT (Step 2).

Install with ``pip install -e '.[web]'`` and start with ``saint serve``.
"""

from .app import create_app

__all__ = ["create_app"]
