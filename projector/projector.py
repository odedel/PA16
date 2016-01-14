import os
import ast
import astor
import graphviz

from collections import namedtuple

GraphEdge = namedtuple('GraphEdge', ['from_', 'to', 'CorD'])  # Control or Dependency


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
    def __init__(self, statement, checked_vars):
        self.statement = statement
        self.checked_vars = checked_vars

    def __str__(self):
        return "%s\t\t%s" % (str(self.checked_vars).ljust(20), self.statement)


class GraphBuilder(ast.NodeVisitor):
    def __init__(self):
        self.nodes = []
        self.edges = []
        self.last_seen = {}
        self.first_seen = {}
        self._code_line = 0
        super(GraphBuilder, self).__init__()

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

        self.nodes.append(AssignNode(code, target, influence_vars))

        # Create dependency edge
        for dependency in influence_vars:
            self.edges.append(GraphEdge(self.last_seen[dependency], self._code_line, 'D'))

        # Update the seen list
        self.last_seen[target] = self._code_line

        # Update first seen
        if target not in self.first_seen:
            self.first_seen[target] = self._code_line

        self._code_line += 1

    def visit_If(self, node):
        starting_if_code_line = self._code_line

        # The test
        code = astor.codegen.to_source(ast.If(test=node.test, body=[], orelse=[]))
        checked_vars = []
        for tested in [node.test.left, node.test.comparators[0]]:
            if isinstance(tested, ast.Name):
                checked_vars.append(tested.id)
        self.nodes.append(ControlNode(code, checked_vars))

        # Then part
        self._build_and_merge_inner_graph(node.body)

        if not node.orelse:
            self.edges.append(GraphEdge(starting_if_code_line, self._code_line, 'C'))
        else:
            self._code_line += 1
            self.edges.append(GraphEdge(starting_if_code_line, self._code_line, 'C'))
            self._build_and_merge_inner_graph(node.orelse)

    def _build_and_merge_inner_graph(self, body):
        code = ''
        for statement in body:
            code += astor.codegen.to_source(statement) + os.linesep
        inner_graph = create_graph(code)

        # Merge graph and inner_graph
        self.nodes.extend(inner_graph.nodes)

        for first_seen_code_line in inner_graph.first_seen.values():
            self.edges.append(GraphEdge(self._code_line, first_seen_code_line + 1 + self._code_line, 'C'))

        self._code_line += 1
        for edge in inner_graph.edges:
            self.edges.append(GraphEdge(edge.from_ + self._code_line, edge.to + self._code_line, edge.CorD))
        self._code_line += len(body)




def print_graph_nodes(nodes):
    print "%s\t%s%s" % ("influenced".ljust(10), "influenced by".ljust(20), "statement")
    for g in nodes:
        print g


def create_graph(original_code):
    builder = GraphBuilder()
    builder.visit(ast.parse(original_code))

    print_graph_nodes(builder.nodes)
    print os.linesep, 'Edges: ', builder.edges, os.linesep

    return builder


def create_projected_variable_path(program_graph, projected_variable):
    mappy = {}
    required = set()
    for x, y, d in program_graph.edges:
        if y not in mappy:
            mappy[y] = []
        mappy[y].append(x)

    for i in xrange(len(program_graph.nodes)):
        pos = len(program_graph.nodes) - i - 1
        g = program_graph.nodes[pos]
        if (isinstance(g, AssignNode) and g.assigned_var is projected_variable) or pos in required:
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
    with file(r'..\Tests\test3.py') as f:
        original_code = f.read()

    projected_code = project(original_code, 'z')

    print 'The projected program:'
    for i in projected_code:
        print i


if __name__ == '__main__':
    main()
