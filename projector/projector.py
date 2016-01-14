import ast
import astor
import graphviz

from collections import namedtuple


class GraphNode(object):
    pass


class AssignNode(GraphNode):
    def __init__(self, statement, assigned_var, influence_vars=[]):
        self.statement = statement
        self.assigned_var = assigned_var
        self.influence_vars = influence_vars

    def __repr__(self):
        return '(%s, %s, %s)' % (self.statement, self.assigned_var, self.influence_vars)

    def __str__(self):
        return "%s\t%s%s" % (self.assigned_var.ljust(10), str(self.influence_vars).ljust(20), self.statement)


class ControlNode(GraphNode):
    def __init__(self, statement, checked_vars=[]):
        self.statement = statement
        self.checked_vars = checked_vars

    def __str__(self):
        return "%s\t\t%s" % (str(self.checked_vars).ljust(20), self.statement)


class ASTWalker(ast.NodeVisitor):
    def __init__(self, graph_nodes=[], graph_edges=[], code_line=0, last_seen={}):
        self.graph_nodes = graph_nodes
        self.graph_edges = graph_edges
        self.code_line = code_line
        self.last_seen = last_seen
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

        self.graph_nodes.append(AssignNode(code, target, influence_vars))

        # Create dependency edge
        for dependency in influence_vars:
            self.graph_edges.append((self.last_seen[dependency], self.code_line))

        # Update the seen list
        self.last_seen[target] = self.code_line

        self.code_line += 1


def print_graph_nodes(nodes):
    print "%s\t%s%s" % ("influenced".ljust(10), "influenced by".ljust(20), "statement")
    for g in nodes:
        print g


def create_graph(original_code):
    walker = ASTWalker()
    walker.visit(ast.parse(original_code))

    print_graph_nodes(walker.graph_nodes)

    ProgramGraph = namedtuple('ProgramGraph', ['nodes', 'edges'])
    return ProgramGraph(walker.graph_nodes, walker.graph_edges)


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


if __name__ == '__main__':
    main()