#!/usr/bin/env python

"""
@package ion.services.mi.util Utility functions for MI
@file ion/services/mi/util.py
@authorBill French
@brief Common MI utility functions
"""

__author__ = 'Bill French'
__license__ = 'Apache 2.0'

def dict_equal(ldict, rdict, ignore_keys=[]):
    """
    Compare two dictionary.  assumes both dictionaries are flat
    @param ldict: left side dict
    @param rdict: right side dict
    @param ignore_keys: list of keys that we don't compare
    @return: true if equal false if not
    """
    if(not isinstance(ignore_keys, list)):
        ignore_keys = [ignore_keys]

    for key in set(ldict.keys() + rdict.keys()):
        if(key in ldict.keys() and key in rdict.keys()):
            if(not key in ignore_keys and ldict[key] != rdict[key]):
                return False
        else:
            return False
        pass

    return True


