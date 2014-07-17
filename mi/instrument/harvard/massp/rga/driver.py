"""
@package mi.instrument.harvard.massp.rga.driver
@file marine-integrations/mi/instrument/harvard/massp/rga/driver.py
@author Peter Cable
@brief Driver for the rga
Release notes:

RGA driver for the MASSP in-situ mass spectrometer
"""

__author__ = 'Peter Cable'
__license__ = 'Apache 2.0'

import re
import struct
import time
import datetime
import functools
import ntplib
import mi.core.log
import mi.core.exceptions as exceptions
from mi.core.driver_scheduler import DriverSchedulerConfigKey
from mi.core.driver_scheduler import TriggerType
from mi.core.instrument.protocol_param_dict import ParameterDictType
from mi.core.instrument.protocol_param_dict import ParameterDictVisibility
from mi.core.common import BaseEnum
from mi.core.instrument.instrument_protocol import CommandResponseInstrumentProtocol
from mi.core.instrument.instrument_fsm import ThreadSafeFSM
from mi.core.instrument.instrument_driver import SingleConnectionInstrumentDriver
from mi.core.instrument.instrument_driver import DriverConfigKey
from mi.core.instrument.instrument_driver import DriverEvent
from mi.core.instrument.instrument_driver import DriverAsyncEvent
from mi.core.instrument.instrument_driver import DriverProtocolState
from mi.core.instrument.instrument_driver import DriverParameter
from mi.core.instrument.instrument_driver import ResourceAgentState
from mi.core.instrument.data_particle import CommonDataParticleType
from mi.core.instrument.data_particle import DataParticle
from mi.core.instrument.data_particle import DataParticleKey
from mi.core.instrument.chunker import StringChunker
from mi.core.instrument.driver_dict import DriverDictKey
from mi.core.common import Units
from mi.core.common import Prefixes
from mi.instrument.harvard.massp.common import MASSP_STATE_ERROR, MASSP_CLEAR_ERROR


log = mi.core.log.get_logger()
META_LOGGER = mi.core.log.get_logging_metaclass()


###
#    Driver Constant Definitions
###
TIMEOUT = 10
NEWLINE = '\r'
SCAN_START_SENTINEL = struct.pack('>I', 0xdeadbeef)
RESPONSE_REGEX = re.compile(r'(.*)\n\r')
MAX_RETRIES = 5
# RGA manual says this should be within .02
CLOSE_ENOUGH = 0.02
QUERY = 'query'
STATUS = 'status'


class DriverUnits(Units):
    COUNT = 'count'
    AMU = 'amu'


class ScheduledJob(BaseEnum):
    """
    Scheduled jobs for the RGA
    """
    TAKE_SCAN = 'take_scan'


class DataParticleType(BaseEnum):
    """
    Data particle types produced by this driver
    """
    RAW = CommonDataParticleType.RAW
    RGA_SAMPLE = 'massp_rga_sample'
    RGA_STATUS = 'massp_rga_status'


class ProtocolState(BaseEnum):
    """
    Instrument protocol states
    """
    UNKNOWN = DriverProtocolState.UNKNOWN
    COMMAND = DriverProtocolState.COMMAND
    DIRECT_ACCESS = DriverProtocolState.DIRECT_ACCESS
    SCAN = 'PROTOCOL_STATE_SCAN'
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
    START_SCAN = 'PROTOCOL_EVENT_START_SCAN'
    STOP_SCAN = 'PROTOCOL_EVENT_STOP_SCAN'
    TAKE_SCAN = 'PROTOCOL_EVENT_TAKE_SCAN'
    ERROR = 'PROTOCOL_EVENT_ERROR'
    CLEAR = MASSP_CLEAR_ERROR
    TIMEOUT = 'PROTOCOL_EVENT_TIMEOUT'


class Capability(BaseEnum):
    """
    Protocol events that should be exposed to users (subset of above).
    """
    START_SCAN = ProtocolEvent.START_SCAN
    STOP_SCAN = ProtocolEvent.STOP_SCAN
    TAKE_SCAN = ProtocolEvent.TAKE_SCAN
    CLEAR = ProtocolEvent.CLEAR


class Parameter(DriverParameter):
    """
    Device specific parameters.
    """
    ID = 'rga_device_id'
    EE = 'rga_electron_energy'
    IE = 'rga_ion_energy'
    VF = 'rga_focus_voltage'
    NF = 'rga_noise_floor'
    ER = 'rga_error_status'
    SA = 'rga_steps_per_amu'
    MI = 'rga_initial_mass'
    MF = 'rga_final_mass'
    AP = 'rga_readings_per_scan'
    HV = 'rga_high_voltage_cdem'
    FL = 'rga_filament_emission_set'
    FL_ACTUAL = 'rga_filament_emission_actual'
    ERROR_REASON = 'rga_error_reason'

    @classmethod
    def reverse_dict(cls):
        return dict((v, k) for k, v in cls.dict().iteritems())


class Responses(BaseEnum):
    """
    This enum tracks whether a set command returns a STATUS byte or
    if the device only responds to queries.
    """
    ID = QUERY
    IN = STATUS
    EE = STATUS
    IE = STATUS
    VF = STATUS
    FL = STATUS
    NF = QUERY
    ER = STATUS
    SA = QUERY
    MI = QUERY
    MF = QUERY
    AP = QUERY
    HV = STATUS


class ParameterConstraints(BaseEnum):
    """
    Parameter constraints for the RGA
    These are necessary because the RGA is configured asynchronously from the SET event.
    (param_type, minimum, maximum)
    """
    EE = (int, 25, 105)
    IE = (int, 0, 1)
    VF = (int, 0, 150)
    FL = (float, 0, 3.5)
    NF = (int, 0, 7)
    SA = (int, 10, 25)
    MI = (int, 1, 200)
    MF = (int, 1, 200)
    HV = (int, 0, 2490)


class Prompt(BaseEnum):
    """
    Device i/o prompts..
    N/A to RGA
    """


class InstrumentCommand(BaseEnum):
    """
    Instrument command strings
    """
    ID = 'ID'
    INITIALIZE = 'IN'
    ELECTRON_ENERGY = 'EE'
    ION_ENERGY = 'IE'
    FOCUS_VOLTAGE = 'VF'
    FILAMENT_EMISSION = 'FL'
    NOISE_FLOOR = 'NF'
    CHECK_ERRORS = 'ER'
    STEPS_PER_AMU = 'SA'
    READINGS_PER_SCAN = 'AP'
    INITIAL_MASS = 'MI'
    FINAL_MASS = 'MF'
    ANALOG_SCAN = 'SC'
    HIGH_VOLTAGE = 'HV'


###############################################################################
# Data Particles
###############################################################################

class RGASampleParticleKey(BaseEnum):
    """
    Data particle keys for the RGA sample particle
    """
    SCAN_DATA = 'massp_scan_data'


# noinspection PyMethodMayBeStatic,PyProtectedMember
class RGASampleParticle(DataParticle):
    """
    RGA Sample particle.  Takes a binary blob, decodes to a list of Integers
    """
    __metaclass__ = META_LOGGER
    _data_particle_type = DataParticleType.RGA_SAMPLE

    def _build_parsed_values(self):
        my_struct = struct.Struct('<%di' % (len(self.raw_data) / 4))
        values = my_struct.unpack(self.raw_data)
        result = [
            {DataParticleKey.VALUE_ID: RGASampleParticleKey.SCAN_DATA,
             DataParticleKey.VALUE: values},
        ]
        return result


class RGAStatusParticleKey(BaseEnum):
    """
    The RGA status particle contains the same keys as DriverParameter, minus the ALL
    """
    ID = 'massp_rga_device_id'
    EE = 'massp_rga_electron_energy'
    IE = 'massp_rga_ion_energy'
    VF = 'massp_rga_focus_voltage'
    FL = 'massp_rga_filament_emission_set'
    NF = 'massp_rga_noise_floor'
    ER = 'massp_rga_error_status'
    SA = 'massp_rga_steps_per_amu'
    MI = 'massp_rga_initial_mass'
    MF = 'massp_rga_final_mass'
    AP = 'massp_rga_readings_per_scan'
    HV = 'massp_rga_high_voltage_cdem'
    FL_ACTUAL = 'massp_rga_filament_emission_actual'


class RGAStatusParticle(DataParticle):
    """
    The contents of the parameter dictionary, published at the start of a scan
    """
    __metaclass__ = META_LOGGER
    _data_particle_type = DataParticleType.RGA_STATUS

    def _build_parsed_values(self):
        result = []
        for key, value in self.raw_data.items():
            if key == Parameter.ERROR_REASON:
                continue
            key = 'massp_%s' % key
            result.append({DataParticleKey.VALUE_ID: key,
                           DataParticleKey.VALUE: value})
        log.debug('STATUS PARTICLE: %r', result)
        return result


###############################################################################
# Driver
###############################################################################

class InstrumentDriver(SingleConnectionInstrumentDriver):
    """
    InstrumentDriver subclass
    Subclasses SingleConnectionInstrumentDriver with connection state machine.
    """
    __metaclass__ = META_LOGGER

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
    __metaclass__ = META_LOGGER

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
            ],
            ProtocolState.COMMAND: [
                (ProtocolEvent.ENTER, self._handler_generic_enter),
                (ProtocolEvent.EXIT, self._handler_generic_exit),
                (ProtocolEvent.START_DIRECT, self._handler_command_start_direct),
                (ProtocolEvent.GET, self._handler_command_get),
                (ProtocolEvent.SET, self._handler_command_set),
                (ProtocolEvent.START_SCAN, self._handler_command_start_scan),
            ],
            ProtocolState.DIRECT_ACCESS: [
                (ProtocolEvent.ENTER, self._handler_direct_access_enter),
                (ProtocolEvent.EXIT, self._handler_generic_exit),
                (ProtocolEvent.STOP_DIRECT, self._handler_direct_access_stop_direct),
                (ProtocolEvent.EXECUTE_DIRECT, self._handler_direct_access_execute_direct),
            ],
            ProtocolState.SCAN: [
                (ProtocolEvent.ENTER, self._handler_scan_enter),
                (ProtocolEvent.EXIT, self._handler_scan_exit),
                (ProtocolEvent.STOP_SCAN, self._handler_scan_stop_scan),
                (ProtocolEvent.TAKE_SCAN, self._handler_scan_take_scan),
                (ProtocolEvent.TIMEOUT, self._handler_scan_timeout),
                (ProtocolEvent.ERROR, self._handler_scan_error),
            ],
            ProtocolState.ERROR: [
                (ProtocolEvent.ENTER, self._handler_generic_enter),
                (ProtocolEvent.EXIT, self._handler_generic_exit),
                (ProtocolEvent.CLEAR, self._handler_error_clear),
                (ProtocolEvent.GET, self._handler_command_get),
            ]
        }

        for state in handlers:
            for event, handler in handlers[state]:
                self._protocol_fsm.add_handler(state, event, handler)

        # Construct the parameter dictionary containing device parameters,
        # current parameter values, and set formatting functions.
        self._build_param_dict()
        self._build_command_dict()
        self._build_driver_dict()

        # Add build handlers for device commands.
        for command in InstrumentCommand.list():
            self._add_build_handler(command, self._generic_build_handler)

        # Add response handlers for device commands.
        for command in InstrumentCommand.list():
            self._add_response_handler(command, functools.partial(self._generic_response_handler, command=command))

        # State state machine in UNKNOWN state.
        self._protocol_fsm.start(ProtocolState.UNKNOWN)

        # commands sent sent to device to be filtered in responses for telnet DA
        self._sent_cmds = []

        self._chunker = StringChunker(Protocol.sieve_function)
        self.initialize_scheduler()

        # all calls to do_cmd_resp should expect RESPONSE_REGEX and use TIMEOUT.  Freeze these arguments...
        self._do_cmd_resp = functools.partial(self._do_cmd_resp, response_regex=RESPONSE_REGEX, timeout=TIMEOUT)

        # these variables are used to track scan time and completion status
        # for development and performance data
        self.scan_start_time = 0
        self.in_scan = False

    @staticmethod
    def sieve_function(raw_data):
        """
        This is a placeholder.  The sieve function for the RGA is built dynamically when a scan is started.
        This function must return a list.
        see self._build_sieve_function()
        """
        return []

    def _build_param_dict(self):
        """
        Populate the parameter dictionary with parameters.
        For each parameter key, add match string, match lambda function,
        and value formatting function for set commands.
        """
        name = 'display_name'
        desc = 'description'
        units = 'units'
        val_desc = 'value_description'

        parameters = {
            Parameter.ID: {
                name: 'RGA ID String',
                desc: 'RGA ID String',
            },
            Parameter.EE: {
                name: 'Electron Energy',
                desc: 'The desired electron ionization energy',
                units: DriverUnits.ELECTRONVOLT,
                val_desc: 'The desired electron ionization energy in units of eV'
            },
            Parameter.IE: {
                name: 'Ion Energy',
                desc: 'Set the Ion Energy to one of two possible levels: Low (8eV) or High(12eV)',
                val_desc: 'Ion energy level: 0 for Low and 1 for High',
            },
            Parameter.VF: {
                name: 'Focus Plate Voltage',
                desc: 'The focus plate voltage in the ionizer',
                val_desc: 'The parameter represents the magnitude of the biasing voltage (negative) in units of volts.',
                units: DriverUnits.VOLT,
            },
            Parameter.NF: {
                name: 'Noise Floor',
                desc: 'Set the rate and detection limit for ion current measurements.',
                val_desc: 'The parameter represents the noise-floor level desired. Lower parameter values ' +
                          'correspond to lower baseline noise, better detection limits and increased measurement ' +
                          'times. Please refer to the Electrometer section of the RGA Electronics Control Unit ' +
                          'chapter to obtain detailed information about detection limits and bandwidth values' +
                          'as a function of NF settings.',
            },
            Parameter.SA: {
                name: 'Steps per AMU',
                desc: 'Set the number of steps executed per amu of analog scan.',
                val_desc: 'The parameter specifies the number of steps-per-amu.',
                units: DriverUnits.COUNT,
            },
            Parameter.MI: {
                name: 'Initial Mass',
                desc: 'The initial scan mass',
                units: DriverUnits.AMU,
            },
            Parameter.MF: {
                name: 'Final Mass',
                desc: 'The final scan mass',
                units: DriverUnits.AMU,
            },
            Parameter.FL: {
                name: 'Electron Emission Current',
                desc: 'Set the electron emission current level in the ionizer.',
                val_desc: 'The parameter represents the desired electron emission current.',
                units: Prefixes.MILLI + Units.AMPERE
            },
            Parameter.FL_ACTUAL: {
                name: 'Actual Electron Emission Current',
                desc: 'The actual electron emission current level in the ionizer',
                val_desc: 'The parameter represents the actual electron emission current.',
                units: Prefixes.MILLI + Units.AMPERE
            },
            Parameter.AP: {
                name: 'Analog Scan Points',
                desc: 'The total number of ion currents that will be measured and transmitted' +
                      'during an analog scan under the current scan conditions.',
                val_desc: 'Total number of ion currents to be transmitted.  Does not include the four extra' +
                          'bytes for total pressure included when performing an analog scan.',
                units: DriverUnits.COUNT
            },
            Parameter.HV: {
                name: 'High Voltage CDEM',
                desc: 'Electron Multiplier High Voltage Bias setting',
                val_desc: '0 disables the CDEM, values from 10-2490 enable the CDEM and specify the CDEM bias voltage',
                units: Units.VOLT
            },
            Parameter.ER: {
                name: 'Status Byte',
                desc: 'Bit-mapped value representing any errors detected by the RGA',
                val_desc: '0 indicates no errors detected.  See the RGA manual if this value is non-zero.',
            },
            Parameter.ERROR_REASON: {
                name: 'RGA Error Reason',
                desc: 'Reason for RGA error state'
            }
        }

        constraints = ParameterConstraints.dict()
        read_only = [Parameter.ID, Parameter.AP, Parameter.ER, Parameter.FL_ACTUAL, Parameter.ERROR_REASON]
        floats = [Parameter.FL, Parameter.FL_ACTUAL]
        strings = [Parameter.ID, Parameter.ERROR_REASON]

        for param in parameters:
            visibility = ParameterDictVisibility.READ_WRITE
            value_type = ParameterDictType.INT
            formatter = int
            startup = True
            if param in read_only:
                visibility = ParameterDictVisibility.READ_ONLY
                startup = False
            if param in floats:
                value_type = ParameterDictType.FLOAT
                formatter = float
            elif param in strings:
                value_type = ParameterDictType.STRING
                formatter = str

            if param in constraints:
                _type, minimum, maximum = constraints[param]
                parameters[param][val_desc] = '%s %s value from %d - %d' % (parameters[param].get(val_desc, ''),
                                                                            _type, minimum, maximum)

            self._param_dict.add(param, '', None, formatter, type=value_type,
                                 visibility=visibility, startup_param=startup, **parameters[param])

    def _build_command_dict(self):
        """
        Populate the command dictionary with commands.
        """
        self._cmd_dict.add(Capability.START_SCAN, display_name="Start scan")
        self._cmd_dict.add(Capability.STOP_SCAN, display_name="Stop scan")
        self._cmd_dict.add(Capability.CLEAR, display_name="Clear the error state")

    def _build_driver_dict(self):
        """
        Populate the driver dictionary with options
        """
        self._driver_dict.add(DriverDictKey.VENDOR_SW_COMPATIBLE, False)

    def _got_chunk(self, chunk, ts):
        """
        The base class got_data has gotten a chunk from the chunker.
        We only generate sample particles and they cannot be verified (beyond size, which is done in the chunker).
        Just create a particle, reset the scheduler and start the next scan.
        @param chunk: data to process
        @param ts: timestamp
        """
        elapsed = time.time() - self.scan_start_time
        self.in_scan = False
        log.debug('_got_chunk: Received complete scan.  AP: %d NF: %d SIZE: %d ET: %d secs',
                  self._param_dict.get(Parameter.AP),
                  self._param_dict.get(Parameter.NF),
                  len(chunk),
                  elapsed)
        self._driver_event(DriverAsyncEvent.SAMPLE, RGASampleParticle(chunk, port_timestamp=ts).generate())
        # Reset the scheduler and initiate the next scan if we are in the scan state
        if self.get_current_state() == ProtocolState.SCAN:
            self._build_scheduler()
            self._async_raise_fsm_event(ProtocolEvent.TAKE_SCAN)

    def _generic_response_handler(self, resp, prompt, command=None):
        """
        Generic response handler.  Shove the results into the param dict.
        The associated command should be frozen when the response handler is registered using functools.partial
        @param resp: command response
        @param prompt: not used, required to match signature
        @param command: command which generated response
        @return: response
        """
        parameter = getattr(Parameter, command, None)
        log.debug('_generic_response_handler: command: %s parameter: %s resp: %s', command, parameter, resp)
        if parameter in self._param_dict.get_keys():
            if parameter == Parameter.FL:
                parameter = Parameter.FL_ACTUAL
            try:
                self._param_dict.set_value(parameter, self._param_dict.format(parameter, resp))
            except ValueError:
                # bad data?  Don't set the value, but keep the driver moving forward
                # verify the data if necessary downstream.
                pass
        return resp

    def _generic_build_handler(self, command, *args, **kwargs):
        """
        Generic build handler.  If a value is passed, then this is a set, otherwise it's a query...
        @param command: command to build
        @param args: arglist which may contain a value
        @return: command string
        """
        if len(args) == 1:
            # this is a set action
            value = args[0]
            return self._build_rga_set(command, value) + NEWLINE
        # this is a query
        return self._build_rga_query(command) + NEWLINE

    def _build_rga_set(self, command, value):
        """
        Build a set command
        @param command: command to build
        @param value: value to set
        @return: command string
        """
        return command + str(value)

    def _build_rga_query(self, command):
        """
        Build a query command
        @param command: command to build
        @return: command string
        """
        return command + '?'

    def _filter_capabilities(self, events):
        """
        Return a list of currently available capabilities.
        @param events: list of events to be filtered
        @return: list of events which are in capability
        """
        return [x for x in events if Capability.has(x)]

    def _wakeup(self, timeout, delay=1):
        """
        Wakeup not required for this instrument
        """

    def _build_scheduler(self):
        """
        Remove any previously scheduled event, then generate an absolute trigger to schedule the next
        scan in case we lose some data and the next scan isn't triggered by got_chunk.
        """
        try:
            self._remove_scheduler(ScheduledJob.TAKE_SCAN)
            log.debug('Successfully removed existing scheduled event TAKE_SCAN.')
        except KeyError as ke:
            log.debug('KeyError: %s', ke)

        # this formula was derived from testing, should yield a slightly higher time than the actual
        # time required to collect a single scan.
        delay = self._param_dict.get(Parameter.AP) / 9 / self._param_dict.get(Parameter.NF) + 5

        if delay > 0:
            dt = datetime.datetime.now() + datetime.timedelta(seconds=delay)

            job_name = ScheduledJob.TAKE_SCAN
            config = {
                DriverConfigKey.SCHEDULER: {
                    job_name: {
                        DriverSchedulerConfigKey.TRIGGER: {
                            DriverSchedulerConfigKey.TRIGGER_TYPE: TriggerType.ABSOLUTE,
                            DriverSchedulerConfigKey.DATE: dt
                        },
                    }
                }
            }

            self.set_init_params(config)
            self._add_scheduler_event(ScheduledJob.TAKE_SCAN, ProtocolEvent.TIMEOUT)

    def _update_params(self, *args, **kwargs):
        """
        Parameters are NOT set in the instrument by this method, as the RGA is configured anytime
        a scan is started, as it may have been powered off since the last time we saw it.
        """

    def _set_params(self, *args, **kwargs):
        """
        Set parameters, raise a CONFIG_CHANGE event if necessary.
        @throws InstrumentParameterException
        """
        self._verify_not_readonly(*args, **kwargs)
        params_to_set = args[0]
        old_config = self._param_dict.get_all()

        # check if in range
        constraints = ParameterConstraints.dict()
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
                    raise exceptions.InstrumentParameterException(
                        'Unable to verify type - parameter: %s value: %s' % (key, val))
                if val < minimum or val > maximum:
                    raise exceptions.InstrumentParameterException(
                        'Value out of range - parameter: %s value: %s min: %s max: %s' %
                        (key, val, minimum, maximum))

        # all constraints met or no constraints exist, set the values
        for key, val in params_to_set.iteritems():
            if key in old_config:
                self._param_dict.set_value(key, val)
            else:
                raise exceptions.InstrumentParameterException(
                    'Attempted to set unknown parameter: %s value: %s' % (key, val))
        new_config = self._param_dict.get_all()

        # If we changed anything, raise a CONFIG_CHANGE event
        if old_config != new_config:
            self._driver_event(DriverAsyncEvent.CONFIG_CHANGE)

    def _check_error_byte(self, error_string):
        """
        Check the error byte as returned by some commands
        @param error_string: byte to be checked for errors
        @throws InstrumentStateException
        """
        # trim, just in case we received some garbage with our response...
        if len(error_string) > 1:
            error_string = error_string[-1]
        if int(error_string):
            self._async_raise_fsm_event(ProtocolEvent.ERROR)
            error = 'RGA Error byte set: %s' % error_string
            self._param_dict.set_value(Parameter.ERROR_REASON, error)
            self._driver_event(DriverAsyncEvent.CONFIG_CHANGE)
            raise exceptions.InstrumentStateException(error)

    def _set_instrument_parameter(self, command):
        """
        Set a parameter on the instrument.
        We will attempt up to MAX_SET_RETRIES to set the value correctly, according to the following sequence:
        1. send set command
        2. verify error byte, if returned (per Responses)
        3. send query command
        4. verify returned value equals the set value (within tolerance)
        @throws InstrumentParameterException
        """
        response_type = getattr(Responses, command)
        parameter = getattr(Parameter, command)

        # store the configured setting
        old_value = self._param_dict.format(parameter)

        if old_value is None:
            raise exceptions.InstrumentParameterException('Missing required instrument parameter: %s' % parameter)

        log.debug('response_type: %s parameter: %s command: %s', response_type, getattr(Parameter, command), command)
        # attempt to set the value up to MAX_SET_RETRIES times
        for x in xrange(MAX_RETRIES):
            if response_type == STATUS:
                resp = self._do_cmd_resp(command, old_value)
                self._check_error_byte(resp)
            else:
                self._do_cmd_no_resp(command, old_value)

            # query the value from the instrument to load the parameter dictionary
            self._do_cmd_resp(command)

            # if values match, we were successful, return.
            difference = abs(self._param_dict.format(parameter) - old_value)
            if difference < CLOSE_ENOUGH:
                return
            log.error('Set attempt failed. Parameter: %s Set value: %s Returned value: %s difference: %.2f',
                      parameter, old_value, self._param_dict.get(parameter), difference)

        # configuring the RGA failed, restore the setting from our configuration and raise an exception
        self._param_dict.set_value(parameter, old_value)
        raise exceptions.InstrumentParameterException('Unable to set instrument parameter: %s, attempted %d times' %
                                                      (parameter, MAX_RETRIES))

    def _build_sieve_function(self):
        """
        Build a sieve function based on the expected data size.  Replace the previous sieve function in
        the chunker.  This should happen during the configuration phase.
        """
        num_points = int(self._param_dict.get(Parameter.AP))
        match_string = r'(?<=%s)(.{%d})' % (SCAN_START_SENTINEL, (num_points + 1) * 4)
        matcher = re.compile(match_string, re.DOTALL)

        def my_sieve(raw_data):
            return_list = []

            log.debug('SIEVE: pattern=%r, raw_data_len=%d', matcher.pattern, len(raw_data))
            # do not descend into this loop unless we are at log level trace...
            if log.isEnabledFor('trace'):
                temp = raw_data[:]
                while temp:
                    log.trace('SIEVE: raw_data: %s', temp[:32].encode('hex'))
                    if len(temp) > 32:
                        temp = temp[32:]
                    else:
                        temp = ''

            for match in matcher.finditer(raw_data):
                # if sentinel value present in this slice it is invalid
                if not SCAN_START_SENTINEL in raw_data[match.start():match.end()]:
                    return_list.append((match.start(), match.end()))

            return return_list

        self._chunker.sieve = my_sieve

    def _verify_filament(self):
        """
        Ensure the filament is on and the current is within tolerance
        @throws InstrumentProtocolException
        """
        self._do_cmd_resp(InstrumentCommand.FILAMENT_EMISSION)
        filament_difference = abs(1 - self._param_dict.get(Parameter.FL_ACTUAL))
        if filament_difference > CLOSE_ENOUGH:
            self._async_raise_fsm_event(ProtocolEvent.ERROR)
            error = 'Filament power not withing tolerance (%.2f): %.2f' % (CLOSE_ENOUGH, filament_difference)
            self._param_dict.set_value(Parameter.ERROR_REASON, error)
            self._driver_event(DriverAsyncEvent.CONFIG_CHANGE)
            raise exceptions.InstrumentProtocolException(error)

    def _stop_instrument(self):
        """
        Stop any running scan, flush the output buffer, turn off the filament and CDEM.
        Update the parameter dictionary for FL.
        """
        try:
            self._remove_scheduler(ScheduledJob.TAKE_SCAN)
            log.debug('Successfully removed existing scheduled event TAKE_SCAN.')
        except KeyError as ke:
            log.debug('KeyError: %s', ke)

        self._do_cmd_resp(InstrumentCommand.INITIALIZE, 0)
        self._do_cmd_resp(InstrumentCommand.INITIALIZE, 2)
        self._do_cmd_resp(InstrumentCommand.FILAMENT_EMISSION)
        self.in_scan = False

    ########################################################################
    # Unknown handlers.
    ########################################################################

    def _handler_unknown_discover(self, *args, **kwargs):
        """
        Discover current state
        @return (next_state, result)
        """
        return ProtocolState.COMMAND, ResourceAgentState.IDLE

    ########################################################################
    # Command handlers.
    ########################################################################

    def _handler_command_get(self, *args, **kwargs):
        """
        Get parameter
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
        @return next_state, (next_agent_state, None)
        """
        return ProtocolState.DIRECT_ACCESS, (ResourceAgentState.DIRECT_ACCESS, None)

    def _handler_command_start_scan(self):
        """
        Start a scan
        @return next_state, (next_agent_state, None)
        """
        return ProtocolState.SCAN, (ResourceAgentState.STREAMING, None)

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
        Forward direct access commands to the instrument.
        @return next_state, (next_agent_state, None)
        """
        self._do_cmd_direct(data)

        # add sent command to list for 'echo' filtering in callback
        self._sent_cmds.append(data)
        return None, (None, None)

    def _handler_direct_access_stop_direct(self):
        """
        Stop direct access, return to COMMAND.
        @return next_state, (next_agent_state, None)
        """
        return ProtocolState.COMMAND, (ResourceAgentState.COMMAND, None)

    ########################################################################
    # Scan handlers
    ########################################################################

    def _handler_scan_enter(self, *args, **kwargs):
        """
        Enter the scan state.  Configure the RGA, start the first scan and the scheduler.
        @throws InstrumentTimeoutException
        """
        for attempt in range(1, MAX_RETRIES+1):
            try:
                self._handler_scan_configure_rga()
                self._async_raise_fsm_event(ProtocolEvent.TAKE_SCAN)
                self._build_scheduler()
                self._driver_event(DriverAsyncEvent.STATE_CHANGE)
                return
            except exceptions.InstrumentTimeoutException:
                log.error('Failed to configure the RGA - attempt %d', attempt)
        self._async_raise_fsm_event(ProtocolEvent.ERROR)
        error = 'Failed to configure RGA and start scanning.'
        self._param_dict.set_value(Parameter.ERROR_REASON, error)
        self._driver_event(DriverAsyncEvent.CONFIG_CHANGE)
        raise exceptions.InstrumentTimeoutException(error)

    def _handler_scan_exit(self, *args, **kwargs):
        """
        Exit scan.  Delete the scheduler.
        """
        try:
            self._remove_scheduler(ScheduledJob.TAKE_SCAN)
        except KeyError:
            log.error("_remove_scheduler could not find: %s", ScheduledJob.TAKE_SCAN)

    def _handler_scan_configure_rga(self):
        """
        Send the appropriate configuration to the RGA and update the chunker sieve function for the
        correct data length.
        """
        # initialize the connection
        self._do_cmd_resp(InstrumentCommand.INITIALIZE, 0)

        # set these
        set_commands = [
            (InstrumentCommand.ELECTRON_ENERGY, Parameter.EE),
            (InstrumentCommand.ION_ENERGY, Parameter.IE),
            (InstrumentCommand.FOCUS_VOLTAGE, Parameter.VF),
            (InstrumentCommand.NOISE_FLOOR, Parameter.NF),
            (InstrumentCommand.STEPS_PER_AMU, Parameter.SA),
            (InstrumentCommand.INITIAL_MASS, Parameter.MI),
            (InstrumentCommand.FINAL_MASS, Parameter.MF),
        ]

        for command, parameter in set_commands:
            self._set_instrument_parameter(command)

        # turn on the filament
        self._set_instrument_parameter(InstrumentCommand.FILAMENT_EMISSION)

        # query the read only items
        for command in [InstrumentCommand.READINGS_PER_SCAN, InstrumentCommand.FILAMENT_EMISSION,
                        InstrumentCommand.ID, InstrumentCommand.CHECK_ERRORS]:
            self._do_cmd_resp(command)

        # publish the config as a status particle
        pd = self._param_dict.get_all()
        log.debug('parameter dictionary: %r', pd)
        ts = ntplib.system_to_ntp_time(time.time())
        self._driver_event(DriverAsyncEvent.SAMPLE, RGAStatusParticle(pd, port_timestamp=ts).generate())

        # replace the sieve function
        self._build_sieve_function()

    def _handler_scan_take_scan(self, *args, **kwargs):
        """
        place a sentinel value in the chunker, then perform one analog scan from the RGA
        @return next_state, (next_agent_state, None)
        """
        # empty the chunker
        self._chunker.clean_all_chunks()
        # place sentinel value in chunker
        self._chunker.add_chunk(SCAN_START_SENTINEL, ntplib.system_to_ntp_time(time.time()))
        self.scan_start_time = time.time()
        if self.in_scan:
            log.error('FAILED scan detected, in_scan sentinel set to TRUE')
        self.in_scan = True
        self._do_cmd_no_resp(InstrumentCommand.ANALOG_SCAN, 1)
        return None, (None, None)

    def _handler_scan_timeout(self, *args, **kwargs):
        """
        Handle scan timeout
        @return next_state, (next_agent_state, None)
        """
        # timeout, clear the instrument buffers
        self._do_cmd_resp(InstrumentCommand.INITIALIZE, 0)
        # verify the filament is still on
        self._verify_filament()
        return self._handler_scan_take_scan()

    def _handler_scan_stop_scan(self, *args, **kwargs):
        """
        Stop scanning, go to COMMAND.
        @return next_state, (next_agent_state, None)
        """
        self._stop_instrument()
        return ProtocolState.COMMAND, (ResourceAgentState.COMMAND, None)

    def _handler_scan_error(self, *args, **kwargs):
        """
        Stop scanning, go to ERROR.
        @return next_state, (next_agent_state, None)
        """
        self._stop_instrument()
        return ProtocolState.ERROR, (ResourceAgentState.COMMAND, None)

    ########################################################################
    # Error handlers
    ########################################################################

    def _handler_error_clear(self):
        """
        Leave the error state, return to COMMAND.
        @return next_state, (next_agent_state, None)
        """
        self._param_dict.set_value(Parameter.ERROR_REASON, '')
        self._driver_event(DriverAsyncEvent.CONFIG_CHANGE)
        return ProtocolState.COMMAND, (ResourceAgentState.COMMAND, None)

    ########################################################################
    # Generic handlers
    ########################################################################

    def _handler_generic_enter(self):
        """
        Generic method to handle entering state.
        """
        if self.get_current_state() != ProtocolState.UNKNOWN:
            self._init_params()
        self._driver_event(DriverAsyncEvent.STATE_CHANGE)

    def _handler_generic_exit(self):
        """
        Generic method to handle exiting state.
        """