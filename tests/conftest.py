import pytest
from pytest_html import extras
from MarkCollector import MarkCollector

collector = MarkCollector()

class PartialTestError(AssertionError):
    """Raised to indicate a partial pass result."""
    pass


def partial(msg: str = ""):
    """Mark a test as partially passed."""
    raise PartialTestError(msg)


pytest.partial = partial  # allows pytest.partial("...") to be called in tests

def pytest_sessionstart(session):
    """Reset collector at the beginning of each session."""
    collector.reports = []
    collector.collected = 0

def pytest_addoption(parser):
    parser.addoption(
        "--submission_path",
        action="store",
        default=None,
        help="Path to student submission file"
    )
    parser.addoption(
        "--report-title",
        action="store",
        default="Test Report",
        help="Set a custom title for the pytest-html report"
    )

def pytest_metadata(metadata):
    """
    Called by pytest-metadata plugin with the metadata dict.
    Clear it (so Environment is empty), or modify as you like.
    """
    metadata.clear()

@pytest.hookimpl(hookwrapper=True)
def pytest_runtest_makereport(item, call):
    outcome = yield
    report = outcome.get_result()

    # Decorate nodeid
    test_fn = item.obj
    func_name = test_fn.__name__
    docstring = getattr(test_fn, "__doc__")
    if docstring:
        report.nodeid = f"{func_name} - {docstring.strip()}"
    else:
        report.nodeid = func_name

    # Track in collector
    if report.when == "call":
        collector.reports.append(report)

def pytest_collection_modifyitems(items):
    collector.collected = len(items)

def pytest_html_report_title(report):
    config = report.config
    title = config.getoption("--report-title")
    report.title = title

def pytest_html_results_summary(prefix, summary, postfix):
    total = collector.collected
    passed = sum(1 for r in collector.reports if r.outcome == "passed")
    grade = round((passed / total) * 100, 2) if total > 0 else 0
    # summary.append(f"<div><b>Grade: {passed}/{total} = {grade}%</b></div>")

