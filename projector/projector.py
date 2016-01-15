import os
import ast
import astor

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
        self.dep_edges = []
        self.control_edges = []
        self.last_seen = {}
        self.unknown_vars = {}
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
            if dependency not in self.last_seen:
                if dependency in self.unknown_vars:
                    self.unknown_vars[dependency].append(self._code_line)
                else:
                    self.unknown_vars[dependency] = [self._code_line]
            else:
                self._create_dep_edge(dependency, self._code_line)

        # Create control edge
        self.control_edges.append(GraphEdge(self._code_line, self._code_line+1, 'C'))

        # Update the seen list
        self.last_seen[target] = [self._code_line]

        self._code_line += 1

    def visit_If(self, node):
        starting_if_code_line = self._code_line

        # The test
        code = astor.codegen.to_source(ast.If(test=node.test, body=[], orelse=[]))
        checked_vars = []
        for tested in [node.test.left, node.test.comparators[0]]:
            if isinstance(tested, ast.Name):
                checked_vars.append(tested.id)
                self._create_dep_edge(tested.id, self._code_line)
        self.nodes.append(ControlNode(code, checked_vars))

        # Then part
        self.control_edges.append(GraphEdge(starting_if_code_line, self._code_line + 1, 'C'))
        last_seen_then_part, unknown_then_part = self._build_and_merge_inner_graph(node.body)

        # Create dep edges from inner to outer
        for var in unknown_then_part:
            for inner_code_line in unknown_then_part[var]:
                for outer_code_line in self.last_seen[var]:
                    self.dep_edges.append(GraphEdge(outer_code_line, inner_code_line, 'D'))

        if not node.orelse:
            self.control_edges.append(GraphEdge(starting_if_code_line, self._code_line + 1, 'C'))
            self.control_edges.append(GraphEdge(self._code_line, self._code_line + 1, 'C'))

            # Update last seen
            for var, code_lines in last_seen_then_part.iteritems():
                for code_line in code_lines:
                    if var in self.last_seen:
                        self.last_seen[var].append(code_line)
                    else:
                        self.last_seen[var] = [code_line]
        else:
            self.control_edges.append(GraphEdge(self._code_line, self._code_line + len(node.orelse) + 2, 'C'))  # Create edge from 'then' skipping the 'else'
            self._code_line += 1
            self.control_edges.append(GraphEdge(starting_if_code_line, self._code_line + 1, 'C'))
            last_seen_else_part, unknown_else_part = self._build_and_merge_inner_graph(node.orelse)
            self.control_edges.append(GraphEdge(self._code_line, self._code_line+1, 'C'))

            # Create dep edges from inner to outer
            for var in unknown_else_part:
                for inner_code_line in unknown_else_part[var]:
                    for outer_code_line in self.last_seen[var]:
                        self.dep_edges.append(GraphEdge(outer_code_line, inner_code_line, 'D'))

            # Update last seen
            for var in last_seen_then_part:
                if var not in last_seen_else_part and var not in self.last_seen:
                    self.last_seen[var] = last_seen_then_part[var]
                elif var in last_seen_else_part:
                    self.last_seen[var] = last_seen_then_part[var] + last_seen_else_part[var]
                elif var not in last_seen_else_part:
                    self.last_seen[var].extend(last_seen_then_part[var])

            for var in last_seen_else_part:
                if var not in last_seen_then_part and var not in self.last_seen:
                    self.last_seen[var] = last_seen_else_part[var]
                elif var not in last_seen_then_part:
                    self.last_seen[var].extend(last_seen_else_part[var])

        self._code_line += 1

    def _create_dep_edge(self, var, to):
        for code_line in self.last_seen[var]:
            self.dep_edges.append(GraphEdge(code_line, to, 'D'))

    def _build_and_merge_inner_graph(self, body):
        code = ''
        for statement in body:
            code += astor.codegen.to_source(statement) + os.linesep
        inner_graph = create_graph(code)

        # Merge graph and inner_graph
        self.nodes.extend(inner_graph.nodes)

        # Delete last control edge
        inner_graph.control_edges = inner_graph.control_edges[:-1]

        for edge in inner_graph.control_edges:
            self.control_edges.append(GraphEdge(edge.from_ + self._code_line + 1, edge.to + self._code_line + 1, 'C'))
        for edge in inner_graph.dep_edges:
            self.dep_edges.append(GraphEdge(edge.from_ + self._code_line + 1, edge.to + self._code_line + 1, 'D'))

        # Update unknown
        for var in inner_graph.unknown_vars:
            fixed_code_lines = []
            for code_line in inner_graph.unknown_vars[var]:
                fixed_code_lines.append(code_line + self._code_line + 1)
            inner_graph.unknown_vars[var] = fixed_code_lines

        # Update last seen
        for var in inner_graph.last_seen:
            fixed_code_lines = []
            for code_line in inner_graph.last_seen[var]:
                fixed_code_lines.append(code_line + self._code_line + 1)
            inner_graph.last_seen[var] = fixed_code_lines

        self._code_line += len(body)

        return inner_graph.last_seen, inner_graph.unknown_vars


def print_graph_nodes(nodes):
    print "%s\t%s%s" % ("influenced".ljust(10), "influenced by".ljust(20), "statement")
    for g in nodes:
        print g


def create_graph(original_code):
    builder = GraphBuilder()
    builder.visit(ast.parse(original_code))

    return builder


# def create_projected_variable_path(program_graph, projected_variable):
#     mappy = {}
#     required = set()
#     for x, y, d in program_graph.edges:
#         if y not in mappy:
#             mappy[y] = []
#         mappy[y].append(x)
#
#     for i in xrange(len(program_graph.nodes)):
#         pos = len(program_graph.nodes) - i - 1
#         g = program_graph.nodes[pos]
#         if (isinstance(g, AssignNode) and g.assigned_var is projected_variable) or pos in required:
#             required.add(pos)
#             if pos in mappy:
#                 required = required.union(mappy[pos])
#     required = list(required)
#
#     return sorted(required)


def build_program(program_graph, projected_path):
    program = []
    for i in projected_path:
        program.append(program_graph.nodes[i].statement)
    return program


def project(original_code, projected_variable):
    program_graph = create_graph(original_code)
    # projected_path = create_projected_variable_path(program_graph, projected_variable)
    # return build_program(program_graph, projected_path)

    print_graph_nodes(program_graph.nodes)
    print os.linesep, 'Control Edges: ', program_graph.control_edges, os.linesep
    print os.linesep, 'Dep Edges: ', program_graph.dep_edges, os.linesep


def main():
    with file(r'..\Tests\test4.py') as f:
        original_code = f.read()

    projected_code = project(original_code, 'z')

    # print 'The projected program:'
    # for i in projected_code:
    #     print i


if __name__ == '__main__':
    main()
