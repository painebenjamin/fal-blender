import os as _os
import sys as _sys

_vendor_dir = _os.path.join(_os.path.dirname(__file__), "vendor")
if _os.path.isdir(_vendor_dir) and _vendor_dir not in _sys.path:
    _sys.path.insert(0, _vendor_dir)

from . import preferences, app

def register() -> None:
    preferences.register()
    app.register()

def unregister() -> None:
    preferences.unregister()
    app.unregister()