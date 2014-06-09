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

from mi.core.instrument.chunker import StringChunker
from mi.core.instrument.instrument_driver import DriverConnectionState, ResourceAgentState, DriverConfigKey
from mi.core.instrument.instrument_driver import DriverProtocolState

from mi.instrument.satlantic.suna_deep.ooicore.driver import InstrumentDriver, SUNAStatusDataParticle, TIMEOUT, \
    SUNATestDataParticle, InstrumentCommandArgs
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

from mi.core.exceptions import SampleException, InstrumentCommandException, InstrumentParameterException

from pyon.agent.agent import ResourceAgentEvent

###
#   Driver parameters for the tests
###
# noinspection PyPep8,PyPep8,PyPep8,PyPep8,PyPep8,PyPep8
InstrumentDriverTestCase.initialize(
    driver_module='mi.instrument.satlantic.suna_deep.ooicore.driver',
    driver_class="InstrumentDriver",

    instrument_agent_resource_id='1BQY0H',
    instrument_agent_name='satlantic_suna_deep_ooicore',
    instrument_agent_packet_config=DataParticleType(),

    driver_startup_config={DriverConfigKey.PARAMETERS: {
            Parameter.OPERATION_MODE: InstrumentCommandArgs.POLLED,
            Parameter.OPERATION_CONTROL: "Operation Control",
            Parameter.LIGHT_SAMPLES: 5,
            Parameter.DARK_SAMPLES: 1,
            Parameter.LIGHT_DURATION: 10,
            Parameter.DARK_DURATION: 5}}
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

spectrum_channels_str = ""
for i in range(256):
    spectrum_channels_str += (str(i % 10) + ",")

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
                    "INTADSTP 20\r\nINTADMAX 20\r\nWFIT_LOW 217.00\r\nWFIT_HGH 240.00\r\nLAMPTIME 172577\r"

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
        "frame_type": {'type': unicode, 'value': "SDF"},
        "serial_number": {'type': unicode, 'value': "0344"},
        "date_of_sample": {'type': int, 'value': 2014125},
        "time_of_sample": {'type': float, 'value': 21.278082},
        "nitrate_concentration": {'type': float, 'value': 0.00},
        "nutnr_nitrogen_in_nitrate": {'type': float, 'value': 0.0000},
        "nutnr_absorbance_at_254_nm": {'type': float, 'value': 0.0000},
        "nutnr_absorbance_at_350_nm": {'type': float, 'value': 0.0000},
        "nutnr_bromide_trace": {'type': float, 'value': 0.00},
        "nutnr_spectrum_average": {'type': int, 'value': 476},
        "nutnr_dark_value_used_for_fit": {'type': int, 'value': 0},
        "nutnr_integration_time_factor": {'type': int, 'value': 1},
        "spectral_channels": {'type': list, 'value': [475,483,494,465,487,490,488,
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
        "temp_interior": {'type': float, 'value': 0.0},
        "temp_spectrometer": {'type': float, 'value': 0.0},
        "temp_lamp": {'type': float, 'value': -99.0},
        "lamp_time": {'type': int, 'value': 172578},
        "humidity": {'type': float, 'value': 6.2},
        "voltage_main": {'type': float, 'value': 12.0},
        "voltage_lamp": {'type': float, 'value': 0.1},
        "nutnr_voltage_int": {'type': float, 'value': 5.0},
        "nutnr_current_main": {'type': float, 'value': 54.0},
        "aux_fitting_1": {'type': float, 'value': 0.00},
        "aux_fitting_2": {'type': float, 'value': 0.00},
        "nutnr_fit_base_1": {'type': float, 'value': 0.0000},
        "nutnr_fit_base_2": {'type': float, 'value': 0.000000},
        "nutnr_fit_rmse": {'type': float, 'value': 0.0000000},
        "checksum": {'type': int, 'value': 203}
    }

    _reference_status_parameters = {
        "nutnr_sensor_type" : {'type': unicode, 'value': "SUNA"},
        "nutnr_sensor_version" : {'type': unicode, 'value': "V2"},
        "serial_number" : {'type': int, 'value': 344} ,
        "nutnr_integrated_wiper" : {'type': unicode, 'value': "Available"},
        "nutnr_ext_power_port" : {'type': unicode, 'value': "Missing"},
        "nutnr_lamp_shutter" : {'type': unicode, 'value': "Missing"},
        "nutnr_reference_detector" : {'type': unicode, 'value': "Missing"},
        "protectr" : {'type': unicode, 'value': "Available"},
        "nutnr_super_capacitors" : {'type': unicode, 'value': "Available"},
        "nutnr_psb_supervisor" : {'type': unicode, 'value': "Available"},
        "nutnr_usb_communication" : {'type': unicode, 'value': "Available"},
        "nutnr_relay_module" : {'type': unicode, 'value': "Available"},
        "nutnr_sdi12_interface" : {'type': unicode, 'value': "Available"},
        "nutnr_analog_output" : {'type': unicode, 'value': "Available"},
        "nutnr_int_data_logging" : {'type': unicode, 'value': "Available"},
        "nutnr_apf_interface" : {'type': unicode, 'value': "Available"},
        "nutnr_scheduling" : {'type': unicode, 'value': "Available"},
        "nutnr_lamp_fan" : {'type': unicode, 'value': "Available"},
        "nutnr_sensor_address_lamp_temp" : {'type': unicode, 'value': '10d0fda4020800eb'},
        "nutnr_sensor_address_spec_temp" : {'type': unicode, 'value': '1086818d020800d8'},
        "nutnr_sensor_address_hous_temp" : {'type': unicode, 'value': '10707b6a020800cc'},
        "nutnr_serial_number_spec" : {'type': int, 'value': 86746},
        "nutnr_serial_number_lamp" : {'type': unicode, 'value': "C3.D01.1590"},
        "stupstus" : {'type': unicode, 'value': "Done"},
        "brnhours" : {'type': int, 'value': 0},
        "brnnumbr" : {'type': int, 'value': 0},
        "drkhours" : {'type': int, 'value': 0},
        "drknumbr" : {'type': int, 'value': 0},
        "chrldura" : {'type': int, 'value': 600},
        "chrddura" : {'type': int, 'value': 0},
        "baud_rate" : {'type': int, 'value': 57600},
        "nutnr_msg_level" : {'type': unicode, 'value': "Info"},
        "nutnr_msg_file_size" : {'type': int, 'value': 2},
        "nutnr_data_file_size" : {'type': int, 'value': 5},
        "nutnr_output_frame_type" : {'type': unicode, 'value': "Full_ASCII"},
        "nutnr_logging_frame_type" : {'type': unicode, 'value': "Full_ASCII"},
        "nutnr_output_dark_frame" : {'type': unicode, 'value': "Output"},
        "nutnr_logging_dark_frame" : {'type': unicode, 'value': "Output"},
        "timeresl" : {'type': unicode, 'value': "Fractsec"},
        "nutnr_log_file_type" : {'type': unicode, 'value': "Acquisition"},
        "acqcount" : {'type': int, 'value': 10},
        "cntcount" : {'type': int, 'value': 130},
        "nutnr_dac_nitrate_min" : {'type': float, 'value': -5.000},
        "nutnr_dac_nitrate_max" : {'type': float, 'value': 100.000},
        "nutnr_data_wavelength_low" : {'type': float, 'value': 217.00},
        "nutnr_data_wavelength_high" : {'type': float, 'value': 250.00},
        "nutnr_sdi12_address" : {'type': int, 'value': 48},
        "datamode" : {'type': unicode, 'value': "Real"},
        "operating_mode" : {'type': unicode, 'value': "Polled"},
        "nutnr_operation_ctrl" : {'type': unicode, 'value': "Duration"},
        "nutnr_extl_dev" : {'type': unicode, 'value': "None"},
        "nutnr_ext_dev_prerun_time" : {'type': int, 'value': 0},
        "nutnr_ext_dev_during_acq" : {'type': unicode, 'value': "Off"},
        "nutnr_watchdog_timer" : {'type': unicode, 'value': "On"},
        "nutnr_countdown" : {'type': int, 'value': 15},
        "nutnr_fixed_time_duration" : {'type': int, 'value': 60},
        "nutnr_periodic_interval" : {'type': unicode, 'value': "1m"},
        "nutnr_periodic_offset" : {'type': int, 'value': 0},
        "nutnr_periodic_duration" : {'type': int, 'value': 5},
        "nutnr_periodic_samples" : {'type': int, 'value': 5},
        "nutnr_polled_timeout" : {'type': int, 'value': 15},
        "nutnr_apf_timeout" : {'type': float, 'value': 10.0000},
        "nutnr_stability_time" : {'type': int, 'value': 5},
        "nutnr_ref_min_lamp_on" : {'type': int, 'value': 0},
        "nutnr_skip_sleep" : {'type': unicode, 'value': "Off"},
        "nutnr_lamp_switchoff_temp" : {'type': int, 'value': 35},
        "nutnr_spec_integration_period" : {'type': int, 'value': 450},
        "drkavers" : {'type': int, 'value': 1},
        "lgtavers" : {'type': int, 'value': 1},
        "refsmpls" : {'type': int, 'value': 20},
        "nutnr_dark_samples" : {'type': int, 'value': 2},
        "nutnr_light_samples" : {'type': int, 'value': 58},
        "nutnr_dark_duration" : {'type': int, 'value': 2},
        "nutnr_light_duration" : {'type': int, 'value': 58},
        "nutnr_temp_comp" : {'type': unicode, 'value': "Off"},
        "nutnr_salinity_fit" : {'type': unicode, 'value': "On"},
        "nutnr_bromide_tracing" : {'type': unicode, 'value': "Off"},
        "nutnr_baseline_order" : {'type': int, 'value': 1},
        "nutnr_concentrations_fit" : {'type': int, 'value': 3},
        "nutnr_dark_corr_method" : {'type': unicode, 'value': "SpecAverage"},
        "drkcoefs" : {'type': unicode, 'value': "Missing"},
        "davgprm0" : {'type': float, 'value': 500.000},
        "davgprm1" : {'type': float, 'value': 0.00000},
        "davgprm2" : {'type': float, 'value': 0.00000},
        "davgprm3" : {'type': float, 'value': 0.000000},
        "nutnr_absorbance_cutoff" : {'type': float, 'value': 1.3000},
        "nutnr_int_time_adj" : {'type': unicode, 'value': "On"},
        "nutnr_int_time_factor" : {'type': int, 'value': 1},
        "nutnr_int_time_step" : {'type': int, 'value': 20},
        "nutnr_int_time_max" : {'type': int, 'value': 20},
        "nutnr_fit_wavelength_low" : {'type': float, 'value': 217.00},
        "nutnr_fit_wavelength_high" : {'type': float, 'value': 240.00},
        "lamp_time" : {'type': int, 'value': 172577}
    }

    _reference_test_parameters = {
        "nutnr_external_disk_size" : {'type': int, 'value': 1960968192},
        "nutnr_external_disk_free" : {'type': int, 'value': 1956216832},
        "nutnr_internal_disk_size" : {'type': int, 'value': 2043904},
        "nutnr_internal_disk_free" : {'type': int, 'value': 1956864},
        "nutnr_fiberlite_odometer" : {'type': unicode, 'value': "0048:10:05"},
        "nutnr_temperatures_hs" : {'type': float, 'value': 22.3},
        "nutnr_temperatures_sp" : {'type': float, 'value': 21.7},
        "nutnr_temperatures_lm" : {'type': float, 'value': 21.6},
        "nutnr_humidity" : {'type': float, 'value': 5.8},
        "nutnr_electrical_mn" : {'type': float, 'value': 12.0},
        "nutnr_electrical_bd" : {'type': float, 'value': 12.0},
        "nutnr_electrical_pr" : {'type': float, 'value': 5.0},
        "nutnr_electrical_c" : {'type': float, 'value': 25.8},
        "nutnr_lamp_power" : {'type': int, 'value': 5505},
        "nutnr_spec_dark_av" : {'type': int, 'value': 471},
        "nutnr_spec_dark_sd" : {'type': int, 'value': 9},
        "nutnr_spec_dark_mi" : {'type': int, 'value': 444},
        "nutnr_spec_dark_ma" : {'type': int, 'value': 494},
        "nutnr_spec_lght_av" : {'type': int, 'value': 22308},
        "nutnr_spec_lght_sd" : {'type': int, 'value': 12009},
        "nutnr_spec_lght_mi" : {'type': int, 'value': 455},
        "nutnr_spec_lght_ma" : {'type': int, 'value': 52004},
        "nutnr_test_result" : {'type': unicode, 'value': "Ok"}
    }

    def assert_data_particle_sample(self, data_particle, verify_values=False):
        """
        Verify that all driver parameters are correct and potentially verify values.
        @param data_particle: driver parameters read from the driver instance
        @param verify_values: should we verify values against definition?
        """
        self.assert_data_particle_parameters(data_particle, self._reference_sample_parameters, verify_values)

    def assert_data_particle_status(self, data_particle, verify_values=False):
        """
        Verify a SUNA status data particle
        @param data_particle: a SUNA status data particle
        @param verify_values: bool, should we verify values against definition?
        """
        self.assert_data_particle_parameters(data_particle, self._reference_status_parameters, verify_values)

    def assert_data_particle(self, data_particle, verify_values=False):
        """
        Verify a SUNA test data particle
        @param data_particle: a SUNA test data particle
        @param verify_values: bool, should we verify values against definition?
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
                                          ProtocolEvent.START_POLL,
                                          ProtocolEvent.START_AUTOSAMPLE,
                                          ProtocolEvent.GET,
                                          ProtocolEvent.SET,
                                          ProtocolEvent.TEST,
                                          ProtocolEvent.CLOCK_SYNC],
            ProtocolState.DIRECT_ACCESS: [ProtocolEvent.EXECUTE_DIRECT,
                                          ProtocolEvent.STOP_DIRECT],
            ProtocolState.POLL:          [ProtocolEvent.ACQUIRE_SAMPLE,
                                          ProtocolEvent.MEASURE_N,
                                          ProtocolEvent.MEASURE_0,
                                          ProtocolEvent.TIMED_N,
                                          ProtocolEvent.STOP_POLL],
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

    def test_get_set(self):
        """
        Verify device parameter access.
        """
        self.assert_initialize_driver()

        #todo - do all params, need to do boundary checking?
        #set read/write params
        self.assert_set(Parameter.OPERATION_MODE, InstrumentCommandArgs.CONTINUOUS)
        self.assert_set(Parameter.OPERATION_CONTROL, "Duration")
        self.assert_set(Parameter.LIGHT_SAMPLES, 57)
        self.assert_set(Parameter.DARK_SAMPLES, 3)
        self.assert_set(Parameter.LIGHT_DURATION, 11)
        self.assert_set(Parameter.DARK_DURATION, 6)
        self.assert_set(Parameter.DARK_SAMPLES, 3)
        self.assert_set(Parameter.DARK_SAMPLES, 3)
        self.assert_set(Parameter.COUNTDOWN, 16)
        self.assert_set(Parameter.TEMP_COMPENSATION, InstrumentCommandArgs.ON)
        self.assert_set(Parameter.FIT_WAVELENGTH_BOTH, "218,241")
        self.assert_set(Parameter.CONCENTRATIONS_IN_FIT, 3)
        self.assert_set(Parameter.BASELINE_ORDER, 1)
        self.assert_set(Parameter.DARK_CORRECTION_METHOD, "SWAverage")
        self.assert_set(Parameter.SALINITY_FITTING, InstrumentCommandArgs.OFF)
        self.assert_set(Parameter.BROMIDE_TRACING, InstrumentCommandArgs.ON)
        self.assert_set(Parameter.ABSORBANCE_CUTOFF, 1.4)
        self.assert_set(Parameter.INTEG_TIME_ADJUSTMENT, InstrumentCommandArgs.OFF)
        self.assert_set(Parameter.INTEG_TIME_FACTOR, 2)
        self.assert_set(Parameter.INTEG_TIME_STEP, 19)
        self.assert_set(Parameter.INTEG_TIME_MAX, 19)

        #set read-only parameters with bogus values, should throw exception
        self.assert_set_readonly(Parameter.POLLED_TIMEOUT, 9001)
        self.assert_set_readonly(Parameter.SKIP_SLEEP_AT_START, InstrumentCommandArgs.OFF)
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

    def test_clock_sync(self):
        """
        Verify instrument can synchronize the clock
        """
        self.assert_initialize_driver()
        self.assert_driver_command(ProtocolEvent.CLOCK_SYNC)

    def test_single_sample(self):
        """
        Verify instrument can acquire a sample in polled mode
        """
        self.assert_initialize_driver()
        self.clear_events()
        self.assert_particle_generation(ProtocolEvent.ACQUIRE_SAMPLE, DataParticleType.SUNA_SAMPLE,
                                        self.assert_data_particle_sample, delay=20)

    def test_status(self):
        """
        Verify instrument can acquire status (in command mode)
        """

        self.assert_initialize_driver()
        self.clear_events()
        self.assert_particle_generation(ProtocolEvent.ACQUIRE_STATUS, DataParticleType.SUNA_STATUS,
                                        self.assert_data_particle_status, delay=30)

    def test_test(self):
        """
        Verify instrument can perform a self test
        """
        self.assert_initialize_driver()
        self.clear_events()
        self.assert_particle_generation(ProtocolEvent.TEST, DataParticleType.SUNA_TEST,
                                        self.assert_data_particle, delay=15)

    def test_polled_sample(self):
        """
        Verify polled acquisition of samples in auto-sample mode
        """
        self.assert_initialize_driver()

        self.assert_driver_command(ProtocolEvent.START_POLL, state=ProtocolState.COMMAND, delay=1)

        # noinspection PyPep8
        self.assert_particle_generation(ProtocolEvent.MEASURE_0, DataParticleType.SUNA_SAMPLE,
                                         self.assert_data_particle_sample, delay=20)

        self.assert_particle_generation(ProtocolEvent.MEASURE_N, DataParticleType.SUNA_SAMPLE,
                                        self.assert_data_particle_sample, delay=20)

        self.assert_particle_generation(ProtocolEvent.TIMED_N, DataParticleType.SUNA_SAMPLE,
                                        self.assert_data_particle_sample, delay=20)

        # Return to command mode.
        self.assert_driver_command(ProtocolEvent.STOP_POLL, state=ProtocolState.COMMAND, delay=1)

    def test_auto_sample(self):
        """
        Verify continuous acquisition of samples in auto-sample mode
        """
        self.assert_initialize_driver()

        self.assert_particle_generation(ProtocolEvent.START_AUTOSAMPLE, DataParticleType.SUNA_SAMPLE,
                                        self.assert_data_particle_sample, delay=5)

        # Return to command mode. Catch timeouts and retry if necessary.
        self.assert_driver_command(ProtocolEvent.STOP_AUTOSAMPLE, state=ProtocolState.COMMAND, delay=1)

        # Test the driver is in command mode.
        state = self.driver_client.cmd_dvr('get_resource_state')
        self.assertEqual(state, ProtocolState.COMMAND)

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
        Override - instrument will always start up in Command mode.  Instrument will instruct instrument into
        Command mode as well.

        Verify when the instrument is either in autosample or command state, the instrument will always discover
        to COMMAND state
        """
        # Verify the agent is in command mode
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
        #   Add instrument specific code here.
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

        self.assert_enter_command_mode()

        #DA param should change back to pre-DA val
        self.assert_get_parameter(Parameter.OPERATION_MODE, InstrumentCommandArgs.POLLED)
        self.assert_get_parameter(Parameter.POLLED_TIMEOUT, 65535)
        self.assert_get_parameter(Parameter.SKIP_SLEEP_AT_START, InstrumentCommandArgs.ON)
        self.assert_get_parameter(Parameter.COUNTDOWN, 15)
        self.assert_get_parameter(Parameter.LAMP_STABIL_TIME, 5)
        self.assert_get_parameter(Parameter.LAMP_SWITCH_OFF_TEMPERATURE, 35)
        self.assert_get_parameter(Parameter.MESSAGE_LEVEL, "Info")
        self.assert_get_parameter(Parameter.MESSAGE_FILE_SIZE, 0)
        self.assert_get_parameter(Parameter.DATA_FILE_SIZE, 5)
        self.assert_get_parameter(Parameter.OUTPUT_FRAME_TYPE, "Full_ASCII")
        self.assert_get_parameter(Parameter.OUTPUT_DARK_FRAME, "Output")
        self.assert_get_parameter(Parameter.TEMP_COMPENSATION, InstrumentCommandArgs.OFF)
        self.assert_get_parameter(Parameter.FIT_WAVELENGTH_BOTH, "217,240")
        self.assert_get_parameter(Parameter.CONCENTRATIONS_IN_FIT, 1)
        self.assert_get_parameter(Parameter.BASELINE_ORDER, 1)
        self.assert_get_parameter(Parameter.DARK_CORRECTION_METHOD, "SpecAverage")
        self.assert_get_parameter(Parameter.SALINITY_FITTING, InstrumentCommandArgs.ON)
        self.assert_get_parameter(Parameter.BROMIDE_TRACING, InstrumentCommandArgs.OFF)
        self.assert_get_parameter(Parameter.ABSORBANCE_CUTOFF, 1.3)
        self.assert_get_parameter(Parameter.INTEG_TIME_ADJUSTMENT, InstrumentCommandArgs.ON)
        self.assert_get_parameter(Parameter.INTEG_TIME_FACTOR, 1)
        self.assert_get_parameter(Parameter.INTEG_TIME_STEP, 20)
        self.assert_get_parameter(Parameter.INTEG_TIME_MAX, 20)

    def test_acquire_status(self):
        """
        Verify the driver can command an acquire status from the instrument
        """
        self.assert_enter_command_mode()
        self.assert_resource_command(Capability.ACQUIRE_STATUS, self.assert_data_particle_status)

    def test_execute_test(self):
        """
        Verify the instrument can perform a self test
        """
        self.assert_enter_command_mode()
        self.assert_resource_command(Capability.TEST, self.assert_data_particle)

    def test_poll(self):
        """
        Verify the driver can collect a sample from the COMMAND state
        """
        self.assert_sample_polled(self.assert_data_particle_sample, DataParticleType.SUNA_SAMPLE)

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
        self.assert_get_parameter(Parameter.SKIP_SLEEP_AT_START, InstrumentCommandArgs.ON)
        self.assert_get_parameter(Parameter.LAMP_STABIL_TIME, 5)
        self.assert_get_parameter(Parameter.LAMP_SWITCH_OFF_TEMPERATURE, 35)
        self.assert_get_parameter(Parameter.MESSAGE_LEVEL, "Info")
        self.assert_get_parameter(Parameter.MESSAGE_FILE_SIZE, 0)
        self.assert_get_parameter(Parameter.DATA_FILE_SIZE, 5)
        self.assert_get_parameter(Parameter.OUTPUT_FRAME_TYPE, "Full_ASCII")
        self.assert_get_parameter(Parameter.OUTPUT_DARK_FRAME, "Output")

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
        self.assert_set_parameter(Parameter.TEMP_COMPENSATION, InstrumentCommandArgs.ON)
        self.assert_set_parameter(Parameter.FIT_WAVELENGTH_BOTH, "218,241")
        self.assert_set_parameter(Parameter.CONCENTRATIONS_IN_FIT, 3)
        self.assert_set_parameter(Parameter.BASELINE_ORDER, 1)
        self.assert_set_parameter(Parameter.DARK_CORRECTION_METHOD, "SWAverage")
        self.assert_set_parameter(Parameter.SALINITY_FITTING, InstrumentCommandArgs.OFF)
        self.assert_set_parameter(Parameter.BROMIDE_TRACING, InstrumentCommandArgs.ON)
        self.assert_set_parameter(Parameter.ABSORBANCE_CUTOFF, 1.4)
        self.assert_set_parameter(Parameter.INTEG_TIME_ADJUSTMENT, InstrumentCommandArgs.OFF)
        self.assert_set_parameter(Parameter.INTEG_TIME_FACTOR, 2)
        self.assert_set_parameter(Parameter.INTEG_TIME_STEP, 19)
        self.assert_set_parameter(Parameter.INTEG_TIME_MAX, 19)

    def test_get_capabilities(self):
        """
        Verify that the correct capabilities are returned from get_capabilities at various driver/agent states.
        """
        self.assert_enter_command_mode()

        ##################
        #  Command Mode
        ##################
        capabilities = {
            AgentCapabilityType.AGENT_COMMAND: self._common_agent_commands(ResourceAgentState.COMMAND),
            AgentCapabilityType.AGENT_PARAMETER: self._common_agent_parameters(),
            AgentCapabilityType.RESOURCE_COMMAND: [
                ProtocolEvent.SET,
                ProtocolEvent.ACQUIRE_SAMPLE,
                ProtocolEvent.GET,
                ProtocolEvent.ACQUIRE_STATUS,
                ProtocolEvent.START_POLL,
                ProtocolEvent.START_AUTOSAMPLE,
                ProtocolEvent.TEST
            ],
            AgentCapabilityType.RESOURCE_INTERFACE: None,
            AgentCapabilityType.RESOURCE_PARAMETER: self._driver_parameters.keys()
        }

        self.assert_capabilities(capabilities)

        ##################
        #  Polled Mode
        ##################
        capabilities[AgentCapabilityType.AGENT_COMMAND] = [
            ResourceAgentEvent.CLEAR,
            ResourceAgentEvent.RESET,
            ResourceAgentEvent.GO_DIRECT_ACCESS,
            ResourceAgentEvent.GO_INACTIVE,
            ResourceAgentEvent.PAUSE,
        ]
        capabilities[AgentCapabilityType.RESOURCE_COMMAND] = [
            ProtocolEvent.ACQUIRE_SAMPLE,
            ProtocolEvent.STOP_POLL,
            ProtocolEvent.MEASURE_N,
            ProtocolEvent.MEASURE_0,
            ProtocolEvent.TIMED_N
        ]

        self.assert_switch_driver_state(ProtocolEvent.START_POLL, DriverProtocolState.POLL)
        self.assert_capabilities(capabilities)
        self.assert_switch_driver_state(ProtocolEvent.STOP_POLL, DriverProtocolState.COMMAND)

        ##################
        #  Streaming Mode
        ##################
        capabilities[AgentCapabilityType.AGENT_COMMAND] = self._common_agent_commands(ResourceAgentState.STREAMING)
        capabilities[AgentCapabilityType.RESOURCE_COMMAND] = [ProtocolEvent.STOP_AUTOSAMPLE]

        self.assert_start_autosample()
        self.assert_capabilities(capabilities)
        self.assert_stop_autosample()

        # ##################
        # #  DA Mode
        # ##################
        capabilities[AgentCapabilityType.AGENT_COMMAND] = self._common_agent_commands(ResourceAgentState.DIRECT_ACCESS)
        capabilities[AgentCapabilityType.RESOURCE_COMMAND] = [ProtocolEvent.STOP_DIRECT]

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
