import sys
sys.path.insert(0, '../projector')

from projector.projector import project_l


def check_var(code, var, expected_lines):
    projection = project_l("\n".join(code), var)
    assert len(projection) == len(expected_lines), "Expected %s but got %s" % (expected_lines, projection)
    assert len(set(projection).intersection(expected_lines)) == len(expected_lines), "Expected %s but got %s" % (expected_lines, projection)


def test_projection():
    code = [
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
    check_var(code, "x", [0, 6])
    check_var(code, "y", [1, 4])
    check_var(code, "z", [0, 2])
    check_var(code, "w", [1, 3])
    check_var(code, "k", [0, 4, 5])
    check_var(code, "a", [7])
    check_var(code, "b", [7, 8])
    check_var(code, "c", [7, 8, 9])
    check_var(code, "d", [7, 8, 9, 10])

