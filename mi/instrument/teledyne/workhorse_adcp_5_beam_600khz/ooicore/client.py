#!/usr/bin/env python

"""
@package mi.instrument.teledyne.workhorse_adcp_5_beam_600khz.ooicore.client
@file    mi/instrument/teledyne/workhorse_adcp_5_beam_600khz/ooicore/client.py
@author Carlos Rueda

@brief VADCP instrument client module.
"""

__author__ = 'Carlos Rueda'
__license__ = 'Apache 2.0'

import time

from threading import Thread
sleep = time.sleep

import sys
import socket
import re

from mi.instrument.teledyne.workhorse_adcp_5_beam_600khz.ooicore.util.coroutine import coroutine
from mi.instrument.teledyne.workhorse_adcp_5_beam_600khz.ooicore.util.ts_filter import timestamp_filter
from mi.instrument.teledyne.workhorse_adcp_5_beam_600khz.ooicore.util.pd0_filter import pd0_filter
from mi.core.common import BaseEnum

import logging
from mi.core.mi_logger import mi_logger
log = mi_logger


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


class _Receiver(Thread):
    """
    Handles all received responses from the connection, keeping relevant
    information and a state.
    """

    # MAX_NUM_LINES: Keep this max number of received lines. Should be greater
    # that any single response. In prelimnary tests an "RR?" command (get
    # recorder file directory) generated about 500 lines. Note that PD0
    # ensembles and timestamps are not included in self._lines.
    # TODO review this MAX_NUM_LINES fixed value
    MAX_NUM_LINES = 1024

    def __init__(self, sock, bufsize=4096, data_listener=None, outfile=None,
                 prefix_state=True):
        """
        """
        Thread.__init__(self, name="_Receiver")
        self._sock = sock
        self._bufsize = bufsize
        self._data_listener = data_listener
        self._outfile = outfile
        self._prefix_state = prefix_state

        self._active = False
        self._state = None
        self.setDaemon(True)

        self._latest_ts = None
        self._latest_pd0 = None

        self._reset_internal_info()

    def _reset_internal_info(self):
        self._last_line = ''
        self._new_line = ''
        self._lines = []
        self._recv_time = 0  # time of last received buffer
        self._set_state(State.TBD)

    def _recv(self):
        """
        Main read method. Reads from the socket, updates the time of last
        received buffer, updates the outfile if any, and return the buffer.
        """
        recv = self._sock.recv(self._bufsize)
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
            pipeline.send(({}, recv))

        pipeline.close()
        self._end_outfile()
        log.info("_Receiver ended.")


class Client(object):
    """
    A basic client to the instrument.
    """

    def __init__(self, host, port, outfile=None, prefix_state=True):
        """
        Creates a Client instance.
        @param host
        @param port
        """
        self._host = host
        self._port = port
        self._outfile = outfile
        self._prefix_state = prefix_state
        self._sock = None
        self._rt = None  # receiver thread

        """sleep time used just before sending data"""
        self._delay_before_send = 0.2

        """generic timeout for various operations"""
        self._generic_timeout = DEFAULT_GENERIC_TIMEOUT

        log.info("VADCP client object created.")

    def set_data_listener(self, data_listener):
        """
        """
        self._data_listener = data_listener

    def set_generic_timeout(self, timeout):
        """Sets generic timeout for various operations.
           By default DEFAULT_GENERIC_TIMEOUT."""
        self._generic_timeout = timeout
        log.info("Generic timeout set to: %d" % self.generic_timeout)

    @property
    def generic_timeout(self):
        """Generic timeout for various operations.
           By default DEFAULT_GENERIC_TIMEOUT."""
        return self._generic_timeout

    def init_comms(self, callback=None):
        """
        Just calls self.connect()
        @param callback ignored
        """
        self.connect()

    def connect(self, max_attempts=4, time_between_attempts=10):
        """
        Establishes the connection and starts the receiving thread.
        The connection is attempted a number of times.
        @param max_attempts Maximum number of socket connection attempts
                            (4 by default).
        @param time_between_attempts Time in seconds between attempts
                            (10 seconds by default).
        @throws socket.error The socket.error that was raised during the
                         last attempt.
        """
        assert self._sock is None

        host, port = self._host, self._port
        last_error = None
        attempt = 0
        while self._sock is None and attempt < max_attempts:
            attempt += 1
            log.info("Trying to connect to %s:%s (attempt=%d)" %
                     (host, port, attempt))
            try:
                sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                sock.connect((host, port))
                self._sock = sock  # success.
            except socket.error, e:
                log.info("Socket error while trying to connect: %s" %
                          str(e))
                last_error = e
                if attempt < max_attempts:
                    log.info("Re-attempting in %s secs ..." %
                              str(time_between_attempts))
                    sleep(time_between_attempts)

        if self._sock:
            log.info("Connected to %s:%s" % (host, port))

#            self._sock.setsockopt(socket.SOL_SOCKET, socket.SO_RCVBUF, 1)

            log.info("creating _Receiver")
            self._rt = _Receiver(self._sock,
                                 outfile=self._outfile,
                                 data_listener=self._data_listener,
                                 prefix_state=self._prefix_state)
            log.info("starting _Receiver")
            self._rt.start()
            log.info("_Receiver thread started.")
        else:
            raise last_error

    def stop_comms(self):
        """
        Just calls self.end()
        """
        self.end()

    def end(self):
        """
        Ends the client.
        """
        if self._sock is None:
            log.warn("end() called again")
            return

        log.info("closing connection")
        try:
            if self._rt:
                self._rt.end()
#            self._sock.shutdown(socket.SHUT_RDWR)
            self._sock.close()
#            log.info("socket shutdown and closed")
            log.info("socket closed")
        finally:
            self._sock = None

    def get_current_state(self, timeout=None):
        """
        """
        return self._rt._state

    def _send(self, s, info=None):
        """
        Sends a string. Returns the number of bytes written.

        @param s the string to send
        @param info string for logging purposes
        """
        c = self._sock.send(s)
        if log.isEnabledFor(logging.INFO):
            info_str = (' (%s)' % info) if info else ''
            log.info("_send:%s%s" % (repr(s), info_str))
        return c

    def send(self, string, info=None):
        """
        Sleeps for self._delay_before_send and then sends string + '\r\n'
        """
        self._rt._reset_internal_info()
        sleep(self._delay_before_send)
        s = string.rstrip() + '\r\n'
        self._send(s, info)

    def send_and_expect_prompt(self, string, timeout=None):
        """
        Sends a string and expects the prompt.
        @param string the string to send
        @param timeout Timeout for the wait, self.generic_timeout by default.

        @retval lines captured from the send to the prompt excluding the
                   prompt.
        @throws TimeoutException if cannot get to the expected state.
        """

        self.send(string)
        sleep(1)
        timeout = timeout or self._generic_timeout
        time_limit = time.time() + timeout
        while self._rt._state != State.PROMPT and time.time() <= time_limit:
            sleep(0.4)
            time_limit = self._rt._recv_time + timeout

        if self._rt._state != State.PROMPT:
            raise TimeoutException(
                    timeout, expected_state=State.PROMPT,
                    curr_state=self._rt._state, lines=self._rt._lines)

        lines = self._rt._lines[0: -1]
        return lines

    def _get_prompt(self, attempts=5):
        """
        Send linefeeds until getting prompt
        """
        # timeout for each attempt
        timeout = 1
        last_exc = None
        for a in xrange(attempts):
            log.info("_get_prompt: attempt=%d" % (a + 1))
            try:
                r = self.send_and_expect_prompt("", timeout)
                return r  # got it
            except TimeoutException, e:
                last_exc = e

        raise last_exc

    def get_latest_ensemble(self, timeout=None):
        """
        CE - Retrieve Most Recent Data Ensemble
        """
        self._get_prompt()
        timeout = timeout or self._generic_timeout

        # now prepare to receive response for latest ensemble
        self._rt._latest_pd0 = None
        self.send("CE")
        sleep(0.2)
        time_limit = time.time() + timeout
        while not self._rt._latest_pd0 and time.time() <= time_limit:
            sleep(0.4)
            time_limit = self._rt._recv_time + timeout

        if not self._rt._latest_pd0:
            raise TimeoutException(timeout, msg="waiting for ensemble")

        return self._rt._latest_pd0

    def get_metadata(self, sections=None, timeout=None):
        """
        Gets metadata
        """
        self._get_prompt()
        timeout = timeout or self._generic_timeout

        if not sections:
            sections = MetadataSections.list()

        result = {}
        for name, cmd in sections:
            lines = self.send_and_expect_prompt(cmd, timeout)
            result[name] = "\n".join(lines)

        return result

    def run_recorder_tests(self, timeout=None):
        """
        RB - Recorder Built-In Test
        """
        self._get_prompt()
        timeout = timeout or self._generic_timeout

        lines = self.send_and_expect_prompt("RB", timeout)

        return "\n".join(lines)

    def run_all_tests(self, timeout=None):
        """
        PT200 - All tests
        """
        self._get_prompt()
        timeout = timeout or self._generic_timeout

        lines = self.send_and_expect_prompt("PT200", timeout)

        return "\n".join(lines)

    def user_loop(self):
        """
        Sends lines received from stdin to the socket. EOF and "q" break the
        loop.
        """
        while True:
            cmd = sys.stdin.readline()
            if not cmd or cmd.strip() == "q":
                break
            else:
                self.send(cmd)


def main(host, port, outfile):
    """
    Demo program:
    """
    client = Client(host, port, outfile)
    try:
        client.connect()
        client.user_loop()

#        pd0 = client.get_latest_ensemble()
#        print "get_latest_ensemble=%s" % str(pd0)
    finally:
        print ":: bye"
        client.end()


if __name__ == '__main__':
    usage = """
    USAGE: client.py [options]
       --host address      # instrument address (localhost)
       --port port         # instrument port (required)
       --outfile filename  # file to save all received data
       --loglevel level    # used to eval mi_logger.setLevel(logging.%%s)
    """
    usage += """
    Example:
        client.py --host 10.180.80.178 --port 2101 --outfile vadcp_output.txt
    """

    host = 'localhost'
    port = None
    outfile = None

    arg = 1
    while arg < len(sys.argv):
        if sys.argv[arg] == "--host":
            arg += 1
            host = sys.argv[arg]
        elif sys.argv[arg] == "--port":
            arg += 1
            port = int(sys.argv[arg])
        elif sys.argv[arg] == "--outfile":
            arg += 1
            outfile = file(sys.argv[arg], 'w')
        elif sys.argv[arg] == "--loglevel":
            arg += 1
            loglevel = sys.argv[arg].upper()
            mi_logger = logging.getLogger('mi_logger')
            eval("mi_logger.setLevel(logging.%s)" % loglevel)
        else:
            print "error: unrecognized option %s" % sys.argv[arg]
            port = None
            break
        arg += 1

    if port is None:
        print usage
    else:
        main(host, port, outfile)
