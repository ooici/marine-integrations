#!/usr/bin/env python

"""
@package mi.core.time
@file mi/core/time.py
@author Bill French
@brief Common time functions for drivers
"""
# Needed because we import the time module below.  With out this '.' is search first
# and we import ourselves.
from __future__ import absolute_import

__author__ = 'Bill French'
__license__ = 'Apache 2.0'

from mi.core.log import get_logger ; log = get_logger()

import datetime
import ntplib
import time
import re
from dateutil import parser

DATE_PATTERN = r'^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(\.\d+)?Z?$'
DATE_MATCHER = re.compile(DATE_PATTERN)

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
        time.sleep(0.2)
        now = datetime.datetime.utcnow()

    current = datetime.datetime.utcnow()
    while(current.microsecond > now.microsecond):
        current = datetime.datetime.utcnow()

    return time.strftime(format, time.gmtime())


def get_timestamp(format):
    '''
    Return a formatted date string of the current utc time.

    Formatting:
    http://docs.python.org/library/time.html#time.strftime

    @param format: strftime() format string
    @return: formatted date string
    @raise ValueError if format is None
    '''
    if(not format):
        raise ValueError

    return time.strftime(format, time.gmtime())

def string_to_ntp_date_time(datestr):
        """
        Extract an ntp date from a ISO8601 formatted date string.
        @param str an ISO8601 formatted string containing date information
        @retval an ntp date number (seconds since jan 1 1900)
        @throws InstrumentParameterException if datestr cannot be formatted to
        a date.
        """
        if not isinstance(datestr, str):
            raise IOError('Value %s is not a string.' % str(datestr))
        if not DATE_MATCHER.match(datestr):
            raise ValueError("date string not in ISO8601 format YYYY-MM-DDTHH:MM:SS.SSSSZ")

        try:
            # This assumes input date string are in UTC (=GMT)
            if datestr[-1:] != 'Z':
                datestr += 'Z'

            # the parsed date time represents a GMT time, but strftime
            # does not take timezone into account, so these are seconds from the
            # local start of 1970
            local_sec = float(parser.parse(datestr).strftime("%s.%f"))
            # remove the local time zone to convert to gmt (seconds since gmt jan 1 1970)
            gmt_sec = local_sec - time.timezone
            # convert to ntp (seconds since gmt jan 1 1900)
            timestamp = ntplib.system_to_ntp_time(gmt_sec)

        except ValueError as e:
            raise ValueError('Value %s could not be formatted to a date. %s' % (str(datestr), e))

        log.debug("converting time string '%s', unix_ts: %s ntp: %s", datestr, gmt_sec, timestamp)

        return timestamp

def time_to_ntp_date_time(unix_time=None):
        """
        return an NTP timestamp.  Currently this is a float, but should be a 64bit fixed point block.
        TODO: Fix return value
        @param unit_time: Unix time as returned from time.time()
        """
        if unix_time is None:
            unix_time = time.time()

        timestamp = ntplib.system_to_ntp_time(unix_time)
        return float(timestamp)
