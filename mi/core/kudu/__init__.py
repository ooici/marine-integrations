#!/usr/bin/env python
# Copyright 2012, 2013, 2014 The Regents of the University of California
"""BRTT Antelope API wrapper"""

import os, sys

# Antelope libs need to see this env var, otherwise blocking calls hold the GIL
# preventing other threads from running.
os.environ['ANTELOPE_PYTHON_GILRELEASE'] = '1'

# This is where Antelope puts it's python modules. Update for other antelope
# versions.
sys.path.append('/opt/antelope/5.3/data/python/antelope')

