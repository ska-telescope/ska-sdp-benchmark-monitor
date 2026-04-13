"""conftest file."""


def pytest_collection_modifyitems(session, config, items):
    """Define order for testing files."""
    file_order = [
        "tests/test_flake8.py",
        "tests/test_run_monitor.py",
        "tests/test_benchmon-run.py",
        "tests/test_benchmon-visu.py",
        "tests/test_visualizer.py",
        "tests/test_hp_collector.py",
        "tests/test_benchmon-visu_func.py",
        "tests/test_g5k.py",
        "tests/test_metrics.py",
    ]

    def sort_key(item):
        try:
            return file_order.index(item.location[0])
        except ValueError:
            return len(file_order)

    items.sort(key=sort_key)
