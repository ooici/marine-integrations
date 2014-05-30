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
from mi.core.exceptions import SampleException, InstrumentParameterException, InstrumentTimeoutException
from mi.core.instrument.driver_dict import DriverDictKey
from mi.core.log import get_logger
from mi.core.log import get_logging_metaclass
from mi.core.common import BaseEnum
from mi.core.instrument.instrument_protocol import CommandResponseInstrumentProtocol
from mi.core.instrument.instrument_fsm import ThreadSafeFSM
from mi.core.instrument.instrument_driver import SingleConnectionInstrumentDriver
from mi.core.instrument.instrument_driver import DriverEvent
from mi.core.instrument.instrument_driver import DriverAsyncEvent
from mi.core.instrument.instrument_driver import DriverProtocolState
from mi.core.instrument.instrument_driver import DriverParameter
from mi.core.instrument.instrument_driver import ResourceAgentState
from mi.core.instrument.data_particle import DataParticle, DataParticleKey
from mi.core.instrument.data_particle import CommonDataParticleType
from mi.core.instrument.chunker import StringChunker
from mi.instrument.harvard.massp.common import MASSP_STATE_ERROR, MASSP_CLEAR_ERROR


__author__ = 'Peter Cable'
__license__ = 'Apache 2.0'

log = get_logger()

METALOGGER_LOG_LEVEL = 'trace'

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
    NAFREG = 'PROTOCOL_STATE_NAFREG'
    IONREG = 'PROTOCOL_STATE_IONREG'
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
    NAFREG_COMPLETE = 'PROTOCOL_EVENT_NAFREG_COMPLETE'
    IONREG = 'PROTOCOL_EVENT_IONREG'
    IONREG_COMPLETE = 'PROTOCOL_EVENT_IONREG_COMPLETE'
    CALIBRATE = DriverEvent.CALIBRATE
    CALIBRATE_COMPLETE = 'PROTOCOL_EVENT_CALIBRATE_COMPLETE'
    ERROR = 'PROTOCOL_EVENT_ERROR'
    STANDBY = 'PROTOCOL_EVENT_STANDBY'
    CLEAR = MASSP_CLEAR_ERROR


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


class Parameter(DriverParameter):
    """
    Device specific parameters.
    """


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
    ONLINE = "M Main Module Online"
    BEAT = "M BEAT"
    POWEROFF = "M POWEROFF mode activated"
    CAL_FINISHED = "M CAL end"
    NAFREG_FINISHED = "M Nafion Reg finished"
    IONREG_FINISHED = "M Ion Reg finished"
    ABORTED = "M ABORTED"
    IN_SEQUENCE = 'E001 already in sequence'


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
    __metaclass__ = get_logging_metaclass(log_level=METALOGGER_LOG_LEVEL)
    _data_particle_type = DataParticleType.MCU_STATUS

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
        return re.compile(McuDataParticle.regex())

    def _build_parsed_values(self):
        """
        Parse the data telegram from the MCU and generate a status particle.
        """
        # data fields are comma-delimited
        # the first and last segment contain labels only
        # data items are colon delimited, first field is a label only
        # all data items are integers, however, the external values
        # masquerade as floats, so we have to explicitly split on the '.'
        try:
            segments = [[int(x.split('.')[0]) for x in row.split(':')[1:]] for row in self.raw_data.split(',')[1:-1]]

            powers, pressures, internals, externals, external_statuses, power_statuses, \
                solenoid_statuses, calibration_statuses, heater_statuses = segments

            result = [
                {DataParticleKey.VALUE_ID: McuStatusParticleKey.RGA_CURRENT,
                 DataParticleKey.VALUE: powers[0]},
                {DataParticleKey.VALUE_ID: McuStatusParticleKey.TURBO_CURRENT,
                 DataParticleKey.VALUE: powers[1]},
                {DataParticleKey.VALUE_ID: McuStatusParticleKey.HEATER_CURRENT,
                 DataParticleKey.VALUE: powers[2]},
                {DataParticleKey.VALUE_ID: McuStatusParticleKey.ROUGHING_CURRENT,
                 DataParticleKey.VALUE: powers[3]},
                {DataParticleKey.VALUE_ID: McuStatusParticleKey.FAN_CURRENT,
                 DataParticleKey.VALUE: powers[4]},
                {DataParticleKey.VALUE_ID: McuStatusParticleKey.SBE_CURRENT,
                 DataParticleKey.VALUE: powers[5]},
                {DataParticleKey.VALUE_ID: McuStatusParticleKey.CONVERTER_24V_MAIN,
                 DataParticleKey.VALUE: powers[6]},
                {DataParticleKey.VALUE_ID: McuStatusParticleKey.CONVERTER_12V_MAIN,
                 DataParticleKey.VALUE: powers[7]},
                {DataParticleKey.VALUE_ID: McuStatusParticleKey.CONVERTER_24V_SEC,
                 DataParticleKey.VALUE: powers[8]},
                {DataParticleKey.VALUE_ID: McuStatusParticleKey.CONVERTER_12V_SEC,
                 DataParticleKey.VALUE: powers[9]},
                {DataParticleKey.VALUE_ID: McuStatusParticleKey.VALVE_CURRENT,
                 DataParticleKey.VALUE: powers[10]},

                {DataParticleKey.VALUE_ID: McuStatusParticleKey.PRESSURE_P1,
                 DataParticleKey.VALUE: pressures[0]},
                {DataParticleKey.VALUE_ID: McuStatusParticleKey.PRESSURE_P2,
                 DataParticleKey.VALUE: pressures[1]},
                {DataParticleKey.VALUE_ID: McuStatusParticleKey.PRESSURE_P3,
                 DataParticleKey.VALUE: pressures[2]},
                {DataParticleKey.VALUE_ID: McuStatusParticleKey.PRESSURE_P4,
                 DataParticleKey.VALUE: pressures[3]},

                {DataParticleKey.VALUE_ID: McuStatusParticleKey.HOUSING_PRESSURE,
                 DataParticleKey.VALUE: internals[0]},
                {DataParticleKey.VALUE_ID: McuStatusParticleKey.HOUSING_HUMIDITY,
                 DataParticleKey.VALUE: internals[1]},
                {DataParticleKey.VALUE_ID: McuStatusParticleKey.TEMP_MAIN_CONTROL,
                 DataParticleKey.VALUE: internals[2]},
                {DataParticleKey.VALUE_ID: McuStatusParticleKey.TEMP_MAIN_ROUGH,
                 DataParticleKey.VALUE: internals[3]},
                {DataParticleKey.VALUE_ID: McuStatusParticleKey.TEMP_SEC_ROUGH,
                 DataParticleKey.VALUE: internals[4]},
                {DataParticleKey.VALUE_ID: McuStatusParticleKey.TEMP_MAIN_24V,
                 DataParticleKey.VALUE: internals[5]},
                {DataParticleKey.VALUE_ID: McuStatusParticleKey.TEMP_SEC_24V,
                 DataParticleKey.VALUE: internals[6]},
                {DataParticleKey.VALUE_ID: McuStatusParticleKey.TEMP_ANALYZER,
                 DataParticleKey.VALUE: internals[7]},
                {DataParticleKey.VALUE_ID: McuStatusParticleKey.TEMP_NAFION,
                 DataParticleKey.VALUE: internals[8]},
                {DataParticleKey.VALUE_ID: McuStatusParticleKey.TEMP_ION,
                 DataParticleKey.VALUE: internals[9]},

                {DataParticleKey.VALUE_ID: McuStatusParticleKey.PH_METER,
                 DataParticleKey.VALUE: externals[0]},
                {DataParticleKey.VALUE_ID: McuStatusParticleKey.INLET_TEMP,
                 DataParticleKey.VALUE: externals[1]},

                {DataParticleKey.VALUE_ID: McuStatusParticleKey.PH_STATUS,
                 DataParticleKey.VALUE: external_statuses[0]},
                {DataParticleKey.VALUE_ID: McuStatusParticleKey.INLET_TEMP_STATUS,
                 DataParticleKey.VALUE: external_statuses[1]},

                {DataParticleKey.VALUE_ID: McuStatusParticleKey.POWER_RELAY_TURBO,
                 DataParticleKey.VALUE: power_statuses[0]},
                {DataParticleKey.VALUE_ID: McuStatusParticleKey.POWER_RELAY_RGA,
                 DataParticleKey.VALUE: power_statuses[1]},
                {DataParticleKey.VALUE_ID: McuStatusParticleKey.POWER_RELAY_MAIN_ROUGH,
                 DataParticleKey.VALUE: power_statuses[2]},
                {DataParticleKey.VALUE_ID: McuStatusParticleKey.POWER_RELAY_SEC_ROUGH,
                 DataParticleKey.VALUE: power_statuses[3]},
                {DataParticleKey.VALUE_ID: McuStatusParticleKey.POWER_RELAY_FAN1,
                 DataParticleKey.VALUE: power_statuses[4]},
                {DataParticleKey.VALUE_ID: McuStatusParticleKey.POWER_RELAY_FAN2,
                 DataParticleKey.VALUE: power_statuses[5]},
                {DataParticleKey.VALUE_ID: McuStatusParticleKey.POWER_RELAY_FAN3,
                 DataParticleKey.VALUE: power_statuses[6]},
                {DataParticleKey.VALUE_ID: McuStatusParticleKey.POWER_RELAY_FAN4,
                 DataParticleKey.VALUE: power_statuses[7]},
                {DataParticleKey.VALUE_ID: McuStatusParticleKey.POWER_RELAY_AUX2,
                 DataParticleKey.VALUE: power_statuses[8]},
                {DataParticleKey.VALUE_ID: McuStatusParticleKey.POWER_RELAY_PH,
                 DataParticleKey.VALUE: power_statuses[9]},
                {DataParticleKey.VALUE_ID: McuStatusParticleKey.POWER_RELAY_PUMP,
                 DataParticleKey.VALUE: power_statuses[10]},
                {DataParticleKey.VALUE_ID: McuStatusParticleKey.POWER_RELAY_HEATERS,
                 DataParticleKey.VALUE: power_statuses[11]},
                {DataParticleKey.VALUE_ID: McuStatusParticleKey.POWER_RELAY_AUX1,
                 DataParticleKey.VALUE: power_statuses[12]},

                {DataParticleKey.VALUE_ID: McuStatusParticleKey.SAMPLE_VALVE1,
                 DataParticleKey.VALUE: solenoid_statuses[0]},
                {DataParticleKey.VALUE_ID: McuStatusParticleKey.SAMPLE_VALVE2,
                 DataParticleKey.VALUE: solenoid_statuses[1]},
                {DataParticleKey.VALUE_ID: McuStatusParticleKey.SAMPLE_VALVE3,
                 DataParticleKey.VALUE: solenoid_statuses[2]},
                {DataParticleKey.VALUE_ID: McuStatusParticleKey.SAMPLE_VALVE4,
                 DataParticleKey.VALUE: solenoid_statuses[3]},

                {DataParticleKey.VALUE_ID: McuStatusParticleKey.GROUND_RELAY_STATUS,
                 DataParticleKey.VALUE: calibration_statuses[0]},
                {DataParticleKey.VALUE_ID: McuStatusParticleKey.EXTERNAL_VALVE1_STATUS,
                 DataParticleKey.VALUE: calibration_statuses[1]},
                {DataParticleKey.VALUE_ID: McuStatusParticleKey.EXTERNAL_VALVE2_STATUS,
                 DataParticleKey.VALUE: calibration_statuses[2]},
                {DataParticleKey.VALUE_ID: McuStatusParticleKey.EXTERNAL_VALVE3_STATUS,
                 DataParticleKey.VALUE: calibration_statuses[3]},
                {DataParticleKey.VALUE_ID: McuStatusParticleKey.EXTERNAL_VALVE4_STATUS,
                 DataParticleKey.VALUE: calibration_statuses[4]},
                {DataParticleKey.VALUE_ID: McuStatusParticleKey.CAL_BAG1_MINUTES,
                 DataParticleKey.VALUE: calibration_statuses[5]},
                {DataParticleKey.VALUE_ID: McuStatusParticleKey.CAL_BAG2_MINUTES,
                 DataParticleKey.VALUE: calibration_statuses[6]},
                {DataParticleKey.VALUE_ID: McuStatusParticleKey.CAL_BAG3_MINUTES,
                 DataParticleKey.VALUE: calibration_statuses[7]},

                {DataParticleKey.VALUE_ID: McuStatusParticleKey.NAFION_HEATER_STATUS,
                 DataParticleKey.VALUE: heater_statuses[0]},
                {DataParticleKey.VALUE_ID: McuStatusParticleKey.NAFION_HEATER1_POWER,
                 DataParticleKey.VALUE: heater_statuses[1]},
                {DataParticleKey.VALUE_ID: McuStatusParticleKey.NAFION_HEATER2_POWER,
                 DataParticleKey.VALUE: heater_statuses[2]},
                {DataParticleKey.VALUE_ID: McuStatusParticleKey.NAFION_CORE_TEMP,
                 DataParticleKey.VALUE: heater_statuses[3]},
                {DataParticleKey.VALUE_ID: McuStatusParticleKey.NAFION_ELAPSED_TIME,
                 DataParticleKey.VALUE: heater_statuses[4]},
                {DataParticleKey.VALUE_ID: McuStatusParticleKey.ION_CHAMBER_STATUS,
                 DataParticleKey.VALUE: heater_statuses[5]},
                {DataParticleKey.VALUE_ID: McuStatusParticleKey.ION_CHAMBER_HEATER1_STATUS,
                 DataParticleKey.VALUE: heater_statuses[7]},
                {DataParticleKey.VALUE_ID: McuStatusParticleKey.ION_CHAMBER_HEATER2_STATUS,
                 DataParticleKey.VALUE: heater_statuses[8]},
            ]
        except IndexError, e:
            raise SampleException('Incomplete or corrupt data telegram received (%s)', e)
        except ValueError, e:
            raise SampleException('Incomplete or corrupt data telegram received (%s)', e)
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
    __metaclass__ = get_logging_metaclass(log_level=METALOGGER_LOG_LEVEL)

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
    __metaclass__ = get_logging_metaclass(log_level=METALOGGER_LOG_LEVEL)

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
                (ProtocolEvent.ENTER, self._handler_unknown_enter),
                (ProtocolEvent.EXIT, self._handler_unknown_exit),
                (ProtocolEvent.DISCOVER, self._handler_unknown_discover),
                (ProtocolEvent.START_DIRECT, self._handler_command_start_direct),
                (ProtocolEvent.ERROR, self._handler_error),
            ],
            ProtocolState.COMMAND: [
                (ProtocolEvent.ENTER, self._handler_command_enter),
                (ProtocolEvent.EXIT, self._handler_command_exit),
                (ProtocolEvent.START_DIRECT, self._handler_command_start_direct),
                (ProtocolEvent.GET, self._handler_command_get),
                (ProtocolEvent.SET, self._handler_command_set),
                (ProtocolEvent.START1, self._handler_command_start1),
                (ProtocolEvent.NAFREG, self._handler_command_nafreg),
                (ProtocolEvent.IONREG, self._handler_command_ionreg),
                (ProtocolEvent.ERROR, self._handler_error),
            ],
            ProtocolState.START1: [
                (ProtocolEvent.ENTER, self._handler_generic_enter),
                (ProtocolEvent.EXIT, self._handler_generic_exit),
                (ProtocolEvent.START1_COMPLETE, self._handler_start1_complete),
                (ProtocolEvent.ERROR, self._handler_error),
            ],
            ProtocolState.WAITING_TURBO: [
                (ProtocolEvent.ENTER, self._handler_generic_enter),
                (ProtocolEvent.EXIT, self._handler_generic_exit),
                (ProtocolEvent.STANDBY, self._handler_standby),
                (ProtocolEvent.START2, self._handler_waiting_turbo_start2),
                (ProtocolEvent.ERROR, self._handler_error),
            ],
            ProtocolState.START2: [
                (ProtocolEvent.ENTER, self._handler_generic_enter),
                (ProtocolEvent.EXIT, self._handler_generic_exit),
                (ProtocolEvent.START2_COMPLETE, self._handler_start2_complete),
                (ProtocolEvent.ERROR, self._handler_error),
            ],
            ProtocolState.WAITING_RGA: [
                (ProtocolEvent.ENTER, self._handler_generic_enter),
                (ProtocolEvent.EXIT, self._handler_generic_exit),
                (ProtocolEvent.STANDBY, self._handler_standby),
                (ProtocolEvent.SAMPLE, self._handler_waiting_rga_sample),
                (ProtocolEvent.CALIBRATE, self._handler_waiting_rga_cal),
                (ProtocolEvent.ERROR, self._handler_error),
            ],
            ProtocolState.SAMPLE: [
                (ProtocolEvent.ENTER, self._handler_generic_enter),
                (ProtocolEvent.EXIT, self._handler_generic_exit),
                (ProtocolEvent.SAMPLE_COMPLETE, self._handler_sample_complete),
                (ProtocolEvent.ERROR, self._handler_error),
            ],
            ProtocolState.CALIBRATE: [
                (ProtocolEvent.ENTER, self._handler_generic_enter),
                (ProtocolEvent.EXIT, self._handler_generic_exit),
                (ProtocolEvent.CALIBRATE_COMPLETE, self._handler_cal_complete),
                (ProtocolEvent.ERROR, self._handler_error),
            ],
            ProtocolState.STOPPING: [
                (ProtocolEvent.ENTER, self._handler_generic_enter),
                (ProtocolEvent.EXIT, self._handler_generic_exit),
                (ProtocolEvent.STANDBY, self._handler_standby),
                (ProtocolEvent.ERROR, self._handler_error),
            ],
            ProtocolState.NAFREG: [
                (ProtocolEvent.ENTER, self._handler_generic_enter),
                (ProtocolEvent.EXIT, self._handler_generic_exit),
                (ProtocolEvent.NAFREG_COMPLETE, self._handler_nafreg_complete),
                (ProtocolEvent.ERROR, self._handler_error),
            ],
            ProtocolState.IONREG: [
                (ProtocolEvent.ENTER, self._handler_generic_enter),
                (ProtocolEvent.EXIT, self._handler_generic_exit),
                (ProtocolEvent.IONREG_COMPLETE, self._handler_ionreg_complete),
                (ProtocolEvent.ERROR, self._handler_error),
            ],
            ProtocolState.DIRECT_ACCESS: [
                (ProtocolEvent.ENTER, self._handler_direct_access_enter),
                (ProtocolEvent.EXIT, self._handler_direct_access_exit),
                (ProtocolEvent.STOP_DIRECT, self._handler_direct_access_stop_direct),
                (ProtocolEvent.EXECUTE_DIRECT, self._handler_direct_access_execute_direct),
            ],
            ProtocolState.ERROR: [
                (ProtocolEvent.ENTER, self._handler_generic_enter),
                (ProtocolEvent.EXIT, self._handler_generic_exit),
                (ProtocolEvent.CLEAR, self._handler_clear),
                (ProtocolEvent.START1_COMPLETE, self._handler_standby),
                (ProtocolEvent.START2_COMPLETE, self._handler_standby),
                (ProtocolEvent.SAMPLE_COMPLETE, self._handler_standby),
                (ProtocolEvent.CALIBRATE_COMPLETE, self._handler_standby),
                (ProtocolEvent.NAFREG_COMPLETE, self._handler_standby),
                (ProtocolEvent.IONREG_COMPLETE, self._handler_standby),
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
            self._add_build_handler(command, self._build_simple_command)

        # State state machine in UNKNOWN state.
        self._protocol_fsm.start(ProtocolState.UNKNOWN)

        # commands sent sent to device to be filtered in responses for telnet DA
        self._sent_cmds = []

        self._chunker = StringChunker(Protocol.sieve_function)

    @staticmethod
    def sieve_function(raw_data):
        """
        The method that splits samples
        """
        matchers = []
        return_list = []

        matchers.append(McuDataParticle.regex_compiled())
        matchers.append(re.compile(r'(M .*?)(?=\r)'))

        for matcher in matchers:
            for match in matcher.finditer(raw_data):
                return_list.append((match.start(), match.end()))

        return return_list

    def _build_param_dict(self):
        """
        Populate the parameter dictionary with parameters.
        For each parameter key, add match string, match lambda function,
        and value formatting function for set commands.
        """
        # Add parameter handlers to parameter dict.

    def _build_command_dict(self):
        """
        Populate the command dictionary with commands.
        """
        self._cmd_dict.add(Capability.START1, display_name="start sequence 1")
        self._cmd_dict.add(Capability.START2, display_name="start sequence 2")
        self._cmd_dict.add(Capability.SAMPLE, display_name="start sample sequence")
        self._cmd_dict.add(Capability.NAFREG, display_name="start nafion regeneration")
        self._cmd_dict.add(Capability.IONREG, display_name="start ion chamber regeneration")
        self._cmd_dict.add(Capability.STANDBY, display_name="transition to standby")
        self._cmd_dict.add(Capability.CLEAR, display_name="clear error state")

    def _build_driver_dict(self):
        """
        Populate the driver dictionary with options
        """
        self._driver_dict.add(DriverDictKey.VENDOR_SW_COMPATIBLE, False)

    def _got_chunk(self, chunk, ts):
        """
        The base class got_data has gotten a chunk from the chunker.  Pass it to extract_sample
        with the appropriate particle objects and regexes.
        """
        event = None
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
            event = ProtocolEvent.IONREG_COMPLETE
        elif chunk == Prompt.NAFREG_FINISHED:
            event = ProtocolEvent.NAFREG_COMPLETE
        elif chunk == Prompt.ERROR:
            event = ProtocolEvent.ERROR
        else:
            log.error('Unhandled chunk: %r in state: %s', chunk, current_state)

        if event is not None:
            self._async_raise_fsm_event(event)

    def _filter_capabilities(self, events):
        """
        Return a list of currently available capabilities.
        """
        return [x for x in events if Capability.has(x)]

    def _wakeup(self, *args, **kwargs):
        """
        Not needed.
        """

    def _generic_response_handler(self, result, prompt, command=None):
        return result

    def _set_params(self, *args, **kwargs):
        params = args[0]
        if params:
            raise InstrumentParameterException('Attempted to set unknown parameters: %r' % params)

    def _abort_sequence(self):
        """
        Abort the current sequence.
        Run the ASTART1 sequence to return to a known state.
        Return to STANDBY
        """
        self._do_cmd_resp(InstrumentCommand.ABORT, expected_prompt=Prompt.ABORTED)
        self._do_cmd_resp(InstrumentCommand.START1, expected_prompt=Prompt.START1, timeout=120)
        self._do_cmd_resp(InstrumentCommand.STANDBY, expected_prompt=Prompt.STANDBY, timeout=30)

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
        @return_value (next_state, result)
        """
        return ProtocolState.COMMAND, ResourceAgentState.IDLE

    ########################################################################
    # Command handlers.
    ########################################################################

    def _handler_command_enter(self, *args, **kwargs):
        """
        Enter command state.
        """
        self._do_cmd_resp(InstrumentCommand.BEAT)

        try:
            result = self._do_cmd_resp(InstrumentCommand.STANDBY, expected_prompt=[Prompt.STANDBY, Prompt.IN_SEQUENCE])
            if Prompt.STANDBY in result:
                log.info('MCU in standby, proceeding to COMMAND')
            elif result == Prompt.IN_SEQUENCE:
                # wait it out or break out?
                self._abort_sequence()
        except InstrumentTimeoutException:
            # something else is wrong, pass the buck to the operator
            self._async_raise_fsm_event(ProtocolEvent.ERROR)

        # Tell driver superclass to send a state change event.
        # Superclass will query the state.
        self._driver_event(DriverAsyncEvent.STATE_CHANGE)

    def _handler_command_get(self, *args, **kwargs):
        """
        Get parameter
        """
        return None, {}

    def _handler_command_set(self, *args, **kwargs):
        """
        Set parameter
        """
        self._set_params(*args, **kwargs)
        return None, None

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
        return next_state, (next_agent_state, result)

    def _handler_command_start1(self):
        """
        Send the start1 command and move to the start1 state
        """
        next_state = ProtocolState.START1
        next_agent_state = ResourceAgentState.BUSY
        result = self._do_cmd_resp(InstrumentCommand.START1)
        return next_state, (next_agent_state, result)

    def _handler_command_nafreg(self):
        """
        Send the nafreg command and move to the nafreg state
        """
        next_state = ProtocolState.NAFREG
        next_agent_state = ResourceAgentState.BUSY
        result = self._do_cmd_resp(InstrumentCommand.NAFREG)
        return next_state, (next_agent_state, result)

    def _handler_command_ionreg(self):
        """
        Send the ionreg command and move to the ionreg state
        """
        next_state = ProtocolState.IONREG
        next_agent_state = ResourceAgentState.BUSY
        result = self._do_cmd_resp(InstrumentCommand.IONREG)
        return next_state, (next_agent_state, result)

    ########################################################################
    # START1 handlers.
    ########################################################################

    def _handler_start1_complete(self):
        """
        Start1 sequence complete, move to waiting_turbo
        """
        next_state = ProtocolState.WAITING_TURBO
        next_agent_state = ResourceAgentState.IDLE
        result = None
        return next_state, (next_agent_state, result)

    ########################################################################
    # WAITING_TURBO handlers.
    ########################################################################

    def _handler_waiting_turbo_start2(self):
        """
        Turbo is at speed, send start2 and move to start2 state
        """
        result = self._do_cmd_resp(InstrumentCommand.START2)
        next_state = ProtocolState.START2
        next_agent_state = ResourceAgentState.BUSY
        result = None
        return next_state, (next_agent_state, result)

    ########################################################################
    # START2 handlers.
    ########################################################################

    def _handler_start2_complete(self):
        """
        Start2 complete, move to waiting_rga state
        """
        next_state = ProtocolState.WAITING_RGA
        next_agent_state = ResourceAgentState.IDLE
        result = None
        return next_state, (next_agent_state, result)

    ########################################################################
    # WAITING_RGA handlers.
    ########################################################################

    def _handler_waiting_rga_sample(self):
        """
        RGA configuration/startup complete, send start sample and move to sample state
        """
        result = self._do_cmd_resp(InstrumentCommand.SAMPLE)
        next_state = ProtocolState.SAMPLE
        next_agent_state = ResourceAgentState.BUSY
        return next_state, (next_agent_state, result)

    def _handler_waiting_rga_cal(self):
        """
        RGA configuration/startup complete, send start cal and move to cal state
        """
        result = self._do_cmd_resp(InstrumentCommand.CAL)
        next_state = ProtocolState.CALIBRATE
        next_agent_state = ResourceAgentState.BUSY
        return next_state, (next_agent_state, result)

    ########################################################################
    # SAMPLE handlers.
    ########################################################################

    def _handler_sample_complete(self):
        """
        Sample complete, move to the stopping state.
        """
        next_state = ProtocolState.STOPPING
        next_agent_state = ResourceAgentState.IDLE
        result = None
        return next_state, (next_agent_state, result)

    ########################################################################
    # CALIBRATE handlers.
    ########################################################################

    def _handler_cal_complete(self):
        """
        Cal complete, move to the stopping state.
        """
        next_state = ProtocolState.STOPPING
        next_agent_state = ResourceAgentState.IDLE
        result = None
        return next_state, (next_agent_state, result)

    ########################################################################
    # GENERIC handlers.
    ########################################################################

    def _handler_standby(self):
        """
        Put MCU in standby, return to COMMAND
        """
        result = self._do_cmd_resp(InstrumentCommand.STANDBY)
        next_state = ProtocolState.COMMAND
        next_agent_state = ResourceAgentState.IDLE
        result = None
        return next_state, (next_agent_state, result)

    ########################################################################
    # NAFREG handlers.
    ########################################################################

    def _handler_nafreg_complete(self):
        """
        Nafion regen complete, going to command
        """
        next_state = ProtocolState.COMMAND
        next_agent_state = ResourceAgentState.IDLE
        result = None
        return next_state, (next_agent_state, result)

    ########################################################################
    # IONREG handlers.
    ########################################################################

    def _handler_ionreg_complete(self):
        """
        Ion regen complete, going to command
        """
        next_state = ProtocolState.COMMAND
        next_agent_state = ResourceAgentState.IDLE
        result = None
        return next_state, (next_agent_state, result)

    ########################################################################
    # ERROR handler. Handle in all states.
    ########################################################################

    def _handler_error(self):
        """
        Error detected, move to error state.
        """
        next_state = ProtocolState.ERROR
        next_agent_state = ResourceAgentState.IDLE
        result = None
        current_state = self.get_current_state()
        non_sequence_states = [ProtocolState.WAITING_TURBO,
                               ProtocolState.WAITING_RGA,
                               ProtocolState.STOPPING]
        if current_state in non_sequence_states:
            # instrument is not in a sequence, go straight to standby
            self._do_cmd_resp(InstrumentCommand.STANDBY)
        else:
            self._abort_sequence()

        return next_state, (next_agent_state, result)

    def _handler_clear(self):
        """
        Operator has requested to clear the error state, return to command.
        """
        next_state = ProtocolState.COMMAND
        next_agent_state = ResourceAgentState.COMMAND
        result = None
        return next_state, (next_agent_state, result)

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

    def _handler_direct_access_exit(self, *args, **kwargs):
        """
        Exit direct access state.
        """

    def _handler_direct_access_execute_direct(self, data):
        """
        Pass direct access commands through to the instrument
        """
        next_state = None
        result = None
        next_agent_state = None

        self._do_cmd_direct(data)

        # add sent command to list for 'echo' filtering in callback
        self._sent_cmds.append(data)

        return next_state, (next_agent_state, result)

    def _handler_direct_access_stop_direct(self):
        """
        @throw InstrumentProtocolException on invalid command
        """
        next_state = None
        result = None

        next_state = ProtocolState.COMMAND
        next_agent_state = ResourceAgentState.COMMAND

        return next_state, (next_agent_state, result)
