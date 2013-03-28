#!/usr/bin/env python

"""
@package mi.instrument.rbr.xr_420_thermistor_24.test.test_driver
@file /Users/Bill/WorkSpace/marine-integrations/mi/instrument/rbr/xr_420_thermistor_24/driver.py
@author Bill Bollenbacher
@brief Test cases for xr_420 thermistor driver
 
USAGE:
 Make tests verbose and provide stdout
   * From the IDK
       $ bin/test_driver
       $ bin/test_driver -u
       $ bin/test_driver -i
       $ bin/test_driver -q

   * From pyon
       $ bin/nosetests -s -v /Users/Bill/WorkSpace/marine-integrations/mi/instrument/rbr/xr_420_thermistor_24
       $ bin/nosetests -s -v /Users/Bill/WorkSpace/marine-integrations/mi/instrument/rbr/xr_420_thermistor_24 -a UNIT
       $ bin/nosetests -s -v /Users/Bill/WorkSpace/marine-integrations/mi/instrument/rbr/xr_420_thermistor_24 -a INT
       $ bin/nosetests -s -v /Users/Bill/WorkSpace/marine-integrations/mi/instrument/rbr/xr_420_thermistor_24 -a QUAL
"""

__author__ = 'Bill Bollenbacher'
__license__ = 'Apache 2.0'

# Ensure the test class is monkey patched for gevent
from gevent import monkey; monkey.patch_all()
import gevent
from mock import Mock

# Standard lib imports
import time
import ntplib
import json

# 3rd party import
from nose.plugins.attrib import attr

# MI logger
from mi.core.log import get_logger ; log = get_logger()
from pyon.agent.agent import ResourceAgentEvent

from mi.core.instrument.instrument_driver import DriverAsyncEvent
from mi.core.instrument.instrument_driver import DriverConnectionState
from mi.core.instrument.instrument_driver import DriverParameter
from mi.core.instrument.instrument_driver import DriverProtocolState
from mi.core.instrument.instrument_driver import DriverEvent

from mi.core.instrument.data_particle import DataParticleKey
from mi.core.instrument.data_particle import DataParticleValue

from mi.core.exceptions import InstrumentCommandException
from mi.core.exceptions import SampleException

from mi.instrument.rbr.xr_420_thermistor_24.ooicore.driver import InstrumentDriver
from mi.instrument.rbr.xr_420_thermistor_24.ooicore.driver import DataParticleType
from mi.instrument.rbr.xr_420_thermistor_24.ooicore.driver import ProtocolStates
from mi.instrument.rbr.xr_420_thermistor_24.ooicore.driver import ProtocolEvent
from mi.instrument.rbr.xr_420_thermistor_24.ooicore.driver import InstrumentProtocol
from mi.instrument.rbr.xr_420_thermistor_24.ooicore.driver import InstrumentParameters
from mi.instrument.rbr.xr_420_thermistor_24.ooicore.driver import InstrumentCmds
from mi.instrument.rbr.xr_420_thermistor_24.ooicore.driver import Capability
from mi.instrument.rbr.xr_420_thermistor_24.ooicore.driver import ScheduledJob
from mi.instrument.rbr.xr_420_thermistor_24.ooicore.driver import InstrumentResponses
from mi.instrument.rbr.xr_420_thermistor_24.ooicore.driver import AdvancedFunctionsParameters
from mi.instrument.rbr.xr_420_thermistor_24.ooicore.driver import AdvancedFuntionsBits
from mi.instrument.rbr.xr_420_thermistor_24.ooicore.driver import XR_420EngineeringDataParticleKey
from mi.instrument.rbr.xr_420_thermistor_24.ooicore.driver import XR_420SampleDataParticleKey
from mi.instrument.rbr.xr_420_thermistor_24.ooicore.driver import XR_420SampleDataParticle
from mi.instrument.rbr.xr_420_thermistor_24.ooicore.driver import INSTRUMENT_NEWLINE

from mi.idk.unit_test import InstrumentDriverTestCase
from mi.idk.unit_test import InstrumentDriverUnitTestCase
from mi.idk.unit_test import InstrumentDriverIntegrationTestCase
from mi.idk.unit_test import InstrumentDriverQualificationTestCase
from mi.idk.unit_test import InstrumentDriverPublicationTestCase
from mi.idk.unit_test import DriverTestMixin
from mi.idk.unit_test import ParameterTestConfigKey
from mi.idk.unit_test import DriverStartupConfigKey
from mi.idk.unit_test import AgentCapabilityType

from mi.core.instrument.chunker import StringChunker

## Initialize the test configuration
InstrumentDriverTestCase.initialize(
    driver_module='mi.instrument.rbr.xr_420_thermistor_24.ooicore.driver',
    driver_class="InstrumentDriver",

    instrument_agent_resource_id = 'rbr_xr_420_ooicore',
    instrument_agent_name = 'rbr_xr_420_ooicore_agent',
    instrument_agent_packet_config = DataParticleType(),
    
    driver_startup_config = {
        DriverStartupConfigKey.PARAMETERS: {
            #InstrumentParameters.SYS_CLOCK: '3',
        },
    }
)

class UtilMixin(DriverTestMixin):
    '''
    Mixin class used for storing data particle constants and common data assertion methods.
    '''
    
    # Create some short names for the parameter test config
    TYPE = ParameterTestConfigKey.TYPE
    READONLY = ParameterTestConfigKey.READONLY
    STARTUP = ParameterTestConfigKey.STARTUP
    DA = ParameterTestConfigKey.DIRECT_ACCESS
    VALUE = ParameterTestConfigKey.VALUE
    REQUIRED = ParameterTestConfigKey.REQUIRED
    DEFAULT = ParameterTestConfigKey.DEFAULT
    
    CLOCK_SYNC_TIME = '21 Feb 2002 11:18:42'
    TIME_IN_PAST    = '01 Jan 2000 12:23:00'
    TIME_IN_FUTURE  = '27 Dec 2023 01:10:59'

    ###
    #  Parameter and Type Definitions
    ###
    _driver_parameters = {
        InstrumentParameters.IDENTIFICATION : {TYPE: str, READONLY: True, DA: False, STARTUP: False},                          
        InstrumentParameters.LOGGER_DATE_AND_TIME : {TYPE: str, READONLY: False, DA: False},
        InstrumentParameters.SAMPLE_INTERVAL : {TYPE: str, READONLY: False, DA: False, STARTUP: True, DEFAULT: '00:00:12'},
        InstrumentParameters.START_DATE_AND_TIME : {TYPE: str, READONLY: False, DA: False, STARTUP: True, DEFAULT: '01 Jan 2000 00:00:00'},
        InstrumentParameters.END_DATE_AND_TIME : {TYPE: str, READONLY: False, DA: False, STARTUP: True, DEFAULT: '01 Jan 2050 00:00:00'},
        InstrumentParameters.STATUS : {TYPE: str, READONLY: True, DA: False, STARTUP: False},
        InstrumentParameters.BATTERY_VOLTAGE : {TYPE: float, READONLY: True, DA: False, STARTUP: False},
        InstrumentParameters.POWER_ALWAYS_ON : {TYPE: int, READONLY: False, DA: False, STARTUP: True, DEFAULT: 1},
        InstrumentParameters.SIX_HZ_PROFILING_MODE : {TYPE: int, READONLY: False, DA: False, STARTUP: True, DEFAULT: 0},
        InstrumentParameters.OUTPUT_INCLUDES_SERIAL_NUMBER : {TYPE: int, READONLY: False, DA: False, STARTUP: True, DEFAULT: 1},
        InstrumentParameters.OUTPUT_INCLUDES_BATTERY_VOLTAGE : {TYPE: int, READONLY: False, DA: False, STARTUP: True, DEFAULT: 1},
        InstrumentParameters.SAMPLING_LED : {TYPE: int, READONLY: False, DA: False, STARTUP: True, DEFAULT: 0},
        InstrumentParameters.ENGINEERING_UNITS_OUTPUT : {TYPE: int, READONLY: False, DA: False, STARTUP: True, DEFAULT: 1},
        InstrumentParameters.AUTO_RUN : {TYPE: int, READONLY: False, DA: False, STARTUP: True, DEFAULT: 1},
        InstrumentParameters.INHIBIT_DATA_STORAGE : {TYPE: int, READONLY: False, DA: False, STARTUP: True, DEFAULT: 1},
        InstrumentParameters.CALIBRATION_COEFFICIENTS_CHANNEL_1 : {TYPE: list, READONLY: True, DA: False, STARTUP: False},
        InstrumentParameters.CALIBRATION_COEFFICIENTS_CHANNEL_2 : {TYPE: list, READONLY: True, DA: False, STARTUP: False},
        InstrumentParameters.CALIBRATION_COEFFICIENTS_CHANNEL_3 : {TYPE: list, READONLY: True, DA: False, STARTUP: False},
        InstrumentParameters.CALIBRATION_COEFFICIENTS_CHANNEL_4 : {TYPE: list, READONLY: True, DA: False, STARTUP: False},
        InstrumentParameters.CALIBRATION_COEFFICIENTS_CHANNEL_5 : {TYPE: list, READONLY: True, DA: False, STARTUP: False},
        InstrumentParameters.CALIBRATION_COEFFICIENTS_CHANNEL_6 : {TYPE: list, READONLY: True, DA: False, STARTUP: False},
        InstrumentParameters.CALIBRATION_COEFFICIENTS_CHANNEL_7 : {TYPE: list, READONLY: True, DA: False, STARTUP: False},
        InstrumentParameters.CALIBRATION_COEFFICIENTS_CHANNEL_8 : {TYPE: list, READONLY: True, DA: False, STARTUP: False},
        InstrumentParameters.CALIBRATION_COEFFICIENTS_CHANNEL_9 : {TYPE: list, READONLY: True, DA: False, STARTUP: False},
        InstrumentParameters.CALIBRATION_COEFFICIENTS_CHANNEL_10 : {TYPE: list, READONLY: True, DA: False, STARTUP: False},
        InstrumentParameters.CALIBRATION_COEFFICIENTS_CHANNEL_11 : {TYPE: list, READONLY: True, DA: False, STARTUP: False},
        InstrumentParameters.CALIBRATION_COEFFICIENTS_CHANNEL_12 : {TYPE: list, READONLY: True, DA: False, STARTUP: False},
        InstrumentParameters.CALIBRATION_COEFFICIENTS_CHANNEL_13 : {TYPE: list, READONLY: True, DA: False, STARTUP: False},
        InstrumentParameters.CALIBRATION_COEFFICIENTS_CHANNEL_14 : {TYPE: list, READONLY: True, DA: False, STARTUP: False},
        InstrumentParameters.CALIBRATION_COEFFICIENTS_CHANNEL_15 : {TYPE: list, READONLY: True, DA: False, STARTUP: False},
        InstrumentParameters.CALIBRATION_COEFFICIENTS_CHANNEL_16 : {TYPE: list, READONLY: True, DA: False, STARTUP: False},
        InstrumentParameters.CALIBRATION_COEFFICIENTS_CHANNEL_17 : {TYPE: list, READONLY: True, DA: False, STARTUP: False},
        InstrumentParameters.CALIBRATION_COEFFICIENTS_CHANNEL_18 : {TYPE: list, READONLY: True, DA: False, STARTUP: False},
        InstrumentParameters.CALIBRATION_COEFFICIENTS_CHANNEL_19 : {TYPE: list, READONLY: True, DA: False, STARTUP: False},
        InstrumentParameters.CALIBRATION_COEFFICIENTS_CHANNEL_20 : {TYPE: list, READONLY: True, DA: False, STARTUP: False},
        InstrumentParameters.CALIBRATION_COEFFICIENTS_CHANNEL_21 : {TYPE: list, READONLY: True, DA: False, STARTUP: False},
        InstrumentParameters.CALIBRATION_COEFFICIENTS_CHANNEL_22 : {TYPE: list, READONLY: True, DA: False, STARTUP: False},
        InstrumentParameters.CALIBRATION_COEFFICIENTS_CHANNEL_23 : {TYPE: list, READONLY: True, DA: False, STARTUP: False},
        InstrumentParameters.CALIBRATION_COEFFICIENTS_CHANNEL_24 : {TYPE: list, READONLY: True, DA: False, STARTUP: False},
    }

    # parameter values to test.
    paramter_test_values = {InstrumentParameters.START_DATE_AND_TIME : TIME_IN_PAST,
                            InstrumentParameters.END_DATE_AND_TIME : TIME_IN_FUTURE,
                            InstrumentParameters.SAMPLE_INTERVAL : '00:00:15',
                            InstrumentParameters.POWER_ALWAYS_ON : 1,
                            InstrumentParameters.SIX_HZ_PROFILING_MODE : 0,
                            InstrumentParameters.OUTPUT_INCLUDES_SERIAL_NUMBER : 1,
                            InstrumentParameters.OUTPUT_INCLUDES_BATTERY_VOLTAGE : 1,
                            InstrumentParameters.SAMPLING_LED : 0,
                            InstrumentParameters.ENGINEERING_UNITS_OUTPUT : 1,
                            InstrumentParameters.AUTO_RUN : 1,
                            InstrumentParameters.INHIBIT_DATA_STORAGE : 1,
                            }
    
    _raw_coefficients = {
        InstrumentParameters.BATTERY_VOLTAGE:  '8ABAT\r\n',
        InstrumentParameters.CALIBRATION_COEFFICIENTS_CHANNEL_1:  '4C02E5F8338B6C3F2EE9CCCCA56F30BF22757E403EB0C43EFF5CF27A032669BECAL\r\n',
        InstrumentParameters.CALIBRATION_COEFFICIENTS_CHANNEL_2:  'BE6B421617B56C3FD5784086847630BF905452AD92CCC43E085570CAF14B70BECAL\r\n',
        InstrumentParameters.CALIBRATION_COEFFICIENTS_CHANNEL_3:  '242263F451486C3F5AF6B89F195C30BFB79BE3E59B53C43EB008321DA84F71BECAL\r\n',
        InstrumentParameters.CALIBRATION_COEFFICIENTS_CHANNEL_4:  '891826C0BBE16C3FF6BCCDDAD77030BFEF6D8EAAA735C53EEAD71EBC6CB671BECAL\r\n',
        InstrumentParameters.CALIBRATION_COEFFICIENTS_CHANNEL_5:  'DB2BA620129C6C3FC06A17A5CE6830BF5EBF4750E2ACC43ED9C08996BF8671BECAL\r\n',
        InstrumentParameters.CALIBRATION_COEFFICIENTS_CHANNEL_6:  '9832B7EB936E6C3F97A33505556630BFC4C17691D551C43E28FAC2E315E467BECAL\r\n',
        InstrumentParameters.CALIBRATION_COEFFICIENTS_CHANNEL_7:  '9E067E30B5BE6C3FF579E335BB7B30BFA90F629A9910C53EBB2346D1E28467BECAL\r\n',
        InstrumentParameters.CALIBRATION_COEFFICIENTS_CHANNEL_8:  '05881C51EBB86C3FC7465FC2E47030BFED17ABD188B2C43E5927D2EC910671BECAL\r\n',
        InstrumentParameters.CALIBRATION_COEFFICIENTS_CHANNEL_9:  '056122D77F6A6C3FEB3E4825ED6030BFB79071014685C43E493A8785B48C70BECAL\r\n',
        InstrumentParameters.CALIBRATION_COEFFICIENTS_CHANNEL_10: 'CAF90420DD8C6C3FF05473B3867330BF46F93CFC3A71C43E8F029EDCE8A470BECAL\r\n',
        InstrumentParameters.CALIBRATION_COEFFICIENTS_CHANNEL_11: 'A718DC5CBD776C3F3499D9E3555F30BF6898FE4C1FC0C43E498718800D4D6BBECAL\r\n',
        InstrumentParameters.CALIBRATION_COEFFICIENTS_CHANNEL_12: 'FCAC137DCC5C6C3FE784F5DBC46130BFD3725AB17844C43EA0421314BF4771BECAL\r\n',
        InstrumentParameters.CALIBRATION_COEFFICIENTS_CHANNEL_13: '0D618D51A16A6C3F428D6D7DAA6E30BF2957DF907903C43EFF89ED2B0C296FBECAL\r\n',
        InstrumentParameters.CALIBRATION_COEFFICIENTS_CHANNEL_14: '53550E2075C36C3F87A2176B7F7330BF664CD355581CC53EE54C1B4B7A4E6DBECAL\r\n',
        InstrumentParameters.CALIBRATION_COEFFICIENTS_CHANNEL_15: '194554FC74456C3F3BE7497C9E5630BFCEF5601309A9C43E64C9B4A15A766CBECAL\r\n',
        InstrumentParameters.CALIBRATION_COEFFICIENTS_CHANNEL_16: 'E677D71494646C3F3C2B90A7136830BF5C9E8FE502D6C43EAF0199BE495667BECAL\r\n',
        InstrumentParameters.CALIBRATION_COEFFICIENTS_CHANNEL_17: '04C6AF97FEE46C3F2C51B20CD37630BF06EAFA626607C53EB8CD64294E5070BECAL\r\n',
        InstrumentParameters.CALIBRATION_COEFFICIENTS_CHANNEL_18: 'A571169A43FB6C3FFFAEE8F3097C30BF86E1E8BCCF27C53E832EC500513472BECAL\r\n',
        InstrumentParameters.CALIBRATION_COEFFICIENTS_CHANNEL_19: 'AB31AF4315F46C3F83F6A77BB88330BF4A91C3CAB7FCC43EC21A809AA3436CBECAL\r\n',
        InstrumentParameters.CALIBRATION_COEFFICIENTS_CHANNEL_20: '1257746962BD6C3F86B89412DC7630BFEA35F6B9C3B3C43E9270885A3A2D70BECAL\r\n',
        InstrumentParameters.CALIBRATION_COEFFICIENTS_CHANNEL_21: 'C3B12A617B066D3FC455D033A87530BF70459B83A260C53EAFEA58B2FBB670BECAL\r\n',
        InstrumentParameters.CALIBRATION_COEFFICIENTS_CHANNEL_22: '306A248B2E726C3FEB9788E93F5C30BFB08D70B2ADDFC43E7F8FFA4D5AC96CBECAL\r\n',
        InstrumentParameters.CALIBRATION_COEFFICIENTS_CHANNEL_23: 'A8A8D23B47876C3F08CCD99F676330BF849601A38FB8C43E3DCF7A08A8EA67BECAL\r\n',
        InstrumentParameters.CALIBRATION_COEFFICIENTS_CHANNEL_24: '13ED538DBED06C3F73B8DB10687030BF1014A4477326C53E8B9E285D3F586CBECAL\r\n',
    }
    
    _engineering_parameters = {
        XR_420EngineeringDataParticleKey.BATTERY_VOLTAGE: {TYPE: float, REQUIRED: False},
        XR_420EngineeringDataParticleKey.CALIBRATION_COEFFICIENTS: {
            TYPE: list,
            VALUE: [
                [0.00348434592083916, -0.00025079534389118, 2.46625541318206e-06, -4.68427140350704e-08],
                [0.00350431927843206, -0.000251204828829799, 2.47944749760338e-06, -6.07097826319064e-08],
                [0.00345245367779891, -0.000249630218352203, 2.42311925467998e-06, -6.44890925539532e-08],
                [0.00352560682330522, -0.000250866602804003, 2.52838011189997e-06, -6.59845645057904e-08],
                [0.00349238911184589, -0.000250387621319053, 2.46469119446334e-06, -6.52907822336288e-08],
                [0.00347069636129611, -0.000250240094109838, 2.42229283361364e-06, -4.45003789108644e-08],
                [0.00350890530165844, -0.000251515584649114, 2.51112506349963e-06, -4.38077113777949e-08],
                [0.00350614509888292, -0.000250869607382059, 2.4673223724984e-06, -6.34255414457636e-08],
                [0.00346875161001148, -0.000249917885668956, 2.4462460817433e-06, -6.16521743719807e-08],
                [0.00348513782969848, -0.000251026521664712, 2.43691281012686e-06, -6.20043955328834e-08],
                [0.00347506508740299, -0.000249823064086735, 2.47364969392914e-06, -5.08520514692428e-08],
                [0.00346221865821905, -0.000249968110400968, 2.41607029745207e-06, -6.43739826056667e-08],
                [0.00346881396800936, -0.000250736831210758, 2.38580390197586e-06, -5.80406598258295e-08],
                [0.00351117015857009, -0.000251024826040815, 2.51659427750457e-06, -5.45877098086669e-08],
                [0.00345108841668974, -0.000249303524732281, 2.46289905716957e-06, -5.30152030837836e-08],
                [0.00346592828894553, -0.000250344084236676, 2.48384257560737e-06, -4.34686667325137e-08],
                [0.0035271618376036, -0.000251223111896753, 2.50684094979287e-06, -6.07732409715931e-08],
                [0.00353778079506935, -0.000251533918261812, 2.52193374386203e-06, -6.78165294521451e-08],
                [0.00353435662461817, -0.000251991786768581, 2.50186675120244e-06, -5.26462032302453e-08],
                [0.00350827427940715, -0.000251225212724367, 2.46789518571518e-06, -6.02627979813181e-08],
                [0.00354312989778391, -0.000251153531111239, 2.54839417555195e-06, -6.22674006461501e-08],
                [0.0034724148801051, -0.000249639133047429, 2.48834421114212e-06, -5.3619098270147e-08],
                [0.0034824744494318, -0.000250065611772488, 2.47012874159369e-06, -4.45481883026538e-08],
                [0.00351750580977995, -0.000250840574934303, 2.52129990230494e-06, -5.2796149358899e-08],
            ]
        }
    }
        
    _sample_parameters = {
        XR_420SampleDataParticleKey.TIMESTAMP: {TYPE: float, VALUE: 3223662780.0},
        XR_420SampleDataParticleKey.TEMPERATURE: {TYPE: list, VALUE:
            [ 21.4548, 21.0132, 20.9255, 21.1266, 21.1341, 21.5606, 21.2156, 21.4749,
              21.3044, 21.1320, 21.1798, 21.2352, 21.3488, 21.1214, 21.6426, 21.1479,
              21.0069, 21.5426, 21.3204, 21.2402, 21.3968, 21.4371, 21.0411, 21.4361 ]
        },
        XR_420SampleDataParticleKey.BATTERY_VOLTAGE: {TYPE: float, VALUE: 11.5916},
        XR_420SampleDataParticleKey.SERIAL_NUMBER: {TYPE: unicode, VALUE: u"021968"},
    }
    
    SAMPLE = \
        "TIM 020225135300 " + \
        "21.4548 21.0132 20.9255 21.1266 21.1341 21.5606 21.2156 21.4749 " + \
        "21.3044 21.1320 21.1798 21.2352 21.3488 21.1214 21.6426 21.1479 " + \
        "21.0069 21.5426 21.3204 21.2402 21.3968 21.4371 21.0411 21.4361 " + \
        "BV: 11.5916 SN: 021968 FET"
             
    def assert_clock_set_correctly(self, sent_time, rcvd_time):
        # verify that the dates match
        self.assertTrue(sent_time[:12].upper() in rcvd_time.upper())
           
        sent_timestamp = time.strptime(sent_time, "%d %b %Y %H:%M:%S")
        ntp_sent_timestamp = ntplib.system_to_ntp_time(time.mktime(sent_timestamp))
        rcvd_timestamp = time.strptime(rcvd_time, "%d %b %Y %H:%M:%S")
        ntp_rcvd_timestamp = ntplib.system_to_ntp_time(time.mktime(rcvd_timestamp))
        # verify that the times match closely
        if ntp_rcvd_timestamp - ntp_sent_timestamp > 3:
            self.fail("time delta too large after clock sync")        
    
    def assert_set_clock(self, time):
        new_parameter_values = {}
        new_parameter_values[InstrumentParameters.LOGGER_DATE_AND_TIME] = time
        new_parameter_list = []
        new_parameter_list.append(InstrumentParameters.LOGGER_DATE_AND_TIME)
        
        # Set parameter and verify.
        self.driver_client.cmd_dvr('set_resource', new_parameter_values)
        reply = self.driver_client.cmd_dvr('get_resource', new_parameter_list)
        
        rcvd_time = reply[InstrumentParameters.LOGGER_DATE_AND_TIME]
        self.assert_clock_set_correctly(time, rcvd_time)

    
    def assert_particle_sample(self, data_particle, verify_values = False):
        '''
        Verify a take sample data particle
        @param data_particle:  data particle
        @param verify_values:  bool, should we verify parameter values
        '''
        self.assert_data_particle_header(data_particle, DataParticleType.SAMPLE)
        self.assert_data_particle_parameters(data_particle, self._sample_parameters, verify_values)

    def assert_engineering_data_particle_header(self, data_particle, stream_name):
        # Verify a engineering data particle header is formatted properly w/o port agent timestamp
        # @param data_particle: version 1 data particle
        # @param stream_name: version 1 data particle
        
        sample_dict = self.convert_data_particle_to_dict(data_particle)
        log.debug("assert_engineering_data_particle_header: SAMPLEDICT = %s" % sample_dict)

        self.assertTrue(sample_dict[DataParticleKey.STREAM_NAME], stream_name)
        self.assertTrue(sample_dict[DataParticleKey.PKT_FORMAT_ID], DataParticleValue.JSON_DATA)
        self.assertTrue(sample_dict[DataParticleKey.PKT_VERSION], 1)
        self.assertIsInstance(sample_dict[DataParticleKey.VALUES], list)

        self.assertTrue(sample_dict.get(DataParticleKey.PREFERRED_TIMESTAMP))

        self.assertIsNotNone(sample_dict.get(DataParticleKey.DRIVER_TIMESTAMP))
        self.assertIsInstance(sample_dict.get(DataParticleKey.DRIVER_TIMESTAMP), float)

    def assert_particle_engineering(self, data_particle, verify_values = True):
        '''
        Verify an engineering data particle
        @param data_particle:  status data particle
        @param verify_values:  bool, should we verify parameter values
        '''
        self.assert_engineering_data_particle_header(data_particle, DataParticleType.ENGINEERING)
        self.assert_data_particle_parameters(data_particle, self._engineering_parameters, verify_values)


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
class TestUNIT(InstrumentDriverUnitTestCase, UtilMixin):
    """Unit Test Container"""
    
    def setUp(self):
        InstrumentDriverUnitTestCase.setUp(self)
    
    def assert_engineering_particle_published(self, particle_assert_method, verify_values = False):
        """
        Verify that we can send data through the port agent and the the correct particles
        are generated.

        Create a port agent packet, send it through got_data, then finally grab the data particle
        from the data particle queue and verify it using the passed in assert method.
        @param driver: instrument driver with mock port agent client
        @param sample_data: the byte string we want to send to the driver
        @param particle_assert_method: assert method to validate the data particle.
        @param verify_values: Should we validate values?
        """
        # Find all particles of the correct data particle types (not raw)
        particles = []
        for p in self._data_particle_received:
            particle_dict = json.loads(p)
            stream_type = particle_dict.get('stream_name')
            self.assertIsNotNone(stream_type)
            if(stream_type == DataParticleType.ENGINEERING):
                particles.append(p)

        log.debug("status particles: %s " % particles)
        self.assertEqual(len(particles), 1)

        # Verify the data particle
        particle_assert_method(particles.pop(), verify_values)

    def test_driver_enums(self):
        """
        Verify that all driver enumerations have no duplicate values that might cause confusion.  Also
        do a little extra validation for the Capabilites
        """
        self.assert_enum_has_no_duplicates(ScheduledJob())
        self.assert_enum_has_no_duplicates(DataParticleType())
        self.assert_enum_has_no_duplicates(InstrumentResponses())
        self.assert_enum_has_no_duplicates(InstrumentCmds())
        self.assert_enum_has_no_duplicates(ProtocolStates())
        self.assert_enum_has_no_duplicates(ProtocolEvent())
        self.assert_enum_has_no_duplicates(InstrumentParameters())
        self.assert_enum_has_no_duplicates(AdvancedFunctionsParameters())
        self.assert_enum_has_no_duplicates(AdvancedFuntionsBits())

        # Test capabilities for duplicates, then verify that capabilities is a subset of protocol events
        self.assert_enum_has_no_duplicates(Capability())
        self.assert_enum_complete(Capability(), ProtocolEvent())

    def test_chunker(self):
        """
        Test the chunker and verify the particles created.
        """
        chunker = StringChunker(InstrumentProtocol.chunker_sieve_function)

        self.assert_chunker_sample(chunker, self.SAMPLE)
        self.assert_chunker_sample_with_noise(chunker, self.SAMPLE)
        self.assert_chunker_fragmented_sample(chunker, self.SAMPLE)
        self.assert_chunker_combined_sample(chunker, self.SAMPLE)
    
    def test_corrupt_data_sample(self):
        # garbage is not okay
        particle = XR_420SampleDataParticle(self.SAMPLE.replace('020225135300', 'foobar'),
                                            port_timestamp = 3558720820.531179)
        with self.assertRaises(SampleException):
            particle.generate()
         
    def test_engineering_particle(self):
        """
        Verify driver produces the correct engineering data particle
        """
        driver = InstrumentDriver(self._got_data_event_callback)
        self.assert_initialize_driver(driver, ProtocolStates.COMMAND)
        
        # mock the _update_params() method which tries to get parameters from an actual instrument
        _update_params_mock = Mock(spec="_update_params")
        driver._protocol._update_params = _update_params_mock

        # load the engineering parameter values
        pd = driver._protocol._param_dict
        for name in self._raw_coefficients.keys():
            pd.update_specific(name, self._raw_coefficients[name])
            
        # clear out any old events
        self.clear_data_particle_queue()

        # call the method in the driver that generates and sends the status data particle
        driver._protocol._generate_status_event()
        
        # check that the status data particle was published
        self.assert_engineering_particle_published(self.assert_particle_engineering, verify_values=True)
    
    def test_got_data(self):
        """
        Verify sample data passed through the got data method produces the correct data particles
        """
        # Create and initialize the instrument driver with a mock port agent
        driver = InstrumentDriver(self._got_data_event_callback)
        self.assert_initialize_driver(driver)    # defaults to autosample mode, so sample generated

        self.assert_raw_particle_published(driver, True)

        # validate data particle
        self.assert_particle_published(driver, self.SAMPLE, self.assert_particle_sample, True)

    def test_protocol_filter_capabilities(self):
        """
        This tests driver filter_capabilities.
        Iterate through available capabilities, and verify that they can pass successfully through the filter.
        Test silly made up capabilities to verify they are blocked by filter.
        """
        my_event_callback = Mock(spec="UNKNOWN WHAT SHOULD GO HERE FOR evt_callback")
        protocol = InstrumentProtocol(InstrumentResponses, INSTRUMENT_NEWLINE, my_event_callback)
        driver_capabilities = Capability().list()
        test_capabilities = Capability().list()

        # Add a bogus capability that will be filtered out.
        test_capabilities.append("BOGUS_CAPABILITY")

        # Verify "BOGUS_CAPABILITY was filtered out
        self.assertEquals(driver_capabilities, protocol._filter_capabilities(test_capabilities))
        
    def test_driver_parameters(self):
        """
        Verify the set of parameters known by the driver
        """
        driver = InstrumentDriver(self._got_data_event_callback)
        self.assert_initialize_driver(driver, ProtocolStates.COMMAND)

        expected_parameters = sorted(self._driver_parameters.keys())
        reported_parameters = sorted(driver.get_resource(InstrumentParameters.ALL))

        log.debug("Reported Parameters: %s" % reported_parameters)
        log.debug("Expected Parameters: %s" % expected_parameters)

        self.assertEqual(reported_parameters, expected_parameters)

        # Verify the parameter definitions
        self.assert_driver_parameter_definition(driver, self._driver_parameters)

    def test_capabilities(self):
        """
        Verify the FSM reports capabilities as expected.  All states defined in this dict must
        also be defined in the protocol FSM.
        """
        capabilities = {
            ProtocolStates.UNKNOWN: ['DRIVER_EVENT_DISCOVER',
                                     'DRIVER_EVENT_GET'],
            ProtocolStates.COMMAND: ['DRIVER_EVENT_ACQUIRE_STATUS',
                                     'DRIVER_EVENT_CLOCK_SYNC',
                                     'DRIVER_EVENT_GET',
                                     'DRIVER_EVENT_SET',
                                     'DRIVER_EVENT_START_AUTOSAMPLE',
                                     'DRIVER_EVENT_START_DIRECT'],
            ProtocolStates.AUTOSAMPLE: ['DRIVER_EVENT_STOP_AUTOSAMPLE',
                                        'DRIVER_EVENT_ACQUIRE_STATUS',
                                        'DRIVER_EVENT_CLOCK_SYNC',
                                        'DRIVER_EVENT_GET'],
            ProtocolStates.DIRECT_ACCESS: ['DRIVER_EVENT_STOP_DIRECT', 
                                           'EXECUTE_DIRECT']
        }

        driver = InstrumentDriver(self._got_data_event_callback)
        self.assert_capabilities(driver, capabilities)


###############################################################################
#                            INTEGRATION TESTS                                #
#     Integration test test the direct driver / instrument interaction        #
#     but making direct calls via zeromq.                                     #
#     - Common Integration tests test the driver through the instrument agent #
#     and common for all drivers (minimum requirement for ION ingestion)       #
###############################################################################

@attr('INT', group='mi')
class TestINT(InstrumentDriverIntegrationTestCase, UtilMixin):
    """Integration Test Container"""
    
    def _is_time_set(self, time_param, expected_time, time_format = "%d %b %Y %H:%M:%S", tolerance=3):
        """
        Verify is what we expect it to be within a given tolerance
        @param time_param: driver parameter
        @param expected_time: what the time should be in seconds since unix epoch or formatted time string
        @param time_format: date time format
        @param tolerance: how close to the set time should the get be?
        """

        result_time = self.assert_get(time_param)
        result_time_struct = time.strptime(result_time, time_format)
        converted_time = time.mktime(result_time_struct)

        if(isinstance(expected_time, float)):
            expected_time_struct = time.localtime(expected_time)
        else:
            # convert time struct to string and back again to get around DST issue so that
            # time is interpreted the same for both the instrument and test
            expected_time_struct = time.strptime(time.strftime(time_format, expected_time), time_format)
        
        log.debug("Current Time: %s, Expected Time: %s", time.strftime("%d %b %y %H:%M:%S", result_time_struct),
                  time.strftime("%d %b %y %H:%M:%S", expected_time_struct))

        log.debug("Current Time: %s, Expected Time: %s, Tolerance: %s",
                  converted_time, time.mktime(expected_time_struct), tolerance)

        # Verify the clock is set within the tolerance
        return abs(converted_time - time.mktime(expected_time_struct)) <= tolerance

    def assert_clock_set(self, time_param, sync_clock_cmd = DriverEvent.CLOCK_SYNC, timeout = 20, tolerance=3):
        """
        Verify the clock is set to at least the current date
        """
        log.debug("verify clock is set to the current time")

        timeout_time = time.time() + timeout
        
        while(not self._is_time_set(time_param, time.gmtime(), tolerance=tolerance)):
            log.debug("time isn't current. sleep for a bit")
            time.sleep(2)

            # Run acquire status command to set clock parameter
            self.assert_driver_command(sync_clock_cmd)

            log.debug("T: %s T: %s", time.time(), timeout_time)
            self.assertLess(time.time(), timeout_time, msg="Timeout waiting for clock sync event")

    def assert_initialize_driver_unspecific(self):
        """
        Walk an uninitialized driver through it's initialize process.  
        """
        # Test the driver is in state unconfigured.
        self.assert_current_state(DriverConnectionState.UNCONFIGURED)

        # Configure driver for comms and transition to disconnected.
        reply = self.driver_client.cmd_dvr('configure', self.port_agent_comm_config())

        # Test the driver is configured for comms.
        self.assert_current_state(DriverConnectionState.DISCONNECTED)

        reply = self.driver_client.cmd_dvr('connect')

        # Test the driver is in unknown state.
        self.assert_current_state(DriverProtocolState.UNKNOWN)

        reply = self.driver_client.cmd_dvr('discover_state')

        state = self.driver_client.cmd_dvr('get_resource_state')
        log.debug("initialize final state: %s" % state)
        
    def _assert_parameters_on_initialization(self):
        self.assert_initialize_driver_unspecific()
        reply = self.driver_client.cmd_dvr('get_resource', InstrumentParameters.ALL)
        self.assert_parameters(reply, self._driver_parameters, True)
        return reply

    def test_instrument_wakeup(self):
        """
        @brief Test for instrument wakeup, expects instrument to be in 'command' state
        """
        self.assert_initialize_driver()
                
    def test_get_parameters(self):
        """
        Test driver parameters and verify their type.  Startup parameters also verify the parameter
        value.  This test confirms that parameters are being read/converted properly and that
        the startup has been applied.
        """
        reply = self._assert_parameters_on_initialization()
        for (name, value) in reply.iteritems():
            log.debug("test_get_parameters: name=%s, value=%s" %(name, str(value)))

    def test_set_clock(self):
        """
        Test device clock, needs to be close but not an exact match.
        """
        self.assert_initialize_driver()
        
        self.assert_set_clock(self.CLOCK_SYNC_TIME)

    def test_set(self):
        """
        Test device parameter access, needs to be an exact match.
        """
        self.assert_initialize_driver()

        # construct values dynamically to get time stamp for notes
        new_parameter_values = {}

        for key in self.paramter_test_values.iterkeys():
            new_parameter_values[key] = self.paramter_test_values[key]
               
        # Set parameters in bulk and verify.
        self.assert_set_bulk(new_parameter_values)
        
        # Set parameters individually and verify.
        for key in self.paramter_test_values.iterkeys():
            self.assert_set(key, self.paramter_test_values[key])
        
    def test_set_errors(self):
        """
        Test error device parameter access.
        """
        self.assert_initialize_driver()

        # try a parameter that shouldn't exist
        self.assert_set_exception('bogus', 'nada')

        # try values that are not legitimate for each parameter
        self.assert_set_exception(InstrumentParameters.POWER_ALWAYS_ON, 'bad')
        self.assert_set_exception(InstrumentParameters.POWER_ALWAYS_ON, 2)
        
        self.assert_set_exception(InstrumentParameters.ENGINEERING_UNITS_OUTPUT, 'bad')
        self.assert_set_exception(InstrumentParameters.ENGINEERING_UNITS_OUTPUT, 255)
        
        self.assert_set_exception(InstrumentParameters.INHIBIT_DATA_STORAGE, 'bad')
        self.assert_set_exception(InstrumentParameters.INHIBIT_DATA_STORAGE, -1)
        
        self.assert_set_exception(InstrumentParameters.OUTPUT_INCLUDES_BATTERY_VOLTAGE, 'bad')
        self.assert_set_exception(InstrumentParameters.OUTPUT_INCLUDES_BATTERY_VOLTAGE, 2090)
        
        self.assert_set_exception(InstrumentParameters.OUTPUT_INCLUDES_SERIAL_NUMBER, 'stupid')
        self.assert_set_exception(InstrumentParameters.OUTPUT_INCLUDES_SERIAL_NUMBER, 4.3)
        
        self.assert_set_exception(InstrumentParameters.SAMPLING_LED, 'bad')
        self.assert_set_exception(InstrumentParameters.SAMPLING_LED, 10)
        
        self.assert_set_exception(InstrumentParameters.SIX_HZ_PROFILING_MODE, 'really bad')
        self.assert_set_exception(InstrumentParameters.SIX_HZ_PROFILING_MODE, -20)
        
        self.assert_set_exception(InstrumentParameters.AUTO_RUN, 'dumb')
        self.assert_set_exception(InstrumentParameters.AUTO_RUN, -2000)
        
        self.assert_set_exception(InstrumentParameters.AUTO_RUN, 'bad')
        self.assert_set_exception(InstrumentParameters.AUTO_RUN, -1)
        
        self.assert_set_exception(InstrumentParameters.END_DATE_AND_TIME, 1)
        self.assert_set_exception(InstrumentParameters.END_DATE_AND_TIME, '40 Feb 2002 11:18:42')
        self.assert_set_exception(InstrumentParameters.END_DATE_AND_TIME, '21 fab 2002 11:18:42')
        self.assert_set_exception(InstrumentParameters.END_DATE_AND_TIME, '21 Feb 2O02 11:18:42')
        self.assert_set_exception(InstrumentParameters.END_DATE_AND_TIME, '21 Feb 2002 25:18:42')
        self.assert_set_exception(InstrumentParameters.END_DATE_AND_TIME, '21 Feb 2002 11:65:42')
        self.assert_set_exception(InstrumentParameters.END_DATE_AND_TIME, '21 Feb 2002 11:18:61')

        self.assert_set_exception(InstrumentParameters.SAMPLE_INTERVAL, '11:18:61')
        self.assert_set_exception(InstrumentParameters.SAMPLE_INTERVAL, '25:18:61')
        self.assert_set_exception(InstrumentParameters.SAMPLE_INTERVAL, '11:118:61')
        self.assert_set_exception(InstrumentParameters.SAMPLE_INTERVAL, 3)
        
        self.assert_set_exception(InstrumentParameters.START_DATE_AND_TIME, 'junk')
        self.assert_set_exception(InstrumentParameters.START_DATE_AND_TIME, '40 Feb 2002 11:18:42')
        self.assert_set_exception(InstrumentParameters.START_DATE_AND_TIME, '21 fab 2002 11:18:42')
        self.assert_set_exception(InstrumentParameters.START_DATE_AND_TIME, '21 Feb 2O02 11:18:42')
        self.assert_set_exception(InstrumentParameters.START_DATE_AND_TIME, '21 Feb 2002 25:18:42')
        self.assert_set_exception(InstrumentParameters.START_DATE_AND_TIME, '21 Feb 2002 11:65:42')
        self.assert_set_exception(InstrumentParameters.START_DATE_AND_TIME, '21 Feb 2002 11:18:61')

        self.assert_set_exception(InstrumentParameters.LOGGER_DATE_AND_TIME, 4.6)
        self.assert_set_exception(InstrumentParameters.LOGGER_DATE_AND_TIME, '40 Feb 2002 11:18:42')
        self.assert_set_exception(InstrumentParameters.LOGGER_DATE_AND_TIME, '21 fab 2002 11:18:42')
        self.assert_set_exception(InstrumentParameters.LOGGER_DATE_AND_TIME, '21 Feb 2O02 11:18:42')
        self.assert_set_exception(InstrumentParameters.LOGGER_DATE_AND_TIME, '21 Feb 2002 25:18:42')
        self.assert_set_exception(InstrumentParameters.LOGGER_DATE_AND_TIME, '21 Feb 2002 11:65:42')

    def test_read_only_parameters(self):
        self.assert_initialize_driver()

        self.assert_set_readonly(InstrumentParameters.STATUS)
        self.assert_set_readonly(InstrumentParameters.IDENTIFICATION)
        self.assert_set_readonly(InstrumentParameters.BATTERY_VOLTAGE)
        self.assert_set_readonly(InstrumentParameters.CALIBRATION_COEFFICIENTS_CHANNEL_1)
        self.assert_set_readonly(InstrumentParameters.CALIBRATION_COEFFICIENTS_CHANNEL_2)
        self.assert_set_readonly(InstrumentParameters.CALIBRATION_COEFFICIENTS_CHANNEL_3)
        self.assert_set_readonly(InstrumentParameters.CALIBRATION_COEFFICIENTS_CHANNEL_4)
        self.assert_set_readonly(InstrumentParameters.CALIBRATION_COEFFICIENTS_CHANNEL_5)
        self.assert_set_readonly(InstrumentParameters.CALIBRATION_COEFFICIENTS_CHANNEL_6)
        self.assert_set_readonly(InstrumentParameters.CALIBRATION_COEFFICIENTS_CHANNEL_7)
        self.assert_set_readonly(InstrumentParameters.CALIBRATION_COEFFICIENTS_CHANNEL_8)
        self.assert_set_readonly(InstrumentParameters.CALIBRATION_COEFFICIENTS_CHANNEL_9)
        self.assert_set_readonly(InstrumentParameters.CALIBRATION_COEFFICIENTS_CHANNEL_10)
        self.assert_set_readonly(InstrumentParameters.CALIBRATION_COEFFICIENTS_CHANNEL_11)
        self.assert_set_readonly(InstrumentParameters.CALIBRATION_COEFFICIENTS_CHANNEL_12)
        self.assert_set_readonly(InstrumentParameters.CALIBRATION_COEFFICIENTS_CHANNEL_13)
        self.assert_set_readonly(InstrumentParameters.CALIBRATION_COEFFICIENTS_CHANNEL_14)
        self.assert_set_readonly(InstrumentParameters.CALIBRATION_COEFFICIENTS_CHANNEL_15)
        self.assert_set_readonly(InstrumentParameters.CALIBRATION_COEFFICIENTS_CHANNEL_16)
        self.assert_set_readonly(InstrumentParameters.CALIBRATION_COEFFICIENTS_CHANNEL_17)
        self.assert_set_readonly(InstrumentParameters.CALIBRATION_COEFFICIENTS_CHANNEL_18)
        self.assert_set_readonly(InstrumentParameters.CALIBRATION_COEFFICIENTS_CHANNEL_19)
        self.assert_set_readonly(InstrumentParameters.CALIBRATION_COEFFICIENTS_CHANNEL_20)
        self.assert_set_readonly(InstrumentParameters.CALIBRATION_COEFFICIENTS_CHANNEL_21)
        self.assert_set_readonly(InstrumentParameters.CALIBRATION_COEFFICIENTS_CHANNEL_22)
        self.assert_set_readonly(InstrumentParameters.CALIBRATION_COEFFICIENTS_CHANNEL_23)
        self.assert_set_readonly(InstrumentParameters.CALIBRATION_COEFFICIENTS_CHANNEL_24)
    
    def test_startup_params(self):
        """
        Verify that startup parameters are applied correctly. Generally this
        happens in the driver discovery method.
        """

        # Change the values of these parameters to something before the
        # driver is re-initialized.  They should be blown away with startup values.
        new_values = {
            InstrumentParameters.SAMPLE_INTERVAL: '00:00:20',
            InstrumentParameters.START_DATE_AND_TIME: '10 Jan 2000 00:00:00',
            InstrumentParameters.END_DATE_AND_TIME: '10 Jan 2050 00:00:00',
            InstrumentParameters.POWER_ALWAYS_ON: 0,
            InstrumentParameters.SIX_HZ_PROFILING_MODE: 0,
            InstrumentParameters.OUTPUT_INCLUDES_SERIAL_NUMBER: 0,
            InstrumentParameters.OUTPUT_INCLUDES_BATTERY_VOLTAGE: 0,
            InstrumentParameters.SAMPLING_LED: 1,
            InstrumentParameters.ENGINEERING_UNITS_OUTPUT: 0,
            InstrumentParameters.AUTO_RUN: 0,
            InstrumentParameters.INHIBIT_DATA_STORAGE: 0,
        }

        # test in command mode
        self._assert_parameters_on_initialization()

        # test in autosample mode
        # set parameters to something other than startup values
        self.assert_set_bulk(new_values)
        self.assert_driver_command(ProtocolEvent.START_AUTOSAMPLE, state=ProtocolStates.AUTOSAMPLE, delay=1)
        # Force a re-apply startup parameters
        reply = self.driver_client.cmd_dvr('apply_startup_params')
        # Should be back to our startup parameters.
        reply = self.driver_client.cmd_dvr('get_resource', DriverParameter.ALL)
        self.assert_parameters(reply, self._driver_parameters, True)

    def test_commands(self):
        """
        Run instrument commands from both command and streaming mode.
        """
        self.assert_initialize_driver()

        ####
        # First test in command mode
        ####
        self.assert_driver_command(ProtocolEvent.CLOCK_SYNC)
        self.assert_driver_command(ProtocolEvent.ACQUIRE_STATUS)
        self.assert_driver_command(ProtocolEvent.START_AUTOSAMPLE, state=ProtocolStates.AUTOSAMPLE, delay=1)
        self.assert_driver_command(ProtocolEvent.STOP_AUTOSAMPLE, state=ProtocolStates.COMMAND, delay=1)

        ####
        # Test in streaming mode
        ####
        # Put us in streaming
        self.assert_driver_command(ProtocolEvent.START_AUTOSAMPLE, state=ProtocolStates.AUTOSAMPLE, delay=1)
        self.assert_driver_command(ProtocolEvent.CLOCK_SYNC)
        self.assert_driver_command(ProtocolEvent.ACQUIRE_STATUS)
        self.assert_driver_command(ProtocolEvent.STOP_AUTOSAMPLE, state=ProtocolStates.COMMAND, delay=1)
        
        ####
        # Test a bad command
        ####
        self.assert_driver_command_exception('ima_bad_command', exception_class=InstrumentCommandException)

    def test_instrument_start_stop_autosample(self):
        """
        @brief Test for start/stop of instrument autosample, puts instrument in 'command' state first
        """
        self.assert_initialize_driver()
                
        log.debug('test_instrumment_start_stop_autosample: starting autosample')
        # start auto-sample.
        reply = self.driver_client.cmd_dvr('execute_resource', ProtocolEvent.START_AUTOSAMPLE)

        # Test the driver is in autosample mode.
        state = self.driver_client.cmd_dvr('get_resource_state')
        self.assertEqual(state, ProtocolStates.AUTOSAMPLE)
        log.debug('test_instrumment_start_stop_autosample: autosample started')        
                
        log.debug('test_instrumment_start_stop_autosample: stopping autosample')
        # stop auto-sample.
        reply = self.driver_client.cmd_dvr('execute_resource', ProtocolEvent.STOP_AUTOSAMPLE)

        # Test the driver is in command mode.
        state = self.driver_client.cmd_dvr('get_resource_state')
        self.assertEqual(state, ProtocolStates.COMMAND)
        log.debug('test_instrumment_start_stop_autosample: autosample stopped')        


    def test_instrument_autosample_samples(self):
        """
        @brief Test for putting instrument in 'auto-sample' state and receiving samples
        """
        self.assert_initialize_driver()

        # command the instrument to auto-sample mode.
        self.driver_client.cmd_dvr('execute_resource', ProtocolEvent.START_AUTOSAMPLE)

        self.assert_current_state(ProtocolStates.AUTOSAMPLE)
           
        # wait for some samples to be generated
        log.debug('test_instrument_start_stop_autosample: waiting 45 seconds for samples')
        gevent.sleep(45)

        # Verify we received at least 2 samples.
        sample_events = [evt for evt in self.events if evt['type']==DriverAsyncEvent.SAMPLE]
        log.debug('test_instrument_start_stop_autosample: # 0f samples = %d' %len(sample_events))
        for sample in sample_events:
            if sample['value'].find(DataParticleType.SAMPLE) != -1:
                log.debug('parsed sample=%s\n' %sample)
                sample_dict = eval(sample['value'])     # turn string into dictionary
                values = sample_dict['values']          # get particle dictionary
                # pull timestamp out of particle
                ntp_timestamp = [item for item in values if item["value_id"] == "timestamp"][0]['value']
                float_timestamp = ntplib.ntp_to_system_time(ntp_timestamp)
                log.debug('dt=%s' %time.ctime(float_timestamp))
        self.assertTrue(len(sample_events) >= 2)

        # stop autosample and return to command mode
        self.driver_client.cmd_dvr('execute_resource', ProtocolEvent.STOP_AUTOSAMPLE)
                
        self.assert_current_state(ProtocolStates.COMMAND)
    

    def test_polled_particle_generation(self):
        """
        Test that we can generate particles with commands
        """
        self.assert_initialize_driver()

        self.assert_particle_generation(ProtocolEvent.ACQUIRE_STATUS, DataParticleType.ENGINEERING, self.assert_particle_engineering, delay=10)
        
    ###
    #   Test scheduled events
    ###

    def assert_acquire_status(self):
        """
        Verify a status particle was generated
        """
        self.clear_events()
        self.assert_async_particle_generation(DataParticleType.ENGINEERING, self.assert_particle_engineering, timeout=120)

    def test_scheduled_device_status_command(self):
        """
        Verify the device status command can be triggered and run in command
        """
        self.assert_scheduled_event(ScheduledJob.ACQUIRE_STATUS, self.assert_acquire_status, delay=30)
        self.assert_current_state(ProtocolStates.COMMAND)

    def test_scheduled_device_status_autosample(self):
        """
        Verify the device status command can be triggered and run in autosample
        """
        self.assert_scheduled_event(ScheduledJob.ACQUIRE_STATUS, self.assert_acquire_status,
                                    autosample_command=ProtocolEvent.START_AUTOSAMPLE, delay=60)
        self.assert_current_state(ProtocolStates.AUTOSAMPLE)
        self.assert_driver_command(ProtocolEvent.STOP_AUTOSAMPLE)

    def test_scheduled_clock_sync_command(self):
        """
        Verify the scheduled clock sync is triggered and functions as expected
        """
        timeout = 85
        self.assert_scheduled_event(ScheduledJob.CLOCK_SYNC, delay=timeout)
        self.assert_current_state(ProtocolStates.COMMAND)

        # Set the clock to some time in the past
        self.assert_set_clock(self.CLOCK_SYNC_TIME)

        # Check the clock until it is set correctly (by a schedued event)
        self.assert_clock_set(InstrumentParameters.LOGGER_DATE_AND_TIME)

    def test_scheduled_clock_sync_autosample(self):
        """
        Verify the scheduled clock sync is triggered and functions as expected
        """
        timeout = 240
        self.assert_scheduled_event(ScheduledJob.CLOCK_SYNC, delay=timeout)
        self.assert_current_state(ProtocolStates.COMMAND)

        # Set the clock to some time in the past
        self.assert_set_clock(self.CLOCK_SYNC_TIME)
        self.assert_driver_command(ProtocolEvent.START_AUTOSAMPLE)

        # Check the clock until it is set correctly (by a scheduled event)
        self.assert_clock_set(InstrumentParameters.LOGGER_DATE_AND_TIME)
        self.assert_driver_command(ProtocolEvent.STOP_AUTOSAMPLE)


###############################################################################
#                            QUALIFICATION TESTS                              #
# Device specific qualification tests are for                                 #
# testing device specific capabilities                                        #
###############################################################################

@attr('QUAL', group='mi')
class TestQUAL(InstrumentDriverQualificationTestCase, UtilMixin):
    """Qualification Test Container"""
    
    # Qualification tests live in the base class.  This class is extended
    # here so that when running this test from 'nosetests' all tests
    # (UNIT, INT, and QUAL) are run.  

    def test_direct_access_telnet_mode(self):
        """
        Test that we can connect to the instrument via direct access.  Also
        verify that direct access parameters are reset on exit.
        """
        self.assert_enter_command_mode()

        # go into direct access, and muck up a setting.
        self.assert_direct_access_start_telnet(timeout=600)
        self.assertTrue(self.tcp_client)
        self.tcp_client.send_data("AA")
        self.assertTrue(self.tcp_client.expect("RBR XR-420 6.810 021968"))

        self.assert_direct_access_stop_telnet()

               
    def test_parameter_enum(self):
        """
        @ brief InstrumentParameters enum test

            1. test that InstrumentParameters matches the expected enums from DriverParameter.
            2. test that multiple distinct parameters do not resolve back to the same string.
        """

        self.assertEqual(InstrumentParameters.ALL, DriverParameter.ALL)

        self.assert_enum_has_no_duplicates(DriverParameter)
        self.assert_enum_has_no_duplicates(InstrumentParameters)

    def test_protocol_state_enum(self):
        """
        @ brief ProtocolState enum test

            1. test that ProtocolState matches the expected enums from DriverProtocolState.
            2. test that multiple distinct states do not resolve back to the same string.

        """

        self.assertEqual(ProtocolStates.UNKNOWN, DriverProtocolState.UNKNOWN)
        self.assertEqual(ProtocolStates.COMMAND, DriverProtocolState.COMMAND)
        self.assertEqual(ProtocolStates.AUTOSAMPLE, DriverProtocolState.AUTOSAMPLE)
        self.assertEqual(ProtocolStates.DIRECT_ACCESS, DriverProtocolState.DIRECT_ACCESS)

        self.assert_enum_has_no_duplicates(DriverProtocolState)
        self.assert_enum_has_no_duplicates(ProtocolStates)

    def test_protocol_event_enum(self):
        """
        @brief ProtocolEvent enum test

            1. test that ProtocolEvent matches the expected enums from DriverProtocolState.
            2. test that multiple distinct events do not resolve back to the same string.
        """

        self.assertEqual(ProtocolEvent.ENTER, DriverEvent.ENTER)
        self.assertEqual(ProtocolEvent.EXIT, DriverEvent.EXIT)
        self.assertEqual(ProtocolEvent.GET, DriverEvent.GET)
        self.assertEqual(ProtocolEvent.SET, DriverEvent.SET)
        self.assertEqual(ProtocolEvent.DISCOVER, DriverEvent.DISCOVER)
        self.assertEqual(ProtocolEvent.START_AUTOSAMPLE, DriverEvent.START_AUTOSAMPLE)
        self.assertEqual(ProtocolEvent.STOP_AUTOSAMPLE, DriverEvent.STOP_AUTOSAMPLE)
        self.assertEqual(ProtocolEvent.EXECUTE_DIRECT, DriverEvent.EXECUTE_DIRECT)
        self.assertEqual(ProtocolEvent.START_DIRECT, DriverEvent.START_DIRECT)
        self.assertEqual(ProtocolEvent.STOP_DIRECT, DriverEvent.STOP_DIRECT)

        self.assert_enum_has_no_duplicates(DriverEvent)
        self.assert_enum_has_no_duplicates(ProtocolEvent)

    def test_get_capabilities(self):
        """
        @brief Verify that the correct capabilities are returned from get_capabilities
        at various driver/agent states.
        """
        ##################
        #  Command Mode
        ##################

        capabilities = {
            AgentCapabilityType.AGENT_COMMAND: [
                ResourceAgentEvent.CLEAR,
                ResourceAgentEvent.RESET,
                ResourceAgentEvent.GO_DIRECT_ACCESS,
                ResourceAgentEvent.GO_INACTIVE,
                ResourceAgentEvent.PAUSE
            ],
            AgentCapabilityType.AGENT_PARAMETER: self._common_agent_parameters(),
            AgentCapabilityType.RESOURCE_COMMAND: [
                DriverEvent.CLOCK_SYNC,
                DriverEvent.GET,
                DriverEvent.SET,
                DriverEvent.ACQUIRE_STATUS,
                DriverEvent.START_AUTOSAMPLE,
            ],
            AgentCapabilityType.RESOURCE_INTERFACE: None,
            AgentCapabilityType.RESOURCE_PARAMETER: self._driver_parameters.keys()
            }

        self.assert_enter_command_mode()
        self.assert_capabilities(capabilities)

        ##################
        #  Streaming Mode
        ##################

        capabilities[AgentCapabilityType.AGENT_COMMAND] = [ResourceAgentEvent.RESET, ResourceAgentEvent.GO_INACTIVE ]
        capabilities[AgentCapabilityType.RESOURCE_COMMAND] =  [
            DriverEvent.CLOCK_SYNC,
            DriverEvent.GET,
            DriverEvent.ACQUIRE_STATUS,
            DriverEvent.STOP_AUTOSAMPLE,
        ]

        self.assert_start_autosample()
        self.assert_capabilities(capabilities)
        self.assert_stop_autosample()

        #######################
        #  Uninitialized Mode
        #######################

        capabilities[AgentCapabilityType.AGENT_COMMAND] = [ResourceAgentEvent.INITIALIZE]
        capabilities[AgentCapabilityType.RESOURCE_COMMAND] = []
        capabilities[AgentCapabilityType.RESOURCE_INTERFACE] = []
        capabilities[AgentCapabilityType.RESOURCE_PARAMETER] = []

        self.assert_reset()
        self.assert_capabilities(capabilities)

    def test_execute_clock_sync(self):
        """
        Verify we can synchronize the instrument internal clock
        """
        self.assert_enter_command_mode()

        self.assert_execute_resource(ProtocolEvent.CLOCK_SYNC)
        self.assert_execute_resource(ProtocolEvent.ACQUIRE_STATUS, timeout=60)

        # Now verify that at least the date matches
        params = [InstrumentParameters.LOGGER_DATE_AND_TIME]
        reply = self.instrument_agent_client.get_resource(params)
        rcvd_time = reply[InstrumentParameters.LOGGER_DATE_AND_TIME]
        lt = time.strftime("%d %b %Y %H:%M:%S", time.gmtime(time.mktime(time.localtime())))
        self.assert_clock_set_correctly(lt, rcvd_time)

    def test_sample_autosample(self):
        self.assert_enter_command_mode()
        self.assert_start_autosample()

        self.assert_sample_async(self.assert_particle_sample, DataParticleType.SAMPLE, timeout=30, sample_count=1)
        
    def test_poll(self):
        '''
        Verify that we can poll for an engineering particle.
        '''
        self.assert_enter_command_mode()

        self.assert_particle_polled(ProtocolEvent.ACQUIRE_STATUS, self.assert_particle_engineering, DataParticleType.ENGINEERING, timeout=30)

###############################################################################
#                             PUBLICATION TESTS                               #
# Device specific pulication tests are for                                    #
# testing device specific capabilities                                        #
###############################################################################
@attr('PUB', group='mi')
class TestPublish(InstrumentDriverPublicationTestCase, UtilMixin):
    def test_granule_generation(self):
        self.assert_initialize_driver()

        # Currently these tests only verify that the data granule is generated, but the values
        # are not tested.  We will eventually need to replace log.debug with a better callback
        # function that actually tests the granule.
        self.assert_sample_async("raw data", log.debug, DataParticleType.RAW, timeout=10)

        self.assert_sample_async(self.SAMPLE, log.debug, DataParticleType.SAMPLE, timeout=10)
