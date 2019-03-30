from fauxcaml import build


def handle_return_code_int_comparison(expected: int, actual: build.ExitCodeResult):
    return [
        f"Comparing executable program exit codes:",
        f"    {actual} != {expected}",
    ]


def pytest_assertrepr_compare(op, left, right):
    if isinstance(left, build.ExitCodeResult) and isinstance(right, int) and op == "==":
        return handle_return_code_int_comparison(right, left)
    if isinstance(right, build.ExitCodeResult) and isinstance(left, int) and op == "==":
        return handle_return_code_int_comparison(left, right)
