import subprocess
from graphviz import Digraph
import errno


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

def visualize(graph, out_path):
    visualize_edges(graph, out_path + "_control", True, False)
    visualize_edges(graph, out_path + "_dep", False, True)
    visualize_edges(graph, out_path + "_all", True, True)


def visualize_edges(graph, out_file, control_edges, dep_edges):
    nodes = graph.nodes
    dot = Digraph(comment='Graph')
    #nodes = []
    row_height = 50
    indent_len = 50
    max_height = len(nodes) * row_height

    known_nodes = []

    def get_height(row_num):
        return max_height - row_num * row_height

    for edges, is_control in [(graph.control_edges, True), (graph.dep_edges, False)]:
        for edge in edges:
            if (is_control and control_edges) or (not is_control and dep_edges):
                x, y = edge.from_, edge.to
                # x_node = pydot.Node("Node B", style="filled", fillcolor="green")
                if x not in known_nodes:
                    dot.node(str(x), nodes[x].statement, color="black", pos="%d,%d" % (nodes[x].indent * indent_len, get_height(x)))
                # print nodes[x].statement
                if y < len(nodes):
                    if y not in known_nodes:
                        dot.node(str(y), nodes[y].statement, pos="%d,%d" % (nodes[y].indent * indent_len, get_height(y)))
                    if not is_control:
                        dot.edge(str(x), str(y), color="green", style="dashed")
                    elif edge.jmp_true is None:
                        dot.edge(str(x), str(y), color="black")
                    elif edge.jmp_true is True:
                        dot.edge(str(x), str(y), color="blue")
                    else:
                        dot.edge(str(x), str(y), color="red")
    # apply_styles(dot, styles)
    dot.engine = "neato"
    dot.save(out_file, None)

    cmd = "neato.exe -Tpdf -O -n2 -Goverlap=false -Gsplines=true " + out_file

    try:
        returncode = subprocess.Popen(cmd).wait()
    except OSError as e:
        if e.errno == errno.ENOENT:
            raise RuntimeError('failed to execute %r, '
                'make sure the Graphviz executables '
                'are on your systems\' path' % cmd)
        else:
            raise
