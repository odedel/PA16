name = 'test6'

code = """
x = 5
y = 7
if x > y:
    h = x + 5
    if h > y:
        m = h
    else:
        m = y
else:
    h = y + 5
    if h > x:
        m = h
h
"""

control_edges = [(0, 1), (1, 2), (2, 3), (3, 4), (4, 5), (5, 12), (4, 7), (2, 9), (9, 10), (10, 11), (7, 12), (11, 12), (10, 12), (12, 13)]
dep_edges = [(0, 2), (1, 2), (0, 3), (3, 4), (1, 4), (3, 5), (1, 7), (1, 9), (9, 10), (0, 10), (9, 11), (3, 12), (9, 12)]