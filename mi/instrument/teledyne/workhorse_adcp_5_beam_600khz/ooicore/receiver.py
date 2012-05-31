#!/usr/bin/env python

"""
@package mi.instrument.teledyne.workhorse_adcp_5_beam_600khz.ooicore.receiver
@file    mi/instrument/teledyne/workhorse_adcp_5_beam_600khz/ooicore/receiver.py
@author Carlos Rueda
@brief Receiver runnable for the VADCP instrument client module.
"""

__author__ = 'Carlos Rueda'
__license__ = 'Apache 2.0'

import time
import socket
import os

from mi.instrument.teledyne.workhorse_adcp_5_beam_600khz.ooicore.defs import PROMPT, State
from mi.instrument.teledyne.workhorse_adcp_5_beam_600khz.ooicore.util.coroutine import coroutine
from mi.instrument.teledyne.workhorse_adcp_5_beam_600khz.ooicore.util.ts_filter import timestamp_filter
from mi.instrument.teledyne.workhorse_adcp_5_beam_600khz.ooicore.util.pd0_filter import pd0_filter

from mi.core.mi_logger import mi_logger as log


def build_receiver(sock, bufsize=4096, data_listener=None, outfile=None,
                 prefix_state=True):
    """
    Creates a returns a receiver object that handles all received responses
    from the connection, keeping relevant information and a state.

    @param sock To read in from the instrument, sock.recv(bufsize)
    @param bufsize To read in from the instrument, sock.recv(bufsize)
    @param data_listener
    @param outfile
    @param prefix_state
    """

    receiver = _Receiver(sock, bufsize, data_listener, outfile, prefix_state)

    # use greenlet if env variable "green_rcvr" is defined
    _use_greenlet = False
    if "green_rcvr" in os.environ:
        _use_greenlet = True
        # definition takes effect only once:
        del os.environ["green_rcvr"]

    if _use_greenlet:
        from gevent import Greenlet
        runnable = Greenlet(receiver.run)
        log.info("Created Greenlet-based _Receiver (env var 'green_rcvr' "
                 "defined)")
    else:
        from threading import Thread
        runnable = Thread(target=receiver.run)
        runnable.setDaemon(True)
        log.info("Created Thread-based _Receiver")

    receiver._thr = runnable

    return receiver


class _Receiver(object):
    """
    Handles all received responses from the connection, keeping relevant
    information and a state.
    """

    # MAX_NUM_LINES: Keep this max number of received lines. Should be greater
    # that any single response. In preliminary tests an "RR?" command (get
    # recorder file directory) generated about 500 lines. Note that PD0
    # ensembles and timestamps are not included in self._lines.
    # TODO review this MAX_NUM_LINES fixed value
    MAX_NUM_LINES = 1024

    def __init__(self, sock, bufsize=4096, data_listener=None, outfile=None,
                 prefix_state=True):
        """
        """
        self._sock = sock
        self._bufsize = bufsize
        self._data_listener = data_listener
        self._outfile = outfile
        self._prefix_state = prefix_state

        self._thr = None
        self._active = False
        self._state = None

        self._latest_ts = None
        self._latest_pd0 = None

        self.reset_internal_info()

    def start(self):
        self._thr.start()

    def reset_internal_info(self):
        self._last_line = ''
        self._new_line = ''
        self._lines = []
        self._recv_time = 0  # time of last received buffer
        self._set_state(State.TBD)

    @property
    def state(self):
        return self._state

    @property
    def recv_time(self):
        return self._recv_time

    @property
    def lines(self):
        return self._lines

    @property
    def latest_pd0(self):
        return self._latest_pd0

    def set_latest_pd0(self, pd0):
        self._latest_pd0 = pd0

    def _recv(self):
        """
        Main read method. Reads from the socket, updates the time of last
        received buffer, updates the outfile if any, and return the buffer.
        """
        log.debug("reading")
        try:
            recv = self._sock.recv(self._bufsize)
        except socket.error, e:
            log.debug("socket.error: %s" % e)
            self._active = False
            return None

        log.debug("read %s bytes" % len(recv))
        self._recv_time = time.time()
        self._update_outfile(recv)
        return recv

    def _set_state(self, state):
        if self._state != state:
            log.info("{{TRANSITION: %s => %s %r}}" % (self._state, state,
                                                   self._last_line))
            if self._last_line:
                log.debug("LINES=\n\t|%s" % "\n\t|".join(self._lines))
            self._state = state

    def end(self):
        self._active = False

    def _update_outfile(self, buffer):
        """
        Updates the outfile if any.
        @param buffer buffer that has just been received
        """
        if self._outfile:
            if self._prefix_state:
                prefix = "\n%20s| " % self._state
                buffer = buffer.replace('\n', prefix)
            self._outfile.write(buffer)
            self._outfile.flush()

    def _end_outfile(self):
        """
        Writes a mark to the outfile to indicate that
        the receiving thread has ended.
        """
        if self._outfile:
            self._outfile.write('\n\n<_Receiver ended.>\n\n')
            self._outfile.flush()

    @coroutine
    def sink(self):
        """
        The sink of the stream parsing pipeline.
        """
        while True:
            xelems, buffer = (yield)
            ts = xelems.get('latest_ts', None)
            if ts:
                self._timestamp_received(ts)

            pd0 = xelems.get('pd0', None)
            if pd0:
                self._pd0_received(pd0)

            if buffer:
                self._buffer_received(buffer)

    def _timestamp_received(self, ts):
        self._latest_ts = ts
        log.debug("{TIMESTAMP=%s}" % (ts))

    def _pd0_received(self, pd0):
        self._set_state(State.COLLECTING_DATA)
        self._latest_pd0 = pd0
        log.debug("PD0=\n    | %s" % (str(pd0).replace('\n', '\n    | ')))
        if self._data_listener:
            self._data_listener(pd0)

    def _buffer_received(self, buffer):
#        sys.stdout.write(buffer)
#        sys.stdout.flush()
        numl = self._update_lines(buffer)
        if self._last_line.rstrip() == PROMPT:
            self._set_state(State.PROMPT)
        elif numl:
            self._state = None

    def _update_lines(self, buffer):
        """
        Updates the internal info about received lines.
        @param buffer buffer that has just been received
        """
        numl = 0
        for c in buffer:
            if c == '\n':
                numl += 1
                self._last_line = self._new_line
                self._new_line = ''
                self._lines.append(self._last_line)
                if len(self._lines) > self.MAX_NUM_LINES:
                    self._lines = self._lines[1 - self.MAX_NUM_LINES:]
#            elif c != '\r' and not isascii(c):
#                print "NOT_ASCII=%r" % c
            else:
                self._new_line += c
        return numl

    def run(self):
        """
        Runs the receiver.
        """
        log.info("_Receiver running")
        self._active = True

        # set up pipeline
        pipeline = timestamp_filter(pd0_filter(self.sink()))

        # and read in and push received data into the pipeline:
        while self._active:
            recv = self._recv()
            if recv is not None:
                pipeline.send(({}, recv))

        pipeline.close()
        self._end_outfile()
        log.info("_Receiver ended.")
