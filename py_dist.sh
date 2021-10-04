#!/bin/bash
# It generates Python packages if no test is broken
venv/bin/python setup.py test && venv/bin/python setup.py sdist bdist_wheel
