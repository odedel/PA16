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

parameters = [
    ("x", [0, 6]),
    ("y", [1, 4]),
    ("z", [0, 2]),
    ("w", [1, 3]),
    ("k", [0, 4, 5]),
    ("a", [7]),
    ("b", [7, 8]),
    ("c", [7, 8, 9]),
    ("d", [7, 8, 9, 10]),
]


@pytest.mark.parametrize("var, expected", parameters)
def test_var(var, expected):
    projection = project_l("\n".join(code_1), var)
    assert len(projection) == len(expected), "Expected %s but got %s" % (expected, projection)
    assert len(set(projection).intersection(expected)) == len(expected), "Expected %s but got %s" % (expected, projection)


