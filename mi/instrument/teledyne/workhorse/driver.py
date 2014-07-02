"""
@package mi.instrument.teledyne.workhorse.driver
@file marine-integrations/mi/instrument/teledyne/workhorse/driver.py
@author Sung Ahn
@brief generic Driver for the Workhorse
Release notes:

Generic Driver for ADCPS-K, ADCPS-I, ADCPT-B and ADCPT-DE
"""

__author__ = 'Sung Ahn'
__license__ = 'Apache 2.0'

import socket
import re
from mi.core.exceptions import InstrumentProtocolException
from mi.instrument.teledyne.particles import ADCP_COMPASS_CALIBRATION_REGEX_MATCHER, \
    ADCP_SYSTEM_CONFIGURATION_REGEX_MATCHER, ADCP_ANCILLARY_SYSTEM_DATA_REGEX_MATCHER, ADCP_TRANSMIT_PATH_REGEX_MATCHER, \
    ADCP_PD0_PARSED_REGEX_MATCHER, ADCP_COMPASS_CALIBRATION_DataParticle, ADCP_PD0_PARSED_DataParticle, \
    ADCP_SYSTEM_CONFIGURATION_DataParticle, ADCP_ANCILLARY_SYSTEM_DATA_PARTICLE, ADCP_TRANSMIT_PATH_PARTICLE
from mi.instrument.teledyne.driver import TeledyneInstrumentDriver
from mi.instrument.teledyne.driver import TeledyneProtocol
from mi.instrument.teledyne.driver import TeledynePrompt
from mi.instrument.teledyne.driver import TeledyneParameter
from mi.instrument.teledyne.driver import TeledyneCapability
from mi.core.instrument.chunker import StringChunker

from mi.core.log import get_logger
from struct import unpack

log = get_logger()

# newline.
NEWLINE = '\r\n'


# ##############################################################################
# Driver
# ##############################################################################
class WorkhorseParameter(TeledyneParameter):
    """
    Device parameters
    """


class WorkhorseInstrumentDriver(TeledyneInstrumentDriver):
    """
    InstrumentDriver subclass for Workhorse driver.
    Subclasses SingleConnectionInstrumentDriver with connection state
    machine.
    """

    def __init__(self, evt_callback):
        """
        InstrumentDriver constructor.
        @param evt_callback Driver process event callback.
        """
        # Construct superclass.
        TeledyneInstrumentDriver.__init__(self, evt_callback)

    # #######################################################################
    # Protocol builder.
    # #######################################################################

    def _build_protocol(self):
        """
        Construct the driver protocol state machine.
        """
        self._protocol = WorkhorseProtocol(TeledynePrompt, NEWLINE, self._driver_event)


# ##########################################################################
# Protocol
# ##########################################################################


class WorkhorseProtocol(TeledyneProtocol):
    """
    Instrument protocol class
    Subclasses CommandResponseInstrumentProtocol
    """

    @staticmethod
    def sieve_function(raw_data):
        """
        Chunker sieve method to help the chunker identify chunks.
        @returns a list of chunks identified, if any.
        The chunks are all the same type.
        """

        sieve_matchers = [ADCP_SYSTEM_CONFIGURATION_REGEX_MATCHER,
                          ADCP_COMPASS_CALIBRATION_REGEX_MATCHER,
                          ADCP_ANCILLARY_SYSTEM_DATA_REGEX_MATCHER,
                          ADCP_TRANSMIT_PATH_REGEX_MATCHER,
                          ADCP_PD0_PARSED_REGEX_MATCHER]

        return_list = []

        for matcher in sieve_matchers:
            if matcher == ADCP_PD0_PARSED_REGEX_MATCHER:
                #
                # Have to cope with variable length binary records...
                # lets grab the length, then write a proper query to
                # snag it.
                #
                matcher2 = re.compile(r'\x7f\x7f(..)', re.DOTALL)
                for match in matcher2.finditer(raw_data):
                    l = unpack("H", match.group(1))
                    outer_pos = match.start()
                    ADCP_PD0_PARSED_TRUE_MATCHER = re.compile(r'\x7f\x7f(.{' + str(l[0]) + '})', re.DOTALL)
                    for _match in ADCP_PD0_PARSED_TRUE_MATCHER.finditer(raw_data, outer_pos):
                        inner_pos = _match.start()

                        if outer_pos == inner_pos:
                            return_list.append((_match.start(), _match.end()))
            else:
                for match in matcher.finditer(raw_data):
                    return_list.append((match.start(), match.end()))

        return return_list

    def __init__(self, prompts, newline, driver_event):
        """
        Protocol constructor.
        @param prompts A BaseEnum class containing instrument prompts.
        @param newline The newline.
        @param driver_event Driver process event callback.
        """

        # Construct protocol superclass.
        TeledyneProtocol.__init__(self, prompts, newline, driver_event)

        self._chunker = StringChunker(WorkhorseProtocol.sieve_function)

    def _build_command_dict(self):
        """
        Build command dictionary
        """
        self._cmd_dict.add(TeledyneCapability.START_AUTOSAMPLE,
                           timeout=300,
                           display_name="Start Autosample",
                           description="Place the instrument into autosample mode")
        self._cmd_dict.add(TeledyneCapability.STOP_AUTOSAMPLE,
                           display_name="Stop Autosample",
                           description="Exit autosample mode and return to command mode")
        self._cmd_dict.add(TeledyneCapability.CLOCK_SYNC,
                           display_name="Sync Clock")
        self._cmd_dict.add(TeledyneCapability.GET_CALIBRATION,
                           display_name="Get Calibration")
        self._cmd_dict.add(TeledyneCapability.RUN_TEST_200,
                            display_name="Run Test 200")
        self._cmd_dict.add(TeledyneCapability.ACQUIRE_STATUS,
                            display_name="Acquire Status")

    # #######################################################################
    # Private helpers.
    # #######################################################################
    def _got_chunk(self, chunk, timestamp):
        """
        The base class got_data has gotten a chunk from the chunker.
        Pass it to extract_sample with the appropriate particle
        objects and REGEXes.
        """

        if (self._extract_sample(ADCP_COMPASS_CALIBRATION_DataParticle,
                                 ADCP_COMPASS_CALIBRATION_REGEX_MATCHER,
                                 chunk,
                                 timestamp)):
            log.debug("_got_chunk - successful match for ADCP_COMPASS_CALIBRATION_DataParticle")

        elif (self._extract_sample(ADCP_PD0_PARSED_DataParticle,
                                   ADCP_PD0_PARSED_REGEX_MATCHER,
                                   chunk,
                                   timestamp)):
            log.debug("_got_chunk - successful match for ADCP_PD0_PARSED_DataParticle")

        elif (self._extract_sample(ADCP_SYSTEM_CONFIGURATION_DataParticle,
                                   ADCP_SYSTEM_CONFIGURATION_REGEX_MATCHER,
                                   chunk,
                                   timestamp)):
            log.debug("_got_chunk - successful match for ADCP_SYSTEM_CONFIGURATION_DataParticle")

        elif (self._extract_sample(ADCP_ANCILLARY_SYSTEM_DATA_PARTICLE,
                                   ADCP_ANCILLARY_SYSTEM_DATA_REGEX_MATCHER,
                                   chunk,
                                   timestamp)):
            log.trace("_got_chunk - successful match for ADCP_ANCILLARY_SYSTEM_DATA_PARTICLE")

        elif (self._extract_sample(ADCP_TRANSMIT_PATH_PARTICLE,
                                   ADCP_TRANSMIT_PATH_REGEX_MATCHER,
                                   chunk,
                                   timestamp)):
            log.trace("_got_chunk - successful match for ADCP_TRANSMIT_PATH_PARTICLE")

    def _get_params(self):
        return dir(WorkhorseParameter)

    def _getattr_key(self, attr):
        return getattr(WorkhorseParameter, attr)

    def _has_parameter(self, param):
        return WorkhorseParameter.has(param)

    # This is only temporary solution for now until port agent is fixed
    def _send_break_cmd(self, delay):
        """
        Send a BREAK to attempt to wake the device.
        """
        # NOTE!!!
        # Once the port agent can handle BREAK, please enable the following line
        # self._connection.send_break(delay)
        #Then remove below lines

        try:
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        except socket.error, msg:
            log.error("Failed to connect Break socket")
            raise InstrumentProtocolException("Init break socket exception")

        try:
            sock.connect(('10.180.80.178', 2102))
        except socket.error, msg:
            log.error("Failed to connect Break socket")
            raise InstrumentProtocolException("Init break socket exception")

        sock.send("break " + str(delay) + "\r\n")
        sock.close()
