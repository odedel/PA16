__author__ = 'Odedz'

def create_graph(original_code):
    pass


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
