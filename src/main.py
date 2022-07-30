#!/usr/bin/env python

# Run as:
# (...)/src/main.py

import sys

# Check the Python version before reading any more code.
# Otherwise an older Python could trip over syntax errors before
# checking the version!

# The specified version (or later) of Python is required for at least the
# following reasons.
#
# Python 3 is required in general for good Unicode support and other features.
#
# Python 3.5 is required for subprocess.run()
#
# Python 3.7 is required for the dictionaries to be ordered by default.
# I don't generally rely on this, but the first dictionary entry in
# parks.yaml is treated specially, so that requires an ordered dictionary.
if sys.version_info < (3, 7):
    sys.exit('Python 3.7 or later is required.')

import bawg
