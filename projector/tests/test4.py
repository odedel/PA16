name = 'test4'

code = """
x = 5
y = 6
if x > 4:
    h = x
else:
    h = y
t = h + x
"""

dep_edges = [(0, 2), (0, 3), (1, 5), (0, 6), (3, 6), (5, 6)]
control_edges = [(0, 1), (1, 2), (2, 3), (2, 5), (3, 6), (5, 6), (6, 7)]