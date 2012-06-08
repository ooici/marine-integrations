#!/usr/bin/env python

"""
@package mi.instrument.teledyne.workhorse_adcp_5_beam_600khz.ooicore.util.ts_filter
@file    mi/instrument/teledyne/workhorse_adcp_5_beam_600khz/ooicore/util/ts_filter.py
@author Carlos Rueda
@brief Timestamp extractor filter
See mi/instrument/teledyne/workhorse_adcp_5_beam_600khz/ooicore/test/direct.py for example usage.
"""

__author__ = 'Carlos Rueda'
__license__ = 'Apache 2.0'

import re

from mi.instrument.teledyne.workhorse_adcp_5_beam_600khz.ooicore.util.coroutine import coroutine

from mi.core.mi_logger import mi_logger as log


# The opening timestamp tag
TS_OPEN_STRING = '<OOI-TS'

# Pattern for the opening timestamp tag
# example: <OOI-TS 2012-05-18T00:25:44.225274 XS>
TS_OPEN_PATTERN = re.compile(
 TS_OPEN_STRING + r'\s+(\d+-\d+-\d+T\d+\:\d+\:\d+\.\d+ \w+)>(\n|\r\n)')

# A number that is greater than any actual opening timestamp tag. It is
# used to safely handle the possibility of any partial match happening at
# the end of the current buffer being analyzed
TS_OPEN_SAFE_SIZE = 40

# The closing timestamp tag
TS_CLOSE_STRING = '<\\00I-TS>\r\n'


@coroutine
def timestamp_filter(receiver):
    """
    A consumer generator that filters out incoming timestamps, if any.

    It expects to be sent tuples of the form (xelems, buffer) where:
    - xelems is a dict of any extracted elements, never None.
    - buffer is a binary string to be analyzed (could be None).

    It calls:
      receiver.sends( (xelems.update({'latest_ts', latest_ts}), send_buffer) )
    where latest_ts is the latest received and extracted timestamp (which
    could be None if not yet known or already reported in a previous send) and
    send_buffer is any unprocessed bytes in the incoming stream, which can be
    None if the upstream component hasn't provided any buffer to process.
    """

    # latest received timestamp
    global latest_ts
    latest_ts = None

    def send(xelems, buffer):
        global latest_ts
        xelems['latest_ts'] = latest_ts
        latest_ts = None  # only reported once
        receiver.send((xelems, buffer))

    # we start by expecting the opening TS tag
    expecting_open_ts = True
    buffer = ''

    while True:
        xelems, rcv = (yield)
        if not rcv:
            # just forward to the receiver
            send(xelems, None)
            continue

        buffer = buffer + rcv
        log.debug("buffer_len = %s" % len(buffer))
        need_more = False

        while len(buffer) > 0 and not need_more:

            if expecting_open_ts:
                mo = TS_OPEN_PATTERN.search(buffer)
                if mo:
                    open_pos = mo.start()
                    log.debug("TS found = %s at %s" % (mo.groups(),
                                                           open_pos))

                    if open_pos > 0:
                        log.debug("send %s bytes before start" % open_pos)
                        send(xelems, buffer[0: open_pos])

                    # save this received timestamp for next send
                    latest_ts = mo.group(1)

                    buffer = buffer[mo.end():]
                    expecting_open_ts = False
                else:
                    (send_buf, buf) = _partial_match(buffer,
                                                     TS_OPEN_STRING,
                                                     TS_OPEN_SAFE_SIZE)

                    if send_buf:
                        send(xelems, send_buf)
                    else:
                        need_more = True
                    buffer = buf

            else:  # expecting closing TS tag
                close_pos = buffer.find(TS_CLOSE_STRING)
                if close_pos >= 0:
                    if close_pos > 0:
                        log.debug("send %s bytes before end" % close_pos)
                        send(xelems, buffer[0: close_pos])

                    # just report closing tag found
                    log.debug("closing tag at %s" % close_pos)

                    buffer = buffer[close_pos + len(TS_CLOSE_STRING):]
                    expecting_open_ts = True
                else:
                    (send_buf, buf) = _partial_match(buffer,
                                                     TS_CLOSE_STRING,
                                                     len(TS_CLOSE_STRING))

                    if send_buf:
                        send(xelems, send_buf)
                    else:
                        need_more = True
                    buffer = buf


def _partial_match(buffer, string, safe_size):
    """
    Helper to handle the possible edge case of a string partially
    occurring at the end of buffer currently under analysis.

    @param buffer buffer to inspect
    @param string string to find
    @param safe_size size of buffer suffix where the partial match is to be
            attempted.

    @retval A partition of the given buffer into two parts (send_buf, buf)
            where:
               send_buf: buffer that can be immediately sent out to receiver;
                         can be '' meaning that more data is required to
                         continue parsing for timestamp related tags.
               buf: continue analyzing this buffer.
    """

    # search string starting from this position:
    start_pos = max(0, len(buffer) - safe_size)
    pos = buffer.find(string, start_pos)
    if pos >= 0:
        # found completely:
        retval = (buffer[0: pos], buffer[pos:])
    else:
        # try partial match:
        prefix = string
        while not buffer.startswith(prefix, len(buffer) - len(prefix)):
            prefix = prefix[:len(prefix) - 1]

        if prefix:
            # there is a partial match:
            retval = (buffer[0: -len(prefix)], buffer[-len(prefix):])
        else:
            retval = (buffer, '')

    (send_buf, buf) = retval
    assert buffer == send_buf + buf, "output must be partition of input"
    return retval