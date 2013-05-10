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
from mi.instrument.seabird.sbe16plus_v2.test.test_driver import SeaBird16plusMixin

from mi.instrument.seabird.sbe16plus_v2.bep.driver import SBE16HardwareDataParticleKey, \
                                                          SBE16CalibrationDataParticleKey, \
                                                          SBE16NoDataParticleKey, \
                                                          SBE16StatusDataParticleKey, \
                                                          SBE16ConfigurationDataParticleKey, \
                                                          SBE16_NO_Protocol, \
                                                          InstrumentDriver, \
                                                          DataParticleType, \
                                                          InstrumentDriver

from mi.instrument.seabird.sbe16plus_v2.driver import ProtocolEvent, \
                                                      Parameter, \
                                                      ProtocolState, \
                                                      NEWLINE
                                                      

from mi.idk.unit_test import InstrumentDriverTestCase

from mi.core.instrument.chunker import StringChunker

InstrumentDriverTestCase.initialize(
    driver_module='mi.instrument.seabird.sbe16plus_v2.bep.driver',
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

SeaBird16plusMixin.InstrumentDriver = InstrumentDriver

SeaBird16plusMixin.VALID_SAMPLE = "#03DC380A738581732F87B10012000C2B950819119C9A" + NEWLINE
SeaBird16plusMixin.VALID_SAMPLE2 = "0409DB0A738C81747A84AC0006000A2E541E18BE6ED9" + NEWLINE

SeaBird16plusMixin.VALID_DS_RESPONSE =  'SBE 16plus V 2.5  SERIAL NO. 6841    28 Feb 2013 16:39:31' + NEWLINE + \
    'vbatt = 23.4, vlith =  8.0, ioper =  61.4 ma, ipump =   0.3 ma,' + NEWLINE + \
    'status = not logging' + NEWLINE + \
    'samples = 0, free = 4386542' + NEWLINE + \
    'sample interval = 10 seconds, number of measurements per sample = 4' + NEWLINE + \
    'Paros integration time = 1.0 seconds' + NEWLINE + \
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

SeaBird16plusMixin.VALID_GETHD_RESPONSE =  "" + \
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

SeaBird16plusMixin.VALID_GETCC_RESPONSE =  "" + \
"<CalibrationCoefficients DeviceType = 'SBE16plus' SerialNumber = '01607231'>" + NEWLINE + \
"   <Calibration format = 'TEMP1' id = 'Main Temperature'>" + NEWLINE + \
"      <SerialNum>01607231</SerialNum>" + NEWLINE + \
"      <CalDate>07-Nov-12</CalDate>" + NEWLINE + \
"      <TA0>1.254755e-03</TA0>" + NEWLINE + \
"      <TA1>2.758871e-04</TA1>" + NEWLINE + \
"      <TA2>-1.368268e-06</TA2>" + NEWLINE + \
"      <TA3>1.910795e-07</TA3>" + NEWLINE + \
"      <TOFFSET>0.000000e+00</TOFFSET>" + NEWLINE + \
"   </Calibration>" + NEWLINE + \
"   <Calibration format = 'WBCOND0' id = 'Main Conductivity'>" + NEWLINE + \
"      <SerialNum>01607231</SerialNum>" + NEWLINE + \
"      <CalDate>07-Nov-12</CalDate>" + NEWLINE + \
"      <G>-9.761799e-01</G>" + NEWLINE + \
"      <H>1.369994e-01</H>" + NEWLINE + \
"      <I>-3.523860e-04</I>" + NEWLINE + \
"      <J>4.404252e-05</J>" + NEWLINE + \
"      <CPCOR>-9.570000e-08</CPCOR>" + NEWLINE + \
"      <CTCOR>3.250000e-06</CTCOR>" + NEWLINE + \
"      <CSLOPE>1.000000e+00</CSLOPE>" + NEWLINE + \
"   </Calibration>" + NEWLINE + \
"   <Calibration format = 'QUARTZ0' id = 'Main Pressure'>" + NEWLINE + \
"      <SerialNum>125270</SerialNum>" + NEWLINE + \
"      <CalDate>02-nov-12</CalDate>" + NEWLINE + \
"      <PC1>-4.642673e+03</PC1>" + NEWLINE + \
"      <PC2>-4.611640e-03</PC2>" + NEWLINE + \
"      <PC3>8.921190e-04</PC3>" + NEWLINE + \
"      <PD1>7.024800e-02</PD1>" + NEWLINE + \
"      <PD2>0.000000e+00</PD2>" + NEWLINE + \
"      <PT1>3.022595e+01</PT1>" + NEWLINE + \
"      <PT2>-1.549720e-04</PT2>" + NEWLINE + \
"      <PT3>2.677750e-06</PT3>" + NEWLINE + \
"      <PT4>1.705490e-09</PT4>" + NEWLINE + \
"      <PSLOPE>1.000000e+00</PSLOPE>" + NEWLINE + \
"      <POFFSET>0.000000e+00</POFFSET>" + NEWLINE + \
"      <PRANGE>1.000000e+03</PRANGE>" + NEWLINE + \
"   </Calibration>" + NEWLINE + \
"   <Calibration format = 'VOLT0' id = 'Volt 0'>" + NEWLINE + \
"      <OFFSET>-4.650526e-02</OFFSET>" + NEWLINE + \
"      <SLOPE>1.246381e+00</SLOPE>" + NEWLINE + \
"   </Calibration>" + NEWLINE + \
"   <Calibration format = 'VOLT0' id = 'Volt 1'>" + NEWLINE + \
"      <OFFSET>-4.618105e-02</OFFSET>" + NEWLINE + \
"      <SLOPE>1.247197e+00</SLOPE>" + NEWLINE + \
"   </Calibration>" + NEWLINE + \
"   <Calibration format = 'VOLT0' id = 'Volt 2'>" + NEWLINE + \
"      <OFFSET>-4.659790e-02</OFFSET>" + NEWLINE + \
"      <SLOPE>1.247601e+00</SLOPE>" + NEWLINE + \
"   </Calibration>" + NEWLINE + \
"   <Calibration format = 'VOLT0' id = 'Volt 3'>" + NEWLINE + \
"      <OFFSET>-4.502421e-02</OFFSET>" + NEWLINE + \
"      <SLOPE>1.246911e+00</SLOPE>" + NEWLINE + \
"   </Calibration>" + NEWLINE + \
"   <Calibration format = 'VOLT0' id = 'Volt 4'>" + NEWLINE + \
"      <OFFSET>-4.589158e-02</OFFSET>" + NEWLINE + \
"      <SLOPE>1.246346e+00</SLOPE>" + NEWLINE + \
"   </Calibration>" + NEWLINE + \
"   <Calibration format = 'VOLT0' id = 'Volt 5'>" + NEWLINE + \
"      <OFFSET>-4.609895e-02</OFFSET>" + NEWLINE + \
"      <SLOPE>1.247868e+00</SLOPE>" + NEWLINE + \
"   </Calibration>" + NEWLINE + \
"   <Calibration format = 'FREQ0' id = 'external frequency channel'>" + NEWLINE + \
"      <EXTFREQSF>9.999949e-01</EXTFREQSF>" + NEWLINE + \
"   </Calibration>" + NEWLINE + \
"</CalibrationCoefficients>" + NEWLINE

SeaBird16plusMixin.VALID_GETSD_RESPONSE =  "" + \
"<StatusData DeviceType = 'SBE16plus' SerialNumber = '01607231'>" + NEWLINE + \
"   <DateTime>2013-04-26T22:20:21</DateTime>" + NEWLINE + \
"   <LoggingState>not logging</LoggingState>" + NEWLINE + \
"   <EventSummary numEvents = '317'/>" + NEWLINE + \
"   <Power>" + NEWLINE + \
"      <vMain>13.0</vMain>" + NEWLINE + \
"      <vLith>8.6</vLith>" + NEWLINE + \
"      <iMain>51.1</iMain>" + NEWLINE + \
"      <iPump> 0.5</iPump>" + NEWLINE + \
"      <iExt01> 0.5</iExt01>" + NEWLINE + \
"      <iSerial>45.1</iSerial>" + NEWLINE + \
"   </Power>" + NEWLINE + \
"   <MemorySummary>" + NEWLINE + \
"      <Bytes>330</Bytes>" + NEWLINE + \
"      <Samples>15</Samples>" + NEWLINE + \
"      <SamplesFree>2990809</SamplesFree>" + NEWLINE + \
"      <SampleLength>22</SampleLength>" + NEWLINE + \
"      <Headers>3</Headers>" + NEWLINE + \
"   </MemorySummary>" + NEWLINE + \
"</StatusData>" + NEWLINE

SeaBird16plusMixin.VALID_GETCD_RESPONSE =  "" + \
"<ConfigurationData DeviceType = 'SBE16plus' SerialNumber = '01607231'>" + NEWLINE + \
"   <SamplingParameters>" + NEWLINE + \
"      <SampleInterval>10</SampleInterval>" + NEWLINE + \
"      <MeasurementsPerSample>4</MeasurementsPerSample>" + NEWLINE + \
"      <ParosIntegrationTime>1.0</ParosIntegrationTime>" + NEWLINE + \
"      <Pump>run pump during sample</Pump>" + NEWLINE + \
"      <DelayBeforeSampling>0.0</DelayBeforeSampling>" + NEWLINE + \
"      <DelayAfterSampling>0.0</DelayAfterSampling>" + NEWLINE + \
"      <TransmitRealTime>yes</TransmitRealTime>" + NEWLINE + \
"   </SamplingParameters>" + NEWLINE + \
"   <Battery>" + NEWLINE + \
"      <CutOff>7.5</CutOff>" + NEWLINE + \
"   </Battery>" + NEWLINE + \
"   <DataChannels>" + NEWLINE + \
"      <ExtVolt0>yes</ExtVolt0>" + NEWLINE + \
"      <ExtVolt1>yes</ExtVolt1>" + NEWLINE + \
"      <ExtVolt2>no</ExtVolt2>" + NEWLINE + \
"      <ExtVolt3>no</ExtVolt3>" + NEWLINE + \
"      <ExtVolt4>no</ExtVolt4>" + NEWLINE + \
"      <ExtVolt5>no</ExtVolt5>" + NEWLINE + \
"      <SBE38>no</SBE38>" + NEWLINE + \
"      <SBE50>no</SBE50>" + NEWLINE + \
"      <WETLABS>no</WETLABS>" + NEWLINE + \
"      <OPTODE>yes</OPTODE>" + NEWLINE + \
"      <SBE63>no</SBE63>" + NEWLINE + \
"      <GTD>no</GTD>" + NEWLINE + \
"   </DataChannels>" + NEWLINE + \
"   <EchoCharacters>yes</EchoCharacters>" + NEWLINE + \
"   <OutputExecutedTag>yes</OutputExecutedTag>" + NEWLINE + \
"   <OutputFormat>raw decimal</OutputFormat>" + NEWLINE + \
"   <SerialLineSync>no</SerialLineSync>" + NEWLINE + \
"</ConfigurationData>" + NEWLINE

SeaBird16plusMixin._driver_parameters[Parameter.PAROS_INTEGRATION] = {SeaBird16plusMixin.TYPE: float, SeaBird16plusMixin.READONLY: True, SeaBird16plusMixin.DA: True, SeaBird16plusMixin.STARTUP: True, SeaBird16plusMixin.DEFAULT: 1.0, SeaBird16plusMixin.VALUE: 1.0}

SeaBird16plusMixin._configuration_parameters = {
        SBE16ConfigurationDataParticleKey.SERIAL_NUMBER: {SeaBird16plusMixin.TYPE: int, SeaBird16plusMixin.VALUE: 1607231, SeaBird16plusMixin.REQUIRED: True},
        SBE16ConfigurationDataParticleKey.SAMPLE_INTERVAL: {SeaBird16plusMixin.TYPE: int, SeaBird16plusMixin.VALUE: 10, SeaBird16plusMixin.REQUIRED: True},
        SBE16ConfigurationDataParticleKey.MEASUREMENTS_PER_SAMPLE: {SeaBird16plusMixin.TYPE: int, SeaBird16plusMixin.VALUE: 4, SeaBird16plusMixin.REQUIRED: True},
        SBE16ConfigurationDataParticleKey.PAROS_INTEGRATION_TIME: {SeaBird16plusMixin.TYPE: float, SeaBird16plusMixin.VALUE: 1.0, SeaBird16plusMixin.REQUIRED: True},
        SBE16ConfigurationDataParticleKey.PUMP_MODE: {SeaBird16plusMixin.TYPE: unicode, SeaBird16plusMixin.VALUE: "run pump during sample", SeaBird16plusMixin.REQUIRED: True},
        SBE16ConfigurationDataParticleKey.DELAY_BEFORE_SAMPLING: {SeaBird16plusMixin.TYPE: float, SeaBird16plusMixin.VALUE: 0.0, SeaBird16plusMixin.REQUIRED: True},
        SBE16ConfigurationDataParticleKey.DELAY_AFTER_SAMPLING: {SeaBird16plusMixin.TYPE: float, SeaBird16plusMixin.VALUE: 0.0, SeaBird16plusMixin.REQUIRED: True},
        SBE16ConfigurationDataParticleKey.TRANSMIT_REAL_TIME: {SeaBird16plusMixin.TYPE: bool, SeaBird16plusMixin.VALUE: True, SeaBird16plusMixin.REQUIRED: True},
        SBE16ConfigurationDataParticleKey.BATTERY_CUTOFF: {SeaBird16plusMixin.TYPE: float, SeaBird16plusMixin.VALUE: 7.5, SeaBird16plusMixin.REQUIRED: True},
        SBE16ConfigurationDataParticleKey.EXT_VOLT_0: {SeaBird16plusMixin.TYPE: bool, SeaBird16plusMixin.VALUE: True, SeaBird16plusMixin.REQUIRED: True},
        SBE16ConfigurationDataParticleKey.EXT_VOLT_1: {SeaBird16plusMixin.TYPE: bool, SeaBird16plusMixin.VALUE: True, SeaBird16plusMixin.REQUIRED: True},
        SBE16ConfigurationDataParticleKey.EXT_VOLT_2: {SeaBird16plusMixin.TYPE: bool, SeaBird16plusMixin.VALUE: False, SeaBird16plusMixin.REQUIRED: True},
        SBE16ConfigurationDataParticleKey.EXT_VOLT_3: {SeaBird16plusMixin.TYPE: bool, SeaBird16plusMixin.VALUE: False, SeaBird16plusMixin.REQUIRED: True},
        SBE16ConfigurationDataParticleKey.EXT_VOLT_4: {SeaBird16plusMixin.TYPE: bool, SeaBird16plusMixin.VALUE: False, SeaBird16plusMixin.REQUIRED: True},
        SBE16ConfigurationDataParticleKey.EXT_VOLT_5: {SeaBird16plusMixin.TYPE: bool, SeaBird16plusMixin.VALUE: False, SeaBird16plusMixin.REQUIRED: True},
        SBE16ConfigurationDataParticleKey.SBE38: {SeaBird16plusMixin.TYPE: bool, SeaBird16plusMixin.VALUE: False, SeaBird16plusMixin.REQUIRED: True},
        SBE16ConfigurationDataParticleKey.SBE50: {SeaBird16plusMixin.TYPE: bool, SeaBird16plusMixin.VALUE: False, SeaBird16plusMixin.REQUIRED: True},
        SBE16ConfigurationDataParticleKey.WETLABS: {SeaBird16plusMixin.TYPE: bool, SeaBird16plusMixin.VALUE: False, SeaBird16plusMixin.REQUIRED: True},
        SBE16ConfigurationDataParticleKey.OPTODE: {SeaBird16plusMixin.TYPE: bool, SeaBird16plusMixin.VALUE: True, SeaBird16plusMixin.REQUIRED: True},
        SBE16ConfigurationDataParticleKey.GAS_TENSION_DEVICE: {SeaBird16plusMixin.TYPE: bool, SeaBird16plusMixin.VALUE: False, SeaBird16plusMixin.REQUIRED: True},
        SBE16ConfigurationDataParticleKey.ECHO_CHARACTERS: {SeaBird16plusMixin.TYPE: bool, SeaBird16plusMixin.VALUE: True, SeaBird16plusMixin.REQUIRED: True},
        SBE16ConfigurationDataParticleKey.OUTPUT_EXECUTED_TAG: {SeaBird16plusMixin.TYPE: bool, SeaBird16plusMixin.VALUE: True, SeaBird16plusMixin.REQUIRED: True},
        SBE16ConfigurationDataParticleKey.OUTPUT_FORMAT: {SeaBird16plusMixin.TYPE: unicode, SeaBird16plusMixin.VALUE: "raw decimal", SeaBird16plusMixin.REQUIRED: True},
        SBE16ConfigurationDataParticleKey.SERIAL_SYNC_MODE: {SeaBird16plusMixin.TYPE: bool, SeaBird16plusMixin.VALUE: False, SeaBird16plusMixin.REQUIRED: True},
    }

SeaBird16plusMixin._status_parameters = {
        SBE16StatusDataParticleKey.SERIAL_NUMBER: {SeaBird16plusMixin.TYPE: int, SeaBird16plusMixin.VALUE: 1607231, SeaBird16plusMixin.REQUIRED: True},
        SBE16StatusDataParticleKey.DATE_TIME: {SeaBird16plusMixin.TYPE: unicode, SeaBird16plusMixin.VALUE: "2013-04-26T22:20:21", SeaBird16plusMixin.REQUIRED: True},
        SBE16StatusDataParticleKey.LOGGING_STATUS: {SeaBird16plusMixin.TYPE: unicode, SeaBird16plusMixin.VALUE: "not logging", SeaBird16plusMixin.REQUIRED: True},
        SBE16StatusDataParticleKey.NUMBER_OF_EVENTS: {SeaBird16plusMixin.TYPE: int, SeaBird16plusMixin.VALUE: 317, SeaBird16plusMixin.REQUIRED: True},
        SBE16StatusDataParticleKey.BATTERY_VOLTAGE_MAIN: {SeaBird16plusMixin.TYPE: float, SeaBird16plusMixin.VALUE: 13.0, SeaBird16plusMixin.REQUIRED: True},
        SBE16StatusDataParticleKey.BATTERY_VOLTAGE_LITHIUM: {SeaBird16plusMixin.TYPE: float, SeaBird16plusMixin.VALUE: 8.6, SeaBird16plusMixin.REQUIRED: True},
        SBE16StatusDataParticleKey.OPERATIONAL_CURRENT: {SeaBird16plusMixin.TYPE: float, SeaBird16plusMixin.VALUE: 51.1, SeaBird16plusMixin.REQUIRED: True},
        SBE16StatusDataParticleKey.PUMP_CURRENT: {SeaBird16plusMixin.TYPE: float, SeaBird16plusMixin.VALUE: 0.5, SeaBird16plusMixin.REQUIRED: True},
        SBE16StatusDataParticleKey.EXT_V01_CURRENT: {SeaBird16plusMixin.TYPE: float, SeaBird16plusMixin.VALUE: 0.5, SeaBird16plusMixin.REQUIRED: True},
        SBE16StatusDataParticleKey.SERIAL_CURRENT: {SeaBird16plusMixin.TYPE: float, SeaBird16plusMixin.VALUE: 45.1, SeaBird16plusMixin.REQUIRED: True},
        SBE16StatusDataParticleKey.MEMMORY_FREE: {SeaBird16plusMixin.TYPE: int, SeaBird16plusMixin.VALUE: 330, SeaBird16plusMixin.REQUIRED: True},
        SBE16StatusDataParticleKey.NUMBER_OF_SAMPLES: {SeaBird16plusMixin.TYPE: int, SeaBird16plusMixin.VALUE: 15, SeaBird16plusMixin.REQUIRED: True},
        SBE16StatusDataParticleKey.SAMPLES_FREE: {SeaBird16plusMixin.TYPE: int, SeaBird16plusMixin.VALUE: 2990809, SeaBird16plusMixin.REQUIRED: True},
        SBE16StatusDataParticleKey.SAMPLE_LENGTH: {SeaBird16plusMixin.TYPE: int, SeaBird16plusMixin.VALUE: 22, SeaBird16plusMixin.REQUIRED: True},
        SBE16StatusDataParticleKey.HEADERS: {SeaBird16plusMixin.TYPE: int, SeaBird16plusMixin.VALUE: 3, SeaBird16plusMixin.REQUIRED: True},
    }

SeaBird16plusMixin._hardware_parameters = {
        SBE16HardwareDataParticleKey.SERIAL_NUMBER: {SeaBird16plusMixin.TYPE: int, SeaBird16plusMixin.VALUE: 1607231, SeaBird16plusMixin.REQUIRED: True},
        SBE16HardwareDataParticleKey.FIRMWARE_VERSION: {SeaBird16plusMixin.TYPE: unicode, SeaBird16plusMixin.VALUE: '2.5.2', SeaBird16plusMixin.REQUIRED: True},
        SBE16HardwareDataParticleKey.FIRMWARE_DATE: {SeaBird16plusMixin.TYPE: unicode, SeaBird16plusMixin.VALUE: '12 Mar 2013 11:50', SeaBird16plusMixin.REQUIRED: True},
        SBE16HardwareDataParticleKey.COMMAND_SET_VERSION: {SeaBird16plusMixin.TYPE: unicode, SeaBird16plusMixin.VALUE: '2.3', SeaBird16plusMixin.REQUIRED: True},
        SBE16HardwareDataParticleKey.MANUFATURE_DATE: {SeaBird16plusMixin.TYPE: unicode, SeaBird16plusMixin.VALUE: '29-Oct-2012', SeaBird16plusMixin.REQUIRED: True},
        SBE16HardwareDataParticleKey.PCB_SERIAL_NUMBER: {SeaBird16plusMixin.TYPE: list, SeaBird16plusMixin.VALUE: ['49577', '46750', '49374', '38071'], SeaBird16plusMixin.REQUIRED: True},
        SBE16HardwareDataParticleKey.ASSEMBLY_NUMBER: {SeaBird16plusMixin.TYPE: list, SeaBird16plusMixin.VALUE: ['41054H', '41580B', '41606', '41057A'], SeaBird16plusMixin.REQUIRED: True},
        SBE16HardwareDataParticleKey.TEMPERATURE_SENSOR_SERIAL_NUMBER: {SeaBird16plusMixin.TYPE: int, SeaBird16plusMixin.VALUE: 1607231, SeaBird16plusMixin.REQUIRED: True},
        SBE16HardwareDataParticleKey.CONDUCTIVITY_SENSOR_SERIAL_NUMBER: {SeaBird16plusMixin.TYPE: int, SeaBird16plusMixin.VALUE: 1607231, SeaBird16plusMixin.REQUIRED: True},
        SBE16HardwareDataParticleKey.QUARTZ_PRESSURE_SENSOR_SERIAL_NUMBER: {SeaBird16plusMixin.TYPE: int, SeaBird16plusMixin.VALUE: 125270, SeaBird16plusMixin.REQUIRED: True},
        SBE16HardwareDataParticleKey.PRESSURE_SENSOR_TYPE: {SeaBird16plusMixin.TYPE: unicode, SeaBird16plusMixin.VALUE: 'quartzTC-0', SeaBird16plusMixin.REQUIRED: True},
    }

SeaBird16plusMixin._calibration_parameters = {
        SBE16CalibrationDataParticleKey.SERIAL_NUMBER: {SeaBird16plusMixin.TYPE: int, SeaBird16plusMixin.VALUE: 1607231, SeaBird16plusMixin.REQUIRED: True},
        SBE16CalibrationDataParticleKey.TEMP_SENSOR_SERIAL_NUMBER: {SeaBird16plusMixin.TYPE: int, SeaBird16plusMixin.VALUE: 1607231, SeaBird16plusMixin.REQUIRED: True },
        SBE16CalibrationDataParticleKey.TEMP_CAL_DATE: {SeaBird16plusMixin.TYPE: unicode, SeaBird16plusMixin.VALUE: "07-Nov-12", SeaBird16plusMixin.REQUIRED: True},
        SBE16CalibrationDataParticleKey.TA0: {SeaBird16plusMixin.TYPE: float, SeaBird16plusMixin.VALUE: 1.254755e-03, SeaBird16plusMixin.REQUIRED: True},
        SBE16CalibrationDataParticleKey.TA1: {SeaBird16plusMixin.TYPE: float, SeaBird16plusMixin.VALUE: 2.758871e-04, SeaBird16plusMixin.REQUIRED: True},
        SBE16CalibrationDataParticleKey.TA2: {SeaBird16plusMixin.TYPE: float, SeaBird16plusMixin.VALUE: -1.368268e-06, SeaBird16plusMixin.REQUIRED: True},
        SBE16CalibrationDataParticleKey.TA3: {SeaBird16plusMixin.TYPE: float, SeaBird16plusMixin.VALUE: 1.910795e-07, SeaBird16plusMixin.REQUIRED: True},
        SBE16CalibrationDataParticleKey.TOFFSET: {SeaBird16plusMixin.TYPE: float, SeaBird16plusMixin.VALUE: 0.0, SeaBird16plusMixin.REQUIRED: True},
        SBE16CalibrationDataParticleKey.COND_SENSOR_SERIAL_NUMBER: {SeaBird16plusMixin.TYPE: int, SeaBird16plusMixin.VALUE: 1607231, SeaBird16plusMixin.REQUIRED: True },
        SBE16CalibrationDataParticleKey.COND_CAL_DATE: {SeaBird16plusMixin.TYPE: unicode, SeaBird16plusMixin.VALUE: '07-Nov-12', SeaBird16plusMixin.REQUIRED: True},
        SBE16CalibrationDataParticleKey.CONDG: {SeaBird16plusMixin.TYPE: float, SeaBird16plusMixin.VALUE: -9.761799e-01, SeaBird16plusMixin.REQUIRED: True},
        SBE16CalibrationDataParticleKey.CONDH: {SeaBird16plusMixin.TYPE: float, SeaBird16plusMixin.VALUE: 1.369994e-01, SeaBird16plusMixin.REQUIRED: True},
        SBE16CalibrationDataParticleKey.CONDI: {SeaBird16plusMixin.TYPE: float, SeaBird16plusMixin.VALUE: -3.523860e-04, SeaBird16plusMixin.REQUIRED: True},
        SBE16CalibrationDataParticleKey.CONDJ: {SeaBird16plusMixin.TYPE: float, SeaBird16plusMixin.VALUE: 4.404252e-05, SeaBird16plusMixin.REQUIRED: True},
        SBE16CalibrationDataParticleKey.CPCOR: {SeaBird16plusMixin.TYPE: float, SeaBird16plusMixin.VALUE: -9.570000e-08, SeaBird16plusMixin.REQUIRED: True},
        SBE16CalibrationDataParticleKey.CTCOR: {SeaBird16plusMixin.TYPE: float, SeaBird16plusMixin.VALUE: 3.250000e-06, SeaBird16plusMixin.REQUIRED: True},
        SBE16CalibrationDataParticleKey.CSLOPE: {SeaBird16plusMixin.TYPE: float, SeaBird16plusMixin.VALUE: 1.0, SeaBird16plusMixin.REQUIRED: True},
        SBE16CalibrationDataParticleKey.PRES_SERIAL_NUMBER: {SeaBird16plusMixin.TYPE: int, SeaBird16plusMixin.VALUE: 125270, SeaBird16plusMixin.REQUIRED: True },
        SBE16CalibrationDataParticleKey.PRES_CAL_DATE: {SeaBird16plusMixin.TYPE: unicode, SeaBird16plusMixin.VALUE: '02-nov-12', SeaBird16plusMixin.REQUIRED: True },
        SBE16CalibrationDataParticleKey.PC1: {SeaBird16plusMixin.TYPE: float, SeaBird16plusMixin.VALUE: -4.642673e+03, SeaBird16plusMixin.REQUIRED: True },
        SBE16CalibrationDataParticleKey.PC2: {SeaBird16plusMixin.TYPE: float, SeaBird16plusMixin.VALUE: -4.611640e-03, SeaBird16plusMixin.REQUIRED: True },
        SBE16CalibrationDataParticleKey.PC3: {SeaBird16plusMixin.TYPE: float, SeaBird16plusMixin.VALUE: 8.921190e-04, SeaBird16plusMixin.REQUIRED: True },
        SBE16CalibrationDataParticleKey.PD1: {SeaBird16plusMixin.TYPE: float, SeaBird16plusMixin.VALUE: 7.024800e-02, SeaBird16plusMixin.REQUIRED: True },
        SBE16CalibrationDataParticleKey.PD2: {SeaBird16plusMixin.TYPE: float, SeaBird16plusMixin.VALUE: 0.000000e+00, SeaBird16plusMixin.REQUIRED: True },
        SBE16CalibrationDataParticleKey.PT1: {SeaBird16plusMixin.TYPE: float, SeaBird16plusMixin.VALUE: 3.022595e+01, SeaBird16plusMixin.REQUIRED: True },
        SBE16CalibrationDataParticleKey.PT2: {SeaBird16plusMixin.TYPE: float, SeaBird16plusMixin.VALUE: -1.549720e-04, SeaBird16plusMixin.REQUIRED: True },
        SBE16CalibrationDataParticleKey.PT3: {SeaBird16plusMixin.TYPE: float, SeaBird16plusMixin.VALUE: 2.677750e-06, SeaBird16plusMixin.REQUIRED: True },
        SBE16CalibrationDataParticleKey.PT4: {SeaBird16plusMixin.TYPE: float, SeaBird16plusMixin.VALUE: 1.705490e-09, SeaBird16plusMixin.REQUIRED: True },
        SBE16CalibrationDataParticleKey.PSLOPE: {SeaBird16plusMixin.TYPE: float, SeaBird16plusMixin.VALUE: 1.000000e+00, SeaBird16plusMixin.REQUIRED: True },
        SBE16CalibrationDataParticleKey.POFFSET: {SeaBird16plusMixin.TYPE: float, SeaBird16plusMixin.VALUE: 0.000000e+00, SeaBird16plusMixin.REQUIRED: True },
        SBE16CalibrationDataParticleKey.PRES_RANGE: {SeaBird16plusMixin.TYPE: int, SeaBird16plusMixin.VALUE: 1000, SeaBird16plusMixin.REQUIRED: True },
        SBE16CalibrationDataParticleKey.EXT_VOLT0_OFFSET: {SeaBird16plusMixin.TYPE: float, SeaBird16plusMixin.VALUE: -4.650526e-02, SeaBird16plusMixin.REQUIRED: True},
        SBE16CalibrationDataParticleKey.EXT_VOLT0_SLOPE: {SeaBird16plusMixin.TYPE: float, SeaBird16plusMixin.VALUE: 1.246381e+00, SeaBird16plusMixin.REQUIRED: True},
        SBE16CalibrationDataParticleKey.EXT_VOLT1_OFFSET: {SeaBird16plusMixin.TYPE: float, SeaBird16plusMixin.VALUE: -4.618105e-02, SeaBird16plusMixin.REQUIRED: True},
        SBE16CalibrationDataParticleKey.EXT_VOLT1_SLOPE: {SeaBird16plusMixin.TYPE: float, SeaBird16plusMixin.VALUE: 1.247197e+00, SeaBird16plusMixin.REQUIRED: True},
        SBE16CalibrationDataParticleKey.EXT_VOLT2_OFFSET: {SeaBird16plusMixin.TYPE: float, SeaBird16plusMixin.VALUE: -4.659790e-02, SeaBird16plusMixin.REQUIRED: True},
        SBE16CalibrationDataParticleKey.EXT_VOLT2_SLOPE: {SeaBird16plusMixin.TYPE: float, SeaBird16plusMixin.VALUE: 1.247601e+00, SeaBird16plusMixin.REQUIRED: True},
        SBE16CalibrationDataParticleKey.EXT_VOLT3_OFFSET: {SeaBird16plusMixin.TYPE: float, SeaBird16plusMixin.VALUE: -4.502421e-02, SeaBird16plusMixin.REQUIRED: True},
        SBE16CalibrationDataParticleKey.EXT_VOLT3_SLOPE: {SeaBird16plusMixin.TYPE: float, SeaBird16plusMixin.VALUE: 1.246911e+00, SeaBird16plusMixin.REQUIRED: True},
        SBE16CalibrationDataParticleKey.EXT_VOLT4_OFFSET: {SeaBird16plusMixin.TYPE: float, SeaBird16plusMixin.VALUE: -4.589158e-02, SeaBird16plusMixin.REQUIRED: True},
        SBE16CalibrationDataParticleKey.EXT_VOLT4_SLOPE: {SeaBird16plusMixin.TYPE: float, SeaBird16plusMixin.VALUE: 1.246346e+00, SeaBird16plusMixin.REQUIRED: True},
        SBE16CalibrationDataParticleKey.EXT_VOLT5_OFFSET: {SeaBird16plusMixin.TYPE: float, SeaBird16plusMixin.VALUE: -4.609895e-02, SeaBird16plusMixin.REQUIRED: True},
        SBE16CalibrationDataParticleKey.EXT_VOLT5_SLOPE: {SeaBird16plusMixin.TYPE: float, SeaBird16plusMixin.VALUE: 1.247868e+00, SeaBird16plusMixin.REQUIRED: True},
        SBE16CalibrationDataParticleKey.EXT_FREQ: {SeaBird16plusMixin.TYPE: float, SeaBird16plusMixin.VALUE: 9.999949e-01, SeaBird16plusMixin.REQUIRED: True},
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

def assert_particle_calibration(self, data_particle, verify_values = False):
    '''
    Verify sample particle
    @param data_particle:  SBE16CalibrationDataParticle calibration particle
    @param verify_values:  bool, should we verify parameter values
    '''
    self.assert_data_particle_keys(SBE16CalibrationDataParticleKey, self._calibration_parameters)
    self.assert_data_particle_header(data_particle, DataParticleType.DEVICE_CALIBRATION)
    self.assert_data_particle_parameters(data_particle, self._calibration_parameters, verify_values)

def assert_particle_status(self, data_particle, verify_values = False):
    '''
    Verify status particle
    @param data_particle:  SBE16StatusDataParticle status particle
    @param verify_values:  bool, should we verify parameter values
    '''
    self.assert_data_particle_keys(SBE16StatusDataParticleKey, self._status_parameters)
    self.assert_data_particle_header(data_particle, DataParticleType.DEVICE_STATUS)
    self.assert_data_particle_parameters(data_particle, self._status_parameters, verify_values)

def assert_particle_configuration(self, data_particle, verify_values = False):
    '''
    Verify configuration particle
    @param data_particle:  SBE16ConfigurationDataParticle configuration particle
    @param verify_values:  bool, should we verify parameter values
    '''
    self.assert_data_particle_keys(SBE16ConfigurationDataParticleKey, self._configuration_parameters)
    self.assert_data_particle_header(data_particle, DataParticleType.DEVICE_CONFIGURATION)
    self.assert_data_particle_parameters(data_particle, self._configuration_parameters, verify_values)

setattr(SeaBird16plusMixin, 'assert_particle_hardware', assert_particle_hardware)
setattr(SeaBird16plusMixin, 'assert_particle_sample', assert_particle_sample)
setattr(SeaBird16plusMixin, 'assert_particle_calibration', assert_particle_calibration)
setattr(SeaBird16plusMixin, 'assert_particle_status', assert_particle_status)
setattr(SeaBird16plusMixin, 'assert_particle_configuration', assert_particle_configuration)

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

        self.assert_chunker_sample(chunker, self.VALID_GETCC_RESPONSE)
        self.assert_chunker_sample_with_noise(chunker, self.VALID_GETCC_RESPONSE)
        self.assert_chunker_fragmented_sample(chunker, self.VALID_GETCC_RESPONSE)
        self.assert_chunker_combined_sample(chunker, self.VALID_GETCC_RESPONSE)

        self.assert_chunker_sample(chunker, self.VALID_GETSD_RESPONSE)
        self.assert_chunker_sample_with_noise(chunker, self.VALID_GETSD_RESPONSE)
        self.assert_chunker_fragmented_sample(chunker, self.VALID_GETSD_RESPONSE)
        self.assert_chunker_combined_sample(chunker, self.VALID_GETSD_RESPONSE)

        self.assert_chunker_sample(chunker, self.VALID_GETCD_RESPONSE)
        self.assert_chunker_sample_with_noise(chunker, self.VALID_GETCD_RESPONSE)
        self.assert_chunker_fragmented_sample(chunker, self.VALID_GETCD_RESPONSE)
        self.assert_chunker_combined_sample(chunker, self.VALID_GETCD_RESPONSE)

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
        self.assert_particle_published(driver, self.VALID_GETCC_RESPONSE, self.assert_particle_calibration, True)
        self.assert_particle_published(driver, self.VALID_GETSD_RESPONSE, self.assert_particle_status, True)
        self.assert_particle_published(driver, self.VALID_GETCD_RESPONSE, self.assert_particle_configuration, True)
        

###############################################################################
#                            INTEGRATION TESTS                                #
#     Integration test test the direct driver / instrument interaction        #
#     but making direct calls via zeromq.                                     #
#     - Common Integration tests test the driver through the instrument agent #
#     and common for all drivers (minimum requirement for ION ingestion)      #
###############################################################################
@attr('INT', group='mi')
class IntFromIDK(SBEIntTestCase):

    def test_autosample(self):
        """
        Verify that we can enter streaming and that all particles are produced properly.

        Because we have to test for three different data particles we can't use
        the common assert_sample_autosample method
        """
        self.assert_initialize_driver()
        self.assert_set(Parameter.INTERVAL, 10)

        self.assert_driver_command(ProtocolEvent.START_AUTOSAMPLE, state=ProtocolState.AUTOSAMPLE, delay=1)
        self.assert_async_particle_generation(DataParticleType.CTD_PARSED, self.assert_particle_sample, timeout=60)

        self.assert_particle_generation(ProtocolEvent.ACQUIRE_STATUS, DataParticleType.DEVICE_STATUS, self.assert_particle_status)
        self.assert_particle_generation(ProtocolEvent.ACQUIRE_STATUS, DataParticleType.DEVICE_HARDWARE, self.assert_particle_hardware)
        self.assert_particle_generation(ProtocolEvent.ACQUIRE_STATUS, DataParticleType.DEVICE_CONFIGURATION, self.assert_particle_configuration)
        self.assert_particle_generation(ProtocolEvent.ACQUIRE_STATUS, DataParticleType.DEVICE_CALIBRATION, self.assert_particle_calibration)
        self.assert_particle_generation(ProtocolEvent.GET_CONFIGURATION, DataParticleType.DEVICE_CALIBRATION, self.assert_particle_calibration)

        self.assert_driver_command(ProtocolEvent.STOP_AUTOSAMPLE, state=ProtocolState.COMMAND, delay=1)

    def test_polled(self):
        """
        Test that we can generate particles with commands while in command mode
        """
        self.assert_initialize_driver()

        # test acquire_status particles
        self.assert_particle_generation(ProtocolEvent.ACQUIRE_STATUS, DataParticleType.DEVICE_STATUS, self.assert_particle_status)
        self.assert_particle_generation(ProtocolEvent.ACQUIRE_STATUS, DataParticleType.DEVICE_HARDWARE, self.assert_particle_hardware)
        self.assert_particle_generation(ProtocolEvent.ACQUIRE_STATUS, DataParticleType.DEVICE_CONFIGURATION, self.assert_particle_configuration)
        self.assert_particle_generation(ProtocolEvent.ACQUIRE_STATUS, DataParticleType.DEVICE_CALIBRATION, self.assert_particle_calibration)

        # test get_congiguration particle
        self.assert_particle_generation(ProtocolEvent.GET_CONFIGURATION, DataParticleType.DEVICE_CALIBRATION, self.assert_particle_calibration)
        
        # test acquire_sample data particle
        self.assert_particle_generation(ProtocolEvent.ACQUIRE_SAMPLE, DataParticleType.CTD_PARSED, self.assert_particle_sample)


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
