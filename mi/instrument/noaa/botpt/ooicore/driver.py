"""
@package mi.instrument.noaa.ooicore.driver
@file marine-integrations/mi/instrument/noaa/ooicore/driver.py
@author Pete Cable
@brief BOTPT
Release notes:
"""
import json
import re
import time
import datetime
import ntplib
from mi.core.driver_scheduler import DriverSchedulerConfigKey, TriggerType
from mi.core.instrument.data_particle import DataParticleKey, DataParticleValue
from mi.core.instrument.protocol_param_dict import ParameterDictVisibility, ParameterDictType
from mi.core.common import BaseEnum, Units, Prefixes
from mi.core.instrument.chunker import StringChunker
from mi.core.instrument.instrument_fsm import ThreadSafeFSM
from mi.core.instrument.instrument_protocol import CommandResponseInstrumentProtocol
from mi.core.instrument.instrument_driver import DriverEvent
from mi.core.instrument.instrument_driver import SingleConnectionInstrumentDriver
from mi.core.instrument.instrument_driver import DriverParameter
from mi.core.instrument.instrument_driver import DriverConfigKey
from mi.core.instrument.instrument_driver import DriverAsyncEvent
from mi.core.instrument.instrument_driver import ResourceAgentState
from mi.core.instrument.instrument_driver import DriverProtocolState
from mi.core.exceptions import InstrumentParameterException
from mi.core.exceptions import InstrumentProtocolException
from mi.core.exceptions import InstrumentDataException
from mi.core.instrument.driver_dict import DriverDictKey
import mi.instrument.noaa.botpt.ooicore.particles as particles
import mi.core.log


__author__ = 'Pete Cable'
__license__ = 'Apache 2.0'

log = mi.core.log.get_logger()
META_LOGGER = mi.core.log.get_logging_metaclass('debug')


###
#    Driver Constant Definitions
###

NEWLINE = '\n'

LILY_STRING = 'LILY,'
NANO_STRING = 'NANO,'
IRIS_STRING = 'IRIS,'
HEAT_STRING = 'HEAT,'
SYST_STRING = 'SYST,'

LILY_COMMAND = '*9900XY'
IRIS_COMMAND = LILY_COMMAND
NANO_COMMAND = '*0100'

NANO_RATE_RESPONSE = '*0001TH'

MAX_BUFFER_SIZE = 2 ** 16


class ScheduledJob(BaseEnum):
    LEVELING_TIMEOUT = 'botpt_leveling_timeout'
    NANO_TIME_SYNC = 'botpt_nano_time_sync'
    ACQUIRE_STATUS = 'botpt_acquire_status'


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
    START_LEVELING = 'PROTOCOL_EVENT_START_LEVELING'
    STOP_LEVELING = 'PROTOCOL_EVENT_STOP_LEVELING'
    NANO_TIME_SYNC = 'PROTOCOL_EVENT_NANO_TIME_SYNC'


class Capability(BaseEnum):
    """
    Protocol events that should be exposed to users (subset of above).
    """
    GET = ProtocolEvent.GET
    SET = ProtocolEvent.SET
    START_AUTOSAMPLE = ProtocolEvent.START_AUTOSAMPLE
    STOP_AUTOSAMPLE = ProtocolEvent.STOP_AUTOSAMPLE
    ACQUIRE_STATUS = ProtocolEvent.ACQUIRE_STATUS
    START_LEVELING = ProtocolEvent.START_LEVELING
    STOP_LEVELING = ProtocolEvent.STOP_LEVELING


class Parameter(DriverParameter):
    """
    Device specific parameters.
    """
    AUTO_RELEVEL = "auto_relevel"  # Auto-relevel mode
    XTILT_TRIGGER = "xtilt_relevel_trigger"
    YTILT_TRIGGER = "ytilt_relevel_trigger"
    LEVELING_TIMEOUT = "relevel_timeout"
    LEVELING_FAILED = "leveling_failed"
    OUTPUT_RATE = 'output_rate_hz'
    SYNC_INTERVAL = 'time_sync_interval'
    HEAT_DURATION = "heat_duration"

    @classmethod
    def reverse_dict(cls):
        return dict((v, k) for k, v in cls.dict().iteritems())


class ParameterConstraint(BaseEnum):
    """
    Constraints for parameters
    (type, min, max)
    """
    XTILT_TRIGGER = (float, 0, 330)
    YTILT_TRIGGER = (float, 0, 330)
    LEVELING_TIMEOUT = (int, 60, 6000)
    OUTPUT_RATE = (int, 1, 40)
    SYNC_INTERVAL = (int, 600, 86400)
    HEAT_DURATION = (int, 1, 8)


class InstrumentCommand(BaseEnum):
    LILY_ON = LILY_STRING + LILY_COMMAND + 'C2'  # turns on continuous data
    LILY_OFF = LILY_STRING + LILY_COMMAND + 'C-OFF'  # turns off continuous data
    LILY_DUMP1 = LILY_STRING + LILY_COMMAND + '-DUMP-SETTINGS'  # outputs current settings
    LILY_DUMP2 = LILY_STRING + LILY_COMMAND + '-DUMP2'  # outputs current extended settings
    LILY_START_LEVELING = LILY_STRING + LILY_COMMAND + '-LEVEL,1'  # starts leveling
    LILY_STOP_LEVELING = LILY_STRING + LILY_COMMAND + '-LEVEL,0'  # stops leveling
    NANO_ON = NANO_STRING + NANO_COMMAND + 'E4'  # turns on continuous data
    NANO_OFF = NANO_STRING + NANO_COMMAND + 'E3'  # turns off continuous data
    NANO_DUMP1 = NANO_STRING + NANO_COMMAND + 'IF'  # outputs current settings
    NANO_SET_TIME = NANO_STRING + 'TS'  # requests the SBC to update the NANO time
    NANO_SET_RATE = NANO_STRING + '*0100EW*0100TH='  # sets the sample rate in Hz
    IRIS_ON = IRIS_STRING + IRIS_COMMAND + 'C2'  # turns on continuous data
    IRIS_OFF = IRIS_STRING + IRIS_COMMAND + 'C-OFF'  # turns off continuous data
    IRIS_DUMP1 = IRIS_STRING + IRIS_COMMAND + '-DUMP-SETTINGS'  # outputs current settings
    IRIS_DUMP2 = IRIS_STRING + IRIS_COMMAND + '-DUMP2'  # outputs current extended settings
    HEAT = HEAT_STRING  # turns the heater on; HEAT,<number of hours>
    SYST_DUMP1 = SYST_STRING + '1'


class Prompt(BaseEnum):
    LILY_ON = LILY_COMMAND + 'C2'
    LILY_OFF = LILY_COMMAND + 'C-OFF'
    IRIS_ON = IRIS_COMMAND + 'C2'
    IRIS_OFF = IRIS_COMMAND + 'C-OFF'
    LILY_START_LEVELING = LILY_COMMAND + '-LEVEL,1'
    LILY_STOP_LEVELING = LILY_COMMAND + '-LEVEL,0'


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
        return Parameter.list()

    def _build_protocol(self):
        """
        Construct the driver protocol state machine.
        """
        self._protocol = Protocol(BaseEnum, NEWLINE, self._driver_event)


###########################################################################
# Protocol
###########################################################################

# noinspection PyUnusedLocal,PyMethodMayBeStatic
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
            ProtocolState.AUTOSAMPLE: [
                (ProtocolEvent.ENTER, self._handler_autosample_enter),
                (ProtocolEvent.EXIT, self._handler_generic_exit),
                (ProtocolEvent.ACQUIRE_STATUS, self._handler_acquire_status),
                (ProtocolEvent.STOP_AUTOSAMPLE, self._handler_autosample_stop_autosample),
                (ProtocolEvent.START_LEVELING, self._handler_start_leveling),
                (ProtocolEvent.STOP_LEVELING, self._handler_stop_leveling),
                (ProtocolEvent.NANO_TIME_SYNC, self._handler_time_sync),
            ],
            ProtocolState.COMMAND: [
                (ProtocolEvent.ENTER, self._handler_command_enter),
                (ProtocolEvent.EXIT, self._handler_generic_exit),
                (ProtocolEvent.GET, self._handler_command_get),
                (ProtocolEvent.SET, self._handler_command_set),
                (ProtocolEvent.ACQUIRE_STATUS, self._handler_acquire_status),
                (ProtocolEvent.START_AUTOSAMPLE, self._handler_command_start_autosample),
                (ProtocolEvent.START_LEVELING, self._handler_start_leveling),
                (ProtocolEvent.STOP_LEVELING, self._handler_stop_leveling),
                (ProtocolEvent.START_DIRECT, self._handler_command_start_direct),
                (ProtocolEvent.NANO_TIME_SYNC, self._handler_time_sync),
            ],
            ProtocolState.DIRECT_ACCESS: [
                (ProtocolEvent.ENTER, self._handler_direct_access_enter),
                (ProtocolEvent.EXIT, self._handler_generic_exit),
                (ProtocolEvent.EXECUTE_DIRECT, self._handler_direct_access_execute_direct),
                (ProtocolEvent.STOP_DIRECT, self._handler_direct_access_stop_direct),
            ],
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
            if command == InstrumentCommand.NANO_SET_RATE:
                self._add_build_handler(command, self._build_nano_output_rate_command)
            else:
                self._add_build_handler(command, self._build_simple_command)

        # # Add response handlers for device commands.
        for command in InstrumentCommand.list():
            self._add_response_handler(command, self._generic_response_handler)

        # State state machine in UNKNOWN state.
        self._protocol_fsm.start(ProtocolState.UNKNOWN)

        # commands sent to device to be filtered in responses for telnet DA
        self._sent_cmds = []

        self._chunker = StringChunker(Protocol.sieve_function)

        self.initialize_scheduler()
        self._last_data_timestamp = 0
        self.leveling = False
        self.has_pps = True
        self._add_scheduler_event(ScheduledJob.ACQUIRE_STATUS, ProtocolEvent.ACQUIRE_STATUS)
        self._add_scheduler_event(ScheduledJob.NANO_TIME_SYNC, ProtocolEvent.NANO_TIME_SYNC)

    @staticmethod
    def sieve_function(raw_data):
        """
        Sort data in the chunker...
        """
        matchers = []
        return_list = []

        matchers.append(particles.HeatSampleParticle.regex_compiled())
        matchers.append(particles.IrisSampleParticle.regex_compiled())
        matchers.append(particles.NanoSampleParticle.regex_compiled())
        matchers.append(particles.LilySampleParticle.regex_compiled())
        matchers.append(particles.LilyLevelingParticle.regex_compiled())

        for matcher in matchers:
            for match in matcher.finditer(raw_data):
                return_list.append((match.start(), match.end()))

        return return_list

    def _got_chunk(self, chunk, ts):
        possible_particles = [
            (particles.LilySampleParticle, self._check_for_autolevel),
            (particles.LilyLevelingParticle, self._check_completed_leveling),
            (particles.HeatSampleParticle, None),
            (particles.IrisSampleParticle, None),
            (particles.NanoSampleParticle, self._check_pps_sync),
        ]

        for particle_type, func in possible_particles:
            sample = self._extract_sample(particle_type, particle_type.regex_compiled(), chunk, ts)
            if sample:
                if func:
                    func(sample)
                return sample

        raise InstrumentProtocolException(u'unhandled chunk received by _got_chunk: [{0!r:s}]'.format(chunk))

    def _extract_sample(self, particle_class, regex, line, timestamp, publish=True):
        """
        Overridden to set the quality flag for LILY particles that are out of range.
        """
        sample = None
        if regex.match(line):
            if particle_class == particles.LilySampleParticle and self._param_dict.get(Parameter.LEVELING_FAILED):
                particle = particle_class(line, port_timestamp=timestamp, quality_flag=DataParticleValue.OUT_OF_RANGE)
            else:
                particle = particle_class(line, port_timestamp=timestamp)
            parsed_sample = particle.generate()

            if publish and self._driver_event:
                self._driver_event(DriverAsyncEvent.SAMPLE, parsed_sample)

            sample = json.loads(parsed_sample)

        return sample

    def _filter_capabilities(self, events):
        return [x for x in events if Capability.has(x)]

    def _build_command_dict(self):
        """
        Populate the command dictionary with commands.
        """
        self._cmd_dict.add(Capability.START_AUTOSAMPLE, display_name="Start autosample")
        self._cmd_dict.add(Capability.STOP_AUTOSAMPLE, display_name="Stop autosample")
        self._cmd_dict.add(Capability.ACQUIRE_STATUS, display_name="Acquire instrument status")
        self._cmd_dict.add(Capability.START_LEVELING, display_name="Start the LILY leveling sequence")
        self._cmd_dict.add(Capability.STOP_LEVELING, display_name="Stop the LILY leveling sequence")

    def _build_param_dict(self):
        """
        Populate the parameter dictionary with parameters.
        For each parameter key, add match string, match lambda function,
        and value formatting function for set commands.
        """
        my_regex = 'Not used'
        ro, rw = ParameterDictVisibility.READ_ONLY, ParameterDictVisibility.READ_WRITE
        _bool, _float, _int = ParameterDictType.BOOL, ParameterDictType.FLOAT, ParameterDictType.INT

        parameters = {
            Parameter.AUTO_RELEVEL: {
                'type': _bool,
                'display_name': 'Automatic Releveling Enabled',
                'visibility': rw,
                'startup_param': True,
            },
            Parameter.XTILT_TRIGGER: {
                'type': _float,
                'display_name': 'X-tilt Releveling Trigger',
                'units': Prefixes.MICRO + Units.RADIAN,
                'visibility': rw,
                'startup_param': True,
            },
            Parameter.YTILT_TRIGGER: {
                'type': _float,
                'display_name': 'Y-tilt Releveling Trigger',
                'visibility': rw,
                'startup_param': True,
            },
            Parameter.LEVELING_TIMEOUT: {
                'type': _int,
                'display_name': 'LILY Leveling Timeout',
                'units': Prefixes.MICRO + Units.RADIAN,
                'visibility': rw,
                'startup_param': True,
            },
            Parameter.LEVELING_FAILED: {
                'type': _bool,
                'display_name': 'LILY Leveling Failed',
                'value': False,
                'visibility': ro,
            },
            Parameter.HEAT_DURATION: {
                'type': _int,
                'display_name': 'Heater Run Time Duration',
                'units': Units.SECOND,
                'visibility': rw,
                'startup_param': True,
            },
            Parameter.OUTPUT_RATE: {
                'type': _int,
                'display_name': 'NANO Output Rate',
                'units': Units.HERTZ,
                'visibility': rw,
                'startup_param': True,
            },
            Parameter.SYNC_INTERVAL: {
                'type': _int,
                'display_name': 'NANO Time Sync Interval',
                'units': Units.SECOND,
                'visibility': rw,
                'startup_param': True,
            },
        }
        for param in parameters:
            self._param_dict.add(param, my_regex, None, None, **parameters[param])

    def _build_driver_dict(self):
        """
        Populate the driver dictionary with options
        """
        self._driver_dict.add(DriverDictKey.VENDOR_SW_COMPATIBLE, False)

    def _build_nano_output_rate_command(self, cmd, rate):
        return '{0:s}{1:d}{2:s}'.format(cmd, rate, NEWLINE)

    def _verify_set_values(self, params):
        """
        Verify supplied values are in range, if applicable
        """
        constraints = ParameterConstraint.dict()
        parameters = Parameter.reverse_dict()

        # step through the list of parameters
        for key, val in params.iteritems():
            # if constraint exists, verify we have not violated it
            constraint_key = parameters.get(key)
            if constraint_key in constraints:
                var_type, minimum, maximum = constraints[constraint_key]
                log.debug('SET CONSTRAINT: %s %r', key, constraints[constraint_key])
                try:
                    value = var_type(val)
                except ValueError:
                    raise InstrumentParameterException(
                        'Unable to verify type - parameter: %s value: %s expected: %s' % (key, val, var_type))
                if minimum is not None and maximum is not None:
                    if val < minimum or val > maximum:
                        raise InstrumentParameterException(
                            'Value out of range - parameter: %s value: %s min: %s max: %s'
                            % (key, val, minimum, maximum))

    def _set_params(self, *args, **kwargs):
        """
        Issue commands to the instrument to set various parameters
        """
        try:
            params = args[0]
        except IndexError:
            raise InstrumentParameterException('Set command requires a parameter dict.')

        self._verify_set_values(params)
        self._verify_not_readonly(*args, **kwargs)
        if Parameter.OUTPUT_RATE in params:
            self._update_params()

        old_config = self._param_dict.get_config()

        # all constraints met or no constraints exist, set the values
        for key, value in params.iteritems():
            try:
                self._param_dict.set_value(key, value)
            except KeyError:
                raise InstrumentParameterException('Received invalid parameter in SET: %s' % key)

        new_config = self._param_dict.get_config()

        if not old_config == new_config:
            log.debug('Config change: %r %r', old_config, new_config)
            if old_config[Parameter.OUTPUT_RATE] is not None:
                if int(old_config[Parameter.OUTPUT_RATE]) != int(new_config[Parameter.OUTPUT_RATE]):
                    self._do_cmd_no_resp(InstrumentCommand.NANO_SET_RATE, int(new_config[Parameter.OUTPUT_RATE]))
            self._driver_event(DriverAsyncEvent.CONFIG_CHANGE)

    def _update_params(self, *args, **kwargs):
        result, _ = self._do_cmd_resp(InstrumentCommand.NANO_DUMP1,
                                      response_regex=particles.NanoStatusParticle.regex_compiled())
        rate = int(re.search(r'NANO,\*TH:(\d+)', result).group(1))
        self._param_dict.set_value(Parameter.OUTPUT_RATE, rate)

    def _wakeup(self, timeout, delay=1):
        """
        Overriding _wakeup; does not apply to this instrument
        """

    def add_to_buffer(self, data):
        """
        Overriding base class to reduce logging due to NANO high data rate
        """
        # Update the line and prompt buffers.
        self._linebuf += data
        self._promptbuf += data
        self._last_data_timestamp = time.time()

        # If our buffer exceeds the max allowable size then drop the leading
        # characters on the floor.
        max_size = self._max_buffer_size()
        if len(self._linebuf) > max_size:
            self._linebuf = self._linebuf[max_size * -1:]

        # If our buffer exceeds the max allowable size then drop the leading
        # characters on the floor.
        if len(self._promptbuf) > max_size:
            self._promptbuf = self._linebuf[max_size * -1:]

    def _max_buffer_size(self):
        """
        Overriding base class to increase max buffer size
        """
        return MAX_BUFFER_SIZE

    def _remove_leveling_timeout(self):
        """
        Set up a leveling timer to make sure we don't stay in
        leveling state forever if something goes wrong
        """
        try:
            self._remove_scheduler(ScheduledJob.LEVELING_TIMEOUT)
        except KeyError:
            log.debug('Unable to remove LEVELING_TIMEOUT scheduled job, job does not exist.')

    def _schedule_leveling_timeout(self):
        """
        Set up a leveling timer to make sure we don't stay in
        leveling state forever if something goes wrong
        """
        self._remove_leveling_timeout()
        dt = datetime.datetime.now() + datetime.timedelta(seconds=self._param_dict.get(Parameter.LEVELING_TIMEOUT))
        job_name = ScheduledJob.LEVELING_TIMEOUT
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
        self._add_scheduler_event(ScheduledJob.LEVELING_TIMEOUT, ProtocolEvent.STOP_LEVELING)

    def _stop_autosample(self):
        self.leveling = False
        self._do_cmd_no_resp(InstrumentCommand.NANO_OFF)
        self._do_cmd_resp(InstrumentCommand.LILY_STOP_LEVELING, expected_prompt=Prompt.LILY_STOP_LEVELING)
        self._do_cmd_resp(InstrumentCommand.LILY_OFF, expected_prompt=Prompt.LILY_OFF)
        self._do_cmd_resp(InstrumentCommand.IRIS_OFF, expected_prompt=Prompt.IRIS_OFF)

    def _generic_response_handler(self, resp, prompt):
        return resp, prompt

    def _particle_to_dict(self, sample):
        sample_dict = {}
        values = sample.get(DataParticleKey.VALUES, [])
        for each in values:
            sample_dict[each[DataParticleKey.VALUE_ID]] = each[DataParticleKey.VALUE]
        return sample_dict

    def _check_for_autolevel(self, sample):
        if self._param_dict.get(Parameter.AUTO_RELEVEL) and self.get_current_state() == ProtocolState.AUTOSAMPLE:
            # Find the current X and Y tilt values
            # If they exceed the trigger parameters, begin autolevel
            relevel = False
            sample = self._particle_to_dict(sample)
            x_tilt = abs(sample[particles.LilySampleParticleKey.X_TILT])
            y_tilt = abs(sample[particles.LilySampleParticleKey.Y_TILT])
            if x_tilt > self._param_dict.get(Parameter.XTILT_TRIGGER) or \
                    y_tilt > self._param_dict.get(Parameter.YTILT_TRIGGER):
                self._async_raise_fsm_event(ProtocolEvent.START_LEVELING)

    def _failed_leveling(self, axis):
        log.error('Detected leveling error in %s axis!', axis)
        # Read only parameter, must be set outside of handler
        self._param_dict.set_value(Parameter.LEVELING_FAILED, True)
        # Use the handler to disable auto relevel to raise a config change event if needed.
        self._handler_command_set({Parameter.AUTO_RELEVEL: False})
        raise InstrumentDataException('LILY Leveling (%s) Failed.  Disabling auto relevel' % axis)

    def _check_completed_leveling(self, sample):
        sample = self._particle_to_dict(sample)
        status = sample[particles.LilyLevelingParticleKey.STATUS]
        if status is not None:
            # Leveling status update received
            # If leveling complete, send STOP_LEVELING, set the _leveling_failed flag to False
            if 'Leveled' in status:
                if self._param_dict.get(Parameter.LEVELING_FAILED):
                    self._handler_command_set({Parameter.LEVELING_FAILED: False})
                    self._driver_event(DriverAsyncEvent.CONFIG_CHANGE)
                self._async_raise_fsm_event(ProtocolEvent.STOP_LEVELING)
            # Leveling X failed!  Set the flag and raise an exception to notify the operator
            # and disable auto leveling. Let the instrument attempt to level
            # in the Y axis.
            elif 'X Axis out of range' in status:
                self._failed_leveling('X')
            # Leveling X failed!  Set the flag and raise an exception to notify the operator
            # and disable auto leveling. Send STOP_LEVELING
            elif 'Y Axis out of range' in status:
                self._async_raise_fsm_event(ProtocolEvent.STOP_LEVELING)
                self._failed_leveling('Y')

    def _check_pps_sync(self, sample):
        sample = self._particle_to_dict(sample)
        pps_sync = sample[particles.NanoSampleParticleKey.PPS_SYNC] == 'P'
        if pps_sync and not self.has_pps:
            # pps sync regained, sync the time
            self._async_raise_fsm_event(ProtocolEvent.NANO_TIME_SYNC)
        elif self.has_pps:
            self.has_pps = False

    ########################################################################
    # Unknown handlers.
    ########################################################################

    def _handler_unknown_discover(self, *args, **kwargs):
        return ProtocolState.COMMAND, ResourceAgentState.IDLE

    ########################################################################
    # Autosample handlers.
    ########################################################################

    def _handler_autosample_enter(self, *args, **kwargs):
        """
        Enter autosample state.
        """
        self._init_params()
        self._driver_event(DriverAsyncEvent.STATE_CHANGE)

    def _handler_autosample_stop_autosample(self, *args, **kwargs):
        return ProtocolState.COMMAND, (ResourceAgentState.COMMAND, None)

    ########################################################################
    # Command handlers.
    ########################################################################

    def _handler_command_enter(self, *args, **kwargs):
        """
        Enter command state.
        """
        self._init_params()
        self._stop_autosample()
        self._driver_event(DriverAsyncEvent.STATE_CHANGE)

    def _handler_command_get(self, *args, **kwargs):
        return self._handler_get(*args, **kwargs)

    def _handler_command_set(self, *args, **kwargs):
        """
        Perform a set command.
        @param args[0] parameter : value dict.
        @retval (next_state, result) tuple, (None, None).
        @throws InstrumentParameterException if missing set parameters, if set parameters not ALL and
        not a dict, or if parameter can't be properly formatted.
        """
        next_state = None
        result = None
        startup = False

        if len(args) < 1:
            raise InstrumentParameterException('Set command requires a parameter dict.')
        params = args[0]
        if len(args) > 1:
            startup = args[1]

        if not isinstance(params, dict):
            raise InstrumentParameterException('Set parameters not a dict.')
        if not isinstance(startup, bool):
            raise InstrumentParameterException('Startup not a bool.')

        self._set_params(params, startup)
        return next_state, result

    def _handler_command_start_direct(self):
        """
        Start direct access
        """
        return ProtocolState.DIRECT_ACCESS, (ResourceAgentState.DIRECT_ACCESS, None)

    def _handler_command_start_autosample(self):
        self._do_cmd_resp(InstrumentCommand.LILY_ON, expected_prompt=Prompt.LILY_ON)
        self._do_cmd_no_resp(InstrumentCommand.NANO_ON)
        self._do_cmd_resp(InstrumentCommand.IRIS_ON, expected_prompt=Prompt.IRIS_ON)
        return ProtocolState.AUTOSAMPLE, (ResourceAgentState.STREAMING, None)

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
        """
        self._do_cmd_direct(data)
        self._sent_cmds.append(data)
        return None, (None, None)

    def _handler_direct_access_stop_direct(self):
        """
        """
        next_state, next_agent_state = self._handler_unknown_discover()
        if next_state == DriverProtocolState.COMMAND:
            next_agent_state = ResourceAgentState.COMMAND

        return next_state, (next_agent_state, None)

    ########################################################################
    # Generic handlers.
    ########################################################################

    def _handler_generic_enter(self, *args, **kwargs):
        """
        Generic enter state handler
        """
        # Tell driver superclass to send a state change event.
        # Superclass will query the state.
        self._driver_event(DriverAsyncEvent.STATE_CHANGE)

    def _handler_generic_exit(self, *args, **kwargs):
        """
        Generic exit state handler
        """

    def _handler_start_leveling(self):
        if not self.leveling:
            self._schedule_leveling_timeout()
            self._do_cmd_resp(InstrumentCommand.LILY_START_LEVELING, expected_prompt=Prompt.LILY_START_LEVELING)
            self.leveling = True
        return None, (None, None)

    def _handler_stop_leveling(self):
        if self.leveling:
            self._remove_leveling_timeout()
            self.leveling = False
            self._do_cmd_resp(InstrumentCommand.LILY_STOP_LEVELING, expected_prompt=Prompt.LILY_STOP_LEVELING)
            if self.get_current_state() == ProtocolState.AUTOSAMPLE:
                self._do_cmd_resp(InstrumentCommand.LILY_ON, expected_prompt=Prompt.LILY_ON)
        return None, (None, None)

    def _handler_acquire_status(self, *args, **kwargs):
        """
        We generate these particles here to avoid the chunker.  This allows us to process status
        messages with embedded messages from the other parts of the instrument.
        """
        ts = ntplib.system_to_ntp_time(time.time())

        for command, particle_class in [
            (InstrumentCommand.SYST_DUMP1, particles.SystStatusParticle),
            (InstrumentCommand.LILY_DUMP1, particles.LilyStatusParticle1),
            (InstrumentCommand.LILY_DUMP2, particles.LilyStatusParticle2),
            (InstrumentCommand.IRIS_DUMP1, particles.IrisStatusParticle1),
            (InstrumentCommand.IRIS_DUMP2, particles.IrisStatusParticle2),
            (InstrumentCommand.NANO_DUMP1, particles.NanoStatusParticle),
        ]:
            result, _ = self._do_cmd_resp(command, response_regex=particle_class.regex_compiled())
            self._extract_sample(particle_class, particle_class.regex_compiled(), result, ts)

        return None, (None, None)

    def _handler_time_sync(self):
        """
        Syncing time starts autosample...
        """
        self._do_cmd_resp(InstrumentCommand.NANO_SET_TIME)
        if self.get_current_state() == ProtocolState.COMMAND:
            self._do_cmd_no_resp(InstrumentCommand.NANO_OFF)
