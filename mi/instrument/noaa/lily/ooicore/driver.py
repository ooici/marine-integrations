"""
@package mi.instrument.noaa.lily.ooicore.driver
@file marine-integrations/mi/instrument/noaa/lily/ooicore/driver.py
@author David Everett
@brief Driver for the ooicore
Release notes:

Driver for LILY TILT on the RSN-BOTPT instrument (v.6)

"""

__author__ = 'David Everett'
__license__ = 'Apache 2.0'

import string
import re
import time
import datetime
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
from mi.core.instrument.protocol_cmd_dict import ProtocolCommandDict
from mi.core.instrument.protocol_param_dict import ParameterDictVisibility
from mi.core.instrument.protocol_param_dict import ParameterDictType
from mi.core.instrument.data_particle import DataParticle
from mi.core.instrument.data_particle import DataParticleKey
from mi.core.instrument.data_particle import CommonDataParticleType
from mi.core.instrument.chunker import StringChunker

# DHE: Might need this if we use multiline regex
#from mi.instrument.noaa.driver import BOTPTParticle

from mi.core.exceptions import InstrumentProtocolException
from mi.core.exceptions import InstrumentTimeoutException
from mi.core.exceptions import SampleException

###
#    Driver Constant Definitions
###

# newline.
NEWLINE = '\x0a'
LILY_STRING = 'LILY,'
LILY_COMMAND_STRING = '*9900XY'
LILY_DATA_ON = 'C2' # turns on continuous data
LILY_DATA_OFF = 'C-OFF' # turns off continuous data
LILY_DUMP_01 = '-DUMP-SETTINGS' # outputs current settings
LILY_DUMP_02 = '-DUMP2' # outputs current extended settings

# default timeout.
TIMEOUT = 10

class DataParticleType(BaseEnum):
    """
    Data particle types produced by this driver
    """
    RAW = CommonDataParticleType.RAW

class ProtocolState(BaseEnum):
    """
    Instrument protocol states
    """
    UNKNOWN = DriverProtocolState.UNKNOWN
    COMMAND = DriverProtocolState.COMMAND
    AUTOSAMPLE = DriverProtocolState.AUTOSAMPLE

class ExportedInstrumentCommand(BaseEnum):
    DUMP_01 = "EXPORTED_INSTRUMENT_DUMP_SETTINGS"
    DUMP_02 = "EXPORTED_INSTRUMENT_DUMP_EXTENDED_SETTINGS"

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
    DUMP_01 = ExportedInstrumentCommand.DUMP_01
    DUMP_02 = ExportedInstrumentCommand.DUMP_02

class Capability(BaseEnum):
    """
    Protocol events that should be exposed to users (subset of above).
    """
    GET = ProtocolEvent.GET
    SET = ProtocolEvent.SET
    START_AUTOSAMPLE = ProtocolEvent.START_AUTOSAMPLE
    STOP_AUTOSAMPLE = ProtocolEvent.STOP_AUTOSAMPLE
    DUMP_01 = ProtocolEvent.DUMP_01
    DUMP_02 = ProtocolEvent.DUMP_02
    
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
    DATA_ON  = LILY_STRING + LILY_COMMAND_STRING + LILY_DATA_ON + NEWLINE # turns on continuous data 
    DATA_OFF = LILY_STRING + LILY_COMMAND_STRING + LILY_DATA_OFF + NEWLINE  # turns off continuous data 
    DUMP_SETTINGS_01  = LILY_STRING + LILY_COMMAND_STRING + LILY_DUMP_01 + NEWLINE   # outputs current settings 
    DUMP_SETTINGS_02  = LILY_STRING + LILY_COMMAND_STRING + LILY_DUMP_02 + NEWLINE    # outputs current extended settings 

class LILYCommandResponse():

    def __init__(self, raw_data):
        """ 
        Construct a LILYCommandResponse object 
        
        @param raw_data The raw data used in the particle
        """
        self.raw_data = raw_data
        self.lily_command_response = None

    @staticmethod
    def regex():
        """
        Regular expression to match a sample pattern
        @return: regex string
        """
        pattern = r'LILY,' # pattern starts with LILY '
        pattern += r'(.*),' # group 1: time
        pattern += r'\*9900XY' # generic part of LILY command
        pattern += r'(.*)' # group 2: echoed command
        pattern += NEWLINE
        return pattern

    @staticmethod
    def regex_compiled():
        """
        get the compiled regex pattern
        @return: compiled re
        """
        return re.compile(LILYCommandResponse.regex())

    def check_command_response(self, expected_response):
        """
        Generic command response method; the expected response
        is passed in as a parameter; that is used to check 
        whether the response from the sensor is valid (positive)
        or not.
        """
        retValue = False

        match = LILYCommandResponse.regex_compiled().match(self.raw_data)

        if not match:
            raise SampleException("No regex match of command response: [%s]" %
                                  self.raw_data)
        try:
            resp_time = match.group(1)
            timestamp = time.strptime(resp_time, "%Y/%m/%d %H:%M:%S")
            self.lily_command_response = match.group(2)
            if expected_response is not None:
                if self.lily_command_response == expected_response:
                    retValue = True
            else:
                retValue = True  

        except ValueError:
            raise SampleException("check_command_response: ValueError" +
                                  " while converting data: [%s]" %
                                  self.raw_data)
        
        return retValue

###############################################################################
# Data Particles
###############################################################################

class DataParticleType(BaseEnum):
    LILY_PARSED = 'botpt_lily_sample'
    LILY_STATUS = 'botpt_lily_status'

class LILYDataParticleKey(BaseEnum):
    TIME = "lily_time"
    X_TILT = "lily_x_tilt"
    Y_TILT = "lily_y_tilt"
    TEMP = "temperature"
    SN = "serial_number"

class LILYDataParticle(DataParticle):
    """
    Routines for parsing raw data into a data particle structure. Override
    the building of values, and the rest should come along for free.

    Sample:
       LILY,2013/06/24 23:22:00,-236.026,  25.666,194.25, 26.01,11.96,N9655
       LILY,2013/06/24 23:22:02,-236.051,  25.611,194.25, 26.02,11.96,N9655       
    Format:
       IIII,YYYY/MM/DD hh:mm:ss,x.xxxx,y.yyyy,tt.tt,sn

        ID = IIII = LILY
        Year = YYYY
        Month = MM
        Day = DD
        Hour = hh
        Minutes = mm
        Seconds = ss
        NOTE: The above time expression is all grouped into one string.
        X_TILT = x.xxxx (float degrees)
        Y_TILT = y.yyyy (float degrees)
        Temp = tt.tt (float degrees C)
        Serial Number = sn
    """
    _data_particle_type = DataParticleType.LILY_PARSED

    @staticmethod
    def regex():
        """
        Regular expression to match a sample pattern
        @return: regex string
        """
        pattern = r'LILY,' # pattern starts with LILY '
        pattern += r'(.*),' # 1 time
        pattern += r'( -*[.0-9]+),' # 2 x-tilt
        pattern += r'( -*[.0-9]+),' # 3 y-tilt
        pattern += r'(.*),' # 4 temp
        pattern += r'(.*)' # 5 serial number
        pattern += NEWLINE
        return pattern

    @staticmethod
    def regex_compiled():
        """
        get the compiled regex pattern
        @return: compiled re
        """
        return re.compile(LILYDataParticle.regex())

    def _build_parsed_values(self):
        """
        Take something in the autosample/TS format and split it into
        C, T, and D values (with appropriate tags)
        
        @throws SampleException If there is a problem with sample creation
        """
        match = LILYDataParticle.regex_compiled().match(self.raw_data)

        if not match:
            raise SampleException("No regex match of parsed sample data: [%s]" %
                                  self.raw_data)
            
        try:
            lily_time = match.group(1)
            timestamp = time.strptime(lily_time, "%Y/%m/%d %H:%M:%S")
            self.set_internal_timestamp(unix_time=time.mktime(timestamp))
            ntp_timestamp = ntplib.system_to_ntp_time(time.mktime(timestamp))
            x_tilt = float(match.group(2))
            y_tilt = float(match.group(3))
            temperature = float(match.group(4))
            sn = str(match.group(5))

        except ValueError:
            raise SampleException("ValueError while converting data: [%s]" %
                                  self.raw_data)
        
        result = [
                  {DataParticleKey.VALUE_ID: LILYDataParticleKey.TIME,
                   DataParticleKey.VALUE: ntp_timestamp},
                  {DataParticleKey.VALUE_ID: LILYDataParticleKey.X_TILT,
                   DataParticleKey.VALUE: x_tilt},
                  {DataParticleKey.VALUE_ID: LILYDataParticleKey.Y_TILT,
                   DataParticleKey.VALUE: y_tilt},
                  {DataParticleKey.VALUE_ID: LILYDataParticleKey.TEMP,
                   DataParticleKey.VALUE: temperature},
                  {DataParticleKey.VALUE_ID: LILYDataParticleKey.SN,
                   DataParticleKey.VALUE: sn}
                  ]
        
        return result

###############################################################################
# Status Particles
###############################################################################
class LILYStatusSignOnParticleKey(BaseEnum):
    MODEL = "model"
    SN = "serial_number"
    FIRMWARE_VERSION = "firmware_version"
    IDENTITY = "identity"

class LILYStatusSignOnParticle(DataParticle):
    _data_particle_type = DataParticleType.LILY_STATUS

    @staticmethod
    def regex():
        """
        Example of output from display signon command (Note: we don't issue this command,
        but the output is prepended to the DUMP-SETTINGS command):
        
        LILY,2013/06/12 18:03:44,*APPLIED GEOMECHANICS Model MD900-T Firmware V5.2 SN-N8642 ID01
        """

        pattern = r'LILY,' # pattern starts with LILY '
        pattern += r'(.*?),' # group 1: time
        pattern += r'\*APPLIED GEOMECHANICS'
        pattern += r'.*?' # non-greedy match of all the junk between
        pattern += NEWLINE
        return pattern

    @staticmethod
    def regex_compiled():
        return re.compile(LILYStatusSignOnParticle.regex())

    def _build_parsed_values(self):
        """        
        @throws SampleException If there is a problem with sample creation
        """
        match = LILYStatusSignOnParticle.regex_compiled().match(self.raw_data)
        
        try:
            lily_time = match.group(1)
            timestamp = time.strptime(lily_time, "%Y/%m/%d %H:%M:%S")
            self.set_internal_timestamp(unix_time=time.mktime(timestamp))
            ntp_timestamp = ntplib.system_to_ntp_time(time.mktime(timestamp))

        except ValueError:
            raise SampleException("ValueError while converting data: [%s]" %
                                  self.raw_data)
        
        result = [
                  {DataParticleKey.VALUE_ID: LILYSignOnParticleKey.TIME,
                   DataParticleKey.VALUE: ntp_timestamp},
                  # Add firmware version"
                  #{DataParticleKey.VALUE_ID: LILYSignOnParticleKey.SN,
                  # DataParticleKey.VALUE: sn}
                  ]
        
        return result

class LILYStatus_01_Particle(DataParticle):
    _data_particle_type = DataParticleType.LILY_STATUS
    lily_status_response = "No response found."

    @staticmethod
    def regex():
        """
        Example of output from DUMP-SETTINGS command:
        
        LILY,2013/06/24 23:35:41,*APPLIED GEOMECHANICS LILY Firmware V2.1 SN-N9655 ID01
        LILY,2013/06/24 23:35:41,*01: Vbias= 0.0000 0.0000 0.0000 0.0000
        LILY,2013/06/24 23:35:41,*01: Vgain= 0.0000 0.0000 0.0000 0.0000
        LILY,2013/06/24 23:35:41,*01: Vmin:  -2.50  -2.50   2.50   2.50
        LILY,2013/06/24 23:35:41,*01: Vmax:   2.50   2.50   2.50   2.50
        LILY,2013/06/24 23:35:41,*01: a0=    0.00000    0.00000    0.00000    0.00000    0.00000    0.00000
        LILY,2013/06/24 23:35:41,*01: a1=    0.00000    0.00000    0.00000    0.00000    0.00000    0.00000
        LILY,2013/06/24 23:35:41,*01: a2=    0.00000    0.00000    0.00000    0.00000    0.00000    0.00000
        LILY,2013/06/24 23:35:41,*01: a3=    0.00000    0.00000    0.00000    0.00000    0.00000    0.00000
        LILY,2013/06/24 23:35:41,*01: Tcoef 0: Ks=           0 Kz=           0 Tcal=           0
        LILY,2013/06/24 23:35:41,*01: Tcoef 1: Ks=           0 Kz=           0 Tcal=           0
        LILY,2013/06/24 23:35:41,*01: N_SAMP= 360 Xzero=  0.00 Yzero=  0.00
        LILY,2013/06/24 23:35:41,*01: TR-PASH-OFF E99-ON  SO-NMEA-SIM XY-EP 19200 baud FV-   
        """
        
        
        pattern = r'LILY,' # pattern starts with LILY '
        pattern += r'(.*?),' # group 1: time
        pattern += r'\*APPLIED GEOMECHANICS'
        pattern += r'.*?' # non-greedy match of all the junk between
        pattern += r'baud FV- *?' + NEWLINE
        return pattern

    @staticmethod
    def regex_compiled():
        return re.compile(LILYStatus_01_Particle.regex(), re.DOTALL)

    def _build_parsed_values(self):
        pass

    def build_response(self):
        """
        build the response to the command that initiated this status.  In this 
        case just assign the string to the lily_status_response.  In the   
        future, we might want to cook the string, as in remove some
        of the other sensor's chunks.
        
        The lily_status_response is pulled out later when do_cmd_resp calls
        the response handler.  The response handler gets passed the particle
        object, and it then uses that to access the objects attribute that
        contains the response string.
        """
        self.lily_status_response = self.raw_data
    
class LILYStatus_02_Particle(DataParticle):
    _data_particle_type = DataParticleType.LILY_STATUS
    lily_status_response = "No response found."

    @staticmethod
    def regex():
        """
        Example of output from DUMP2 command:
        LILY,2013/06/24 23:36:05,*01: TBias: 5.00 
        LILY,2013/06/24 23:36:05,*01: Above 0.00(KZMinTemp): kz[0]=           0, kz[1]=           0
        LILY,2013/06/24 23:36:05,*01: Below 0.00(KZMinTemp): kz[2]=           0, kz[3]=           0
        LILY,2013/06/24 23:36:05,*01: ADCDelay:  310 
        LILY,2013/06/24 23:36:05,*01: PCA Model: 84833-14
        LILY,2013/06/24 23:36:05,*01: Firmware Version: 2.1 Rev D
        LILY,2013/06/24 23:36:05,*01: X Ch Gain= 1.0000, Y Ch Gain= 1.0000, Temperature Gain= 1.0000
        LILY,2013/06/24 23:36:05,*01: Calibrated in uRadian, Current Output Mode: uRadian
        LILY,2013/06/24 23:36:05,*01: Using RS232
        LILY,2013/06/24 23:36:05,*01: Real Time Clock: Installed
        LILY,2013/06/24 23:36:05,*01: Use RTC for Timing: Yes
        LILY,2013/06/24 23:36:05,*01: External Flash: 2162688 Bytes Installed
        LILY,2013/06/24 23:36:05,*01: Flash Status (in Samples) (Used/Total): (-1/55424)
        LILY,2013/06/24 23:36:05,*01: Low Power Logger Data Rate: -1 Seconds per Sample
        LILY,2013/06/24 23:36:05,*01: Calibration method: Dynamic 
        LILY,2013/06/24 23:36:05,*01: Positive Limit=330.00   Negative Limit=-330.00 
        IRIS,2013/06/24 23:36:05, -0.0680, -0.3284,28.07,N3616
        LILY,2013/06/24 23:36:05,*01: Calibration Points:023  X: Enabled  Y: Enabled
        LILY,2013/06/24 23:36:05,*01: Uniaxial (x2) Sensor Type (1)
        LILY,2013/06/24 23:36:05,*01: ADC: 16-bit(external)
        LILY,2013/06/24 23:36:05,*01: Compass: Installed   Magnetic Declination: 0.000000
        LILY,2013/06/24 23:36:05,*01: Compass: Xoffset:   12, Yoffset:  210, Xrange: 1371, Yrange: 1307
        LILY,2013/06/24 23:36:05,*01: PID Coeff: iMax:100.0, iMin:-100.0, iGain:0.0150, pGain: 2.50, dGain: 10.0
        LILY,2013/06/24 23:36:05,*01: Motor I_limit: 90.0mA
        LILY,2013/06/24 23:36:05,*01: Current Time: 01/11/00 02:12:32
        LILY,2013/06/24 23:36:06,*01: Supply Voltage: 11.96 Volts
        LILY,2013/06/24 23:36:06,*01: Memory Save Mode: Off
        LILY,2013/06/24 23:36:06,*01: Outputting Data: Yes
        LILY,2013/06/24 23:36:06,*01: Auto Power-Off Recovery Mode: Off
        LILY,2013/06/24 23:36:06,*01: Advanced Memory Mode: Off, Delete with XY-MEMD: No
        """
        pattern = r'LILY,' # pattern starts with LILY '
        pattern += r'(.*?),' # group 1: time
        pattern += r'\*01: TBias:' # unique identifier for status
        pattern += r'.*?' # non-greedy match of all the junk between
        pattern += r'\*01: Advanced Memory Mode: Off, Delete with XY-MEMD: No' + NEWLINE
        return pattern

    @staticmethod
    def regex_compiled():
        return re.compile(LILYStatus_02_Particle.regex(), re.DOTALL)

    def encoders(self):
        return {}

    def _build_parsed_values(self):
        pass

    def build_response(self):
        """
        build the response to the command that initiated this status.  In this 
        case just assign the string to the lily_status_response.  In the   
        future, we might want to cook the string, as in remove some
        of the other sensor's chunks.
        
        The lily_status_response is pulled out later when do_cmd_resp calls
        the response handler.  The response handler gets passed the particle
        object, and it then uses that to access the objects attribute that
        contains the response string.
        """
        self.lily_status_response = self.raw_data
    

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

        self._protocol_fsm.add_handler(ProtocolState.AUTOSAMPLE, ProtocolEvent.ENTER, self._handler_autosample_enter)
        self._protocol_fsm.add_handler(ProtocolState.AUTOSAMPLE, ProtocolEvent.EXIT, self._handler_autosample_exit)
        self._protocol_fsm.add_handler(ProtocolState.AUTOSAMPLE, ProtocolEvent.STOP_AUTOSAMPLE, self._handler_autosample_stop_autosample)
        self._protocol_fsm.add_handler(ProtocolState.AUTOSAMPLE, ProtocolEvent.DUMP_01, self._handler_command_autosample_dump01)
        self._protocol_fsm.add_handler(ProtocolState.AUTOSAMPLE, ProtocolEvent.DUMP_02, self._handler_command_autosample_dump02)

        self._protocol_fsm.add_handler(ProtocolState.COMMAND, ProtocolEvent.ENTER, self._handler_command_enter)
        self._protocol_fsm.add_handler(ProtocolState.COMMAND, ProtocolEvent.EXIT, self._handler_command_exit)
        self._protocol_fsm.add_handler(ProtocolState.COMMAND, ProtocolEvent.GET, self._handler_command_get)
        self._protocol_fsm.add_handler(ProtocolState.COMMAND, ProtocolEvent.SET, self._handler_command_set)
        self._protocol_fsm.add_handler(ProtocolState.COMMAND, ProtocolEvent.DUMP_01, self._handler_command_autosample_dump01)
        self._protocol_fsm.add_handler(ProtocolState.COMMAND, ProtocolEvent.DUMP_02, self._handler_command_autosample_dump02)
        self._protocol_fsm.add_handler(ProtocolState.COMMAND, ProtocolEvent.START_AUTOSAMPLE, self._handler_command_start_autosample)

        # Construct the parameter dictionary containing device parameters,
        # current parameter values, and set formatting functions.
        self._build_param_dict()

        # Add build handlers for device commands.
        self._add_build_handler(InstrumentCommand.DATA_ON, self._build_command)
        self._add_build_handler(InstrumentCommand.DATA_OFF, self._build_command)
        self._add_build_handler(InstrumentCommand.DUMP_SETTINGS_01, self._build_command)
        self._add_build_handler(InstrumentCommand.DUMP_SETTINGS_02, self._build_command)

        # Add response handlers for device commands.
        self._add_response_handler(InstrumentCommand.DATA_ON, self._parse_data_on_off_resp)
        self._add_response_handler(InstrumentCommand.DATA_OFF, self._parse_data_on_off_resp)
        self._add_response_handler(InstrumentCommand.DUMP_SETTINGS_01, self._parse_status_01_resp)
        self._add_response_handler(InstrumentCommand.DUMP_SETTINGS_02, self._parse_status_02_resp)

        # Add sample handlers.

        # State state machine in UNKNOWN state.
        self._protocol_fsm.start(ProtocolState.UNKNOWN)

        # commands sent sent to device to be filtered in responses for telnet DA
        self._sent_cmds = []

        #
        self._chunker = StringChunker(Protocol.sieve_function)

        # set up the regexes now so we don't have to do it repeatedly
        self.data_regex = LILYDataParticle.regex_compiled()
        self.cmd_rsp_regex = LILYCommandResponse.regex_compiled()
        self.signon_regex = LILYStatusSignOnParticle.regex_compiled()
        self.status_01_regex = LILYStatus_01_Particle.regex_compiled()
        self.status_02_regex = LILYStatus_02_Particle.regex_compiled()


    @staticmethod
    def sieve_function(raw_data):
        """
        The method that splits samples
        """

        matchers = []
        return_list = []

        """
        would be nice to be able to do this.
        matchers.append(self.data_regex)
        matchers.append(self.signon_regex)
        matchers.append(self.status_01_regex)
        matchers.append(self.status_02_regex)
        matchers.append(self.cmd_rsp_regex)
        """
        
        """
        Not a good idea to be compiling these for every invocation of this
        method; they don't change.
        """
 
        matchers.append(LILYDataParticle.regex_compiled())
        #matchers.append(LILYStatusSignOnParticle.regex_compiled())
        matchers.append(LILYStatus_01_Particle.regex_compiled())
        matchers.append(LILYStatus_02_Particle.regex_compiled())
        matchers.append(LILYCommandResponse.regex_compiled())

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
        Populate the command dictionary with NOAA LILY Driver metadata information. 
        Currently LILY only supports DATA_ON and DATA_OFF.
        """
        self._cmd_dict = ProtocolCommandDict()
        
    def _build_param_dict(self):
        """
        Populate the parameter dictionary with parameters.
        For each parameter key, add match stirng, match lambda function,
        and value formatting function for set commands.
        """
        # Add parameter handlers to parameter dict.
        pass

    def add_to_buffer(self, data):
        '''
        Overridden because most of the data coming to this driver
        isn't meant for it.  I'm only adding to the buffer when
        a chunk arrives (see my_add_to_buffer, below), so this 
        method does nothing.
        
        @param data: bytes to add to the buffer
        '''
        pass
    
    def _my_add_to_buffer(self, data):
        """
        Replaces add_to_buffer. Most data coming to this driver isn't meant
        for it.  I'm only adding to the buffer when data meant for this 
        driver arrives.  That is accomplished using the chunker mechanism. This
        method would normally collet any data fragments that are then search by
        the get_response method in the context of a synchronous command sent
        from the observatory.  However, because so much data arrives here that
        is not applicable, the add_to_buffer method has been overridden to do
        nothing.
        
        @param data: bytes to add to the buffer
        """
        
        # Update the line and prompt buffers.
        self._linebuf += data
        self._promptbuf += data
        self._last_data_timestamp = time.time()

    def _got_chunk(self, chunk, timestamp):
        """
        The base class got_data has gotten a chunk from the chunker.  Invoke
        this driver's _my_add_to_buffer, or pass it to extract_sample
        with the appropriate particle objects and REGEXes.  We need to invoke
        _my_add_to_buffer, because we've overridden the base class
        add_to_buffer that is called from got_data().  The reason is explained
        in comments in _my_add_to_buffer.
        """

        log.debug("_got_chunk_: %s", chunk)
        
        if (self.cmd_rsp_regex.match(chunk) \
        #or self.signon_regex.match(chunk) \ # currently not using the signon chunk
        or self.status_01_regex.match(chunk) \
        or self.status_02_regex.match(chunk)):
            self._my_add_to_buffer(chunk)
        else:
            if not self._extract_sample(LILYDataParticle,
                                        self.data_regex, 
                                        chunk, timestamp):
                raise InstrumentProtocolException("Unhandled chunk")


    def _build_command(self, cmd, *args, **kwargs):
        command = cmd + NEWLINE
        log.debug("_build_command: command is: %s", command)
        return command

    def _parse_data_on_off_resp(self, response, prompt):
        log.debug("_parse_data_on_off_resp: response: %r; prompt: %s", response, prompt)
        return response.lily_command_response
        
    def _parse_status_01_resp(self, response, prompt):
        log.debug("_parse_status_01_resp: response: %r; prompt: %s", response, prompt)
        return response.lily_status_response
        
    def _parse_status_02_resp(self, response, prompt):
        log.debug("_parse_status_02_resp: response: %r; prompt: %s", response, prompt)
        return response.lily_status_response
        
    def _wakeup(self, timeout, delay=1):
        """
        Overriding _wakeup; does not apply to this instrument
        """
        pass

    def _get_response(self, timeout=10, expected_prompt=None):
        """
        Overriding _get_response: this one uses regex on chunks
        that have already been filtered by the chunker.  An improvement
        to the chunker could be metadata labeling the chunk so that we
        don't have to do another match, although I don't think it is that
        expensive once the chunk has been pulled out to match again
        
        @param timeout The timeout in seconds
        @param expected_prompt Only consider the specific expected prompt as
        presented by this string
        @throw InstrumentProtocolExecption on timeout
        """
        # Grab time for timeout and wait for response

        starttime = time.time()
        
        response = None
        
        """
        Spin around for <timeout> looking for the response to arrive
        """
        continuing = True
        response = "no response"
        while continuing:
            if self.cmd_rsp_regex.match(self._promptbuf):
                response = LILYCommandResponse(self._promptbuf)
                log.debug("_get_response() matched CommandResponse")
                response.check_command_response(expected_prompt)
                continuing = False
            #elif self.signon_regex.match(self._promptbuf):
                #response = LILYStatusSignOnParticle(self._promptbuf)
                #log.debug("~~~~~~~~~ SignonResponse")
                """
                Currently not using the signon particle.
                """
            elif self.status_01_regex.match(self._promptbuf):
                response = LILYStatus_01_Particle(self._promptbuf)
                log.debug("_get_response() matched Status_01_Response")
                response.build_response()
                continuing = False
            elif self.status_02_regex.match(self._promptbuf):
                response = LILYStatus_02_Particle(self._promptbuf)
                log.debug("_get_response() matched Status_02_Response")
                response.build_response()
                continuing = False
            else:
                self._promptbuf = ''
                time.sleep(.1)

            if timeout and time.time() > starttime + timeout:
                raise InstrumentTimeoutException("in BOTPT LILY driver._get_response()")

        return ('LILY_RESPONSE', response)
    
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
        return (ProtocolState.COMMAND, ResourceAgentState.IDLE)

    ########################################################################
    # Autosample handlers.
    ########################################################################

    def _handler_autosample_enter(self, *args, **kwargs):
        """
        Enter autosample state.
        """

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
        Turn the lily data off
        """
        next_state = ProtocolState.COMMAND
        next_agent_state = ResourceAgentState.COMMAND

        result = self._do_cmd_resp(InstrumentCommand.DATA_OFF, 
                                   expected_prompt = LILY_DATA_OFF)
        
        return (next_state, (next_agent_state, result))

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
        result = {}

        return (next_state, result)

    def _handler_command_set(self, *args, **kwargs):
        """
        Set parameter
        """
        next_state = None
        result = None

        params = args[0]
        
        return (next_state, result)

    def _handler_command_start_autosample(self, *args, **kwargs):
        """
        Turn the lily data on
        """
        next_state = ProtocolState.AUTOSAMPLE
        next_agent_state = ResourceAgentState.STREAMING

        """ 
        call _do_cmd_resp, passing our LILY_DATA_ON as the expected_prompt
        """
        result = self._do_cmd_resp(InstrumentCommand.DATA_ON, 
                                   expected_prompt = LILY_DATA_ON)

        return (next_state, (next_agent_state, result))

    def _handler_command_exit(self, *args, **kwargs):
        """
        Exit command state.
        """
        pass

    ########################################################################
    # Handlers common to Command and Autosample States.
    ########################################################################

    def _handler_command_autosample_acquire_status(self, *args, **kwargs):
        """
        Get device status
        """
        next_state = None
        next_agent_state = None
        result = None
        log.debug("_handler_command_autosample_acquire_status")

        result = self._do_cmd_resp(InstrumentCommand.DUMP_SETTINGS_01)

        log.debug("DUMP_SETTINGS_01 response: %s", result)

        result = self._do_cmd_resp(InstrumentCommand.DUMP_SETTINGS_02)

        log.debug("DUMP_SETTINGS_02 response: %s", result)

        return (next_state, (next_agent_state, result))


    def _handler_command_autosample_dump01(self, *args, **kwargs):
        """
        Get device status
        """
        next_state = None
        next_agent_state = None
        result = None
        log.debug("_handler_command_autosample_dump01")

        timeout = kwargs.get('timeout')

        if timeout is not None:
            result = self._do_cmd_resp(InstrumentCommand.DUMP_SETTINGS_01, timeout = timeout)
        else:
            result = self._do_cmd_resp(InstrumentCommand.DUMP_SETTINGS_01)

        log.debug("DUMP_SETTINGS_01 response: %s", result)

        return (next_state, (next_agent_state, result))


    def _handler_command_autosample_dump02(self, *args, **kwargs):
        """
        Get device status
        """
        next_state = None
        next_agent_state = None
        result = None
        log.debug("_handler_command_autosample_dump02")

        result = self._do_cmd_resp(InstrumentCommand.DUMP_SETTINGS_02)

        log.debug("DUMP_SETTINGS_02 response: %s", result)

        return (next_state, (next_agent_state, result))

