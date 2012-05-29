#!/usr/bin/env python

"""
@package mi.instrument.teledyne.workhorse_adcp_5_beam_600khz.ooicore.util
@file    ion/services/mi/drivers/vadcp/util/__init__.py
@author Carlos Rueda
@brief Misc utilities
"""

__author__ = 'Carlos Rueda'
__license__ = 'Apache 2.0'


def prefix(s, prefix='\n    |'):
    s = str(s)
    return "%s%s" % (prefix, s.replace('\n', prefix))


def isascii(c, printable=True):
    o = ord(c)
    return (o <= 0x7f) and (not printable or 0x20 <= o <= 0x7e)
