name = 'test9'

code = """
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


control_edges = [(0, 1), (1, 2), (2, 3), (3, 4), (3, 15), (4, 5), (5, 6), (6, 7), (7, 8), (8, 9), (8, 12), (9, 10), (10, 3), (12, 13), (13, 14), (14, 3), (15, 16)]
dep_edges = []