from .multi_node_visualizer import BenchmonMNSyncVisualizer
from .visualizer import BenchmonVisualizer

__all__ = [
    "BenchmonVisualizer",
    "BenchmonMNSyncVisualizer",
    "BenchmonInfluxDBVisualizer",
]

def __getattr__(name):
    if name == "BenchmonInfluxDBVisualizer":
        from .visualizer_influxdb import BenchmonInfluxDBVisualizer

        return BenchmonInfluxDBVisualizer
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
