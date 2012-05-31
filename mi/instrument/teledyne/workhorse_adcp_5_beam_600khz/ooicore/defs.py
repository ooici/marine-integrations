#!/usr/bin/env python

"""
@package mi.instrument.teledyne.workhorse_adcp_5_beam_600khz.ooicore.defs
@file    mi/instrument/teledyne/workhorse_adcp_5_beam_600khz/ooicore/defs.py
@author Carlos Rueda

@brief Common definitions
"""

__author__ = 'Carlos Rueda'
__license__ = 'Apache 2.0'


from mi.core.common import BaseEnum

# default value for the generic timeout. By default, 30 secs
DEFAULT_GENERIC_TIMEOUT = 30

PROMPT = '>'


class State(object):
    """Instrument states"""
    COLLECTING_DATA = "COLLECTING_DATA"
    TBD = "TBD"
    PROMPT = "PROMPT"


class ClientException(Exception):
    """Some exception occured in TrhphClient."""


class TimeoutException(ClientException):
    """Timeout while waiting for some event or state in the instrument."""

    def __init__(self, timeout, msg=None,
                 expected_state=None, curr_state=None, lines=None):

        self.timeout = timeout
        self.expected_state = expected_state
        self.curr_state = curr_state
        self.lines = lines
        if msg:
            self.msg = msg
        elif expected_state:
            self.msg = "timeout while expecting state %s" % expected_state
            if curr_state:
                self.msg += " (curr_state=%s)" % curr_state
        else:
            self.msg = "timeout reached"

    def __str__(self):
        s = "TimeoutException(msg='%s'" % self.msg
        s += "; timeout=%s" % str(self.timeout)
        if self.expected_state:
            s += "; expected_state=%s" % self.expected_state
        if self.curr_state:
            s += "; curr_state=%s" % self.curr_state
        if self.lines:
            s += "; lines=%s" % "\n".join(self.lines)
        s += ")"
        return s


class MetadataSections(BaseEnum):
    # code = (section-name, command)
    SYSTEM_CONFIG = ('System configuration', 'PS0')
    SYSTEM_FEATURES = ('System features', 'OL')
    SYSTEM_SERIAL_CONFIG = ('System serial config', 'CB?')
    TRANSFORMATION_MATRIX = ('Instrument Transformation Matrix', 'PS3')
    DEPLOYMENTS_RECORDED = ('Number of Deployments Recorded', 'RA')
    RECORDER_SPACE = ('Recorder Space used/free (bytes)', 'RF')
    RECORDER_FILE_DIRECTORY = ('Recorder File Directory', 'RR')


md_section_names = [name for (name, _) in MetadataSections.list()]
