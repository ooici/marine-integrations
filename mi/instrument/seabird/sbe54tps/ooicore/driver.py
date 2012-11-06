"""
@package mi.instrument.seabird.sbe54tps.ooicore.driver
@file /Users/unwin/OOI/Workspace/code/marine-integrations/mi/instrument/seabird/sbe54tps/ooicore/driver.py
@author Roger Unwin
@brief Driver for the ooicore
Release notes:

10.180.80.170:2101 Instrument
10.180.80.170:2102 Digi
Done
"""

__author__ = 'Roger Unwin'
__license__ = 'Apache 2.0'

import string

from mi.core.common import BaseEnum
from mi.core.instrument.instrument_protocol import CommandResponseInstrumentProtocol
from mi.core.instrument.instrument_fsm import InstrumentFSM
from mi.core.instrument.instrument_driver import SingleConnectionInstrumentDriver
from mi.core.instrument.instrument_driver import DriverEvent
from mi.core.instrument.instrument_driver import DriverAsyncEvent
from mi.core.instrument.instrument_driver import DriverProtocolState
from mi.core.instrument.instrument_driver import DriverParameter

from mi.core.log import get_logger ; log = get_logger()


# newline.
NEWLINE = '\r\n'

# default timeout.
TIMEOUT = 10

STATUS_DATA_REGEX = r"(<StatusData DeviceType='.*?</StatusData>)"
STATUS_DATA_REGEX_MATCHER = re.compile(STATUS_DATA_REGEX)



# Packet config\
STREAM_NAME_PARSED = DataParticleValue.PARSED
STREAM_NAME_RAW = DataParticleValue.RAW
PACKET_CONFIG = [STREAM_NAME_PARSED, STREAM_NAME_RAW]

PACKET_CONFIG = {
    STREAM_NAME_PARSED : 'ctd_parsed_param_dict',
    STREAM_NAME_RAW : 'ctd_raw_param_dict'
}



# Device specific parameters.
class InstrumentCmds(BaseEnum):
    """
    Instrument Commands
    These are the commands that according to the science profile must be supported.
    """


    #### Artificial Constructed Commands for Driver ####
    #SET = "set"
    #GET = "get"

    ################
    #### Status ####
    ################
    GET_CONFIGURATION_DATA = "GetCD"
    GET_STATUS_DATA = "GetSD"
    GET_EVENT_COUNTER_DATA = "GetEC"
    GET_HARDWARE_DATA = "GetHD"

    ###############################
    #### Setup - Communication ####
    ###############################
    # SET_BAUD_RATE = "SetBaudRate"                                         # DO NOT IMPLEMENT

    #########################
    #### Setup - General ####
    #########################
    # INITIALIZE = "*Init"                                                  # DO NOT IMPLEMENT
    SET_TIME = "SetTime"
    SET_BATTERY_TYPE = "SetBatteryType"

    #############################
    #### Setup – Data Output ####
    #############################
    ENABLE_ALERTS ="SetEnableAlerts"

    ##################
    #### Sampling ####
    ##################
    INIT_LOGGING = "InitLogging"
    START_SAMPLING = "Start"
    STOP_SAMPLING = "Stop"
    SAMPLE_REFERENCE_OSCILLATOR = "SampleRefOsc"

    ################################
    #### Data Access and Upload ####
    ################################
    # GET_SAMPLES = "GetSamples"                                            # DO NOT IMPLEMENT
    # GET_LAST_PRESSURE_SAMPLES = "GetLastPSamples"                         # DO NOT IMPLEMENT
    # GET_LAST_REFERENCE_SAMPLES = "GetLastRSamples"                        # DO NOT IMPLEMENT
    # GET_REFERENCE_SAMPLES_LIST = "GetRSampleList"                         # DO NOT IMPLEMENT
    SET_UPLOAD_TYPE = "SetUploadType"
    # UPLOAD_DATA = "UploadData"                                            # DO NOT IMPLEMENT

    ####################
    #### Diagnostic ####
    ####################
    RESET_EC = "ResetEC"
    TEST_EPROM = "TestEeprom"
    # TEST_REFERENCE_OSCILLATOR = "TestRefOsc"                              # DO NOT IMPLEMENT

    ##################################
    #### Calibration Coefficients ####
    ##################################
    # SetAcqOscCalDate=S        S= acquisition crystal calibration date.
    # SET_ACQUISITION_OSCILLATOR_CALIBRATION_DATE = "SetAcqOscCalDate"      # DO NOT IMPLEMENT

    # SetFRA0=F                 F= acquisition crystal frequency A0.
    # SET_ACQUISITION_FREQUENCY_A0 = "SetFRA0"                              # DO NOT IMPLEMENT

    # SetFRA1=F                 F= acquisition crystal frequency A1.
    # SET_ACQUISITION_FREQUENCY_A1 = "SetFRA1"                              # DO NOT IMPLEMENT

    # SetFRA2=F                 F= acquisition crystal frequency A2.
    # SET_ACQUISITION_FREQUENCY_A2 = "SetFRA2"                              # DO NOT IMPLEMENT

    # SetFRA3=F                 F= acquisition crystal frequency A3.
    # SET_ACQUISITION_FREQUENCY_A3 = "SetFRA3"                              # DO NOT IMPLEMENT

    # SetPressureCalDate=S      S= pressure sensor calibration date.
    # SET_PRESSURE_CALIBRATION_DATE = "SetPressureCalDate"                  # DO NOT IMPLEMENT

    # SetPressureSerialNum=S    S= pressure sensor serial number.
    # SET_PRESSURE_SERIAL_NUMBER = "SetPressureSerialNum"                   # DO NOT IMPLEMENT

    # SetPRange=F               F= pressure sensor full scale range (psia).
    # SET_PRESSURE_SENSOR_FULL_SCALE_RANGE = "SetPRange"                    # DO NOT IMPLEMENT

    # SetPOffset=F              F= pressure sensor offset (psia).
    # SET_PRESSURE_SENSOR_OFFSET = "SetPOffset"                             # DO NOT IMPLEMENT

    # SetPU0=F                  F= pressure sensor U0.
    # SET_PRESSURE_SENSOR_U0 = "SetPU0"                                     # DO NOT IMPLEMENT

    # SetPY1=F                  F= pressure sensor Y1.
    # SET_PRESSURE_SENSOR_Y1 = "SetPY1"                                     # DO NOT IMPLEMENT

    # SetPY2=F                  F= pressure sensor Y2.
    # SET_PRESSURE_SENSOR_Y2 = "SetPY2"                                     # DO NOT IMPLEMENT

    # SetPY3=F                  F= pressure sensor Y3.
    # SET_PRESSURE_SENSOR_Y3 = "SetPY3"                                     # DO NOT IMPLEMENT

    # SetPC1=F                  F= pressure sensor C1.
    # SET_PRESSURE_SENSOR_C1 = "SetPC1"                                     # DO NOT IMPLEMENT

    # SetPC2=F                  F= pressure sensor C2.
    # SET_PRESSURE_SENSOR_C2 = "SetPC2"                                     # DO NOT IMPLEMENT

    # SetPC3=F                  F= pressure sensor C3.
    # SET_PRESSURE_SENSOR_C3 = "SetPC3"                                     # DO NOT IMPLEMENT

    # SetPD1=F                  F= pressure sensor D1.
    # SET_PRESSURE_SENSOR_D1 = "SetPD1"                                     # DO NOT IMPLEMENT

    # SetPD2=F                  F= pressure sensor D2.
    # SET_PRESSURE_SENSOR_D2 = "SetPD2"                                     # DO NOT IMPLEMENT

    # SetPT1=F                  F= pressure sensor T1.
    # SET_PRESSURE_SENSOR_T1 = "SetPT1"                                     # DO NOT IMPLEMENT

    # SetPT2=F                  F= pressure sensor T2.
    # SET_PRESSURE_SENSOR_T2 = "SetPT2"                                     # DO NOT IMPLEMENT

    # SetPT3=F                  F= pressure sensor T3.
    # SET_PRESSURE_SENSOR_T3 = "SetPT3"                                     # DO NOT IMPLEMENT

    # SetPT4=F                  F= pressure sensor T4.
    # SET_PRESSURE_SENSOR_T4 = "SetPT4"                                     # DO NOT IMPLEMENT




class ProtocolState(BaseEnum):
    """
    Protocol states
    enum.
    """
    UNKNOWN = DriverProtocolState.UNKNOWN
    COMMAND = DriverProtocolState.COMMAND
    AUTOSAMPLE = DriverProtocolState.AUTOSAMPLE
    DIRECT_ACCESS = DriverProtocolState.DIRECT_ACCESS
    #TEST = DriverProtocolState.TEST
    #CALIBRATE = DriverProtocolState.CALIBRATE


class ProtocolEvent(BaseEnum):
    """
    Protocol events
    """
    FORCE_STATE = DriverEvent.FORCE_STATE

    ENTER = DriverEvent.ENTER
    EXIT = DriverEvent.EXIT
    START_DIRECT = DriverEvent.START_DIRECT
    STOP_DIRECT = DriverEvent.STOP_DIRECT
    EXECUTE_DIRECT = DriverEvent.EXECUTE_DIRECT

    DISCOVER = DriverEvent.DISCOVER
    START_AUTOSAMPLE = DriverEvent.START_AUTOSAMPLE
    STOP_AUTOSAMPLE = DriverEvent.STOP_AUTOSAMPLE

    CLOCK_SYNC = DriverEvent.CLOCK_SYNC

    ACQUIRE_SAMPLE = DriverEvent.ACQUIRE_SAMPLE
    ACQUIRE_STATUS = DriverEvent.ACQUIRE_STATUS

    INIT_LOGGING = 'PROTOCOL_EVENT_INIT_LOGGING'

    # Do we need these here?
    GET = DriverEvent.GET
    SET = DriverEvent.SET

    PING_DRIVER = DriverEvent.PING_DRIVER





######################################### PARTICLES #############################


class SBE54tpsStatusDataParticleKey(BaseEnum):
    DEVICE_TYPE = "device_type"
    SERIAL_NUMBER = "serial_number"
    DATE_TIME = "date_time"
    EVENT_COUNT = "event_count"
    MAIN_SUPPLY_VOLTAGE = "main_supply_voltage"
    NUMBER_OF_SAMPLES = "number_of_samples"
    BYTES_USED = "bytes_used"
    BYTES_FREE = "bytes_free"


class SBE54tpsStatusDataParticle(DataParticle):
    """
    Routines for parsing raw data into a data particle structure. Override
    the building of values, and the rest should come along for free.
    """
    def _build_parsed_values(self):
        """
        Take something in the autosample format and split it into
        values with appropriate tags

        @throws SampleException If there is a problem with sample creation
        """




'''
S>getsd
getsd


<StatusData DeviceType='SBE54' SerialNumber='05400012'>
<DateTime>2012-11-06T10:55:44</DateTime>
<EventSummary numEvents='573'/>
<Power>
<MainSupplyVoltage>23.3</MainSupplyVoltage>
</Power>
<MemorySummary>
<Samples>22618</Samples>
<Bytes>341504</Bytes>
<BytesFree>133876224</BytesFree>
</MemorySummary>
</StatusData>
<Executed/>
S>
'''

        single_var_matchers  = {
            SBE54tpsStatusDataParticleKey.DEVICE_TYPE:
                re.compile(r"StatusData DeviceType='([^']+'"),
            SBE54tpsStatusDataParticleKey.SERIAL_NUMBER:
                re.compile(r"SerialNumber='(\d+)'"),
            SBE54tpsStatusDataParticleKey.DATE_TIME:
                re.compile(r"<DateTime>([^<]+)</DateTime>"),
            SBE54tpsStatusDataParticleKey.EVENT_COUNT:
                re.compile(r"<EventSummary numEvents='(\d+)'/>"),
            SBE54tpsStatusDataParticleKey.MAIN_SUPPLY_VOLTAGE:
                re.compile(r"<MainSupplyVoltage>(\d+)</MainSupplyVoltage>"),
            SBE54tpsStatusDataParticleKey.NUMBER_OF_SAMPLES:
                re.compile(r"<Samples>(\d+)</Samples>"),
            SBE54tpsStatusDataParticleKey.BYTES_USED:
                re.compile(r"<Bytes>(\d+)</Bytes>"),
            SBE54tpsStatusDataParticleKey.BYTES_FREE:
                re.compile(r"<BytesFree>(\d+)</BytesFree>")
        }

        # Initialize

        single_var_matches  = {
            SBE54tpsStatusDataParticleKey.DEVICE_TYPE: None,
            SBE54tpsStatusDataParticleKey.SERIAL_NUMBER: None,
            SBE54tpsStatusDataParticleKey.DATE_TIME: None,
            SBE54tpsStatusDataParticleKey.EVENT_COUNT: None,
            SBE54tpsStatusDataParticleKey.MAIN_SUPPLY_VOLTAGE: None,
            SBE54tpsStatusDataParticleKey.NUMBER_OF_SAMPLES: None,
            SBE54tpsStatusDataParticleKey.BYTES_USED: None,
            SBE54tpsStatusDataParticleKey.BYTES_FREE: None
        }

        for line in self.raw_data.split(NEWLINE):
            for (key, matcher) in single_var_matchers:
                match = single_var_matchers[key].match(line)
                if match:

                    # str
                    if key in [
                        SBE54tpsStatusDataParticleKey.DEVICE_TYPE
                    ]:
                        single_var_matches[key] = match(1)
                    # int
                    elif key in [
                        SBE54tpsStatusDataParticleKey.SERIAL_NUMBER
                    ]:
                        single_var_matches[key] = int(match(1))
                    #float
                    elif key in [

                    ]:
                        single_var_matches[key] = float(match(1))
                    # datetime
                    elif key in [
                        SBE54tpsStatusDataParticleKey.DATE_TIME
                    ]:
                        single_var_matches[key] = float(match(1))

        return result



S>getcd
getcd
<ConfigurationData DeviceType='SBE54' SerialNumber='05400012'>
<CalibrationCoefficients>
<AcqOscCalDate>2012-02-20</AcqOscCalDate>
<FRA0>5.999926E+06</FRA0>
<FRA1>5.792290E-03</FRA1>
<FRA2>-1.195664E-07</FRA2>
<FRA3>7.018589E-13</FRA3>
<PressureSerialNum>121451</PressureSerialNum>
<PressureCalDate>2011-06-01</PressureCalDate>
<pu0>5.820407E+00</pu0>
<py1>-3.845374E+03</py1>
<py2>-1.078882E+04</py2>
<py3>0.000000E+00</py3>
<pc1>-2.700543E+04</pc1>
<pc2>-1.738438E+03</pc2>
<pc3>7.629962E+04</pc3>
<pd1>3.739600E-02</pd1>
<pd2>0.000000E+00</pd2>
<pt1>3.027306E+01</pt1>
<pt2>2.231025E-01</pt2>
<pt3>5.398972E+01</pt3>
<pt4>1.455506E+02</pt4>
<poffset>0.000000E+00</poffset>
<prange>6.000000E+03</prange>
</CalibrationCoefficients>
<Settings
batteryType='0'
baudRate='9600'
enableAlerts='0'
uploadType='0'
samplePeriod='15'
/>
</ConfigurationData>
<Executed/>






S>getec
getec
<EventSummary numEvents='573' maxStack='354'/>
<EventList DeviceType='SBE54' SerialNumber='05400012'>
<Event type='PowerOnReset' count='25'/>
<Event type='PowerFailReset' count='25'/>
<Event type='SerialByteErr' count='9'/>
<Event type='CMDBuffOflow' count='1'/>
<Event type='SerialRxOflow' count='255'/>
<Event type='LowBattery' count='255'/>
<Event type='SignalErr' count='1'/>
<Event type='Error10' count='1'/>
<Event type='Error12' count='1'/>
</EventList>
<Executed/>
S>

S>gethd
gethd
<HardwareData DeviceType='SBE54' SerialNumber='05400012'>
<Manufacturer>Sea-Bird Electronics, Inc</Manufacturer>
<FirmwareVersion>SBE54 V1.3-6MHZ</FirmwareVersion>
<FirmwareDate>Mar 22 2007</FirmwareDate>
<HardwareVersion>41477A.1</HardwareVersion>
<HardwareVersion>41478A.1T</HardwareVersion>
<PCBSerialNum>NOT SET</PCBSerialNum>
<PCBSerialNum>NOT SET</PCBSerialNum>
<PCBType>1</PCBType>
<MfgDate>Jun 27 2007</MfgDate>
</HardwareData>
<Executed/>
S>




# Device specific parameters.
class Parameter(DriverParameter):
    """
    Device parameters
    """

    ACQUISITION_OSCILLATOR_CALIBRATION_DATE = "AcqOscCalDate"
    ACQUISITION_FREQUENCY_A0 = "FRA0"
    ACQUISITION_FREQUENCY_A1 = "FRA1"
    ACQUISITION_FREQUENCY_A2 = "FRA2"
    ACQUISITION_FREQUENCY_A3 = "FRA3"
    PRESSURE_CALIBRATION_DATE = "PressureCalDate"
    PRESSURE_SERIAL_NUMBER = "PressureSerialNum"
    PRESSURE_SENSOR_FULL_SCALE_RANGE = "prange"     # (psia)
    PRESSURE_SENSOR_OFFSET = "poffset"              # (psia)

    PRESSURE_SENSOR_U0 = "pu0"
    PRESSURE_SENSOR_Y1 = "py1"
    PRESSURE_SENSOR_Y2 = "py2"
    PRESSURE_SENSOR_Y3 = "py3"
    PRESSURE_SENSOR_C1 = "pc1"
    PRESSURE_SENSOR_C2 = "pc2"
    PRESSURE_SENSOR_C3 = "pc3"
    PRESSURE_SENSOR_D1 = "pd1"
    PRESSURE_SENSOR_D2 = "pd2"
    PRESSURE_SENSOR_T1 = "pt1"
    PRESSURE_SENSOR_T2 = "pt2"
    PRESSURE_SENSOR_T3 = "pt3"
    PRESSURE_SENSOR_T4 = "pt4"

    BATTERY_TYPE = "batteryType"
    BAUD_RATE = "baudRate"
    ENABLE_ALERTS = "enableAlerts"
    UPLOAD_TYPE = "uploadType"
    SAMPLE_PERIOD = "samplePeriod"








to do aquire sample, will need to:
stop
SetSamplePeriod=1
collect a sample
stop
restore sample period.


######################################### /PARTICLES #############################

# Device prompts.
class Prompt(BaseEnum):
    """
    io prompts.
    """

    COMMAND = "<Executed/>\r\nS>"
    BAD_COMMAND = "<Executed/>\r\nS>" # More to this, but it depends on the error


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

###############################################################################
# Protocol
################################################################################

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
        self._protocol_fsm.add_handler(ProtocolState.UNKNOWN, ProtocolEvent.START_DIRECT, self._handler_command_start_direct)
        self._protocol_fsm.add_handler(ProtocolState.COMMAND, ProtocolEvent.ENTER, self._handler_command_enter)
        self._protocol_fsm.add_handler(ProtocolState.COMMAND, ProtocolEvent.EXIT, self._handler_command_exit)
        self._protocol_fsm.add_handler(ProtocolState.COMMAND, ProtocolEvent.START_DIRECT, self._handler_command_start_direct)
        self._protocol_fsm.add_handler(ProtocolState.DIRECT_ACCESS, ProtocolEvent.ENTER, self._handler_direct_access_enter)
        self._protocol_fsm.add_handler(ProtocolState.DIRECT_ACCESS, ProtocolEvent.EXIT, self._handler_direct_access_exit)
        self._protocol_fsm.add_handler(ProtocolState.DIRECT_ACCESS, ProtocolEvent.STOP_DIRECT, self._handler_direct_access_stop_direct)
        self._protocol_fsm.add_handler(ProtocolState.DIRECT_ACCESS, ProtocolEvent.EXECUTE_DIRECT, self._handler_direct_access_execute_direct)

        # Construct the parameter dictionary containing device parameters,
        # current parameter values, and set formatting functions.
        self._build_param_dict()

        # Add build handlers for device commands.

        # Add response handlers for device commands.

       # Add sample handlers.

        # State state machine in UNKNOWN state.
        self._protocol_fsm.start(ProtocolState.UNKNOWN)

        # commands sent sent to device to be filtered in responses for telnet DA
        self._sent_cmds = []



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
        (ProtocolState.COMMAND, None)

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

    def _handler_command_exit(self, *args, **kwargs):
        """
        Exit command state.
        """
        pass

    def _handler_command_start_direct(self):
        """
        """
        next_state = None
        result = None

        next_state = ProtocolState.DIRECT_ACCESS

        return (next_state, result)

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

        self._do_cmd_direct(data)

        # add sent command to list for 'echo' filtering in callback
        self._sent_cmds.append(data)

        return (next_state, result)

    def _handler_direct_access_stop_direct(self):
        """
        @throw InstrumentProtocolException on invalid command
        """
        next_state = None
        result = None

        next_state = ProtocolState.COMMAND

        return (next_state, result)

    def _build_param_dict(self):
        """
        Populate the parameter dictionary with parameters.
        For each parameter key, add match stirng, match lambda function,
        and value formatting function for set commands.
        """
        # Add parameter handlers to parameter dict.

    def got_data(self, data):
        """
        Callback for receiving new data from the device.
        """
        # got data callback for direct access only
        # TODO: should we have a generic got_data in the base class that does something useful??  Is this code
        # TODO: instrument specific?
        if self.get_current_state() == ProtocolState.DIRECT_ACCESS:
            # direct access mode
            if len(data) > 0:
                log.debug("Protocol._got_data(): <" + data + ">")
                # check for echoed commands from instrument (TODO: this should only be done for telnet?)
                if len(self._sent_cmds) > 0:
                    # there are sent commands that need to have there echoes filtered out
                    oldest_sent_cmd = self._sent_cmds[0]
                    if string.count(data, oldest_sent_cmd) > 0:
                        # found a command echo, so remove it from data and delete the command form list
                        data = string.replace(data, oldest_sent_cmd, "", 1)
                        self._sent_cmds.pop(0)
                if len(data) > 0 and self._driver_event:
                    self._driver_event(DriverAsyncEvent.DIRECT_ACCESS, data)
                    # TODO: what about logging this as an event?
            return


