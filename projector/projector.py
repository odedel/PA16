import ast
import os
import sys
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
    def __init__(self, statement, assigned_var, indent, influence_vars=[]):
        self.statement = statement
        self.assigned_var = assigned_var
        self.influence_vars = influence_vars
        self.indent = indent

    def __repr__(self):
        return '(%s, %s, %s)' % (self.statement, self.assigned_var, self.influence_vars)

    def __str__(self):
        return "%s\t%s%s" % (self.assigned_var.ljust(10), str(self.influence_vars).ljust(50), self.statement)


class ControlNode(Node):
    def __init__(self, statement, checked_vars, indent):
        self.statement = statement
        self.checked_vars = checked_vars
        self.indent = indent

    def __str__(self):
        return "%s\t%s" % (str(self.checked_vars).ljust(20), self.statement)


class GraphBuilder(ast.NodeVisitor):
    def __init__(self, indent_level):
        self.nodes = []
        self.dep_edges = []
        self.control_edges = []
        self.last_seen = {}
        self.unknown_vars = {}
        self.var_to_object = {}
        self.object_to_var = {}
        self._code_line = 0
        self.indent_level = indent_level
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
        self.control_edges.append(Edge(block_starting_line, self._code_line + 1, jmp_true=True))
        last_seen_then_part, then_code_length = self._build_and_merge_inner_graph(node.body)

        if node.orelse:
            self._code_line += 1
            self.nodes.append(ControlNode('else:', '', self.indent_level))
            self.control_edges.append(Edge(block_starting_line, self._code_line + 1, jmp_true=False))
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

        self.control_edges.append(Edge(block_starting_line, self._code_line + 1, jmp_true=True))

        # First iteration
        control_node = self._create_condition_dependencies(node)
        last_seen_inner, loop_code_length = self._build_and_merge_inner_graph(node.body)
        self._merge_last_seen(last_seen_inner, {})

        # Any other iteration
        code = ''
        for statement in node.body:
            code += astor.codegen.to_source(statement) + os.linesep
        inner_graph = create_graph(code, self.indent_level + 1)
        self._find_unknown_variables(inner_graph.unknown_vars, block_starting_line)
        self._create_condition_dependencies(node, block_starting_line, control_node)
        self._fix_inner_code_lines(inner_graph.last_seen, block_starting_line)
        self._merge_last_seen(inner_graph.last_seen, {})

        # Add and Fix edges
        self._fix_control_edges_that_point_to_the_end_of_block(block_starting_line, block_starting_line + inner_graph.code_length, block_starting_line)

        # self.control_edges.append(Edge(block_starting_line + loop_code_length, block_starting_line))
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
                elif isinstance(inner_disassembly, ast.Attribute):
                    influence_name = inner_disassembly.value.id
                    influence_attribute = inner_disassembly.attr
                    influence_var_with_attribute = influence_name + '#' + influence_attribute
                    if influence_var_with_attribute in self.last_seen:
                        influence_vars.add(influence_var_with_attribute)
                    else:
                        for var in self._get_vars_that_points_to_the_same_object(influence_name):
                            other_var_with_attribute = var + '#' + influence_attribute
                            if other_var_with_attribute in self.last_seen:
                                influence_vars.add(other_var_with_attribute)
                                break
        elif isinstance(node.value, ast.Name):
            assigned_var = node.value.id
            influence_vars.add(assigned_var)
            influence_vars = influence_vars.union(self._find_attributes_of_the_same_object(assigned_var))
        elif isinstance(node.value, ast.Call):      # Call to ctor
            obj = '#' + str(uuid.uuid4()) + '#' + node.value.func.id
            self.var_to_object[target] = set([obj])
            self.object_to_var[obj] = set([target])
        elif isinstance(node.value, ast.Attribute):
            influence_name = node.value.value.id
            influence_attribute = node.value.attr
            assigned_var = influence_name + '#' + influence_attribute
            if assigned_var in self.last_seen:
                influence_vars.add(assigned_var)
                influence_vars = influence_vars.union(self._find_attributes_of_the_same_object(assigned_var))
            else:
                vars_pointing_to_the_same_element = self._get_vars_that_points_to_the_same_object(influence_name)
                if not vars_pointing_to_the_same_element:   # We don't know this pointing, maybe it's from higher level
                    influence_vars.add(assigned_var)
                else:
                    influence_vars.add(influence_name)      # Add the assignment to other variable
                    for var in vars_pointing_to_the_same_element:   # Search for corresponding attribute
                        other_var_with_attribute = var + '#' + influence_attribute
                        if other_var_with_attribute in self.last_seen:
                            influence_vars.add(other_var_with_attribute)
                            influence_vars = influence_vars.union(self._find_attributes_of_the_same_object(other_var_with_attribute))
                            break

        # if isinstance(node, ast.Expr):
        #     if isinstance(node.value, ast.Attribute) or isinstance(node.value, ast.Name):
        #         influence_vars = influence_vars.union(set(self._get_vars_that_points_to_the_same_object(assigned_var)))

        # If the target is attribute, the object declaration is also influence
        if '#' in target:
            name, attribute = target.split('#')
            influence_vars.add(name)

        self.nodes.append(StatementNode(code, target, self.indent_level, influence_vars))
        self._create_dep_edge(influence_vars, self._code_line)

        # Update the abstract domain
        if isinstance(node, ast.Assign):
            if isinstance(node.value, ast.Name) or isinstance(node.value, ast.Attribute):
                if assigned_var in self.var_to_object:
                    self.var_to_object[target] = set()
                    for obj in self.var_to_object[assigned_var]:
                        self.object_to_var[obj].add(target)
                        self.var_to_object[target].add(obj)
                elif assigned_var not in self.last_seen:   # We don't know the assigned object it probably from higher level
                    object_name = '@DONT_KNOW@' + assigned_var
                    self.var_to_object[target] = set([object_name])
                    self.object_to_var[object_name] = set([target])
            elif isinstance(node.value, ast.Num):
                self.var_to_object[target] = set()

    def _find_attributes_of_the_same_object(self, var_name):
        return_list = []
        for other_var in self._get_vars_that_points_to_the_same_object(var_name) + [var_name]:
            for tmp_var in self.last_seen.keys():
                if other_var + '#' in tmp_var and other_var == tmp_var.rsplit('#', 1)[0]:
                    return_list.append(tmp_var)
        return set(return_list)

    def _get_vars_that_points_to_the_same_object(self, var):
        return_list = []

        for obj in self.object_to_var:
            if '@DONT_KNOW@' + var == obj:
                return list(self.object_to_var[obj])

        if var in self.var_to_object:
            for obj in self.var_to_object[var]:
                for other_var in self.object_to_var[obj]:
                    return_list.append(other_var)

        # if '#' in var:
        #     name, attr = var.split('#')
        #     for other_var in self._get_vars_that_points_to_the_same_object(name):
        #         possible_match = other_var + '#' + attr
        #         if possible_match in self.last_seen:
        #             return_list.append(possible_match)

        while var in return_list:
            return_list.remove(var)

        return return_list

    def _create_condition_dependencies(self, node, code_line=None, control_node=None):
        if isinstance(node, ast.If):
            code = astor.codegen.to_source(ast.If(test=node.test, body=[], orelse=[]))
        else:   # While
            code = astor.codegen.to_source(ast.While(test=node.test, body=[], orelse=[]))
        checked_vars = []
        for tested in [node.test.left, node.test.comparators[0]]:
            if isinstance(tested, ast.Name):
                checked_vars.append(tested.id)
            elif isinstance(tested, ast.Attribute):
                checked_vars.append(tested.value.id + '#' + tested.attr)
        self._create_dep_edge(checked_vars, self._code_line if not code_line else code_line)
        if not control_node:
            control_node = ControlNode(code, checked_vars, self.indent_level)
            self.nodes.append(control_node)
        return control_node

    def _build_and_merge_inner_graph(self, body):
        code = ''
        for statement in body:
            code += astor.codegen.to_source(statement) + os.linesep
        inner_graph = create_graph(code, self.indent_level + 1)

        self.nodes.extend(inner_graph.nodes)

        self._merge_edges(self.control_edges, inner_graph.control_edges)
        self._merge_edges(self.dep_edges, inner_graph.dep_edges)
        self._fix_inner_code_lines(inner_graph.last_seen)
        self._find_unknown_variables(inner_graph.unknown_vars)
        self._merge_objects(inner_graph.object_to_var, inner_graph.var_to_object)

        self._code_line += inner_graph.code_length

        return inner_graph.last_seen, inner_graph.code_length

    def _merge_objects(self, inner_objects_to_var, inner_var_to_objects):
        for obj, vars in inner_objects_to_var.iteritems():
            if '@' not in obj:  # Created new object in the inner code
                self.object_to_var[obj] = inner_objects_to_var[obj]
            else:   # Reference to object from outside
                var_name = obj.rsplit('@')[-1]
                if var_name in self.var_to_object:
                    for found_object in self.var_to_object[var_name]:
                        self.object_to_var[found_object] = self.object_to_var[found_object].union(vars)
                else:   # We don't know this object either
                    self.object_to_var[obj] = vars

        for var, objects in inner_var_to_objects.iteritems():
            if var not in self.var_to_object:
                self.var_to_object[var] = set()
            for obj in objects:
                if '@' not in obj:  # Created new object in the inner code
                    self.var_to_object[var].add(obj)
                else:
                    var_name = obj.rsplit('@')[-1]
                    if var_name in self.var_to_object:
                        correct_objects = self.var_to_object[var_name]
                        for c_obj in correct_objects:
                            self.var_to_object[var].add(c_obj)
                            self.object_to_var[c_obj].add(var)
                    else:
                        self.var_to_object[var].add(obj)

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
            outer_edges.append(Edge(edge.from_ + self._code_line + 1, edge.to + self._code_line + 1, edge.jmp_true))


def create_graph(original_code, indent_level=0):
    builder = GraphBuilder(indent_level)
    builder.visit(ast.parse(original_code))

    return builder


def create_projected_variable_path(code, projected_variable):
    program_graph = create_graph(code + "\n" + projected_variable)
    dep_map = {}
    control_map = {}
    r_control_map = {}
    r_dep_map = {}
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
    for edge in program_graph.dep_edges:
        if edge.from_ not in r_dep_map:
            r_dep_map[edge.from_] = []
        r_dep_map[edge.from_].append(edge.to)

    for i in xrange(len(program_graph.nodes)):
        pos = len(program_graph.nodes) - i - 1
        g = program_graph.nodes[pos]
        if (isinstance(g, StatementNode) and g.assigned_var.split("#")[0] == projected_variable) or i == 0:
            r = set()
            r.add(pos)
            post_len = 0
            pre_len = 1

            #add dependencies
            r = get_dependencies(dep_map, pos, r)
            required = required.union(r)

            #add every branch on the way to the node

    r = set()
    for pos in required:
        r = r.union(recurse_walk(control_map, dep_map, pos, r, r_control_map))
    required = required.union(r)

    required = list(required)
    return sorted(required)[:-1]


def recurse_walk(control_map, dep_map, pos, r, r_control_map):
    if pos in r_control_map:
        prev = r_control_map[pos]

        while prev is not 0:
            l = prev
            for prev in l:
                if len(control_map[prev]) == 2:
                    low = control_map[prev][0]
                    high = control_map[prev][1]
                    if low <= pos and pos < high:
                        r.add(prev)
                        #r = r.union(dep_map[prev])
                        r = get_dependencies(dep_map, prev, r)
                if prev not in r_control_map:
                    break
                prev = r_control_map[prev]
    return r


def get_dependencies(dep_map, pos, r):
    r = set()
    r.add(pos)
    post_len = 0
    pre_len = 1
    while pre_len != post_len:
        pre_len = len(r)
        for i in r:
            if i in dep_map:
                r = r.union(dep_map[i])
        post_len = len(r)
    return r


def build_program(program_graph, projected_path):
    program = []
    for i in projected_path:
        program.append(program_graph.nodes[i].statement)
    return program


def output_analysis_result(graph, output_directory):
    from tabulate import tabulate
    headers = ['#line', 'assigned variable', 'influence variables', 'statement']
    table = []
    for index, node in enumerate(graph.nodes):
        if isinstance(node, StatementNode):
            table.append([index, node.assigned_var, node.influence_vars, node.statement])
        else:
            table.append([index, None, node.checked_vars, node.statement])
    with file(output_directory + os.sep + 'analysis_result.txt', 'w') as f:
        f.write(tabulate(table, headers, tablefmt="grid"))
        f.write(os.linesep)
        f.write('Control Edges: ' + str(graph.control_edges) + os.linesep)
        f.write('Dependency Edges: ' + str(graph.dep_edges))


def output_code(graph, relevant_nodes, output_dir):
    with file(output_dir + os.path.sep + 'projected_code.py', 'w') as f:
        for node_number in relevant_nodes:
            if isinstance(graph.nodes[node_number-1], ControlNode) and graph.nodes[node_number-1].statement == 'else:':
                f.write('\t'*graph.nodes[node_number-1].indent + graph.nodes[node_number-1].statement + '\n')
            f.write('\t'*graph.nodes[node_number].indent + graph.nodes[node_number].statement + '\n')


def main():
    if len(sys.argv) != 4:
        raise RuntimeError('Illegal number of arguments.' + os.linesep +
                           'Execution line should be: python projector.py <code_file> <output_dir> <projected_variable>')
    code_file = sys.argv[1]
    output_directory = sys.argv[2]
    projected_variable = sys.argv[3]

    with file(code_file) as f:
        code = f.read()

    graph = create_graph(code)
    output_analysis_result(graph, output_directory)

    visualize(graph, output_directory + os.path.sep + 'out.gv')

    relevant_nodes = create_projected_variable_path(code, projected_variable)
    output_code(graph, relevant_nodes, output_directory)
    print relevant_nodes


if __name__ == '__main__':
    main()
