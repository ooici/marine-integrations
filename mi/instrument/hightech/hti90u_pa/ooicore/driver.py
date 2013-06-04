"""
@package mi.instrument.hightech.hti90u_pa.ooicore.driver
@file marine-integrations/mi/instrument/hightech/hti90u_pa/ooicore/driver.py
@author Jeff Laughlin
@brief Driver for the ooicore
Release notes:

Low Frequency Hydrophone deployed as part of the OBS package. Interface will be through OBS.

Data flow:
hydrophone -> guralp logger -> seedlink server -> slink2orb -> antelope orb(s)
-> port agent antelope -> port agent client -> this module

See also:
https://confluence.oceanobservatories.org/display/instruments/HYDLF+-+A
https://confluence.oceanobservatories.org/display/instruments/HYDLF-A+Instrument+Operational+Specification
https://confluence.oceanobservatories.org/display/instruments/OBSBB%2CK
https://github.com/ooici/port-agent-antelope

"""

__author__ = 'Jeff Laughlin'
__license__ = 'Apache 2.0'

# TODO: Use a safer serialization format than Pickle. Even though we take what
# precautions we can, it's not impossible that somebody could attack this
# program via a malicious pickle. -JML
#
# DO NOT switch to plain pickle without using a safe-unpickler class.
# see http://docs.python.org/2/library/pickle.html#subclassing-unpicklers
from cPickle import Unpickler
from cStringIO import StringIO

import string

import ntplib

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
from mi.core.instrument.data_particle import DataParticle
from mi.core.instrument.data_particle import DataParticleKey
from mi.core.instrument.data_particle import CommonDataParticleType
from mi.core.instrument.chunker import StringChunker
from mi.core.instrument.driver_dict import DriverDictKey


# newline.
NEWLINE = '\r\n'

# default timeout.
TIMEOUT = 10

###
#    Driver Constant Definitions
###

class DataParticleType(BaseEnum):
    """
    Data particle types produced by this driver
    """
    RAW = CommonDataParticleType.RAW

    HYDLF_SAMPLE = 'hydlf_sample'
#    HYDLF_STATUS = 'hydlf_status'

class ProtocolState(BaseEnum):
    """
    Instrument protocol states
    """
    UNKNOWN = DriverProtocolState.UNKNOWN
    COMMAND = DriverProtocolState.COMMAND
    AUTOSAMPLE = DriverProtocolState.AUTOSAMPLE
# JML: Not sure but I don't think we can support these
    DIRECT_ACCESS = DriverProtocolState.DIRECT_ACCESS
#    TEST = DriverProtocolState.TEST
#    CALIBRATE = DriverProtocolState.CALIBRATE

class ProtocolEvent(BaseEnum):
    """
    Protocol events
    """
    ENTER = DriverEvent.ENTER
    EXIT = DriverEvent.EXIT
    GET = DriverEvent.GET
    SET = DriverEvent.SET
    DISCOVER = DriverEvent.DISCOVER
    START_DIRECT = DriverEvent.START_DIRECT
    STOP_DIRECT = DriverEvent.STOP_DIRECT
#    ACQUIRE_SAMPLE = DriverEvent.ACQUIRE_SAMPLE
    START_AUTOSAMPLE = DriverEvent.START_AUTOSAMPLE
    STOP_AUTOSAMPLE = DriverEvent.STOP_AUTOSAMPLE
    EXECUTE_DIRECT = DriverEvent.EXECUTE_DIRECT
#    CLOCK_SYNC = DriverEvent.CLOCK_SYNC
#    ACQUIRE_STATUS = DriverEvent.ACQUIRE_STATUS

class Capability(BaseEnum):
    """
    Protocol events that should be exposed to users (subset of above).
    """
#    ACQUIRE_SAMPLE = ProtocolEvent.ACQUIRE_SAMPLE
    START_AUTOSAMPLE = ProtocolEvent.START_AUTOSAMPLE
    STOP_AUTOSAMPLE = ProtocolEvent.STOP_AUTOSAMPLE
#    CLOCK_SYNC = ProtocolEvent.CLOCK_SYNC
#    ACQUIRE_STATUS  = ProtocolEvent.ACQUIRE_STATUS

class Parameter(DriverParameter):
    """
    Device specific parameters.
    """
    # JML: select/reject goes here?

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

class HYDLF_SampleDataParticleKey(BaseEnum):
    # From Packet object
#    CHANNELS = 'channels'
#    DB = 'db'
#    DFILE = 'dfile'
#    PF = 'pf'
#    SRCNAME = 'srcname'
#    STRING = 'string'
#    TIME = 'time'
#    TYPE = 'type'
#    VERSION = 'version'

    # From Channel object
    CALIB = 'calib'
    CALPER = 'calper'
    CHAN = 'chan'
#    CUSER1 = 'cuser1'
#    CUSER2 = 'cuser2'
#    DATA = 'data'
#    DUSER1 = 'duser1'
#    DUSER2 = 'duser2'
#    IUSER1 = 'iuser1'
#    IUSER2 = 'iuser2'
#    IUSER3 = 'iuser3'
    LOC = 'loc'
    NET = 'net'
    NSAMP = 'nsamp'
    SAMPRATE = 'samprate'
    SEGTYPE = 'segtype'
    STA = 'sta'
    TIME = 'time'
    SAMPLE = 'sample'
    SAMPLE_IDX = 'sample_idx'


class HYDLF_SampleDataParticle(DataParticle):
    _data_particle_type = DataParticleType.HYDLF_SAMPLE

    def _build_parsed_values(self):

        orb_packet, chan, index, sample = self.raw_data

        # Calculate sample timestamp
        unix_internal_timestamp = chan['time'] + (float(index) / float(chan['samprate']))
        self.set_internal_timestamp(unix_time=unix_internal_timestamp)

        result = []
        pk = HYDLF_SampleDataParticleKey
        vid = DataParticleKey.VALUE_ID
        v = DataParticleKey.VALUE

        # Copy this stuff verbatim from the Antelope PktChannel object
        result.append({vid: pk.CALIB, v: chan[pk.CALIB]})
        result.append({vid: pk.CALPER, v: chan[pk.CALPER]})
        result.append({vid: pk.CHAN, v: chan[pk.CHAN]})
        result.append({vid: pk.LOC, v: chan[pk.LOC]})
        result.append({vid: pk.NET, v: chan[pk.NET]})
        result.append({vid: pk.NSAMP, v: chan[pk.NSAMP]})
        result.append({vid: pk.SAMPRATE, v: chan[pk.SAMPRATE]})
        result.append({vid: pk.SEGTYPE, v: chan[pk.SEGTYPE]})
        result.append({vid: pk.STA, v: chan[pk.STA]})
        # this is the timestamp on samples[0]; INTERNAL_TIMESTAMP has the real
        # timestamp for this sample.
        result.append({vid: pk.TIME, v: chan[pk.TIME]})

        # Extracted from enumerate(PktChannel.data)
        result.append({vid: pk.SAMPLE_IDX, v: index})
        result.append({vid: pk.SAMPLE, v: sample})
        return result


# Status would go here I guess
# port_agent_antelope happily sends along parameter file (antelope's proprietary
# JSON-like serialization format) and string packets, if there are any. They
# could be on a different srcname or different orb or there may not be any at
# all. If there are status packets I'm guessing we would use a sieve function
# to split the two streams and then add the appropirate particle classes here.

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
    # Superclass overrides for resource query.
    ########################################################################

    def get_resource_params(self):
        """
        Return list of device parameters available.
        """
        return Parameter.list()

    ########################################################################
    # Protocol builder.
    ########################################################################

    def _build_protocol(self):
        """
        Construct the driver protocol state machine.
        """
        self._protocol = Protocol(Prompt, NEWLINE, self._driver_event)


###########################################################################
# Protocol
###########################################################################

class Protocol(CommandResponseInstrumentProtocol):
    """
    Instrument protocol class
    Subclasses CommandResponseInstrumentProtocol
    """
    def __init__(self, prompts, newline, driver_event):
        """
        Protocol constructor.
        @param prompts A BaseEnum class containing instrument prompts.
        @param newline The newline.
        @param driver_event Driver process event callback.
        """
        # Construct protocol superclass.
        CommandResponseInstrumentProtocol.__init__(self, prompts, newline, driver_event)

        # Build protocol state machine.
        self._protocol_fsm = InstrumentFSM(ProtocolState, ProtocolEvent,
                            ProtocolEvent.ENTER, ProtocolEvent.EXIT)

        # Add event handlers for protocol state machine.
        self._protocol_fsm.add_handler(ProtocolState.UNKNOWN, ProtocolEvent.ENTER, self._handler_unknown_enter)
        self._protocol_fsm.add_handler(ProtocolState.UNKNOWN, ProtocolEvent.EXIT, self._handler_unknown_exit)
        self._protocol_fsm.add_handler(ProtocolState.UNKNOWN, ProtocolEvent.DISCOVER, self._handler_unknown_discover)
#        self._protocol_fsm.add_handler(ProtocolState.UNKNOWN, ProtocolEvent.START_DIRECT, self._handler_command_start_direct)
        self._protocol_fsm.add_handler(ProtocolState.COMMAND, ProtocolEvent.START_AUTOSAMPLE, self._handler_command_start_autosample)
 
        self._protocol_fsm.add_handler(ProtocolState.COMMAND, ProtocolEvent.ENTER, self._handler_command_enter)
        self._protocol_fsm.add_handler(ProtocolState.COMMAND, ProtocolEvent.EXIT, self._handler_command_exit)
        self._protocol_fsm.add_handler(ProtocolState.COMMAND, ProtocolEvent.START_DIRECT, self._handler_command_start_direct)
        self._protocol_fsm.add_handler(ProtocolState.COMMAND, ProtocolEvent.GET, self._handler_command_get)
        self._protocol_fsm.add_handler(ProtocolState.COMMAND, ProtocolEvent.SET, self._handler_command_set)

        self._protocol_fsm.add_handler(ProtocolState.AUTOSAMPLE, ProtocolEvent.ENTER, self._handler_autosample_enter)
        self._protocol_fsm.add_handler(ProtocolState.AUTOSAMPLE, ProtocolEvent.EXIT, self._handler_autosample_exit)
        self._protocol_fsm.add_handler(ProtocolState.AUTOSAMPLE, ProtocolEvent.STOP_AUTOSAMPLE, self._handler_autosample_stop_autosample)

        self._protocol_fsm.add_handler(ProtocolState.DIRECT_ACCESS, ProtocolEvent.ENTER, self._handler_direct_access_enter)
        self._protocol_fsm.add_handler(ProtocolState.DIRECT_ACCESS, ProtocolEvent.EXIT, self._handler_direct_access_exit)
        self._protocol_fsm.add_handler(ProtocolState.DIRECT_ACCESS, ProtocolEvent.STOP_DIRECT, self._handler_direct_access_stop_direct)
        self._protocol_fsm.add_handler(ProtocolState.DIRECT_ACCESS, ProtocolEvent.EXECUTE_DIRECT, self._handler_direct_access_execute_direct)

        # Construct the parameter dictionary containing device parameters,
        # current parameter values, and set formatting functions.
        #
        # JML: Not in OPTAA?
        #
        #self._build_param_dict()

        # Add build handlers for device commands.

        # Add response handlers for device commands.

        # Add sample handlers.

        # State state machine in UNKNOWN state.
        self._protocol_fsm.start(ProtocolState.UNKNOWN)

        # commands sent sent to device to be filtered in responses for telnet DA
        #
        # JML: Not in OPTAA?
        #
        #self._sent_cmds = []

        #
        # JML: Billy sez "no chunker, no sieve"
        #
        #self._chunker = StringChunker(Protocol.sieve_function)

        # JML: What does this do?
        self._build_driver_dict()

    #
    # JML: Billy sez "no chunker, no sieve"
    #
#    @staticmethod
#    def sieve_function(raw_data):
#        """
#        The method that splits samples
#        """
#
#        return_list = []
#
#        return return_list

    def got_raw(self, *args, **kwargs):
        pass

    def got_data(self, port_agent_packet):
        """
        Called by the instrument connection when data is available.

        Also add data to the chunker and when received call got_chunk
        to publish results.
        """

        data_length = port_agent_packet.get_data_length()
        data = port_agent_packet.get_data()
        timestamp = port_agent_packet.get_timestamp()

        log.debug("Got Data: %s" % data)
        log.debug("Add Port Agent Timestamp: %s" % timestamp)

        unpickler = Unpickler(StringIO(data))
        # Disable class unpickling, for security; record should be all
        # built-in types. Note this only works with cPickle.
        unpickler.find_global = None

        # pkt is an antelope.Pkt.Packet object converted to a dict. Refer to
        # the documentation for the Antelope Python bindings for compelete
        # details.

        pkt = unpickler.load()

        for particle in self._particle_factory(pkt, timestamp):
            self._publish_particle(particle)

    def _particle_factory(self, orb_packet, port_timestamp):
        """Generate a sequence of particles from orb_packet

        @returns An iterator which yields a new particle object for each sample
        for each channel.
        """
        # TODO Might want to verify that the channel name matches a pattern,
        # e.g. the SEED standard for hydrophones.
        for chan in orb_packet['channels']:
            for index, sample in enumerate(chan['data']):
                # Yield a new particle
                # TODO don't hardcode particle class
                particle = HYDLF_SampleDataParticle(
                    # TODO: Fix this passing raw_data as tuple hack
                    raw_data = (orb_packet, chan, index, sample),
                    port_timestamp = port_timestamp,
                    preferred_timestamp = DataParticleKey.INTERNAL_TIMESTAMP
                )
                yield particle

    def _publish_particle(self, particle):
        """publish parsed particle"""
        parsed_sample = particle.generate()
        if self._driver_event:
            self._driver_event(DriverAsyncEvent.SAMPLE, parsed_sample)

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
        pass

    def _filter_capabilities(self, events):
        """
        Return a list of currently available capabilities.
        """
        return [x for x in events if Capability.has(x)]

    # JML: Copied from OPTAA; need this?
    def _build_driver_dict(self):
        """
        Populate the driver dictionary with options
        """
        self._driver_dict.add(DriverDictKey.VENDOR_SW_COMPATIBLE, True)


    ########################################################################
    # Unknown handlers.
    ########################################################################

    def _handler_unknown_enter(self, *args, **kwargs):
        """
        Enter unknown state.
        """
        # Tell driver superclass to send a state change event.
        # Superclass will query the state.
        self._driver_event(DriverAsyncEvent.STATE_CHANGE)

    def _handler_unknown_exit(self, *args, **kwargs):
        """
        Exit unknown state.
        """
        pass

    def _handler_unknown_discover(self, *args, **kwargs):
        """
        Discover current state
        @retval (next_state, result)
        """

        # JML: Copied from OPTAA
        # force to auto-sample, this instrument has no command mode
        next_state = ProtocolState.AUTOSAMPLE
        result = ResourceAgentState.STREAMING

        return (next_state, result)


    ########################################################################
    # Command handlers.
    ########################################################################

    def _handler_command_enter(self, *args, **kwargs):
        """
        Enter command state.
        @throws InstrumentTimeoutException if the device cannot be woken.
        @throws InstrumentProtocolException if the update commands and not recognized.
        """
        # Command device to update parameters and send a config change event.
        #self._update_params()

        # Tell driver superclass to send a state change event.
        # Superclass will query the state.
        self._driver_event(DriverAsyncEvent.STATE_CHANGE)

    def _handler_command_get(self, *args, **kwargs):
        """
        Get parameter
        """
        next_state = None
        result = None


        return (next_state, result)

    def _handler_command_set(self, *args, **kwargs):
        """
        Set parameter
        """
        next_state = None
        result = None

        return (next_state, result)

    def _handler_command_exit(self, *args, **kwargs):
        """
        Exit command state.
        """
        pass

    def _handler_command_start_direct(self):
        """
        Start direct access
        """
        next_state = ProtocolState.DIRECT_ACCESS
        next_agent_state = ResourceAgentState.DIRECT_ACCESS
        result = None
        log.debug("_handler_command_start_direct: entering DA mode")
        return (next_state, (next_agent_state, result))

    # JML: Copied from OPTAA
    def _handler_command_start_autosample(self, *args, **kwargs):
        """
        """
        result = None
        next_state = ProtocolState.AUTOSAMPLE
        next_agent_state = ResourceAgentState.STREAMING

        return (next_state, (next_agent_state, result))

    # JML: Copied wholesale from OPTAA
    ########################################################################
    # Autosample handlers.
    ########################################################################

    def _handler_autosample_enter(self, *args, **kwargs):
        """
        Enter command state.
        @throws InstrumentTimeoutException if the device cannot be woken.
        @throws InstrumentProtocolException if the update commands and not recognized.
        """
        # Command device to update parameters and send a config change event.
        #self._update_params()

        # Tell driver superclass to send a state change event.
        # Superclass will query the state.
        self._driver_event(DriverAsyncEvent.STATE_CHANGE)

    def _handler_autosample_exit(self, *args, **kwargs):
        """
        Exit command state.
        """
        pass

    def _handler_autosample_stop_autosample(self):
        """
        """
        result = None
        next_state = ProtocolState.COMMAND
        next_agent_state = ResourceAgentState.COMMAND

        return (next_state, (next_agent_state, result))



    ########################################################################
    # Direct access handlers.
    ########################################################################

    def _handler_direct_access_enter(self, *args, **kwargs):
        """
        Enter direct access state.
        """
        # Tell driver superclass to send a state change event.
        # Superclass will query the state.
        self._driver_event(DriverAsyncEvent.STATE_CHANGE)

        self._sent_cmds = []

    def _handler_direct_access_exit(self, *args, **kwargs):
        """
        Exit direct access state.
        """
        pass

    def _handler_direct_access_execute_direct(self, data):
        """
        """
        next_state = None
        result = None
        next_agent_state = None

        self._do_cmd_direct(data)

        # add sent command to list for 'echo' filtering in callback
        # JML: Not in OPTAA
        # self._sent_cmds.append(data)

        return (next_state, (next_agent_state, result))

    def _handler_direct_access_stop_direct(self):
        """
        @throw InstrumentProtocolException on invalid command
        """
        next_state = None
        result = None

        next_state = ProtocolState.COMMAND
        next_agent_state = ResourceAgentState.COMMAND

        return (next_state, (next_agent_state, result))
