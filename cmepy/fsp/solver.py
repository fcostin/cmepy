"""
An implementation of FSP with compression.
"""

import numpy
import cmepy.restorable_solver
import cmepy.domain
import cmepy.state_enum
import exceptions

def create(model, domain_states, domain_enum, domain_expander, **kwargs):
    """
    Returns an experimental *dense* FSP based CME solver.

    See the documentation of the ``cmepy.fsp.FspSolver`` class for
    more information about the returned solver's methods.

    The returned solver will adaptively expand its domain, as necessary,
    in order to keep the domain truncation error below the epsilon
    thresholds specified when the solver ``step`` method is called.

    The ``domain_expander`` argument is used to implement the domain
    expansion strategy. This argument is used by the FSP implementation as
    follows::

        expanded_domain = domain_expander.expand(
            domain_states = domain,
            p = p,
            p_sink = p_sink,
            t = t
        )

    where ``domain``, ``p``, ``p_sink`` and ``t`` are the current domain,
    solution, truncation error and time, respectively. Note that these are
    all passed to the ``domain_expander``'s ``expand`` method as keyword
    arguments.

    Any additional keyword arguments passed to this ``create`` function are
    treated in the same way as keyword arguments passed to the
    ``cmepy.solver.create`` function. Please refer to the documentation for
    the ``cmepy.solver.create`` function for additional details.
    """

    kwargs['domain_states'] = domain_states
    kwargs['domain_enum'] = domain_enum

    return FspSolver(
        cmepy.restorable_solver.create(
            model,
            sink = True,
            **kwargs
        ),
        domain_states,
        domain_enum,
        domain_expander
    )

class ExpansionFailureError(exceptions.StandardError):
    """
    Exception raised if a failure occurs while expanding the domain states.

    Attributes:
        msg  -- explanation of the error
    """

    def __init__(self, msg):
        self.msg = msg
        exceptions.StandardError.__init__(self)


class FspSolver(object):
    """
    FspSolver is a CME solver that adaptively expands the domain using FSP.
    """
    def __init__(self, restorable_solver, initial_domain, domain_enum, domain_expander):
        """
        Creates an FspSolver for given solver, domain states, domain enum, and domain_expander
        """
        self.solver = restorable_solver
        self.domain_states = initial_domain
        self.domain_enum = domain_enum
        self.domain_expander = domain_expander

    def step(self, t, epsilon):
        """
        Advance solution to time ``t`` at the cost of at most ``epsilon`` error.
        """

        step_epsilon = self.solver.restore_point_error + epsilon
        number_of_states = numpy.size(self.domain_states, 1)

        while True:
            self.solver.step(t)
            p, p_sink = self.solver.y

            if p_sink > step_epsilon:
                # expand domain states
                expanded_states = self.domain_expander.expand(
                    domain_states = self.domain_states,
                    p = p,
                    p_sink = p_sink,
                    t = t
                )
                # we need to translate the dense p, defined wrt to
                # an enum of the domain states, to a dense p wrt to
                # an enum of these new expanded domain states

                # get the domain states that p_0 is defined over
                p_0 = self.solver.restore_args['p_0']
                p_0_domain = self.solver.restore_args['domain_enum'].states(
                    numpy.arange(len(p_0)),
                )
                # define the new state enum for the expanded domain
                expanded_enum = cmepy.state_enum.StateEnum(expanded_states)
                # figure out the indices to store each domain state in
                # according to the new state enum
                domain_indices = expanded_enum.indices(p_0_domain)
                # make a new dense distribution
                expanded_p_0 = numpy.zeros(
                    (expanded_enum.size, ),
                    dtype = numpy.float
                )
                # copy the probabilities from p_0 across into the
                # correct indices of the expanded version of p_0
                expanded_p_0[domain_indices] = p_0
                # update fsp solver bookkeeping
                self.domain_states = expanded_states
                self.domain_enum = expanded_enum
                # check that expansion did in fact add some extra states
                if numpy.size(self.domain_states, 1) <= number_of_states:
                    lament = 'expansion did not increase size of domain'
                    raise ExpansionFailureError(lament)
                # restore solver to previous state, but use expanded domain
                self.solver.restore(
                    domain_states = self.domain_states,
                    domain_enum = self.domain_enum,
                    p_0 = expanded_p_0,
                )
            else:
                self.solver.set_restore_point()
                break

    @property
    def y(self):
        """
        Read-only property, returning a *copy* of the current solution y.
        """
        return self.solver.y
    
    @property
    def t(self):
        """
        Read-only property, returning the current solution time t.
        """
        return self.solver.t
    
    @property
    def dy_dt(self):
        """
        Read-only property, returning the differential equations dy_dt.
        """
        return self.solver.dy_dt