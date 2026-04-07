import pytest
from tests.FunctionExtractor import FunctionExtractor


@pytest.fixture(scope="class", autouse=True)
def get_funcs(request):
    submission_path = request.config.getoption("--submission_path")
    if not submission_path:
        raise ValueError("submission_path must be provided via --submission_path")
    fe = FunctionExtractor(submission_path)
    funcs = {f: fe.get_function(f) for f in ["function1", "function2"]}  # Add more function names as needed
    return funcs


class TestA0:
    
    @pytest.mark.timeout(5)
    def test_0(self, get_funcs):
        """Test 0"""
        expected = None  # Replace with expected value
        actual = get_funcs["function1"](None)  # Replace with appropriate function call
        assert expected == actual, f"Expected {expected}, got {actual}"
    