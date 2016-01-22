import ast
import os
import uuid
import astor

from graph_utils import visualize


class Edge(object):
    def __init__(self, from_, to, jmp_true=None):
        self.from_ = from_
        self.to = to
        self.jmp_true = jmp_true

    def __repr__(self):
        return '(%s, %s)' % (self.from_, self.to)

    def __hash__(self):
        return hash((self.from_, self.to))

    def __eq__(self, other):
        return other.from_ == self.from_ and other.to == self.to

    def __lt__(self, other):
        return other.from_ > self.from_ or (other.from_ == self.from_ and other.to > self.to)


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
        self.var_to_object = {}
        self.object_to_var = {}
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

        if node.orelse:
            self._code_line += 1
            self.nodes.append(ControlNode('else:', ''))
            self.control_edges.append(Edge(block_starting_line, self._code_line + 1))
            last_seen_else_part, else_code_length = self._build_and_merge_inner_graph(node.orelse)
            self._fix_control_edges_that_point_to_the_end_of_block(block_starting_line, block_starting_line + then_code_length,
                                                                   block_starting_line + then_code_length + else_code_length + 2)
        else:
            self.control_edges.append(Edge(block_starting_line, block_starting_line + then_code_length + 1))
            last_seen_else_part = {}
        self._merge_last_seen(last_seen_then_part, last_seen_else_part)

        self._code_line += 1

    def visit_While(self, node):
        block_starting_line = self._code_line

        self.control_edges.append(Edge(block_starting_line, self._code_line + 1))

        # First iteration
        self._create_condition_dependencies(node)
        last_seen_inner, loop_code_length = self._build_and_merge_inner_graph(node.body)
        self._merge_last_seen(last_seen_inner, {})

        # Any other iteration
        code = ''
        for statement in node.body:
            code += astor.codegen.to_source(statement) + os.linesep
        inner_graph = create_graph(code)
        self._find_unknown_variables(inner_graph.unknown_vars, block_starting_line)
        self._create_condition_dependencies(node, block_starting_line)
        self._fix_inner_code_lines(inner_graph.last_seen, block_starting_line)
        self._merge_last_seen(inner_graph.last_seen, {})

        # Add and Fix edges
        self._fix_control_edges_that_point_to_the_end_of_block(block_starting_line, block_starting_line + inner_graph.code_length, block_starting_line)

        self.control_edges.append(Edge(block_starting_line + loop_code_length, block_starting_line))
        self.control_edges.append(Edge(block_starting_line, block_starting_line + loop_code_length + 1))

        self._code_line += 1

    def _fix_control_edges_that_point_to_the_end_of_block(self, block_starting_line, block_end_line, right_pointing_line):
        """
        If mekunan fixes - edges the points from the if to else
        """
        for edge in self.control_edges:
            if edge.from_ > block_starting_line and edge.to == block_end_line + 1:
                edge.to = right_pointing_line

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
            self.last_seen[var] = list(set(self.last_seen[var]))

    def _handle_statement(self, node, update_last_seen=True):
        # Find target
        target = ''
        if isinstance(node, ast.Assign):
            if isinstance(node.targets[0], ast.Name):   # Assign to variable
                target = node.targets[0].id
            else:   # Assign to attribute
                target = node.targets[0].value.id + '#' + node.targets[0].attr

        self._create_statement_dependencies(node, target)
        self.control_edges.append(Edge(self._code_line, self._code_line+1))
        if update_last_seen:
            self.last_seen[target] = [self._code_line]
        self._code_line += 1

    def _create_dep_edge(self, influence_vars, to):
        for var in influence_vars:
            if var in self.last_seen:
                for code_line in self.last_seen[var]:
                    edge = Edge(code_line, to)
                    if edge not in self.dep_edges:
                        self.dep_edges.append(edge)
            else:
                if var in self.unknown_vars:
                    self.unknown_vars[var].append(self._code_line)
                else:
                    self.unknown_vars[var] = [self._code_line]

    def _create_statement_dependencies(self, node, target):
        """
        Find the dependency of the assign node and create an edge if possible, otherwise - append the dependency to unknown
        """
        code = astor.codegen.to_source(node)

        # Find the variables that influence on me variable dependencies
        influence_vars = set()
        if isinstance(node.value, ast.BinOp):
            for inner_disassembly in [node.value.right, node.value.left]:
                if isinstance(inner_disassembly, ast.Name):
                    influence_vars.add(inner_disassembly.id)
        elif isinstance(node.value, ast.Name):
            assigned_var = node.value.id
            influence_vars.add(assigned_var)
            # Find influencing attributes
            for other_var in self._get_vars_that_points_to_the_same_object(assigned_var) + [assigned_var]:
                for tmp_var in self.var_to_object.keys():
                    if other_var + '#' in tmp_var:
                        influence_vars.add(tmp_var)
        elif isinstance(node.value, ast.Call):      # Call to ctor
            obj = '#' + str(uuid.uuid4()) + '#' + node.value.func.id
            self.var_to_object[target] = set([obj])
            self.object_to_var[obj] = set([target])
        elif isinstance(node.value, ast.Attribute):
            influence_name = node.value.value.id
            influence_attribute = node.value.attr
            assigned_var = influence_name + '#' + influence_attribute
            influence_vars.add(assigned_var)
            # Find influencing attributes
            for var in self._get_vars_that_points_to_the_same_object(influence_name):
                other_var_with_attribute = var + '#' + influence_attribute
                if other_var_with_attribute in self.last_seen:
                    influence_vars.add(other_var_with_attribute)

        # If the target is attribute, the object declaration is also influence
        if '#' in target:
            name, attribute = target.split('#')
            influence_vars.add(name)

        tmp_list = []
        for var in influence_vars:
            if '#' in var:  # The influence variable is attribute, the declaration of the object is influencing too.
                name, attribute = var.split('#')
                tmp_list.append(name)
        influence_vars = influence_vars.union(set(tmp_list))

        # Find all the may influence vars using the abstract domain
        tmp_list = []
        for var in influence_vars:
            for other_var in self._get_vars_that_points_to_the_same_object(var):
                tmp_list.append(other_var)
        influence_vars = influence_vars.union(set(tmp_list))

        # Delete variables that doesn't exists
        tmp_list = []
        for var in influence_vars:
            if var not in self.last_seen:
                tmp_list.append(var)
        influence_vars = influence_vars.difference(set(tmp_list))

        print influence_vars

        self.nodes.append(StatementNode(code, target, influence_vars))
        self._create_dep_edge(influence_vars, self._code_line)

        print 'Unknown: ', self.unknown_vars

        # Update the abstract domain
        if isinstance(node, ast.Assign):    # Need to update the abstract domain
            if isinstance(node.value, ast.Name) or isinstance(node.value, ast.Attribute):
                self._delete_variable_from_abstract_domain(target)
                self.var_to_object[target] = set()
                for obj in self.var_to_object[assigned_var]:
                    self.object_to_var[obj].add(target)
                    self.var_to_object[target].add(obj)

    def _delete_variable_from_abstract_domain(self, target):
        for var in self.var_to_object.keys():
            if target is var:
                self._delete_object_to_var_entry(target)
                self.var_to_object.pop(var)
            if target + '#' in var:
                self._delete_object_to_var_entry(var)
                self.var_to_object.pop(var)

    def _delete_object_to_var_entry(self, target):
        for obj in self.var_to_object[target]:
            self.object_to_var[obj].remove(target)
            if not self.object_to_var[obj]:
                self.object_to_var.pop(target)

    def _get_vars_that_points_to_the_same_object(self, var):
        return_list = []
        if var in self.var_to_object:
            for obj in self.var_to_object[var]:
                for other_var in self.object_to_var[obj]:
                    return_list.append(other_var)

        while var in return_list:
            return_list.remove(var)

        return return_list

    def _create_condition_dependencies(self, node, code_line=None):
        code = astor.codegen.to_source(ast.If(test=node.test, body=[], orelse=[]))
        checked_vars = []
        for tested in [node.test.left, node.test.comparators[0]]:
            if isinstance(tested, ast.Name):
                checked_vars.append(tested.id)
        self._create_dep_edge(checked_vars, self._code_line if not code_line else code_line)
        self.nodes.append(ControlNode(code, checked_vars))

    def _build_and_merge_inner_graph(self, body):
        code = ''
        for statement in body:
            code += astor.codegen.to_source(statement) + os.linesep
        inner_graph = create_graph(code)

        self.nodes.extend(inner_graph.nodes)

        self._merge_edges(self.control_edges, inner_graph.control_edges)
        self._merge_edges(self.dep_edges, inner_graph.dep_edges)
        self._fix_inner_code_lines(inner_graph.last_seen)
        self._find_unknown_variables(inner_graph.unknown_vars)

        self._code_line += inner_graph.code_length

        return inner_graph.last_seen, inner_graph.code_length

    def _find_unknown_variables(self, unknown_vars, reference_code_line=None):
        self._fix_inner_code_lines(unknown_vars, reference_code_line)

        for var, inner_code_lines in unknown_vars.iteritems():
            for inner_code_line in inner_code_lines:
                if var in self.last_seen:
                    self._create_dep_edge([var], inner_code_line)
                else:
                    if var in self.unknown_vars:
                        self.unknown_vars[var].extend(inner_code_lines)
                    else:
                        self.unknown_vars[var] = inner_code_lines

    def _fix_inner_code_lines(self, inner_dict, reference_code_line=None):
        for var in inner_dict:
            fixed_code_lines = []
            for code_line in inner_dict[var]:
                fixed_code_lines.append(code_line + (self._code_line if not reference_code_line else reference_code_line) + 1)
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


def create_projected_variable_path(program_graph, projected_variable):
    dep_map = {}
    control_map = {}
    r_control_map = {}
    required = set()
    for edge in program_graph.dep_edges:
        if edge.to not in dep_map:
            dep_map[edge.to] = []
        dep_map[edge.to].append(edge.from_)
    for edge in program_graph.control_edges:
        if edge.from_ not in control_map:
            control_map[edge.from_] = []
        control_map[edge.from_].append(edge.to)
    for edge in program_graph.control_edges:
        if edge.to > edge.from_:
            if edge.to not in r_control_map:
                r_control_map[edge.to] = []
            r_control_map[edge.to].append(edge.from_)
    for i in xrange(len(program_graph.nodes)):
        pos = len(program_graph.nodes) - i - 1
        g = program_graph.nodes[pos]
        if (isinstance(g, StatementNode) and g.assigned_var is projected_variable) or pos in required:
            required.add(pos)

            if pos in r_control_map:
                prev = r_control_map[pos]

                while prev is not 0:
                    l = prev
                    for prev in l:
                        if len(control_map[prev]) > 1:
                            required.add(prev)
                            required = required.union(dep_map[prev])
                        if prev not in r_control_map:
                            break
                        prev = r_control_map[prev]
                if pos in dep_map:
                    required = required.union(dep_map[pos])
    required = list(required)
    return sorted(required)


def build_program(program_graph, projected_path):
    program = []
    for i in projected_path:
        program.append(program_graph.nodes[i].statement)
    return program


def project(original_code):
    program_graph = create_graph(original_code)

    print_graph_nodes(program_graph.nodes)
    print os.linesep, 'Control Edges: ', program_graph.control_edges, os.linesep
    print os.linesep, 'Dep Edges: ', program_graph.dep_edges, os.linesep
    return program_graph


def main():
    # with file(r'tests\test15.py') as f:
    #     original_code = f.read()
    #
    # project(original_code)

    projected_code = project("""
x = X()
y = Y()
x.a = y
y.b = Z()
x
""")
#     create_projected_variable_path(projected_code, "x")
#     visualize(projected_code)
    # print 'The projected program:'
    # for i in projected_code:
    #     print i


if __name__ == '__main__':
    main()
