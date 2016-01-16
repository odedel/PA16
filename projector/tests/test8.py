name = 'test8'

code = """
x = 2
if x > x:
    x = 5
x
"""

control_edges = [(0, 1), (1, 2), (2, 3), (3, 4), (1, 3)]
dep_edges = [(0, 1), (0, 3), (2, 3)]
