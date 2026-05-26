"""
GUI Package

This package contains the graphical user interface components.
"""

__all__ = [
    'dialogs',
    'widgets',
    'panels'
]

def __getattr__(name):
    if name == 'dialogs':
        from . import dialogs as _dialogs
        return _dialogs
    if name == 'widgets':
        from . import widgets as _widgets
        return _widgets
    if name == 'panels':
        from . import panels as _panels
        return _panels
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
