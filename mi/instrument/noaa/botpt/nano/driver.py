"""
@package mi.instrument.noaa.nano.ooicore.driver
@file marine-integrations/mi/instrument/noaa/nano/ooicore/driver.py
@author David Everett
@brief Driver for the ooicore
Release notes:

Driver for NANO TILT on the RSN-BOTPT instrument (v.6)

"""

__author__ = 'David Everett'
__license__ = 'Apache 2.0'

import re
import time

import ntplib

from mi.core.log import get_logger


log = get_logger()

from mi.core.common import BaseEnum
from mi.core.instrument.instrument_fsm import InstrumentFSM
from mi.core.instrument.instrument_driver import SingleConnectionInstrumentDriver
from mi.core.instrument.instrument_driver import DriverEvent
from mi.core.instrument.instrument_driver import DriverProtocolState
from mi.core.instrument.instrument_driver import DriverParameter
from mi.core.instrument.instrument_driver import ResourceAgentState
from mi.core.instrument.protocol_cmd_dict import ProtocolCommandDict
from mi.core.instrument.data_particle import DataParticle
from mi.core.instrument.data_particle import DataParticleKey
from mi.core.instrument.chunker import StringChunker
from mi.instrument.noaa.botpt.driver import BotptProtocol
from mi.instrument.noaa.botpt.driver import NEWLINE

from mi.core.exceptions import InstrumentTimeoutException
from mi.core.exceptions import SampleException

###
#    Driver Constant Definitions
###

# newline.
NANO_STRING = 'NANO,'
NANO_COMMAND_STRING = '*0100'
NANO_DATA_ON = 'E4'  # turns on continuous data
NANO_DATA_OFF = 'E3'  # turns off continuous data
NANO_DUMP_SETTINGS = '1F'  # outputs current settings
NANO_SET_TIME = 'TS'  # Tells the CPU to set the NANO time


class ProtocolState(BaseEnum):
    """
    Instrument protocol states
    """
    UNKNOWN = DriverProtocolState.UNKNOWN
    COMMAND = DriverProtocolState.COMMAND
    AUTOSAMPLE = DriverProtocolState.AUTOSAMPLE


class ExportedInstrumentCommand(BaseEnum):
    SET_TIME = "EXPORTED_INSTRUMENT_SET_TIME"


class ProtocolEvent(BaseEnum):
    """
    Protocol events
    """
    ENTER = DriverEvent.ENTER
    EXIT = DriverEvent.EXIT
    GET = DriverEvent.GET
    SET = DriverEvent.SET
    START_AUTOSAMPLE = DriverEvent.START_AUTOSAMPLE
    STOP_AUTOSAMPLE = DriverEvent.STOP_AUTOSAMPLE
    DISCOVER = DriverEvent.DISCOVER
    ACQUIRE_STATUS = DriverEvent.ACQUIRE_STATUS
    SET_TIME = ExportedInstrumentCommand.SET_TIME


class Capability(BaseEnum):
    """
    Protocol events that should be exposed to users (subset of above).
    """
    GET = ProtocolEvent.GET
    SET = ProtocolEvent.SET
    START_AUTOSAMPLE = ProtocolEvent.START_AUTOSAMPLE
    STOP_AUTOSAMPLE = ProtocolEvent.STOP_AUTOSAMPLE
    ACQUIRE_STATUS = ProtocolEvent.ACQUIRE_STATUS
    SET_TIME = ProtocolEvent.SET_TIME


class Parameter(DriverParameter):
    """
    Device specific parameters.
    """


class Prompt(BaseEnum):
    """
    Device i/o prompts..
    """


###############################################################################
# Command Response (not a particle but uses regex and chunker to parse command
# responses rather than the normal get_response() method)
###############################################################################

class InstrumentCommand(BaseEnum):
    """
    Instrument command strings
    """
    DATA_ON = NANO_STRING + NANO_COMMAND_STRING + NANO_DATA_ON  # turns on continuous data
    DATA_OFF = NANO_STRING + NANO_COMMAND_STRING + NANO_DATA_OFF  # turns off continuous data
    DUMP_SETTINGS = NANO_STRING + NANO_COMMAND_STRING + NANO_DUMP_SETTINGS  # outputs current settings
    SET_TIME = NANO_STRING + NANO_SET_TIME  # outputs current settings


###############################################################################
# Data Particles
###############################################################################

class DataParticleType(BaseEnum):
    NANO_PARSED = 'botpt_nano_sample'
    NANO_STATUS = 'botpt_nano_status'


class NANODataParticleKey(BaseEnum):
    TIME = "nano_time"
    PPS_SYNC = "nano_pps_sync"
    PRESSURE = "pressure"
    TEMP = "temperature"


class NANODataParticle(DataParticle):
    """
    Routines for parsing raw data into a data particle structure. Override
    the building of values, and the rest should come along for free.

    Sample:
       NANO,V,2013/08/22 22:48:36.013,13.888533,26.147947328
    Format:
       IIII,YYYY/MM/DD hh:mm:ss,x.xxxx,y.yyyy,tt.tt,sn

        ID = IIII = NANO
        Year = YYYY
        Month = MM
        Day = DD
        Hour = hh
        Minutes = mm
        Seconds = ss
        NOTE: The above time expression is all grouped into one string.
        Pressure = x.xxxx (float PSI)
        Temp = tt.tt (float degrees C)
    """
    _data_particle_type = DataParticleType.NANO_PARSED

    @staticmethod
    def regex():
        """
        Regular expression to match a sample pattern
        @return: regex string
        """
        pattern = r'NANO,'  # pattern starts with NANO '
        pattern += r'(V|P),'  # 1 time-sync (PPS or lost)
        pattern += r'(.*),'  # 2 time
        pattern += r'(-*[.0-9]+),'  # 3 pressure (PSIA)
        pattern += r'(-*[.0-9]+)'  # 4 temperature (degrees)
        pattern += r'.*'
        pattern += NEWLINE
        return pattern

    @staticmethod
    def regex_compiled():
        """
        get the compiled regex pattern
        @return: compiled re
        """
        return re.compile(NANODataParticle.regex())

    def _build_parsed_values(self):
        """
        Take something in the autosample/TS format and split it into
        C, T, and D values (with appropriate tags)
        
        @throws SampleException If there is a problem with sample creation
        """
        match = NANODataParticle.regex_compiled().match(self.raw_data)

        if not match:
            raise SampleException("No regex match of parsed sample data: [%s]" %
                                  self.raw_data)

        try:
            pps_sync = match.group(1) == 'P'
            nano_time = match.group(2)
            timestamp = time.strptime(nano_time, "%Y/%m/%d %H:%M:%S.%f")
            self.set_internal_timestamp(unix_time=time.mktime(timestamp))
            ntp_timestamp = ntplib.system_to_ntp_time(time.mktime(timestamp))
            pressure = float(match.group(3))
            temperature = float(match.group(4))

        except ValueError:
            raise SampleException("ValueError while converting data: [%s]" %
                                  self.raw_data)

        result = [
            {DataParticleKey.VALUE_ID: NANODataParticleKey.TIME,
             DataParticleKey.VALUE: ntp_timestamp},
            {DataParticleKey.VALUE_ID: NANODataParticleKey.PRESSURE,
             DataParticleKey.VALUE: pressure},
            {DataParticleKey.VALUE_ID: NANODataParticleKey.TEMP,
             DataParticleKey.VALUE: temperature},
            {DataParticleKey.VALUE_ID: NANODataParticleKey.PPS_SYNC,
             DataParticleKey.VALUE: pps_sync},
        ]

        return result


###############################################################################
# Status Particles
###############################################################################
class NANOStatus01Particle(DataParticle):
    _data_particle_type = DataParticleType.NANO_STATUS
    nano_status_response = "No response found."

    @staticmethod
    def regex():
        """
        Example of output from DUMP-SETTINGS command:
        
        NANO,*______________________________________________________________
        NANO,*PAROSCIENTIFIC SMT SYSTEM INFORMATION
        NANO,*Model Number: 42.4K-265               
        NANO,*Serial Number: 120785
        NANO,*Firmware Revision: R5.20
        NANO,*Firmware Release Date: 03-25-13
        NANO,*PPS status: V : PPS signal NOT detected.
        NANO,*--------------------------------------------------------------
        NANO,*AA:7.161800     AC:7.290000     AH:160.0000     AM:0            
        NANO,*AP:0            AR:160.0000     BL:0            BR1:115200      
        NANO,*BR2:115200      BV:10.9         BX:112          C1:-9747.897    
        NANO,*C2:288.5739     C3:27200.78     CF:BA0F         CM:4            
        NANO,*CS:7412         D1:.0572567     D2:.0000000     DH:2000.000     
        NANO,*DL:0            DM:0            DO:0            DP:6            
        NANO,*DZ:.0000000     EM:0            ET:0            FD:.153479      
        NANO,*FM:0            GD:0            GE:2            GF:0            
        NANO,*GP::            GT:1            IA1:8           IA2:12          
        NANO,*IB:0            ID:1            IE:0            IK:46           
        NANO,*IM:0            IS:5            IY:0            KH:0            
        NANO,*LH:2250.000     LL:.0000000     M1:13.880032    M3:14.090198    
        NANO,*MA:             MD:0            MU:             MX:0            
        NANO,*NO:0            OI:0            OP:2100.000     OR:1.00         
        NANO,*OY:1.000000     OZ:0            PA:.0000000     PC:.0000000     
        NANO,*PF:2000.000     PI:25           PL:2400.000     PM:1.000000     
        NANO,*PO:0            PR:238          PS:0            PT:N            
        NANO,*PX:3            RE:0            RS:5            RU:0            
        NANO,*SD:12           SE:0            SI:OFF          SK:0            
        NANO,*SL:0            SM:OFF          SP:0            ST:10           
        NANO,*SU:0            T1:30.00412     T2:1.251426     T3:50.64434     
        NANO,*T4:134.5816     T5:.0000000     TC:.6781681     TF:.00          
        NANO,*TH:1,P4;>OK     TI:25           TJ:2            TP:0            
        NANO,*TQ:1            TR:952          TS:1            TU:0            
        NANO,*U0:5.839037     UE:0            UF:1.000000     
        NANO,*UL:                             UM:user         UN:1            
        NANO,*US:0            VP:4            WI:Def=15:00-061311             
        NANO,*XC:8            XD:A            XM:1            XN:0            
        NANO,*XS:0011         XX:1            Y1:-3818.141    Y2:-10271.53    
        NANO,*Y3:.0000000     ZE:0            ZI:0            ZL:0            
        NANO,*ZM:0            ZS:0            ZV:.0000000     
        """

        pattern = r'NANO,\*----.*' + NEWLINE  # pattern starts with NANO '
        pattern += r'NANO,\*PAROSCIENTIFIC SMT SYSTEM INFORMATION.*' + NEWLINE
        pattern += r'NANO,.*ZM.*' + NEWLINE
        return pattern

    @staticmethod
    def regex_compiled():
        return re.compile(NANOStatus01Particle.regex(), re.DOTALL)

    def _build_parsed_values(self):
        pass

    def build_response(self):
        """
        build the response to the command that initiated this status.  In this 
        case just assign the string to the nano_status_response.  In the   
        future, we might want to cook the string, as in remove some
        of the other sensor's chunks.
        
        The nano_status_response is pulled out later when do_cmd_resp calls
        the response handler.  The response handler gets passed the particle
        object, and it then uses that to access the objects attribute that
        contains the response string.
        """
        self.nano_status_response = self.raw_data


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
    # noinspection PyMethodMayBeStatic
    def get_resource_params(self):
        """
        Return list of device parameters available.
        """
        return Parameter.list()

    def _build_protocol(self):
        """
        Construct the driver protocol state machine.
        """
        self._protocol = Protocol(Prompt, NEWLINE, self._driver_event)


# noinspection PyMethodMayBeStatic
class Protocol(BotptProtocol):
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
        BotptProtocol.__init__(self, prompts, newline, driver_event)

        # Build protocol state machine.
        self._protocol_fsm = InstrumentFSM(ProtocolState, ProtocolEvent,
                                           ProtocolEvent.ENTER, ProtocolEvent.EXIT)

        handlers = {
            ProtocolState.UNKNOWN: [
                (ProtocolEvent.ENTER, self._handler_unknown_enter),
                (ProtocolEvent.ENTER, self._handler_unknown_enter),
                (ProtocolEvent.EXIT, self._handler_unknown_exit),
                (ProtocolEvent.DISCOVER, self._handler_unknown_discover),
            ],
            ProtocolState.AUTOSAMPLE: [
                (ProtocolEvent.ENTER, self._handler_autosample_enter),
                (ProtocolEvent.EXIT, self._handler_autosample_exit),
                (ProtocolEvent.STOP_AUTOSAMPLE, self._handler_autosample_stop_autosample),
                (ProtocolEvent.ACQUIRE_STATUS, self._handler_command_autosample_acquire_status),
                (ProtocolEvent.SET_TIME, self._handler_command_autosample_set_time),
            ],
            ProtocolState.COMMAND: [
                (ProtocolEvent.ENTER, self._handler_command_enter),
                (ProtocolEvent.EXIT, self._handler_command_exit),
                (ProtocolEvent.GET, self._handler_command_get),
                (ProtocolEvent.SET, self._handler_command_set),
                (ProtocolEvent.ACQUIRE_STATUS, self._handler_command_autosample_acquire_status),
                (ProtocolEvent.SET_TIME, self._handler_command_autosample_set_time),
                (ProtocolEvent.START_AUTOSAMPLE, self._handler_command_start_autosample),
            ],
        }

        for state in handlers:
            for event, handler in handlers[state]:
                self._protocol_fsm.add_handler(state, event, handler)

        # Construct the parameter dictionary containing device parameters,
        # current parameter values, and set formatting functions.
        self._build_param_dict()

        # Add build handlers for device commands.
        self._add_build_handler(InstrumentCommand.DATA_ON, self._build_command)
        self._add_build_handler(InstrumentCommand.DATA_OFF, self._build_command)
        self._add_build_handler(InstrumentCommand.DUMP_SETTINGS, self._build_command)
        self._add_build_handler(InstrumentCommand.SET_TIME, self._build_command)

        # Add response handlers for device commands.
        self._add_response_handler(InstrumentCommand.DATA_ON, self._parse_data_on_off_resp)
        self._add_response_handler(InstrumentCommand.DATA_OFF, self._parse_data_on_off_resp)
        self._add_response_handler(InstrumentCommand.DUMP_SETTINGS, self._parse_status_01_resp)

        # Add sample handlers.

        # State state machine in UNKNOWN state.
        self._protocol_fsm.start(ProtocolState.UNKNOWN)

        # commands sent sent to device to be filtered in responses for telnet DA
        self._sent_cmds = []

        #
        self._chunker = StringChunker(Protocol.sieve_function)

        # set up the regexes now so we don't have to do it repeatedly
        self.data_regex = NANODataParticle.regex_compiled()
        self.status_01_regex = NANOStatus01Particle.regex_compiled()
        self._last_data_timestamp = 0
        self._filter_string = NANO_STRING

    @staticmethod
    def sieve_function(raw_data):
        """
        The method that splits samples
        """

        matchers = []
        return_list = []

        matchers.append(NANODataParticle.regex_compiled())
        matchers.append(NANOStatus01Particle.regex_compiled())

        for matcher in matchers:
            for match in matcher.finditer(raw_data):
                return_list.append((match.start(), match.end()))

        return return_list

    def _filter_capabilities(self, events):
        """
        Return a list of currently available capabilities.
        """
        events_out = [x for x in events if Capability.has(x)]
        return events_out

    def _build_cmd_dict(self):
        """
        Populate the command dictionary with NOAA NANO Driver metadata information. 
        Currently NANO only supports DATA_ON and DATA_OFF.
        """
        self._cmd_dict = ProtocolCommandDict()

    def _build_param_dict(self):
        """
        Populate the parameter dictionary with parameters.
        For each parameter key, add match string, match lambda function,
        and value formatting function for set commands.
        """
        # Add parameter handlers to parameter dict.
        pass

    def _got_chunk(self, chunk, timestamp):
        """
        """
        # TODO docstring
        log.debug("_got_chunk_: %s", chunk)
        if not (self._extract_sample(NANODataParticle, NANODataParticle.regex_compiled(), chunk, timestamp) or
                    self._extract_sample(NANOStatus01Particle, NANOStatus01Particle.regex_compiled(), chunk,
                                         timestamp)):
            pass

    def _parse_data_on_off_resp(self, response, prompt):
        log.debug("_parse_data_on_off_resp: response: %r; prompt: %s", response, prompt)
        #return response.nano_command_response
        return

    def _parse_status_01_resp(self, response, prompt):
        log.debug("_parse_status_01_resp: response: %r; prompt: %s", response, prompt)
        #return response.nano_status_response
        return

    ########################################################################
    # Unknown handlers.
    ########################################################################

    def _handler_unknown_discover(self, *args, **kwargs):
        """
        Discover current state
        @retval (next_state, result)
        """
        # Attempt to find a line containing a NANO sample
        # If a sample is found, go to AUTOSAMPLE, otherwise COMMAND
        next_state = ProtocolState.COMMAND
        next_agent_state = ResourceAgentState.COMMAND
        result = None
        try:
            response = self._get_response(timeout=1, response_regex=self.data_regex)
            log.debug('_handler_unknown_discover: response: [%r]', response)
            # autosample
            if response:
                next_state = ProtocolState.AUTOSAMPLE
                next_agent_state = ResourceAgentState.STREAMING
                result = ProtocolState.AUTOSAMPLE
        # timed out, assume command
        except InstrumentTimeoutException:
            pass
        return next_state, (next_agent_state, result)

    ########################################################################
    # Autosample handlers.
    ########################################################################

    def _handler_autosample_stop_autosample(self):
        """
        Turn the nano data off
        """
        return self._handler_command_generic(InstrumentCommand.DATA_OFF,
                                             ProtocolState.COMMAND,
                                             ResourceAgentState.COMMAND,
                                             None,
                                             expected_prompt=None)

    ########################################################################
    # Command handlers.
    ########################################################################

    def _handler_command_get(self, *args, **kwargs):
        """
        Get parameter
        """

        next_state = None
        result = {}

        return next_state, result

    def _handler_command_set(self, *args, **kwargs):
        """
        Set parameter
        """
        next_state = None
        result = None

        params = args[0]

        return next_state, result

    def _handler_command_start_autosample(self, *args, **kwargs):
        """
        Turn the nano data on
        """
        return self._handler_command_generic(InstrumentCommand.DATA_ON,
                                             ProtocolState.AUTOSAMPLE,
                                             ResourceAgentState.STREAMING,
                                             None,
                                             expected_prompt=None)

    ########################################################################
    # Handlers common to Command and Autosample States.
    ########################################################################

    def _handler_command_autosample_acquire_status(self, *args, **kwargs):
        """
        Get device status
        """
        return self._handler_command_generic(InstrumentCommand.DUMP_SETTINGS,
                                             None, None, None, None)

    def _handler_command_autosample_set_time(self, *args, **kwargs):
        """
        Get device status
        """
        next_state = None
        next_agent_state = None
        result = None
        log.debug("_handler_command_autosample_set_time")

        timeout = kwargs.get('timeout')

        if timeout is None:
            result = self._do_cmd_resp(InstrumentCommand.SET_TIME)
        else:
            result = self._do_cmd_resp(InstrumentCommand.SET_TIME, timeout=timeout)

        log.debug("SET_TIME response: %s", result)

        return next_state, (next_agent_state, result)