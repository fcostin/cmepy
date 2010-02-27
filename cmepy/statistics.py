"""
Statistical utilities for working with CME solver output.
"""

import itertools
import operator
import numpy

from cmepy import domain

class Distribution(dict):
    """
    Distributions are mappings that represent probability distributions
    over a discrete state space.
    """
    def __init__(self, p=None):
        """
        Distribution([p]) -> distribution
        
        Returns distribution instance initialised using mapping p.
        They keys of p define states in the state space, with the associated
        values of p defining the corresponding probabilities.
        
        If p is omitted, defaults to an empty distribution, that is, no states.
        """
        if p is None:
            p = {}
        dict.__init__(self, p)
    
    @property
    def statistics(self):
        return {
            'expectation' : self.expectation,
            'expected_value' : self.expectation,
            'variance' : self.variance,
            'covariance' : self.covariance,
            'standard_deviation' : self.standard_deviation
        }
    
    @property
    def dimension(self):
        """
        inferred dimension of state space of this distribution
        """
        # attempt to infer dimension of state space
        if self:
            for state in self.iterkeys():
                try:
                    # self is keyed by vector
                    # arguments, return the length of the first one
                    return len(state)
                except TypeError:
                    # self is keyed by scalar arguments,
                    # treat this as dimension 1
                    return 1
        else:
            # empty distributions have dimension zero
            return 0
    
    def map(self, f, g=None):
        """
        d.map(f [, g]) -> distribution
        
        Returns a copy of the distribution d, with each key replaced by its
        image under f. Any duplicate image keys are merged, with the value of
        the merged key equal to the sum of the values.
        
        If g is supplied, it is used instead of addition to reduce the values of
        duplicate image keys.
        """
        return Distribution(map_distribution(f, self, g))
    
    def expectation(self):
        """
        d.expectation() -> mu
        
        Returns expected state of the distribution d, provided dimension > 0.
        """
        assert self.dimension > 0
        return expectation(self)
    
    def variance(self):
        """
        d.variance() -> sigma_squared
        
        Returns variance of the Distribution d, provided dimension == 1.
        """
        assert self.dimension == 1
        return variance(self)
    
    def covariance(self):
        """
        d.covariance() -> cov
        
        Returns covariance of the distribution d, provided dimension == 2.
        """
        assert self.dimension == 2
        return covariance(self)
    
    def standard_deviation(self):
        """
        d.standard_deviation() -> sigma
        
        Returns std deviation of the Distribution d, provided dimension == 1.
        """
        return numpy.sqrt(self.variance())
    
    def to_dense(self, shape, origin=None):
        """
        d.to_dense(shape[, origin]) -> array
        
        Returns dense version of distribution for given array shape and origin
        """
        
        if origin is None:
            origin = (0, )*len(shape)

        states = set(domain.to_iter(domain.from_rect(shape, origin=origin)))
        states &= set(self.iterkeys())
        p_dense = numpy.zeros(shape, dtype=numpy.float)
        for state in states:
            probability = self[state]
            shifted_state = tuple(numpy.asarray(state) - numpy.asarray(origin))
            p_dense[shifted_state] += probability
        return p_dense
    
    def compress(self, epsilon):
        """
        d.compress(epsilon) -> compressed epsilon-approximation of d
        
        Returns compressed version of distribution.
        
        The returned approximation is *compressed*, in the sense that it is the
        approximation with the smallest support, while the error between d and
        the approximation is within epsilon (L1 norm).
        """
        
        return Distribution(compress(self, epsilon))

def map_distribution_simple(f, p, g=None):
    """
    map_distribution_simple(f, p [, g]) -> mapping
    
    reference implementation of map_distribution that is simple but slow
    """
    
    if g is None:
        g = operator.add   
    f_p = {}
    for state, probability in p.iteritems():
        f_state = f(state)
        if f_state in f_p:
            f_p[f_state] = g(f_p[f_state], probability)
        else:
            f_p[f_state] = probability
    return f_p

def map_distribution(f, p, g=None):
    """
    map_distribution(f, p [, g]) -> mapping
    
    Returns a copy of the mapping p, with each key replaced by its
    image under f. Any duplicate image keys are merged, with the value of
    the merged key equal to the sum of the values.
    
    It is expected that f returns tuples or scalars, and behaves in a
    reasonable way when given vector state array arguments.
    
    If g is supplied, it is used instead of addition to reduce the values of
    duplicate image keys. If given, g must have a reduce method of the form
        g.reduce(probabilities) -> reduced_probability
        
    for example, setting g to a numpy ufunc would be fine.
    """
    
    # all this nonsense actually does something fairly straight forward
    # see 'map_distribution_simple' for a reference implementation that
    # avoids numpy operations
    
    num_items = len(p)
    
    if num_items == 0:
        return {}
    
    if g is None:
        g = numpy.add
    
    s, v = domain.from_mapping(p)
    fs = numpy.asarray(f(s))
    
    # handle case where f returns scalar arguments, say
    # this might be a touch flakey
    if len(fs.shape) != 2:
        fs = fs*numpy.ones((1, s.shape[1]))
    
    # sort image states using lexical ordering on coords, then
    # apply same ordering to values
    
    order = numpy.lexsort(fs)
    sfs = fs[:, order]
    sv = v[order]
    
    # figure out the indices of the first instance of each state
    not_equal_adj = numpy.logical_or.reduce(sfs[:, :-1] != sfs[:, 1:])
    not_equal_adj = numpy.concatenate(([True], not_equal_adj))
    
    # extract the unique image states under f
    usfs = sfs[:, not_equal_adj]
    
    # convert back from arrya representation to iterator of state tuples
    unique_image_states = domain.to_iter(usfs)
    
    # determine start and end indices of each equivalence class of
    # values in the sorted values array, where values are equivalent if
    # they are associated with states that agree under the transform f
    class_begin = numpy.nonzero(not_equal_adj)[0]
    class_end = numpy.concatenate((class_begin[1:], [num_items]))
    
    # construct the resulting mapped probability distribution
    # each image state s maps to the values in its equivalence class,
    # reduced by g
    p_mapped = {}
    for s, i, j in itertools.izip(unique_image_states, class_begin, class_end):
        p_mapped[s] = g.reduce(sv[i:j])
    
    return p_mapped
        
        
def expectation(p):
    """
    expectation(p) -> mu
    
    Returns the expected value mu, treating the mapping p as a distribution
    p : states -> probabilities.
    """
    
    if type(p) is tuple:
        assert len(p) == 2
        states, probabilities = p
    else:
        states, probabilities = domain.from_mapping(p)
    weighted_states = states * probabilities[numpy.newaxis, :]
    mu = numpy.add.reduce(weighted_states, axis=1)
    
    return mu

def _metavariance(p, exponent):
    """
    _metavariance(p, exponent) -> alpha
    
    Returns alpha := E[ product_i (X_i - mu_i)**alpha ], where
    i ranges over the dimension of the keys of p.
    """
    
    states, probabilities = domain.from_mapping(p)
    mu = expectation((states, probabilities))
    diffs = (states - numpy.asarray(mu)[:, numpy.newaxis])
    if exponent != 1:
        diffs **= exponent
    product = numpy.multiply.reduce(diffs, axis = 0)
    alpha = expectation((product, probabilities))
    assert alpha.shape == (1, )
    return alpha[0]
    
    
def variance(p):
    """
    variance(p) -> sigma_squared
    
    Returns the variance sigma_squared, treating the mapping p as a distribution
    p : states -> probabilities.
    """
    return _metavariance(p, exponent=2)

def covariance(p):
    """
    covariance(p) -> cov
    
    Returns the covariance cov, treating the mapping p as a distribution
    p : states -> probabilities.
    """
    return _metavariance(p, exponent=1)

def compress(p, epsilon):
    """
    compress(p, epsilon) -> compressed epsilon-approximation of p
    
    Returns an approximation of the mapping p, treating p as a distribution
    p : states -> probabilities. The returned approximation is *compressed*,
    in the sense that it is the approximation with the smallest support, while
    the error between p and the approximation is within epsilon (L1 norm).
    """
    
    if not (0.0 <= epsilon <= 1.0):
        raise ValueError('epsilon must be within range: 0.0 <= epsilon <= 1.0')
    
    p_compressed = {}
    
    if len(p) > 0:
        # create array representation of distribution
        states, probabilities = domain.from_mapping(p)
        
        # order entries with respect to increasing probability
        order = numpy.argsort(probabilities)
        states = states.transpose()[order]
        probabilities = probabilities[order]
        
        # discard the largest number of states while keeping the
        # corresponding net probability discarded below epsilon
        cumulative_probability = numpy.add.accumulate(probabilities)
        approximation = (cumulative_probability >= epsilon)
        states = states[approximation]
        probabilities = probabilities[approximation]
        
        assert len(states) == len(probabilities)
        
        # convert approximation back to a sparse dictionary format
        for state, probability in itertools.izip(states, probabilities):
            p_compressed[tuple(state)] = probability
        
    return p_compressed
