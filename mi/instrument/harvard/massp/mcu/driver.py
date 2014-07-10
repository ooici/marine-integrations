"""
@package mi.instrument.harvard.massp.mcu.driver
@file marine-integrations/mi/instrument/harvard/massp/mcu/driver.py
@author Peter Cable
@brief Driver for the mcu
Release notes:

MCU driver for the MASSP in-situ mass spectrometer
"""

import re
import functools

from mi.core.exceptions import SampleException, InstrumentParameterException, InstrumentTimeoutException, \
    InstrumentProtocolException
from mi.core.instrument.driver_dict import DriverDictKey
from mi.core.instrument.protocol_param_dict import ParameterDictVisibility, ParameterDictType
from mi.core.log import get_logger
from mi.core.log import get_logging_metaclass
from mi.core.common import BaseEnum, Units, Prefixes
from mi.core.instrument.instrument_protocol import CommandResponseInstrumentProtocol
from mi.core.instrument.instrument_fsm import ThreadSafeFSM
from mi.core.instrument.instrument_driver import SingleConnectionInstrumentDriver
from mi.core.instrument.instrument_driver import DriverEvent
from mi.core.instrument.instrument_driver import DriverAsyncEvent
from mi.core.instrument.instrument_driver import DriverProtocolState
from mi.core.instrument.instrument_driver import DriverParameter
from mi.core.instrument.instrument_driver import ResourceAgentState
from mi.core.instrument.data_particle import DataParticle
from mi.core.instrument.data_particle import CommonDataParticleType
from mi.core.instrument.chunker import StringChunker
from mi.instrument.harvard.massp.common import MASSP_STATE_ERROR, MASSP_CLEAR_ERROR


__author__ = 'Peter Cable'
__license__ = 'Apache 2.0'

log = get_logger()

METALOGGER = get_logging_metaclass()

# newline.
NEWLINE = '\r'


class DataParticleType(BaseEnum):
    """
    Data particle types produced by this driver
    """
    RAW = CommonDataParticleType.RAW
    MCU_STATUS = 'massp_mcu_status'


class ProtocolState(BaseEnum):
    """
    Instrument protocol states
    """
    UNKNOWN = DriverProtocolState.UNKNOWN
    COMMAND = DriverProtocolState.COMMAND
    DIRECT_ACCESS = DriverProtocolState.DIRECT_ACCESS
    CALIBRATE = DriverProtocolState.CALIBRATE
    START1 = 'PROTOCOL_STATE_START1'
    WAITING_TURBO = 'PROTOCOL_STATE_WAITING_TURBO'
    START2 = 'PROTOCOL_STATE_START2'
    WAITING_RGA = 'PROTOCOL_STATE_WAITING_RGA'
    SAMPLE = 'PROTOCOL_STATE_SAMPLE'
    STOPPING = 'PROTOCOL_STATE_STOPPING'
    REGEN = 'PROTOCOL_STATE_REGEN'
    ERROR = MASSP_STATE_ERROR


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
    EXECUTE_DIRECT = DriverEvent.EXECUTE_DIRECT
    START1 = 'PROTOCOL_EVENT_START1'
    START1_COMPLETE = 'PROTOCOL_EVENT_START1_COMPLETE'
    START2 = 'PROTOCOL_EVENT_START2'
    START2_COMPLETE = 'PROTOCOL_EVENT_START2_COMPLETE'
    SAMPLE = 'PROTOCOL_EVENT_SAMPLE'
    SAMPLE_COMPLETE = 'PROTOCOL_EVENT_SAMPLE_COMPLETE'
    NAFREG = 'PROTOCOL_EVENT_NAFREG'
    IONREG = 'PROTOCOL_EVENT_IONREG'
    CALIBRATE = DriverEvent.CALIBRATE
    CALIBRATE_COMPLETE = 'PROTOCOL_EVENT_CALIBRATE_COMPLETE'
    ERROR = 'PROTOCOL_EVENT_ERROR'
    STANDBY = 'PROTOCOL_EVENT_STANDBY'
    CLEAR = MASSP_CLEAR_ERROR
    POWEROFF = 'PROTOCOL_EVENT_POWEROFF'


class Capability(BaseEnum):
    """
    Protocol events that should be exposed to users (subset of above).
    """
    START1 = ProtocolEvent.START1
    START2 = ProtocolEvent.START2
    SAMPLE = ProtocolEvent.SAMPLE
    CALIBRATE = ProtocolEvent.CALIBRATE
    NAFREG = ProtocolEvent.NAFREG
    IONREG = ProtocolEvent.IONREG
    STANDBY = ProtocolEvent.STANDBY
    CLEAR = ProtocolEvent.CLEAR
    POWEROFF = ProtocolEvent.POWEROFF


class Parameter(DriverParameter):
    """
    Device specific parameters.
    """
    TELEGRAM_INTERVAL = 'mcu_telegram_interval'
    ONE_MINUTE = 'mcu_one_minute'
    SAMPLE_TIME = 'mcu_sample_time'
    ERROR_REASON = 'mcu_error_reason'

    @classmethod
    def reverse_dict(cls):
        return dict((v, k) for k, v in cls.dict().iteritems())


class ParameterConstraint(BaseEnum):
    """
    Constraints for parameters
    (type, min, max)
    """
    TELEGRAM_INTERVAL = (int, 1, 30000)
    ONE_MINUTE = (int, 1, 99999)
    SAMPLE_TIME = (int, 1, 99)


class Prompt(BaseEnum):
    """
    Device i/o prompts..
    """
    OK = 'M OK'
    ERROR = 'M EN'
    START1 = "M START1 finished"
    START2 = "M START2 finished"
    SAMPLE_START = "M Sampling time set to"
    SAMPLE_FINISHED = "M Sampling Finished"
    STANDBY = "M STANDBY mode activated"
    BEAT = "M BEAT"
    POWEROFF = "M POWEROFF mode activated"
    CAL_FINISHED = "M CAL end"
    NAFREG_FINISHED = "M Nafion Reg finished"
    IONREG_FINISHED = "M Ion Reg finished"
    ABORTED = "M ABORTED"
    IN_SEQUENCE = 'E001 already in sequence'
    SET_MINUTE = 'M set minutes to'
    ONLINE = 'M MainModule Online'
    NAFTEMP_NOT_ACHIEVED = 'E005 Nafion regeneration: temp not achieved'
    IONTEMP_NOT_ACHIEVED = 'E008 Ion regeneration: temp not achieved'


class InstrumentCommand(BaseEnum):
    """
    Instrument command strings
    """
    BEAT = 'U BEAT'
    DATA = 'U ?DATA'
    START1 = 'U ASTART1'
    START2 = 'U ASTART2'
    SAMPLE = 'U ASAMPLE'
    STANDBY = 'U ASTANDBY'
    POWEROFF = 'U APOWEROFF'
    CAL = 'U ACAL9'
    NAFREG = 'U ANAFREG3'
    IONREG = 'U AIONREG3'
    ABORT = 'U AABORT'
    RESETP = 'U SETRESETP'
    SET_TELEGRAM_INTERVAL = 'U SETRATEDLR'
    SET_MINUTE = 'U SETMINUTE'
    SET_WATCHDOG = 'U SETWDTON'


###############################################################################
# Data Particles
###############################################################################


class McuStatusParticleKey(BaseEnum):
    """
    Keys for the MCU Status Particle
    """
    RGA_CURRENT = 'massp_rga_current'
    TURBO_CURRENT = 'massp_turbo_current'
    HEATER_CURRENT = 'massp_heater_current'
    ROUGHING_CURRENT = 'massp_roughing_current'
    FAN_CURRENT = 'massp_fan_current'
    SBE_CURRENT = 'massp_sbe_current'
    CONVERTER_24V_MAIN = 'massp_converter_24v_main'
    CONVERTER_12V_MAIN = 'massp_converter_12v_main'
    CONVERTER_24V_SEC = 'massp_converter_24v_sec'
    CONVERTER_12V_SEC = 'massp_converter_12v_sec'
    VALVE_CURRENT = 'massp_valve_current'

    PRESSURE_P1 = 'massp_pressure_p1'
    PRESSURE_P2 = 'massp_pressure_p2'
    PRESSURE_P3 = 'massp_pressure_p3'
    PRESSURE_P4 = 'massp_pressure_p4'

    HOUSING_PRESSURE = 'massp_housing_pressure'
    HOUSING_HUMIDITY = 'massp_housing_humidity'
    TEMP_MAIN_CONTROL = 'massp_temp_main_control'
    TEMP_MAIN_ROUGH = 'massp_temp_main_rough'
    TEMP_SEC_ROUGH = 'massp_temp_sec_rough'
    TEMP_MAIN_24V = 'massp_temp_main_24v'
    TEMP_SEC_24V = 'massp_temp_sec_24v'
    TEMP_ANALYZER = 'massp_temp_analyzer'
    TEMP_NAFION = 'massp_temp_nafion'
    TEMP_ION = 'massp_temp_ion'

    PH_METER = 'massp_ph_meter_value'
    INLET_TEMP = 'massp_inlet_temp_value'

    PH_STATUS = 'massp_ph_meter_status'
    INLET_TEMP_STATUS = 'massp_inlet_temp_status'

    POWER_RELAY_TURBO = 'massp_power_relay_turbo'
    POWER_RELAY_RGA = 'massp_power_relay_rga'
    POWER_RELAY_MAIN_ROUGH = 'massp_power_relay_main_rough'
    POWER_RELAY_SEC_ROUGH = 'massp_power_relay_sec_rough'
    POWER_RELAY_FAN1 = 'massp_power_relay_fan1'
    POWER_RELAY_FAN2 = 'massp_power_relay_fan2'
    POWER_RELAY_FAN3 = 'massp_power_relay_fan3'
    POWER_RELAY_FAN4 = 'massp_power_relay_fan4'
    POWER_RELAY_AUX2 = 'massp_power_relay_aux2'
    POWER_RELAY_PH = 'massp_power_relay_ph'
    POWER_RELAY_PUMP = 'massp_power_relay_pump'
    POWER_RELAY_HEATERS = 'massp_power_relay_heaters'
    POWER_RELAY_AUX1 = 'massp_power_relay_aux1'

    SAMPLE_VALVE1 = 'massp_sample_valve1'
    SAMPLE_VALVE2 = 'massp_sample_valve2'
    SAMPLE_VALVE3 = 'massp_sample_valve3'
    SAMPLE_VALVE4 = 'massp_sample_valve4'

    GROUND_RELAY_STATUS = 'massp_ground_relay_status'
    EXTERNAL_VALVE1_STATUS = 'massp_external_valve1_status'
    EXTERNAL_VALVE2_STATUS = 'massp_external_valve2_status'
    EXTERNAL_VALVE3_STATUS = 'massp_external_valve3_status'
    EXTERNAL_VALVE4_STATUS = 'massp_external_valve4_status'
    CAL_BAG1_MINUTES = 'massp_cal_bag1_minutes'
    CAL_BAG2_MINUTES = 'massp_cal_bag2_minutes'
    CAL_BAG3_MINUTES = 'massp_cal_bag3_minutes'

    NAFION_HEATER_STATUS = 'massp_nafion_heater_status'
    NAFION_HEATER1_POWER = 'massp_nafion_heater1_power'
    NAFION_HEATER2_POWER = 'massp_nafion_heater2_power'
    NAFION_CORE_TEMP = 'massp_nafion_core_temp'
    NAFION_ELAPSED_TIME = 'massp_nafion_elapsed_time'
    ION_CHAMBER_STATUS = 'massp_ion_chamber_heater_status'
    ION_CHAMBER_HEATER1_STATUS = 'massp_ion_chamber_heater1_status'
    ION_CHAMBER_HEATER2_STATUS = 'massp_ion_chamber_heater2_status'


class McuDataParticle(DataParticle):
    """
    DATA,POW:Pow0:Pow1:Pow2:Pow3:Pow4:Pow5:Pow6:Pow7:Pow8:Pow9:Pow10,
    PRE:p1:p2:p3:p4,
    INT:int1:int2:int3:int4:int5:int6:int7:int8:int9:int10,
    EXT:e1:e2:e3,
    EXTST:es1:es2:es3,
    POWST:ps0:ps1:ps2:ps3:ps4:ps5:ps6:ps7:ps8:ps9:ps10:ps11:ps12,
    SOLST:sv1:sv2:sv3:sv4:sv5:sv6,
    CAL:sv0:sv1:sv2:sv3:sv4:ct1:ct2:ct3:ct4,
    HEAT:x0:x1:x2:x3:x4:x5:x6:x7:x8:x9,
    ENDDATA

    DATA,POW:4967:4983:1994:4978:4978:4973:1998:5124:2003:4994:6794,PRE:955:938:957:955,
    INT:50:35:17:20:20:21:20:20:20:20:20,EXT:2.00:0.00:-1.00,EXTST:1:0:0,POWST:0:0:0:0:1:0:0:0:0:0:0:0:0,
    SOLST:0:0:0:1:0:0,CAL:0:0:0:0:0:10:10:1:0,HEAT:0:0:0:20:0:-1:-1:-1:-1:-1,ENDDATA
    """
    __metaclass__ = METALOGGER
    _data_particle_type = DataParticleType.MCU_STATUS
    _compiled = None

    @staticmethod
    def regex():
        """
        Regular expression to match a sample pattern
        @return: regex string
        """
        return 'DATA,.*?ENDDATA' + NEWLINE

    @staticmethod
    def regex_compiled():
        """
        get the compiled regex pattern
        @return: compiled re
        """
        if McuDataParticle._compiled is None:
            McuDataParticle._compiled = re.compile(McuDataParticle.regex())
        return McuDataParticle._compiled

    def _build_parsed_values(self):
        """
        Parse the data telegram from the MCU and generate a status particle.
        @return result , list of encoded values
        """
        # data fields are comma-delimited
        # the first and last segment contain labels only
        # data items are colon delimited, first field is a label only
        # all data items are integers, however, the external values
        # masquerade as floats, so we have to explicitly split on the '.'
        try:
            segments = [[x.split('.')[0] for x in row.split(':')[1:]] for row in self.raw_data.split(',')[1:-1]]

            powers, pressures, internals, externals, external_statuses, power_statuses, \
                solenoid_statuses, calibration_statuses, heater_statuses = segments

            for index, value in enumerate(calibration_statuses):
                if value == '':
                    calibration_statuses[index] = 0

            result = [
                self._encode_value(McuStatusParticleKey.RGA_CURRENT, powers[0], int),
                self._encode_value(McuStatusParticleKey.TURBO_CURRENT, powers[1], int),
                self._encode_value(McuStatusParticleKey.HEATER_CURRENT, powers[2], int),
                self._encode_value(McuStatusParticleKey.ROUGHING_CURRENT, powers[3], int),
                self._encode_value(McuStatusParticleKey.FAN_CURRENT, powers[4], int),
                self._encode_value(McuStatusParticleKey.SBE_CURRENT, powers[5], int),
                self._encode_value(McuStatusParticleKey.CONVERTER_24V_MAIN, powers[6], int),
                self._encode_value(McuStatusParticleKey.CONVERTER_12V_MAIN, powers[7], int),
                self._encode_value(McuStatusParticleKey.CONVERTER_24V_SEC, powers[8], int),
                self._encode_value(McuStatusParticleKey.CONVERTER_12V_SEC, powers[9], int),
                self._encode_value(McuStatusParticleKey.VALVE_CURRENT, powers[10], int),

                self._encode_value(McuStatusParticleKey.PRESSURE_P1, pressures[0], int),
                self._encode_value(McuStatusParticleKey.PRESSURE_P2, pressures[1], int),
                self._encode_value(McuStatusParticleKey.PRESSURE_P3, pressures[2], int),
                self._encode_value(McuStatusParticleKey.PRESSURE_P4, pressures[3], int),

                self._encode_value(McuStatusParticleKey.HOUSING_PRESSURE, internals[0], int),
                self._encode_value(McuStatusParticleKey.HOUSING_HUMIDITY, internals[1], int),
                self._encode_value(McuStatusParticleKey.TEMP_MAIN_CONTROL, internals[2], int),
                self._encode_value(McuStatusParticleKey.TEMP_MAIN_ROUGH, internals[3], int),
                self._encode_value(McuStatusParticleKey.TEMP_SEC_ROUGH, internals[4], int),
                self._encode_value(McuStatusParticleKey.TEMP_MAIN_24V, internals[5], int),
                self._encode_value(McuStatusParticleKey.TEMP_SEC_24V, internals[6], int),
                self._encode_value(McuStatusParticleKey.TEMP_ANALYZER, internals[7], int),
                self._encode_value(McuStatusParticleKey.TEMP_NAFION, internals[8], int),
                self._encode_value(McuStatusParticleKey.TEMP_ION, internals[9], int),

                self._encode_value(McuStatusParticleKey.PH_METER, externals[0], int),
                self._encode_value(McuStatusParticleKey.INLET_TEMP, externals[1], int),

                self._encode_value(McuStatusParticleKey.PH_STATUS, external_statuses[0], int),
                self._encode_value(McuStatusParticleKey.INLET_TEMP_STATUS, external_statuses[1], int),

                self._encode_value(McuStatusParticleKey.POWER_RELAY_TURBO, power_statuses[0], int),
                self._encode_value(McuStatusParticleKey.POWER_RELAY_RGA, power_statuses[1], int),
                self._encode_value(McuStatusParticleKey.POWER_RELAY_MAIN_ROUGH, power_statuses[2], int),
                self._encode_value(McuStatusParticleKey.POWER_RELAY_SEC_ROUGH, power_statuses[3], int),
                self._encode_value(McuStatusParticleKey.POWER_RELAY_FAN1, power_statuses[4], int),
                self._encode_value(McuStatusParticleKey.POWER_RELAY_FAN2, power_statuses[5], int),
                self._encode_value(McuStatusParticleKey.POWER_RELAY_FAN3, power_statuses[6], int),
                self._encode_value(McuStatusParticleKey.POWER_RELAY_FAN4, power_statuses[7], int),
                self._encode_value(McuStatusParticleKey.POWER_RELAY_AUX2, power_statuses[8], int),
                self._encode_value(McuStatusParticleKey.POWER_RELAY_PH, power_statuses[9], int),
                self._encode_value(McuStatusParticleKey.POWER_RELAY_PUMP, power_statuses[10], int),
                self._encode_value(McuStatusParticleKey.POWER_RELAY_HEATERS, power_statuses[11], int),
                self._encode_value(McuStatusParticleKey.POWER_RELAY_AUX1, power_statuses[12], int),

                self._encode_value(McuStatusParticleKey.SAMPLE_VALVE1, solenoid_statuses[0], int),
                self._encode_value(McuStatusParticleKey.SAMPLE_VALVE2, solenoid_statuses[1], int),
                self._encode_value(McuStatusParticleKey.SAMPLE_VALVE3, solenoid_statuses[2], int),
                self._encode_value(McuStatusParticleKey.SAMPLE_VALVE4, solenoid_statuses[3], int),

                self._encode_value(McuStatusParticleKey.GROUND_RELAY_STATUS, calibration_statuses[0], int),
                self._encode_value(McuStatusParticleKey.EXTERNAL_VALVE1_STATUS, calibration_statuses[1], int),
                self._encode_value(McuStatusParticleKey.EXTERNAL_VALVE2_STATUS, calibration_statuses[2], int),
                self._encode_value(McuStatusParticleKey.EXTERNAL_VALVE3_STATUS, calibration_statuses[3], int),
                self._encode_value(McuStatusParticleKey.EXTERNAL_VALVE4_STATUS, calibration_statuses[4], int),
                self._encode_value(McuStatusParticleKey.CAL_BAG1_MINUTES, calibration_statuses[5], int),
                self._encode_value(McuStatusParticleKey.CAL_BAG2_MINUTES, calibration_statuses[6], int),
                self._encode_value(McuStatusParticleKey.CAL_BAG3_MINUTES, calibration_statuses[7], int),

                self._encode_value(McuStatusParticleKey.NAFION_HEATER_STATUS, heater_statuses[0], int),
                self._encode_value(McuStatusParticleKey.NAFION_HEATER1_POWER, heater_statuses[1], int),
                self._encode_value(McuStatusParticleKey.NAFION_HEATER2_POWER, heater_statuses[2], int),
                self._encode_value(McuStatusParticleKey.NAFION_CORE_TEMP, heater_statuses[3], int),
                self._encode_value(McuStatusParticleKey.NAFION_ELAPSED_TIME, heater_statuses[4], int),
                self._encode_value(McuStatusParticleKey.ION_CHAMBER_STATUS, heater_statuses[5], int),
                self._encode_value(McuStatusParticleKey.ION_CHAMBER_HEATER1_STATUS, heater_statuses[7], int),
                self._encode_value(McuStatusParticleKey.ION_CHAMBER_HEATER2_STATUS, heater_statuses[8], int)
            ]
        except IndexError, e:
            raise SampleException('Incomplete or corrupt data telegram received (%s)', e)
        except ValueError, e:
            raise SampleException('Incomplete or corrupt data telegram received (%s)', e)
        if self.get_encoding_errors():
            raise SampleException('Incomplete or corrupt data telegram received (%s)', self.get_encoding_errors())
        return result


###############################################################################
# Driver
###############################################################################

class InstrumentDriver(SingleConnectionInstrumentDriver):
    """
    InstrumentDriver subclass
    Subclasses SingleConnectionInstrumentDriver with connection state
    machine.
    """
    __metaclass__ = METALOGGER

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
        self._protocol = Protocol(Prompt, NEWLINE, self._driver_event)


###########################################################################
# Protocol
###########################################################################

# noinspection PyMethodMayBeStatic,PyUnusedLocal
class Protocol(CommandResponseInstrumentProtocol):
    """
    Instrument protocol class
    Subclasses CommandResponseInstrumentProtocol
    """
    __metaclass__ = METALOGGER

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
        self._protocol_fsm = ThreadSafeFSM(ProtocolState, ProtocolEvent,
                                           ProtocolEvent.ENTER, ProtocolEvent.EXIT)

        # Add event handlers for protocol state machine.

        handlers = {
            ProtocolState.UNKNOWN: [
                (ProtocolEvent.ENTER, self._handler_generic_enter),
                (ProtocolEvent.EXIT, self._handler_generic_exit),
                (ProtocolEvent.DISCOVER, self._handler_unknown_discover),
                (ProtocolEvent.ERROR, self._handler_error),
            ],
            ProtocolState.COMMAND: [
                (ProtocolEvent.ENTER, self._handler_command_enter),
                (ProtocolEvent.EXIT, self._handler_generic_exit),
                (ProtocolEvent.START_DIRECT, self._handler_command_start_direct),
                (ProtocolEvent.GET, self._handler_command_get),
                (ProtocolEvent.SET, self._handler_command_set),
                (ProtocolEvent.START1, self._handler_command_start1),
                (ProtocolEvent.NAFREG, self._handler_command_nafreg),
                (ProtocolEvent.IONREG, self._handler_command_ionreg),
                (ProtocolEvent.POWEROFF, self._handler_command_poweroff),
                (ProtocolEvent.ERROR, self._handler_error),
            ],
            ProtocolState.START1: [
                (ProtocolEvent.ENTER, self._handler_generic_enter),
                (ProtocolEvent.EXIT, self._handler_generic_exit),
                (ProtocolEvent.START1_COMPLETE, self._handler_start1_complete),
                (ProtocolEvent.STANDBY, self._handler_stop),
                (ProtocolEvent.ERROR, self._handler_error),
            ],
            ProtocolState.WAITING_TURBO: [
                (ProtocolEvent.ENTER, self._handler_generic_enter),
                (ProtocolEvent.EXIT, self._handler_generic_exit),
                (ProtocolEvent.STANDBY, self._handler_stop),
                (ProtocolEvent.START2, self._handler_waiting_turbo_start2),
                (ProtocolEvent.ERROR, self._handler_error),
            ],
            ProtocolState.START2: [
                (ProtocolEvent.ENTER, self._handler_generic_enter),
                (ProtocolEvent.EXIT, self._handler_generic_exit),
                (ProtocolEvent.START2_COMPLETE, self._handler_start2_complete),
                (ProtocolEvent.STANDBY, self._handler_stop),
                (ProtocolEvent.ERROR, self._handler_error),
            ],
            ProtocolState.WAITING_RGA: [
                (ProtocolEvent.ENTER, self._handler_generic_enter),
                (ProtocolEvent.EXIT, self._handler_generic_exit),
                (ProtocolEvent.STANDBY, self._handler_stop),
                (ProtocolEvent.SAMPLE, self._handler_waiting_rga_sample),
                (ProtocolEvent.CALIBRATE, self._handler_waiting_rga_cal),
                (ProtocolEvent.ERROR, self._handler_error),
            ],
            ProtocolState.SAMPLE: [
                (ProtocolEvent.ENTER, self._handler_generic_enter),
                (ProtocolEvent.EXIT, self._handler_generic_exit),
                (ProtocolEvent.SAMPLE_COMPLETE, self._handler_sample_complete),
                (ProtocolEvent.STANDBY, self._handler_stop),
                (ProtocolEvent.ERROR, self._handler_error),
            ],
            ProtocolState.CALIBRATE: [
                (ProtocolEvent.ENTER, self._handler_generic_enter),
                (ProtocolEvent.EXIT, self._handler_generic_exit),
                (ProtocolEvent.CALIBRATE_COMPLETE, self._handler_cal_complete),
                (ProtocolEvent.STANDBY, self._handler_stop),
                (ProtocolEvent.ERROR, self._handler_error),
            ],
            ProtocolState.STOPPING: [
                (ProtocolEvent.ENTER, self._handler_generic_enter),
                (ProtocolEvent.EXIT, self._handler_generic_exit),
                (ProtocolEvent.STANDBY, self._handler_stop),
                (ProtocolEvent.ERROR, self._handler_error),
            ],
            ProtocolState.REGEN: [
                (ProtocolEvent.ENTER, self._handler_generic_enter),
                (ProtocolEvent.EXIT, self._handler_generic_exit),
                (ProtocolEvent.STANDBY, self._handler_stop),
                (ProtocolEvent.ERROR, self._handler_error),
            ],
            ProtocolState.DIRECT_ACCESS: [
                (ProtocolEvent.ENTER, self._handler_direct_access_enter),
                (ProtocolEvent.EXIT, self._handler_generic_exit),
                (ProtocolEvent.STOP_DIRECT, self._handler_stop),
                (ProtocolEvent.EXECUTE_DIRECT, self._handler_direct_access_execute_direct),
            ],
            ProtocolState.ERROR: [
                (ProtocolEvent.ENTER, self._handler_generic_enter),
                (ProtocolEvent.EXIT, self._handler_generic_exit),
                (ProtocolEvent.STANDBY, self._handler_error_standby),
                (ProtocolEvent.CLEAR, self._handler_stop),
            ],
        }

        for state in handlers:
            for event, handler in handlers[state]:
                self._protocol_fsm.add_handler(state, event, handler)

        # response handlers
        for command in InstrumentCommand.list():
            self._add_response_handler(command, functools.partial(self._generic_response_handler, command=command))

        # Construct the parameter dictionary containing device parameters,
        # current parameter values, and set formatting functions.
        self._build_param_dict()
        self._build_command_dict()
        self._build_driver_dict()

        # Add build handlers for device commands.
        for command in InstrumentCommand.list():
            if command == InstrumentCommand.SET_TELEGRAM_INTERVAL:
                self._add_build_handler(command, self._build_telegram_interval_command)
            elif command == InstrumentCommand.SAMPLE:
                self._add_build_handler(command, self._build_sample_command)
            elif command == InstrumentCommand.SET_MINUTE:
                self._add_build_handler(command, self._build_set_minute_command)
            else:
                self._add_build_handler(command, self._build_simple_command)

        # State state machine in UNKNOWN state.
        self._protocol_fsm.start(ProtocolState.UNKNOWN)

        # commands sent sent to device to be filtered in responses for telnet DA
        self._sent_cmds = []

        self._chunker = StringChunker(Protocol.sieve_function)

        self.resetting = False

    @staticmethod
    def sieve_function(raw_data):
        """
        The method that splits samples
        @param raw_data - data to be searched
        """
        matchers = []
        return_list = []

        matchers.append(McuDataParticle.regex_compiled())
        matchers.append(re.compile(r'(M .*?)(?=\r)'))
        matchers.append(re.compile(r'(E\d{3}.*?)(?=\r)'))

        for matcher in matchers:
            for match in matcher.finditer(raw_data):
                return_list.append((match.start(), match.end()))

        return return_list

    def _build_param_dict(self):
        """
        Build the parameter dictionary
        """
        self._param_dict.add(Parameter.TELEGRAM_INTERVAL,
                             '',
                             None,
                             None,
                             type=ParameterDictType.INT,
                             startup_param=True,
                             display_name='Data Telegram Interval in Sample',
                             units=Prefixes.MILLI + Units.SECOND,
                             description='The interval in milliseconds between successive MCU data telegrams' +
                                         'while in the SAMPLE/CAL state')
        self._param_dict.add(Parameter.SAMPLE_TIME,
                             '',
                             None,
                             None,
                             type=ParameterDictType.INT,
                             startup_param=True,
                             display_name='Sample Cycle Time',
                             units=Units.MINUTE,
                             description='The length of each portion of the sample cycle')
        self._param_dict.add(Parameter.ONE_MINUTE,
                             '',
                             None,
                             None,
                             visibility=ParameterDictVisibility.IMMUTABLE,
                             type=ParameterDictType.INT,
                             startup_param=True,
                             default_value=60000,
                             display_name='Length of One Minute',
                             units=Prefixes.MILLI + Units.SECOND,
                             description='MCU timing constant representing the number of seconds per minute')
        self._param_dict.add(Parameter.ERROR_REASON,
                             '',
                             None,
                             None,
                             visibility=ParameterDictVisibility.READ_ONLY,
                             type=ParameterDictType.STRING,
                             value='',
                             display_name='Reason for Error State',
                             description='Reason for Error State')

    def _build_command_dict(self):
        """
        Populate the command dictionary with commands.
        """
        self._cmd_dict.add(Capability.START1, display_name="Execute ASTART1")
        self._cmd_dict.add(Capability.START2, display_name="Execute ASTART2")
        self._cmd_dict.add(Capability.SAMPLE, display_name="Execute ASAMPLEXX")
        self._cmd_dict.add(Capability.CALIBRATE, display_name="Execute ACAL9")
        self._cmd_dict.add(Capability.NAFREG, display_name="Execute U ANAFREG3")
        self._cmd_dict.add(Capability.IONREG, display_name="Execute U AIONREG3")
        self._cmd_dict.add(Capability.STANDBY, display_name="Execute U ASTANDBY")
        self._cmd_dict.add(Capability.CLEAR, display_name="Clear the driver error state")
        self._cmd_dict.add(Capability.POWEROFF, display_name="Execute U APOWEROFF")

    def _build_driver_dict(self):
        """
        Populate the driver dictionary with options
        """
        self._driver_dict.add(DriverDictKey.VENDOR_SW_COMPATIBLE, False)

    def _build_telegram_interval_command(self, *args, **kwargs):
        """
        Build the telegram interval command using the TELEGRAM_INTERVAL parameter
        """
        return '%s%08d%s' % (InstrumentCommand.SET_TELEGRAM_INTERVAL,
                             int(self._param_dict.get(Parameter.TELEGRAM_INTERVAL)),
                             NEWLINE)

    def _build_set_minute_command(self, *args, **kwargs):
        """
        Build the SETMINUTE command
        """
        return '%s%05d%s' % (InstrumentCommand.SET_MINUTE,
                             int(self._param_dict.get(Parameter.ONE_MINUTE)),
                             NEWLINE)

    def _build_sample_command(self, *args, **kwargs):
        """
        Build the SAMPLE command
        """
        return '%s%02d%s' % (InstrumentCommand.SAMPLE,
                             int(self._param_dict.get(Parameter.SAMPLE_TIME)),
                             NEWLINE)

    def _got_chunk(self, chunk, ts):
        """
        The base class got_data has gotten a chunk from the chunker.  Pass it to extract_sample
        with the appropriate particle objects and regexes.

        Raise specific events on receipt of chunks.  This allows the driver to react asynchronously.

        @param chunk - data to be converted to a particle
        @param ts - timestamp
        """
        event = None
        exception = None
        sample = self._extract_sample(McuDataParticle, McuDataParticle.regex_compiled(), chunk, ts)
        if sample:
            return

        # we don't want to act on any responses in direct access or command mode
        # so just return here if that's the case...
        current_state = self.get_current_state()
        if current_state in [ProtocolState.DIRECT_ACCESS, ProtocolState.COMMAND]:
            return

        # These responses (may) come from the instrument asynchronously, so they are handled
        # here rather than in a response handler.
        ignored = [Prompt.OK, Prompt.BEAT, Prompt.STANDBY]
        if chunk in ignored:
            pass
        elif chunk == Prompt.START1:
            event = ProtocolEvent.START1_COMPLETE
        elif chunk == Prompt.START2:
            event = ProtocolEvent.START2_COMPLETE
        elif chunk == Prompt.SAMPLE_FINISHED:
            event = ProtocolEvent.SAMPLE_COMPLETE
        elif chunk == Prompt.CAL_FINISHED:
            event = ProtocolEvent.CALIBRATE_COMPLETE
        elif chunk == Prompt.IONREG_FINISHED:
            event = ProtocolEvent.STANDBY
        elif chunk == Prompt.NAFREG_FINISHED:
            event = ProtocolEvent.STANDBY
        elif chunk == Prompt.ERROR:
            event = ProtocolEvent.ERROR
            self._param_dict.set_value(Parameter.ERROR_REASON, 'Error prompt received from instrument.')
            self._driver_event(DriverAsyncEvent.CONFIG_CHANGE)
        elif chunk == Prompt.ONLINE:
            if not self.resetting:
                # This is an unexpected reset, ignore if we are in command or error
                if current_state == ProtocolState.ERROR:
                    event = ProtocolEvent.ERROR
                    self._param_dict.set_value(Parameter.ERROR_REASON, 'MCU reset during sequence.')
                    self._driver_event(DriverAsyncEvent.CONFIG_CHANGE)
        elif chunk in [Prompt.NAFTEMP_NOT_ACHIEVED, Prompt.IONTEMP_NOT_ACHIEVED]:
            # regeneration temperature not achieved, move to COMMAND and raise an exception
            event = ProtocolEvent.STANDBY
            exception = InstrumentProtocolException('Failed to achieve regen temperature')
        else:
            log.error('Unhandled chunk: %r in state: %s', chunk, current_state)
            exception = InstrumentProtocolException('Unhandled chunk: %r in state: %s' % (chunk, current_state))

        if event is not None:
            self._async_raise_fsm_event(event)
        if exception:
            self._driver_event(DriverAsyncEvent.ERROR, exception)

    def _filter_capabilities(self, events):
        """
        Return a list of currently available capabilities.
        @param events - events to be filtered
        @return list of events which are also capabilities
        """
        return [x for x in events if Capability.has(x)]

    def _wakeup(self, *args, **kwargs):
        """
        Not needed, the MCU never sleeps...
        """

    def _generic_response_handler(self, result, prompt, command=None):
        """
        Generic response handler to pass results through unmodified.
        @param result - result
        @param prompt - prompt
        @command - Command which generated the result
        @return result
        """
        return result

    def _set_params(self, *args, **kwargs):
        """
        This instrument has no params
        @throws InstrumentParameterException
        """
        self._verify_not_readonly(*args, **kwargs)
        params_to_set = args[0]
        startup = False
        if len(args) > 1:
            startup = args[1]
        old_config = self._param_dict.get_all()

        # check if in range
        constraints = ParameterConstraint.dict()
        parameters = Parameter.reverse_dict()

        # step through the list of parameters
        for key, val in params_to_set.iteritems():
            # if constraint exists, verify we have not violated it
            constraint_key = parameters.get(key)
            if constraint_key in constraints:
                var_type, minimum, maximum = constraints[constraint_key]
                try:
                    value = var_type(val)
                except ValueError:
                    raise InstrumentParameterException(
                        'Unable to verify type - parameter: %s value: %s' % (key, val))
                if val < minimum or val > maximum:
                    raise InstrumentParameterException(
                        'Value out of range - parameter: %s value: %s min: %s max: %s' %
                        (key, val, minimum, maximum))

        # all constraints met or no constraints exist, set the values
        for key, val in params_to_set.iteritems():
            if key in old_config:
                self._param_dict.set_value(key, val)
            else:
                raise InstrumentParameterException(
                    'Attempted to set unknown parameter: %s value: %s' % (key, val))
        new_config = self._param_dict.get_all()

        # If we changed anything, raise a CONFIG_CHANGE event
        if old_config != new_config:
            self._driver_event(DriverAsyncEvent.CONFIG_CHANGE)

    def _reset_mcu(self):
        """
        Reset the MCU via the watchdog timer
        """
        try:
            self.resetting = True
            # set the watchdog timer
            self._do_cmd_resp(InstrumentCommand.SET_WATCHDOG, expected_prompt=Prompt.OK, timeout=60)
            # try to put the MCU in standby, if successful watchdog will reset MCU
            result = self._do_cmd_resp(InstrumentCommand.STANDBY,
                                       expected_prompt=[Prompt.ONLINE, Prompt.IN_SEQUENCE], timeout=60)
            # MCU was in sequence, abort it and then go standby to reset MCU
            if result == Prompt.IN_SEQUENCE:
                self._do_cmd_resp(InstrumentCommand.ABORT, expected_prompt=Prompt.ABORTED, timeout=60)
                self._do_cmd_resp(InstrumentCommand.STANDBY, expected_prompt=Prompt.ONLINE, timeout=60)
            # MCU expects a BEAT after reset, send it
            self._do_cmd_resp(InstrumentCommand.BEAT, expected_prompt=Prompt.BEAT)
            # set the MINUTE value
            self._do_cmd_resp(InstrumentCommand.SET_MINUTE, expected_prompt=Prompt.SET_MINUTE)
            # This should actually put us in standby
            self._do_cmd_resp(InstrumentCommand.STANDBY, expected_prompt=Prompt.STANDBY, timeout=60)
        finally:
            self.resetting = False

    ########################################################################
    # Unknown handlers.
    ########################################################################

    def _handler_unknown_discover(self, *args, **kwargs):
        """
        Discover current state
        @return_value (next_state, result)
        """
        return ProtocolState.COMMAND, ResourceAgentState.IDLE

    ########################################################################
    # Command handlers.
    ########################################################################

    def _handler_command_enter(self, *args, **kwargs):
        """
        Enter command state.  Break out of any currently running sequence and return the MCU to STANDBY
        """
        self._init_params()

        try:
            self._reset_mcu()
        except InstrumentTimeoutException:
            # something else is wrong, pass the buck to the operator
            self._param_dict.set_value(Parameter.ERROR_REASON, 'Timeout communicating with instrument.')
            self._driver_event(DriverAsyncEvent.CONFIG_CHANGE)
            self._async_raise_fsm_event(ProtocolEvent.ERROR)

        # Tell driver superclass to send a state change event.
        # Superclass will query the state.
        self._driver_event(DriverAsyncEvent.STATE_CHANGE)

    def _handler_command_get(self, *args, **kwargs):
        """
        This driver has no parameters, return an empty dict.
        """
        return self._handler_get(*args, **kwargs)

    def _handler_command_set(self, *args, **kwargs):
        """
        Set parameter
        """
        self._set_params(*args, **kwargs)
        return None, None

    def _handler_command_start_direct(self):
        """
        Start direct access
        @return next_state, (next_agent_state, result)
        """
        return ProtocolState.DIRECT_ACCESS, (ResourceAgentState.DIRECT_ACCESS, None)

    def _handler_command_start1(self):
        """
        Send the start1 command and move to the start1 state
        @return next_state, (next_agent_state, result)
        """
        self._reset_mcu()
        return ProtocolState.START1, (ResourceAgentState.BUSY, self._do_cmd_resp(InstrumentCommand.START1))

    def _handler_command_nafreg(self):
        """
        Send the nafreg command and move to the nafreg state
        @return next_state, (next_agent_state, result)
        """
        return ProtocolState.REGEN, (ResourceAgentState.BUSY, self._do_cmd_resp(InstrumentCommand.NAFREG))

    def _handler_command_ionreg(self):
        """
        Send the ionreg command and move to the ionreg state
        @return next_state, (next_agent_state, result)
        """
        return ProtocolState.REGEN, (ResourceAgentState.BUSY, self._do_cmd_resp(InstrumentCommand.IONREG))

    def _handler_command_poweroff(self):
        """
        Send the ionreg command and move to the ionreg state
        @return next_state, (next_agent_state, result)
        """
        return None, (None, self._do_cmd_resp(InstrumentCommand.POWEROFF))

    ########################################################################
    # START1 handlers.
    ########################################################################

    def _handler_start1_complete(self):
        """
        Start1 sequence complete, move to waiting_turbo
        @return next_state, (next_agent_state, result)
        """
        return ProtocolState.WAITING_TURBO, (ResourceAgentState.IDLE, None)

    ########################################################################
    # WAITING_TURBO handlers.
    ########################################################################

    def _handler_waiting_turbo_start2(self):
        """
        Turbo is at speed, send start2 and move to start2 state
        @return next_state, (next_agent_state, result)
        """
        return ProtocolState.START2, (ResourceAgentState.BUSY, self._do_cmd_resp(InstrumentCommand.START2))

    ########################################################################
    # START2 handlers.
    ########################################################################

    def _handler_start2_complete(self):
        """
        Start2 complete, move to waiting_rga state
        @return next_state, (next_agent_state, result)
        """
        return ProtocolState.WAITING_RGA, (ResourceAgentState.BUSY, None)

    ########################################################################
    # WAITING_RGA handlers.
    ########################################################################

    def _handler_waiting_rga_sample(self):
        """
        RGA configuration/startup complete, send start sample and move to sample state
        @return next_state, (next_agent_state, result)
        """
        result = self._do_cmd_resp(InstrumentCommand.SAMPLE)
        self._do_cmd_resp(InstrumentCommand.SET_TELEGRAM_INTERVAL)
        return ProtocolState.SAMPLE, (ResourceAgentState.BUSY, result)

    def _handler_waiting_rga_cal(self):
        """
        RGA configuration/startup complete, send start cal and move to cal state
        @return next_state, (next_agent_state, result)
        """
        result = self._do_cmd_resp(InstrumentCommand.CAL)
        self._do_cmd_resp(InstrumentCommand.SET_TELEGRAM_INTERVAL)
        return ProtocolState.CALIBRATE, (ResourceAgentState.BUSY, result)

    ########################################################################
    # SAMPLE handlers.
    ########################################################################

    def _handler_sample_complete(self):
        """
        Sample complete, move to the stopping state.
        @return next_state, (next_agent_state, result)
        """
        return ProtocolState.STOPPING, (ResourceAgentState.BUSY, None)

    ########################################################################
    # CALIBRATE handlers.
    ########################################################################

    def _handler_cal_complete(self):
        """
        Cal complete, move to the stopping state.
        @return next_state, (next_agent_state, result)
        """
        return ProtocolState.STOPPING, (ResourceAgentState.BUSY, None)

    ########################################################################
    # ERROR handler. Handle in all states.
    ########################################################################

    def _handler_error(self):
        """
        Error detected, move to error state.
        @return next_state, (next_agent_state, result)
        """
        return ProtocolState.ERROR, (ResourceAgentState.BUSY, None)

    def _handler_stop(self):
        """
        Return to COMMAND
        """
        if self._param_dict.get(Parameter.ERROR_REASON):
            self._param_dict.set_value(Parameter.ERROR_REASON, '')
            self._driver_event(DriverAsyncEvent.CONFIG_CHANGE)
        return ProtocolState.COMMAND, (ResourceAgentState.COMMAND, None)

    def _handler_error_standby(self):
        """
        Move instrument to STANDBY, stay in error state
        """
        self._reset_mcu()

    ########################################################################
    # GENERIC handlers.
    ########################################################################

    def _handler_generic_enter(self, *args, **kwargs):
        """
        Generic enter handler
        """
        self._driver_event(DriverAsyncEvent.STATE_CHANGE)

    def _handler_generic_exit(self, *args, **kwargs):
        """
        Generic exit handler
        """

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

    def _handler_direct_access_execute_direct(self, data):
        """
        Pass direct access commands through to the instrument
        @return next_state, (next_agent_state, result)
        """
        self._do_cmd_direct(data)

        # add sent command to list for 'echo' filtering in callback
        self._sent_cmds.append(data)
        return None, (None, None)
