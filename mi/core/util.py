#!/usr/bin/env python

"""
@package ion.services.mi.util Utility functions for MI
@file ion/services/mi/util.py
@authorBill French
@brief Common MI utility functions
"""

__author__ = 'Bill French'
__license__ = 'Apache 2.0'

def dict_equal(ldict, rdict):
    """
    Compare two dictionary.  assumes both dictionaries are flat
    @param ldict: left side dict
    @param rdict: right side dict
    @return: true if equal false if not
    """
    for key in set(ldict.keys() + rdict.keys()):
        if(key in ldict.keys() and key in rdict.keys()):
            if(ldict[key] != rdict[key]):
                return False
        else:
            return False
        pass

    return True


