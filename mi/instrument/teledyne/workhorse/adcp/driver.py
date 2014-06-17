"""
@package mi.instrument.teledyne.workhorse.adcp.driver
@file marine-integrations/mi/instrument/teledyne/workhorse/adcp/driver.py
@author Sung Ahn
@brief Driver for the ADCP
Release notes:

Generic Driver for ADCPS-K, ADCPS-I, ADCPT-B and ADCPT-DE
"""
from mi.core.common import Units
from mi.instrument.teledyne.workhorse.driver import WorkhorseInstrumentDriver
from mi.instrument.teledyne.workhorse.driver import WorkhorseProtocol

from mi.instrument.teledyne.driver import TeledyneScheduledJob
from mi.instrument.teledyne.driver import TeledyneCapability
from mi.instrument.teledyne.driver import TeledyneInstrumentCmds
from mi.instrument.teledyne.driver import TeledyneProtocolState
from mi.instrument.teledyne.driver import TeledynePrompt

from mi.instrument.teledyne.workhorse.driver import NEWLINE
from mi.core.log import get_logger

log = get_logger()

from mi.core.instrument.protocol_param_dict import ParameterDictVisibility
from mi.core.instrument.protocol_param_dict import ParameterDictType
from mi.instrument.teledyne.workhorse.driver import WorkhorseParameter
from mi.instrument.teledyne.driver import TeledyneProtocolEvent


class Prompt(TeledynePrompt):
    """
    Device i/o prompts..
    """


class Parameter(WorkhorseParameter):
    """
    Device parameters
    """
    #
    # set-able parameters
    #


class ProtocolEvent(TeledyneProtocolEvent):
    """
    Protocol events
    """


class Capability(TeledyneCapability):
    """
    Protocol events that should be exposed to users (subset of above).
    """


class ScheduledJob(TeledyneScheduledJob):
    """
    Complete this last.
    """


class InstrumentCmds(TeledyneInstrumentCmds):
    """
    Device specific commands
    Represents the commands the driver implements and the string that
    must be sent to the instrument to execute the command.
    """


class ProtocolState(TeledyneProtocolState):
    """
    Instrument protocol states
    """


class InstrumentDriver(WorkhorseInstrumentDriver):
    """
    Specialization for this version of the workhorse ADCP driver
    """

    def __init__(self, evt_callback):
        """
        InstrumentDriver constructor.
        @param evt_callback Driver process event callback.
        """
        # Construct superclass.
        WorkhorseInstrumentDriver.__init__(self, evt_callback)

    def _build_protocol(self):
        """
        Construct the driver protocol state machine.
        """
        self._protocol = Protocol(Prompt, NEWLINE, self._driver_event)
        log.debug("self._protocol = " + repr(self._protocol))


class ADCPUnits(Units):
    INTERVALTIME = 'Hour:Minute:Second'
    INTERVALTIMEMILLI = 'Hour:Minute:Second.Second/100'
    DATETIME = 'CCYY/MM/DD,hh:mm:ss'
    PINGTIME = "min:sec.sec/100"
    SETTIME = 'CCYY/MM/DD,hh:mm:ss'
    SERIALDATAOUT = 'Vel Cor Amp'
    FLOWCONTROL = 'BITS: EnsCyc PngCyc Binry Ser Rec'
    TRUEFALSE = 'True(1)/False(0)'
    NONE = ' '
    SLEEP = '0 = Disable, 1 = Enable, 2 See Manual'
    XMTPOWER = 'XMT Power 0-255'
    CDEGREE = '1/100 degree'
    DM = 'dm'
    MPERS = 'm/s'
    PPTHOUSAND = 'pp thousand'
    SELECTION = 'selection'
    ENSEMBLEPERBURST = 'Ensembles Per Burst'
    CMPERSRADIAL = 'cm/s radial'
    TENTHMILLISECOND = '1/10 msec'


class Protocol(WorkhorseProtocol):
    """
    Specialization for this version of the workhorse driver
    """

    def __init__(self, prompts, newline, driver_event):
        log.debug("IN Protocol.__init__")
        WorkhorseProtocol.__init__(self, prompts, newline, driver_event)
        self.initialize_scheduler()

    def _build_param_dict(self):
        """
        Populate the parameter dictionary with ADCP parameters.
        For each parameter key, add match stirng, match lambda function,
        and value formatting function for set commands.
        """

        self._param_dict.add(Parameter.SERIAL_DATA_OUT,
                             r'CD = (\d\d\d \d\d\d \d\d\d) \-+ Serial Data Out ',
                             lambda match: str(match.group(1)),
                             str,
                             type=ParameterDictType.STRING,
                             display_name="serial data out",
                             units=ADCPUnits.SERIALDATAOUT,
                             startup_param=True,
                             direct_access=True,
                             visibility=ParameterDictVisibility.IMMUTABLE,
                             default_value='000 000 000')

        self._param_dict.add(Parameter.SERIAL_FLOW_CONTROL,
                             r'CF = (\d+) \-+ Flow Ctrl ',
                             lambda match: str(match.group(1)),
                             str,
                             type=ParameterDictType.STRING,
                             display_name="serial flow control",
                             units=ADCPUnits.FLOWCONTROL,
                             startup_param=True,
                             direct_access=True,
                             visibility=ParameterDictVisibility.IMMUTABLE,
                             default_value='11110')

        self._param_dict.add(Parameter.BANNER,
                             r'CH = (\d) \-+ Suppress Banner',
                             lambda match: bool(int(match.group(1), base=10)),
                             self._bool_to_int,
                             type=ParameterDictType.BOOL,
                             display_name="banner",
                             units=ADCPUnits.TRUEFALSE,
                             startup_param=True,
                             direct_access=True,
                             visibility=ParameterDictVisibility.IMMUTABLE,
                             default_value=0)

        self._param_dict.add(Parameter.INSTRUMENT_ID,
                             r'CI = (\d+) \-+ Instrument ID ',
                             lambda match: int(match.group(1), base=10),
                             self._int_to_string,
                             type=ParameterDictType.INT,
                             display_name="instrument id",
                             units=ADCPUnits.NONE,
                             direct_access=True,
                             startup_param=True,
                             visibility=ParameterDictVisibility.IMMUTABLE,
                             default_value=0)

        self._param_dict.add(Parameter.SLEEP_ENABLE,
                             r'CL = (\d) \-+ Sleep Enable',
                             lambda match: int(match.group(1), base=10),
                             self._int_to_string,
                             type=ParameterDictType.INT,
                             display_name="sleep enable",
                             units=ADCPUnits.SLEEP,
                             startup_param=True,
                             direct_access=True,
                             visibility=ParameterDictVisibility.IMMUTABLE,
                             default_value=False)

        self._param_dict.add(Parameter.SAVE_NVRAM_TO_RECORDER,
                             r'CN = (\d) \-+ Save NVRAM to recorder',
                             lambda match: bool(int(match.group(1), base=10)),
                             self._bool_to_int,
                             type=ParameterDictType.BOOL,
                             display_name="save nvram to recorder",
                             units=ADCPUnits.TRUEFALSE,
                             startup_param=True,
                             default_value=True,
                             direct_access=True,
                             visibility=ParameterDictVisibility.IMMUTABLE)

        self._param_dict.add(Parameter.POLLED_MODE,
                             r'CP = (\d) \-+ PolledMode ',
                             lambda match: bool(int(match.group(1), base=10)),
                             self._bool_to_int,
                             type=ParameterDictType.BOOL,
                             display_name="polled mode",
                             units=ADCPUnits.TRUEFALSE,
                             startup_param=True,
                             direct_access=True,
                             visibility=ParameterDictVisibility.IMMUTABLE,
                             default_value=False)

        self._param_dict.add(Parameter.XMIT_POWER,
                             r'CQ = (\d+) \-+ Xmt Power ',
                             lambda match: int(match.group(1), base=10),
                             self._int_to_string,
                             type=ParameterDictType.INT,
                             display_name="xmit power",
                             startup_param=True,
                             units=ADCPUnits.XMTPOWER,
                             direct_access=True,
                             default_value=255)

        self._param_dict.add(Parameter.LATENCY_TRIGGER,
                             r'CX = (\d) \-+ Trigger Enable ',
                             lambda match: int(match.group(1), base=10),
                             self._bool_to_int,
                             type=ParameterDictType.INT,
                             display_name="latency trigger",
                             units=ADCPUnits.TRUEFALSE,
                             visibility=ParameterDictVisibility.IMMUTABLE,
                             startup_param=True,
                             direct_access=True,
                             default_value=False)

        self._param_dict.add(Parameter.HEADING_ALIGNMENT,
                             r'EA = ([\+\-\d]+) \-+ Heading Alignment',
                             lambda match: str(match.group(1)),
                             str,
                             type=ParameterDictType.STRING,
                             display_name="Heading alignment",
                             units=ADCPUnits.CDEGREE,
                             visibility=ParameterDictVisibility.IMMUTABLE,
                             direct_access=True,
                             startup_param=True,
                             default_value='+00000')

        self._param_dict.add(Parameter.HEADING_BIAS,
                             r'EB = ([\+\-\d]+) \-+ Heading Bias',
                             lambda match: str(match.group(1)),
                             str,
                             type=ParameterDictType.STRING,
                             display_name="Heading Bias",
                             units=ADCPUnits.CDEGREE,
                             visibility=ParameterDictVisibility.IMMUTABLE,
                             startup_param=True,
                             direct_access=True,
                             default_value='+00000')

        self._param_dict.add(Parameter.SPEED_OF_SOUND,
                             r'EC = (\d+) \-+ Speed Of Sound',
                             lambda match: int(match.group(1), base=10),
                             self._int_to_string,
                             type=ParameterDictType.INT,
                             display_name="speed of sound",
                             units=ADCPUnits.MPERS,
                             startup_param=True,
                             direct_access=True,
                             default_value=1485)

        self._param_dict.add(Parameter.TRANSDUCER_DEPTH,
                             r'ED = (\d+) \-+ Transducer Depth ',
                             lambda match: int(match.group(1), base=10),
                             self._int_to_string,
                             type=ParameterDictType.INT,
                             display_name="Transducer Depth",
                             units=ADCPUnits.DM,
                             startup_param=True,
                             direct_access=True,
                             default_value=8000)

        self._param_dict.add(Parameter.PITCH,
                             r'EP = ([\+\-\d]+) \-+ Tilt 1 Sensor ',
                             lambda match: int(match.group(1), base=10),
                             self._int_to_string,
                             type=ParameterDictType.INT,
                             display_name="pitch",
                             units=ADCPUnits.CDEGREE,
                             startup_param=True,
                             direct_access=True,
                             default_value=0)

        self._param_dict.add(Parameter.ROLL,
                             r'ER = ([\+\-\d]+) \-+ Tilt 2 Sensor ',
                             lambda match: int(match.group(1), base=10),
                             self._int_to_string,
                             type=ParameterDictType.INT,
                             display_name="roll",
                             units=ADCPUnits.CDEGREE,
                             startup_param=True,
                             direct_access=True,
                             default_value=0)

        self._param_dict.add(Parameter.SALINITY,
                             r'ES = (\d+) \-+ Salinity ',
                             lambda match: int(match.group(1), base=10),
                             self._int_to_string,
                             type=ParameterDictType.INT,
                             display_name="salinity",
                             units=ADCPUnits.PPTHOUSAND,
                             startup_param=True,
                             direct_access=True,
                             default_value=35)

        self._param_dict.add(Parameter.COORDINATE_TRANSFORMATION,
                             r'EX = (\d+) \-+ Coord Transform ',
                             lambda match: str(match.group(1)),
                             str,
                             type=ParameterDictType.STRING,
                             display_name="coordinate transformation",
                             units=ADCPUnits.BIT,
                             startup_param=True,
                             direct_access=True,
                             visibility=ParameterDictVisibility.IMMUTABLE,
                             default_value='00111')

        self._param_dict.add(Parameter.SENSOR_SOURCE,
                             r'EZ = (\d+) \-+ Sensor Source ',
                             lambda match: str(match.group(1)),
                             str,
                             type=ParameterDictType.STRING,
                             display_name="sensor source",
                             units=ADCPUnits.BIT,
                             startup_param=True,
                             direct_access=True,
                             default_value='1111101')

        self._param_dict.add(Parameter.DATA_STREAM_SELECTION,
                             r'PD = (\d+) \-+ Data Stream Select',
                             lambda match: int(match.group(1), base=10),
                             self._int_to_string,
                             type=ParameterDictType.INT,
                             display_name="Data Stream Selection",
                             units=ADCPUnits.SELECTION,
                             visibility=ParameterDictVisibility.IMMUTABLE,
                             startup_param=True,
                             direct_access=True,
                             default_value=0)

        self._param_dict.add(Parameter.ENSEMBLE_PER_BURST,
                             r'TC (\d+) \-+ Ensembles Per Burst',
                             lambda match: int(match.group(1), base=10),
                             self._int_to_string,
                             type=ParameterDictType.INT,
                             display_name="Ensemble per burst",
                             units=ADCPUnits.ENSEMBLEPERBURST,
                             visibility=ParameterDictVisibility.IMMUTABLE,
                             startup_param=True,
                             direct_access=True,
                             default_value=0)

        self._param_dict.add(Parameter.TIME_PER_ENSEMBLE,
                             r'TE (\d\d:\d\d:\d\d.\d\d) \-+ Time per Ensemble ',
                             lambda match: str(match.group(1)),
                             str,
                             type=ParameterDictType.STRING,
                             display_name="time per ensemble",
                             units=ADCPUnits.INTERVALTIMEMILLI,
                             startup_param=True,
                             direct_access=True,
                             default_value='00:00:00.00')

        self._param_dict.add(Parameter.TIME_OF_FIRST_PING,
                             r'TG (..../../..,..:..:..) - Time of First Ping ',
                             lambda match: str(match.group(1)),
                             str,
                             type=ParameterDictType.STRING,
                             display_name="time of first ping",
                             units=ADCPUnits.DATETIME,
                             startup_param=False,
                             direct_access=False,
                             visibility=ParameterDictVisibility.READ_ONLY)

        self._param_dict.add(Parameter.TIME_PER_PING,
                             r'TP (\d\d:\d\d.\d\d) \-+ Time per Ping',
                             lambda match: str(match.group(1)),
                             str,
                             type=ParameterDictType.STRING,
                             display_name="time per ping",
                             units=ADCPUnits.PINGTIME,
                             startup_param=True,
                             direct_access=True,
                             default_value='00:01.00')

        self._param_dict.add(Parameter.TIME,
                             r'TT (\d\d\d\d/\d\d/\d\d,\d\d:\d\d:\d\d) \- Time Set ',
                             lambda match: str(match.group(1) + " UTC"),
                             str,
                             type=ParameterDictType.STRING,
                             display_name="time",
                             units=ADCPUnits.SETTIME,
                             expiration=86400)  # expire once per day 60 * 60 * 24

        self._param_dict.add(Parameter.BUFFERED_OUTPUT_PERIOD,
                             r'TX (\d\d:\d\d:\d\d) \-+ Buffer Output Period:',
                             lambda match: str(match.group(1)),
                             str,
                             type=ParameterDictType.STRING,
                             display_name="Buffered output period",
                             units=ADCPUnits.INTERVALTIME,
                             visibility=ParameterDictVisibility.IMMUTABLE,
                             startup_param=True,
                             direct_access=True,
                             default_value='00:00:00')

        self._param_dict.add(Parameter.FALSE_TARGET_THRESHOLD,
                             r'WA (\d+,\d+) \-+ False Target Threshold ',
                             lambda match: str(match.group(1)),
                             str,
                             type=ParameterDictType.STRING,
                             display_name="false target threshold",
                             units=ADCPUnits.BIT,
                             startup_param=True,
                             direct_access=True,
                             default_value='050,001')

        self._param_dict.add(Parameter.BANDWIDTH_CONTROL,
                             r'WB (\d) \-+ Bandwidth Control ',
                             lambda match: int(match.group(1), base=10),
                             self._int_to_string,
                             type=ParameterDictType.INT,
                             display_name="bandwidth control",
                             units=ADCPUnits.TRUEFALSE,
                             startup_param=True,
                             direct_access=True,
                             default_value=0)

        self._param_dict.add(Parameter.CORRELATION_THRESHOLD,
                             r'WC (\d+) \-+ Correlation Threshold',
                             lambda match: int(match.group(1), base=10),
                             self._int_to_string,
                             type=ParameterDictType.INT,
                             display_name="correlation threshold",
                             units=ADCPUnits.NONE,
                             startup_param=True,
                             direct_access=True,
                             default_value=64)

        self._param_dict.add(Parameter.SERIAL_OUT_FW_SWITCHES,
                             r'WD ([\d ]+) \-+ Data Out ',
                             lambda match: str(match.group(1)),
                             str,
                             type=ParameterDictType.STRING,
                             display_name="serial out fw switches",
                             units=ADCPUnits.BIT,
                             visibility=ParameterDictVisibility.IMMUTABLE,
                             startup_param=True,
                             direct_access=True,
                             default_value='111100000')

        self._param_dict.add(Parameter.ERROR_VELOCITY_THRESHOLD,
                             r'WE (\d+) \-+ Error Velocity Threshold',
                             lambda match: int(match.group(1), base=10),
                             self._int_to_string,
                             type=ParameterDictType.INT,
                             display_name="error velocity threshold",
                             units=ADCPUnits.MPERS,
                             startup_param=True,
                             direct_access=True,
                             default_value=2000)

        self._param_dict.add(Parameter.BLANK_AFTER_TRANSMIT,
                             r'WF (\d+) \-+ Blank After Transmit',
                             lambda match: int(match.group(1), base=10),
                             self._int_to_string,
                             type=ParameterDictType.INT,
                             display_name="blank after transmit",
                             units=ADCPUnits.CENTIMETER,
                             startup_param=True,
                             direct_access=True,
                             default_value=704)

        self._param_dict.add(Parameter.CLIP_DATA_PAST_BOTTOM,
                             r'WI (\d) \-+ Clip Data Past Bottom',
                             lambda match: bool(int(match.group(1), base=10)),
                             self._bool_to_int,
                             type=ParameterDictType.BOOL,
                             display_name="clip data past bottom",
                             units=ADCPUnits.TRUEFALSE,
                             startup_param=True,
                             direct_access=True,
                             default_value=False)

        self._param_dict.add(Parameter.RECEIVER_GAIN_SELECT,
                             r'WJ (\d) \-+ Rcvr Gain Select \(0=Low,1=High\)',
                             lambda match: int(match.group(1), base=10),
                             self._int_to_string,
                             type=ParameterDictType.INT,
                             display_name="receiver gain select",
                             units=ADCPUnits.TRUEFALSE,
                             startup_param=True,
                             direct_access=True,
                             default_value=1)

        self._param_dict.add(Parameter.NUMBER_OF_DEPTH_CELLS,
                             r'WN (\d+) \-+ Number of depth cells',
                             lambda match: int(match.group(1), base=10),
                             self._int_to_string,
                             type=ParameterDictType.INT,
                             display_name="number of depth cells",
                             units=ADCPUnits.NONE,
                             startup_param=True,
                             direct_access=True,
                             default_value=100)

        self._param_dict.add(Parameter.PINGS_PER_ENSEMBLE,
                             r'WP (\d+) \-+ Pings per Ensemble ',
                             lambda match: int(match.group(1), base=10),
                             self._int_to_string,
                             type=ParameterDictType.INT,
                             display_name="pings per ensemble",
                             units=ADCPUnits.NONE,
                             startup_param=True,
                             direct_access=True,
                             default_value=1)

        self._param_dict.add(Parameter.SAMPLE_AMBIENT_SOUND,
                             r'WQ (\d) \-+ Sample Ambient Sound',
                             lambda match: int(match.group(1), base=10),
                             self._int_to_string,
                             type=ParameterDictType.INT,
                             display_name="Sample ambient sound",
                             units=ADCPUnits.TRUEFALSE,
                             visibility=ParameterDictVisibility.IMMUTABLE,
                             startup_param=True,
                             direct_access=True,
                             default_value=0)

        self._param_dict.add(Parameter.DEPTH_CELL_SIZE,
                             r'WS (\d+) \-+ Depth Cell Size \(cm\)',
                             lambda match: int(match.group(1), base=10),
                             self._int_to_string,
                             type=ParameterDictType.INT,
                             display_name="depth cell size",
                             units=ADCPUnits.CENTIMETER,
                             startup_param=True,
                             direct_access=True,
                             default_value=800)

        self._param_dict.add(Parameter.TRANSMIT_LENGTH,
                             r'WT (\d+) \-+ Transmit Length ',
                             lambda match: int(match.group(1), base=10),
                             self._int_to_string,
                             type=ParameterDictType.INT,
                             display_name="transmit length",
                             units=ADCPUnits.CENTIMETER,
                             startup_param=True,
                             direct_access=True,
                             default_value=0)

        self._param_dict.add(Parameter.PING_WEIGHT,
                             r'WU (\d) \-+ Ping Weighting ',
                             lambda match: int(match.group(1), base=10),
                             self._int_to_string,
                             type=ParameterDictType.INT,
                             display_name="ping weight",
                             units=ADCPUnits.TRUEFALSE,
                             startup_param=True,
                             direct_access=True,
                             default_value=0)

        self._param_dict.add(Parameter.AMBIGUITY_VELOCITY,
                             r'WV (\d+) \-+ Mode 1 Ambiguity Vel ',
                             lambda match: int(match.group(1), base=10),
                             self._int_to_string,
                             type=ParameterDictType.INT,
                             display_name="ambiguity velocity",
                             units=ADCPUnits.CMPERSRADIAL,
                             startup_param=True,
                             direct_access=True,
                             default_value=175)

        # Engineering parameters
        self._param_dict.add(Parameter.CLOCK_SYNCH_INTERVAL,
                             r'BOGUS',
                             None,
                             str,
                             type=ParameterDictType.STRING,
                             display_name="clock synch interval",
                             units=ADCPUnits.INTERVALTIME,
                             startup_param=True,
                             direct_access=False,
                             default_value="00:00:00")

        self._param_dict.add(Parameter.GET_STATUS_INTERVAL,
                             r'BOGUS',
                             None,
                             str,
                             type=ParameterDictType.STRING,
                             display_name="get status interval",
                             units=ADCPUnits.INTERVALTIME,
                             startup_param=True,
                             direct_access=False,
                             default_value="00:00:00")

        self._param_dict.set_default(Parameter.CLOCK_SYNCH_INTERVAL)
        self._param_dict.set_default(Parameter.GET_STATUS_INTERVAL)



