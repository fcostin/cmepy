CmePy v0.3
==========
--------------------------------------------
a Chemical Master Equation solver for Python
--------------------------------------------

Features
~~~~~~~~
 *   models can be defined using species or reaction counts
 *   both dense 'rectangular' and sparse state spaces are supported
 *   error due to state space truncation may be tracked with an FSP-style
     'sink' state
 *   reaction propensities may be scaled by time dependent coefficients
 *   common statistical results are easily obtained

Dependencies
~~~~~~~~~~~~

CmePy supports Python_ 2.7 and depends upon SciPy_, Numpy_ and Matplotib_ .

In the past, CmePy has also run under Python_ 2.5 and 2.6.

Getting Started
~~~~~~~~~~~~~~~

Here is a brief example of how to download CmePy, install CmePy's
dependencies into an isolated virtual environment, run all the unit
tests, then install CmePy into the virtual environment.

Prerequisites:

 *    you are running Ubuntu 16.04 LTS or a similar Linux distribution
 *    Git_, Python_ 2.7 and Virtualenv_ are installed.

In order for Virtualenv to work, you must use the same environment for
all steps in this example.

First, create a fresh virtual environment to use for CmePy and its dependencies::

	mkdir -p ~/cmepy_working_dir
	cd ~/cmepy_working_dir
	virtualenv .venv

Activate the virtual environment::

	source .venv/bin/activate

Next, download the latest version of CmePy::

	git clone git://github.com/hegland/cmepy.git

Install CmePy's runtime and test dependencies into the virtual environment::

	cd cmepy
	pip install -r requirements.txt
	pip install -r test_requirements.txt

Run the unit test suite to confirm that all tests are passing::

	pytest

Finally, install CmePy into the virtual environment::

	python setup.py install


Documentation
~~~~~~~~~~~~~
See http://hegland.github.com/cmepy/


Authors
~~~~~~~

 * Reuben Fletcher-Costin ( reuben dot fletchercostin at gmail dot com )
 * Markus Hegland ( markus dot hegland at anu dot edu dot au )


.. _Python: http://www.python.org/
.. _SciPy: http://www.scipy.org/
.. _Numpy: http://numpy.scipy.org/
.. _Matplotlib: http://matplotlib.sourceforge.net/
.. _Git: http://git-scm.com/
.. _Virtualenv: https://virtualenv.pypa.io/en/stable/

