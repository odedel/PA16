import sys
sys.path.insert(0, '../projector')
import pytest
from projector.projector import create_graph, Edge, create_projected_variable_path

code_1 = """
x = 5
y = 6
z = x + 3
w = y
y = 2
k = x + y
x = 1
a=1
b=a
c=b
d=c*b
"""

parameters_1 = [
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

control_edges_1 = [Edge(x,y) for x,y in [(0, 1), (1, 2), (2, 3), (3, 4), (4, 5), (5, 6), (6, 7), (7, 8), (8, 9), (9, 10), (10, 11)]]
dep_edges_1 = [Edge(x,y) for x,y in [(0, 2), (1, 3), (0, 5), (4, 5), (7, 8), (8, 9), (8, 10), (9, 10)]]

code_3 = """
x = 5
y = x + 5
z = 512
if x > 3:
    x = y + 5
    x = y + z
    m = x + z
    y = 123
h = z + m
i = x + y
"""

parameters_3 = [
    ("x", [0, 1, 2, 3, 4, 5]),
    ("y", [0, 1, 3, 7]),
    ("z", [2]),
    ("m", [0, 1, 2, 3, 5, 6]),
    ("h", [0, 1, 2, 3, 5, 6, 8]),
    ("i", [0, 1, 2, 3, 5, 7, 9]),
]

control_edges_3 = [Edge(x,y) for x,y in [(0, 1), (1, 2), (2, 3), (3, 4), (3, 8), (4, 5), (5, 6), (6, 7), (7, 8), (8, 9), (9, 10)]]
dep_edges_3 = [Edge(x,y) for x,y in [(0, 1), (0, 3), (1, 4), (1, 5), (2, 5), (5, 6), (2, 6), (2, 8), (6, 8), (0, 9), (1, 9), (5, 9), (7, 9)]]

code_4 = """
x = 5
y = 6
if x > 4:
    h = x
else:
    h = y
t = h + x
"""

parameters_4 = [
    ("x", [0]),
    ("y", [1]),
    #FIXME - ("h", [0, 1, 2, 3, 5]),
    #FIXME - ("t", [0, 1, 2, 3, 5, 6]),
]

control_edges_4 = [Edge(x,y) for x,y in [(0, 1), (1, 2), (2, 3), (2, 5), (3, 6), (5, 6), (6, 7)]]
dep_edges_4 = [Edge(x,y) for x,y in [(0, 2), (0, 3), (1, 5), (0, 6), (3, 6), (5, 6)]]

code_5 = """
x = 2
x = x + x
x
"""

control_edges_5 = [Edge(x,y) for x,y in [(0, 1), (1, 2), (2, 3)]]
dep_edges_5 = [Edge(x,y) for x,y in [(0, 1), (1, 2)]]

code_6 = """
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

control_edges_6 = [Edge(x,y) for x,y in [(0, 1), (1, 2), (2, 3), (3, 4), (4, 5), (5, 12), (4, 7), (2, 9), (9, 10), (10, 11), (7, 12), (11, 12), (10, 12), (12, 13)]]
dep_edges_6 = [Edge(x,y) for x,y in [(0, 2), (1, 2), (0, 3), (3, 4), (1, 4), (3, 5), (1, 7), (1, 9), (9, 10), (0, 10), (9, 11), (3, 12), (9, 12)]]

code_7 = """
x = 2
t = 124
counter = 0
while t < x:
    t = t + 5
    x = 2
    t = t + 5
    counter = counter + 1
t
"""

control_edges_7 = [Edge(x,y) for x,y in [(0, 1), (1, 2), (2, 3), (3, 4), (4, 5), (5, 6), (6, 7), (7, 3), (3, 8), (8, 9)]]
dep_edges_7 = [Edge(x,y) for x,y in [(0, 3), (1, 3), (1, 4), (4, 6), (2, 7), (6, 3), (5, 3), (6, 4), (7, 7), (6, 8), (1, 8)]]

code_8 = """
x = 2
if x > x:
    x = 5
x
"""

control_edges_8 = [Edge(x,y) for x,y in [(0, 1), (1, 2), (2, 3), (3, 4), (1, 3)]]
dep_edges_8 = [Edge(x,y) for x,y in [(0, 1), (0, 3), (2, 3)]]

code_9 = """
x = 2
t = 124
counter = 0
while t < x:
    t = t + 5
    x = 2
    t = t + 5
    counter = counter + 1
    if t > x:
        t = t - counter
        counter = counter + x
    else:
        x = x + 100
        counter = counter - 1
        t = counter + x
t
"""


control_edges_9 = [Edge(x,y) for x,y in [(0, 1), (1, 2), (2, 3), (3, 4), (3, 15), (4, 5), (5, 6), (6, 7), (7, 8), (8, 9), (8, 12), (9, 10), (10, 3), (12, 13), (13, 14), (14, 3), (15, 16)]]
dep_edges_9 = [Edge(x,y) for x,y in [(0, 3), (1, 3), (1, 4), (4, 6), (2, 7), (5, 8), (6, 8), (6, 9), (7, 9), (5, 12), (7, 13), (13, 14), (12, 14), (9, 15),
             (9, 3), (14, 3), (5, 3), (12, 3), (9, 4), (14, 4), (10, 7), (13, 7), (5, 10), (7, 10), (1, 15), (14, 15)]]

tests = [
         (code_1, control_edges_1, dep_edges_1, parameters_1),
         (code_3, control_edges_3, dep_edges_3, parameters_3),
         (code_4, control_edges_4, dep_edges_4, parameters_4),
         #(code_5, control_edges_5, dep_edges_5),
         #(code_6, control_edges_6, dep_edges_6),
         #(code_7, control_edges_7, dep_edges_7),
         #(code_8, control_edges_8, dep_edges_8),
         #(code_9, control_edges_9, dep_edges_9),
         ]


def compare_lists(l1, l2):
    sl1 = sorted(list(set(l1)))
    sl2 = sorted(list(set(set(l2))))

    assert len(sl1) == len(sl2)
    for i in xrange(len(sl1)):
        assert sl1[i] == sl2[i], "arrays differ at location %d [%s] - [%s]" % (i, sl1, sl2)


@pytest.mark.parametrize("code, control_edges, dep_edges, parameters", tests)
def test_var(code, control_edges, dep_edges, parameters):
    graph = create_graph(code)
    compare_lists(graph.control_edges, control_edges)
    compare_lists(graph.dep_edges, dep_edges)
    for val, deps in parameters:
        projection = create_projected_variable_path(graph, val)
        compare_lists(projection, deps)


