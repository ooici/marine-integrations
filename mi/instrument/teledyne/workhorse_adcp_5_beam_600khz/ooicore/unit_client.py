#!/usr/bin/env python

"""
@package mi.instrument.teledyne.workhorse_adcp_5_beam_600khz.ooicore.unit_client
@file    mi/instrument/teledyne/workhorse_adcp_5_beam_600khz/ooicore/unit_client.py
@author Carlos Rueda

@brief Client module for a VADCP unit (4-beam or 5th beam).
"""

__author__ = 'Carlos Rueda'
__license__ = 'Apache 2.0'

import time
sleep = time.sleep

import sys

from mi.instrument.teledyne.workhorse_adcp_5_beam_600khz.ooicore.defs import \
    AdcpUnitConnConfig, EOLN, DEFAULT_GENERIC_TIMEOUT, State, \
    TimeoutException, MetadataSections
from mi.instrument.teledyne.workhorse_adcp_5_beam_600khz.ooicore.util import \
    connect_socket
from mi.instrument.teledyne.workhorse_adcp_5_beam_600khz.ooicore.receiver import \
    ReceiverBuilder

import logging
from mi.core.mi_logger import mi_logger as log


class UnitClient(object):
    """
    Client to a VADCP unit, either the 4-beam unit or the 5th beam unit.
    """

    def __init__(self, conn_config, outfile=None, prefix_state=True):
        """
        Creates a UnitClient instance.

        @param conn_config AdcpUnitConnConfig
        @param outfile
        @param prefix_state

        """
        self._conn_config = conn_config
        self._outfile = outfile
        self._prefix_state = prefix_state
        self._sock = None
        self._rt = None  # receiver thread

        """sleep time used just before sending data"""
        self._delay_before_send = 0.2

        """generic timeout for various operations"""
        self._generic_timeout = DEFAULT_GENERIC_TIMEOUT

        log.info("UnitClient created.")

    def _data_listener(self, pd0):
        pass

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
        @param callback ignored.
        """
        self.connect()

    def connect(self):
        """
        Establishes the connection and starts the receiving thread.

        @throws socket.error The socket.error that was raised during the
                         last attempt to connect the socket.
        """
        assert self._sock is None

        host = self._conn_config.host
        port = self._conn_config.port

        self._sock = connect_socket(host, port)

        log.info("creating _Receiver")
        self._rt = ReceiverBuilder.build_receiver(self._sock,
                                  outfile=self._outfile,
                                  data_listener=self._data_listener,
                                  prefix_state=self._prefix_state)
        log.info("starting _Receiver")
        self._rt.start()

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
        return self._rt.state

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
        self._rt.reset_internal_info()
        sleep(self._delay_before_send)
        s = string.rstrip() + EOLN
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
        while self._rt.state != State.PROMPT and time.time() <= \
                                                          time_limit:
            sleep(0.4)
            time_limit = self._rt.recv_time + timeout

        if self._rt.state != State.PROMPT:
            raise TimeoutException(
                    timeout, expected_state=State.PROMPT,
                    curr_state=self._rt.state, lines=self._rt.lines)

        lines = self._rt.lines[0: -1]
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

    def get_latest_sample(self, timeout=None):
        """
        CE - Retrieve Most Recent Data Ensemble
        """
        self._get_prompt()
        timeout = timeout or self._generic_timeout
        # now prepare to receive response for latest ensemble
        self._rt.set_latest_pd0(None)
        self.send("CE")
        sleep(0.2)
        time_limit = time.time() + timeout
        while not self._rt.latest_pd0 and time.time() <= time_limit:
            sleep(0.4)
            time_limit = self._rt.recv_time + timeout

        if not self._rt.latest_pd0:
            raise TimeoutException(timeout, msg="waiting for ensemble")

        return self._rt.latest_pd0

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

    def start_autosample(self, timeout=None):
        """
        PD0 - Binary output data format
        CS - Start pinging
        """

        timeout = timeout or self._generic_timeout

        # TODO eventually keep current state with enough reliability to
        # check whether we are already in streaming mode ...
#        if self._rt.state == State.COLLECTING_DATA:
#            return  # already streaming
        # ... to just return if already streaming.

        # However, for the moment, force a break:
        self.send_break(timeout=timeout)
        # and continue with regular steps to start autosampling:

        self._get_prompt()

        # send PD0 - Binary output data format
        self.send_and_expect_prompt("PD0", timeout)

        # send CS - Start pinging
        self.send("CS")
        sleep(1)
        time_limit = time.time() + timeout
        while self._rt.state != State.COLLECTING_DATA and time.time() <= \
                                                          time_limit:
            sleep(0.4)
            time_limit = self._rt.recv_time + timeout

        if self._rt.state != State.COLLECTING_DATA:
            raise TimeoutException(
                    timeout, expected_state=State.COLLECTING_DATA,
                    curr_state=self._rt.state, lines=self._rt.lines)

    def stop_autosample(self, timeout=None):
        """
        Sends a "break" command via the OOI Digi connection
        """

        if self._rt.state != State.COLLECTING_DATA:
            return  # not streaming

        timeout = timeout or self._generic_timeout

        self.send_break(timeout=timeout)
        self._get_prompt()

    ###############################################
    # OOI Digi
    ###############################################

    def _connect_ooi_digi(self):
        """
        Establishes the connection to the OOI digi
        """

        host = self._conn_config.ooi_digi_host
        port = self._conn_config.ooi_digi_port

        sock = connect_socket(host, port)

        if 'localhost' == host:
            outfilename = 'vadcp_ooi_digi_output.txt'
        else:
            outfilename = 'vadcp_output_%s_%s.txt' % (host, port)
        outfile = open(outfilename, 'a')
        log.info("creating OOI Digi _Receiver")
        rt = ReceiverBuilder.build_receiver(sock, outfile=outfile)
        log.info("starting OOI Digi _Receiver")
        rt.start()

        return (sock, rt, host, port)

    def send_break(self, duration=1000, attempts=3, timeout=None):
        """
        Issues a "break <duration>" command to the OOI digi.

        @param duration Duration for the break command (by default 1000)
        @param attempts Max number of attempts, 3 by default.
        @param timeout

        @retval True iff the command has had effect.
        """

        timeout = timeout or self._generic_timeout

        # TODO the expectation below should be getting the corresponding
        # response on the regular raw port.

        sock, rt, host, port = self._connect_ooi_digi()
        ok = False
        try:
            for a in xrange(attempts):
                time.sleep(1)
                rt.reset_internal_info()
                log.info("Sending break (attempt=%d)" % (a + 1))
                sock.send("break %s%s" % (duration, EOLN))
                time.sleep(2)
                response = "\n".join(rt.lines)
                ok = response.find("Sending Serial Break") >= 0
                if ok:
                    break
        finally:
            log.info("Got expected response from OOI Digi: %s" % ok)

            log.info("ending OOI Digi receiver")
            rt.end()

            time.sleep(2)

            log.info("closing socket to OOI Digi on: %s, %s" % (host, port))
            sock.close()
            log.info("socket to OOI Digi closed")

        return ok


def main(conn_config, outfile):
    """
    Ad hoc program for experimentation.
    """
    import re

    def user_loop(client):
        """
        Sends lines received from stdin to the socket. EOF and "q" break the
        loop.
        """
        polled = False
        while True:
            cmd = sys.stdin.readline()
            if not cmd:
                break
            cmd = cmd.strip()
            if cmd == "q":
                break
            elif re.match(r"CP\s*(0|1)", cmd, re.IGNORECASE):
                cmd = cmd.upper()
                polled = cmd.endswith('1')
                client.send(cmd)
                log.info("polled set to: %s" % polled)
            elif cmd == "break":
                client.send_break()
            elif polled and cmd.upper() in ['!', '+', '-', 'D', 'E', 'T']:
                # See Table 10: Polled Mode Commands in "Workhorse Commands
                # an Output Data Format" doc.
                # I've noted (on both units) that only '!' and '+' are
                # actually handled, that is, with no echo and apparently
                # triggering the documented behavior (certainly for the '!'
                # break reset one); the others are echoed and probably not
                # causing the corresponding behavior.
                cmd = cmd.upper()
                client._send(cmd, info="sending polled mode cmd='%s'" % cmd)
            else:
                client.send(cmd)


    client = UnitClient(conn_config, outfile)
    try:
        client.connect()
        user_loop(client)

#        sample = client.get_latest_sample()
#        print "get_latest_sample=%s" % str(sample)
    finally:
        print ":: bye"
        client.end()


if __name__ == '__main__':
    usage = """
    USAGE: unit_client.py [options]
       --unit [4 | 5]      # unit: 4-beam or 5th beam
       --outfile filename  # file to save all received data ('-' == stdout)
    """
    usage += """
    Example:
        unit_client.py --unit four_beam --outfile -
        Connects to the 4-beam unit writing all received responses or data to stdout
    """

    unit = None
    outfile = None

    arg = 1
    while arg < len(sys.argv):
        if sys.argv[arg] == "--unit":
            arg += 1
            unit = sys.argv[arg]
        elif sys.argv[arg] == "--outfile":
            arg += 1
            outfilename = sys.argv[arg]
            outfile = sys.stdout if outfilename == "-" else file(outfilename, 'w')
        else:
            print "error: unrecognized option %s" % sys.argv[arg]
            port = None
            break
        arg += 1

    host = None
    port = 2101
    ooi_digi_port = 2102
    if unit == "4":
        host = '10.180.80.178'
    elif unit == "5":
        host = '10.180.80.177'

    if host:
        conn_config = AdcpUnitConnConfig(host, port, host, ooi_digi_port)
        main(conn_config, outfile)
    else:
        print usage
