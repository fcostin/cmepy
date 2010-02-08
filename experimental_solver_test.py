"""
solves munsky_khammash_gene_toggle using experimental solver
"""

import numpy
import cmepy.new_core.domain as domain
import cmepy.new_core.cme_solver_experimental as cme_solver
import cmepy.new_core.recorder as cme_recorder
import pylab

from munsky_khammash_gene_toggle_08 import create_model

def plot_recorded_data(recorder, title):
    """
    plot recorder species count expectation and standard devation
    """
    pylab.figure()
    for measurement in recorder.measurements('species'):
        pylab.plot(measurement.times,
                   measurement.expected_value,
                   label = measurement.name)
    pylab.legend()
    pylab.title(title+': species count expected value')
    
    pylab.figure()
    for measurement in recorder.measurements('species'):
        pylab.plot(measurement.times,
                   measurement.standard_deviation,
                   label = measurement.name)
    pylab.legend()
    pylab.title(title+': species count standard deviation')

def main():
    """
    solve Gene Toggle model then display results
    """
    
    # create model. The origin must be specified in order for CmeSolver to
    # automatically determine initial distribution ...
    max_s1_copies = 40
    max_s2_copies = 100
    model = create_model(max_s1_copies, max_s2_copies)
    
    # define domain states as union of two rectangular regions along the axes
    a_shape = (max_s1_copies, 6)
    b_shape = (10, max_s2_copies)
    domain_states_a = set(domain.to_iter(domain.from_rect(a_shape)))
    domain_states_b = set(domain.to_iter(domain.from_rect(b_shape)))
    states = domain.from_iter(domain_states_a | domain_states_b)
    
    solver = cme_solver.create_cme_solver(model,
                                          sink = True,
                                          domain_states = states)
    
    recorder = cme_recorder.CmeRecorder(model)
    recorder.add_target('species',
                        ['expected value', 'standard deviation'],
                        model['species'],
                        model['species counts'])
    
    time_steps = numpy.linspace(0.0, 100.0, 101)
    for t in time_steps:
        solver.step(t)
        p, p_sink = solver.y
        
        print '\ttime = %g' % t
        print '\tsink state probability %g' % p_sink
        
        # translate solution from sparse mapping format to
        # rectangular dense array, so recorder can understand it
        
        p_dense = numpy.zeros(model['np'])
        for state, probability in p.iteritems():
            p_dense[state] = probability
        
        recorder.write(t, p_dense)
    
    plot_recorded_data(recorder, model['doc'])
    pylab.show()


if __name__ == '__main__':
    main()
