#!/usr/bin/env python

"""
@package mi.instrument.teledyne.workhorse_adcp_5_beam_600khz.ooicore.util
@file    mi/instrument/teledyne/workhorse_adcp_5_beam_600khz/ooicore/util/__init__.py
@author Carlos Rueda
@brief Misc utilities
"""

__author__ = 'Carlos Rueda'
__license__ = 'Apache 2.0'

import time
import socket
from mi.core.mi_logger import mi_logger as log


def connect_socket(host, port, max_attempts=4, time_between_attempts=10):
    """
    Establishes a socket connection, which is attempted a number of times.

    @param host
    @param port
    @param max_attempts Maximum number of socket connection attempts
                        (4 by default).
    @param time_between_attempts Time in seconds between attempts
                        (10 by default).

    @retval open socket

    @throws socket.error The socket.error that was raised during the
                     last attempt.
    """
    last_error = None
    attempt = 0
    sock = None
    while sock is None and attempt < max_attempts:
        attempt += 1
        log.info("Trying to connect to %s:%s (attempt=%d)" %
                 (host, port, attempt))
        try:
            s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            s.connect((host, port))
            sock = s
        except socket.error, e:
            log.info("Socket error while trying to connect: %s" %
                      str(e))
            last_error = e
            if attempt < max_attempts:
                log.info("Re-attempting in %s secs ..." %
                          str(time_between_attempts))
                time.sleep(time_between_attempts)

    if sock:
        log.info("Connected to %s:%s" % (host, port))
        return sock
    else:
        raise last_error


def prefix(s, prefix='\n    |'):
    s = str(s)
    return "%s%s" % (prefix, s.replace('\n', prefix))


def isascii(c, printable=True):
    o = ord(c)
    return (o <= 0x7f) and (not printable or 0x20 <= o <= 0x7e)