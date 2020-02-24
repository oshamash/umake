#! /usr/bin/env python

from distutils.core import setup
from setuptools import find_packages

# pip install -e .                                              # install from source
# python setup.py sdist                                         # create dist
# sudo pip install --no-index --find-links=./dist/ xray         # install dist

with open('requirements.txt') as f:
    required = f.read().splitlines()

setup(
    name='umake',
    version='0',
    package_dir={'':'.'},
    # packages=find_packages(where="./cli/"),
    install_requires=required,
    license='MIT',
    scripts=['./umake']
)
