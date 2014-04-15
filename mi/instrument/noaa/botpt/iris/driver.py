"""
@package mi.instrument.noaa.iris.ooicore.driver
@file marine-integrations/mi/instrument/noaa/iris/ooicore/driver.py
@author David Everett, Pete Cable
@brief Driver for the ooicore
Release notes:

Driver for IRIS TILT on the RSN-BOTPT instrument (v.6)

"""

__author__ = 'David Everett'
__license__ = 'Apache 2.0'

import re
import time

from mi.core.log import get_logger


log = get_logger()

from mi.core.common import BaseEnum
from mi.core.instrument.instrument_fsm import InstrumentFSM
from mi.core.instrument.instrument_driver import SingleConnectionInstrumentDriver
from mi.core.instrument.instrument_driver import DriverEvent
from mi.core.instrument.instrument_driver import DriverProtocolState
from mi.core.instrument.instrument_driver import DriverParameter
from mi.core.instrument.instrument_driver import ResourceAgentState
from mi.core.instrument.data_particle import DataParticle
from mi.core.instrument.data_particle import DataParticleKey
from mi.core.instrument.chunker import StringChunker
from mi.instrument.noaa.botpt.driver import BotptProtocol
from mi.instrument.noaa.botpt.driver import BotptStatus01Particle
from mi.instrument.noaa.botpt.driver import BotptStatus02ParticleKey
from mi.instrument.noaa.botpt.driver import BotptStatus02Particle
from mi.instrument.noaa.botpt.driver import NEWLINE

from mi.core.exceptions import InstrumentProtocolException
from mi.core.exceptions import InstrumentTimeoutException
from mi.core.exceptions import SampleException

###
#    Driver Constant Definitions
###

IRIS_STRING = 'IRIS,'
IRIS_COMMAND_STRING = '*9900XY'
IRIS_DATA_ON = 'C2'  # turns on continuous data
IRIS_DATA_OFF = 'C-OFF'  # turns off continuous data
IRIS_DUMP_01 = '-DUMP-SETTINGS'  # outputs current settings
IRIS_DUMP_02 = '-DUMP2'  # outputs current extended settings


class ProtocolState(BaseEnum):
    """
    Instrument protocol states
    """
    UNKNOWN = DriverProtocolState.UNKNOWN
    COMMAND = DriverProtocolState.COMMAND
    AUTOSAMPLE = DriverProtocolState.AUTOSAMPLE
    DIRECT_ACCESS = DriverProtocolState.DIRECT_ACCESS


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
    START_DIRECT = DriverEvent.START_DIRECT
    EXECUTE_DIRECT = DriverEvent.EXECUTE_DIRECT
    STOP_DIRECT = DriverEvent.STOP_DIRECT


class Capability(BaseEnum):
    """
    Protocol events that should be exposed to users (subset of above).
    """
    GET = ProtocolEvent.GET
    SET = ProtocolEvent.SET
    START_AUTOSAMPLE = ProtocolEvent.START_AUTOSAMPLE
    STOP_AUTOSAMPLE = ProtocolEvent.STOP_AUTOSAMPLE
    ACQUIRE_STATUS = ProtocolEvent.ACQUIRE_STATUS


class InstrumentCommand(BaseEnum):
    """
    Instrument command strings
    """
    DATA_ON = IRIS_STRING + IRIS_COMMAND_STRING + IRIS_DATA_ON  # turns on continuous data
    DATA_OFF = IRIS_STRING + IRIS_COMMAND_STRING + IRIS_DATA_OFF  # turns off continuous data
    DUMP_SETTINGS_01 = IRIS_STRING + IRIS_COMMAND_STRING + IRIS_DUMP_01  # outputs current settings
    DUMP_SETTINGS_02 = IRIS_STRING + IRIS_COMMAND_STRING + IRIS_DUMP_02  # outputs current extended settings


###############################################################################
# Data Particles
###############################################################################

class DataParticleType(BaseEnum):
    IRIS_PARSED = 'botpt_iris_sample'
    IRIS_STATUS1 = 'botpt_iris_status1'
    IRIS_STATUS2 = 'botpt_iris_status2'


class IRISDataParticleKey(BaseEnum):
    SENSOR_ID = "sensor_id"
    TIME = "date_time_string"
    X_TILT = "iris_x_tilt"
    Y_TILT = "iris_y_tilt"
    TEMP = "temperature"
    SN = "serial_number"


class IRISDataParticle(DataParticle):
    """
    Routines for parsing raw data into a data particle structure. Override
    the building of values, and the rest should come along for free.

    Sample:
       IRIS,2013/05/29 00:25:36, -0.0885, -0.7517,28.49,N8642
       IRIS,2013/05/29 00:25:34, -0.0882, -0.7524,28.45,N8642       
    Format:
       IIII,YYYY/MM/DD hh:mm:ss,x.xxxx,y.yyyy,tt.tt,sn

        ID = IIII = IRIS
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
    _data_particle_type = DataParticleType.IRIS_PARSED
    _compiled_regex = None

    @staticmethod
    def regex():
        """
        Regular expression to match a sample pattern
        @return: regex string
        """
        pattern = r'IRIS,'  # pattern starts with IRIS '
        pattern += r'(.*),'  # 1 time
        pattern += r'( -*[.0-9]+),'  # 2 x-tilt
        pattern += r'( -*[.0-9]+),'  # 3 y-tilt
        pattern += r'(.*),'  # 4 temp
        pattern += r'(.*)'  # 5 serial number
        pattern += NEWLINE
        return pattern

    @staticmethod
    def regex_compiled():
        """
        get the compiled regex pattern
        @return: compiled re
        """
        if IRISDataParticle._compiled_regex is None:
            IRISDataParticle._compiled_regex = re.compile(IRISDataParticle.regex())
        return IRISDataParticle._compiled_regex

    def _build_parsed_values(self):
        """
        Take something in the autosample/TS format and split it into
        C, T, and D values (with appropriate tags)
        
        @throws SampleException If there is a problem with sample creation
        """
        match = IRISDataParticle.regex_compiled().match(self.raw_data)

        if not match:
            raise SampleException("No regex match of parsed sample data: [%s]" %
                                  self.raw_data)

        try:
            iris_time = match.group(1)
            timestamp = time.strptime(iris_time, "%Y/%m/%d %H:%M:%S")
            self.set_internal_timestamp(unix_time=time.mktime(timestamp))
            x_tilt = float(match.group(2))
            y_tilt = float(match.group(3))
            temperature = float(match.group(4))
            sn = str(match.group(5))

        except ValueError:
            raise SampleException("ValueError while converting data: [%s]" % self.raw_data)

        result = [
            {DataParticleKey.VALUE_ID: IRISDataParticleKey.SENSOR_ID,
             DataParticleKey.VALUE: 'IRIS'},
            {DataParticleKey.VALUE_ID: IRISDataParticleKey.TIME,
             DataParticleKey.VALUE: iris_time},
            {DataParticleKey.VALUE_ID: IRISDataParticleKey.X_TILT,
             DataParticleKey.VALUE: x_tilt},
            {DataParticleKey.VALUE_ID: IRISDataParticleKey.Y_TILT,
             DataParticleKey.VALUE: y_tilt},
            {DataParticleKey.VALUE_ID: IRISDataParticleKey.TEMP,
             DataParticleKey.VALUE: temperature},
            {DataParticleKey.VALUE_ID: IRISDataParticleKey.SN,
             DataParticleKey.VALUE: sn}
        ]

        return result


###############################################################################
# Status Particles
###############################################################################
class IRISStatus01Particle(BotptStatus01Particle):
    _data_particle_type = DataParticleType.IRIS_STATUS1


class IRISStatus02ParticleKey(BotptStatus02ParticleKey):
    CONTROL = 'iris_control'
    XPOS_RELAY_THRESHOLD = 'iris_xpos_relay_threshold'
    XNEG_RELAY_THRESHOLD = 'iris_xneg_relay_threshold'
    YPOS_RELAY_THRESHOLD = 'iris_ypos_relay_threshold'
    YNEG_RELAY_THRESHOLD = 'iris_yneg_relay_threshold'
    RELAY_HYSTERESIS = 'iris_relay_hysteresis'
    DAC_SCALE_FACTOR = 'iris_dac_output_scale_factor'
    DAC_SCALE_UNITS = 'iris_dac_output_scale_units'
    SAMPLE_STORAGE_CAPACITY = 'iris_sample_storage_capacity'
    BAE_SCALE_FACTOR = 'iris_bae_scale_factor'
    BAE_SCALE_FACTOR_UNITS = 'iris_bae_scale_factor_units'


# noinspection PyMethodMayBeStatic
class IRISStatus02Particle(BotptStatus02Particle):
    _data_particle_type = DataParticleType.IRIS_STATUS2
    # Example of output from DUMP2 command:
    # IRIS/LILY Common items (handled in base class):
    # IRIS,2013/06/12 23:55:09,*01: TBias: 8.85
    # IRIS,2013/06/12 23:55:09,*Above 0.00(KZMinTemp): kz[0]=           0, kz[1]=           0
    # IRIS,2013/06/12 18:04:01,*Below 0.00(KZMinTemp): kz[2]=           0, kz[3]=           0
    # IRIS,2013/06/12 18:04:01,*01: ADCDelay:  310
    # IRIS,2013/06/12 18:04:01,*01: PCA Model: 90009-01
    # IRIS,2013/06/12 18:04:01,*01: Firmware Version: 5.2 Rev N
    # IRIS,2013/06/12 18:04:01,*01: X Ch Gain= 1.0000, Y Ch Gain= 1.0000, Temperature Gain= 1.0000
    # IRIS,2013/06/12 18:04:01,*01: Output Mode: Degrees
    # IRIS,2013/06/12 18:04:01,*01: Calibration performed in Degrees
    # IRIS,2013/06/12 18:04:01,*01: Using RS232
    # IRIS,2013/06/12 18:04:01,*01: Real Time Clock: Not Installed
    # IRIS,2013/06/12 18:04:01,*01: Use RTC for Timing: No
    # IRIS,2013/06/12 18:04:01,*01: External Flash Capacity: 0 Bytes(Not Installed)
    # IRIS,2013/06/12 18:04:01,*01: Calibration method: Dynamic
    # IRIS,2013/06/12 18:04:01,*01: Positive Limit=26.25   Negative Limit=-26.25
    # IRIS,2013/06/12 18:04:02,*01: Calibration Points:025  X: Disabled  Y: Disabled
    # IRIS,2013/06/12 18:04:02,*01: Biaxial Sensor Type (0)
    # IRIS,2013/06/12 18:04:02,*01: ADC: 12-bit (internal)

    # IRIS unique items:
    # IRIS,2013/06/12 18:04:01,*01: Control: Off
    # IRIS,2013/06/12 18:04:01,*01: Relay Thresholds:
    # IRIS,2013/06/12 18:04:01,*01:   Xpositive= 1.0000   Xnegative=-1.0000
    # IRIS,2013/06/12 18:04:01,*01:   Ypositive= 1.0000   Ynegative=-1.0000
    # IRIS,2013/06/12 18:04:01,*01: Relay Hysteresis:
    # IRIS,2013/06/12 18:04:01,*01:   Hysteresis= 0.0000
    # IRIS,2013/06/12 18:04:02,*01: DAC Output Scale Factor: 0.10 Volts/Degree
    # IRIS,2013/06/12 18:04:02,*01: Total Sample Storage Capacity: 372
    # IRIS,2013/06/12 18:04:02,*01: BAE Scale Factor:  2.88388 (arcseconds/bit)

    _encoders = BotptStatus02Particle._encoders
    _encoders.update({
        IRISStatus02ParticleKey.CONTROL: str,
        IRISStatus02ParticleKey.DAC_SCALE_UNITS: str,
        IRISStatus02ParticleKey.SAMPLE_STORAGE_CAPACITY: int,
        IRISStatus02ParticleKey.BAE_SCALE_FACTOR_UNITS: str,
    })

    @classmethod
    def _regex_multiline(cls):
        sub_dict = {
            'float': cls.floating_point_num,
            'four_floats': cls.four_floats,
            'six_floats': cls.six_floats,
            'int': cls.integer,
            'word': cls.word,
        }
        regex_dict = {
            IRISStatus02ParticleKey.CONTROL: r'Control: %(word)s' % sub_dict,
            IRISStatus02ParticleKey.XPOS_RELAY_THRESHOLD: r'Xpositive=\s*%(float)s' % sub_dict,
            IRISStatus02ParticleKey.XNEG_RELAY_THRESHOLD: r'Xnegative=\s*%(float)s' % sub_dict,
            IRISStatus02ParticleKey.YPOS_RELAY_THRESHOLD: r'Ypositive=\s*%(float)s' % sub_dict,
            IRISStatus02ParticleKey.YNEG_RELAY_THRESHOLD: r'Ynegative=\s*%(float)s' % sub_dict,
            IRISStatus02ParticleKey.RELAY_HYSTERESIS: r'Hysteresis=\s*%(float)s' % sub_dict,
            IRISStatus02ParticleKey.DAC_SCALE_FACTOR: r'DAC Output Scale Factor: %(float)s' % sub_dict,
            IRISStatus02ParticleKey.DAC_SCALE_UNITS: r'DAC Output Scale Factor: -?\d*\.\d* %(word)s' % sub_dict,
            IRISStatus02ParticleKey.SAMPLE_STORAGE_CAPACITY: r'Total Sample Storage Capacity: %(int)s' % sub_dict,
            IRISStatus02ParticleKey.BAE_SCALE_FACTOR: r'BAE Scale Factor:\s*%(float)s' % sub_dict,
            IRISStatus02ParticleKey.BAE_SCALE_FACTOR_UNITS: r'BAE Scale Factor:.*\(%(word)s\)' % sub_dict,
        }
        regex_dict.update(BotptStatus02Particle._regex_multiline())
        return regex_dict


###############################################################################
# Driver
###############################################################################

# noinspection PyMethodMayBeStatic
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
        return DriverParameter.list()

    ########################################################################
    # Protocol builder.
    ########################################################################

    def _build_protocol(self):
        """
        Construct the driver protocol state machine.
        """
        self._protocol = Protocol(BaseEnum, NEWLINE, self._driver_event)


###########################################################################
# Protocol
###########################################################################

# noinspection PyMethodMayBeStatic, PyUnusedLocal
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

        # Add event handlers for protocol state machine.
        handlers = {
            ProtocolState.UNKNOWN: [
                (ProtocolEvent.ENTER, self._handler_unknown_enter),
                (ProtocolEvent.EXIT, self._handler_unknown_exit),
                (ProtocolEvent.DISCOVER, self._handler_unknown_discover),
            ],
            ProtocolState.AUTOSAMPLE: [
                (ProtocolEvent.ENTER, self._handler_autosample_enter),
                (ProtocolEvent.EXIT, self._handler_autosample_exit),
                (ProtocolEvent.STOP_AUTOSAMPLE, self._handler_autosample_stop_autosample),
                (ProtocolEvent.ACQUIRE_STATUS, self._handler_command_autosample_acquire_status),
                (ProtocolEvent.START_DIRECT, self._handler_command_start_direct)
            ],
            ProtocolState.COMMAND: [
                (ProtocolEvent.ENTER, self._handler_command_enter),
                (ProtocolEvent.EXIT, self._handler_command_exit),
                (ProtocolEvent.GET, self._handler_command_get),
                (ProtocolEvent.SET, self._handler_command_set),
                (ProtocolEvent.ACQUIRE_STATUS, self._handler_command_autosample_acquire_status),
                (ProtocolEvent.START_AUTOSAMPLE, self._handler_command_start_autosample),
                (ProtocolEvent.START_DIRECT, self._handler_command_start_direct)
            ],
            ProtocolState.DIRECT_ACCESS: [
                (ProtocolEvent.ENTER, self._handler_direct_access_enter),
                (ProtocolEvent.EXIT, self._handler_direct_access_exit),
                (ProtocolEvent.EXECUTE_DIRECT, self._handler_direct_access_execute_direct),
                (ProtocolEvent.STOP_DIRECT, self._handler_direct_access_stop_direct),
            ]
        }

        for state in handlers:
            for event, handler in handlers[state]:
                self._protocol_fsm.add_handler(state, event, handler)

        # Add build handlers for device commands.
        for command in InstrumentCommand.list():
            self._add_build_handler(command, self._build_command)

        # Add response handlers for device commands.
        for command in InstrumentCommand.list():
            self._add_response_handler(command, self._resp_handler)

        self._build_command_dict()
        self._build_param_dict()

        # Start state machine in UNKNOWN state.
        self._protocol_fsm.start(ProtocolState.UNKNOWN)

        self._chunker = StringChunker(Protocol.sieve_function)

        # set up the regexes now so we don't have to do it repeatedly
        self.data_regex = IRISDataParticle.regex_compiled()
        self.status_01_regex = IRISStatus01Particle.regex_compiled()
        self.status_02_regex = IRISStatus02Particle.regex_compiled()
        self._last_data_timestamp = 0
        self._filter_string = IRIS_STRING

    @staticmethod
    def sieve_function(raw_data):
        """
        The method that splits samples
        """
        matchers = []
        return_list = []

        matchers.append(IRISDataParticle.regex_compiled())
        matchers.append(IRISStatus01Particle.regex_compiled())
        matchers.append(IRISStatus02Particle.regex_compiled())

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

    def _build_command_dict(self):
        """
        Populate the command dictionary with command.
        """
        self._cmd_dict.add(Capability.START_AUTOSAMPLE, display_name="start autosample")
        self._cmd_dict.add(Capability.STOP_AUTOSAMPLE, display_name="stop autosample")
        self._cmd_dict.add(Capability.ACQUIRE_STATUS, display_name="acquire status")

    def _build_param_dict(self):
        pass

    def _got_chunk(self, chunk, timestamp):
        """
        Extract particles from our chunks
        """

        log.debug("_got_chunk_: %r", chunk)
        if self._extract_sample(IRISDataParticle, self.data_regex, chunk, timestamp) or \
                self._extract_sample(IRISStatus01Particle, self.status_01_regex, chunk, timestamp) or \
                self._extract_sample(IRISStatus02Particle, self.status_02_regex, chunk, timestamp):
            return
        else:
            raise InstrumentProtocolException('Unhandled chunk %r' % chunk)

    def _resp_handler(self, response, prompt):
        log.debug('_resp_handler - response: %r prompt: %r', response, prompt)
        return response

    ########################################################################
    # Unknown handlers.
    ########################################################################

    def _handler_unknown_discover(self, *args, **kwargs):
        """
        Discover current state
        @retval (next_state, result)
        """
        # attempt to find a data particle.  If found, go to AUTOSAMPLE, else COMMAND
        try:
            # clear out the buffers to ensure we are getting new data
            # this is necessary when discovering out of direct access.
            self._promptbuf = ''
            self._linebuf = ''
            result = self._get_response(timeout=2, response_regex=IRISDataParticle.regex_compiled())
            next_state = ProtocolState.AUTOSAMPLE
            next_agent_state = ResourceAgentState.STREAMING
        except InstrumentTimeoutException:
            next_state = ProtocolState.COMMAND
            next_agent_state = ResourceAgentState.IDLE
        return next_state, next_agent_state

    ########################################################################
    # Autosample handlers.
    ########################################################################

    def _handler_autosample_stop_autosample(self, *args, **kwargs):
        """
        Turn the iris data off
        """
        return self._handler_command_generic(InstrumentCommand.DATA_OFF,
                                             ProtocolState.COMMAND, ResourceAgentState.COMMAND,
                                             expected_prompt=IRIS_DATA_OFF)

    ########################################################################
    # Command handlers.
    ########################################################################

    def _handler_command_start_autosample(self, *args, **kwargs):
        """
        Turn the iris data on
        """
        return self._handler_command_generic(InstrumentCommand.DATA_ON,
                                             ProtocolState.AUTOSAMPLE, ResourceAgentState.STREAMING,
                                             expected_prompt=IRIS_DATA_ON)

    ########################################################################
    # Handlers common to Command and Autosample States.
    ########################################################################

    def _handler_command_autosample_acquire_status(self, *args, **kwargs):
        """
        Get device status
        """
        log.debug("_handler_command_autosample_acquire_status")
        result1 = self._handler_command_generic(InstrumentCommand.DUMP_SETTINGS_01,
                                                None, None, expected_prompt=IRIS_DUMP_01)
        result2 = self._handler_command_generic(InstrumentCommand.DUMP_SETTINGS_02,
                                                None, None, expected_prompt=IRIS_DUMP_02)
        return None, (None, '%s %s' % (result1[1][1], result2[1][1]))
