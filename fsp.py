import itertools
import numpy
import scipy.sparse

class StateIndexMap(object):
    def __init__(self, dim, vectstates, origin=None):
        self.dim = dim
        self.vectstates = numpy.asarray(vectstates)
        if origin is None:
            self.origin = 0
        else:
            self.origin = int(origin)
        
        # build dict-based state<->index transforms
        self.state_to_index = {}
        self.index_to_state = {}
        for relative_index, state in enumerate(itertools.izip(*vectstates)):
            index = self.origin + relative_index
            self.state_to_index[state] = index
            self.index_to_state[index] = state
        
        self.size = len(self.state_to_index)
        
        # dynamically generate numpy-vectorised state<->index transforms
        v_func = numpy.vectorize(lambda *state : self.state_to_index[state],
                                 [numpy.int])
        self.vectstates_to_indices = lambda states : v_func(*states)
        
        func = lambda index : self.index_to_state[index]
        otypes = (numpy.int, )*self.dim   
        self.indices_to_vectstates = numpy.vectorize(func, otypes)
        
        # generate characteristic function for states
        func2 = lambda *state : state in self.state_to_index
        v_func2 = numpy.vectorize(func2, [numpy.bool])
        self.vectstates_in_map = lambda states : v_func2(*states)
        
        # create constants
        self.indices = self.vectstates_to_indices(self.vectstates)
        
def create_flux_matrices(model, state_index_map, error_trackers):
    
    propensities = model['propensities']
    offset_vectors = model['offset_vectors']
    
    source_states = state_index_map.vectstates
    source_indices = state_index_map.indices
    
    flux_matrices = []
    for (propensity, offset_vector) in itertools.izip(propensities,
                                                      offset_vectors):
        
        # ensure offset_vector has the correct structure
        offset_vector = numpy.asarray(offset_vector)[:, numpy.newaxis]
        dest_states = source_states + offset_vector
        
        # figure out which of these states are legal
        state_mask = state_index_map.vectstates_in_map(dest_states)
        not_state_mask = numpy.logical_not(state_mask)
        
        num_states = numpy.add.reduce(state_mask)
        num_error_states = numpy.add.reduce(not_state_mask)
        
        data = []
        rows = []
        cols = []
        
        if num_states > 0:
            masked_source_indices = numpy.array(source_indices[state_mask])
            masked_source_states = numpy.array(source_states[:, state_mask])
            masked_dest_indices = state_index_map.vectstates_to_indices(dest_states[:, state_mask])
            coefficients = propensity(*masked_source_states)
            
            data.append(-coefficients)
            cols.append(masked_source_indices)
            rows.append(masked_source_indices)
            data.append(coefficients)
            cols.append(masked_source_indices)
            rows.append(masked_dest_indices)
            
        
        if num_error_states > 0:
            # only operate on valid states that are not contained in the truncated state space
            validity_mask = numpy.logical_and.reduce(dest_states[:, not_state_mask]>=0, axis=0)
            num_valid_states = numpy.add.reduce(validity_mask)
            
            if num_valid_states > 0:
                valid_dest_states = numpy.array(dest_states[:, not_state_mask][:, validity_mask])
                valid_source_indices = numpy.array(source_indices[not_state_mask][validity_mask])
                valid_source_states = numpy.array(source_states[:, not_state_mask][:, validity_mask])
                coefficients = propensity(*valid_source_states)
                
                # flux lost due to truncation of state space
                data.append(-coefficients)
                cols.append(valid_source_indices)
                rows.append(valid_source_indices)
                
                # record lost flux in error states, if any are provided
                for error_tracker in error_trackers:
                    error_projection, error_index_map = error_tracker
                    
                    # todo fix this hack
                    projection_dim = 4
                    v = numpy.vectorize(error_projection, otypes = [numpy.int, ]*projection_dim)
                    
                    dest_error_states = v(*valid_dest_states)
                    
                    dest_error_indices = error_index_map.vectstates_to_indices(dest_error_states)
                    
                    data.append(coefficients)
                    cols.append(valid_source_indices)
                    rows.append(dest_error_indices)
            
        if len(data)==0:
            continue
        
        def join(x):
            if len(x) == 0:
                return []
            
            size = numpy.add.reduce([numpy.size(a) for a in x])
            joined_x = numpy.zeros((size, ), dtype=x[0].dtype)
            offset = 0
            for a in x:
                a_size = numpy.size(a)
                joined_x[offset:offset+a_size] = a
                offset += a_size
            return joined_x
        
        # merge data, rows, cols
        data = join(data)
        cols = join(cols)
        rows = join(rows)
        
        # figure out how many indices there are in total
        size = state_index_map.size
        for error_tracker in error_trackers:
            size += error_tracker[1].size
        
        flux_matrix = scipy.sparse.coo_matrix((data, (rows, cols)), (size, )*2)
        #print '\t coo : %s' % repr(flux_matrix)
        flux_matrix = flux_matrix.tocsr()
        #print '\t csr : %s' % repr(flux_matrix)
        flux_matrix.eliminate_zeros()
        flux_matrix.sum_duplicates()
        #print '\t csr (cleaned?) : %s' % repr(flux_matrix)
        flux_matrices.append(flux_matrix)
            
    return flux_matrices

def create_diff_eqs(size, flux_matrices, time_dependencies):
        
    def diff_eqs(t, p):
        """
        this routine defines our mapping diff_eqs(t,p) ---> dp/dt(t,p)
        which is later called by the ode solver
        """
        
        inflated_shape = numpy.shape(p)
        
        # the net flux will be accumulated inside the array p_dot
        p_dot = numpy.zeros(inflated_shape)
        
        for phi, flux_matrix in itertools.izip(time_dependencies,
                                               flux_matrices):
            p_dot += phi(t)*(flux_matrix*p)
        
        # return the net flux
        return p_dot
    
    return diff_eqs