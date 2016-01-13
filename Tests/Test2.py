import sys
sys.path.insert(0, '../projector')
import pytest
from projector.projector import project_l

code_1 = [
        "x = 5",
        "y = 6",
        "z = x + 3",
        "w = y",
        "y = 2",
        "k = x + y",
        "x = 1",
        "a=1",
        "b=a",
        "c=b",
        "d=c*b",
    ]


@pytest.mark.parametrize("code, var, expected_lines", [
    (code_1, "x", [0, 6]),
    (code_1, "y", [1, 4]),
    (code_1, "z", [0, 2]),
    (code_1, "w", [1, 3]),
    (code_1, "k", [0, 4, 5]),
    (code_1, "a", [7]),
    (code_1, "b", [7, 8]),
    (code_1, "c", [7, 8, 9]),
    (code_1, "d", [7, 8, 9, 10]),
])
def test_var(code, var, expected_lines):
    projection = project_l("\n".join(code), var)
    assert len(projection) == len(expected_lines), "Expected %s but got %s" % (expected_lines, projection)
    assert len(set(projection).intersection(expected_lines)) == len(expected_lines), "Expected %s but got %s" % (expected_lines, projection)


