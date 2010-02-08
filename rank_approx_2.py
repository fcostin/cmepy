import numpy
import scipy.sparse

import cmepy.core.matrix_cme as matrix_cme
import cmepy.new_core.ode_solver as ode_solver
import cmepy.new_core.cme_solver as cme_solver
import cmepy.new_core.recorder as cme_recorder

import block_diagonal

def get_catalyser_models(initial_s_count, initial_e_count, epsilon):
    species = ('S', 'E', 'C', 'D')
    species_counts = (lambda *x : x[0],
                      lambda *x : x[1],
                      lambda *x : x[2],
                      lambda *x : initial_s_count - x[0] - x[2])
    propensities = (lambda *x : 1.0*x[0]*x[1],
                    lambda *x : 1.0*x[2],
                    lambda *x : epsilon*x[2])
    offset_vectors = ((-1, -1, 1),
                      (1, 1, -1),
                      (0, 1, -1))
    np = (initial_s_count+1, initial_e_count+1, initial_s_count+1)
    model = {'species' : species,
             'species counts' : species_counts,
             'propensities' : propensities,
             'offset_vectors' : offset_vectors,
             'np' : np}
    
    slow_model = {'propensities' : propensities[:-1],
                  'offset_vectors' : offset_vectors[:-1],
                  'np' : np}
    
    fast_model = {'propensities' : (lambda *x : epsilon*x[1], ),
                  'offset_vectors' : ((1, -1), ),
                  'np' : (initial_e_count+1, initial_s_count+1)}
    return model, slow_model, fast_model

def create_indexing(np, f):
    # xxx todo strictly there should be something about norigin in here
    # use cmepy.util(s).indices_ext ....
    states = [numpy.ravel(i) for i in numpy.indices(np)]
    f_states = f(*states)
    permutation = numpy.argsort(f_states)
    inverse_permutation = numpy.argsort(permutation)
    return permutation, inverse_permutation

def create_cme_solver(initial_s_count, initial_e_count, epsilon):
    # ==========================================================================
    # define model & decomposition into slow and fast models
    # ==========================================================================    
    full_model, slow_model, fast_model = get_catalyser_models(initial_s_count,
                                                              initial_e_count,
                                                              epsilon)
    # ==========================================================================
    # define state space indexing scheme as follows:
    #
    # for any two states x & y,
    #   1) order by comparing x.E + x.C with y.E + y.C ; if tied, continue
    #   2) order by comparing x.E - x.C with y.E - y.C ; if tied, continue
    #   3) order by comparing x.S with y.S (if states contain an S value...)
    #
    # the reason this scheme is chosen is to ensure that the matrix for the
    # fast_model ends up having a really nice block diagonal structure.
    # since the indexing scheme for the slow_model doesn't really matter
    # we just define it so transforming between the slow_model scheme
    # and the fast_model scheme is simple
    # ==========================================================================
    
    # xxx todo define these bijections in a nice way without
    # the magic numbers
    f_fast = lambda *x : (x[0]+x[1])*1000 + (x[0]-x[1])
    f_slow = lambda *x : (x[1]+x[2])*1000000 + (x[1]-x[2])*1000 + x[0]
    
    fast_indexing, fast_indexing_inverse = create_indexing(fast_model['np'],
                                                           f_fast)
    slow_indexing, slow_indexing_inverse = create_indexing(slow_model['np'],
                                                           f_slow)
    # important! pass the **inverse** indexing permutation to the
    # sparse matrix construction routine ....
    
    fast_flux_data = cme_solver.create_flux_data(fast_model)
    fast_matrix = matrix_cme.gen_sparse_matrix(fast_model['np'],
                                               fast_flux_data,
                                               fast_indexing_inverse)
    fast_matrix *= epsilon
    fast_matrix = fast_matrix.tocsr()
    
    slow_flux_data = cme_solver.create_flux_data(slow_model)
    slow_matrix = matrix_cme.gen_sparse_matrix(slow_model['np'],
                                               slow_flux_data,
                                               slow_indexing_inverse)
    slow_matrix = slow_matrix.tocsr()
    
    # ==========================================================================
    # define matrices to transform between the fast and slow schemes...
    # d maps from fast to slow, with inverse d_tilde.
    # For example, with S ranging over 4 states (ie duplication of 4) we have:
    # fast | 0  0  0  0  1  1  1  1  2  2  2  2  3  3  3  3 ...
    # slow | 0  1  2  3  4  5  6  7  8  9 10 11 12 13 14 15 ...
    # ==========================================================================
    num_fast_states = numpy.product(fast_model['np'])
    duplication = slow_model['np'][0]
    num_slow_states = num_fast_states*duplication
    assert num_slow_states == numpy.product(slow_model['np'])
    temp_fast = numpy.repeat(numpy.arange(num_fast_states), duplication)
    temp_slow = numpy.arange(num_slow_states)
    # d is acting like a de aggregation matrix. "d for de-aggregation"
    d = scipy.sparse.coo_matrix((numpy.ones((num_slow_states, )),
                                 (numpy.array(temp_slow),
                                  numpy.array(temp_fast))),
                                (num_slow_states, num_fast_states))
    # d_tilde is acting like an aggregation matrix.
    d_tilde = scipy.sparse.coo_matrix((numpy.ones((num_slow_states, ))/duplication,
                                 (numpy.array(temp_fast),
                                  numpy.array(temp_slow))),
                                (num_fast_states, num_slow_states))
    d = d.tocsr()
    d_tilde = d_tilde.tocsr()
    
    # NB: d_tilde*d should be equal to the identity of shape (num_fast_states, )*2
    
    # ==========================================================================
    # compute matrix exponential of fast_matrix
    # -- use accelerated block diagonal routines ...
    # ==========================================================================
    
    # xxx todo this is a bit of a hack to compute the limit as t goes to infty
    # if too large a time is used the sparse block diagonal expm routine
    # will a bit upset by infinities popping up in sub blocks and
    # start returning nan entries ...
    t_infty = 1000.0
    bd_fast = block_diagonal.from_sparse_matrix(fast_matrix)
    bd_m = block_diagonal.expm(bd_fast, t_infty)
    m = block_diagonal.to_sparse(bd_m).tocsr()
    
    # ==========================================================================
    # define initial conditions, differential equations, and packing functions
    # ==========================================================================
    
    # initialise system with maximal copies of S & E, zero copies of C & D
    p_0 = numpy.zeros(slow_model['np'])
    p_0[-1, -1, 0] = 1.0
    
    # define differential equations in terms of fast reaction indexing scheme
    
    # xxx todo this approach is flawed
    # need to have a separate copy of the (reduced) fast matrix
    # for each state S ...
    # ie needs to be some kind of outer product construction here
    # instead of just matrices d, d_tilde
    a_hat = m*d_tilde*slow_matrix*d
    def dy_dt(t, y):
        return a_hat*y
    
    # flatten p
    # permute ordering to match slow indexing scheme
    # aggregate to give corresponding fast indexing scheme data
    def pack(p):
        return d_tilde*(numpy.ravel(p)[slow_indexing])
    
    # de-aggregate to give corresponding slow indexing scheme data
    # inverse permute to match default indexing scheme
    # inflate
    def unpack(y):
        return numpy.reshape((d*y)[slow_indexing_inverse], slow_model['np'])
    
    # ==========================================================================
    # construct the cme solver
    # ==========================================================================
    
    new_solver = ode_solver.Solver(dy_dt, p_0)
    # nb -- it is important to set the transform_dy_dt flag to False here
    # otherwise the solver will assume that the provided dy_dt is actually
    # of the form dp_dt and needs to be conjugated by the pack / unpack
    # functions ...
    new_solver.set_packing(pack,
                           unpack,
                           transform_dy_dt=False)
    return new_solver, full_model

def main():
    # ==========================================================================
    # set model definition parameters
    # ==========================================================================
    
    # xxx todo if these counts are set higher than 999 bad things will happen.
    # cf dirty hacks used to define state ordering for index schemes
    initial_s_count = 10
    initial_e_count = 3
    epsilon = 0.01
    
    # ==========================================================================
    # compute the approximate cme solver for this model
    # ==========================================================================
    
    # nb the (full) model is used to interface with the cme recorder ...
    solver, model = create_cme_solver(initial_s_count, initial_e_count, epsilon)
    
    print solver.y[-1, -1, 0]
    # ==========================================================================
    # advance the solution and plot some results
    # ==========================================================================
    recorder = cme_recorder.CmeRecorder(model)
    recorder.add_target('species',
                        ['expected value', 'standard deviation'],
                        model['species'],
                        model['species counts'])
    
    time_steps = numpy.linspace(0.0, 5.0, 101)
    for t in time_steps:
        solver.step(t)
        recorder.write(t, solver.y)
    
    graph = True
    
    #  graphing code ...
    if graph:
        title = 's_count %d e_count %d;\n' % (initial_s_count, initial_e_count)
        import pylab
        pylab.figure()
        for measurement in recorder.measurements('species'):
            pylab.plot(measurement.times,
                       measurement.expected_value,
                       label = measurement.name)
        pylab.legend()
        pylab.title(title+'species count expected value')
        pylab.savefig('ev_%d_%d_approx.png' % (initial_s_count, initial_e_count))
        pylab.close()
        pylab.figure()
        for measurement in recorder.measurements('species'):
            pylab.plot(measurement.times,
                       measurement.standard_deviation,
                       label = measurement.name)
        pylab.legend()
        pylab.title(title+'species count standard deviation')
        pylab.savefig('sd_%d_%d_approx.png' % (initial_s_count, initial_e_count))
        pylab.close()
    
if __name__ == '__main__':
    main()