name = 'test5'

code = """
x = 2
x = x + x
x
"""

control_edges = [(0, 1), (1, 2), (2, 3)]
dep_edges = [(0, 1), (1, 2)]
