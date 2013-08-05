"""
@package mi.instrument.sunburst.test.test_driver
@file marine-integrations/mi/instrument/sunburst/driver.py
@author Stuart Pearce & Chris Wingard
@brief Common test case code for SAMI instrument drivers

USAGE:
 Make tests verbose and provide stdout
   * From the IDK
       $ bin/test_driver
       $ bin/test_driver -u [-t testname]
       $ bin/test_driver -i [-t testname]
       $ bin/test_driver -q [-t testname]
"""

__author__ = 'Stuart Pearce & Chris Wingard'
__license__ = 'Apache 2.0'

import unittest

from nose.plugins.attrib import attr
from mock import Mock

from mi.core.log import get_logger
log = get_logger()

# MI imports.
from mi.idk.unit_test import InstrumentDriverTestCase
from mi.idk.unit_test import InstrumentDriverUnitTestCase
from mi.idk.unit_test import InstrumentDriverIntegrationTestCase
from mi.idk.unit_test import InstrumentDriverQualificationTestCase
from mi.idk.unit_test import DriverTestMixin
from mi.idk.unit_test import ParameterTestConfigKey

from interface.objects import AgentCommand

from mi.core.instrument.logger_client import LoggerClient

# Might need these for later Integration tests and Qualification tests
#from mi.core.instrument.instrument_driver import DriverAsyncEvent
#from mi.core.instrument.instrument_driver import DriverConnectionState
#from mi.core.instrument.instrument_driver import DriverProtocolState
#from ion.agents.instrument.instrument_agent import InstrumentAgentState
#from ion.agents.instrument.direct_access.direct_access_server import DirectAccessTypes

# Changed imports
#from mi.instrument.sunburst.sami2_ph.ooicore.driver import DataParticleType
from mi.instrument.sunburst.driver import SamiDataParticleType
#from mi.instrument.sunburst.sami2_ph.ooicore.driver import PhsenConfigDataParticleKey
from mi.instrument.sunburst.driver import SamiConfigDataParticleKey
#from mi.instrument.sunburst.sami2_ph.ooicore.driver import SamiControlRecordDataParticleKey
from mi.instrument.sunburst.driver import SamiControlRecordDataParticleKey
#from mi.instrument.sunburst.sami2_ph.ooicore.driver import SamiRegularStatusDataParticleKey
from mi.instrument.sunburst.driver import SamiRegularStatusDataParticleKey
#from mi.instrument.sunburst.sami2_ph.ooicore.driver import ProtocolState
from mi.instrument.sunburst.driver import ProtocolState
#from mi.instrument.sunburst.sami2_ph.ooicore.driver import ProtocolEvent
from mi.instrument.sunburst.driver import ProtocolEvent
#from mi.instrument.sunburst.sami2_ph.ooicore.driver import Capability
from mi.instrument.sunburst.driver import Capability
#from mi.instrument.sunburst.sami2_ph.ooicore.driver import NEWLINE
from mi.instrument.sunburst.driver import NEWLINE
#from mi.instrument.sunburst.sami2_ph.ooicore.driver import Parameter
from mi.instrument.sunburst.driver import SamiParameter

# Removed imports for base classes (used in the specific test_driver)
#from mi.core.instrument.chunker import StringChunker
#from mi.instrument.sunburst.sami2_ph.ooicore.driver import InstrumentDriver
#from mi.instrument.sunburst.sami2_ph.ooicore.driver import InstrumentCommand
#from mi.instrument.sunburst.sami2_ph.ooicore.driver import PhsenSamiSampleDataParticleKey
#from mi.instrument.sunburst.sami2_ph.ooicore.driver import Protocol
#from mi.instrument.sunburst.sami2_ph.ooicore.driver import Prompt

###
#   Driver parameters for the tests
###


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

###
#   Driver constant definitions
###

###############################################################################
#                           DRIVER TEST MIXIN        		                  #
#     Defines a set of constants and assert methods used for data particle    #
#     verification 														      #
#                                                                             #
#  In python mixin classes are classes designed such that they wouldn't be    #
#  able to stand on their own, but are inherited by other classes generally   #
#  using multiple inheritance.                                                #
#                                                                             #
# This class defines a configuration structure for testing and common assert  #
# methods for validating data particles.									  #
###############################################################################

""" ---------- SPECIFIC DRIVER NOTE --------------------------------
In the specific test_driver, change parent mixin class to SamiMixin.
-----------------------------------------------------------------"""


class SamiMixin(DriverTestMixin):
    '''
    Mixin class used for storing SAMI instrument data particle constants and common data
    assertion methods.

    Should be subclassed in the specific test driver
    '''
    # Create some short names for the parameter test config
    TYPE = ParameterTestConfigKey.TYPE
    READONLY = ParameterTestConfigKey.READONLY
    STARTUP = ParameterTestConfigKey.STARTUP
    DA = ParameterTestConfigKey.DIRECT_ACCESS
    VALUE = ParameterTestConfigKey.VALUE
    REQUIRED = ParameterTestConfigKey.REQUIRED
    DEFAULT = ParameterTestConfigKey.DEFAULT
    STATES = ParameterTestConfigKey.STATES

    """ ---------- SPECIFIC DRIVER NOTE --------------------------------
    add the commented out section below to the specific test_driver
    -----------------------------------------------------------------"""
    ####
    ##  Instrument output (driver input) Definitions
    ####
    ## Configuration string received from the instrument via the L command
    ## (clock set to 2014-01-01 00:00:00) with sampling set to start 540 days
    ## (~18 months) later and stop 365 days after that. SAMI and Device1
    ## (external SBE pump) are set to run every 60 minutes, but will be polled
    ## on a regular schedule rather than autosampled. Device1 is not configured
    ## to run after the SAMI and will run for 10 seconds. To configure the
    ## instrument using this string, add a null byte (00) to the end of the
    ## string.
    #VALID_CONFIG_STRING = 'CDDD731D01E1338001E1338002000E100A0200000000110' + \
    #    '0000000110000000011000000001107013704200108081004081008170000' + \
    #    '0000000000000000000000000000000000000000000000000000000000000' + \
    #    '0000000000000000000000000000000000000000000000000000000000000' + \
    #    '00' + \
    #    'FFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFF' + \
    #    'FFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFF' + \
    #    'FFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFF' + \
    #    'FFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFF' + \
    #    'FFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFF' + NEWLINE
    #
    ## Data records -- SAMI (response to the R or R0 command)
    #VALID_DATA_SAMPLE = '*F8E70ACDDE9E4F06350BAA077C06A408040BAD077906A307' + \
    #    'FE0BA80778069F08010BAA077C06A208020BAB077E06A208040BAB077906A' + \
    #    '008010BAA06F806A107FE0BAE04EC06A707EF0BAF027C06A407E20BAA0126' + \
    #    '069E07D60BAF00A806A207D60BAC008906A407DF0BAD009206A207E70BAB0' + \
    #    '0C206A207F20BB0011306A707F80BAC019106A208000BAE022D069F08010B' + \
    #    'AB02E006A008030BAD039706A308000BAB044706A208000BAA04E906A3080' + \
    #    '30BAB056D06A408030BAA05DC069F08010BAF063406A608070BAE067406A2' + \
    #    '08000BAC06AB069E07FF0BAD06D506A2080200000D650636CE' + NEWLINE

    # Control records
    VALID_CONTROL_RECORD = '*F81285CDDD74DD0041000003000000000224FC' + NEWLINE

    # Regular Status Message (response to S0 command)
    VALID_STATUS_MESSAGE = ':CDDD74E10041000003000000000236F8' + NEWLINE

    # Error records (valid error codes are between 0x00 and 0x11)
    VALID_ERROR_CODE = '?0B' + NEWLINE

    ###
    #  Parameter and Type Definitions
    ###
    _driver_parameters = {
        # Parameters defined in the IOS
        SamiParameter.LAUNCH_TIME:              {TYPE: int, READONLY: True, DA: False, STARTUP: False,
                                                 DEFAULT: 0x00000000, VALUE: 0xCDDD731D},
        SamiParameter.START_TIME_FROM_LAUNCH:   {TYPE: int, READONLY: True, DA: False, STARTUP: False,
                                                 DEFAULT: 0x00000000, VALUE: 0x01E13380},
        SamiParameter.STOP_TIME_FROM_START:     {TYPE: int, READONLY: True, DA: False, STARTUP: False,
                                                 DEFAULT: 0x01E13380, VALUE: 0x01E13380},
        SamiParameter.MODE_BITS:                {TYPE: int, READONLY: True, DA: False, STARTUP: False,
                                                 DEFAULT: 0x02, VALUE: 0x02},
        SamiParameter.SAMI_SAMPLE_INTERVAL:     {TYPE: int, READONLY: True, DA: False, STARTUP: False,
                                                 DEFAULT: 0x000E10, VALUE: 0x000E10},
        SamiParameter.SAMI_DRIVER_VERSION:      {TYPE: int, READONLY: True, DA: False, STARTUP: False,
                                                 DEFAULT: 0x0A, VALUE: 0x0A},
        SamiParameter.SAMI_PARAMS_POINTER:      {TYPE: int, READONLY: True, DA: False, STARTUP: False,
                                                 DEFAULT: 0x02, VALUE: 0x02},
        SamiParameter.DEVICE1_SAMPLE_INTERVAL:  {TYPE: int, READONLY: True, DA: False, STARTUP: False,
                                                 DEFAULT: 0x000000, VALUE: 0x000000},
        SamiParameter.DEVICE1_DRIVER_VERSION:   {TYPE: int, READONLY: True, DA: False, STARTUP: False,
                                                 DEFAULT: 0x00, VALUE: 0x00},
        SamiParameter.DEVICE1_PARAMS_POINTER:   {TYPE: int, READONLY: True, DA: False, STARTUP: False,
                                                 DEFAULT: 0x11, VALUE: 0x11},
        SamiParameter.DEVICE2_SAMPLE_INTERVAL:  {TYPE: int, READONLY: True, DA: False, STARTUP: False,
                                                 DEFAULT: 0x000000, VALUE: 0x000000},
        SamiParameter.DEVICE2_DRIVER_VERSION:   {TYPE: int, READONLY: True, DA: False, STARTUP: False,
                                                 DEFAULT: 0x00, VALUE: 0x00},
        SamiParameter.DEVICE2_PARAMS_POINTER:   {TYPE: int, READONLY: True, DA: False, STARTUP: False,
                                                 DEFAULT: 0x11, VALUE: 0x11},
        SamiParameter.DEVICE3_SAMPLE_INTERVAL:  {TYPE: int, READONLY: True, DA: False, STARTUP: False,
                                                 DEFAULT: 0x000000, VALUE: 0x000000},
        SamiParameter.DEVICE3_DRIVER_VERSION:   {TYPE: int, READONLY: True, DA: False, STARTUP: False,
                                                 DEFAULT: 0x00, VALUE: 0x00},
        SamiParameter.DEVICE3_PARAMS_POINTER:   {TYPE: int, READONLY: True, DA: False, STARTUP: False,
                                                 DEFAULT: 0x11, VALUE: 0x11},
        SamiParameter.PRESTART_SAMPLE_INTERVAL: {TYPE: int, READONLY: True, DA: False, STARTUP: False,
                                                 DEFAULT: 0x000000, VALUE: 0x000000},
        SamiParameter.PRESTART_DRIVER_VERSION:  {TYPE: int, READONLY: True, DA: False, STARTUP: False,
                                                 DEFAULT: 0x00, VALUE: 0x00},
        SamiParameter.PRESTART_PARAMS_POINTER:  {TYPE: int, READONLY: True, DA: False, STARTUP: False,
                                                 DEFAULT: 0x11, VALUE: 0x11},
        SamiParameter.GLOBAL_CONFIGURATION:     {TYPE: int, READONLY: True, DA: False, STARTUP: False,
                                                 DEFAULT: 0x07, VALUE: 0x07}
    }

    """ ---------- SPECIFIC DRIVER NOTE --------------------------------
    The _driver_parameters dictionary above should be extended by using
    the update method of a dictionary object, with a dictionary
    containing the instrument specific parameters in the specific
    driver.  Use the Parameter Class to provide the Keys.

    E.g.:
    >>> SamiMixin._driver_parameters.update(_driver_parameters_continued)
    -----------------------------------------------------------------"""
    #    Parameter.NUMBER_SAMPLES_AVERAGED:  {TYPE: int, READONLY: True, DA: False, STARTUP: False,
    #                                         DEFAULT: 0x01, VALUE: 0x01},
    #    Parameter.NUMBER_FLUSHES:           {TYPE: int, READONLY: True, DA: False, STARTUP: False,
    #                                         DEFAULT: 0x37, VALUE: 0x37},
    #    Parameter.PUMP_ON_FLUSH:            {TYPE: int, READONLY: True, DA: False, STARTUP: False,
    #                                         DEFAULT: 0x04, VALUE: 0x04},
    #    Parameter.PUMP_OFF_FLUSH:           {TYPE: int, READONLY: True, DA: False, STARTUP: False,
    #                                         DEFAULT: 0x20, VALUE: 0x20},
    #    Parameter.NUMBER_REAGENT_PUMPS:     {TYPE: int, READONLY: True, DA: False, STARTUP: False,
    #                                         DEFAULT: 0x01, VALUE: 0x01},
    #    Parameter.VALVE_DELAY:              {TYPE: int, READONLY: True, DA: False, STARTUP: False,
    #                                         DEFAULT: 0x08, VALUE: 0x08},
    #    Parameter.PUMP_ON_IND:              {TYPE: int, READONLY: True, DA: False, STARTUP: False,
    #                                         DEFAULT: 0x08, VALUE: 0x08},
    #    Parameter.PV_OFF_IND:               {TYPE: int, READONLY: True, DA: False, STARTUP: False,
    #                                         DEFAULT: 0x10, VALUE: 0x10},
    #    Parameter.NUMBER_BLANKS:            {TYPE: int, READONLY: True, DA: False, STARTUP: False,
    #                                         DEFAULT: 0x04, VALUE: 0x04},
    #    Parameter.PUMP_MEASURE_T:           {TYPE: int, READONLY: True, DA: False, STARTUP: False,
    #                                         DEFAULT: 0x08, VALUE: 0x08},
    #    Parameter.PUMP_OFF_TO_MEASURE:      {TYPE: int, READONLY: True, DA: False, STARTUP: False,
    #                                         DEFAULT: 0x10, VALUE: 0x10},
    #    Parameter.MEASURE_TO_PUMP_ON:       {TYPE: int, READONLY: True, DA: False, STARTUP: False,
    #                                         DEFAULT: 0x08, VALUE: 0x08},
    #    Parameter.NUMBER_MEASUREMENTS:      {TYPE: int, READONLY: True, DA: False, STARTUP: False,
    #                                         DEFAULT: 0x17, VALUE: 0x17},
    #    Parameter.SALINITY_DELAY:           {TYPE: int, READONLY: True, DA: False, STARTUP: False,
    #                                         DEFAULT: 0x00, VALUE: 0x00}
    #}

    _driver_capabilities = {
        # capabilities defined in the IOS
        Capability.ACQUIRE_STATUS:      {STATES: [ProtocolState.COMMAND]},
        #Capability.ACQUIRE_SAMPLE:      {STATES: [ProtocolState.COMMAND]},
        Capability.START_AUTOSAMPLE:    {STATES: [ProtocolState.COMMAND,
                                                  ProtocolState.AUTOSAMPLE]},
        Capability.STOP_AUTOSAMPLE:     {STATES: [ProtocolState.AUTOSAMPLE,
                                                  ProtocolState.COMMAND]},
        Capability.START_DIRECT:        {STATES: [ProtocolState.COMMAND,
                                                  ProtocolState.UNKNOWN,
                                                  ProtocolState.DIRECT_ACCESS]},
        Capability.STOP_DIRECT:         {STATES: [ProtocolState.DIRECT_ACCESS,
                                                  ProtocolState.UNKNOWN]}
    }

    _regular_status_parameters = {
        # SAMI Regular Status Messages (S0)
        SamiRegularStatusDataParticleKey.ELAPSED_TIME_CONFIG:       {TYPE: int, VALUE: 0xCDDD74E1, REQUIRED: True},
        SamiRegularStatusDataParticleKey.CLOCK_ACTIVE:              {TYPE: bool, VALUE: True, REQUIRED: True},
        SamiRegularStatusDataParticleKey.RECORDING_ACTIVE:          {TYPE: bool, VALUE: False, REQUIRED: True},
        SamiRegularStatusDataParticleKey.RECORD_END_ON_TIME:        {TYPE: bool, VALUE: False, REQUIRED: True},
        SamiRegularStatusDataParticleKey.RECORD_MEMORY_FULL:        {TYPE: bool, VALUE: False, REQUIRED: True},
        SamiRegularStatusDataParticleKey.RECORD_END_ON_ERROR:       {TYPE: bool, VALUE: False, REQUIRED: True},
        SamiRegularStatusDataParticleKey.DATA_DOWNLOAD_OK:          {TYPE: bool, VALUE: False, REQUIRED: True},
        SamiRegularStatusDataParticleKey.FLASH_MEMORY_OPEN:         {TYPE: bool, VALUE: True, REQUIRED: True},
        SamiRegularStatusDataParticleKey.BATTERY_LOW_PRESTART:      {TYPE: bool, VALUE: False, REQUIRED: True},
        SamiRegularStatusDataParticleKey.BATTERY_LOW_MEASUREMENT:   {TYPE: bool, VALUE: False, REQUIRED: True},
        SamiRegularStatusDataParticleKey.BATTERY_LOW_BANK:          {TYPE: bool, VALUE: False, REQUIRED: True},
        SamiRegularStatusDataParticleKey.BATTERY_LOW_EXTERNAL:      {TYPE: bool, VALUE: False, REQUIRED: True},
        SamiRegularStatusDataParticleKey.EXTERNAL_DEVICE1_FAULT:    {TYPE: bool, VALUE: False, REQUIRED: True},
        SamiRegularStatusDataParticleKey.EXTERNAL_DEVICE2_FAULT:    {TYPE: bool, VALUE: False, REQUIRED: True},
        SamiRegularStatusDataParticleKey.EXTERNAL_DEVICE3_FAULT:    {TYPE: bool, VALUE: False, REQUIRED: True},
        SamiRegularStatusDataParticleKey.FLASH_ERASED:              {TYPE: bool, VALUE: False, REQUIRED: True},
        SamiRegularStatusDataParticleKey.POWER_ON_INVALID:          {TYPE: bool, VALUE: False, REQUIRED: True},
        SamiRegularStatusDataParticleKey.NUM_DATA_RECORDS:          {TYPE: int, VALUE: 0x000003, REQUIRED: True},
        SamiRegularStatusDataParticleKey.NUM_ERROR_RECORDS:         {TYPE: int, VALUE: 0x000000, REQUIRED: True},
        SamiRegularStatusDataParticleKey.NUM_BYTES_STORED:          {TYPE: int, VALUE: 0x000236, REQUIRED: True},
        SamiRegularStatusDataParticleKey.CHECKSUM:                  {TYPE: int, VALUE: 0xF8, REQUIRED: True}
    }

    _control_record_parameters = {
        SamiControlRecordDataParticleKey.UNIQUE_ID:               {TYPE: int, VALUE: 0xF8, REQUIRED: True},
        SamiControlRecordDataParticleKey.RECORD_LENGTH:           {TYPE: int, VALUE: 0x12, REQUIRED: True},
        SamiControlRecordDataParticleKey.RECORD_TYPE:             {TYPE: int, VALUE: 0x85,  REQUIRED: True},
        SamiControlRecordDataParticleKey.RECORD_TIME:             {TYPE: int, VALUE: 0xCDDD74DD, REQUIRED: True},
        SamiControlRecordDataParticleKey.CLOCK_ACTIVE:            {TYPE: bool, VALUE: True, REQUIRED: True},
        SamiControlRecordDataParticleKey.RECORDING_ACTIVE:        {TYPE: bool, VALUE: False, REQUIRED: True},
        SamiControlRecordDataParticleKey.RECORD_END_ON_TIME:      {TYPE: bool, VALUE: False, REQUIRED: True},
        SamiControlRecordDataParticleKey.RECORD_MEMORY_FULL:      {TYPE: bool, VALUE: False, REQUIRED: True},
        SamiControlRecordDataParticleKey.RECORD_END_ON_ERROR:     {TYPE: bool, VALUE: False, REQUIRED: True},
        SamiControlRecordDataParticleKey.DATA_DOWNLOAD_OK:        {TYPE: bool, VALUE: False, REQUIRED: True},
        SamiControlRecordDataParticleKey.FLASH_MEMORY_OPEN:       {TYPE: bool, VALUE: True, REQUIRED: True},
        SamiControlRecordDataParticleKey.BATTERY_LOW_PRESTART:    {TYPE: bool, VALUE: False, REQUIRED: True},
        SamiControlRecordDataParticleKey.BATTERY_LOW_MEASUREMENT: {TYPE: bool, VALUE: False, REQUIRED: True},
        SamiControlRecordDataParticleKey.BATTERY_LOW_BANK:        {TYPE: bool, VALUE: False, REQUIRED: True},
        SamiControlRecordDataParticleKey.BATTERY_LOW_EXTERNAL:    {TYPE: bool, VALUE: False, REQUIRED: True},
        SamiControlRecordDataParticleKey.EXTERNAL_DEVICE1_FAULT:  {TYPE: bool, VALUE: False, REQUIRED: True},
        SamiControlRecordDataParticleKey.EXTERNAL_DEVICE2_FAULT:  {TYPE: bool, VALUE: False, REQUIRED: True},
        SamiControlRecordDataParticleKey.EXTERNAL_DEVICE3_FAULT:  {TYPE: bool, VALUE: False, REQUIRED: True},
        SamiControlRecordDataParticleKey.FLASH_ERASED:            {TYPE: bool, VALUE: False, REQUIRED: True},
        SamiControlRecordDataParticleKey.POWER_ON_INVALID:        {TYPE: bool, VALUE: False, REQUIRED: True},
        SamiControlRecordDataParticleKey.NUM_DATA_RECORDS:        {TYPE: int, VALUE: 0x000003, REQUIRED: True},
        SamiControlRecordDataParticleKey.NUM_ERROR_RECORDS:       {TYPE: int, VALUE: 0x000000, REQUIRED: True},
        SamiControlRecordDataParticleKey.NUM_BYTES_STORED:        {TYPE: int, VALUE: 0x000224, REQUIRED: True},
        SamiControlRecordDataParticleKey.CHECKSUM:                {TYPE: int, VALUE: 0xFC, REQUIRED: True}
    }

    """ ---------- SPECIFIC DRIVER NOTE --------------------------------
    put the _sami_data_sample_parameters dictionary in the specifc
    driver.
    -----------------------------------------------------------------"""
    #_sami_data_sample_parameters = {
    #    # SAMI pH sample (type 0x0A)
    #    PhsenSamiSampleDataParticleKey.UNIQUE_ID:        {TYPE: int, VALUE: 0xF8, REQUIRED: True},
    #    PhsenSamiSampleDataParticleKey.RECORD_LENGTH:    {TYPE: int, VALUE: 0xE7, REQUIRED: True},
    #    PhsenSamiSampleDataParticleKey.RECORD_TYPE:      {TYPE: int, VALUE: 0x0A, REQUIRED: True},
    #    PhsenSamiSampleDataParticleKey.RECORD_TIME:      {TYPE: int, VALUE: 0xCDDE9E4F, REQUIRED: True},
    #    PhsenSamiSampleDataParticleKey.START_THERMISTOR: {TYPE: int, VALUE: 0x0635, REQUIRED: True},
    #    PhsenSamiSampleDataParticleKey.REF_MEASUREMENTS: {
    #        TYPE: list, VALUE:
    #        [0x0BAA, 0x077C, 0x06A4, 0x0804,
    #         0x0BAD, 0x0779, 0x06A3, 0x07FE,
    #         0x0BA8, 0x0778, 0x069F, 0x0801,
    #         0x0BAA, 0x077C, 0x06A2, 0x0802],
    #        REQUIRED: True},
    #    PhsenSamiSampleDataParticleKey.PH_MEASUREMENTS:  {
    #        TYPE: list, VALUE:
    #        [0x0BAB, 0x077E, 0x06A2, 0x0804,
    #         0x0BAB, 0x0779, 0x06A0, 0x0801,
    #         0x0BAA, 0x06F8, 0x06A1, 0x07FE,
    #         0x0BAE, 0x04EC, 0x06A7, 0x07EF,
    #         0x0BAF, 0x027C, 0x06A4, 0x07E2,
    #         0x0BAA, 0x0126, 0x069E, 0x07D6,
    #         0x0BAF, 0x00A8, 0x06A2, 0x07D6,
    #         0x0BAC, 0x0089, 0x06A4, 0x07DF,
    #         0x0BAD, 0x0092, 0x06A2, 0x07E7,
    #         0x0BAB, 0x00C2, 0x06A2, 0x07F2,
    #         0x0BB0, 0x0113, 0x06A7, 0x07F8,
    #         0x0BAC, 0x0191, 0x06A2, 0x0800,
    #         0x0BAE, 0x022D, 0x069F, 0x0801,
    #         0x0BAB, 0x02E0, 0x06A0, 0x0803,
    #         0x0BAD, 0x0397, 0x06A3, 0x0800,
    #         0x0BAB, 0x0447, 0x06A2, 0x0800,
    #         0x0BAA, 0x04E9, 0x06A3, 0x0803,
    #         0x0BAB, 0x056D, 0x06A4, 0x0803,
    #         0x0BAA, 0x05DC, 0x069F, 0x0801,
    #         0x0BAF, 0x0634, 0x06A6, 0x0807,
    #         0x0BAE, 0x0674, 0x06A2, 0x0800,
    #         0x0BAC, 0x06AB, 0x069E, 0x07FF,
    #         0x0BAD, 0x06D5, 0x06A2, 0x0802],
    #        REQUIRED: True},
    #    PhsenSamiSampleDataParticleKey.RESERVED_UNUSED:  {TYPE: int, VALUE: 0x0000, REQUIRED: True},
    #    PhsenSamiSampleDataParticleKey.VOLTAGE_BATTERY:  {TYPE: int, VALUE: 0x0D65, REQUIRED: True},
    #    PhsenSamiSampleDataParticleKey.END_THERMISTOR:   {TYPE: int, VALUE: 0x0636, REQUIRED: True},
    #    PhsenSamiSampleDataParticleKey.CHECKSUM:         {TYPE: int, VALUE: 0xCE, REQUIRED: True}
    #}

    _configuration_parameters = {
        # Configuration settings
        SamiConfigDataParticleKey.LAUNCH_TIME:                 {TYPE: int, VALUE: 0xCDDD731D, REQUIRED: True},
        SamiConfigDataParticleKey.START_TIME_OFFSET:           {TYPE: int, VALUE: 0x01E13380, REQUIRED: True},
        SamiConfigDataParticleKey.RECORDING_TIME:              {TYPE: int, VALUE: 0x01E13380, REQUIRED: True},
        SamiConfigDataParticleKey.PMI_SAMPLE_SCHEDULE:         {TYPE: bool, VALUE: False,  REQUIRED: True},
        SamiConfigDataParticleKey.SAMI_SAMPLE_SCHEDULE:        {TYPE: bool, VALUE: True,  REQUIRED: True},
        SamiConfigDataParticleKey.SLOT1_FOLLOWS_SAMI_SCHEDULE: {TYPE: bool, VALUE: False,  REQUIRED: True},
        SamiConfigDataParticleKey.SLOT1_INDEPENDENT_SCHEDULE:  {TYPE: bool, VALUE: False, REQUIRED: True},
        SamiConfigDataParticleKey.SLOT2_FOLLOWS_SAMI_SCHEDULE: {TYPE: bool, VALUE: False,  REQUIRED: True},
        SamiConfigDataParticleKey.SLOT2_INDEPENDENT_SCHEDULE:  {TYPE: bool, VALUE: False, REQUIRED: True},
        SamiConfigDataParticleKey.SLOT3_FOLLOWS_SAMI_SCHEDULE: {TYPE: bool, VALUE: False,  REQUIRED: True},
        SamiConfigDataParticleKey.SLOT3_INDEPENDENT_SCHEDULE:  {TYPE: bool, VALUE: False, REQUIRED: True},
        SamiConfigDataParticleKey.TIMER_INTERVAL_SAMI:         {TYPE: int, VALUE: 0x000E10, REQUIRED: True},
        SamiConfigDataParticleKey.DRIVER_ID_SAMI:              {TYPE: int, VALUE: 0x0A,  REQUIRED: True},
        SamiConfigDataParticleKey.PARAMETER_POINTER_SAMI:      {TYPE: int, VALUE: 0x02,  REQUIRED: True},
        SamiConfigDataParticleKey.TIMER_INTERVAL_DEVICE1:      {TYPE: int, VALUE: 0x000000, REQUIRED: True},
        SamiConfigDataParticleKey.DRIVER_ID_DEVICE1:           {TYPE: int, VALUE: 0x00,  REQUIRED: True},
        SamiConfigDataParticleKey.PARAMETER_POINTER_DEVICE1:   {TYPE: int, VALUE: 0x11, REQUIRED: True},
        SamiConfigDataParticleKey.TIMER_INTERVAL_DEVICE2:      {TYPE: int, VALUE: 0x000000, REQUIRED: True},
        SamiConfigDataParticleKey.DRIVER_ID_DEVICE2:           {TYPE: int, VALUE: 0x00,  REQUIRED: True},
        SamiConfigDataParticleKey.PARAMETER_POINTER_DEVICE2:   {TYPE: int, VALUE: 0x11, REQUIRED: True},
        SamiConfigDataParticleKey.TIMER_INTERVAL_DEVICE3:      {TYPE: int, VALUE: 0x000000, REQUIRED: True},
        SamiConfigDataParticleKey.DRIVER_ID_DEVICE3:           {TYPE: int, VALUE: 0x00,  REQUIRED: True},
        SamiConfigDataParticleKey.PARAMETER_POINTER_DEVICE3:   {TYPE: int, VALUE: 0x11, REQUIRED: True},
        SamiConfigDataParticleKey.TIMER_INTERVAL_PRESTART:     {TYPE: int, VALUE: 0x000000, REQUIRED: True},
        SamiConfigDataParticleKey.DRIVER_ID_PRESTART:          {TYPE: int, VALUE: 0x00, REQUIRED: True},
        SamiConfigDataParticleKey.PARAMETER_POINTER_PRESTART:  {TYPE: int, VALUE: 0x11, REQUIRED: True},
        SamiConfigDataParticleKey.USE_BAUD_RATE_57600:         {TYPE: bool, VALUE: True, REQUIRED: True},
        SamiConfigDataParticleKey.SEND_RECORD_TYPE:            {TYPE: bool, VALUE: True, REQUIRED: True},
        SamiConfigDataParticleKey.SEND_LIVE_RECORDS:           {TYPE: bool, VALUE: True, REQUIRED: True},
        SamiConfigDataParticleKey.EXTEND_GLOBAL_CONFIG:        {TYPE: bool, VALUE: False, REQUIRED: True}
    }

    """ ---------- SPECIFIC DRIVER NOTE --------------------------------
    The _configuration_parameters dictionary above should be extended by
    using the update method of a dictionary object, with a dictionary
    containing the instrument specific parameters in the specific
    driver.
    Make sure to use the correct DataParticleKey class.
    -----------------------------------------------------------------"""
    #    # These are uniqe to pH
    #    PhsenConfigDataParticleKey.NUMBER_SAMPLES_AVERAGED:     {TYPE: int, VALUE: 0x01, REQUIRED: True},
    #    PhsenConfigDataParticleKey.NUMBER_FLUSHES:              {TYPE: int, VALUE: 0x37, REQUIRED: True},
    #    PhsenConfigDataParticleKey.PUMP_ON_FLUSH:               {TYPE: int, VALUE: 0x04, REQUIRED: True},
    #    PhsenConfigDataParticleKey.PUMP_OFF_FLUSH:              {TYPE: int, VALUE: 0x20, REQUIRED: True},
    #    PhsenConfigDataParticleKey.NUMBER_REAGENT_PUMPS:        {TYPE: int, VALUE: 0x01, REQUIRED: True},
    #    PhsenConfigDataParticleKey.VALVE_DELAY:                 {TYPE: int, VALUE: 0x08, REQUIRED: True},
    #    PhsenConfigDataParticleKey.PUMP_ON_IND:                 {TYPE: int, VALUE: 0x08, REQUIRED: True},
    #    PhsenConfigDataParticleKey.PV_OFF_IND:                  {TYPE: int, VALUE: 0x10, REQUIRED: True},
    #    PhsenConfigDataParticleKey.NUMBER_BLANKS:               {TYPE: int, VALUE: 0x04, REQUIRED: True},
    #    PhsenConfigDataParticleKey.PUMP_MEASURE_T:              {TYPE: int, VALUE: 0x08, REQUIRED: True},
    #    PhsenConfigDataParticleKey.PUMP_OFF_TO_MEASURE:         {TYPE: int, VALUE: 0x10, REQUIRED: True},
    #    PhsenConfigDataParticleKey.MEASURE_TO_PUMP_ON:          {TYPE: int, VALUE: 0x08, REQUIRED: True},
    #    PhsenConfigDataParticleKey.NUMBER_MEASUREMENTS:         {TYPE: int, VALUE: 0x17, REQUIRED: True},
    #    PhsenConfigDataParticleKey.SALINITY_DELAY:              {TYPE: int, VALUE: 0x00, REQUIRED: True}
    #}

    def assertSampleDataParticle(self, data_particle):
        '''
        Verify a particle is a known particle to this driver and verify the particle is
        correct
        @param data_particle: Data particle of unkown type produced by the driver
        '''
        if (isinstance(data_particle, RawDataParticle)):
            self.assert_particle_raw(data_particle)
        else:
            log.error("Unknown Particle Detected: %s" % data_particle)
            self.assertFalse(True)

    def assert_driver_parameters(self, current_parameters, verify_values=False):
        """
        Verify that all driver parameters are correct and potentially verify
        values.
        @param current_parameters: driver parameters read from the driver
        instance
        @param verify_values: should we verify values against definition?
        """
        self.assert_parameters(current_parameters, self._driver_parameters,
                               verify_values)

    def assert_particle_regular_status(self, data_particle, verify_values=False):
        '''
        Verify regular_status particle
        @param data_particle: SamiRegularStatusDataParticle data particle
        @param verify_values: bool, should we verify parameter values
        '''
        self.assert_data_particle_keys(SamiRegularStatusDataParticleKey,
                                       self._regular_status_parameters)
        self.assert_data_particle_header(data_particle,
                                         SamiDataParticleType.REGULAR_STATUS)
        self.assert_data_particle_parameters(data_particle,
                                             self._regular_status_parameters,
                                             verify_values)

    # NOTE: can be here because SamiControlRecordDataParticleKey is in base driver
    def assert_particle_control_record(self, data_particle, verify_values=False):
        '''
        Verify control_record particle
        @param data_particle: SamiControlRecordDataParticle data particle
        @param verify_values: bool, should we verify parameter values
        '''
        self.assert_data_particle_keys(SamiControlRecordDataParticleKey,
                                       self._control_record_parameters)
        self.assert_data_particle_header(data_particle,
                                         SamiDataParticleType.CONTROL_RECORD)
        self.assert_data_particle_parameters(data_particle,
                                             self._control_record_parameters,
                                             verify_values)

    # NOTE: this should probably be in the specific, but as long as it
    # is never run until Phsen --- nope goes in the specific
    #def assert_particle_sami_data_sample(self, data_particle, verify_values=False):
    #    '''
    #    Verify sami_data_sample particle (Type 0A pH)
    #    @param data_particle: PhsenSamiSampleDataParticle data particle
    #    @param verify_values: bool, should we verify parameter values
    #    '''
    #    self.assert_data_particle_keys(PhsenSamiSampleDataParticleKey,
    #                                   self._sami_data_sample_parameters)
    #    self.assert_data_particle_header(data_particle,
    #                                     DataParticleType.SAMI_SAMPLE)
    #    self.assert_data_particle_parameters(data_particle,
    #                                         self._sami_data_sample_parameters,
    #                                         verify_values)

    # NOTE: goes in the specific because of the PhsenConfig...
    #def assert_particle_configuration(self, data_particle, verify_values=False):
    #    '''
    #    Verify configuration particle
    #    @param data_particle: PhsenConfigDataParticle data particle
    #    @param verify_values: bool, should we verify parameter values
    #    '''
    #    self.assert_data_particle_keys(PhsenConfigDataParticleKey,
    #                                   self._configuration_parameters)
    #    self.assert_data_particle_header(data_particle,
    #                                     DataParticleType.CONFIGURATION)
    #    self.assert_data_particle_parameters(data_particle,
    #                                         self._configuration_parameters,
    #                                     verify_values)


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
class SamiUnitTest(InstrumentDriverUnitTestCase, SamiMixin):
    # This is not needed.  Inheritance takes care of that.
    #def setUp(self):
    #    InstrumentDriverUnitTestCase.setUp(self)

    # NOTE: I think can stay here, no probably not.  Needs to call Instrument Driver class
    #def test_driver_schema(self):
    #    """
    #    get the driver schema and verify it is configured properly
    #    """
    #    driver = InstrumentDriver(self._got_data_event_callback)
    #    self.assert_driver_schema(driver, self._driver_parameters, self._driver_capabilities)

    # NOTE: may need to move to specific because of the no duplicates
    # for DataParticleType, Parameter, and InstrumentCommand.  Maybe move those
    # three assert statements to a specific test_ph_driver_enums, and here
    # change the name to test_sami_driver_enum
    def test_base_driver_enums(self):
        """
        Verify that all the SAMI Instrument driver enumerations have no
        duplicate values that might cause confusion. Also do a little
        extra validation for the Capabilites
        """
        #self.assert_enum_has_no_duplicates(DataParticleType())
        self.assert_enum_has_no_duplicates(ProtocolState())
        self.assert_enum_has_no_duplicates(ProtocolEvent())
        #self.assert_enum_has_no_duplicates(Parameter())
        #self.assert_enum_has_no_duplicates(InstrumentCommand())

        # Test capabilites for duplicates, them verify that capabilities is a subset of proto events
        self.assert_enum_has_no_duplicates(Capability())
        self.assert_enum_complete(Capability(), ProtocolEvent())

    # NOTE: this definitely moves to the specific
    #def test_chunker(self):
    #    """
    #    Test the chunker and verify the particles created.
    #    """
    #    chunker = StringChunker(Protocol.sieve_function)
    #
    #    self.assert_chunker_sample(chunker, self.VALID_STATUS_MESSAGE)
    #    self.assert_chunker_sample_with_noise(chunker, self.VALID_STATUS_MESSAGE)
    #    self.assert_chunker_fragmented_sample(chunker, self.VALID_STATUS_MESSAGE)
    #    self.assert_chunker_combined_sample(chunker, self.VALID_STATUS_MESSAGE)
    #
    #    self.assert_chunker_sample(chunker, self.VALID_CONTROL_RECORD)
    #    self.assert_chunker_sample_with_noise(chunker, self.VALID_CONTROL_RECORD)
    #    self.assert_chunker_fragmented_sample(chunker, self.VALID_CONTROL_RECORD)
    #    self.assert_chunker_combined_sample(chunker, self.VALID_CONTROL_RECORD)
    #
    #    self.assert_chunker_sample(chunker, self.VALID_DATA_SAMPLE)
    #    self.assert_chunker_sample_with_noise(chunker, self.VALID_DATA_SAMPLE)
    #    self.assert_chunker_fragmented_sample(chunker, self.VALID_DATA_SAMPLE)
    #    self.assert_chunker_combined_sample(chunker, self.VALID_DATA_SAMPLE)
    #
    #    self.assert_chunker_sample(chunker, self.VALID_CONFIG_STRING)
    #    self.assert_chunker_sample_with_noise(chunker, self.VALID_CONFIG_STRING)
    #    self.assert_chunker_fragmented_sample(chunker, self.VALID_CONFIG_STRING)
    #    self.assert_chunker_combined_sample(chunker, self.VALID_CONFIG_STRING)

    # NOTE: Move to specific
    #def test_got_data(self):
    #    """
    #    Verify sample data passed through the got data method produces the correct data particles
    #    """
    #    # Create and initialize the instrument driver with a mock port agent
    #    driver = InstrumentDriver(self._got_data_event_callback)
    #    self.assert_initialize_driver(driver)
    #
    #    self.assert_raw_particle_published(driver, True)
    #
    #    # Start validating data particles
    #    self.assert_particle_published(driver, self.VALID_STATUS_MESSAGE, self.assert_particle_regular_status, True)
    #    self.assert_particle_published(driver, self.VALID_CONTROL_RECORD, self.assert_particle_control_record, True)
    #    self.assert_particle_published(driver, self.VALID_DATA_SAMPLE, self.assert_particle_sami_data_sample, True)
    #    self.assert_particle_published(driver, self.VALID_CONFIG_STRING, self.assert_particle_configuration, True)

    # Move to specific because of Protocol
    #def test_protocol_filter_capabilities(self):
    #    """
    #    This tests driver filter_capabilities.
    #    Iterate through available capabilities, and verify that they can pass successfully through the filter.
    #    Test silly made up capabilities to verify they are blocked by filter.
    #    """
    #    mock_callback = Mock()
    #    protocol = Protocol(Prompt, NEWLINE, mock_callback)
    #    driver_capabilities = Capability().list()
    #    test_capabilities = Capability().list()
    #
    #    # Add a bogus capability that will be filtered out.
    #    test_capabilities.append("BOGUS_CAPABILITY")
    #
    #    # Verify "BOGUS_CAPABILITY was filtered out
    #    self.assertEquals(sorted(driver_capabilities),
    #                      sorted(protocol._filter_capabilities(test_capabilities)))

    # NOTE: the definition needs to move to the specific unittest class,
    # because of the call to the driver, however the capabilities
    # dictionary could be defined here as self.capabilities and the test
    # call self.capabilities instead.
    #def test_capabilities(self):
    #    """
    #    Verify the FSM reports capabilities as expected. All states defined in
    #    this dict must also be defined in the protocol FSM. Note, the EXIT and
    #    ENTER DRIVER_EVENTS don't need to be listed here.
    #    """
    #    capabilities = {
    #        ProtocolState.UNKNOWN:          ['DRIVER_EVENT_START_DIRECT',
    #                                         'DRIVER_EVENT_DISCOVER'],
    #        ProtocolState.WAITING:          ['DRIVER_EVENT_DISCOVER'],
    #        ProtocolState.COMMAND:          ['DRIVER_EVENT_GET',
    #                                         'DRIVER_EVENT_SET',
    #                                         'DRIVER_EVENT_START_DIRECT',
    #                                         #'DRIVER_EVENT_ACQUIRE_CONFIGURATION',
    #                                         'DRIVER_EVENT_ACQUIRE_STATUS',
    #                                         'DRIVER_EVENT_ACQUIRE_SAMPLE',
    #                                         'DRIVER_EVENT_START_AUTOSAMPLE'],
    #        ProtocolState.AUTOSAMPLE:       ['DRIVER_EVENT_ACQUIRE_SAMPLE',
    #                                         'DRIVER_EVENT_STOP_AUTOSAMPLE'],
    #        ProtocolState.DIRECT_ACCESS:    ['EXECUTE_DIRECT',
    #                                         'DRIVER_EVENT_STOP_DIRECT'],
    #        ProtocolState.SCHEDULED_SAMPLE: ['PROTOCOL_EVENT_SUCCESS',
    #                                         'PROTOCOL_EVENT_TIMEOUT'],
    #        ProtocolState.POLLED_SAMPLE:    ['PROTOCOL_EVENT_SUCCESS',
    #                                         'PROTOCOL_EVENT_TIMEOUT']
    #    }
    #
    #    driver = InstrumentDriver(self._got_data_event_callback)
    #    self.assert_capabilities(driver, capabilities)

    capabilities_test_dict = {
        ProtocolState.UNKNOWN:          ['DRIVER_EVENT_START_DIRECT',
                                         'DRIVER_EVENT_DISCOVER'],
        ProtocolState.WAITING:          ['DRIVER_EVENT_DISCOVER'],
        ProtocolState.COMMAND:          ['DRIVER_EVENT_GET',
                                         'DRIVER_EVENT_SET',
                                         'DRIVER_EVENT_START_DIRECT',
                                         #'DRIVER_EVENT_ACQUIRE_CONFIGURATION',
                                         'DRIVER_EVENT_ACQUIRE_STATUS',
                                         'DRIVER_EVENT_ACQUIRE_SAMPLE',
                                         'DRIVER_EVENT_START_AUTOSAMPLE'],
        ProtocolState.AUTOSAMPLE:       ['DRIVER_EVENT_ACQUIRE_SAMPLE',
                                         'DRIVER_EVENT_STOP_AUTOSAMPLE'],
        ProtocolState.DIRECT_ACCESS:    ['EXECUTE_DIRECT',
                                         'DRIVER_EVENT_STOP_DIRECT'],
        ProtocolState.SCHEDULED_SAMPLE: ['PROTOCOL_EVENT_SUCCESS',
                                         'PROTOCOL_EVENT_TIMEOUT'],
        ProtocolState.POLLED_SAMPLE:    ['PROTOCOL_EVENT_SUCCESS',
                                         'PROTOCOL_EVENT_TIMEOUT']
    }


###############################################################################
#                            INTEGRATION TESTS                                #
#     Integration test test the direct driver / instrument interaction        #
#     but making direct calls via zeromq.                                     #
#     - Common Integration tests test the driver through the instrument agent #
#     and common for all drivers (minimum requirement for ION ingestion)      #
###############################################################################
@attr('INT', group='mi')
class SamiIntegrationTest(InstrumentDriverIntegrationTestCase):
    def setUp(self):
        InstrumentDriverIntegrationTestCase.setUp(self)


###############################################################################
#                            QUALIFICATION TESTS                              #
# Device specific qualification tests are for doing final testing of ion      #
# integration.  The generally aren't used for instrument debugging and should #
# be tackled after all unit and integration tests are complete                #
###############################################################################
@attr('QUAL', group='mi')
class SamiQualificationTest(InstrumentDriverQualificationTestCase):
    def setUp(self):
        InstrumentDriverQualificationTestCase.setUp(self)

    def test_direct_access_telnet_mode(self):
        """
        @brief This test manually tests that the Instrument Driver properly supports direct access to the physical instrument. (telnet mode)
        """
        self.assert_direct_access_start_telnet()
        self.assertTrue(self.tcp_client)

        ###
        #   Add instrument specific code here.
        ###

        self.assert_direct_access_stop_telnet()

    def test_poll(self):
        '''
        No polling for a single sample
        '''

    def test_autosample(self):
        '''
        start and stop autosample and verify data particle
        '''

    def test_get_set_parameters(self):
        '''
        verify that all parameters can be get set properly, this includes
        ensuring that read only parameters fail on set.
        '''
        self.assert_enter_command_mode()

    def test_get_capabilities(self):
        """
        @brief Walk through all driver protocol states and verify capabilities
        returned by get_current_capabilities
        """
        self.assert_enter_command_mode()