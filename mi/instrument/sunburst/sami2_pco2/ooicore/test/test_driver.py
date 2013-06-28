"""
@package mi.instrument.sunburst.sami2_pco2.ooicore.test.test_driver
@file marine-integrations/mi/instrument/sunburst/sami2_pco2/ooicore/driver.py
@author Christopher Wingard
@brief Test cases for ooicore driver

USAGE:
 Make tests verbose and provide stdout
   * From the IDK
       $ bin/test_driver
       $ bin/test_driver -u [-t testname]
       $ bin/test_driver -i [-t testname]
       $ bin/test_driver -q [-t testname]
"""

__author__ = 'Christopher Wingard'
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

from mi.core.instrument.chunker import StringChunker
from mi.core.instrument.instrument_driver import DriverAsyncEvent
from mi.core.instrument.instrument_driver import DriverConnectionState
from mi.core.instrument.instrument_driver import DriverProtocolState

from ion.agents.instrument.instrument_agent import InstrumentAgentState
from ion.agents.instrument.direct_access.direct_access_server import DirectAccessTypes

from mi.instrument.sunburst.sami2_pco2.ooicore.driver import InstrumentDriver
from mi.instrument.sunburst.sami2_pco2.ooicore.driver import DataParticleType
from mi.instrument.sunburst.sami2_pco2.ooicore.driver import InstrumentCommand
from mi.instrument.sunburst.sami2_pco2.ooicore.driver import ProtocolState
from mi.instrument.sunburst.sami2_pco2.ooicore.driver import ProtocolEvent
from mi.instrument.sunburst.sami2_pco2.ooicore.driver import Capability
from mi.instrument.sunburst.sami2_pco2.ooicore.driver import Parameter
from mi.instrument.sunburst.sami2_pco2.ooicore.driver import Protocol
from mi.instrument.sunburst.sami2_pco2.ooicore.driver import Prompt
from mi.instrument.sunburst.sami2_pco2.ooicore.driver import NEWLINE
from mi.instrument.sunburst.sami2_pco2.ooicore.driver import SAMI_EPOCH
from mi.instrument.sunburst.sami2_pco2.ooicore.driver import SamiRegularStatusDataParticleKey
from mi.instrument.sunburst.sami2_pco2.ooicore.driver import SamiControlRecordDataParticleKey
from mi.instrument.sunburst.sami2_pco2.ooicore.driver import SamiErrorCodeDataParticleKey
from mi.instrument.sunburst.sami2_pco2.ooicore.driver import Pco2wSamiSampleDataParticleKey
from mi.instrument.sunburst.sami2_pco2.ooicore.driver import Pco2wDev1SampleDataParticleKey
from mi.instrument.sunburst.sami2_pco2.ooicore.driver import Pco2wConfigurationDataParticleKey

###
#   Driver parameters for the tests
###
InstrumentDriverTestCase.initialize(
    driver_module='mi.instrument.sunburst.sami2_pco2.ooicore.driver',
    driver_class="InstrumentDriver",

    instrument_agent_resource_id='V7HE4T',
    instrument_agent_name='sunburst_sami2_pco2_ooicore',
    instrument_agent_packet_config=DataParticleType(),

    driver_startup_config={}
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

###
# Driver constant definitions
###

###############################################################################
#                           DRIVER TEST MIXIN                                 #
#     Defines a set of constants and assert methods used for data particle    #
#     verification                                                            #
#                                                                             #
#  In python mixin classes are classes designed such that they wouldn't be    #
#  able to stand on their own, but are inherited by other classes generally   #
#  using multiple inheritance.                                                #
#                                                                             #
# This class defines a configuration structure for testing and common assert  #
# methods for validating data particles.                                      #
###############################################################################
class DriverTestMixinSub(DriverTestMixin):
    '''
    Mixin class used for storing data particle constants and common data
    assertion methods.
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

    ###
    #  Instrument output (driver input) Definitions
    ###
    # Configuration string received from the instrument via the L command
    # (clock set to 2014-01-01 00:00:00) with sampling set to start 540 days
    # (~18 months) later and stop 365 days after that. SAMI and Device1
    # (external SBE pump) are set to run every 60 minutes, but will be polled
    # on a regular schedule rather than autosampled. Device1 is not configured
    # to run after the SAMI and will run for 10 seconds. To configure the
    # instrument using this string, add a null byte (00) to the end of the
    # string.
    VALID_CONFIG_STRING = 'CEE90B0002C7EA0001E133800A000E100402000E10010B' + \
                          '000000000D000000000D000000000D07' + \
                          '1020FF54181C01003814' + \
                          '000000000000000000000000000000000000000000000000000' + \
                          '000000000000000000000000000000000000000000000000000' + \
                          '0000000000000000000000000000' + \
                          'FFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFF' + \
                          'FFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFF' + \
                          'FFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFF' + \
                          'FFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFF' + \
                          'FFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFF' + \
                          'FFFFFFFFFFFFFFFFFFFFFFFFFFFFF' + NEWLINE

    # Regular Status Message (response to S0 command)
    VALID_STATUS_MESSAGE = ':CEE90B1B004100000100000000021254' + NEWLINE

    # Data records -- SAMI and Device1 (external pump) (responses to R0 and R1
    # commands, respectively)
    VALID_R0_BLANK_SAMPLE = '*542705CEE91CC800400019096206800730074C2CE042' + \
                            '74003B0018096106800732074E0D82066124' + NEWLINE
    VALID_R0_DATA_SAMPLE = '*542704CEE91CC8003B001909620155073003E908A1232' + \
                           'D0043001A09620154072F03EA0D92065F46' + NEWLINE
    VALID_R1_SAMPLE = '*540711CEE91DE2CE' + NEWLINE

    # Control records
    VALID_CONTROL_RECORD = '*541280CEE90B170041000001000000000200AF' + NEWLINE

    # Error records (valid error codes are between 0x00 and 0x11)
    VALID_ERROR_CODE = '?05' + NEWLINE

    ###
    #  Parameter and Type Definitions
    ###
    _driver_parameters = {
        # Parameters defined in the IOS
        Parameter.LAUNCH_TIME:              {TYPE: int, READONLY: True, DA: False, STARTUP: False,
                                             DEFAULT: 0x00000000, VALUE: 0xCEE90B00},
        Parameter.START_TIME_FROM_LAUNCH:   {TYPE: int, READONLY: True, DA: False, STARTUP: False,
                                             DEFAULT: 0x02C7EA00, VALUE: 0x02C7EA00},
        Parameter.STOP_TIME_FROM_START:     {TYPE: int, READONLY: True, DA: False, STARTUP: False,
                                             DEFAULT: 0x01E13380, VALUE: 0x01E13380},
        Parameter.MODE_BITS:                {TYPE: int, READONLY: True, DA: False, STARTUP: False,
                                             DEFAULT: 0x0A, VALUE: 0x0A},
        Parameter.SAMI_SAMPLE_INTERVAL:     {TYPE: int, READONLY: True, DA: False, STARTUP: False,
                                             DEFAULT: 0x000E10, VALUE: 0x000E10},
        Parameter.SAMI_DRIVER_VERSION:      {TYPE: int, READONLY: True, DA: False, STARTUP: False,
                                             DEFAULT: 0x04, VALUE: 0x04},
        Parameter.SAMI_PARAMS_POINTER:      {TYPE: int, READONLY: True, DA: False, STARTUP: False,
                                             DEFAULT: 0x02, VALUE: 0x02},
        Parameter.DEVICE1_SAMPLE_INTERVAL:  {TYPE: int, READONLY: True, DA: False, STARTUP: False,
                                             DEFAULT: 0x000E10, VALUE: 0x000E10},
        Parameter.DEVICE1_DRIVER_VERSION:   {TYPE: int, READONLY: True, DA: False, STARTUP: False,
                                             DEFAULT: 0x01, VALUE: 0x01},
        Parameter.DEVICE1_PARAMS_POINTER:   {TYPE: int, READONLY: True, DA: False, STARTUP: False,
                                             DEFAULT: 0x0B, VALUE: 0x0B},
        Parameter.DEVICE2_SAMPLE_INTERVAL:  {TYPE: int, READONLY: True, DA: False, STARTUP: False,
                                             DEFAULT: 0x000000, VALUE: 0x000000},
        Parameter.DEVICE2_DRIVER_VERSION:   {TYPE: int, READONLY: True, DA: False, STARTUP: False,
                                             DEFAULT: 0x00, VALUE: 0x00},
        Parameter.DEVICE2_PARAMS_POINTER:   {TYPE: int, READONLY: True, DA: False, STARTUP: False,
                                             DEFAULT: 0x0D, VALUE: 0x0D},
        Parameter.DEVICE3_SAMPLE_INTERVAL:  {TYPE: int, READONLY: True, DA: False, STARTUP: False,
                                             DEFAULT: 0x000000, VALUE: 0x000000},
        Parameter.DEVICE3_DRIVER_VERSION:   {TYPE: int, READONLY: True, DA: False, STARTUP: False,
                                             DEFAULT: 0x00, VALUE: 0x00},
        Parameter.DEVICE3_PARAMS_POINTER:   {TYPE: int, READONLY: True, DA: False, STARTUP: False,
                                             DEFAULT: 0x0D, VALUE: 0x0D},
        Parameter.PRESTART_SAMPLE_INTERVAL: {TYPE: int, READONLY: True, DA: False, STARTUP: False,
                                             DEFAULT: 0x000000, VALUE: 0x000000},
        Parameter.PRESTART_DRIVER_VERSION:  {TYPE: int, READONLY: True, DA: False, STARTUP: False,
                                             DEFAULT: 0x00, VALUE: 0x00},
        Parameter.PRESTART_PARAMS_POINTER:  {TYPE: int, READONLY: True, DA: False, STARTUP: False,
                                             DEFAULT: 0x0D, VALUE: 0x0D},
        Parameter.GLOBAL_CONFIGURATION:     {TYPE: int, READONLY: True, DA: False, STARTUP: False,
                                             DEFAULT: 0x07, VALUE: 0x07},
        Parameter.PUMP_PULSE:               {TYPE: int, READONLY: True, DA: False, STARTUP: False,
                                             DEFAULT: 0x10, VALUE: 0x10},
        Parameter.PUMP_DURATION:            {TYPE: int, READONLY: True, DA: False, STARTUP: False,
                                             DEFAULT: 0x20, VALUE: 0x20},
        Parameter.SAMPLES_PER_MEASUREMENT:  {TYPE: int, READONLY: True, DA: False, STARTUP: False,
                                             DEFAULT: 0xFF, VALUE: 0xFF},
        Parameter.CYCLES_BETWEEN_BLANKS:    {TYPE: int, READONLY: True, DA: False, STARTUP: False,
                                             DEFAULT: 0x54, VALUE: 0x54},
        Parameter.NUMBER_REAGENT_CYCLES:    {TYPE: int, READONLY: True, DA: False, STARTUP: False,
                                             DEFAULT: 0x18, VALUE: 0x18},
        Parameter.NUMBER_BLANK_CYCLES:      {TYPE: int, READONLY: True, DA: False, STARTUP: False,
                                             DEFAULT: 0x1C, VALUE: 0x1C},
        Parameter.FLUSH_PUMP_INTERVAL:      {TYPE: int, READONLY: True, DA: False, STARTUP: False,
                                             DEFAULT: 0x01, VALUE: 0x01},
        Parameter.BIT_SWITCHES:             {TYPE: int, READONLY: True, DA: False, STARTUP: False,
                                             DEFAULT: 0x00, VALUE: 0x00},
        Parameter.NUMBER_EXTRA_PUMP_CYCLES: {TYPE: int, READONLY: True, DA: False, STARTUP: False,
                                             DEFAULT: 0x38, VALUE: 0x38},
        Parameter.EXTERNAL_PUMP_SETTINGS:   {TYPE: int, READONLY: True, DA: False, STARTUP: False,
                                             DEFAULT: 0x14, VALUE: 0x14}
    }

    # [TODO] Consider moving to base class as these apply to both PCO2 and pH
    _driver_capabilities = {
        # capabilities defined in the IOS
        Capability.ACQUIRE_STATUS:      {STATES: [ProtocolState.COMMAND]},
        Capability.ACQUIRE_SAMPLE:      {STATES: [ProtocolState.COMMAND]}
    }

    # [TODO] Consider moving to base class as these apply to both PCO2 and pH
    _regular_status_parameters = {
        # SAMI Regular Status Messages (S0)
        SamiRegularStatusDataParticleKey.ELAPSED_TIME_CONFIG:       {TYPE: int, VALUE: 0xCEE90B1B, REQUIRED: True},
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
        SamiRegularStatusDataParticleKey.NUM_DATA_RECORDS:          {TYPE: int, VALUE: 0x000001, REQUIRED: True},
        SamiRegularStatusDataParticleKey.NUM_ERROR_RECORDS:         {TYPE: int, VALUE: 0x000000, REQUIRED: True},
        SamiRegularStatusDataParticleKey.NUM_BYTES_STORED:          {TYPE: int, VALUE: 0x000212, REQUIRED: True},
        SamiRegularStatusDataParticleKey.CHECKSUM:                  {TYPE: int, VALUE: 0x54, REQUIRED: True}
    }

    # [TODO] Consider moving to base class as these apply to both PCO2 and pH
    _control_record_parameters = {
        SamiControlRecordDataParticleKey.UNIQUE_ID:                {TYPE: int, VALUE: 0x54, REQUIRED: True},
        SamiControlRecordDataParticleKey.RECORD_LENGTH:            {TYPE: int, VALUE: 0x12, REQUIRED: True},
        SamiControlRecordDataParticleKey.RECORD_TYPE:              {TYPE: int, VALUE: 0x80,  REQUIRED: True},
        SamiControlRecordDataParticleKey.RECORD_TIME:              {TYPE: int, VALUE: 0xCEE90B17, REQUIRED: True},
        SamiControlRecordDataParticleKey.CLOCK_ACTIVE:             {TYPE: bool, VALUE: True, REQUIRED: True},
        SamiControlRecordDataParticleKey.RECORDING_ACTIVE:         {TYPE: bool, VALUE: False, REQUIRED: True},
        SamiControlRecordDataParticleKey.RECORD_END_ON_TIME:       {TYPE: bool, VALUE: False, REQUIRED: True},
        SamiControlRecordDataParticleKey.RECORD_MEMORY_FULL:       {TYPE: bool, VALUE: False, REQUIRED: True},
        SamiControlRecordDataParticleKey.RECORD_END_ON_ERROR:      {TYPE: bool, VALUE: False, REQUIRED: True},
        SamiControlRecordDataParticleKey.DATA_DOWNLOAD_OK:         {TYPE: bool, VALUE: False, REQUIRED: True},
        SamiControlRecordDataParticleKey.FLASH_MEMORY_OPEN:        {TYPE: bool, VALUE: True, REQUIRED: True},
        SamiControlRecordDataParticleKey.BATTERY_LOW_PRESTART:     {TYPE: bool, VALUE: False, REQUIRED: True},
        SamiControlRecordDataParticleKey.BATTERY_LOW_MEASUREMENT:  {TYPE: bool, VALUE: False, REQUIRED: True},
        SamiControlRecordDataParticleKey.BATTERY_LOW_BANK:         {TYPE: bool, VALUE: False, REQUIRED: True},
        SamiControlRecordDataParticleKey.BATTERY_LOW_EXTERNAL:     {TYPE: bool, VALUE: False, REQUIRED: True},
        SamiControlRecordDataParticleKey.EXTERNAL_DEVICE1_FAULT:   {TYPE: bool, VALUE: False, REQUIRED: True},
        SamiControlRecordDataParticleKey.EXTERNAL_DEVICE2_FAULT:   {TYPE: bool, VALUE: False, REQUIRED: True},
        SamiControlRecordDataParticleKey.EXTERNAL_DEVICE3_FAULT:   {TYPE: bool, VALUE: False, REQUIRED: True},
        SamiControlRecordDataParticleKey.FLASH_ERASED:             {TYPE: bool, VALUE: False, REQUIRED: True},
        SamiControlRecordDataParticleKey.POWER_ON_INVALID:         {TYPE: bool, VALUE: False, REQUIRED: True},
        SamiControlRecordDataParticleKey.NUM_DATA_RECORDS:         {TYPE: int, VALUE: 0x000001, REQUIRED: True},
        SamiControlRecordDataParticleKey.NUM_ERROR_RECORDS:        {TYPE: int, VALUE: 0x000000, REQUIRED: True},
        SamiControlRecordDataParticleKey.NUM_BYTES_STORED:         {TYPE: int, VALUE: 0x000200, REQUIRED: True},
        SamiControlRecordDataParticleKey.CHECKSUM:                 {TYPE: int, VALUE: 0xAF, REQUIRED: True},
    }

    _sami_data_sample_parameters = {
        # SAMI Type 4/5 sample (in this case it is a Type 4)
        Pco2wSamiSampleDataParticleKey.UNIQUE_ID:           {TYPE: int, VALUE: 0x54, REQUIRED: True},
        Pco2wSamiSampleDataParticleKey.RECORD_LENGTH:       {TYPE: int, VALUE: 0x27, REQUIRED: True},
        Pco2wSamiSampleDataParticleKey.RECORD_TYPE:         {TYPE: int, VALUE: 0x04, REQUIRED: True},
        Pco2wSamiSampleDataParticleKey.RECORD_TIME:         {TYPE: int, VALUE: 0xCEE91CC8, REQUIRED: True},
        Pco2wSamiSampleDataParticleKey.LIGHT_MEASUREMENTS:  {TYPE: list, VALUE: [0x003B, 0x0019, 0x0962, 0x0155,
                                                                                 0x0730, 0x03E9, 0x08A1, 0x232D,
                                                                                 0x0043, 0x001A, 0x0962, 0x0154,
                                                                                 0x072F, 0x03EA], REQUIRED: True},
        Pco2wSamiSampleDataParticleKey.VOLTAGE_BATTERY:     {TYPE: int, VALUE: 0x0D92, REQUIRED: True},
        Pco2wSamiSampleDataParticleKey.THERMISTER_RAW:      {TYPE: int, VALUE: 0x065F, REQUIRED: True},
        Pco2wSamiSampleDataParticleKey.CHECKSUM:            {TYPE: int, VALUE: 0x46, REQUIRED: True}
    }

    _sami_blank_sample_parameters = {
        # SAMI Type 4/5 sample (in this case it is a Type 5)
        Pco2wSamiSampleDataParticleKey.UNIQUE_ID:           {TYPE: int, VALUE: 0x54, REQUIRED: True},
        Pco2wSamiSampleDataParticleKey.RECORD_LENGTH:       {TYPE: int, VALUE: 0x27, REQUIRED: True},
        Pco2wSamiSampleDataParticleKey.RECORD_TYPE:         {TYPE: int, VALUE: 0x05, REQUIRED: True},
        Pco2wSamiSampleDataParticleKey.RECORD_TIME:         {TYPE: int, VALUE: 0xCEE91CC8, REQUIRED: True},
        Pco2wSamiSampleDataParticleKey.LIGHT_MEASUREMENTS:  {TYPE: list, VALUE: [0x0040, 0x0019, 0x0962, 0x0680, 0x0730,
                                                                                 0x074C, 0x2CE0, 0x4274, 0x003B, 0x0018,
                                                                                 0x0961, 0x0680, 0x0732, 0x074E],
                                                             REQUIRED: True},
        Pco2wSamiSampleDataParticleKey.VOLTAGE_BATTERY:     {TYPE: int, VALUE: 0x0D82, REQUIRED: True},
        Pco2wSamiSampleDataParticleKey.THERMISTER_RAW:      {TYPE: int, VALUE: 0x0661, REQUIRED: True},
        Pco2wSamiSampleDataParticleKey.CHECKSUM:            {TYPE: int, VALUE: 0x24, REQUIRED: True}
    }

    _dev1_sample_parameters = {
        # Device 1 (external pump) Type 17 sample
        Pco2wDev1SampleDataParticleKey.UNIQUE_ID:        {TYPE: int, VALUE: 0x54, REQUIRED: True},
        Pco2wDev1SampleDataParticleKey.RECORD_LENGTH:    {TYPE: int, VALUE: 0x07, REQUIRED: True},
        Pco2wDev1SampleDataParticleKey.RECORD_TYPE:      {TYPE: int, VALUE: 0x11,  REQUIRED: True},
        Pco2wDev1SampleDataParticleKey.RECORD_TIME:      {TYPE: int, VALUE: 0xCEE91DE2, REQUIRED: True},
        Pco2wDev1SampleDataParticleKey.CHECKSUM:         {TYPE: int, VALUE: 0xCE, REQUIRED: True}
    }

    # [TODO] Several of these particles could come from a share base class.
    _configuration_parameters = {
        # Configuration settings
        Pco2wConfigurationDataParticleKey.LAUNCH_TIME:                  {TYPE: int, VALUE: 0xCEE90B00, REQUIRED: True},
        Pco2wConfigurationDataParticleKey.START_TIME_OFFSET:            {TYPE: int, VALUE: 0x02C7EA00, REQUIRED: True},
        Pco2wConfigurationDataParticleKey.RECORDING_TIME:               {TYPE: int, VALUE: 0x01E13380, REQUIRED: True},
        Pco2wConfigurationDataParticleKey.PMI_SAMPLE_SCHEDULE:          {TYPE: bool, VALUE: False,  REQUIRED: True},
        Pco2wConfigurationDataParticleKey.SAMI_SAMPLE_SCHEDULE:         {TYPE: bool, VALUE: True,  REQUIRED: True},
        Pco2wConfigurationDataParticleKey.SLOT1_FOLLOWS_SAMI_SCHEDULE:  {TYPE: bool, VALUE: False,  REQUIRED: True},
        Pco2wConfigurationDataParticleKey.SLOT1_INDEPENDENT_SCHEDULE:   {TYPE: bool, VALUE: True, REQUIRED: True},
        Pco2wConfigurationDataParticleKey.SLOT2_FOLLOWS_SAMI_SCHEDULE:  {TYPE: bool, VALUE: False,  REQUIRED: True},
        Pco2wConfigurationDataParticleKey.SLOT2_INDEPENDENT_SCHEDULE:   {TYPE: bool, VALUE: False, REQUIRED: True},
        Pco2wConfigurationDataParticleKey.SLOT3_FOLLOWS_SAMI_SCHEDULE:  {TYPE: bool, VALUE: False,  REQUIRED: True},
        Pco2wConfigurationDataParticleKey.SLOT3_INDEPENDENT_SCHEDULE:   {TYPE: bool, VALUE: False, REQUIRED: True},
        Pco2wConfigurationDataParticleKey.TIMER_INTERVAL_SAMI:          {TYPE: int, VALUE: 0x000E10, REQUIRED: True},
        Pco2wConfigurationDataParticleKey.DRIVER_ID_SAMI:               {TYPE: int, VALUE: 0x04,  REQUIRED: True},
        Pco2wConfigurationDataParticleKey.PARAMETER_POINTER_SAMI:       {TYPE: int, VALUE: 0x02,  REQUIRED: True},
        Pco2wConfigurationDataParticleKey.TIMER_INTERVAL_DEVICE1:       {TYPE: int, VALUE: 0x000E10, REQUIRED: True},
        Pco2wConfigurationDataParticleKey.DRIVER_ID_DEVICE1:            {TYPE: int, VALUE: 0x01,  REQUIRED: True},
        Pco2wConfigurationDataParticleKey.PARAMETER_POINTER_DEVICE1:    {TYPE: int, VALUE: 0x0B, REQUIRED: True},
        Pco2wConfigurationDataParticleKey.TIMER_INTERVAL_DEVICE2:       {TYPE: int, VALUE: 0x000000, REQUIRED: True},
        Pco2wConfigurationDataParticleKey.DRIVER_ID_DEVICE2:            {TYPE: int, VALUE: 0x00,  REQUIRED: True},
        Pco2wConfigurationDataParticleKey.PARAMETER_POINTER_DEVICE2:    {TYPE: int, VALUE: 0x0D, REQUIRED: True},
        Pco2wConfigurationDataParticleKey.TIMER_INTERVAL_DEVICE3:       {TYPE: int, VALUE: 0x000000, REQUIRED: True},
        Pco2wConfigurationDataParticleKey.DRIVER_ID_DEVICE3:            {TYPE: int, VALUE: 0x00,  REQUIRED: True},
        Pco2wConfigurationDataParticleKey.PARAMETER_POINTER_DEVICE3:    {TYPE: int, VALUE: 0x0D, REQUIRED: True},
        Pco2wConfigurationDataParticleKey.TIMER_INTERVAL_PRESTART:      {TYPE: int, VALUE: 0x000000, REQUIRED: True},
        Pco2wConfigurationDataParticleKey.DRIVER_ID_PRESTART:           {TYPE: int, VALUE: 0x00, REQUIRED: True},
        Pco2wConfigurationDataParticleKey.PARAMETER_POINTER_PRESTART:   {TYPE: int, VALUE: 0x0D, REQUIRED: True},
        Pco2wConfigurationDataParticleKey.USE_BAUD_RATE_57600:          {TYPE: bool, VALUE: True, REQUIRED: True},
        Pco2wConfigurationDataParticleKey.SEND_RECORD_TYPE:             {TYPE: bool, VALUE: True, REQUIRED: True},
        Pco2wConfigurationDataParticleKey.SEND_LIVE_RECORDS:            {TYPE: bool, VALUE: True, REQUIRED: True},
        Pco2wConfigurationDataParticleKey.EXTEND_GLOBAL_CONFIG:         {TYPE: bool, VALUE: False, REQUIRED: True},
        Pco2wConfigurationDataParticleKey.PUMP_PULSE:                   {TYPE: int, VALUE: 0x10, REQUIRED: True},
        Pco2wConfigurationDataParticleKey.PUMP_ON_TO_MEAURSURE:         {TYPE: int, VALUE: 0x20, REQUIRED: True},
        Pco2wConfigurationDataParticleKey.SAMPLES_PER_MEASURE:          {TYPE: int, VALUE: 0xFF, REQUIRED: True},
        Pco2wConfigurationDataParticleKey.CYCLES_BETWEEN_BLANKS:        {TYPE: int, VALUE: 0x54, REQUIRED: True},
        Pco2wConfigurationDataParticleKey.NUM_REAGENT_CYCLES:           {TYPE: int, VALUE: 0x18, REQUIRED: True},
        Pco2wConfigurationDataParticleKey.NUM_BLANK_CYCLES:             {TYPE: int, VALUE: 0x1C, REQUIRED: True},
        Pco2wConfigurationDataParticleKey.FLUSH_PUMP_INTERVAL:          {TYPE: int, VALUE: 0x01,  REQUIRED: True},
        Pco2wConfigurationDataParticleKey.DISABLE_START_BLANK_FLUSH:    {TYPE: bool, VALUE: False, REQUIRED: True},
        Pco2wConfigurationDataParticleKey.MEASURE_AFTER_PUMP_PULSE:     {TYPE: bool, VALUE: False, REQUIRED: True},
        Pco2wConfigurationDataParticleKey.CYCLE_RATE:                   {TYPE: int,  VALUE: 0x38, REQUIRED: True},
        Pco2wConfigurationDataParticleKey.EXTERNAL_PUMP_SETTING:        {TYPE: int,  VALUE: 0x14, REQUIRED: True}
    }

    # [TODO] Move to base class
    _error_code_parameters = {
        # Error codes
        SamiErrorCodeDataParticleKey.ERROR_CODE:        {TYPE: int, VALUE: 0x05, REQUIRED: True},
    }

    ###
    #   Driver Parameter Methods
    ###
    def assertSampleDataParticle(self, data_particle):
        '''
        Verify a particle is a known particle to this driver and verify the
        particle is correct.
        @param data_particle: Data particle of unknown type produced by the driver
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
                                         DataParticleType.REGULAR_STATUS)
        self.assert_data_particle_parameters(data_particle,
                                             self._regular_status_parameters,
                                             verify_values)

    def assert_particle_control_record(self, data_particle, verify_values=False):
        '''
        Verify control_record particle
        @param data_particle: SamiControlRecordDataParticle data particle
        @param verify_values: bool, should we verify parameter values
        '''
        self.assert_data_particle_keys(SamiControlRecordDataParticleKey,
                                       self._control_record_parameters)
        self.assert_data_particle_header(data_particle,
                                         DataParticleType.CONTROL_RECORD)
        self.assert_data_particle_parameters(data_particle,
                                             self._control_record_parameters,
                                             verify_values)

    def assert_particle_sami_data_sample(self, data_particle, verify_values=False):
        '''
        Verify sami_data_sample particle (Type 4)
        @param data_particle: Pco2wSamiSampleDataParticle data particle
        @param verify_values: bool, should we verify parameter values
        '''
        self.assert_data_particle_keys(Pco2wSamiSampleDataParticleKey,
                                       self._sami_data_sample_parameters)
        self.assert_data_particle_header(data_particle,
                                         DataParticleType.SAMI_SAMPLE)
        self.assert_data_particle_parameters(data_particle,
                                             self._sami_data_sample_parameters,
                                             verify_values)

    def assert_particle_sami_blank_sample(self, data_particle, verify_values=False):
        '''
        Verify sami_blank_sample particle (Type 5)
        @param data_particle: Pco2wSamiSampleDataParticle data particle
        @param verify_values: bool, should we verify parameter values
        '''
        self.assert_data_particle_keys(Pco2wSamiSampleDataParticleKey,
                                       self._sami_blank_sample_parameters)
        self.assert_data_particle_header(data_particle,
                                         DataParticleType.SAMI_SAMPLE)
        self.assert_data_particle_parameters(data_particle,
                                             self._sami_blank_sample_parameters,
                                             verify_values)

    def assert_particle_dev1_sample(self, data_particle, verify_values=False):
        '''
        Verify dev1_sample particle
        @param data_particle: Pco2wDev1SampleDataParticle data particle
        @param verify_values: bool, should we verify parameter values
        '''
        self.assert_data_particle_keys(Pco2wDev1SampleDataParticleKey,
                                       self._dev1_sample_parameters)
        self.assert_data_particle_header(data_particle,
                                         DataParticleType.DEV1_SAMPLE)
        self.assert_data_particle_parameters(data_particle,
                                             self._dev1_sample_parameters,
                                             verify_values)

    def assert_particle_configuration(self, data_particle, verify_values=False):
        '''
        Verify configuration particle
        @param data_particle: Pco2wConfigurationDataParticle data particle
        @param verify_values: bool, should we verify parameter values
        '''
        self.assert_data_particle_keys(Pco2wConfigurationDataParticleKey,
                                       self._configuration_parameters)
        self.assert_data_particle_header(data_particle,
                                         DataParticleType.CONFIGURATION)
        self.assert_data_particle_parameters(data_particle,
                                             self._configuration_parameters,
                                             verify_values)

    def assert_particle_error_code(self, data_particle, verify_values=False):
        '''
        Verify error_code particle
        @param data_particle: SamiErrorCodeDataParticle data particle
        @param verify_values: bool, should we verify parameter values
        '''
        self.assert_data_particle_keys(SamiErrorCodeDataParticleKey,
                                       self._error_code_parameters)
        self.assert_data_particle_header(data_particle,
                                         DataParticleType.ERROR_CODE)
        self.assert_data_particle_parameters(data_particle,
                                             self._error_code_parameters,
                                             verify_values)


###############################################################################
#                                UNIT TESTS                                   #
#         Unit Tests: test the method calls and parameters using Mock.        #
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
        Verify that all driver enumeration has no duplicate values that might
        cause confusion. Also do a little extra validation for the Capabilites
        """
        self.assert_enum_has_no_duplicates(DataParticleType())
        self.assert_enum_has_no_duplicates(ProtocolState())
        self.assert_enum_has_no_duplicates(ProtocolEvent())
        self.assert_enum_has_no_duplicates(Parameter())
        self.assert_enum_has_no_duplicates(InstrumentCommand())

        # Test capabilites for duplicates, then verify that capabilities is a
        # subset of proto events
        self.assert_enum_has_no_duplicates(Capability())
        self.assert_enum_complete(Capability(), ProtocolEvent())

    def test_chunker(self):
        """
        Test the chunker and verify the particles created.
        """
        chunker = StringChunker(Protocol.sieve_function)

        self.assert_chunker_sample(chunker, self.VALID_STATUS_MESSAGE)
        self.assert_chunker_sample_with_noise(chunker, self.VALID_STATUS_MESSAGE)
        self.assert_chunker_fragmented_sample(chunker, self.VALID_STATUS_MESSAGE, 32)
        self.assert_chunker_combined_sample(chunker, self.VALID_STATUS_MESSAGE)

        self.assert_chunker_sample(chunker, self.VALID_CONTROL_RECORD)
        self.assert_chunker_sample_with_noise(chunker, self.VALID_CONTROL_RECORD)
        self.assert_chunker_fragmented_sample(chunker, self.VALID_CONTROL_RECORD, 32)
        self.assert_chunker_combined_sample(chunker, self.VALID_CONTROL_RECORD)

        self.assert_chunker_sample(chunker, self.VALID_R0_BLANK_SAMPLE)
        self.assert_chunker_sample_with_noise(chunker, self.VALID_R0_BLANK_SAMPLE)
        self.assert_chunker_fragmented_sample(chunker, self.VALID_R0_BLANK_SAMPLE, 32)
        self.assert_chunker_combined_sample(chunker, self.VALID_R0_BLANK_SAMPLE)

        self.assert_chunker_sample(chunker, self.VALID_R0_DATA_SAMPLE)
        self.assert_chunker_sample_with_noise(chunker, self.VALID_R0_DATA_SAMPLE)
        self.assert_chunker_fragmented_sample(chunker, self.VALID_R0_DATA_SAMPLE, 32)
        self.assert_chunker_combined_sample(chunker, self.VALID_R0_DATA_SAMPLE)

        self.assert_chunker_sample(chunker, self.VALID_R1_SAMPLE)
        self.assert_chunker_sample_with_noise(chunker, self.VALID_R1_SAMPLE)
        self.assert_chunker_fragmented_sample(chunker, self.VALID_R1_SAMPLE, 8)
        self.assert_chunker_combined_sample(chunker, self.VALID_R1_SAMPLE)

        self.assert_chunker_sample(chunker, self.VALID_CONFIG_STRING)
        self.assert_chunker_sample_with_noise(chunker, self.VALID_CONFIG_STRING)
        self.assert_chunker_fragmented_sample(chunker, self.VALID_CONFIG_STRING, 32)
        self.assert_chunker_combined_sample(chunker, self.VALID_CONFIG_STRING)

        self.assert_chunker_sample(chunker, self.VALID_ERROR_CODE)
        self.assert_chunker_sample_with_noise(chunker, self.VALID_ERROR_CODE)
        self.assert_chunker_fragmented_sample(chunker, self.VALID_ERROR_CODE, 2)
        self.assert_chunker_combined_sample(chunker, self.VALID_ERROR_CODE)

    def test_got_data(self):
        """
        Verify sample data passed through the got data method produces the
        correct data particles
        """
        # Create and initialize the instrument driver with a mock port agent
        driver = InstrumentDriver(self._got_data_event_callback)
        self.assert_initialize_driver(driver)

        self.assert_raw_particle_published(driver, True)

        # Start validating data particles
        self.assert_particle_published(driver, self.VALID_STATUS_MESSAGE, self.assert_particle_regular_status, True)
        self.assert_particle_published(driver, self.VALID_CONTROL_RECORD, self.assert_particle_control_record, True)
        self.assert_particle_published(driver, self.VALID_R0_BLANK_SAMPLE, self.assert_particle_sami_blank_sample, True)
        self.assert_particle_published(driver, self.VALID_R0_DATA_SAMPLE, self.assert_particle_sami_data_sample, True)
        self.assert_particle_published(driver, self.VALID_R1_SAMPLE, self.assert_particle_dev1_sample, True)
        self.assert_particle_published(driver, self.VALID_CONFIG_STRING, self.assert_particle_configuration, True)
        self.assert_particle_published(driver, self.VALID_ERROR_CODE, self.assert_particle_error_code, True)

    def test_protocol_filter_capabilities(self):
        """
        This tests driver filter_capabilities. Iterate through available
        capabilities, and verify that they can pass successfully through the
        filter. Test silly made up capabilities to verify they are blocked by
        filter.
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


###############################################################################
#                            INTEGRATION TESTS                                #
#     Integration test test the direct driver / instrument interaction        #
#     but making direct calls via zeromq.                                     #
#     - Common Integration tests test the driver through the instrument agent #
#     and common for all drivers (minimum requirement for ION ingestion)      #
###############################################################################
@attr('INT', group='mi')
class DriverIntegrationTest(InstrumentDriverIntegrationTestCase):
    def setUp(self):
        InstrumentDriverIntegrationTestCase.setUp(self)


###############################################################################
#                            QUALIFICATION TESTS                              #
# Device specific qualification tests are for doing final testing of ion      #
# integration.  The generally aren't used for instrument debugging and should #
# be tackled after all unit and integration tests are complete                #
###############################################################################
@attr('QUAL', group='mi')
class DriverQualificationTest(InstrumentDriverQualificationTestCase):
    def setUp(self):
        InstrumentDriverQualificationTestCase.setUp(self)

    def test_direct_access_telnet_mode(self):
        """
        @brief This test manually tests that the Instrument Driver properly
        supports direct access to the physical instrument. (telnet mode)
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
