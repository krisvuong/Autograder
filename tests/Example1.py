import pytest
from tests.FunctionExtractor import FunctionExtractor


def try_assert(expected, actual, request, cast_to=int):
    # Correct value, correct type
    if expected == actual:
        return
    
    if cast_to != bool:
        # Try casting student's answer to expected type
        try:
            casted_actual = cast_to(actual)
        except Exception as e:
            casted_actual = None
            print(f"Could not cast actual value {actual} to expected type {cast_to}: {e}.")

        # Correct value, wrong type
        if expected == casted_actual:
            request.node.user_properties.append(("partial_pass", True))
            pytest.partial(f"Expected {expected!r}, got {actual!r}. (-0.5 marks)")
            return

    # Wrong value
    pytest.fail(f"Expected {expected!r}, got {actual!r}. (-1 mark)")


@pytest.fixture(scope="function")
def get_funcs(request):
    submission_path = request.config.getoption("--submission_path")
    if not submission_path:
        raise ValueError("submission_path must be provided via --submission_path")
    fe = FunctionExtractor(submission_path)

    # Load all functions once
    funcs = {f: fe.get_function(f) for f in ["function1", "function2"]}  # Add more function names as needed
    
    # Re-inject dependencies into their globals
    # Handles cases where functions call each other
    for func in funcs.values():
        func.__globals__.update(funcs)

    return funcs


class TestA1:
    
    # ---------- Tests for test_function_1 ----------
    @pytest.mark.timeout(5)
    def test_function_1(self, get_funcs, request):
        """Assert function1("10") == True"""
        expected = True
        actual = get_funcs["function1"]("10")
        try_assert(expected, actual, request, bool)
