"""
@package mi.instrument.seabird.sbe16plus_v2.test.test_driver
@file mi/instrument/seabird/sbe16plus_v2/test/test_driver.py
@author David Everett 
@brief Test cases for InstrumentDriver

USAGE:
 Make tests verbose and provide stdout
   * From the IDK
       $ bin/test_driver
       $ bin/test_driver -u
       $ bin/test_driver -i
       $ bin/test_driver -q

   * From pyon
       $ bin/nosetests -s -v .../mi/instrument/seabird/sbe16plus_v2/ooicore
       $ bin/nosetests -s -v .../mi/instrument/seabird/sbe16plus_v2/ooicore -a UNIT
       $ bin/nosetests -s -v .../mi/instrument/seabird/sbe16plus_v2/ooicore -a INT
       $ bin/nosetests -s -v .../mi/instrument/seabird/sbe16plus_v2/ooicore -a QUAL
"""

__author__ = 'David Everett'
__license__ = 'Apache 2.0'

# Standard lib imports
import time

# 3rd party imports
from nose.plugins.attrib import attr
from mock import Mock

# MI logger
from mi.core.log import get_logger ; log = get_logger()

from mi.core.instrument.instrument_driver import DriverAsyncEvent
from mi.core.instrument.chunker import StringChunker
from interface.objects import AgentCommand

from mi.idk.unit_test import DriverTestMixin
from mi.idk.unit_test import ParameterTestConfigKey
from mi.idk.unit_test import AgentCapabilityType

from mi.core.exceptions import InstrumentParameterException
from mi.core.exceptions import InstrumentProtocolException
from mi.core.exceptions import InstrumentCommandException
from mi.core.exceptions import InstrumentTimeoutException

from mi.instrument.seabird.sbe16plus_v2.driver import SBE16Protocol
from mi.instrument.seabird.sbe16plus_v2.driver import SBE16InstrumentDriver
from mi.instrument.seabird.sbe16plus_v2.driver import DataParticleType
from mi.instrument.seabird.sbe16plus_v2.driver import ConfirmedParameter
from mi.instrument.seabird.sbe16plus_v2.driver import NEWLINE
from mi.instrument.seabird.sbe16plus_v2.driver import SBE16DataParticleKey
from mi.instrument.seabird.sbe16plus_v2.driver import SBE16StatusParticleKey
from mi.instrument.seabird.sbe16plus_v2.driver import SBE16CalibrationParticleKey
from mi.instrument.seabird.sbe16plus_v2.driver import ProtocolState
from mi.instrument.seabird.sbe16plus_v2.driver import ProtocolEvent
from mi.instrument.seabird.sbe16plus_v2.driver import ScheduledJob
from mi.instrument.seabird.sbe16plus_v2.driver import Capability
from mi.instrument.seabird.sbe16plus_v2.driver import Parameter
from mi.instrument.seabird.sbe16plus_v2.driver import Command
from mi.instrument.seabird.sbe16plus_v2.driver import Prompt
from mi.instrument.seabird.driver import SBE_EPOCH

from mi.instrument.seabird.test.test_driver import SeaBirdUnitTest
from mi.instrument.seabird.test.test_driver import SeaBirdIntegrationTest
from mi.instrument.seabird.test.test_driver import SeaBirdQualificationTest
from mi.instrument.seabird.test.test_driver import SeaBirdPublicationTest

from mi.core.instrument.instrument_driver import DriverConnectionState
from mi.core.instrument.instrument_driver import DriverProtocolState
from pyon.agent.agent import ResourceAgentState
from pyon.agent.agent import ResourceAgentEvent
from pyon.core.exception import ServerError
from pyon.core.exception import Conflict

class SeaBird16plusMixin(DriverTestMixin):
    
    InstrumentDriver = SBE16InstrumentDriver
    
    '''
    Mixin class used for storing data particle constants and common data assertion methods.
    '''
    # Create some short names for the parameter test config
    TYPE      = ParameterTestConfigKey.TYPE
    READONLY  = ParameterTestConfigKey.READONLY
    STARTUP   = ParameterTestConfigKey.STARTUP
    DA        = ParameterTestConfigKey.DIRECT_ACCESS
    VALUE     = ParameterTestConfigKey.VALUE
    REQUIRED  = ParameterTestConfigKey.REQUIRED
    DEFAULT   = ParameterTestConfigKey.DEFAULT
    STATES    = ParameterTestConfigKey.STATES

    ###
    #  Instrument output (driver input) Definitions
    ###
    VALID_SAMPLE = "#0409DB0A738C81747A84AC0006000A2E541E18BE6ED9" + NEWLINE
    VALID_SAMPLE2 = "0409DB0A738C81747A84AC0006000A2E541E18BE6ED9" + NEWLINE
    
    VALID_DS_RESPONSE =  'SBE 16plus V 2.5  SERIAL NO. 6841    28 Feb 2013 16:39:31' + NEWLINE + \
        'vbatt = 23.4, vlith =  8.0, ioper =  61.4 ma, ipump =   0.3 ma,' + NEWLINE + \
        'status = not logging' + NEWLINE + \
        'samples = 0, free = 4386542' + NEWLINE + \
        'sample interval = 10 seconds, number of measurements per sample = 4' + NEWLINE + \
        'pump = run pump during sample, delay before sampling = 0.0 seconds, delay after sampling = 0.0 seconds' + NEWLINE + \
        'transmit real-time = yes' + NEWLINE + \
        'battery cutoff =  7.5 volts' + NEWLINE + \
        'pressure sensor = strain gauge, range = 160.0' + NEWLINE + \
        'SBE 38 = no, SBE 50 = no, WETLABS = no, OPTODE = no, SBE63 = no, Gas Tension Device = no' + NEWLINE + \
        'Ext Volt 0 = yes, Ext Volt 1 = yes' + NEWLINE + \
        'Ext Volt 2 = yes, Ext Volt 3 = yes' + NEWLINE + \
        'Ext Volt 4 = yes, Ext Volt 5 = yes' + NEWLINE + \
        'echo characters = yes' + NEWLINE + \
        'output format = raw HEX' + NEWLINE + \
        'serial sync mode disabled' + NEWLINE
    
    VALID_DCAL_QUARTZ = 'SBE 16plus V 2.5  SERIAL NO. 6841    28 Feb 2013 18:37:40' + NEWLINE + \
        'temperature:  18-May-12' + NEWLINE + \
        '    TA0 = 1.561342e-03' + NEWLINE + \
        '    TA1 = 2.561486e-04' + NEWLINE + \
        '    TA2 = 1.896537e-07' + NEWLINE + \
        '    TA3 = 1.301189e-07' + NEWLINE + \
        '    TOFFSET = 0.000000e+00' + NEWLINE + \
        'conductivity:  18-May-11' + NEWLINE + \
        '    G = -9.896568e-01' + NEWLINE + \
        '    H = 1.316599e-01' + NEWLINE + \
        '    I = -2.213854e-04' + NEWLINE + \
        '    J = 3.292199e-05' + NEWLINE + \
        '    CPCOR = -9.570000e-08' + NEWLINE + \
        '    CTCOR = 3.250000e-06' + NEWLINE + \
        '    CSLOPE = 1.000000e+00' + NEWLINE + \
        'pressure S/N = 125270, range = 1000 psia:  02-nov-12' + NEWLINE + \
        '   PC1 = -4.642673e+03' + NEWLINE + \
        '   PC2 = -4.611640e-03' + NEWLINE + \
        '   PC3 = 8.921190e-04' + NEWLINE + \
        '   PD1 = 7.024800e-02' + NEWLINE + \
        '   PD2 = 0.000000e+00' + NEWLINE + \
        '   PT1 = 3.022595e+01' + NEWLINE + \
        '   PT2 = -1.549720e-04' + NEWLINE + \
        '   PT3 = 2.677750e-06' + NEWLINE + \
        '   PT4 = 1.705490e-09' + NEWLINE + \
        '   PSLOPE = 1.000000e+00' + NEWLINE + \
        '   POFFSET = 0.000000e+00' + NEWLINE + \
        'volt 0: offset = -4.650526e-02, slope = 1.246381e+00' + NEWLINE + \
        'volt 1: offset = -4.618105e-02, slope = 1.247197e+00' + NEWLINE + \
        'volt 2: offset = -4.659790e-02, slope = 1.247601e+00' + NEWLINE + \
        'volt 3: offset = -4.502421e-02, slope = 1.246911e+00' + NEWLINE + \
        'volt 4: offset = -4.589158e-02, slope = 1.246346e+00' + NEWLINE + \
        'volt 5: offset = -4.609895e-02, slope = 1.247868e+00' + NEWLINE + \
        '   EXTFREQSF = 9.999949e-01' + NEWLINE
    
    VALID_DCAL_STRAIN ='SBE 16plus V 2.5  SERIAL NO. 6841    28 Feb 2013 18:37:40' + NEWLINE + \
        'temperature:  18-May-12' + NEWLINE + \
        '    TA0 = 1.561342e-03' + NEWLINE + \
        '    TA1 = 2.561486e-04' + NEWLINE + \
        '    TA2 = 1.896537e-07' + NEWLINE + \
        '    TA3 = 1.301189e-07' + NEWLINE + \
        '    TOFFSET = 0.000000e+00' + NEWLINE + \
        'conductivity:  18-May-11' + NEWLINE + \
        '    G = -9.896568e-01' + NEWLINE + \
        '    H = 1.316599e-01' + NEWLINE + \
        '    I = -2.213854e-04' + NEWLINE + \
        '    J = 3.292199e-05' + NEWLINE + \
        '    CPCOR = -9.570000e-08' + NEWLINE + \
        '    CTCOR = 3.250000e-06' + NEWLINE + \
        '    CSLOPE = 1.000000e+00' + NEWLINE + \
        'pressure S/N = 3230195, range = 160 psia:  11-May-11' + NEWLINE + \
        '    PA0 = 4.960417e-02' + NEWLINE + \
        '    PA1 = 4.883682e-04' + NEWLINE + \
        '    PA2 = -5.687309e-12' + NEWLINE + \
        '    PTCA0 = 5.249802e+05' + NEWLINE + \
        '    PTCA1 = 7.595719e+00' + NEWLINE + \
        '    PTCA2 = -1.322776e-01' + NEWLINE + \
        '    PTCB0 = 2.503125e+01' + NEWLINE + \
        '    PTCB1 = 5.000000e-05' + NEWLINE + \
        '    PTCB2 = 0.000000e+00' + NEWLINE + \
        '    PTEMPA0 = -6.431504e+01' + NEWLINE + \
        '    PTEMPA1 = 5.168177e+01' + NEWLINE + \
        '    PTEMPA2 = -2.847757e-01' + NEWLINE + \
        '    POFFSET = 0.000000e+00' + NEWLINE + \
        'volt 0: offset = -4.650526e-02, slope = 1.246381e+00' + NEWLINE + \
        'volt 1: offset = -4.618105e-02, slope = 1.247197e+00' + NEWLINE + \
        'volt 2: offset = -4.659790e-02, slope = 1.247601e+00' + NEWLINE + \
        'volt 3: offset = -4.502421e-02, slope = 1.246911e+00' + NEWLINE + \
        'volt 4: offset = -4.589158e-02, slope = 1.246346e+00' + NEWLINE + \
        'volt 5: offset = -4.609895e-02, slope = 1.247868e+00' + NEWLINE + \
        '    EXTFREQSF = 9.999949e-01' + NEWLINE
    
    ###
    #  Parameter and Type Definitions
    ###
    _driver_parameters = {
        # Parameters defined in the IOS
        Parameter.DATE_TIME : {TYPE: str, READONLY: True, DA: False, STARTUP: False},
        Parameter.ECHO : {TYPE: bool, READONLY: True, DA: True, STARTUP: True, DEFAULT: True, VALUE: True},
        Parameter.OUTPUT_EXEC_TAG : {TYPE: bool, READONLY: True, DA: True, STARTUP: True, DEFAULT: True, VALUE: True},
        Parameter.TXREALTIME : {TYPE: bool, READONLY: True, DA: True, STARTUP: True, DEFAULT: True, VALUE: True},
        Parameter.PUMP_MODE : {TYPE: int, READONLY: False, DA: True, STARTUP: True, DEFAULT: 2, VALUE: 2},
        Parameter.NCYCLES : {TYPE: int, READONLY: False, DA: False, STARTUP: True, DEFAULT: 4, VALUE: 4},
        Parameter.INTERVAL : {TYPE: int, READONLY: False, DA: False, STARTUP: True, VALUE: 10},
        Parameter.BIOWIPER : {TYPE: bool, READONLY: True, DA: True, STARTUP: True, DEFAULT: False, VALUE: False},
        Parameter.PTYPE : {TYPE: int, READONLY: True, DA: True, STARTUP: True, DEFAULT: 1, VALUE: 1},
        Parameter.VOLT0 : {TYPE: bool, READONLY: True, DA: True, STARTUP: True, DEFAULT: True, VALUE: True},
        Parameter.VOLT1 : {TYPE: bool, READONLY: True, DA: True, STARTUP: True, DEFAULT: True, VALUE: True},
        Parameter.VOLT2 : {TYPE: bool, READONLY: True, DA: True, STARTUP: True, DEFAULT: True, VALUE: True},
        Parameter.VOLT3 : {TYPE: bool, READONLY: True, DA: True, STARTUP: True, DEFAULT: True, VALUE: True},
        Parameter.VOLT4 : {TYPE: bool, READONLY: True, DA: True, STARTUP: True, DEFAULT: True, VALUE: True},
        Parameter.VOLT5 : {TYPE: bool, READONLY: True, DA: True, STARTUP: True, DEFAULT: True, VALUE: True},
        Parameter.DELAY_BEFORE_SAMPLE : {TYPE: float, READONLY: True, DA: True, STARTUP: True, DEFAULT: 0.0, VALUE: 0.0},
        Parameter.DELAY_AFTER_SAMPLE : {TYPE: float, READONLY: True, DA: True, STARTUP: True, DEFAULT: 0.0, VALUE: 0.0},
        Parameter.SBE63 : {TYPE: bool, READONLY: True, DA: True, STARTUP: True, DEFAULT: False, VALUE: False},
        Parameter.SBE38 : {TYPE: bool, READONLY: True, DA: True, STARTUP: True, DEFAULT: False, VALUE: False},
        Parameter.SBE50 : {TYPE: bool, READONLY: True, DA: True, STARTUP: True, DEFAULT: False, VALUE: False},
        Parameter.WETLABS : {TYPE: bool, READONLY: True, DA: True, STARTUP: True, DEFAULT: False, VALUE: False},
        Parameter.GTD : {TYPE: bool, READONLY: True, DA: True, STARTUP: True, DEFAULT: False, VALUE: False},
        Parameter.OPTODE : {TYPE: bool, READONLY: True, DA: True, STARTUP: True, DEFAULT: False, VALUE: False},
        Parameter.SYNCMODE : {TYPE: bool, READONLY: True, DA: True, STARTUP: True, DEFAULT: False, VALUE: False},
        Parameter.SYNCWAIT : {TYPE: bool, READONLY: True, DA: False, STARTUP: False, DEFAULT: 0, VALUE: 0, REQUIRED: False},
        Parameter.OUTPUT_FORMAT : {TYPE: int, READONLY: True, DA: True, STARTUP: True, DEFAULT: 0, VALUE: 0},
        Parameter.LOGGING : {TYPE: bool, READONLY: True, DA: False, STARTUP: False},
    }

    _driver_capabilities = {
        # capabilities defined in the IOS
        Capability.QUIT_SESSION : {STATES: [ProtocolState.COMMAND, ProtocolState.AUTOSAMPLE]},
        Capability.START_AUTOSAMPLE : {STATES: [ProtocolState.COMMAND]},
        Capability.STOP_AUTOSAMPLE : {STATES: [ProtocolState.AUTOSAMPLE]},
        Capability.CLOCK_SYNC : {STATES: [ProtocolState.COMMAND]},
        Capability.ACQUIRE_STATUS : {STATES: [ProtocolState.COMMAND, ProtocolState.AUTOSAMPLE]},
        Capability.GET_CONFIGURATION : {STATES: [ProtocolState.COMMAND, ProtocolState.AUTOSAMPLE]},
        Capability.TEST : {STATES: [ProtocolState.COMMAND]},
        Capability.RESET_EC : {STATES: [ProtocolState.COMMAND]},
    }

    _sample_parameters = {
        SBE16DataParticleKey.TEMP: {TYPE: int, VALUE: 264667, REQUIRED: True },
        SBE16DataParticleKey.CONDUCTIVITY: {TYPE: int, VALUE: 684940, REQUIRED: True },
        SBE16DataParticleKey.PRESSURE: {TYPE: int, VALUE: 8483962, REQUIRED: True },
        SBE16DataParticleKey.PRESSURE_TEMP: {TYPE: int, VALUE: 33964, REQUIRED: True },
        SBE16DataParticleKey.TIME: {TYPE: int, VALUE: 415133401, REQUIRED: True },
    }

    _status_parameters = {
        SBE16StatusParticleKey.FIRMWARE_VERSION: {TYPE: unicode, VALUE: '2.5', REQUIRED: True },
        SBE16StatusParticleKey.SERIAL_NUMBER: {TYPE: int, VALUE: 6841, REQUIRED: True },
        SBE16StatusParticleKey.DATE_TIME: {TYPE: unicode, VALUE: '28 Feb 2013 16:39:31', REQUIRED: True },
        SBE16StatusParticleKey.VBATT: {TYPE: float, VALUE: 23.4, REQUIRED: True },
        SBE16StatusParticleKey.VLITH: {TYPE: float, VALUE: 8.0, REQUIRED: True },
        SBE16StatusParticleKey.IOPER: {TYPE: float, VALUE: 61.4, REQUIRED: True },
        SBE16StatusParticleKey.IPUMP: {TYPE: float, VALUE: 0.3, REQUIRED: True },
        SBE16StatusParticleKey.STATUS: {TYPE: unicode, VALUE: 'not logging', REQUIRED: True },
        SBE16StatusParticleKey.SAMPLES: {TYPE: int, VALUE: 0, REQUIRED: True },
        SBE16StatusParticleKey.FREE: {TYPE: int, VALUE: 4386542, REQUIRED: True },
        SBE16StatusParticleKey.SAMPLE_INTERVAL: {TYPE: int, VALUE: 10, REQUIRED: True },
        SBE16StatusParticleKey.MEASUREMENTS_PER_SAMPLE: {TYPE: int, VALUE: 4, REQUIRED: True },
        SBE16StatusParticleKey.PUMP_MODE: {TYPE: unicode, VALUE: 'run pump during sample', REQUIRED: True },
        SBE16StatusParticleKey.DELAY_BEFORE_SAMPLING: {TYPE: float, VALUE: 0.0, REQUIRED: True },
        SBE16StatusParticleKey.DELAY_AFTER_SAMPLING: {TYPE: float, VALUE: 0.0, REQUIRED: True },
        SBE16StatusParticleKey.TX_REAL_TIME: {TYPE: bool, VALUE: True, REQUIRED: True },
        SBE16StatusParticleKey.BATTERY_CUTOFF: {TYPE: float, VALUE: 7.5, REQUIRED: True },
        SBE16StatusParticleKey.PRESSURE_SENSOR: {TYPE: unicode, VALUE: 'strain gauge', REQUIRED: True },
        SBE16StatusParticleKey.RANGE: {TYPE: float, VALUE: 160, REQUIRED: True },
        SBE16StatusParticleKey.SBE38: {TYPE: bool, VALUE: False, REQUIRED: True },
        SBE16StatusParticleKey.SBE50: {TYPE: bool, VALUE: False, REQUIRED: True },
        SBE16StatusParticleKey.WETLABS: {TYPE: bool, VALUE: False, REQUIRED: True },
        SBE16StatusParticleKey.OPTODE: {TYPE: bool, VALUE: False, REQUIRED: True },
        SBE16StatusParticleKey.GAS_TENSION_DEVICE: {TYPE: bool, VALUE: False, REQUIRED: True },
        SBE16StatusParticleKey.EXT_VOLT_0: {TYPE: bool, VALUE: True, REQUIRED: True },
        SBE16StatusParticleKey.EXT_VOLT_1: {TYPE: bool, VALUE: True, REQUIRED: True },
        SBE16StatusParticleKey.EXT_VOLT_2: {TYPE: bool, VALUE: True, REQUIRED: True },
        SBE16StatusParticleKey.EXT_VOLT_3: {TYPE: bool, VALUE: True, REQUIRED: True },
        SBE16StatusParticleKey.EXT_VOLT_4: {TYPE: bool, VALUE: True, REQUIRED: True },
        SBE16StatusParticleKey.EXT_VOLT_5: {TYPE: bool, VALUE: True, REQUIRED: True },
        SBE16StatusParticleKey.ECHO_CHARACTERS: {TYPE: bool, VALUE: True, REQUIRED: True },
        SBE16StatusParticleKey.OUTPUT_FORMAT: {TYPE: int, VALUE: 0, REQUIRED: True },
        SBE16StatusParticleKey.OUTPUT_SALINITY: {TYPE: bool, VALUE: False, REQUIRED: False },
        SBE16StatusParticleKey.OUTPUT_SOUND_VELOCITY: {TYPE: bool, VALUE: False, REQUIRED: False },
        SBE16StatusParticleKey.SERIAL_SYNC_MODE: {TYPE: bool, VALUE: False, REQUIRED: True },
    }

    # Base calibration structure, but exludes pressure sensor type.  Those parameters are based
    # on  ptype
    _calibration_parameters_base = {
        SBE16CalibrationParticleKey.FIRMWARE_VERSION: {TYPE: unicode, VALUE: "2.5", REQUIRED: True },
        SBE16CalibrationParticleKey.SERIAL_NUMBER: {TYPE: int, VALUE: 6841, REQUIRED: True },
        SBE16CalibrationParticleKey.DATE_TIME: {TYPE: unicode, VALUE: "28 Feb 2013 18:37:40", REQUIRED: True },
        SBE16CalibrationParticleKey.TEMP_CAL_DATE: {TYPE: unicode, VALUE: "18-May-12", REQUIRED: True },
        SBE16CalibrationParticleKey.TA0: {TYPE: float, VALUE: 1.561342e-03, REQUIRED: True },
        SBE16CalibrationParticleKey.TA1: {TYPE: float, VALUE: 2.561486e-04, REQUIRED: True },
        SBE16CalibrationParticleKey.TA2: {TYPE: float, VALUE: 1.896537e-07, REQUIRED: True },
        SBE16CalibrationParticleKey.TA3: {TYPE: float, VALUE: 1.301189e-07, REQUIRED: True },
        SBE16CalibrationParticleKey.TOFFSET: {TYPE: float, VALUE: 0.0, REQUIRED: True },
        SBE16CalibrationParticleKey.COND_CAL_DATE: {TYPE: unicode, VALUE: '18-May-11', REQUIRED: True },
        SBE16CalibrationParticleKey.CONDG: {TYPE: float, VALUE: -9.896568e-01, REQUIRED: True },
        SBE16CalibrationParticleKey.CONDH: {TYPE: float, VALUE: 1.316599e-01, REQUIRED: True },
        SBE16CalibrationParticleKey.CONDI: {TYPE: float, VALUE: -2.213854e-04, REQUIRED: True },
        SBE16CalibrationParticleKey.CONDJ: {TYPE: float, VALUE: 3.292199e-05, REQUIRED: True },
        SBE16CalibrationParticleKey.CPCOR: {TYPE: float, VALUE: -9.570000e-08, REQUIRED: True },
        SBE16CalibrationParticleKey.CTCOR: {TYPE: float, VALUE: 3.250000e-06, REQUIRED: True },
        SBE16CalibrationParticleKey.CSLOPE: {TYPE: float, VALUE: 1.0, REQUIRED: True },
        SBE16CalibrationParticleKey.EXT_VOLT0_OFFSET: {TYPE: float, VALUE: -4.650526e-02, REQUIRED: True },
        SBE16CalibrationParticleKey.EXT_VOLT0_SLOPE: {TYPE: float, VALUE: 1.246381e+00, REQUIRED: True },
        SBE16CalibrationParticleKey.EXT_VOLT1_OFFSET: {TYPE: float, VALUE: -4.618105e-02, REQUIRED: True },
        SBE16CalibrationParticleKey.EXT_VOLT1_SLOPE: {TYPE: float, VALUE: 1.247197e+00, REQUIRED: True },
        SBE16CalibrationParticleKey.EXT_VOLT2_OFFSET: {TYPE: float, VALUE: -4.659790e-02, REQUIRED: True },
        SBE16CalibrationParticleKey.EXT_VOLT2_SLOPE: {TYPE: float, VALUE: 1.247601e+00, REQUIRED: True },
        SBE16CalibrationParticleKey.EXT_VOLT3_OFFSET: {TYPE: float, VALUE: -4.502421e-02, REQUIRED: True },
        SBE16CalibrationParticleKey.EXT_VOLT3_SLOPE: {TYPE: float, VALUE: 1.246911e+00, REQUIRED: True },
        SBE16CalibrationParticleKey.EXT_VOLT4_OFFSET: {TYPE: float, VALUE: -4.589158e-02, REQUIRED: True },
        SBE16CalibrationParticleKey.EXT_VOLT4_SLOPE: {TYPE: float, VALUE: 1.246346e+00, REQUIRED: True },
        SBE16CalibrationParticleKey.EXT_VOLT5_OFFSET: {TYPE: float, VALUE: -4.609895e-02, REQUIRED: True },
        SBE16CalibrationParticleKey.EXT_VOLT5_SLOPE: {TYPE: float, VALUE: 1.247868e+00, REQUIRED: True },
        SBE16CalibrationParticleKey.EXT_FREQ: {TYPE: float, VALUE: 9.999949e-01, REQUIRED: True },
    }

    # Calibration particle definition for a 16 with a quartz  pressure sensor
    _calibration_parameters_quartz = dict(
        {
            SBE16CalibrationParticleKey.PRES_SERIAL_NUMBER: {TYPE: int, VALUE: 125270, REQUIRED: True },
            SBE16CalibrationParticleKey.PRES_RANGE: {TYPE: int, VALUE: 1000, REQUIRED: True },
            SBE16CalibrationParticleKey.PRES_CAL_DATE: {TYPE: unicode, VALUE: '02-nov-12', REQUIRED: True },
            SBE16CalibrationParticleKey.PC1: {TYPE: float, VALUE: -4.642673e+03, REQUIRED: True },
            SBE16CalibrationParticleKey.PC2: {TYPE: float, VALUE: -4.611640e-03, REQUIRED: True },
            SBE16CalibrationParticleKey.PC3: {TYPE: float, VALUE: 8.921190e-04, REQUIRED: True },
            SBE16CalibrationParticleKey.PD1: {TYPE: float, VALUE: 7.024800e-02, REQUIRED: True },
            SBE16CalibrationParticleKey.PD2: {TYPE: float, VALUE: 0.000000e+00, REQUIRED: True },
            SBE16CalibrationParticleKey.PT1: {TYPE: float, VALUE: 3.022595e+01, REQUIRED: True },
            SBE16CalibrationParticleKey.PT2: {TYPE: float, VALUE: -1.549720e-04, REQUIRED: True },
            SBE16CalibrationParticleKey.PT3: {TYPE: float, VALUE: 2.677750e-06, REQUIRED: True },
            SBE16CalibrationParticleKey.PT4: {TYPE: float, VALUE: 1.705490e-09, REQUIRED: True },
            SBE16CalibrationParticleKey.PSLOPE: {TYPE: float, VALUE: 1.000000e+00, REQUIRED: True },
            SBE16CalibrationParticleKey.POFFSET: {TYPE: float, VALUE: 0.000000e+00, REQUIRED: True },
            },
        **_calibration_parameters_base
    )

    # Calibration particle definition for a 16 with a stain gauge  pressure sensor
    _calibration_parameters_strain = dict(
        {
            SBE16CalibrationParticleKey.PRES_SERIAL_NUMBER: {TYPE: int, VALUE: 3230195, REQUIRED: True },
            SBE16CalibrationParticleKey.PRES_RANGE: {TYPE: int, VALUE: 160, REQUIRED: True },
            SBE16CalibrationParticleKey.PRES_CAL_DATE: {TYPE: unicode, VALUE: '11-May-11', REQUIRED: True },
            SBE16CalibrationParticleKey.PA0: {TYPE: float, VALUE: 4.960417e-02, REQUIRED: True },
            SBE16CalibrationParticleKey.PA1: {TYPE: float, VALUE: 4.883682e-04, REQUIRED: True },
            SBE16CalibrationParticleKey.PA2: {TYPE: float, VALUE: -5.687309e-12, REQUIRED: True },
            SBE16CalibrationParticleKey.PTCA0: {TYPE: float, VALUE: 5.249802e+05, REQUIRED: True },
            SBE16CalibrationParticleKey.PTCA1: {TYPE: float, VALUE: 7.595719e+00, REQUIRED: True },
            SBE16CalibrationParticleKey.PTCA2: {TYPE: float, VALUE: -1.322776e-01, REQUIRED: True },
            SBE16CalibrationParticleKey.PTCB0: {TYPE: float, VALUE: 2.503125e+01, REQUIRED: True },
            SBE16CalibrationParticleKey.PTCB1: {TYPE: float, VALUE: 5.000000e-05, REQUIRED: True },
            SBE16CalibrationParticleKey.PTCB2: {TYPE: float, VALUE: 0.000000e+003, REQUIRED: True },
            SBE16CalibrationParticleKey.PTEMPA0: {TYPE: float, VALUE: -6.431504e+01, REQUIRED: True },
            SBE16CalibrationParticleKey.PTEMPA1: {TYPE: float, VALUE: 5.168177e+01, REQUIRED: True },
            SBE16CalibrationParticleKey.PTEMPA2: {TYPE: float, VALUE: -2.847757e-01, REQUIRED: True },
            SBE16CalibrationParticleKey.POFFSET: {TYPE: float, VALUE: 0.000000e+00, REQUIRED: True },
        },
        **_calibration_parameters_base
    )

    ###
    #   Driver Parameter Methods
    ###
    def assert_driver_parameters(self, current_parameters, verify_values = False):
        """
        Verify that all driver parameters are correct and potentially verify values.
        @param current_parameters: driver parameters read from the driver instance
        @param verify_values: should we verify values against definition?
        """
        self.assert_parameters(current_parameters, self._driver_parameters, verify_values)

    def assert_particle_sample(self, data_particle, verify_values = False):
        '''
        Verify sample particle
        @param data_particle:  SBE16DataParticle data particle
        @param verify_values:  bool, should we verify parameter values
        '''
        self.assert_data_particle_keys(SBE16DataParticleKey, self._sample_parameters)
        self.assert_data_particle_header(data_particle, DataParticleType.CTD_PARSED, require_instrument_timestamp=True)
        self.assert_data_particle_parameters(data_particle, self._sample_parameters, verify_values)

    def assert_particle_status(self, data_particle, verify_values = False):
        '''
        Verify status particle
        @param data_particle:  SBE16StatusParticle data particle
        @param verify_values:  bool, should we verify parameter values
        '''
        self.assert_data_particle_keys(SBE16StatusParticleKey, self._status_parameters)
        self.assert_data_particle_header(data_particle, DataParticleType.DEVICE_STATUS)
        self.assert_data_particle_parameters(data_particle, self._status_parameters, verify_values)

    def assert_particle_calibration_quartz(self, data_particle, verify_values = False):
        '''
        Verify calibration particle
        @param data_particle:  SBE16CalibrationParticle data particle
        @param verify_values:  bool, should we verify parameter values
        '''
        # Have to skip this test because the parameter set is dynamic
        #self.assert_data_particle_keys(SBE16CalibrationParticleKey, self._calibration_parameters_quartz)
        self.assert_data_particle_header(data_particle, DataParticleType.DEVICE_CALIBRATION)
        self.assert_data_particle_parameters(data_particle, self._calibration_parameters_quartz, verify_values)

    def assert_particle_calibration_strain(self, data_particle, verify_values = False):
        '''
        Verify calibration particle
        @param data_particle:  SBE16CalibrationParticle data particle
        @param verify_values:  bool, should we verify parameter values
        '''
        # Have to skip this test because the parameter set is dynamic
        #self.assert_data_particle_keys(SBE16CalibrationParticleKey, self._calibration_parameters_strain)
        self.assert_data_particle_header(data_particle, DataParticleType.DEVICE_CALIBRATION)
        self.assert_data_particle_parameters(data_particle, self._calibration_parameters_strain, verify_values)

    def assert_granule_calibration_strain(self, granule, verify_values = False):
        '''
        Verify calibration granule
        @param data_particle:  SBE16CalibrationParticle data granule
        @param verify_values:  bool, should we verify parameter values
        '''
        # Have to skip this test because the parameter set is dynamic
        #self.assert_data_particle_keys(SBE16CalibrationParticleKey, self._calibration_parameters_strain)
        self.assert_data_particle_header(granule, DataParticleType.DEVICE_CALIBRATION)
        self.assert_data_particle_parameters(granule, self._calibration_parameters_strain, verify_values)

#################################### RULES ####################################
#                                                                             #
# Common capabilities in the base class                                       #
#                                                                             #
# Instrument specific stuff in the derived class                              #
#                                                                             #
# Generator spits out either stubs or comments describing test this here,     #
# test that there.                                                            #
#                                                                             #
# Qualification tests are driven through the instrument_agent                 #
#                                                                             #
###############################################################################

###############################################################################
#                                UNIT TESTS                                   #
#         Unit tests test the method calls and parameters using Mock.         #
###############################################################################

@attr('UNIT', group='mi')
class SBEUnitTestCase(SeaBirdUnitTest, SeaBird16plusMixin):
    """Unit Test Driver"""
    def test_driver_enums(self):
        """
        Verify that all driver enumeration has no duplicate values that might cause confusion.  Also
        do a little extra validation for the Capabilites
        """
        self.assert_enum_has_no_duplicates(Command())
        self.assert_enum_has_no_duplicates(ScheduledJob())
        self.assert_enum_has_no_duplicates(DataParticleType())
        self.assert_enum_has_no_duplicates(ProtocolState())
        self.assert_enum_has_no_duplicates(ProtocolEvent())

        self.assert_enum_has_no_duplicates(Parameter())
        self.assert_enum_complete(ConfirmedParameter(), Parameter())

        # Test capabilites for duplicates, them verify that capabilities is a subset of proto events
        self.assert_enum_has_no_duplicates(Capability())
        self.assert_enum_complete(Capability(), ProtocolEvent())

    def test_driver_schema(self):
        """
        get the driver schema and verify it is configured properly
        """
        driver = self.InstrumentDriver(self._got_data_event_callback)
        self.assert_driver_schema(driver, self._driver_parameters, self._driver_capabilities)

    def test_chunker(self):
        """
        Test the chunker and verify the particles created.
        """
        chunker = StringChunker(SBE16Protocol.sieve_function)

        self.assert_chunker_sample(chunker, self.VALID_SAMPLE)
        self.assert_chunker_sample_with_noise(chunker, self.VALID_SAMPLE)
        self.assert_chunker_fragmented_sample(chunker, self.VALID_SAMPLE)
        self.assert_chunker_combined_sample(chunker, self.VALID_SAMPLE)

        self.assert_chunker_sample(chunker, self.VALID_SAMPLE2)
        self.assert_chunker_sample_with_noise(chunker, self.VALID_SAMPLE2)
        self.assert_chunker_fragmented_sample(chunker, self.VALID_SAMPLE2)
        self.assert_chunker_combined_sample(chunker, self.VALID_SAMPLE2)

        self.assert_chunker_sample(chunker, self.VALID_DS_RESPONSE)
        self.assert_chunker_sample_with_noise(chunker, self.VALID_DS_RESPONSE)
        self.assert_chunker_fragmented_sample(chunker, self.VALID_DS_RESPONSE, 64)
        self.assert_chunker_combined_sample(chunker, self.VALID_DS_RESPONSE)

        self.assert_chunker_sample(chunker, self.VALID_DCAL_QUARTZ)
        self.assert_chunker_sample_with_noise(chunker, self.VALID_DCAL_QUARTZ)
        self.assert_chunker_fragmented_sample(chunker, self.VALID_DCAL_QUARTZ, 64)
        self.assert_chunker_combined_sample(chunker, self.VALID_DCAL_QUARTZ)

        self.assert_chunker_sample(chunker, self.VALID_DCAL_STRAIN)
        self.assert_chunker_sample_with_noise(chunker, self.VALID_DCAL_STRAIN)
        self.assert_chunker_fragmented_sample(chunker, self.VALID_DCAL_STRAIN, 64)
        self.assert_chunker_combined_sample(chunker, self.VALID_DCAL_STRAIN)

    def test_got_data(self):
        """
        Verify sample data passed through the got data method produces the correct data particles
        """
        # Create and initialize the instrument driver with a mock port agent
        driver = self.InstrumentDriver(self._got_data_event_callback)
        self.assert_initialize_driver(driver)

        self.assert_raw_particle_published(driver, True)

        # Start validating data particles
        self.assert_particle_published(driver, self.VALID_SAMPLE, self.assert_particle_sample, True)
        self.assert_particle_published(driver, self.VALID_SAMPLE2, self.assert_particle_sample, True)
        self.assert_particle_published(driver, self.VALID_DS_RESPONSE, self.assert_particle_status, True)
        self.assert_particle_published(driver, self.VALID_DCAL_QUARTZ, self.assert_particle_calibration_quartz, True)
        self.assert_particle_published(driver, self.VALID_DCAL_STRAIN, self.assert_particle_calibration_strain, True)

    def test_capabilities(self):
        """
        Verify the FSM reports capabilities as expected.  All states defined in this dict must
        also be defined in the protocol FSM.
        """
        capabilities = {
            ProtocolState.UNKNOWN: ['DRIVER_EVENT_DISCOVER'],
            ProtocolState.TEST: ['DRIVER_EVENT_GET',
                                 'DRIVER_EVENT_RUN_TEST'],
            ProtocolState.COMMAND: ['DRIVER_EVENT_ACQUIRE_SAMPLE',
                                    'DRIVER_EVENT_ACQUIRE_STATUS',
                                    'DRIVER_EVENT_CLOCK_SYNC',
                                    'DRIVER_EVENT_GET',
                                    'DRIVER_EVENT_SET',
                                    'DRIVER_EVENT_TEST',
                                    'DRIVER_EVENT_START_AUTOSAMPLE',
                                    'DRIVER_EVENT_START_DIRECT',
                                    'PROTOCOL_EVENT_GET_CONFIGURATION',
                                    'PROTOCOL_EVENT_RESET_EC',
                                    'PROTOCOL_EVENT_QUIT_SESSION',
                                    'DRIVER_EVENT_SCHEDULED_CLOCK_SYNC'],
            ProtocolState.AUTOSAMPLE: ['DRIVER_EVENT_GET',
                                       'PROTOCOL_EVENT_QUIT_SESSION',
                                       'DRIVER_EVENT_STOP_AUTOSAMPLE',
                                       'PROTOCOL_EVENT_GET_CONFIGURATION',
                                       'DRIVER_EVENT_SCHEDULED_CLOCK_SYNC',
                                       'DRIVER_EVENT_ACQUIRE_STATUS'],
            ProtocolState.DIRECT_ACCESS: ['DRIVER_EVENT_STOP_DIRECT', 'EXECUTE_DIRECT']
        }

        driver = self.InstrumentDriver(self._got_data_event_callback)
        self.assert_capabilities(driver, capabilities)

    def test_parse_ds(self):
        """
        Create a mock port agent
        """
        driver = self.InstrumentDriver(self._got_data_event_callback)
        self.assert_initialize_driver(driver, ProtocolState.COMMAND)
        source = self.VALID_DS_RESPONSE

        baseline = driver._protocol._param_dict.get_current_timestamp()

        # First verify that parse ds sets all know parameters.
        driver._protocol._parse_dsdc_response(source, '<Executed/>')
        pd = driver._protocol._param_dict.get_all(baseline)
        log.debug("Param Dict Values: %s" % pd)
        log.debug("Param Sample: %s" % source)
        self.assert_driver_parameters(pd, True)

        # Now change some things and make sure they are parsed properly
        # Note:  Only checking parameters that can change.

        # Logging
        source = source.replace("= not logging", "= logging")
        log.debug("Param Sample: %s" % source)
        driver._protocol._parse_dsdc_response(source, '<Executed/>')
        pd = driver._protocol._param_dict.get_all(baseline)
        self.assertTrue(pd.get(Parameter.LOGGING))

        # Sync Mode
        source = source.replace("serial sync mode disabled", "serial sync mode enabled")
        log.debug("Param Sample: %s" % source)
        driver._protocol._parse_dsdc_response(source, '<Executed/>')
        pd = driver._protocol._param_dict.get_all(baseline)
        self.assertTrue(pd.get(Parameter.SYNCMODE))

        # Pump Mode 0
        source = source.replace("run pump during sample", "no pump")
        log.debug("Param Sample: %s" % source)
        driver._protocol._parse_dsdc_response(source, '<Executed/>')
        pd = driver._protocol._param_dict.get_all(baseline)
        self.assertEqual(pd.get(Parameter.PUMP_MODE), 0)

        # Pump Mode 1
        source = source.replace("no pump", "run pump for 0.5 sec")
        log.debug("Param Sample: %s" % source)
        driver._protocol._parse_dsdc_response(source, '<Executed/>')
        pd = driver._protocol._param_dict.get_all(baseline)
        self.assertEqual(pd.get(Parameter.PUMP_MODE), 1)

        # Pressure Sensor type 2
        source = source.replace("strain gauge", "quartz without temp comp")
        log.debug("Param Sample: %s" % source)
        driver._protocol._parse_dsdc_response(source, '<Executed/>')
        pd = driver._protocol._param_dict.get_all(baseline)
        self.assertEqual(pd.get(Parameter.PTYPE), 2)

        # Pressure Sensor type 3
        source = source.replace("quartz without temp comp", "quartz with temp comp")
        log.debug("Param Sample: %s" % source)
        driver._protocol._parse_dsdc_response(source, '<Executed/>')
        pd = driver._protocol._param_dict.get_all(baseline)
        self.assertEqual(pd.get(Parameter.PTYPE), 3)

    def test_parse_set_response(self):
        """
        Test response from set commands.
        """
        driver = self.InstrumentDriver(self._got_data_event_callback)
        self.assert_initialize_driver(driver, ProtocolState.COMMAND)

        response = "Not an error"
        driver._protocol._parse_set_response(response, Prompt.EXECUTED)
        driver._protocol._parse_set_response(response, Prompt.COMMAND)

        with self.assertRaises(InstrumentProtocolException):
            driver._protocol._parse_set_response(response, Prompt.BAD_COMMAND)

        response = "<ERROR type='INVALID ARGUMENT' msg='out of range'/>"
        with self.assertRaises(InstrumentParameterException):
            driver._protocol._parse_set_response(response, Prompt.EXECUTED)


###############################################################################
#                            INTEGRATION TESTS                                #
#     Integration test test the direct driver / instrument interaction        #
#     but making direct calls via zeromq.                                     #
#     - Common Integration tests test the driver through the instrument agent #
#     and common for all drivers (minmum requirement for ION ingestion)       #
###############################################################################

@attr('INT', group='mi')
class SBEIntTestCase(SeaBirdIntegrationTest, SeaBird16plusMixin):
    """
    Integration tests for the sbe16 driver. This class tests and shows
    use patterns for the sbe16 driver as a zmq driver process.
    """    
    def test_test(self):
        """
        Test the hardware testing mode.
        """
        self.assert_initialize_driver()

        start_time = time.time()
        timeout = time.time() + 300
        reply = self.driver_client.cmd_dvr('execute_resource', ProtocolEvent.TEST)

        self.assert_current_state(ProtocolState.TEST)

        # Test the driver is in test state.
        state = self.driver_client.cmd_dvr('get_resource_state')

        while state != ProtocolState.COMMAND:
            time.sleep(5)
            elapsed = time.time() - start_time
            log.info('Device testing %f seconds elapsed.' % elapsed)
            state = self.driver_client.cmd_dvr('get_resource_state')
            self.assertLess(time.time(), timeout, msg="Timeout waiting for instrument to come out of test")

        # Verify we received the test result and it passed.
        test_results = [evt for evt in self.events if evt['type']==DriverAsyncEvent.RESULT]
        self.assertTrue(len(test_results) == 1)
        self.assertEqual(test_results[0]['value']['success'], 'Passed')

    def test_parameters(self):
        """
        Test driver parameters and verify their type.  Startup parameters also verify the parameter
        value.  This test confirms that parameters are being read/converted properly and that
        the startup has been applied.
        """
        self.assert_initialize_driver()
        reply = self.driver_client.cmd_dvr('get_resource', Parameter.ALL)
        self.assert_driver_parameters(reply, True)

    def test_set(self):
        """
        Test all set commands. Verify all exception cases.
        """
        self.assert_initialize_driver()

        # Verify we can set all parameters in bulk
        new_values = {
            Parameter.INTERVAL: 20,
            Parameter.PUMP_MODE: 0,
            Parameter.NCYCLES: 6
        }
        self.assert_set_bulk(new_values)

        # Pump Mode
        # x=0: No pump.
        # x=1: Run pump for 0.5 sec before each sample.
        # x=2: Run pump during each sample.
        self.assert_set(Parameter.PUMP_MODE, 0)
        self.assert_set(Parameter.PUMP_MODE, 1)
        self.assert_set(Parameter.PUMP_MODE, 2)
        self.assert_set_exception(Parameter.PUMP_MODE, -1)
        self.assert_set_exception(Parameter.PUMP_MODE, 3)
        self.assert_set_exception(Parameter.PUMP_MODE, 'bad')

        # NCYCLE Range 1 - 100
        self.assert_set(Parameter.NCYCLES, 1)
        self.assert_set(Parameter.NCYCLES, 100)
        self.assert_set_exception(Parameter.NCYCLES, 0)
        self.assert_set_exception(Parameter.NCYCLES, 101)
        self.assert_set_exception(Parameter.NCYCLES, -1)
        self.assert_set_exception(Parameter.NCYCLES, 0.1)
        self.assert_set_exception(Parameter.NCYCLES, 'bad')

        # SampleInterval Range 10 - 14,400
        self.assert_set(Parameter.INTERVAL, 10)
        self.assert_set(Parameter.INTERVAL, 14400)
        self.assert_set_exception(Parameter.INTERVAL, 9)
        self.assert_set_exception(Parameter.INTERVAL, 14401)
        self.assert_set_exception(Parameter.INTERVAL, -1)
        self.assert_set_exception(Parameter.INTERVAL, 0.1)
        self.assert_set_exception(Parameter.INTERVAL, 'bad')

        # Read only parameters
        self.assert_set_readonly(Parameter.ECHO, False)
        self.assert_set_readonly(Parameter.OUTPUT_EXEC_TAG, False)
        self.assert_set_readonly(Parameter.TXREALTIME, False)
        self.assert_set_readonly(Parameter.BIOWIPER, False)
        self.assert_set_readonly(Parameter.PTYPE, 1)
        self.assert_set_readonly(Parameter.VOLT0, False)
        self.assert_set_readonly(Parameter.VOLT1, False)
        self.assert_set_readonly(Parameter.VOLT2, False)
        self.assert_set_readonly(Parameter.VOLT3, False)
        self.assert_set_readonly(Parameter.VOLT4, False)
        self.assert_set_readonly(Parameter.VOLT5, False)
        self.assert_set_readonly(Parameter.DELAY_BEFORE_SAMPLE, 1)
        self.assert_set_readonly(Parameter.DELAY_AFTER_SAMPLE, 1)
        self.assert_set_readonly(Parameter.SBE63, False)
        self.assert_set_readonly(Parameter.SBE38, False)
        self.assert_set_readonly(Parameter.SBE50, False)
        self.assert_set_readonly(Parameter.WETLABS, False)
        self.assert_set_readonly(Parameter.GTD, False)
        self.assert_set_readonly(Parameter.OPTODE, False)
        self.assert_set_readonly(Parameter.SYNCMODE, False)
        self.assert_set_readonly(Parameter.SYNCWAIT, 1)
        self.assert_set_readonly(Parameter.OUTPUT_FORMAT, 1)
        self.assert_set_readonly(Parameter.LOGGING, False)

    def test_startup_params(self):
        """
        Verify that startup parameters are applied correctly. Generally this
        happens in the driver discovery method.
        """

        # Explicitly verify these values after discover.  They should match
        # what the startup values should be
        get_values = {
            Parameter.INTERVAL: 10,
            Parameter.PUMP_MODE: 2,
            Parameter.NCYCLES: 4
        }

        # Change the values of these parameters to something before the
        # driver is reinitalized.  They should be blown away on reinit.
        new_values = {
            Parameter.INTERVAL: 20,
            Parameter.PUMP_MODE: 0,
            Parameter.NCYCLES: 6
        }

        self.assert_initialize_driver()
        self.assert_startup_parameters(self.assert_driver_parameters, new_values, get_values)

        # Start autosample and try again
        self.assert_set_bulk(new_values)
        self.assert_driver_command(ProtocolEvent.START_AUTOSAMPLE, state=ProtocolState.AUTOSAMPLE, delay=1)
        self.assert_startup_parameters(self.assert_driver_parameters)
        self.assert_current_state(ProtocolState.AUTOSAMPLE)

    def test_commands(self):
        """
        Run instrument commands from both command and streaming mode.
        """
        self.assert_initialize_driver()

        ####
        # First test in command mode
        ####
        self.assert_driver_command(ProtocolEvent.CLOCK_SYNC)
        self.assert_driver_command(ProtocolEvent.SCHEDULED_CLOCK_SYNC)
        self.assert_driver_command(ProtocolEvent.QUIT_SESSION)
        self.assert_driver_command(ProtocolEvent.START_AUTOSAMPLE, state=ProtocolState.AUTOSAMPLE, delay=1)
        self.assert_driver_command(ProtocolEvent.STOP_AUTOSAMPLE, state=ProtocolState.COMMAND, delay=1)
        self.assert_driver_command(ProtocolEvent.ACQUIRE_STATUS, regex=r'serial sync mode')
        self.assert_driver_command(ProtocolEvent.RESET_EC)

        self.assert_driver_command(ProtocolEvent.ACQUIRE_STATUS, regex=r'serial sync mode')
        self.assert_driver_command(ProtocolEvent.GET_CONFIGURATION, regex=r'EXTFREQSF =')

        ####
        # Test in streaming mode
        ####
        # Put us in streaming
        self.assert_driver_command(ProtocolEvent.START_AUTOSAMPLE, state=ProtocolState.AUTOSAMPLE, delay=1)

        self.assert_driver_command(ProtocolEvent.SCHEDULED_CLOCK_SYNC)
        self.assert_driver_command(ProtocolEvent.ACQUIRE_STATUS, regex=r'serial sync mode')
        self.assert_driver_command(ProtocolEvent.GET_CONFIGURATION, regex=r'EXTFREQSF =')
        self.assert_driver_command(ProtocolEvent.QUIT_SESSION)

        self.assert_driver_command(ProtocolEvent.STOP_AUTOSAMPLE, state=ProtocolState.COMMAND, delay=1)

        ####
        # Test a bad command
        ####
        self.assert_driver_command_exception('ima_bad_command', exception_class=InstrumentCommandException)

    def test_autosample(self):
        """
        Verify that we can enter streaming and that all particles are produced
        properly.

        Because we have to test for three different data particles we can't use
        the common assert_sample_autosample method
        """
        self.assert_initialize_driver()
        self.assert_set(Parameter.INTERVAL, 10)

        self.assert_driver_command(ProtocolEvent.START_AUTOSAMPLE, state=ProtocolState.AUTOSAMPLE, delay=1)
        self.assert_async_particle_generation(DataParticleType.CTD_PARSED, self.assert_particle_sample, timeout=60)

        self.assert_particle_generation(ProtocolEvent.ACQUIRE_STATUS, DataParticleType.DEVICE_STATUS, self.assert_particle_status)
        self.assert_particle_generation(ProtocolEvent.GET_CONFIGURATION, DataParticleType.DEVICE_CALIBRATION, self.assert_particle_calibration_strain)

        self.assert_driver_command(ProtocolEvent.STOP_AUTOSAMPLE, state=ProtocolState.COMMAND, delay=1)

    def test_polled(self):
        """
        Test that we can generate particles with commands
        """
        self.assert_initialize_driver()

        self.assert_particle_generation(ProtocolEvent.GET_CONFIGURATION, DataParticleType.DEVICE_CALIBRATION, self.assert_particle_calibration_strain)
        self.assert_particle_generation(ProtocolEvent.ACQUIRE_STATUS, DataParticleType.DEVICE_STATUS, self.assert_particle_status)
        self.assert_particle_generation(ProtocolEvent.ACQUIRE_SAMPLE, DataParticleType.CTD_PARSED, self.assert_particle_sample)

    ###
    #   Test scheduled events
    ###
    def assert_calibration_coefficients(self):
        """
        Verify a calibration particle was generated
        """
        self.clear_events()
        self.assert_async_particle_generation(DataParticleType.DEVICE_CALIBRATION, self.assert_particle_calibration_strain, timeout=120)

    def test_scheduled_device_configuration_command(self):
        """
        Verify the device configuration command can be triggered and run in command
        """
        self.assert_scheduled_event(ScheduledJob.CONFIGURATION_DATA, self.assert_calibration_coefficients, delay=120)
        self.assert_current_state(ProtocolState.COMMAND)

    def test_scheduled_device_configuration_autosample(self):
        """
        Verify the device configuration command can be triggered and run in autosample
        """
        self.assert_scheduled_event(ScheduledJob.CONFIGURATION_DATA, self.assert_calibration_coefficients,
                                    autosample_command=ProtocolEvent.START_AUTOSAMPLE, delay=180)
        self.assert_current_state(ProtocolState.AUTOSAMPLE)
        self.assert_driver_command(ProtocolEvent.STOP_AUTOSAMPLE)

    def assert_acquire_status(self):
        """
        Verify a status particle was generated
        """
        self.clear_events()
        self.assert_async_particle_generation(DataParticleType.DEVICE_STATUS, self.assert_particle_status, timeout=120)

    def test_scheduled_device_status_command(self):
        """
        Verify the device status command can be triggered and run in command
        """
        self.assert_scheduled_event(ScheduledJob.ACQUIRE_STATUS, self.assert_acquire_status, delay=120)
        self.assert_current_state(ProtocolState.COMMAND)

    def test_scheduled_device_status_autosample(self):
        """
        Verify the device status command can be triggered and run in autosample
        """
        self.assert_scheduled_event(ScheduledJob.ACQUIRE_STATUS, self.assert_acquire_status,
                                    autosample_command=ProtocolEvent.START_AUTOSAMPLE, delay=180)
        self.assert_current_state(ProtocolState.AUTOSAMPLE)
        self.assert_driver_command(ProtocolEvent.STOP_AUTOSAMPLE)

    def test_scheduled_clock_sync_command(self):
        """
        Verify the scheduled clock sync is triggered and functions as expected
        """
        timeout = 120
        self.assert_scheduled_event(ScheduledJob.CLOCK_SYNC, delay=timeout)
        self.assert_current_state(ProtocolState.COMMAND)

        # Set the clock to some time in the past
        # Need an easy way to do this now that DATE_TIME is read only
        #self.assert_set_clock(Parameter.DATE_TIME, time_override=SBE_EPOCH)

        # Check the clock until it is set correctly (by a schedued event)
        #self.assert_clock_set(Parameter.DATE_TIME, sync_clock_cmd=ProtocolEvent.GET_CONFIGURATION, timeout=timeout)

    def test_scheduled_clock_sync_autosample(self):
        """
        Verify the scheduled clock sync is triggered and functions as expected
        """
        timeout = 240
        self.assert_scheduled_event(ScheduledJob.CLOCK_SYNC, delay=timeout)
        self.assert_current_state(ProtocolState.COMMAND)

        # Set the clock to some time in the past
        # Need an easy way to do this now that DATE_TIME is read only
        #self.assert_set_clock(Parameter.DATE_TIME, time_override=SBE_EPOCH)
        self.assert_driver_command(ProtocolEvent.START_AUTOSAMPLE)

        # Check the clock until it is set correctly (by a scheduled event)
        #self.assert_clock_set(Parameter.DATE_TIME, sync_clock_cmd=ProtocolEvent.GET_CONFIGURATION, timeout=timeout, tolerance=10)

    def assert_cycle(self):
        self.assert_current_state(ProtocolState.COMMAND)
        self.assert_driver_command(ProtocolEvent.START_AUTOSAMPLE)
        self.assert_current_state(ProtocolState.AUTOSAMPLE)

        self.assert_async_particle_generation(DataParticleType.CTD_PARSED, self.assert_particle_sample, particle_count = 6, timeout=60)
        self.assert_particle_generation(ProtocolEvent.ACQUIRE_STATUS, DataParticleType.DEVICE_STATUS, self.assert_particle_status)
        self.assert_particle_generation(ProtocolEvent.GET_CONFIGURATION, DataParticleType.DEVICE_CALIBRATION, self.assert_particle_calibration_strain)

        self.assert_driver_command(ProtocolEvent.STOP_AUTOSAMPLE)
        self.assert_current_state(ProtocolState.COMMAND)

    def test_discover(self):
        """
        Verify we can discover from both command and auto sample modes
        """
        self.assert_initialize_driver()
        self.assert_cycle()
        self.assert_cycle()

###############################################################################
#                            QUALIFICATION TESTS                              #
# Device specific qualification tests are for                                 #
# testing device specific capabilities                                        #
###############################################################################

@attr('QUAL', group='mi')
class SBEQualTestCase(SeaBirdQualificationTest, SeaBird16plusMixin):
    """Qualification Test Container"""

    def test_autosample(self):
        """
        Verify autosample works and data particles are created
        """
        self.assert_enter_command_mode()
        self.assert_set_parameter(Parameter.INTERVAL, 10)

        self.assert_start_autosample()
        self.assert_particle_async(DataParticleType.CTD_PARSED, self.assert_particle_sample)

        self.assert_particle_polled(ProtocolEvent.ACQUIRE_STATUS, self.assert_particle_status, DataParticleType.DEVICE_STATUS, sample_count=1, timeout=20)
        self.assert_particle_polled(ProtocolEvent.GET_CONFIGURATION, self.assert_particle_calibration_strain, DataParticleType.DEVICE_CALIBRATION, sample_count=1, timeout=20)

        # Stop autosample and do run a couple commands.
        self.assert_stop_autosample()

        self.assert_particle_polled(ProtocolEvent.ACQUIRE_STATUS, self.assert_particle_status, DataParticleType.DEVICE_STATUS, sample_count=1)
        self.assert_particle_polled(ProtocolEvent.GET_CONFIGURATION, self.assert_particle_calibration_strain, DataParticleType.DEVICE_CALIBRATION, sample_count=1)

        # Restart autosample and gather a couple samples
        self.assert_sample_autosample(self.assert_particle_sample, DataParticleType.CTD_PARSED)

    def assert_cycle(self):
        self.assert_start_autosample()

        self.assert_particle_async(DataParticleType.CTD_PARSED, self.assert_particle_sample)

        self.assert_particle_polled(ProtocolEvent.ACQUIRE_STATUS, self.assert_particle_status, DataParticleType.DEVICE_STATUS, sample_count=1, timeout=20)
        self.assert_particle_polled(ProtocolEvent.GET_CONFIGURATION, self.assert_particle_calibration_strain, DataParticleType.DEVICE_CALIBRATION, sample_count=1, timeout=20)

        self.assert_stop_autosample()

        self.assert_particle_polled(ProtocolEvent.ACQUIRE_STATUS, self.assert_particle_status, DataParticleType.DEVICE_STATUS, sample_count=1)
        self.assert_particle_polled(ProtocolEvent.GET_CONFIGURATION, self.assert_particle_calibration_strain, DataParticleType.DEVICE_CALIBRATION, sample_count=1)

    def test_cycle(self):
        """
        Verify we can bounce between command and streaming.  We try it a few times to see if we can find a timeout.
        """
        self.assert_enter_command_mode()

        self.assert_cycle()
        self.assert_cycle()
        self.assert_cycle()
        self.assert_cycle()

    def test_poll(self):
        '''
        Verify that we can poll for a sample.  Take sample for this instrument
        Also poll for other engineering data streams.
        '''
        self.assert_enter_command_mode()

        self.assert_particle_polled(ProtocolEvent.ACQUIRE_SAMPLE, self.assert_particle_sample, DataParticleType.CTD_PARSED, sample_count=1)
        self.assert_particle_polled(ProtocolEvent.ACQUIRE_STATUS, self.assert_particle_status, DataParticleType.DEVICE_STATUS, sample_count=1)
        self.assert_particle_polled(ProtocolEvent.GET_CONFIGURATION, self.assert_particle_calibration_strain, DataParticleType.DEVICE_CALIBRATION, sample_count=1)

    def test_direct_access_telnet_mode(self):
        """
        @brief This test manually tests that the Instrument Driver properly supports direct access to the physical instrument. (telnet mode)
        """
        self.assert_enter_command_mode()
        self.assert_set_parameter(Parameter.INTERVAL, 10)

        # go into direct access, and muck up a setting.
        self.assert_direct_access_start_telnet(timeout=600)
        self.tcp_client.send_data("%sampleinterval=97%s" % (NEWLINE, NEWLINE))
        self.tcp_client.expect(Prompt.EXECUTED)

        self.assert_direct_access_stop_telnet()

        # verify the setting got restored.
        self.assert_enter_command_mode()
        self.assert_get_parameter(Parameter.INTERVAL, 10)

    def test_execute_clock_sync(self):
        """
        Verify we can syncronize the instrument internal clock
        """
        self.assert_enter_command_mode()

        self.assert_execute_resource(ProtocolEvent.CLOCK_SYNC)
        self.assert_execute_resource(ProtocolEvent.ACQUIRE_STATUS)

        # Now verify that at least the date matches
        check_new_params = self.instrument_agent_client.get_resource([Parameter.DATE_TIME])
        instrument_time = time.mktime(time.strptime(check_new_params.get(Parameter.DATE_TIME).lower(), "%d %b %Y %H:%M:%S"))
        self.assertLessEqual(abs(instrument_time - time.mktime(time.gmtime())), 15)

    def test_get_capabilities(self):
        """
        @brief Verify that the correct capabilities are returned from get_capabilities
        at various driver/agent states.
        """
        self.assert_enter_command_mode()

        ##################
        #  Command Mode
        ##################
        capabilities = {
            AgentCapabilityType.AGENT_COMMAND: self._common_agent_commands(ResourceAgentState.COMMAND),
            AgentCapabilityType.AGENT_PARAMETER: self._common_agent_parameters(),
            AgentCapabilityType.RESOURCE_COMMAND: [
                ProtocolEvent.TEST,
                ProtocolEvent.GET,
                ProtocolEvent.SET,
                ProtocolEvent.RESET_EC,
                ProtocolEvent.CLOCK_SYNC,
                ProtocolEvent.QUIT_SESSION,
                ProtocolEvent.ACQUIRE_STATUS,
                ProtocolEvent.START_AUTOSAMPLE,
                ProtocolEvent.GET_CONFIGURATION,
                ],
            AgentCapabilityType.RESOURCE_INTERFACE: None,
            AgentCapabilityType.RESOURCE_PARAMETER: self._driver_parameters.keys()
        }

        self.assert_capabilities(capabilities)

        ##################
        #  Streaming Mode
        ##################

        capabilities[AgentCapabilityType.AGENT_COMMAND] = self._common_agent_commands(ResourceAgentState.STREAMING)
        capabilities[AgentCapabilityType.RESOURCE_COMMAND] =  [
            ProtocolEvent.GET,
            ProtocolEvent.STOP_AUTOSAMPLE,
            ProtocolEvent.QUIT_SESSION,
            ProtocolEvent.ACQUIRE_STATUS,
            ProtocolEvent.GET_CONFIGURATION,
            ]

        self.assert_start_autosample()
        self.assert_capabilities(capabilities)
        self.assert_stop_autosample()

        ##################
        #  DA Mode
        ##################

        capabilities[AgentCapabilityType.AGENT_COMMAND] = self._common_agent_commands(ResourceAgentState.DIRECT_ACCESS)
        capabilities[AgentCapabilityType.RESOURCE_COMMAND] = self._common_da_resource_commands()

        self.assert_direct_access_start_telnet()
        self.assert_capabilities(capabilities)
        self.assert_direct_access_stop_telnet()

        #######################
        #  Uninitialized Mode
        #######################

        capabilities[AgentCapabilityType.AGENT_COMMAND] = self._common_agent_commands(ResourceAgentState.UNINITIALIZED)
        capabilities[AgentCapabilityType.RESOURCE_COMMAND] = []
        capabilities[AgentCapabilityType.RESOURCE_INTERFACE] = []
        capabilities[AgentCapabilityType.RESOURCE_PARAMETER] = []

        self.assert_reset()
        self.assert_capabilities(capabilities)

###############################################################################
#                             PUBLICATION TESTS                               #
# Device specific pulication tests are for                                    #
# testing device specific capabilities                                        #
###############################################################################
@attr('PUB', group='mi')
class SBEPubTestCase(SeaBirdPublicationTest):
    def test_granule_generation(self):
        self.assert_initialize_driver()

        # Currently these tests only verify that the data granule is generated, but the values
        # are not tested.  We will eventually need to replace log.debug with a better callback
        # function that actually tests the granule.
        self.assert_sample_async("raw data", log.debug, DataParticleType.RAW, timeout=10)

        self.assert_sample_async(self.VALID_SAMPLE, log.debug, DataParticleType.CTD_PARSED, timeout=10)
        self.assert_sample_async(self.VALID_DS_RESPONSE, log.debug, DataParticleType.DEVICE_STATUS, timeout=10)
        self.assert_sample_async(self.VALID_DCAL_STRAIN, log.debug, DataParticleType.DEVICE_CALIBRATION, timeout=10)
        self.assert_sample_async(self.VALID_DCAL_QUARTZ, log.debug, DataParticleType.DEVICE_CALIBRATION, timeout=10)

