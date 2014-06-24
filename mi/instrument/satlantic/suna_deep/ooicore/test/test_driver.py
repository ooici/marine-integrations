"""
@package mi.instrument.satlantic.suna_deep.ooicore.test.test_driver
@file marine-integrations/mi/instrument/satlantic/suna_deep/ooicore/driver.py
@author Rachel Manoni
@brief Test cases for ooicore driver

USAGE:
 Make tests verbose and provide stdout
    * From the IDK
       $ bin/test_driver
       $ bin/test_driver -u [-t testname]
       $ bin/test_driver -i [-t testname]
       $ bin/test_driver -q [-t testname]
    * From pyon
       $ bin/nosetests -s -v /Users/Bill/WorkSpace/marine-integrations/mi/instrument/nortek/vector/ooicore
       $ bin/nosetests -s -v /Users/Bill/WorkSpace/marine-integrations/mi/instrument/nortek/vector/ooicore -a UNIT
       $ bin/nosetests -s -v /Users/Bill/WorkSpace/marine-integrations/mi/instrument/nortek/vector/ooicore -a INT
       $ bin/nosetests -s -v /Users/Bill/WorkSpace/marine-integrations/mi/instrument/nortek/vector/ooicore -a QUAL
"""

__author__ = 'Rachel Manoni'
__license__ = 'Apache 2.0'


from nose.plugins.attrib import attr
from mock import Mock

from mi.core.log import get_logger
log = get_logger()

from mi.idk.unit_test import InstrumentDriverTestCase
from mi.idk.unit_test import InstrumentDriverUnitTestCase
from mi.idk.unit_test import InstrumentDriverIntegrationTestCase
from mi.idk.unit_test import InstrumentDriverQualificationTestCase
from mi.idk.unit_test import DriverTestMixin
from mi.idk.unit_test import AgentCapabilityType

from mi.core.common import BaseEnum

from mi.core.instrument.chunker import StringChunker
from mi.core.instrument.instrument_driver import DriverConnectionState, ResourceAgentState, DriverConfigKey, DriverEvent

from mi.instrument.satlantic.suna_deep.ooicore.driver import InstrumentDriver, SUNAStatusDataParticle, TIMEOUT, \
    SUNATestDataParticle, InstrumentCommandArgs, SUNASampleDataParticleKey, SUNAStatusDataParticleKey, \
    SUNATestDataParticleKey
from mi.instrument.satlantic.suna_deep.ooicore.driver import DataParticleType
from mi.instrument.satlantic.suna_deep.ooicore.driver import InstrumentCommand
from mi.instrument.satlantic.suna_deep.ooicore.driver import ProtocolState
from mi.instrument.satlantic.suna_deep.ooicore.driver import ProtocolEvent
from mi.instrument.satlantic.suna_deep.ooicore.driver import Capability
from mi.instrument.satlantic.suna_deep.ooicore.driver import Parameter
from mi.instrument.satlantic.suna_deep.ooicore.driver import Protocol
from mi.instrument.satlantic.suna_deep.ooicore.driver import Prompt
from mi.instrument.satlantic.suna_deep.ooicore.driver import NEWLINE
from mi.instrument.satlantic.suna_deep.ooicore.driver import SUNASampleDataParticle

from mi.core.exceptions import SampleException, InstrumentCommandException, InstrumentParameterException, \
    InstrumentProtocolException

###
#   Driver parameters for the tests
###
InstrumentDriverTestCase.initialize(
    driver_module='mi.instrument.satlantic.suna_deep.ooicore.driver',
    driver_class="InstrumentDriver",

    instrument_agent_resource_id='1BQY0H',
    instrument_agent_name='satlantic_suna_deep_ooicore',
    instrument_agent_packet_config=DataParticleType(),

    driver_startup_config={DriverConfigKey.PARAMETERS: {
            Parameter.OPERATION_MODE: InstrumentCommandArgs.POLLED,
            Parameter.OPERATION_CONTROL: "Samples",
            Parameter.LIGHT_SAMPLES: 5,
            Parameter.DARK_SAMPLES: 1,
            Parameter.LIGHT_DURATION: 10,
            Parameter.DARK_DURATION: 5,
            Parameter.NUM_LIGHT_SAMPLES: 1,
            Parameter.TIME_LIGHT_SAMPLE: 5}}
)

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
SUNA_ASCII_SAMPLE = "SATSDF0344,2014125,21.278082,0.00,0.0000,0.0000,0.0000,0.00,476,0,1,475,483,494,465,487,490,488," \
                    "477,465,471,477,476,475,469,477,482,485,485,481,481,474,467,484,472,469,483,489,488,484,497,488," \
                    "482,484,474,461,455,485,469,495,481,485,474,487,464,491,477,464,485,492,492,475,485,478,479,477," \
                    "465,455,471,482,486,482,480,486,478,484,488,480,485,485,473,480,481,485,462,469,466,455,487,488," \
                    "482,485,489,485,478,489,472,475,456,483,450,471,450,487,480,493,490,482,472,485,484,481,494,494," \
                    "482,482,468,467,467,477,472,469,487,473,475,475,481,492,468,471,477,464,487,466,487,476,466,461," \
                    "469,467,469,461,459,475,481,477,476,467,469,476,484,462,479,464,467,471,485,477,466,471,470,481," \
                    "473,493,496,470,487,478,469,471,475,464,485,472,468,462,483,481,489,482,495,481,471,471,456,459," \
                    "465,454,475,452,459,472,464,491,488,478,487,465,483,470,465,478,465,487,480,487,474,478,488,480," \
                    "469,473,463,477,466,473,485,489,486,476,471,475,470,455,471,456,459,467,457,467,477,467,475,489," \
                    "485,484,470,489,482,481,474,471,479,479,468,479,481,484,480,491,468,479,474,474,468,471,477,480," \
                    "490,484,493,480,485,464,469,477,276,0.0,0.0,-99.0,172578,6.2,12.0,0.1,5.0,54,0.00,0.00,0.0000," \
                    "0.000000,0.000000,,,,,203\r\n"


SUNA_ASCII_STATUS = "SENSTYPE SUNA\r\nSENSVERS V2\r\nSERIALNO 344\r\nINTWIPER Available\r\nEXTPPORT Missing\r\n" \
                    "LMPSHUTR Missing\r\nREFDTECT Missing\r\nPROTECTR Available\r\nSUPRCAPS Available\r\n" \
                    "PWRSVISR Available\r\nUSBSWTCH Available\r\nRELAYBRD Available\r\nSDI12BRD Available\r\n" \
                    "ANALGBRD Available\r\nINTDATLG Available\r\nAPFIFACE Available\r\nSCHDLING Available\r\n" \
                    "FANATLMP Available\r\nOWIRETLP 10d0fda4020800eb\r\nOWIRETSP 1086818d020800d8\r\n" \
                    "OWIRETHS 10707b6a020800cc\r\nZSPEC_SN 86746\r\nFIBERLSN C3.D01.1590\r\nSTUPSTUS Done\r\n" \
                    "BRNHOURS 0\r\nBRNNUMBR 0\r\nDRKHOURS 0\r\nDRKNUMBR 0\r\nCHRLDURA 600\r\nCHRDDURA 0\r\n" \
                    "BAUDRATE 57600\r\nMSGLEVEL Info\r\nMSGFSIZE 2\r\nDATFSIZE 5\r\nOUTFRTYP Full_ASCII\r\n" \
                    "LOGFRTYP Full_ASCII\r\nOUTDRKFR Output\r\nLOGDRKFR Output\r\nTIMERESL Fractsec\r\n" \
                    "LOGFTYPE Acquisition\r\nACQCOUNT 10\r\nCNTCOUNT 130\r\nDCMINNO3 -5.000\r\nDCMAXNO3 100.000\r\n" \
                    "WDAT_LOW 217.00\r\nWDAT_HGH 250.00\r\nSDI12ADD 48\r\nDATAMODE Real\r\nOPERMODE Polled\r\n" \
                    "OPERCTRL Duration\r\nEXDEVTYP None\r\nEXDEVPRE 0\r\nEXDEVRUN Off\r\nWATCHDOG On\r\nCOUNTDWN 15\r\n" \
                    "FIXDDURA 60\r\nPERDIVAL 1m\r\nPERDOFFS 0\r\nPERDDURA 5\r\nPERDSMPL 5\r\nPOLLTOUT 15\r\n" \
                    "APFATOFF 10.0000\r\nSTBLTIME 5\r\nREFLIMIT 0\r\nSKPSLEEP Off\r\nLAMPTOFF 35\r\nSPINTPER 450\r\n" \
                    "DRKAVERS 1\r\nLGTAVERS 1\r\nREFSMPLS 20\r\nDRKSMPLS 2\r\nLGTSMPLS 58\r\nDRKDURAT 2\r\n" \
                    "LGTDURAT 58\r\nTEMPCOMP Off\r\nSALINFIT On\r\nBRMTRACE Off\r\nBL_ORDER 1\r\nFITCONCS 3\r\n" \
                    "DRKCORMT SpecAverage\r\nDRKCOEFS Missing\r\nDAVGPRM0 500.000\r\nDAVGPRM1 0.00000\r\n" \
                    "DAVGPRM2 0.00000\r\nDAVGPRM3 0.000000\r\nA_CUTOFF 1.3000\r\nINTPRADJ On\r\nINTPRFAC 1\r\n" \
                    "INTADSTP 20\r\nINTADMAX 20\r\nWFIT_LOW 217.00\r\nWFIT_HGH 240.00\r\nLAMPTIME 172577\r\n" \
                    "$Ok \r\nSUNA> get activecalfile\r\nget activecalfile\r\n$Ok SNA0234H.cal"


SUNA_ASCII_TEST = "Extrn Disk Size; Free , 1960968192; 1956216832\r\n" \
                  "Intrn Disk Size; Free , 2043904; 1956864\r\n" \
                  "Fiberlite    Odometer , 0048:10:05\r\n" \
                  "Temperatures Hs Sp Lm , 22.3 21.7 21.6\r\n" \
                  "Humidity              , 5.8\r\n" \
                  "Electrical Mn Bd Pr C , 12.0 12.0 5.0 25.8\r\n" \
                  "Lamp            Power , 5505 mW\r\n" \
                  "Spec Dark av sd mi ma ,   471 (+/-     9) [  444:  494]\r\n" \
                  "Spec Lght av sd mi ma , 22308 (+/- 12009) [  455:52004]\r\n" \
                  "$Ok"


class ParameterConstraints(BaseEnum):
    OPERATION_MODE = (Parameter.OPERATION_MODE, str, InstrumentCommandArgs.CONTINUOUS, InstrumentCommandArgs.POLLED)
    OPERATION_CONTROL = (Parameter.OPERATION_CONTROL, str, 'Samples', 'Duration')
    LIGHT_SAMPLES = (Parameter.LIGHT_SAMPLES, int, 1, 65535)
    DARK_SAMPLES = (Parameter.DARK_SAMPLES, int, 1, 65535)
    LIGHT_DURATION = (Parameter.LIGHT_DURATION, int, 1, 65535)
    DARK_DURATION = (Parameter.DARK_DURATION, int, 1, 65535)
    COUNTDOWN = (Parameter.COUNTDOWN, int, 0, 3600)
    TEMP_COMPENSATION = (Parameter.TEMP_COMPENSATION, bool, True, False)
    FIT_WAVELENGTH_BOTH = (Parameter.FIT_WAVELENGTH_BOTH, str, '210,210', '350,350')
    CONCENTRATIONS_IN_FIT = (Parameter.CONCENTRATIONS_IN_FIT, int, 1, 3)
    DARK_CORRECTION_METHOD = (Parameter.DARK_CORRECTION_METHOD, str, 'SpecAverage', 'SWAverage')
    SALINITY_FITTING = (Parameter.SALINITY_FITTING, bool, True, False)
    BROMIDE_TRACING = (Parameter.BROMIDE_TRACING, bool, True, False)
    ABSORBANCE_CUTOFF = (Parameter.ABSORBANCE_CUTOFF, float, 0.01, 10.0)
    INTEG_TIME_ADJUSTMENT = (Parameter.INTEG_TIME_ADJUSTMENT, bool, True, False)
    INTEG_TIME_FACTOR = (Parameter.INTEG_TIME_FACTOR, int, 1, 20)
    INTEG_TIME_STEP = (Parameter.INTEG_TIME_STEP, int, 1, 20)
    INTEG_TIME_MAX = (Parameter.INTEG_TIME_MAX, int, 1, 20)


###############################################################################
#                        DATA PARTICLE TEST MIXIN      	                  #
#     Defines a set of constants and assert methods used for data particle    #
#     verification      #
#                                                                             #
#  In python mixin classes are classes designed such that they wouldn't be    #
#  able to stand on their own, but are inherited by other classes generally   #
#  using multiple inheritance.                                                #
#                                                                             #
# This class defines a configuration structure for testing and common assert  #
# methods for validating data particles.	  #
###############################################################################
# noinspection PyPep8
class DriverTestMixinSub(DriverTestMixin):

    _reference_sample_parameters = {
        SUNASampleDataParticleKey.FRAME_TYPE: {'type': unicode, 'value': "SDF"},
        SUNASampleDataParticleKey.SERIAL_NUM: {'type': unicode, 'value': "0344"},
        SUNASampleDataParticleKey.SAMPLE_DATE: {'type': int, 'value': 2014125},
        SUNASampleDataParticleKey.SAMPLE_TIME: {'type': float, 'value': 21.278082},
        SUNASampleDataParticleKey.NITRATE_CONCEN: {'type': float, 'value': 0.00},
        SUNASampleDataParticleKey.NITROGEN: {'type': float, 'value': 0.0000},
        SUNASampleDataParticleKey.ABSORB_254: {'type': float, 'value': 0.0000},
        SUNASampleDataParticleKey.ABSORB_350: {'type': float, 'value': 0.0000},
        SUNASampleDataParticleKey.BROMIDE_TRACE: {'type': float, 'value': 0.00},
        SUNASampleDataParticleKey.SPECTRUM_AVE: {'type': int, 'value': 476},
        SUNASampleDataParticleKey.FIT_DARK_VALUE: {'type': int, 'value': 0},
        SUNASampleDataParticleKey.TIME_FACTOR: {'type': int, 'value': 1},
        SUNASampleDataParticleKey.SPECTRAL_CHANNELS: {'type': list, 'value': [475,483,494,465,487,490,488,
                    477,465,471,477,476,475,469,477,482,485,485,481,481,474,467,484,472,469,483,489,488,484,497,488,
                    482,484,474,461,455,485,469,495,481,485,474,487,464,491,477,464,485,492,492,475,485,478,479,477,
                    465,455,471,482,486,482,480,486,478,484,488,480,485,485,473,480,481,485,462,469,466,455,487,488,
                    482,485,489,485,478,489,472,475,456,483,450,471,450,487,480,493,490,482,472,485,484,481,494,494,
                    482,482,468,467,467,477,472,469,487,473,475,475,481,492,468,471,477,464,487,466,487,476,466,461,
                    469,467,469,461,459,475,481,477,476,467,469,476,484,462,479,464,467,471,485,477,466,471,470,481,
                    473,493,496,470,487,478,469,471,475,464,485,472,468,462,483,481,489,482,495,481,471,471,456,459,
                    465,454,475,452,459,472,464,491,488,478,487,465,483,470,465,478,465,487,480,487,474,478,488,480,
                    469,473,463,477,466,473,485,489,486,476,471,475,470,455,471,456,459,467,457,467,477,467,475,489,
                    485,484,470,489,482,481,474,471,479,479,468,479,481,484,480,491,468,479,474,474,468,471,477,480,
                    490,484,493,480,485,464,469,477,276]},
        SUNASampleDataParticleKey.TEMP_INTERIOR: {'type': float, 'value': 0.0},
        SUNASampleDataParticleKey.TEMP_SPECTROMETER: {'type': float, 'value': 0.0},
        SUNASampleDataParticleKey.TEMP_LAMP: {'type': float, 'value': -99.0},
        SUNASampleDataParticleKey.LAMP_TIME: {'type': int, 'value': 172578},
        SUNASampleDataParticleKey.HUMIDITY: {'type': float, 'value': 6.2},
        SUNASampleDataParticleKey.VOLTAGE_MAIN: {'type': float, 'value': 12.0},
        SUNASampleDataParticleKey.VOLTAGE_LAMP: {'type': float, 'value': 0.1},
        SUNASampleDataParticleKey.VOLTAGE_INT: {'type': float, 'value': 5.0},
        SUNASampleDataParticleKey.CURRENT_MAIN: {'type': float, 'value': 54.0},
        SUNASampleDataParticleKey.FIT_1: {'type': float, 'value': 0.00},
        SUNASampleDataParticleKey.FIT_2: {'type': float, 'value': 0.00},
        SUNASampleDataParticleKey.FIT_BASE_1: {'type': float, 'value': 0.0000},
        SUNASampleDataParticleKey.FIT_BASE_2: {'type': float, 'value': 0.000000},
        SUNASampleDataParticleKey.FIT_RMSE: {'type': float, 'value': 0.0000000},
        SUNASampleDataParticleKey.CHECKSUM: {'type': int, 'value': 203}
    }

    _reference_status_parameters = {
        SUNAStatusDataParticleKey.SENSOR_TYPE: {'type': unicode, 'value': "SUNA"},
        SUNAStatusDataParticleKey.SENSOR_VERSION: {'type': unicode, 'value': "V2"},
        SUNAStatusDataParticleKey.SERIAL_NUMBER: {'type': unicode, 'value': '344'},
        SUNAStatusDataParticleKey.INTEGRATED_WIPER: {'type': unicode, 'value': "Available"},
        SUNAStatusDataParticleKey.EXT_POWER_PORT: {'type': unicode, 'value': "Missing"},
        SUNAStatusDataParticleKey.LAMP_SHUTTER: {'type': unicode, 'value': "Missing"},
        SUNAStatusDataParticleKey.REF_DETECTOR: {'type': unicode, 'value': "Missing"},
        SUNAStatusDataParticleKey.PROTECTR: {'type': unicode, 'value': "Available"},
        SUNAStatusDataParticleKey.SUPER_CAPACITORS: {'type': unicode, 'value': "Available"},
        SUNAStatusDataParticleKey.PSB_SUPERVISOR: {'type': unicode, 'value': "Available"},
        SUNAStatusDataParticleKey.USB_COMM: {'type': unicode, 'value': "Available"},
        SUNAStatusDataParticleKey.RELAY_MODULE: {'type': unicode, 'value': "Available"},
        SUNAStatusDataParticleKey.SDII2_INTERFACE: {'type': unicode, 'value': "Available"},
        SUNAStatusDataParticleKey.ANALOG_OUTPUT: {'type': unicode, 'value': "Available"},
        SUNAStatusDataParticleKey.DATA_LOGGING: {'type': unicode, 'value': "Available"},
        SUNAStatusDataParticleKey.APF_INTERFACE: {'type': unicode, 'value': "Available"},
        SUNAStatusDataParticleKey.SCHEDULING: {'type': unicode, 'value': "Available"},
        SUNAStatusDataParticleKey.LAMP_FAN: {'type': unicode, 'value': "Available"},
        SUNAStatusDataParticleKey.ADDR_LAMP_TEMP: {'type': unicode, 'value': '10d0fda4020800eb'},
        SUNAStatusDataParticleKey.ADDR_SPEC_TEMP: {'type': unicode, 'value': '1086818d020800d8'},
        SUNAStatusDataParticleKey.SENSOR_ADDR_HOUS_TEMP: {'type': unicode, 'value': '10707b6a020800cc'},
        SUNAStatusDataParticleKey.SERIAL_NUM_SPECT: {'type': unicode, 'value': '86746'},
        SUNAStatusDataParticleKey.SERIAL_NUM_LAMP: {'type': unicode, 'value': "C3.D01.1590"},
        SUNAStatusDataParticleKey.STUPSTUS: {'type': unicode, 'value': "Done"},
        SUNAStatusDataParticleKey.BRNHOURS: {'type': int, 'value': 0},
        SUNAStatusDataParticleKey.BRNNUMBER: {'type': int, 'value': 0},
        SUNAStatusDataParticleKey.DARK_HOURS: {'type': int, 'value': 0},
        SUNAStatusDataParticleKey.DARK_NUM: {'type': int, 'value': 0},
        SUNAStatusDataParticleKey.CHRLDURA: {'type': int, 'value': 600},
        SUNAStatusDataParticleKey.CHRDDURA: {'type': int, 'value': 0},
        SUNAStatusDataParticleKey.BAUD_RATE: {'type': int, 'value': 57600},
        SUNAStatusDataParticleKey.MSG_LEVEL: {'type': unicode, 'value': "Info"},
        SUNAStatusDataParticleKey.MSG_FILE_SIZE: {'type': int, 'value': 2},
        SUNAStatusDataParticleKey.DATA_FILE_SIZE: {'type': int, 'value': 5},
        SUNAStatusDataParticleKey.OUTPUT_FRAME_TYPE: {'type': unicode, 'value': "Full_ASCII"},
        SUNAStatusDataParticleKey.LOGGING_FRAME_TYPE: {'type': unicode, 'value': "Full_ASCII"},
        SUNAStatusDataParticleKey.OUTPUT_DARK_FRAME: {'type': unicode, 'value': "Output"},
        SUNAStatusDataParticleKey.LOGGING_DARK_FRAME: {'type': unicode, 'value': "Output"},
        SUNAStatusDataParticleKey.TIMERESL: {'type': unicode, 'value': "Fractsec"},
        SUNAStatusDataParticleKey.LOG_FILE_TYPE: {'type': unicode, 'value': "Acquisition"},
        SUNAStatusDataParticleKey.ACQCOUNT: {'type': int, 'value': 10},
        SUNAStatusDataParticleKey.CNTCOUNT: {'type': int, 'value': 130},
        SUNAStatusDataParticleKey.NITRATE_MIN: {'type': float, 'value': -5.000},
        SUNAStatusDataParticleKey.NITRATE_MAX: {'type': float, 'value': 100.000},
        SUNAStatusDataParticleKey.WAVELENGTH_LOW: {'type': float, 'value': 217.00},
        SUNAStatusDataParticleKey.WAVELENGTH_HIGH: {'type': float, 'value': 250.00},
        SUNAStatusDataParticleKey.SDI12_ADDR: {'type': int, 'value': 48},
        SUNAStatusDataParticleKey.DATAMODE: {'type': unicode, 'value': "Real"},
        SUNAStatusDataParticleKey.OPERATING_MODE: {'type': unicode, 'value': "Polled"},
        SUNAStatusDataParticleKey.OPERATION_CTRL: {'type': unicode, 'value': "Duration"},
        SUNAStatusDataParticleKey.EXTL_DEV: {'type': unicode, 'value': "None"},
        SUNAStatusDataParticleKey.PRERUN_TIME: {'type': int, 'value': 0},
        SUNAStatusDataParticleKey.DEV_DURING_ACQ: {'type': unicode, 'value': "Off"},
        SUNAStatusDataParticleKey.WATCHDOG_TIME: {'type': unicode, 'value': "On"},
        SUNAStatusDataParticleKey.COUNTDOWN: {'type': int, 'value': 15},
        SUNAStatusDataParticleKey.FIXED_TIME: {'type': int, 'value': 60},
        SUNAStatusDataParticleKey.PERIODIC_INTERVAL: {'type': unicode, 'value': "1m"},
        SUNAStatusDataParticleKey.PERIODIC_OFFSET: {'type': int, 'value': 0},
        SUNAStatusDataParticleKey.PERIODIC_DURATION: {'type': int, 'value': 5},
        SUNAStatusDataParticleKey.PERIODIC_SAMPLES: {'type': int, 'value': 5},
        SUNAStatusDataParticleKey.POLLED_TIMEOUT: {'type': int, 'value': 15},
        SUNAStatusDataParticleKey.APF_TIMEOUT: {'type': float, 'value': 10.0000},
        SUNAStatusDataParticleKey.STABILITY_TIME: {'type': int, 'value': 5},
        SUNAStatusDataParticleKey.MIN_LAMP_ON: {'type': int, 'value': 0},
        SUNAStatusDataParticleKey.SKIP_SLEEP: {'type': unicode, 'value': "Off"},
        SUNAStatusDataParticleKey.SWITCHOFF_TEMP: {'type': int, 'value': 35},
        SUNAStatusDataParticleKey.SPEC_PERIOD: {'type': int, 'value': 450},
        SUNAStatusDataParticleKey.DRKAVERS: {'type': int, 'value': 1},
        SUNAStatusDataParticleKey.LGTAVERS: {'type': int, 'value': 1},
        SUNAStatusDataParticleKey.REFSAMPLES: {'type': int, 'value': 20},
        SUNAStatusDataParticleKey.DARK_SAMPLES: {'type': int, 'value': 2},
        SUNAStatusDataParticleKey.LIGHT_SAMPLES: {'type': int, 'value': 58},
        SUNAStatusDataParticleKey.DARK_DURATION: {'type': int, 'value': 2},
        SUNAStatusDataParticleKey.LIGHT_DURATION: {'type': int, 'value': 58},
        SUNAStatusDataParticleKey.TEMP_COMP: {'type': unicode, 'value': "Off"},
        SUNAStatusDataParticleKey.SALINITY_FIT: {'type': unicode, 'value': "On"},
        SUNAStatusDataParticleKey.BROMIDE_TRACING: {'type': unicode, 'value': "Off"},
        SUNAStatusDataParticleKey.BASELINE_ORDER: {'type': int, 'value': 1},
        SUNAStatusDataParticleKey.CONCENTRATIONS_FIT: {'type': int, 'value': 3},
        SUNAStatusDataParticleKey.DARK_CORR_METHOD: {'type': unicode, 'value': "SpecAverage"},
        SUNAStatusDataParticleKey.DRKCOEFS: {'type': unicode, 'value': "Missing"},
        SUNAStatusDataParticleKey.DAVGPRM_0: {'type': float, 'value': 500.000},
        SUNAStatusDataParticleKey.DAVGPRM_1: {'type': float, 'value': 0.00000},
        SUNAStatusDataParticleKey.DAVGPRM_2: {'type': float, 'value': 0.00000},
        SUNAStatusDataParticleKey.DAVGPRM_3: {'type': float, 'value': 0.000000},
        SUNAStatusDataParticleKey.ABSORBANCE_CUTOFF: {'type': float, 'value': 1.3000},
        SUNAStatusDataParticleKey.TIME_ADJ: {'type': unicode, 'value': "On"},
        SUNAStatusDataParticleKey.TIME_FACTOR: {'type': int, 'value': 1},
        SUNAStatusDataParticleKey.TIME_STEP: {'type': int, 'value': 20},
        SUNAStatusDataParticleKey.TIME_MAX: {'type': int, 'value': 20},
        SUNAStatusDataParticleKey.FIT_WAVE_LOW: {'type': float, 'value': 217.00},
        SUNAStatusDataParticleKey.FIT_WAVE_HIGH: {'type': float, 'value': 240.00},
        SUNAStatusDataParticleKey.LAMP_TIME: {'type': int, 'value': 172577},
        SUNAStatusDataParticleKey.CALIBRATION_FILE: {'type': unicode, 'value': 'SNA0234H.cal'}
    }

    _reference_test_parameters = {
        SUNATestDataParticleKey.EXT_DISK_SIZE: {'type': int, 'value': 1960968192},
        SUNATestDataParticleKey.EXT_DISK_FREE: {'type': int, 'value': 1956216832},
        SUNATestDataParticleKey.INT_DISK_SIZE: {'type': int, 'value': 2043904},
        SUNATestDataParticleKey.INT_DISK_FREE: {'type': int, 'value': 1956864},
        SUNATestDataParticleKey.TEMP_HS: {'type': float, 'value': 22.3},
        SUNATestDataParticleKey.TEMP_SP: {'type': float, 'value': 21.7},
        SUNATestDataParticleKey.TEMP_LM: {'type': float, 'value': 21.6},
        SUNATestDataParticleKey.LAMP_TIME: {'type': int, 'value': 173405},
        SUNATestDataParticleKey.HUMIDITY: {'type': float, 'value': 5.8},
        SUNATestDataParticleKey.ELECTRICAL_MN: {'type': float, 'value': 12.0},
        SUNATestDataParticleKey.ELECTRICAL_BD: {'type': float, 'value': 12.0},
        SUNATestDataParticleKey.ELECTRICAL_PR: {'type': float, 'value': 5.0},
        SUNATestDataParticleKey.ELECTRICAL_C: {'type': float, 'value': 25.8},
        SUNATestDataParticleKey.LAMP_POWER: {'type': int, 'value': 5505},
        SUNATestDataParticleKey.SPEC_DARK_AV: {'type': int, 'value': 471},
        SUNATestDataParticleKey.SPEC_DARK_SD: {'type': int, 'value': 9},
        SUNATestDataParticleKey.SPEC_DARK_MI: {'type': int, 'value': 444},
        SUNATestDataParticleKey.SPEC_DARK_MA: {'type': int, 'value': 494},
        SUNATestDataParticleKey.SPEC_LIGHT_AV: {'type': int, 'value': 22308},
        SUNATestDataParticleKey.SPEC_LIGHT_SD: {'type': int, 'value': 12009},
        SUNATestDataParticleKey.SPEC_LIGHT_MI: {'type': int, 'value': 455},
        SUNATestDataParticleKey.SPEC_LIGHT_MA: {'type': int, 'value': 52004},
        SUNATestDataParticleKey.TEST_RESULT: {'type': unicode, 'value': "Ok"}
    }

    def assert_data_particle_sample(self, data_particle, verify_values=False):
        """
        Verify that all driver parameters are correct and potentially verify values.
        @param data_particle: driver parameters read from the driver instance
        @param verify_values:bool,  False = do not verify values against definition
        """
        self.assert_data_particle_parameters(data_particle, self._reference_sample_parameters, verify_values)

    def assert_data_particle_status(self, data_particle, verify_values=False):
        """
        Verify a SUNA status data particle
        @param data_particle: a SUNA status data particle
        @param verify_values: bool,  False = do not verify values against definition
        """
        self.assert_data_particle_parameters(data_particle, self._reference_status_parameters, verify_values)

    def assert_data_particle(self, data_particle, verify_values=False):
        """
        Verify a SUNA test data particle
        @param data_particle: a SUNA test data particle
        @param verify_values: bool, False = do not verify values against definition
        """
        self.assert_data_particle_parameters(data_particle, self._reference_test_parameters, verify_values)


###############################################################################
#                                UNIT TESTS                                   #
#         Unit tests test the method calls and parameters using Mock.         #
#                                                                             #
#   These tests are especially useful for testing parsers and other data      #
#   handling.  The tests generally focus on small segments of code, like a    #
#   single function call, but more complex code using Mock objects.  However  #
#   if you find yourself mocking too much maybe it is better as an            #
#   integration test.                                                         #
#                                                                             #
#   Unit tests do not start up external processes like the port agent or      #
#   driver process.                                                           #
###############################################################################
@attr('UNIT', group='mi')
class DriverUnitTest(InstrumentDriverUnitTestCase, DriverTestMixinSub):
    def setUp(self):
        InstrumentDriverUnitTestCase.setUp(self)

    def test_driver_enums(self):
        """
        Verify that all driver enumeration has no duplicate values that might cause confusion.  Also
        do a little extra validation for the Capabilities
        """
        self.assert_enum_has_no_duplicates(DataParticleType())
        self.assert_enum_has_no_duplicates(ProtocolState())
        self.assert_enum_has_no_duplicates(ProtocolEvent())
        self.assert_enum_has_no_duplicates(Parameter())
        self.assert_enum_has_no_duplicates(InstrumentCommand())

        # Test capabilities for duplicates, them verify that capabilities is a subset of protocol events
        self.assert_enum_has_no_duplicates(Capability())
        self.assert_enum_complete(Capability(), ProtocolEvent())

    def test_chunker(self):
        """
        Test the chunker and verify the particles created.
        """
        chunker = StringChunker(Protocol.sieve_function)

        self.assert_chunker_sample(chunker, SUNA_ASCII_SAMPLE)
        self.assert_chunker_fragmented_sample(chunker, SUNA_ASCII_SAMPLE)
        self.assert_chunker_combined_sample(chunker, SUNA_ASCII_SAMPLE)
        self.assert_chunker_sample_with_noise(chunker, SUNA_ASCII_SAMPLE)

        self.assert_chunker_sample(chunker, SUNA_ASCII_STATUS)
        self.assert_chunker_sample_with_noise(chunker, SUNA_ASCII_STATUS)
        self.assert_chunker_fragmented_sample(chunker, SUNA_ASCII_STATUS)
        self.assert_chunker_combined_sample(chunker, SUNA_ASCII_STATUS)

        self.assert_chunker_sample(chunker, SUNA_ASCII_TEST)
        self.assert_chunker_sample_with_noise(chunker, SUNA_ASCII_TEST)
        self.assert_chunker_fragmented_sample(chunker, SUNA_ASCII_TEST)
        self.assert_chunker_combined_sample(chunker, SUNA_ASCII_TEST)

    def test_corrupt_data_particles(self):
        """
        test with data partially replaced by garbage value
        """
        particle = SUNASampleDataParticle(SUNA_ASCII_SAMPLE.replace("SAT", "FOO"))
        with self.assertRaises(SampleException):
            particle.generate()

        particle = SUNAStatusDataParticle(SUNA_ASCII_STATUS.replace('SENSTYPE', 'BLAH!'))
        with self.assertRaises(SampleException):
            particle.generate()

        particle = SUNATestDataParticle(SUNA_ASCII_TEST.replace('5505 mW', '5505f.1 mW'))
        with self.assertRaises(SampleException):
            particle.generate()

    def test_got_data(self):
        """
        Verify sample data passed through the got data method produces the correct data particles
        """
        # Create and initialize the instrument driver with a mock port agent
        driver = InstrumentDriver(self._got_data_event_callback)
        self.assert_initialize_driver(driver)

        self.assert_raw_particle_published(driver, True)

        #validate data particles
        self.assert_particle_published(driver, SUNA_ASCII_SAMPLE, self.assert_data_particle_sample, True)
        self.assert_particle_published(driver, SUNA_ASCII_STATUS, self.assert_data_particle_status, True)
        self.assert_particle_published(driver, SUNA_ASCII_TEST, self.assert_data_particle, True)

    def test_protocol_filter_capabilities(self):
        """
        This tests driver filter_capabilities.
        Iterate through available capabilities, and verify that they can pass successfully through the filter.
        Test silly made up capabilities to verify they are blocked by filter.
        """
        mock_callback = Mock()
        protocol = Protocol(Prompt, NEWLINE, mock_callback)
        driver_capabilities = Capability().list()
        test_capabilities = Capability().list()

        # Add a bogus capability that will be filtered out.
        test_capabilities.append("BOGUS_CAPABILITY")

        # Verify "BOGUS_CAPABILITY was filtered out
        self.assertEquals(sorted(driver_capabilities),
                          sorted(protocol._filter_capabilities(test_capabilities)))

    # noinspection PyPep8,PyPep8,PyPep8,PyPep8
    def test_capabilities(self):
        """
        Verify the FSM reports capabilities as expected.  All states defined in this dict must
        also be defined in the protocol FSM.
        """
        capabilities = {
            ProtocolState.UNKNOWN:       [ProtocolEvent.DISCOVER],
            ProtocolState.COMMAND:       [ProtocolEvent.ACQUIRE_SAMPLE,
                                          ProtocolEvent.ACQUIRE_STATUS,
                                          ProtocolEvent.START_DIRECT,
                                          #ProtocolEvent.START_POLL,
                                          ProtocolEvent.START_AUTOSAMPLE,
                                          ProtocolEvent.GET,
                                          ProtocolEvent.SET,
                                          ProtocolEvent.TEST,
                                          ProtocolEvent.CLOCK_SYNC,
                                          ProtocolEvent.MEASURE_N,
                                          ProtocolEvent.MEASURE_0,
                                          ProtocolEvent.TIMED_N],
            ProtocolState.DIRECT_ACCESS: [ProtocolEvent.EXECUTE_DIRECT,
                                          ProtocolEvent.STOP_DIRECT],
            ProtocolState.AUTOSAMPLE:    [ProtocolEvent.STOP_AUTOSAMPLE]
        }

        driver = InstrumentDriver(self._got_data_event_callback)
        self.assert_capabilities(driver, capabilities)


###############################################################################
#                            INTEGRATION TESTS                                #
#     Integration test test the direct driver / instrument interaction        #
#     but making direct calls via zeromq.                                     #
#     - Common Integration tests test the driver through the instrument agent #
#     and common for all drivers (minimum requirement for ION ingestion)      #
###############################################################################
@attr('INT', group='mi')
class DriverIntegrationTest(InstrumentDriverIntegrationTestCase, DriverTestMixinSub):
    def setUp(self):
        InstrumentDriverIntegrationTestCase.setUp(self)

    def test_out_of_range(self):
        """
        Verify when the instrument receives a set param with value out of range or invalid string,
        the instrument throws an exception
        """
        self.assert_initialize_driver()

        constraints = ParameterConstraints.dict()
        for param in constraints:
            param_name, type_class, minimum, maximum = constraints[param]

            log.debug("PARAM NAME %s", param_name)

            if type_class is int:
                self.assert_set_exception(param_name, minimum - 1, exception_class=InstrumentProtocolException)
                self.assert_set_exception(param_name, maximum + 1, exception_class=InstrumentProtocolException)
                self.assert_set_exception(param_name, 'badString', exception_class=InstrumentProtocolException)
            elif type_class is str:
                self.assert_set_exception(param_name, 'invalidvalue', exception_class=InstrumentProtocolException)
                self.assert_set_exception(param_name, 1, exception_class=InstrumentProtocolException)
            elif type_class is float:
                self.assert_set_exception(param_name, minimum - 0.1, exception_class=InstrumentProtocolException)
                self.assert_set_exception(param_name, maximum + 0.1, exception_class=InstrumentProtocolException)
                self.assert_set_exception(param_name, 'badString', exception_class=InstrumentProtocolException)

    def test_get_set(self):
        """
        Verify device parameter access.
        """
        self.assert_initialize_driver()

        #set read/write params
        self.assert_set(Parameter.OPERATION_MODE, InstrumentCommandArgs.CONTINUOUS)
        self.assert_set(Parameter.OPERATION_CONTROL, "Duration")
        self.assert_set(Parameter.LIGHT_SAMPLES, 57)
        self.assert_set(Parameter.DARK_SAMPLES, 3)
        self.assert_set(Parameter.LIGHT_DURATION, 11)
        self.assert_set(Parameter.DARK_DURATION, 6)
        self.assert_set(Parameter.COUNTDOWN, 16)
        self.assert_set(Parameter.TEMP_COMPENSATION, True)
        self.assert_set(Parameter.FIT_WAVELENGTH_BOTH, "218,241")
        self.assert_set(Parameter.CONCENTRATIONS_IN_FIT, 3)
        self.assert_set(Parameter.DARK_CORRECTION_METHOD, "SWAverage")
        self.assert_set(Parameter.SALINITY_FITTING, False)
        self.assert_set(Parameter.BROMIDE_TRACING, True)
        self.assert_set(Parameter.ABSORBANCE_CUTOFF, 1.4)
        self.assert_set(Parameter.INTEG_TIME_ADJUSTMENT, False)
        self.assert_set(Parameter.INTEG_TIME_FACTOR, 2)
        self.assert_set(Parameter.INTEG_TIME_STEP, 19)
        self.assert_set(Parameter.INTEG_TIME_MAX, 19)

        #set read-only parameters with bogus values, should throw exception
        self.assert_set_readonly(Parameter.POLLED_TIMEOUT, 9001)
        self.assert_set_readonly(Parameter.SKIP_SLEEP_AT_START, False)
        self.assert_set_readonly(Parameter.REF_MIN_AT_LAMP_ON, 9001)
        self.assert_set_readonly(Parameter.LAMP_STABIL_TIME, 6)
        self.assert_set_readonly(Parameter.LAMP_SWITCH_OFF_TEMPERATURE, 34)
        self.assert_set_readonly(Parameter.SPECTROMETER_INTEG_PERIOD, 9001)
        self.assert_set_readonly(Parameter.MESSAGE_LEVEL, "Warn")
        self.assert_set_readonly(Parameter.MESSAGE_FILE_SIZE, 5)
        self.assert_set_readonly(Parameter.DATA_FILE_SIZE, 10)
        self.assert_set_readonly(Parameter.OUTPUT_FRAME_TYPE, "Full_Binary")
        self.assert_set_readonly(Parameter.OUTPUT_DARK_FRAME, "Suppress")
        self.assert_set_readonly(Parameter.FIT_WAVELENGTH_LOW, 9002)
        self.assert_set_readonly(Parameter.FIT_WAVELENGTH_HIGH, 9003)
        self.assert_set_readonly(Parameter.BASELINE_ORDER, 2)

    def test_clock_sync(self):
        """
        Verify instrument can synchronize the clock
        """
        self.assert_initialize_driver()
        self.assert_driver_command(ProtocolEvent.CLOCK_SYNC)

    def test_acquire_sample(self):
        """
        Verify instrument can acquire a sample in command mode
        """
        self.assert_initialize_driver()
        self.clear_events()
        self.assert_particle_generation(ProtocolEvent.ACQUIRE_SAMPLE, DataParticleType.SUNA_SAMPLE,
                                        self.assert_data_particle_sample, delay=TIMEOUT)

    def test_acquire_status(self):
        """
        Verify instrument can acquire status (in command mode)
        """
        self.assert_initialize_driver()
        self.clear_events()
        self.assert_particle_generation(ProtocolEvent.ACQUIRE_STATUS, DataParticleType.SUNA_STATUS,
                                         self.assert_data_particle_status, delay=TIMEOUT)

    def test_selftest(self):
        """
        Verify instrument can perform a self test
        """
        self.assert_initialize_driver()
        self.clear_events()
        self.assert_particle_generation(ProtocolEvent.TEST, DataParticleType.SUNA_TEST,
                                        self.assert_data_particle, delay=TIMEOUT)

    def test_start_stop_polled(self):
        """
        Verify polled acquisition of samples in auto-sample mode
        """
        self.assert_initialize_driver()

        self.assert_particle_generation(ProtocolEvent.MEASURE_0, DataParticleType.SUNA_SAMPLE,
                                         self.assert_data_particle_sample, delay=TIMEOUT)

        self.assert_particle_generation(ProtocolEvent.MEASURE_N, DataParticleType.SUNA_SAMPLE,
                                        self.assert_data_particle_sample, delay=TIMEOUT)

        self.assert_particle_generation(ProtocolEvent.TIMED_N, DataParticleType.SUNA_SAMPLE,
                                        self.assert_data_particle_sample, delay=TIMEOUT)

    def test_start_stop_auto_sample(self):
        """
        Verify continuous acquisition of samples in auto-sample mode
        """
        self.assert_initialize_driver()

        self.assert_particle_generation(ProtocolEvent.START_AUTOSAMPLE, DataParticleType.SUNA_SAMPLE,
                                        self.assert_data_particle_sample, delay=5)

        #Stop autosample
        self.assert_driver_command(ProtocolEvent.STOP_AUTOSAMPLE, state=ProtocolState.COMMAND, delay=1)

        # transition back to auto to test countdown logic
        self.assert_particle_generation(ProtocolEvent.START_AUTOSAMPLE, DataParticleType.SUNA_SAMPLE,
                                        self.assert_data_particle_sample, delay=22)

        # Return to command mode.
        self.assert_driver_command(ProtocolEvent.STOP_AUTOSAMPLE, state=ProtocolState.COMMAND, delay=1)

    def test_errors(self):
        """
        Verify response to erroneous commands and setting bad parameters.
        """
        self.assert_initialize_driver(ProtocolState.COMMAND)

        #Assert an invalid command
        self.assert_driver_command_exception('ima_bad_command', exception_class=InstrumentCommandException)

        # Assert for a known command, invalid state.
        self.assert_driver_command_exception(ProtocolEvent.STOP_AUTOSAMPLE, exception_class=InstrumentCommandException)

        # Assert set fails with a bad parameter (not ALL or a list).
        self.assert_set_exception('I am a bogus param.', exception_class=InstrumentParameterException)

        #Assert set fails with bad parameter and bad value
        self.assert_set_exception('I am a bogus param.', value='bogus value', exception_class=InstrumentParameterException)

        # put driver in disconnected state.
        self.driver_client.cmd_dvr('disconnect')

        # Assert for a known command, invalid state.
        self.assert_driver_command_exception(ProtocolEvent.ACQUIRE_SAMPLE, exception_class=InstrumentCommandException)

        # Test that the driver is in state disconnected.
        self.assert_state_change(DriverConnectionState.DISCONNECTED, timeout=TIMEOUT)

        # Setup the protocol state machine and the connection to port agent.
        self.driver_client.cmd_dvr('initialize')

        # Test that the driver is in state unconfigured.
        self.assert_state_change(DriverConnectionState.UNCONFIGURED, timeout=TIMEOUT)

        # Assert we forgot the comms parameter.
        self.assert_driver_command_exception('configure', exception_class=InstrumentParameterException)


###############################################################################
#                            QUALIFICATION TESTS                              #
# Device specific qualification tests are for doing final testing of ion      #
# integration.  The generally aren't used for instrument debugging and should #
# be tackled after all unit and integration tests are complete                #
###############################################################################
@attr('QUAL', group='mi')
class DriverQualificationTest(InstrumentDriverQualificationTestCase, DriverTestMixinSub):
    def setUp(self):
        InstrumentDriverQualificationTestCase.setUp(self)

    def test_discover(self):
        """
        Override method- instrument will always start up in Command mode.  Instrument will instruct instrument into
        Command mode as well.

        Verify when the instrument is either in autosample or command state, the instrument will always discover
        to COMMAND state
        """

        self.assert_enter_command_mode()
        # Now reset and try to discover.  This will stop the driver which holds the current
        # instrument state.
        self.assert_reset()
        self.assert_discover(ResourceAgentState.COMMAND)

        # Now put the instrument in streaming and reset the driver again.
        self.assert_start_autosample()
        self.assert_reset()

        # When the driver reconnects it should be streaming
        self.assert_discover(ResourceAgentState.COMMAND)

    def test_direct_access_telnet_mode(self):
        """
        Verify while in Direct Access, we can manually set DA parameters.
        After stopping DA, the instrument will enter Command State and any
        parameters set during DA are reset to previous values.
        Also verifying timeouts with inactivity, with activity, and without activity.
        """
        self.assert_direct_access_start_telnet()
        self.assertTrue(self.tcp_client)

        ###
        # In DA mode, set the DA parameters to different values
        ###
        self.tcp_client.send_data("set opermode Continuous" + NEWLINE)
        self.tcp_client.expect("SUNA>")

        self.tcp_client.send_data("set polltout 60000" + NEWLINE)
        self.tcp_client.expect("SUNA>")

        self.tcp_client.send_data("set outfrtyp Full_Binary" + NEWLINE)
        self.tcp_client.expect("SUNA>")

        self.tcp_client.send_data("set spintper 600" + NEWLINE)
        self.tcp_client.expect("SUNA>")

        self.tcp_client.send_data("set salinfit Off" + NEWLINE)
        self.tcp_client.expect("SUNA>")

        self.tcp_client.send_data("set brmtrace On" + NEWLINE)
        self.tcp_client.expect("SUNA>")

        self.tcp_client.send_data("set intadstp 19" + NEWLINE)
        self.tcp_client.expect("SUNA>")

        self.assert_direct_access_stop_telnet()
        self.assert_state_change(ResourceAgentState.COMMAND, ProtocolState.COMMAND, TIMEOUT)

        #DA param should change back to pre-DA val
        self.assert_get_parameter(Parameter.OPERATION_MODE, InstrumentCommandArgs.POLLED)
        self.assert_get_parameter(Parameter.POLLED_TIMEOUT, 65535)
        self.assert_get_parameter(Parameter.SKIP_SLEEP_AT_START, True)
        self.assert_get_parameter(Parameter.COUNTDOWN, 15)
        self.assert_get_parameter(Parameter.LAMP_STABIL_TIME, 5)
        self.assert_get_parameter(Parameter.LAMP_SWITCH_OFF_TEMPERATURE, 35)
        self.assert_get_parameter(Parameter.MESSAGE_LEVEL, "Info")
        self.assert_get_parameter(Parameter.MESSAGE_FILE_SIZE, 0)
        self.assert_get_parameter(Parameter.DATA_FILE_SIZE, 5)
        self.assert_get_parameter(Parameter.OUTPUT_FRAME_TYPE, "Full_ASCII")
        self.assert_get_parameter(Parameter.OUTPUT_DARK_FRAME, "Output")
        self.assert_get_parameter(Parameter.TEMP_COMPENSATION, False)
        self.assert_get_parameter(Parameter.FIT_WAVELENGTH_BOTH, "217,240")
        self.assert_get_parameter(Parameter.CONCENTRATIONS_IN_FIT, 1)
        self.assert_get_parameter(Parameter.BASELINE_ORDER, 1)
        self.assert_get_parameter(Parameter.DARK_CORRECTION_METHOD, "SpecAverage")
        self.assert_get_parameter(Parameter.SALINITY_FITTING, True)
        self.assert_get_parameter(Parameter.BROMIDE_TRACING, False)
        self.assert_get_parameter(Parameter.ABSORBANCE_CUTOFF, 1.3)
        self.assert_get_parameter(Parameter.INTEG_TIME_ADJUSTMENT, True)
        self.assert_get_parameter(Parameter.INTEG_TIME_FACTOR, 1)
        self.assert_get_parameter(Parameter.INTEG_TIME_STEP, 20)
        self.assert_get_parameter(Parameter.INTEG_TIME_MAX, 20)

    def test_acquire_status(self):
        """
        Verify the driver can command an acquire status from the instrument
        """
        self.assert_enter_command_mode()
        self.assert_particle_polled(DriverEvent.ACQUIRE_STATUS, self.assert_data_particle_status,
                                    DataParticleType.SUNA_STATUS, timeout=TIMEOUT, sample_count=1)

    def test_execute_test(self):
        """
        Verify the instrument can perform a self test
        """
        self.assert_enter_command_mode()
        self.assert_particle_polled(DriverEvent.TEST, self.assert_data_particle, DataParticleType.SUNA_TEST,
                                    timeout=TIMEOUT, sample_count=1)

    def test_poll(self):
        """
        Verify the driver can collect a sample from the COMMAND state
        """
        self.assert_enter_command_mode()
        self.assert_particle_polled(DriverEvent.ACQUIRE_SAMPLE, self.assert_data_particle_sample,
                                    DataParticleType.SUNA_SAMPLE, timeout=TIMEOUT, sample_count=1)

    def test_autosample(self):
        """
        Verify the driver can start and stop autosample and verify data particle
        """
        self.assert_sample_autosample(self.assert_data_particle_sample, DataParticleType.SUNA_SAMPLE)

    def test_get_set_parameters(self):
        """
        Verify that all parameters can be get set properly, this includes
        ensuring that read only parameters fail on set.
        """
        self.assert_enter_command_mode()

        #read only params
        self.assert_get_parameter(Parameter.POLLED_TIMEOUT, 65535)
        self.assert_get_parameter(Parameter.SKIP_SLEEP_AT_START, True)
        self.assert_get_parameter(Parameter.LAMP_STABIL_TIME, 5)
        self.assert_get_parameter(Parameter.LAMP_SWITCH_OFF_TEMPERATURE, 35)
        self.assert_get_parameter(Parameter.MESSAGE_LEVEL, "Info")
        self.assert_get_parameter(Parameter.MESSAGE_FILE_SIZE, 0)
        self.assert_get_parameter(Parameter.DATA_FILE_SIZE, 5)
        self.assert_get_parameter(Parameter.OUTPUT_FRAME_TYPE, "Full_ASCII")
        self.assert_get_parameter(Parameter.OUTPUT_DARK_FRAME, "Output")
        self.assert_get_parameter(Parameter.BASELINE_ORDER, 1)

        #NOTE: THESE ARE READ_ONLY PARMS WITH NO DEFAULT VALUES, THE VALUES ARE DEPENDANT ON THE INSTRUMENT BEING TESTED
        #self.assert_get_parameter(Parameter.REF_MIN_AT_LAMP_ON, 9001)
        #self.assert_get_parameter(Parameter.SPECTROMETER_INTEG_PERIOD, 9001)
        #self.assert_get_parameter(Parameter.FIT_WAVELENGTH_LOW, 9002)
        #self.assert_get_parameter(Parameter.FIT_WAVELENGTH_HIGH, 9003)

        #read/write params
        self.assert_set_parameter(Parameter.OPERATION_MODE, InstrumentCommandArgs.CONTINUOUS)
        self.assert_set_parameter(Parameter.OPERATION_CONTROL, "Duration")
        self.assert_set_parameter(Parameter.LIGHT_SAMPLES, 57)
        self.assert_set_parameter(Parameter.DARK_SAMPLES, 3)
        self.assert_set_parameter(Parameter.LIGHT_DURATION, 11)
        self.assert_set_parameter(Parameter.DARK_DURATION, 6)
        self.assert_set_parameter(Parameter.DARK_SAMPLES, 3)
        self.assert_set_parameter(Parameter.DARK_SAMPLES, 3)
        self.assert_set_parameter(Parameter.COUNTDOWN, 16)
        self.assert_set_parameter(Parameter.TEMP_COMPENSATION, True)
        self.assert_set_parameter(Parameter.FIT_WAVELENGTH_BOTH, "218,241")
        self.assert_set_parameter(Parameter.CONCENTRATIONS_IN_FIT, 3)
        self.assert_set_parameter(Parameter.DARK_CORRECTION_METHOD, "SWAverage")
        self.assert_set_parameter(Parameter.SALINITY_FITTING, False)
        self.assert_set_parameter(Parameter.BROMIDE_TRACING, True)
        self.assert_set_parameter(Parameter.ABSORBANCE_CUTOFF, 1.4)
        self.assert_set_parameter(Parameter.INTEG_TIME_ADJUSTMENT, False)
        self.assert_set_parameter(Parameter.INTEG_TIME_FACTOR, 2)
        self.assert_set_parameter(Parameter.INTEG_TIME_STEP, 19)
        self.assert_set_parameter(Parameter.INTEG_TIME_MAX, 19)

    def test_get_capabilities(self):
        """
        Verify that the correct capabilities are returned from get_capabilities at various driver/agent states.
        """
        ##################
        #  Command Mode
        ##################
        capabilities = {
            AgentCapabilityType.AGENT_COMMAND: self._common_agent_commands(ResourceAgentState.COMMAND),
            AgentCapabilityType.AGENT_PARAMETER: self._common_agent_parameters(),
            AgentCapabilityType.RESOURCE_COMMAND: [ProtocolEvent.ACQUIRE_SAMPLE,
                                          ProtocolEvent.ACQUIRE_STATUS,
                                          ProtocolEvent.START_AUTOSAMPLE,
                                          ProtocolEvent.GET,
                                          ProtocolEvent.SET,
                                          ProtocolEvent.TEST,
                                          ProtocolEvent.CLOCK_SYNC,
                                          ProtocolEvent.MEASURE_N,
                                          ProtocolEvent.MEASURE_0,
                                          ProtocolEvent.TIMED_N],
            AgentCapabilityType.RESOURCE_INTERFACE: None,
            AgentCapabilityType.RESOURCE_PARAMETER: ['a_cutoff', 'bl_order', 'brmtrace', 'countdwn', 'datfsize',
                                                     'drkcormt', 'drkdurat', 'drksmpls', 'fitconcs', 'intadmax',
                                                     'intadstp', 'intpradj', 'intprfac', 'lamptoff', 'lgtdurat',
                                                     'lgtsmpls', 'msgfsize', 'msglevel', 'nmlgtspl', 'operctrl',
                                                     'opermode', 'outdrkfr', 'outfrtyp', 'polltout', 'reflimit',
                                                     'salinfit', 'skpsleep', 'spintper', 'stbltime', 'tempcomp',
                                                     'tlgtsmpl', 'wfit_hgh', 'wfit_low', 'wfitboth']}

        self.assert_enter_command_mode()
        self.assert_capabilities(capabilities)

        ##################
        #  Streaming Mode
        ##################
        capabilities[AgentCapabilityType.AGENT_COMMAND] = self._common_agent_commands(ResourceAgentState.STREAMING)
        capabilities[AgentCapabilityType.RESOURCE_COMMAND] = [ProtocolEvent.STOP_AUTOSAMPLE]

        self.assert_start_autosample()
        self.assert_capabilities(capabilities)
        self.assert_stop_autosample()

        ##################
        #  DA Mode
        ##################
        capabilities[AgentCapabilityType.AGENT_COMMAND] = self._common_agent_commands(ResourceAgentState.DIRECT_ACCESS)
        capabilities[AgentCapabilityType.RESOURCE_COMMAND] = []

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
