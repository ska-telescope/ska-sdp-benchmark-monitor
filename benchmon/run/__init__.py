"""Package to gather run context."""

from .run_utils import RunUtils

__all__ = [
    "RunMonitor",
    "RunUtils",
]


def __getattr__(name):
    if name == "RunMonitor":
        from .run_monitor import RunMonitor

        return RunMonitor
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
