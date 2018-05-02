#!python

"""
CmePy setup script
"""

VERSION = '0.3.1'

from setuptools import setup, find_packages
setup(
    name = 'cmepy',
    version = VERSION,
    
    package_data = {'':['*.txt']},

    packages = find_packages()
)

