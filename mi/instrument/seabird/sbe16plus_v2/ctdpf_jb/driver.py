"""
@package mi.instrument.seabird.sbe16plus_v2.ctdpf_jb.driver
@file marine-integrations/mi/instrument/seabird/sbe16plus_v2/ctdpf_jb/driver.py
@author Tapana Gupta
@brief Driver for the CTDPF-JB instrument
Release notes:

SBE Driver
"""

__author__ = 'Tapana Gupta'
__license__ = 'Apache 2.0'

from mi.core.log import get_logger ; log = get_logger()

from mi.core.common import BaseEnum
from mi.core.instrument.instrument_protocol import CommandResponseInstrumentProtocol
from mi.core.instrument.instrument_fsm import InstrumentFSM
from mi.core.instrument.instrument_driver import SingleConnectionInstrumentDriver
from mi.core.instrument.instrument_driver import DriverEvent
from mi.core.instrument.instrument_driver import DriverAsyncEvent
from mi.core.instrument.instrument_driver import DriverProtocolState
from mi.core.instrument.instrument_driver import DriverParameter
from mi.core.instrument.instrument_driver import ResourceAgentState
from mi.core.instrument.data_particle import CommonDataParticleType
from mi.core.instrument.chunker import StringChunker

import re

from mi.instrument.seabird.sbe16plus_v2.driver import ProtocolState
from mi.instrument.seabird.sbe16plus_v2.driver import ProtocolEvent
from mi.instrument.seabird.sbe16plus_v2.driver import Capability
from mi.instrument.seabird.sbe16plus_v2.driver import SBE16Protocol

# newline.
NEWLINE = '\r\n'

# default timeout.
# TIMEOUT = 10


class ScheduledJob(BaseEnum):
    ACQUIRE_STATUS = 'acquire_status'
    CONFIGURATION_DATA = "configuration_data"
    CLOCK_SYNC = 'clock_sync'


class Command(BaseEnum):

        GET_CD = 'GetCD'
        GET_SD = 'GetSD'
        GET_CC = 'GetCC'
        GET_EC = 'GetEC'
        RESET_EC = 'ResetEC'
        GET_HD = 'GetHD'
        START_NOW = 'StartNow'
        STOP = 'Stop'
        TS = 'ts'

        #TODO: not specified in IOS
        SET = 'set'


class DataParticleType(BaseEnum):
    """
    Data particle types produced by this driver
    """
    RAW = CommonDataParticleType.RAW


class Parameter(DriverParameter):
    """
    Device specific parameters.
    """

class Prompt(BaseEnum):
    """
    Device i/o prompts..
    """

class InstrumentCommand(BaseEnum):
    """
    Instrument command strings
    """


###############################################################################
# Data Particles
###############################################################################


###############################################################################
# Driver
###############################################################################

class InstrumentDriver(SingleConnectionInstrumentDriver):
    """
    InstrumentDriver subclass
    Subclasses SingleConnectionInstrumentDriver with connection state
    machine.
    """
    def __init__(self, evt_callback):
        """
        Driver constructor.
        @param evt_callback Driver process event callback.
        """
        #Construct superclass.
        SingleConnectionInstrumentDriver.__init__(self, evt_callback)

    ########################################################################
    # Protocol builder.
    ########################################################################

    def _build_protocol(self):
        """
        Construct the driver protocol state machine.
        """
        self._protocol = SBE19Protocol(Prompt, NEWLINE, self._driver_event)


###########################################################################
# Protocol
###########################################################################

class SBE19Protocol(SBE16Protocol):
    """
    Instrument protocol class for SBE19 Driver
    Subclasses SBE16Protocol
    """
    def __init__(self, prompts, newline, driver_event):
        """
        SBE19Protocol constructor.
        @param prompts A BaseEnum class containing instrument prompts.
        @param newline The SBE19 newline.
        @param driver_event Driver process event callback.
        """
        # Construct protocol superclass.
        CommandResponseInstrumentProtocol.__init__(self, prompts, newline, driver_event)

        # Build SBE16 protocol state machine.
        self._protocol_fsm = InstrumentFSM(ProtocolState, ProtocolEvent,
                            ProtocolEvent.ENTER, ProtocolEvent.EXIT)

        # Add event handlers for protocol state machine.
        self._protocol_fsm.add_handler(ProtocolState.UNKNOWN, ProtocolEvent.ENTER, self._handler_unknown_enter)
        self._protocol_fsm.add_handler(ProtocolState.UNKNOWN, ProtocolEvent.EXIT, self._handler_unknown_exit)
        self._protocol_fsm.add_handler(ProtocolState.UNKNOWN, ProtocolEvent.DISCOVER, self._handler_unknown_discover)
        self._protocol_fsm.add_handler(ProtocolState.COMMAND, ProtocolEvent.ENTER, self._handler_command_enter)
        self._protocol_fsm.add_handler(ProtocolState.COMMAND, ProtocolEvent.EXIT, self._handler_command_exit)
        self._protocol_fsm.add_handler(ProtocolState.COMMAND, ProtocolEvent.QUIT_SESSION, self._handler_command_autosample_quit_session)
        self._protocol_fsm.add_handler(ProtocolState.COMMAND, ProtocolEvent.ACQUIRE_SAMPLE, self._handler_command_acquire_sample)
        self._protocol_fsm.add_handler(ProtocolState.COMMAND, ProtocolEvent.GET_CONFIGURATION, self._handler_command_get_configuration)
        self._protocol_fsm.add_handler(ProtocolState.COMMAND, ProtocolEvent.START_AUTOSAMPLE, self._handler_command_start_autosample)
        self._protocol_fsm.add_handler(ProtocolState.COMMAND, ProtocolEvent.RESET_EC, self._handler_command_reset_ec)
        self._protocol_fsm.add_handler(ProtocolState.COMMAND, ProtocolEvent.GET, self._handler_command_get)
        self._protocol_fsm.add_handler(ProtocolState.COMMAND, ProtocolEvent.SET, self._handler_command_set)
        self._protocol_fsm.add_handler(ProtocolState.COMMAND, ProtocolEvent.TEST, self._handler_command_test)
        self._protocol_fsm.add_handler(ProtocolState.COMMAND, ProtocolEvent.START_DIRECT, self._handler_command_start_direct)
        self._protocol_fsm.add_handler(ProtocolState.COMMAND, ProtocolEvent.CLOCK_SYNC, self._handler_command_clock_sync_clock)
        self._protocol_fsm.add_handler(ProtocolState.COMMAND, ProtocolEvent.SCHEDULED_CLOCK_SYNC, self._handler_command_clock_sync_clock)
        self._protocol_fsm.add_handler(ProtocolState.COMMAND, ProtocolEvent.ACQUIRE_STATUS, self._handler_command_acquire_status)
        self._protocol_fsm.add_handler(ProtocolState.AUTOSAMPLE, ProtocolEvent.QUIT_SESSION, self._handler_command_autosample_quit_session)
        self._protocol_fsm.add_handler(ProtocolState.AUTOSAMPLE, ProtocolEvent.ENTER, self._handler_autosample_enter)
        self._protocol_fsm.add_handler(ProtocolState.AUTOSAMPLE, ProtocolEvent.EXIT, self._handler_autosample_exit)
        self._protocol_fsm.add_handler(ProtocolState.AUTOSAMPLE, ProtocolEvent.GET, self._handler_command_get)
        self._protocol_fsm.add_handler(ProtocolState.AUTOSAMPLE, ProtocolEvent.STOP_AUTOSAMPLE, self._handler_autosample_stop_autosample)
        self._protocol_fsm.add_handler(ProtocolState.AUTOSAMPLE, ProtocolEvent.ACQUIRE_STATUS, self._handler_autosample_acquire_status)
        self._protocol_fsm.add_handler(ProtocolState.AUTOSAMPLE, ProtocolEvent.GET_CONFIGURATION, self._handler_autosample_get_configuration)
        self._protocol_fsm.add_handler(ProtocolState.AUTOSAMPLE, ProtocolEvent.SCHEDULED_CLOCK_SYNC, self._handler_autosample_clock_sync)
        self._protocol_fsm.add_handler(ProtocolState.TEST, ProtocolEvent.ENTER, self._handler_test_enter)
        self._protocol_fsm.add_handler(ProtocolState.TEST, ProtocolEvent.EXIT, self._handler_test_exit)
        self._protocol_fsm.add_handler(ProtocolState.TEST, ProtocolEvent.RUN_TEST, self._handler_test_run_tests)
        self._protocol_fsm.add_handler(ProtocolState.TEST, ProtocolEvent.GET, self._handler_command_get)
        self._protocol_fsm.add_handler(ProtocolState.DIRECT_ACCESS, ProtocolEvent.ENTER, self._handler_direct_access_enter)
        self._protocol_fsm.add_handler(ProtocolState.DIRECT_ACCESS, ProtocolEvent.EXIT, self._handler_direct_access_exit)
        self._protocol_fsm.add_handler(ProtocolState.DIRECT_ACCESS, ProtocolEvent.EXECUTE_DIRECT, self._handler_direct_access_execute_direct)
        self._protocol_fsm.add_handler(ProtocolState.DIRECT_ACCESS, ProtocolEvent.STOP_DIRECT, self._handler_direct_access_stop_direct)


        # Construct the parameter dictionary containing device parameters,
        # current parameter values, and set formatting functions.
        self._build_driver_dict()
        self._build_command_dict()
        self._build_param_dict()

        # Add build handlers for device commands.

        self._add_build_handler(Command.GET_CD, self._build_simple_command)
        self._add_build_handler(Command.GET_SD, self._build_simple_command)
        self._add_build_handler(Command.GET_CC, self._build_simple_command)
        self._add_build_handler(Command.GET_EC, self._build_simple_command)
        self._add_build_handler(Command.RESET_EC, self._build_simple_command)
        self._add_build_handler(Command.GET_HD, self._build_simple_command)

        self._add_build_handler(Command.STARTNOW, self._build_simple_command)
        self._add_build_handler(Command.STOP, self._build_simple_command)

        self._add_build_handler(Command.TS, self._build_simple_command)

        self._add_build_handler(Command.SET, self._build_set_command)


        # Add response handlers for device commands.
        self._add_response_handler(Command.SET, self._parse_set_response)

        #TODO: what other commands need response handlers?

        # State state machine in UNKNOWN state.
        self._protocol_fsm.start(ProtocolState.UNKNOWN)

        self._chunker = StringChunker(self.sieve_function)

        #TODO: what other commands are schedulable?
        self._add_scheduler_event(ScheduledJob.ACQUIRE_STATUS, ProtocolEvent.ACQUIRE_STATUS)
        self._add_scheduler_event(ScheduledJob.CONFIGURATION_DATA, ProtocolEvent.GET_CONFIGURATION)
        self._add_scheduler_event(ScheduledJob.CLOCK_SYNC, ProtocolEvent.SCHEDULED_CLOCK_SYNC)


    @staticmethod
    def sieve_function(raw_data):
        """
        The method that splits samples
        """

        return_list = []

        return return_list

    def _build_param_dict(self):
        """
        Populate the parameter dictionary with parameters.
        For each parameter key, add match stirng, match lambda function,
        and value formatting function for set commands.
        """
        # Add parameter handlers to parameter dict.

    def _got_chunk(self, chunk):
        """
        The base class got_data has gotten a chunk from the chunker.  Pass it to extract_sample
        with the appropriate particle objects and REGEXes.
        """

    def _filter_capabilities(self, events):
        """
        Return a list of currently available capabilities.
        """
        return [x for x in events if Capability.has(x)]

    ########################################################################
    # Unknown handlers.
    ########################################################################

    # All handlers inherited from SBE16 Protocol.

    ########################################################################
    # Command handlers.
    ########################################################################


    ########################################################################
    # Direct access handlers.
    ########################################################################


