#!/usr/bin/env python

"""
@package mi.instrument.teledyne.workhorse_adcp_5_beam_600khz.ooicore.util.pd0_filter
@file    mi/instrument/teledyne/workhorse_adcp_5_beam_600khz.ooicore/util/pd0_filter.py
@author Carlos Rueda
@brief PD0 ensemble extractor filter
See mi/instrument/teledyne/workhorse_adcp_5_beam_600khz/ooicore/test/direct.py for example usage.
"""

__author__ = 'Carlos Rueda'
__license__ = 'Apache 2.0'

from mi.instrument.teledyne.workhorse_adcp_5_beam_600khz.ooicore.pd0 import PD0DataStructure
from mi.instrument.teledyne.workhorse_adcp_5_beam_600khz.ooicore.util.coroutine import coroutine

from mi.core.mi_logger import mi_logger
log = mi_logger


# Some min data size to try to construct a structure and extract
# the actual length of the ensemble. The number 30 seems enough
# according to various runs.
MIN_LENGTH_TRY_ENSEMBLE = 30


@coroutine
def pd0_filter(receiver):
    """
    A consumer generator that handles and filters out incoming PD0 ensembles,
    if any.

    It expects to be sent tuples of the form (xelems, buffer) where:
    - xelems is a dict of any extracted elements, never None.
    - buffer is a binary string to be analyzed (could be None).

    There are two cases for sending data to the receiver:

    Upon extracting a PD0 ensemble from the stream, this filter creates a
    PD0DataStructure instance, pd0, and calls
        receiver.sends( (xelems.update({'pd0', pd0}), None) ).

    For any unhandled bytes in the stream, this filter calls
        receiver.sends( (xelems.update({'pd0', None}), send_buffer) )
    where send_buffer is a buffer of unrecognized bytes.
    """

    data = ''  # never None

    # the length of the current ensemble. Initialized with a
    # small number (but enough to extract the actual len):
    ensemble_len = MIN_LENGTH_TRY_ENSEMBLE

    while True:
        xelems, buffer = (yield)

#        for rcv in buffer:
        while buffer:
            idx = buffer.find('\x7f')
            if idx < 0:
                if len(data) == 0:
                    xelems['pd0'] = None
                    receiver.send((xelems, buffer))
                    break  # ie., go receive more.

            elif idx > 0:
                if len(data) == 0:
                    xelems['pd0'] = None
                    receiver.send((xelems, buffer[0:idx]))
                    buffer = buffer[idx:]

            rcv = buffer[0]
            buffer = buffer[1:]
            if rcv == '\x7f':
                if len(data) == 0:
                    log.debug("RECEIVING DATA **")

            elif len(data) == 0:
                xelems['pd0'] = None
                receiver.send((xelems, rcv))
                continue

            data += rcv

            if len(data) < ensemble_len:
                continue

            # if ensemble_len is our small number, it will still allow us
            # to "try" a structure and retrieve the actual ensemble length:
            #
            try:
                pd0 = PD0DataStructure(data)
                ensemble_len = pd0.getNumberOfBytesInEnsemble()
            except Exception, e:
                #
                # ok, we are not yet seeing the beginning of a structure, just
                # shift the data array a position and continue
                # receiving:
                #
                data = data[1:]
                continue

            if len(data) < ensemble_len:
                #
                # we don't yet have enough of the ensemble, just continue
                # receiving:
                #
                continue

            # we have our complete ensemble:
            ensemble = data[:ensemble_len]
            pd0 = PD0DataStructure(ensemble)
            xelems['pd0'] = pd0
            receiver.send((xelems, None))

            data = data[ensemble_len:]

            ensemble_len = MIN_LENGTH_TRY_ENSEMBLE
