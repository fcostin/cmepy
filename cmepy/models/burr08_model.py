"""
model of two competing clonotypes
"""

from cmepy import model

def __create_burr08_model():
    """
    reaction count model of two competing clonotypes
    """
    
    import numpy
    
    # we first define the mappings from reaction counts to species counts
    species_count_a = lambda *r : numpy.maximum(10 + r[0] - r[1], 0)
    species_count_b = lambda *r : numpy.maximum(10 + r[2] - r[3], 0)
    
    # we now define the reaction propensities using the species counts
    def reaction_a_birth(*r):
        """
        propensity of birth reaction for species a
        """
        s_a = species_count_a(*r)
        s_b = species_count_b(*r)
        return numpy.where(s_a + s_b > 0,
                           60*s_a*(numpy.divide(0.5, s_a + s_b) +
                                   numpy.divide(0.5, (s_a + 10*100))),
                           0.0)
    
    reaction_a_decay = lambda *r : species_count_a(*r)
    
    def reaction_b_birth(*r):
        """
        propensity of birth reaction for species b
        """
        s_a = species_count_a(*r)
        s_b = species_count_b(*r)
        return numpy.where(s_a + s_b > 0,
                           60*s_b*(numpy.divide(0.5, s_a + s_b) +
                                   numpy.divide(0.5, (s_b + 10*100))),
                           0.0)
    
    reaction_b_decay = lambda *r : species_count_b(*r)
    
    m = model.create(
        name = 'T Cell clonoTypes (Time Independent Propensities)',
        shape = (11, )*4,
        propensities = (
            reaction_a_birth,
            reaction_a_decay,
            reaction_b_birth,
            reaction_b_decay
        ),
        transitions = (
            (1, 0),
            (-1, 0),
            (0, 1),
            (0, -1)
        ),
        reactions = (
            '*->A',
            'A->*',
            '*->B',
            'B->*'
        ),
        species_counts = (
            species_count_a,
            species_count_b
        ),
        species = (
            'A',
            'B'
        )
    )
    return m

BURR08 = __create_burr08_model()
