import pytest
from tests.FunctionExtractor import FunctionExtractor


@pytest.fixture(scope="class", autouse=True)
def get_funcs(request):
    submission_path = request.config.getoption("--submission_path")
    if not submission_path:
        raise ValueError("submission_path must be provided via --submission_path")
    fe = FunctionExtractor(submission_path)
    funcs = {f: fe.get_function(f) for f in ["function1"]}  # Add more function names as needed
    return funcs


class TestA0:
    
    @pytest.mark.timeout(5)
    def test_function_1(self, get_funcs):
        """Assert function1(0,0) == 5"""
        expected = 5
        actual = get_funcs["function1"](0, 0)
        assert expected == actual, f"Expected {expected}, got {actual}"
    