from graphviz import Digraph

styles = {
    'graph': {
        'label': 'A Fancy Graph',
        'fontsize': '16',
        'fontcolor': 'white',
        #'bgcolor': '#333333',
        #'rankdir': 'BT',
    },
    'nodes': {
        'fontname': 'Helvetica',
        'shape': 'hexagon',
        'fontcolor': 'white',
        'color': 'white',
        'style': 'filled',
        'fillcolor': '#006699',
    },
    'edges': {
        #'style': 'dashed',
        'color': 'blue',
        'arrowhead': 'open',
        'fontname': 'Courier',
        'fontsize': '12',
        'fontcolor': 'white',
    }
}

def apply_styles(graph, styles):
    graph.graph_attr.update(
        ('graph' in styles and styles['graph']) or {}
    )
    graph.node_attr.update(
        ('nodes' in styles and styles['nodes']) or {}
    )
    graph.edge_attr.update(
        ('edges' in styles and styles['edges']) or {}
    )
    return graph

def visualize(graph):
    visualize_edges(graph.control_edges, graph.nodes)


def visualize_edges(edges, nodes):
    dot = Digraph(comment='Graph')
    #nodes = []
    for edge in edges:
        x, y = edge.from_, edge.to
        # x_node = pydot.Node("Node B", style="filled", fillcolor="green")
        if nodes[x].statement == 'if (t < x):':
            i = 1
        dot.node(str(x), nodes[x].statement, color="black")
        print nodes[x].statement
        if y < len(nodes):
            dot.node(str(y), nodes[y].statement)
            if edge.jmp_true is None:
                dot.edge(str(x), str(y), color="black")
            elif edge.jmp_true is True:
                dot.edge(str(x), str(y), color="blue")
            else:
                dot.edge(str(x), str(y), color="red")
    # apply_styles(dot, styles)
    dot.render(r"T:\out.gv", view=False)

