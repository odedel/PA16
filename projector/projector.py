import ast
import astor
import graphviz

graph_nodes = []
graph_edges = []

class GraphNode(object):
    def __init__(self, statement, assigned_var, influence_vars=[]):
        self.statement = statement
        self.assigned_var = assigned_var
        self.influence_vars = influence_vars

    def __repr__(self):
        return '(%s, %s, %s)' % (self.statement, self.assigned_var, self.influence_vars)



class ASTWalker(ast.NodeVisitor):

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

        graph_nodes.append(GraphNode(code, target, influence_vars))


def create_graph(original_code):
    ast_tree = ast.parse(original_code)
    ASTWalker().visit(ast_tree)

    seen_variables_to_line_code = {}
    for enumeration, node in enumerate(graph_nodes):
        # Create edges
        for dependency in node.influence_vars:
            graph_edges.append((seen_variables_to_line_code[dependency], enumeration))

        # Update the seen list
        seen_variables_to_line_code[node.assigned_var] = enumeration

    print graph_edges



def create_projected_variable_path(program_graph, projected_variable):
    pass


def build_program(projected_path):
    pass


def project(original_code, projected_variable):
    program_graph = create_graph(original_code)
    projected_path = create_projected_variable_path(program_graph, projected_variable)
    return build_program(projected_path)


def main():
    with file(r'..\Tests\test1.py') as f:
        original_code = f.read()

    projected_code = project(original_code, 'z')

    print projected_code

if __name__ == '__main__':
    main()
    print "%s\t%s%s" % ("assigned".ljust(10), "influenced by".ljust(20), "statement")
    for g in graph_nodes:
        print "%s\t%s%s" % (str(g.assigned_var).ljust(10), str(g.influence_vars).ljust(20), g.statement)
