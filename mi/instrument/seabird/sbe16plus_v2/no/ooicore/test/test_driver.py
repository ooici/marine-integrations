"""
@package mi.instrument.seabird.sbe16plus_v2.ooicore.test.test_driver
@file ion/services/mi/drivers/sbe16_plus_v2/test_sbe16_driver.py
@author David Everett 
@brief Test cases for InstrumentDriver

USAGE:
 Make tests verbose and provide stdout
   * From the IDK
       $ bin/test_driver
       $ bin/test_driver -u
       $ bin/test_driver -i
       $ bin/test_driver -q

"""
__author__ = 'Bill Bollenbacher'
__license__ = 'Apache 2.0'

# MI logger
import logging
from mi.core.log import get_logger ; log = get_logger()

import unittest
from nose.plugins.attrib import attr

from mi.instrument.seabird.sbe16plus_v2.test.test_driver import SBEUnitTestCase
from mi.instrument.seabird.sbe16plus_v2.test.test_driver import SBEIntTestCase
from mi.instrument.seabird.sbe16plus_v2.test.test_driver import SBEQualTestCase
from mi.instrument.seabird.sbe16plus_v2.test.test_driver import SBEPubTestCase
from mi.instrument.seabird.sbe16plus_v2.test.test_driver import VersionSpecificStructures, \
                                                                SeaBird16plusMixin

from mi.instrument.seabird.sbe16plus_v2.no.ooicore.driver import SBE16HardwareDataParticleKey, \
                                                                 SBE16NoDataParticleKey, \
                                                                 SBE16_NO_Protocol, \
                                                                 InstrumentDriver, \
                                                                 DataParticleType

from mi.instrument.seabird.sbe16plus_v2.driver import SBE16Protocol

from mi.instrument.seabird.sbe16plus_v2.driver import NEWLINE

from mi.idk.unit_test import InstrumentDriverTestCase

from mi.core.instrument.chunker import StringChunker

InstrumentDriverTestCase.initialize(
    driver_module='mi.instrument.seabird.sbe16plus_v2.no.ooicore.driver',
    driver_class="InstrumentDriver",

    instrument_agent_preload_id = 'IA5',
    instrument_agent_resource_id = '123xyz',
    instrument_agent_name = 'Agent007',
    instrument_agent_packet_config = DataParticleType()
)

###############################################################################
#                   Driver Version Specific Structures                        #
###############################################################################
###
# Test Inputs
###

VersionSpecificStructures.VALID_SAMPLE = "#03DC380A738581732F87B10012000C2B950819119C9A" + NEWLINE
VersionSpecificStructures.VALID_SAMPLE2 = "0409DB0A738C81747A84AC0006000A2E541E18BE6ED9" + NEWLINE

VersionSpecificStructures.VALID_DS_RESPONSE =  'SBE 16plus V 2.5  SERIAL NO. 6841    28 Feb 2013 16:39:31' + NEWLINE + \
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

VersionSpecificStructures.VALID_DCAL_QUARTZ = 'SBE 16plus V 2.5  SERIAL NO. 6841    28 Feb 2013 18:37:40' + NEWLINE + \
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

VersionSpecificStructures.VALID_DCAL_STRAIN ='SBE 16plus V 2.5  SERIAL NO. 6841    28 Feb 2013 18:37:40' + NEWLINE + \
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

VersionSpecificStructures.VALID_GETHD_RESPONSE =  "" + \
"<HardwareData DeviceType = 'SBE16plus' SerialNumber = '01607231'>" + NEWLINE + \
"   <Manufacturer>Sea-Bird Electronics, Inc.</Manufacturer>" + NEWLINE + \
"   <FirmwareVersion>2.5.2</FirmwareVersion>" + NEWLINE + \
"   <FirmwareDate>12 Mar 2013 11:50</FirmwareDate>" + NEWLINE + \
"   <CommandSetVersion>2.3</CommandSetVersion>" + NEWLINE + \
"   <PCBAssembly PCBSerialNum = '49577' AssemblyNum = '41054H'/>" + NEWLINE + \
"   <PCBAssembly PCBSerialNum = '46750' AssemblyNum = '41580B'/>" + NEWLINE + \
"   <PCBAssembly PCBSerialNum = '49374' AssemblyNum = '41606'/>" + NEWLINE + \
"   <PCBAssembly PCBSerialNum = '38071' AssemblyNum = '41057A'/>" + NEWLINE + \
"   <MfgDate>29-Oct-2012</MfgDate>" + NEWLINE + \
"   <InternalSensors>" + NEWLINE + \
"      <Sensor id = 'Main Temperature'>" + NEWLINE + \
"         <type>temperature0</type>" + NEWLINE + \
"         <SerialNumber>01607231</SerialNumber>" + NEWLINE + \
"      </Sensor>" + NEWLINE + \
"      <Sensor id = 'Main Conductivity'>" + NEWLINE + \
"         <type>conductivity-0</type>" + NEWLINE + \
"         <SerialNumber>01607231</SerialNumber>" + NEWLINE + \
"      </Sensor>" + NEWLINE + \
"      <Sensor id = 'Main Pressure'>" + NEWLINE + \
"         <type>quartzTC-0</type>" + NEWLINE + \
"         <SerialNumber>125270</SerialNumber>" + NEWLINE + \
"      </Sensor>" + NEWLINE + \
"   </InternalSensors>" + NEWLINE + \
"   <ExternalSensors>" + NEWLINE + \
"      <Sensor id = 'volt 0'>" + NEWLINE + \
"         <type>not assigned</type>" + NEWLINE + \
"         <SerialNumber>not assigned</SerialNumber>" + NEWLINE + \
"      </Sensor>" + NEWLINE + \
"      <Sensor id = 'volt 1'>" + NEWLINE + \
"         <type>not assigned</type>" + NEWLINE + \
"         <SerialNumber>not assigned</SerialNumber>" + NEWLINE + \
"      </Sensor>" + NEWLINE + \
"      <Sensor id = 'volt 2'>" + NEWLINE + \
"         <type>not assigned</type>" + NEWLINE + \
"         <SerialNumber>not assigned</SerialNumber>" + NEWLINE + \
"      </Sensor>" + NEWLINE + \
"      <Sensor id = 'volt 3'>" + NEWLINE + \
"         <type>not assigned</type>" + NEWLINE + \
"         <SerialNumber>not assigned</SerialNumber>" + NEWLINE + \
"      </Sensor>" + NEWLINE + \
"      <Sensor id = 'volt 4'>" + NEWLINE + \
"         <type>not assigned</type>" + NEWLINE + \
"         <SerialNumber>not assigned</SerialNumber>" + NEWLINE + \
"      </Sensor>" + NEWLINE + \
"      <Sensor id = 'volt 5'>" + NEWLINE + \
"         <type>not assigned</type>" + NEWLINE + \
"         <SerialNumber>not assigned</SerialNumber>" + NEWLINE + \
"      </Sensor>" + NEWLINE + \
"      <Sensor id = 'serial'>" + NEWLINE + \
"         <type>not assigned</type>" + NEWLINE + \
"         <SerialNumber>not assigned</SerialNumber>" + NEWLINE + \
"      </Sensor>" + NEWLINE + \
"   </ExternalSensors>" + NEWLINE + \
"</HardwareData>" + NEWLINE

SeaBird16plusMixin._hardware_parameters = {
        SBE16HardwareDataParticleKey.SERIAL_NUMBER: {SeaBird16plusMixin.TYPE: unicode, SeaBird16plusMixin.VALUE: '01607231', SeaBird16plusMixin.REQUIRED: True},
        SBE16HardwareDataParticleKey.FIRMWARE_VERSION: {SeaBird16plusMixin.TYPE: unicode, SeaBird16plusMixin.VALUE: '2.5.2', SeaBird16plusMixin.REQUIRED: True},
        SBE16HardwareDataParticleKey.FIRMWARE_DATE: {SeaBird16plusMixin.TYPE: unicode, SeaBird16plusMixin.VALUE: '12 Mar 2013 11:50', SeaBird16plusMixin.REQUIRED: True},
        SBE16HardwareDataParticleKey.COMMAND_SET_VERSION: {SeaBird16plusMixin.TYPE: unicode, SeaBird16plusMixin.VALUE: '2.3', SeaBird16plusMixin.REQUIRED: True},
        SBE16HardwareDataParticleKey.MANUFATURE_DATE: {SeaBird16plusMixin.TYPE: unicode, SeaBird16plusMixin.VALUE: '29-Oct-2012', SeaBird16plusMixin.REQUIRED: True},
        SBE16HardwareDataParticleKey.PCB_SERIAL_NUMBER: {SeaBird16plusMixin.TYPE: list, SeaBird16plusMixin.VALUE: ['49577', '46750', '49374', '38071'], SeaBird16plusMixin.REQUIRED: True},
        SBE16HardwareDataParticleKey.ASSEMBLY_NUMBER: {SeaBird16plusMixin.TYPE: list, SeaBird16plusMixin.VALUE: ['41054H', '41580B', '41606', '41057A'], SeaBird16plusMixin.REQUIRED: True},
        SBE16HardwareDataParticleKey.TEMPERATURE_SENSOR_SERIAL_NUMBER: {SeaBird16plusMixin.TYPE: unicode, SeaBird16plusMixin.VALUE: '01607231', SeaBird16plusMixin.REQUIRED: True},
        SBE16HardwareDataParticleKey.CONDUCTIVITY_SENSOR_SERIAL_NUMBER: {SeaBird16plusMixin.TYPE: unicode, SeaBird16plusMixin.VALUE: '01607231', SeaBird16plusMixin.REQUIRED: True},
        SBE16HardwareDataParticleKey.QUARTZ_PRESSURE_SENSOR_SERIAL_NUMBER: {SeaBird16plusMixin.TYPE: unicode, SeaBird16plusMixin.VALUE: '125270', SeaBird16plusMixin.REQUIRED: True},
        SBE16HardwareDataParticleKey.PRESSURE_SENSOR_TYPE: {SeaBird16plusMixin.TYPE: unicode, SeaBird16plusMixin.VALUE: 'quartzTC-0', SeaBird16plusMixin.REQUIRED: True},
    }

SeaBird16plusMixin._sample_parameters = {
        SBE16NoDataParticleKey.TEMP: {SeaBird16plusMixin.TYPE: int, SeaBird16plusMixin.VALUE: 252984, SeaBird16plusMixin.REQUIRED: True },
        SBE16NoDataParticleKey.CONDUCTIVITY: {SeaBird16plusMixin.TYPE: int, SeaBird16plusMixin.VALUE: 684933, SeaBird16plusMixin.REQUIRED: True },
        SBE16NoDataParticleKey.PRESSURE: {SeaBird16plusMixin.TYPE: int, SeaBird16plusMixin.VALUE: 8483631, SeaBird16plusMixin.REQUIRED: True },
        SBE16NoDataParticleKey.PRESSURE_TEMP: {SeaBird16plusMixin.TYPE: int, SeaBird16plusMixin.VALUE: 34737, SeaBird16plusMixin.REQUIRED: True },
        SBE16NoDataParticleKey.TIME: {SeaBird16plusMixin.TYPE: int, SeaBird16plusMixin.VALUE: 420584602, SeaBird16plusMixin.REQUIRED: True },
        SBE16NoDataParticleKey.OXY_CALPHASE: {SeaBird16plusMixin.TYPE: int, SeaBird16plusMixin.VALUE: 18, SeaBird16plusMixin.REQUIRED: True },
        SBE16NoDataParticleKey.OXYGEN: {SeaBird16plusMixin.TYPE: int, SeaBird16plusMixin.VALUE: 2856200, SeaBird16plusMixin.REQUIRED: True },
        SBE16NoDataParticleKey.OXY_TEMP: {SeaBird16plusMixin.TYPE: int, SeaBird16plusMixin.VALUE: 12, SeaBird16plusMixin.REQUIRED: True },
    }


###############################################################################
#                                UNIT TESTS                                   #
#         Unit tests test the method calls and parameters using Mock.         #
###############################################################################
@attr('UNIT', group='mi')
class UnitFromIDK(SBEUnitTestCase):
    
    def setUp(self):
        SBEUnitTestCase.setUp(self)
        if log.getEffectiveLevel() == logging.DEBUG:
            # output a newline if logging level is set to debug so the stupid output from startTest() in
            # /Library/Frameworks/Python.framework/Versions/2.7/lib/python2.7/unittest/runtest.py
            # doesn't mess up the logging output alignment
            print("")

    def assert_particle_hardware(self, data_particle, verify_values = False):
        '''
        Verify hardware particle
        @param data_particle:  SBE16HardwareDataParticle data particle
        @param verify_values:  bool, should we verify parameter values
        '''
        self.assert_data_particle_keys(SBE16HardwareDataParticleKey, self._hardware_parameters)
        self.assert_data_particle_header(data_particle, DataParticleType.DEVICE_HARDWARE)
        self.assert_data_particle_parameters(data_particle, self._hardware_parameters, verify_values)

    def assert_particle_sample(self, data_particle, verify_values = False):
        '''
        Verify sample particle
        @param data_particle:  SBE16DataParticle data particle
        @param verify_values:  bool, should we verify parameter values
        '''
        self.assert_data_particle_keys(SBE16NoDataParticleKey, self._sample_parameters)
        self.assert_data_particle_header(data_particle, DataParticleType.CTD_PARSED, require_instrument_timestamp=True)
        self.assert_data_particle_parameters(data_particle, self._sample_parameters, verify_values)

    def test_chunker(self):
        """
        Test the chunker for NO version and verify the particles created.
        """
        chunker = StringChunker(SBE16_NO_Protocol.sieve_function)

        self.assert_chunker_sample(chunker, self.VALID_SAMPLE)
        self.assert_chunker_sample_with_noise(chunker, self.VALID_SAMPLE)
        self.assert_chunker_fragmented_sample(chunker, self.VALID_SAMPLE)
        self.assert_chunker_combined_sample(chunker, self.VALID_SAMPLE)

        self.assert_chunker_sample(chunker, self.VALID_GETHD_RESPONSE)
        self.assert_chunker_sample_with_noise(chunker, self.VALID_GETHD_RESPONSE)
        self.assert_chunker_fragmented_sample(chunker, self.VALID_GETHD_RESPONSE)
        self.assert_chunker_combined_sample(chunker, self.VALID_GETHD_RESPONSE)

    def test_got_data(self):
        """
        Verify sample data passed through the got data method produces the correct data particles for NO version 
        """
        # Create and initialize the instrument driver with a mock port agent
        driver = InstrumentDriver(self._got_data_event_callback)
        self.assert_initialize_driver(driver)

        # Start validating data particles
        self.assert_particle_published(driver, self.VALID_GETHD_RESPONSE, self.assert_particle_hardware, True)
        self.assert_particle_published(driver, self.VALID_SAMPLE, self.assert_particle_sample, True)
        

###############################################################################
#                            INTEGRATION TESTS                                #
#     Integration test test the direct driver / instrument interaction        #
#     but making direct calls via zeromq.                                     #
#     - Common Integration tests test the driver through the instrument agent #
#     and common for all drivers (minimum requirement for ION ingestion)      #
###############################################################################
@attr('INT', group='mi')
class IntFromIDK(SBEIntTestCase):
    pass


###############################################################################
#                            QUALIFICATION TESTS                              #
# Device specific qualification tests are for                                 #
# testing device specific capabilities                                        #
###############################################################################
@attr('QUAL', group='mi')
class QualFromIDK(SBEQualTestCase):
    pass


###############################################################################
#                             PUBLICATION TESTS                               #
# Device specific publication tests are for                                   #
# testing device specific capabilities                                        #
###############################################################################
@attr('PUB', group='mi')
class PubFromIDK(SBEPubTestCase):
    pass
