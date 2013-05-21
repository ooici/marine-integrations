from mi.instrument.teledyne.workhorse_monitor_75_khz.driver import WorkhorseInstrumentDriver
from mi.instrument.teledyne.workhorse_monitor_75_khz.driver import WorkhorseProtocol
from mi.instrument.teledyne.workhorse_monitor_75_khz.driver import Prompt
from mi.instrument.teledyne.workhorse_monitor_75_khz.driver import NEWLINE
from mi.core.log import get_logger ; log = get_logger()
import socket
import time

from mi.core.instrument.protocol_param_dict import ParameterDictVisibility
from mi.core.instrument.protocol_param_dict import ParameterDictType
from mi.instrument.teledyne.workhorse_monitor_75_khz.driver import Parameter

class InstrumentDriver(WorkhorseInstrumentDriver):
    """
    Specialization for this version of the workhorse_monitor_75_khz driver
    """
    def __init__(self, evt_callback):
        """
        InstrumentDriver constructor.
        @param evt_callback Driver process event callback.
        """
        #Construct superclass.
        WorkhorseInstrumentDriver.__init__(self, evt_callback)

    def _build_protocol(self):
        """
        Construct the driver protocol state machine.
        """
        self._protocol = Protocol(Prompt, NEWLINE, self._driver_event)
        log.debug("self._protocol = " + repr(self._protocol))


class Protocol(WorkhorseProtocol):
    """
    Specialization for this version of the workhorse_monitor_75_khz driver
    """
    def __init__(self, prompts, newline, driver_event):
        log.debug("IN Protocol.__init__")
        WorkhorseProtocol.__init__(self, prompts, newline, driver_event)

    def _build_param_dict(self):
        """
        Populate the parameter dictionary with sbe26plus parameters.
        For each parameter key, add match stirng, match lambda function,
        and value formatting function for set commands.
        """

        self._param_dict.add(Parameter.SERIAL_DATA_OUT,
            r'CD = (\d\d\d \d\d\d \d\d\d) \-+ Serial Data Out ',
            lambda match: str(match.group(1)),
            str,
            type=ParameterDictType.STRING,
            display_name="serial data out",
            visibility=ParameterDictVisibility.READ_ONLY)

        self._param_dict.add(Parameter.SERIAL_FLOW_CONTROL,
            r'CF = (\d+) \-+ Flow Ctrl ',
            lambda match: str(match.group(1)),
            str,
            type=ParameterDictType.STRING,
            display_name="serial flow control",
            startup_param=True,
            direct_access=False,
            visibility=ParameterDictVisibility.IMMUTABLE,
            default_value='11110')

        self._param_dict.add(Parameter.BANNER,
            r'CH = (\d) \-+ Suppress Banner',
            lambda match:  bool(int(match.group(1), base=10)),
            self._bool_to_int, # _reverse_bool_to_int
            type=ParameterDictType.BOOL,
            display_name="banner",
            startup_param=True,
            visibility=ParameterDictVisibility.IMMUTABLE,
            default_value=0)

        self._param_dict.add(Parameter.INSTRUMENT_ID,
            r'CI = (\d+) \-+ Instrument ID ',
            lambda match: int(match.group(1), base=10),
            self._int_to_string,
            type=ParameterDictType.INT,
            display_name="instrument id",
            startup_param=True,
            default_value=0)

        self._param_dict.add(Parameter.SLEEP_ENABLE,
            r'CL = (\d) \-+ Sleep Enable',
            lambda match: int(match.group(1), base=10),
            self._int_to_string,
            type=ParameterDictType.INT,
            display_name="sleep enable",
            startup_param=True,
            default_value=False)

        self._param_dict.add(Parameter.SAVE_NVRAM_TO_RECORDER,
            r'CN = (\d) \-+ Save NVRAM to recorder',
            lambda match: bool(int(match.group(1), base=10)),
            self._bool_to_int,
            type=ParameterDictType.BOOL,
            display_name="save nvram to recorder",
            startup_param=True,
            default_value=True,
            visibility=ParameterDictVisibility.IMMUTABLE)

        self._param_dict.add(Parameter.POLLED_MODE,
            r'CP = (\d) \-+ PolledMode ',
            lambda match: bool(int(match.group(1), base=10)),
            self._bool_to_int,
            type=ParameterDictType.BOOL,
            display_name="polled mode",
            startup_param=True,
            default_value=False)

        self._param_dict.add(Parameter.XMIT_POWER,
            r'CQ = (\d+) \-+ Xmt Power ',
            lambda match: int(match.group(1), base=10),
            self._int_to_string,
            type=ParameterDictType.INT,
            display_name="xmit power",
            startup_param=True,
            default_value=255)

        self._param_dict.add(Parameter.SPEED_OF_SOUND,
            r'EC = (\d+) \-+ Speed Of Sound',
            lambda match: int(match.group(1), base=10),
            self._int_to_string,
            type=ParameterDictType.INT,
            display_name="speed of sound",
            startup_param=True,
            default_value=1485)

        self._param_dict.add(Parameter.PITCH,
            r'EP = ([\+\-\d]+) \-+ Tilt 1 Sensor ',
            lambda match: int(match.group(1), base=10),
            self._int_to_string,
            type=ParameterDictType.INT,
            display_name="pitch",
            startup_param=True,
            default_value=0)

        self._param_dict.add(Parameter.ROLL,
            r'ER = ([\+\-\d]+) \-+ Tilt 2 Sensor ',
            lambda match: int(match.group(1), base=10),
            self._int_to_string,
            type=ParameterDictType.INT,
            display_name="roll",
            startup_param=True,
            default_value=0)

        self._param_dict.add(Parameter.SALINITY,
            r'ES = (\d+) \-+ Salinity ',
            lambda match: int(match.group(1), base=10),
            self._int_to_string,
            type=ParameterDictType.INT,
            display_name="salinity",
            startup_param=True,
            default_value=35)

        self._param_dict.add(Parameter.COORDINATE_TRANSFORMATION,
            r'EX = (\d+) \-+ Coord Transform ',
            lambda match: str(match.group(1)),
            str,
            type=ParameterDictType.STRING,
            display_name="coordinate transformation",
            startup_param=True,
            default_value='11111')

        self._param_dict.add(Parameter.SENSOR_SOURCE,
            r'EZ = (\d+) \-+ Sensor Source ',
            lambda match: str(match.group(1)),
            str,
            type=ParameterDictType.STRING,
            display_name="sensor source")

        self._param_dict.add(Parameter.TIME_PER_ENSEMBLE,
            r'TE (\d\d:\d\d:\d\d.\d\d) \-+ Time per Ensemble ',
            lambda match: str(match.group(1)),
            str,
            type=ParameterDictType.STRING,
            display_name="time per ensemble",
            startup_param=True,
            default_value='00:00:00.00')

        self._param_dict.add(Parameter.TIME_OF_FIRST_PING,
            r'TG (..../../..,..:..:..) - Time of First Ping ',
            lambda match: str(match.group(1)),
            str,
            type=ParameterDictType.STRING,
            display_name="time of first ping")
            #startup_param=True,
            #default_value='****/**/**,**:**:**')

        self._param_dict.add(Parameter.TIME_PER_PING,
            r'TP (\d\d:\d\d.\d\d) \-+ Time per Ping',
            lambda match: str(match.group(1)),
            str,
            type=ParameterDictType.STRING,
            display_name="time per ping",
            startup_param=True,
            default_value='00:01.00')

        self._param_dict.add(Parameter.TIME,
            r'TT (\d\d\d\d/\d\d/\d\d,\d\d:\d\d:\d\d) \- Time Set ',
            lambda match: str(match.group(1) + " UTC"),
            str,
            type=ParameterDictType.STRING,
            display_name="time",
            expiration=1,
            visibility=ParameterDictVisibility.READ_ONLY)

        self._param_dict.add(Parameter.FALSE_TARGET_THRESHOLD,
            r'WA (\d+,\d+) \-+ False Target Threshold ',
            lambda match: str(match.group(1)),
            str,
            type=ParameterDictType.STRING,
            display_name="false target threshold",
            startup_param=True,
            default_value='050,001')

        self._param_dict.add(Parameter.BANDWIDTH_CONTROL,
            r'WB (\d) \-+ Bandwidth Control ',
            lambda match: int(match.group(1), base=10),
            self._int_to_string,
            type=ParameterDictType.INT,
            display_name="bandwidth control",
            startup_param=True,
            default_value=0)

        self._param_dict.add(Parameter.CORRELATION_THRESHOLD,
            r'WC (\d+) \-+ Correlation Threshold',
            lambda match: int(match.group(1), base=10),
            self._int_to_string,
            type=ParameterDictType.INT,
            display_name="correlation threshold",
            startup_param=True,
            default_value=64)

        self._param_dict.add(Parameter.SERIAL_OUT_FW_SWITCHES,
            r'WD ([\d ]+) \-+ Data Out ',
            lambda match: str(match.group(1)),
            str,
            type=ParameterDictType.STRING,
            display_name="serial out fw switches",
            visibility=ParameterDictVisibility.IMMUTABLE,
            startup_param=True,
            default_value='111100000')

        self._param_dict.add(Parameter.ERROR_VELOCITY_THRESHOLD,
            r'WE (\d+) \-+ Error Velocity Threshold',
            lambda match: int(match.group(1), base=10),
            self._int_to_string,
            type=ParameterDictType.INT,
            display_name="error velocity threshold",
            startup_param=True,
            default_value=2000)

        self._param_dict.add(Parameter.BLANK_AFTER_TRANSMIT,
            r'WF (\d+) \-+ Blank After Transmit',
            lambda match: int(match.group(1), base=10),
            self._int_to_string,
            type=ParameterDictType.INT,
            display_name="blank after transmit",
            startup_param=True,
            default_value=704)

        self._param_dict.add(Parameter.CLIP_DATA_PAST_BOTTOM,
            r'WI (\d) \-+ Clip Data Past Bottom',
            lambda match: bool(int(match.group(1), base=10)),
            self._bool_to_int,
            type=ParameterDictType.BOOL,
            display_name="clip data past bottom",
            startup_param=True,
            default_value=False)

        self._param_dict.add(Parameter.RECEIVER_GAIN_SELECT,
            r'WJ (\d) \-+ Rcvr Gain Select \(0=Low,1=High\)',
            lambda match: int(match.group(1), base=10),
            self._int_to_string,
            type=ParameterDictType.INT,
            display_name="receiver gain select",
            startup_param=True,
            default_value=1)

        self._param_dict.add(Parameter.WATER_REFERENCE_LAYER,
            r'WL (\d+,\d+) \-+ Water Reference Layer:  ',
            lambda match: str(match.group(1)),
            str,
            type=ParameterDictType.STRING,
            display_name="water reerence layer",
            startup_param=True,
            default_value='001,005')

        self._param_dict.add(Parameter.WATER_PROFILING_MODE,
            r'WM (\d+) \-+ Profiling Mode ',
            lambda match: int(match.group(1), base=10),
            self._int_to_string,
            type=ParameterDictType.INT,
            display_name="water profiling mode",
            visibility=ParameterDictVisibility.IMMUTABLE,
            startup_param=True,
            default_value=1)

        self._param_dict.add(Parameter.NUMBER_OF_DEPTH_CELLS,
            r'WN (\d+) \-+ Number of depth cells',
            lambda match: int(match.group(1), base=10),
            self._int_to_string,
            type=ParameterDictType.INT,
            display_name="number of depth cells",
            startup_param=True,
            default_value=100)

        self._param_dict.add(Parameter.PINGS_PER_ENSEMBLE,
            r'WP (\d+) \-+ Pings per Ensemble ',
            lambda match: int(match.group(1), base=10),
            self._int_to_string,
            type=ParameterDictType.INT,
            display_name="pings per ensemble",
            startup_param=True,
            default_value=1)

        self._param_dict.add(Parameter.DEPTH_CELL_SIZE,
            r'WS (\d+) \-+ Depth Cell Size \(cm\)',
            lambda match: int(match.group(1), base=10),
            self._int_to_string,
            type=ParameterDictType.INT,
            display_name="depth cell size",
            startup_param=True,
            default_value=800)

        self._param_dict.add(Parameter.TRANSMIT_LENGTH,
            r'WT (\d+) \-+ Transmit Length ',
            lambda match: int(match.group(1), base=10),
            self._int_to_string,
            type=ParameterDictType.INT,
            display_name="transmit length",
            startup_param=True,
            default_value=0)

        self._param_dict.add(Parameter.PING_WEIGHT,
            r'WU (\d) \-+ Ping Weighting ',
            lambda match: int(match.group(1), base=10),
            self._int_to_string,
            type=ParameterDictType.INT,
            display_name="ping weight",
            startup_param=True,
            default_value=0)

        self._param_dict.add(Parameter.AMBIGUITY_VELOCITY,
            r'WV (\d+) \-+ Mode 1 Ambiguity Vel ',
            lambda match: int(match.group(1), base=10),
            self._int_to_string,
            type=ParameterDictType.INT,
            display_name="ambiguity velocity",
            startup_param=True,
            default_value=175)

    def _send_break_cmd(self):
        """
        Send a BREAK to attempt to wake the device.
        """
        log.debug("IN _send_break_cmd")
        try:
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        except socket.error, msg:
            log.error("WHOOPS! 1")

        try:
            sock.connect(('localhost', 2102))
        except socket.error, msg:
            log.error("WHOOPS! 2")
        sock.send("break 500\r\n")
        sock.close()

    pass
