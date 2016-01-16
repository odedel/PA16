import os
import ast
import astor


class Edge(object):
    def __init__(self, from_, to):
        self.from_ = from_
        self.to = to

    def __repr__(self):
        return '(%s, %s)' % (self.from_, self.to)


class Node(object):
    pass


class StatementNode(Node):
    def __init__(self, statement, assigned_var, influence_vars=[]):
        self.statement = statement
        self.assigned_var = assigned_var
        self.influence_vars = influence_vars

    def __repr__(self):
        return '(%s, %s, %s)' % (self.statement, self.assigned_var, self.influence_vars)

    def __str__(self):
        return "%s\t%s%s" % (self.assigned_var.ljust(10), str(self.influence_vars).ljust(20), self.statement)


class ControlNode(Node):
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

    @property
    def code_length(self):
        return self._code_line

    def visit_Expr(self, node):
        self._handle_statement(node, False)

    def visit_Assign(self, node):
        self._handle_statement(node)

    def visit_If(self, node):
        block_starting_line = self._code_line

        self._create_condition_dependencies(node)

        # Then part
        self.control_edges.append(Edge(block_starting_line, self._code_line + 1))
        last_seen_then_part, then_code_length = self._build_and_merge_inner_graph(node.body)
        # self.control_edges.append(Edge(self._code_line, self._code_line + then_code_length + (2 if node.orelse else 1)))

        if node.orelse:
            self._code_line += 1
            self.control_edges.append(Edge(block_starting_line, self._code_line + 1))
            last_seen_else_part, else_code_length = self._build_and_merge_inner_graph(node.orelse)
            # self.control_edges.append(Edge(self._code_line, self._code_line+1))
            self._fix_then_control_edges_that_does_not_aware_to_else(block_starting_line, then_code_length, else_code_length)
        else:
            last_seen_else_part = {}
        self._merge_last_seen(last_seen_then_part, last_seen_else_part)

        self._code_line += 1

    def _fix_then_control_edges_that_does_not_aware_to_else(self, block_starting_line, then_code_length, else_code_length):
        """
        If mekunan fixes - edges the points from the if to else
        """
        for edge in self.control_edges:
            if edge.from_ > block_starting_line and edge.to == block_starting_line + then_code_length + 1:
                edge.to = block_starting_line + then_code_length + else_code_length + 2

    def _merge_last_seen(self, last_seen_then, last_seen_else):
        for var in set(last_seen_then.keys() + last_seen_else.keys()):
            if var in last_seen_then and var in last_seen_else or var not in self.last_seen:
                fixed_locations = []
                if var in last_seen_then:
                    fixed_locations.extend(last_seen_then[var])
                if var in last_seen_else:
                    fixed_locations.extend(last_seen_else[var])
                self.last_seen[var] = fixed_locations
            elif var in last_seen_then:
                self.last_seen[var].extend(last_seen_then[var])
            else:
                self.last_seen[var].extend(last_seen_else[var])

    def _handle_statement(self, node, update_last_seen=True):
            self._create_statement_dependencies(node)
            self.control_edges.append(Edge(self._code_line, self._code_line+1))
            if update_last_seen:
                self.last_seen[node.targets[0].id] = [self._code_line]
            self._code_line += 1

    def _create_dep_edge(self, influence_vars, to):
        for var in influence_vars:
            if var in self.last_seen:
                for code_line in self.last_seen[var]:
                    self.dep_edges.append(Edge(code_line, to))
            else:
                if var in self.unknown_vars:
                    self.unknown_vars[var].append(self._code_line)
                else:
                    self.unknown_vars[var] = [self._code_line]

    def _create_statement_dependencies(self, node):
        """
        Find the dependency of the assign node and create an edge if possible, otherwise - append the dependency to unknown
        """
        code = astor.codegen.to_source(node)

        # Find variable dependencies
        influence_vars = []
        if isinstance(node.value, ast.BinOp):
            for inner_disassembly in [node.value.right, node.value.left]:
                if isinstance(inner_disassembly, ast.Name):
                    influence_vars.append(inner_disassembly.id)
        elif isinstance(node.value, ast.Name):
            influence_vars.append(node.value.id)
        self.nodes.append(StatementNode(code, node.targets[0].id if isinstance(node, ast.Assign) else '', influence_vars))
        self._create_dep_edge(influence_vars, self._code_line)

    def _create_condition_dependencies(self, node):
        code = astor.codegen.to_source(ast.If(test=node.test, body=[], orelse=[]))
        checked_vars = []
        for tested in [node.test.left, node.test.comparators[0]]:
            if isinstance(tested, ast.Name):
                checked_vars.append(tested.id)
        self._create_dep_edge(checked_vars, self._code_line)
        self.nodes.append(ControlNode(code, checked_vars))

    def _build_and_merge_inner_graph(self, body):
        code = ''
        for statement in body:
            code += astor.codegen.to_source(statement) + os.linesep
        inner_graph = create_graph(code)

        self.nodes.extend(inner_graph.nodes)
        # inner_graph.control_edges = inner_graph.control_edges[:-1]

        self._merge_edges(self.control_edges, inner_graph.control_edges)
        self._merge_edges(self.dep_edges, inner_graph.dep_edges)
        self._fix_inner_code_lines(inner_graph.last_seen)
        self._find_unknown_variables(inner_graph.unknown_vars)

        self._code_line += inner_graph.code_length

        return inner_graph.last_seen, inner_graph.code_length

    def _find_unknown_variables(self, unknown_vars):
        self._fix_inner_code_lines(unknown_vars)

        for var, inner_code_lines in unknown_vars.iteritems():
            for inner_code_line in inner_code_lines:
                if var in self.last_seen:
                    for outer_code_line in self.last_seen[var]:
                        self.dep_edges.append(Edge(outer_code_line, inner_code_line))
                    else:
                        if var in self.unknown_vars:
                            self.unknown_vars[var].extend(inner_code_lines)
                        else:
                            self.unknown_vars[var] = inner_code_lines

    def _fix_inner_code_lines(self, inner_dict):
        for var in inner_dict:
            fixed_code_lines = []
            for code_line in inner_dict[var]:
                fixed_code_lines.append(code_line + self._code_line + 1)
            inner_dict[var] = fixed_code_lines

    def _merge_edges(self, outer_edges, inner_edges):
        for edge in inner_edges:
            outer_edges.append(Edge(edge.from_ + self._code_line + 1, edge.to + self._code_line + 1))


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
    with file(r'..\Tests\test6.py') as f:
        original_code = f.read()

    projected_code = project(original_code, 'z')

    # print 'The projected program:'
    # for i in projected_code:
    #     print i


if __name__ == '__main__':
    main()
