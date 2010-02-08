"""
proof-of-concept test of the generalised state space and
partial time-dependence functionality

solves two variants of the competing T-cell problem
using a species-count state space of 2 dimensions,
and 4 reactions.

the first variant has time-independent propensities

the second variant features both birth reactions being scaled by
an exponential decay ...

note that the CmeRecorder actually works fine when computing
species count expectations and standard deviations.

- reuben fletcher-costin, 7 / 12 / 09 
"""


import numpy
import pylab
import math
    
def create_model(np):
    """
    function to create species count state space version of the model
    
    this is a slightly modified version of the burr08_model definition
    from the cmepy/models/burr08_model.py file ...
    """
        
    # we first define the mappings from the state space to species counts
    # this is pretty easy since we choose species count state space
    species_count_a = lambda *x : x[0]
    species_count_b = lambda *x : x[1]
    
    # we now define the reaction propensities using the species counts
    def reaction_a_birth(*x):
        """
        propensity of birth reaction for species a
        """
        s_a = species_count_a(*x)
        s_b = species_count_b(*x)
        return numpy.where(s_a + s_b > 0,
                           60.0*s_a*(numpy.divide(0.5, s_a + s_b) +
                                   numpy.divide(0.5, (s_a + 10*100))),
                           0.0)
    
    reaction_a_decay = lambda *x : 1.0*species_count_a(*x)
    
    def reaction_b_birth(*x):
        """
        propensity of birth reaction for species b
        """
        s_a = species_count_a(*x)
        s_b = species_count_b(*x)
        return numpy.where(s_a + s_b > 0,
                           60.0*s_b*(numpy.divide(0.5, s_a + s_b) +
                                   numpy.divide(0.5, (s_b + 10*100))),
                           0.0)
    
    reaction_b_decay = lambda *x : 1.0*species_count_b(*x)
    
    model = {}
    model['doc'] = 'T Cell clonoTypes (Time Independent Propensities)'
    model['np'] = np
    model['propensities'] = (reaction_a_birth,
                             reaction_a_decay,
                             reaction_b_birth,
                             reaction_b_decay)
    model['offset_vectors'] = ((1, 0), (-1, 0), (0, 1), (0, -1))
    model['reactions'] = ['*->A', 'A->*', '*->B', 'B->*']
    model['species counts'] = (species_count_a, species_count_b)
    model['species'] = ['A', 'B']
    return model

def test(time_dependence):
    """
    solves the model, applying the given time_dependence coefficients
    to the propensity functions, if any
    
    outputs a few graphs via pylab once finished
    """
    
    
    np = (101, 101)
    # initially 10 copies of both species : s_a and s_b
    p0 = numpy.zeros(np)
    p0[10, 10] = 1.0
    
    model = create_model(np)
    model['time_dependence'] = time_dependence
    
    from cmepy.solver import CmeSolverMatrix
    from cmepy.recorder import CmeRecorder
    solver = CmeSolverMatrix(model)
    solver.set_solver_params(tol = 1.0e-7)
    solver.set_initial_values(p0 = p0)
    recorder = CmeRecorder(solver)
    recorder.add_target(output=['expectation', 'std_dev'],
                        species=model['species'])
    
    time_steps = numpy.linspace(0.0, 30.0, 31.0)
    for i, t in enumerate(time_steps):
        print 'step %d of %d, t = %g' % (i+1, len(time_steps), t)
        print 'stepping ODE'
        solver.step(t)
        print 'recording data'
        recorder.take_measurements()
    
    model_title = 'time dependence: %s, ' % (time_dependence is not None)
    
#===============================================================================
#    #XXX TODO THIS IS A TEMP HACK TO OUTPUT SPARSE MATRIX A FOR
#    #ANALYSIS ...
#    import itertools
#    csr_matrix = solver.sparse_matrix
#    coo_matrix = csr_matrix.tocoo()
#    
#    
#    p = solver.get_p()
#    num_states = numpy.product(numpy.shape(p))
#    print 'num_states = '+str(len(p))
#    
#    #XXX TODO TEMP HACK FOR SPY VISUALISATION OF SPARSE STRUCTURE
#    histogram_states = 1 + (num_states / 100)
#    histogram = numpy.zeros((histogram_states, histogram_states))
#    histogram_2 = numpy.zeros((1000, 1000))
#    
#    
#    print 'matrix dump begin:'
#    print ''
#    for i, (r, c, d) in enumerate(itertools.izip(coo_matrix.row,
#                                                 coo_matrix.col,
#                                                 coo_matrix.data)):
#        print '%d, %d, %g' % (r, c, d)
#        histogram[r/100, c/100] += 1
#        if (r < 1000) and (c<1000):
#            histogram_2[r, c] += 1
#    
#    print ''
#    print 'matrix dump end of %d entries' % (i+1)
#    
#    pylab.matshow(histogram)
#    pylab.matshow(histogram_2)
#    pylab.show()
#    
#    #XXX TODO END TEMP HACK
#    
#    return
#===============================================================================
    
    # plot expectation, over time, of all species counts
    pylab.figure()
    for s_info in recorder.measurements('species'):
        pylab.plot(s_info.times, s_info.expectation, label = s_info.name)
    pylab.legend()
    pylab.title(model_title+'species count expectation values')
    
    # plot std dev, over time, of all species counts
    pylab.figure()
    for s_info in recorder.measurements('species'):
        pylab.plot(s_info.times, s_info.std_dev, label = s_info.name)
    pylab.legend()
    pylab.title(model_title+'species count std dev')
    
    pylab.figure()
    p = solver.get_p()
    pylab.contourf(numpy.where(p>0.0, p, 0.0))
    pylab.title(model_title+'final probability distribution ...')

def test_all():
    test(time_dependence = None)
    #pylab.show()

if __name__ == '__main__':
    import cProfile, pstats
    PROFILE_NAME = 'reversible_expokit_test.profile'
    cProfile.run('test_all()', PROFILE_NAME)
    import pstats
    profile = pstats.Stats(PROFILE_NAME)
    profile.sort_stats('cumulative').print_stats(30)