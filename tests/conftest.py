"""conftest file"""


def pytest_collection_modifyitems(session, config, items):
    """Define order for testing files"""
    file_order = [
        "tests/test_flake8.py",
        "tests/test_run_monitor.py",
        "tests/test_benchmon-run.py",
        "tests/test_benchmon-visu.py",
        "tests/test_visualizer.py",
        "tests/test_benchmon-visu_func.py",
        "tests/test_g5k.py",
        "tests/test_metrics.py"
    ]

    items.sort(key=lambda item: file_order.index(item.location[0]))
