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


# 0->1, 0->3, 1->4, 1 -> 5, 2->5, 5->6, 2->6, 2->8, 6->8, 0->9, 1->9, 5->9, 7->9
# 0->1, 0->3, 1->4, 1 -> 5, 2->5, 5->6, 2->6,       6->8,