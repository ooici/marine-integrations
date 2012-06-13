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
sleep = time.sleep

import sys

from mi.instrument.teledyne.workhorse_adcp_5_beam_600khz.ooicore.unit_client import \
    UnitClient
from mi.instrument.teledyne.workhorse_adcp_5_beam_600khz.ooicore.defs import \
    AdcpUnitConnConfig, VadcpSample, DEFAULT_GENERIC_TIMEOUT

from mi.core.mi_logger import mi_logger as log


class VadcpClient(object):
    """
    Client to the VADCP instrument, which comprises two units: 
    a 4-beam unit and a 5th beam unit.
    """

    def __init__(self, conn_config, b4_outfile=None, b5_outfile=None):
        """
        Creates a VadcpClient instance.

        @param conn_config connection configurations for the two units
        @param b4_outfile
        @param b5_outfile

        """

        self._u4 = UnitClient(conn_config['four_beam'], outfile=b4_outfile)
        self._u5 = UnitClient(conn_config['fifth_beam'], outfile=b5_outfile)

        # sleep time used just before sending data
        self._delay_before_send = 0.2

        # generic timeout for various operations
        self._generic_timeout = DEFAULT_GENERIC_TIMEOUT

        log.info("VADCP client object created.")

    def _data_listener(self, pd0):
        pass

    def set_data_listener(self, data_listener):
        """
        """
        self._data_listener = data_listener

    def set_generic_timeout(self, timeout):
        """Sets generic timeout for various operations.
           By default DEFAULT_GENERIC_TIMEOUT."""
        self._u5.set_generic_timeout(timeout)
        self._u4.set_generic_timeout(timeout)

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
        Establishes the connection to the two units.

        @throws socket.error The socket.error that was raised during the
                         last attempt to connect the socket.
        """
        
        self._u4.connect()
        self._u5.connect()

    def stop_comms(self):
        """
        Just calls self.end()
        """
        self.end()

    def end(self):
        """
        Ends the client.
        """
        try:
            self._u4.end()
        finally:
            self._u5.end()

    def get_current_state(self, timeout=None):
        """
        """
        # TODO could the master unit simply determine the state of the client?
        return self._u4.get_current_state(timeout=timeout)


    def get_latest_sample(self, timeout=None):
        """
        CE - Retrieve Most Recent Data Ensemble
        """
        # TODO determine format for aggregation of the data
        
        u4_res = self._u4.get_latest_sample(timeout=timeout)
        u5_res = self._u5.get_latest_sample(timeout=timeout)

        sample = VadcpSample(u4_res, u5_res)

        return sample

    def get_metadata(self, sections=None, timeout=None):
        """
        Gets metadata
        """
        # TODO determine format for metadata
        
        u4_res = self._u4.get_metadata(timeout=timeout)
        u5_res = self._u5.get_metadata(timeout=timeout)

        res = dict(four_beam=u4_res, fifth_beam=u5_res)
        return res

    def run_recorder_tests(self, timeout=None):
        """
        RB - Recorder Built-In Test
        """
        
        # TODO determine format to report the tests
        
        u4_res = self._u4.run_recorder_tests(timeout=timeout)
        u5_res = self._u5.run_recorder_tests(timeout=timeout)

        res = dict(four_beam=u4_res, fifth_beam=u5_res)
        return res

    def run_all_tests(self, timeout=None):
        """
        PT200 - All tests
        """
        # TODO determine format to report the tests
        
        u4_res = self._u4.run_all_tests(timeout=timeout)
        u5_res = self._u5.run_all_tests(timeout=timeout)

        res = dict(four_beam=u4_res, fifth_beam=u5_res)
        return res

    def send_break(self, timeout=None):
        """
        Sends the two units a "break" command via the corresp OOI Digi
        connections. First to the 5th beam, then to the 4-beam.
        """

        self._u5.send_break(timeout=timeout)
        self._u5._get_prompt()
        sleep(1)
        self._u4.send_break(timeout=timeout)
        self._u4._get_prompt()

    def start_autosample(self, timeout=None):
        """
        PD0 - Binary output data format
        CS - Start pinging
        """

        timeout = timeout or self._generic_timeout

        # TODO eventually keep current state with enough reliability to
        # check whether we are already in streaming mode ...

        # However, for the moment, force a break:

        self.send_break(timeout=timeout)

        # then start autosampling, again first on the 5th beam, then 4-beam

        self._u5.send_and_expect_prompt("PD0", timeout)
        self._u5.send("CS")

        sleep(1)

        self._u4.send_and_expect_prompt("PD0", timeout)
        self._u4.send("CS")

    def stop_autosample(self, timeout=None):
        """
        Same as self.send_break(timeout=timeout)
        """

        self.send_break(timeout=timeout)


def main(conn_config, b4_outfile, b5_outfile):
    """
    program for experimentation.
    """

    def user_loop(client):
        """
        Sends lines received from stdin to the socket. EOF and "q" break the
        loop.
        """
        while True:
            cmd = sys.stdin.readline()
            if not cmd or cmd.strip() == "q":
                break
            elif cmd.strip() == "cs":
                client.start_autosample()
            elif cmd.strip() == "break":
                client.send_break()
            else:
                client._u5.send(cmd)
                client._u4.send(cmd)


    client = VadcpClient(conn_config, b4_outfile, b5_outfile)
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
    USAGE: client.py --b4_outfile file --b5_outfile file
        Connects to the two units writing all received responses or data to
        stdout
    """

    b4_outfile = None
    b5_outfile = None

    arg = 1
    while arg < len(sys.argv):
        if sys.argv[arg] == "--b4_outfile":
            arg += 1
            outfilename = sys.argv[arg]
            b4_outfile = sys.stdout if outfilename == "-" else file(outfilename, 'w')
        elif sys.argv[arg] == "--b5_outfile":
            arg += 1
            outfilename = sys.argv[arg]
            b5_outfile = sys.stdout if outfilename == "-" else file( outfilename, 'w')
        else:
            print "error: unrecognized option %s" % sys.argv[arg]
            port = None
            break
        arg += 1

    conn_config = {
        'four_beam': AdcpUnitConnConfig('10.180.80.178', 2101,
                                        '10.180.80.178', 2102),
        'fifth_beam': AdcpUnitConnConfig('10.180.80.177', 2101,
                                        '10.180.80.177', 2102),
        }

    main(conn_config, b4_outfile, b5_outfile)
