from projector import projector
import test1
import test3
import test4
import test6

if __name__ == '__main__':
    checks = [test1, test3, test4, test6]
    for test in checks:
        print 'Checking', test.name, '...'
        graph = projector.create_graph(test.code)

        passed = True
        for edge in graph.control_edges:
            if (edge.from_, edge.to) not in test.control_edges:
                print 'Extra Control Edge: ', (edge.from_, edge.to)
                passed = False
        for edge in test.control_edges:
            if not filter(lambda x: x.from_ == edge[0] and x.to == edge[1], graph.control_edges):
                print 'Missing Control Edge: ', edge
                passed = False

        if passed:
            print 'Pass Control Edges'

        passed = True
        for edge in graph.dep_edges:
            if (edge.from_, edge.to) not in test.dep_edges:
                print 'Extra Dep Edge: ', (edge.from_, edge.to)
                passed = False
        for edge in test.dep_edges:
            if not filter(lambda x: x.from_ == edge[0] and x.to == edge[1], graph.dep_edges):
                print 'Missing Dep Edge: ', edge
                passed = False

        if passed:
            print 'Pass Dep Edges'

        print
