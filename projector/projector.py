import ast
import astor
import graphviz

from collections import namedtuple


class GraphNode(object):
    def __init__(self, statement, assigned_var, influence_vars=[]):
        self.statement = statement
        self.assigned_var = assigned_var
        self.influence_vars = influence_vars

    def __repr__(self):
        return '(%s, %s, %s)' % (self.statement, self.assigned_var, self.influence_vars)



class ASTWalker(ast.NodeVisitor):

    def __init__(self, graph_nodes=[]):
        self.graph_nodes = graph_nodes
        super(ASTWalker, self).__init__()

    def visit_Assign(self, node):
        target = node.targets[0].id
        code = astor.codegen.to_source(node)

        influence_vars = []
        if isinstance(node.value, ast.BinOp):
            for inner_disassembly in [node.value.right, node.value.left]:
                if isinstance(inner_disassembly, ast.Name):
                    influence_vars.append(inner_disassembly.id)
        elif isinstance(node.value, ast.Name):
            influence_vars.append(node.value.id)

        self.graph_nodes.append(GraphNode(code, target, influence_vars))


def create_graph(original_code):
    walker = ASTWalker()
    walker.visit(ast.parse(original_code))

    seen_variables_to_line_code = {}
    graph_edges = []
    for enumeration, node in enumerate(walker.graph_nodes):
        # Create edges
        for dependency in node.influence_vars:
            graph_edges.append((seen_variables_to_line_code[dependency], enumeration))

        # Update the seen list
        seen_variables_to_line_code[node.assigned_var] = enumeration

    ProgramGraph = namedtuple('ProgramGraph', ['nodes', 'edges'])
    return ProgramGraph(walker.graph_nodes, graph_edges)



def create_projected_variable_path(program_graph, projected_variable):
    mappy = {}
    required = set()
    for x, y in program_graph.edges:
        if y not in mappy:
            mappy[y] = []
        mappy[y].append(x)

    for i in xrange(len(program_graph.nodes)):
        pos = len(program_graph.nodes) - i - 1
        g = program_graph.nodes[pos]
        if g.assigned_var is projected_variable or pos in required:
            required.add(pos)
            if pos in mappy:
                required = required.union(mappy[pos])
    required = list(required)

    return sorted(required)


def build_program(program_graph, projected_path):
    program = []
    for i in projected_path:
        program.append(program_graph.nodes[i].statement)
    return program


def project(original_code, projected_variable):
    program_graph = create_graph(original_code)
    projected_path = create_projected_variable_path(program_graph, projected_variable)
    return build_program(program_graph, projected_path)


def main():
    with file(r'..\Tests\test1.py') as f:
        original_code = f.read()

    projected_code = project(original_code, 'd')

    for i in projected_code:
        print i


# def print_graph_nodes():
#     print "%s\t%s%s" % ("assigned".ljust(10), "influenced by".ljust(20), "statement")
#     for g in graph_nodes:
#         print "%s\t%s%s" % (str(g.assigned_var).ljust(10), str(g.influence_vars).ljust(20), g.statement)


if __name__ == '__main__':
    main()
    # print_graph_nodes()
