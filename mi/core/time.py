#!/usr/bin/env python

"""
@package mi.core.time
@file mi/core/time.py
@author Bill French
@brief Common time functions for drivers
"""

__author__ = 'Bill French'
__license__ = 'Apache 2.0'

from mi.core.log import get_logger ; log = get_logger()

import datetime
import gevent

def get_timestamp_delayed(format):
    '''
    Return a formatted date string of the current utc time,
    but the string return is delayed until the next second
    transition.

    Formatting:
    http://docs.python.org/library/time.html#time.strftime

    @param format: strftime() format string
    @return: formatted date string
    @raise ValueError if format is None
    '''
    if(not format):
        raise ValueError

    result = None
    now = datetime.datetime.utcnow()

    # If we are too close to a second transition then sleep for a bit.
    if(now.microsecond < 100000):
        gevent.sleep(0.2)
        now = datetime.datetime.utcnow()

    current = datetime.datetime.utcnow()
    while(current.microsecond > now.microsecond):
        current = datetime.datetime.utcnow()

    return current.strftime(format)
