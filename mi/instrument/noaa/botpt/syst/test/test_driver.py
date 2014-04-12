"""
@package mi.instrument.noaa.syst.ooicore.test.test_driver
@file marine-integrations/mi/instrument/noaa/syst/ooicore/driver.py
@author David Everett
@brief Test cases for ooicore driver

USAGE:
 Make tests verbose and provide stdout
   * From the IDK
       $ bin/test_driver
       $ bin/test_driver -u [-t testname]
       $ bin/test_driver -i [-t testname]
       $ bin/test_driver -q [-t testname]
"""
from mi.core.instrument.data_particle import RawDataParticle
from mi.instrument.noaa.botpt.test.test_driver import BotptDriverUnitTest

__author__ = 'David Everett'
__license__ = 'Apache 2.0'

from nose.plugins.attrib import attr

from mi.core.log import get_logger

log = get_logger()

# MI imports.
from mi.idk.unit_test import InstrumentDriverTestCase, ParameterTestConfigKey, AgentCapabilityType
from mi.idk.unit_test import InstrumentDriverIntegrationTestCase
from mi.idk.unit_test import InstrumentDriverQualificationTestCase
from mi.idk.unit_test import DriverTestMixin

from mi.core.instrument.instrument_driver import DriverParameter
from mi.core.instrument.instrument_driver import DriverProtocolState

from pyon.agent.agent import ResourceAgentState

from mi.instrument.noaa.botpt.syst.driver import InstrumentDriver, SYSTStatusParticleKey, SYSTStatusParticle
from mi.instrument.noaa.botpt.syst.driver import DataParticleType
from mi.instrument.noaa.botpt.syst.driver import InstrumentCommand
from mi.instrument.noaa.botpt.syst.driver import ProtocolState
from mi.instrument.noaa.botpt.syst.driver import ProtocolEvent
from mi.instrument.noaa.botpt.syst.driver import Capability
from mi.instrument.noaa.botpt.syst.driver import Protocol
from mi.instrument.noaa.botpt.syst.driver import NEWLINE

###
#   Driver parameters for the tests
###
InstrumentDriverTestCase.initialize(
    driver_module='mi.instrument.noaa.botpt.syst.driver',
    driver_class="InstrumentDriver",

    instrument_agent_resource_id='DZWXL3',
    instrument_agent_name='noaa_syst_ooicore',
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
#   Driver constant definitions
###

INVALID_SAMPLE = 'SYS1T,2014/04/07 21:23:18,*BOTPT BPR' + NEWLINE + 'NANO,123' + NEWLINE + 'grep root/bin' + NEWLINE

STATUS = '''SYST,2014/04/07 21:23:18,*BOTPT BPR and tilt instrument controller
SYST,2014/04/07 21:23:18,*ts7550n3
SYST,2014/04/07 21:23:18,*System uptime
SYST,2014/04/07 21:23:18,* 21:17:01 up 13 days, 20:11,  0 users,  load average: 0.00, 0.00, 0.00
SYST,2014/04/07 21:23:18,*Memory stats
SYST,2014/04/07 21:23:18,*             total       used       free     shared    buffers     cached
SYST,2014/04/07 21:23:18,*Mem:         62888      18508      44380          0       2268       5120
SYST,2014/04/07 21:23:18,*-/+ buffers/cache:      11120      51768
SYST,2014/04/07 21:23:18,*Swap:            0          0          0
SYST,2014/04/07 21:23:18,*MemTotal:        62888 kB
SYST,2014/04/07 21:23:18,*MemFree:         44404 kB
SYST,2014/04/07 21:23:18,*Buffers:          2268 kB
SYST,2014/04/07 21:23:18,*Cached:           5120 kB
SYST,2014/04/07 21:23:18,*SwapCached:          0 kB
SYST,2014/04/07 21:23:18,*Active:           9936 kB
SYST,2014/04/07 21:23:18,*Inactive:         3440 kB
SYST,2014/04/07 21:23:18,*SwapTotal:           0 kB
SYST,2014/04/07 21:23:18,*SwapFree:            0 kB
SYST,2014/04/07 21:23:18,*Dirty:               0 kB
SYST,2014/04/07 21:23:18,*Writeback:           0 kB
SYST,2014/04/07 21:23:18,*AnonPages:        6008 kB
SYST,2014/04/07 21:23:18,*Mapped:           3976 kB
SYST,2014/04/07 21:23:18,*Slab:             3096 kB
SYST,2014/04/07 21:23:18,*SReclaimable:      804 kB
SYST,2014/04/07 21:23:18,*SUnreclaim:       2292 kB
SYST,2014/04/07 21:23:18,*PageTables:        512 kB
SYST,2014/04/07 21:23:18,*NFS_Unstable:        0 kB
SYST,2014/04/07 21:23:18,*Bounce:              0 kB
SYST,2014/04/07 21:23:18,*CommitLimit:     31444 kB
SYST,2014/04/07 21:23:18,*Committed_AS:   167276 kB
SYST,2014/04/07 21:23:18,*VmallocTotal:   188416 kB
SYST,2014/04/07 21:23:18,*VmallocUsed:         0 kB
SYST,2014/04/07 21:23:18,*VmallocChunk:   188416 kB
SYST,2014/04/07 21:23:18,*Listening network services
SYST,2014/04/07 21:23:18,*tcp        0      0 *:9337-commands         *:*                     LISTEN
SYST,2014/04/07 21:23:18,*tcp        0      0 *:9338-data             *:*                     LISTEN
SYST,2014/04/07 21:23:18,*udp        0      0 *:323                   *:*
SYST,2014/04/07 21:23:18,*udp        0      0 *:54361                 *:*
SYST,2014/04/07 21:23:18,*udp        0      0 *:mdns                  *:*
SYST,2014/04/07 21:23:18,*udp        0      0 *:ntp                   *:*
SYST,2014/04/07 21:23:18,*Data processes
SYST,2014/04/07 21:23:18,*root       643  0.0  2.2  20100  1436 ?        Sl   Mar25   0:01 /root/bin/COMMANDER
SYST,2014/04/07 21:23:18,*root       647  0.0  2.5  21124  1604 ?        Sl   Mar25   0:16 /root/bin/SEND_DATA
SYST,2014/04/07 21:23:18,*root       650  0.0  2.2  19960  1388 ?        Sl   Mar25   0:00 /root/bin/DIO_Rel1
SYST,2014/04/07 21:23:18,*root       654  0.0  2.1  19960  1360 ?        Sl   Mar25   0:02 /root/bin/HEAT
SYST,2014/04/07 21:23:18,*root       667  0.0  2.2  19960  1396 ?        Sl   Mar25   0:00 /root/bin/IRIS
SYST,2014/04/07 21:23:18,*root       672  0.0  2.2  19960  1396 ?        Sl   Mar25   0:01 /root/bin/LILY
SYST,2014/04/07 21:23:18,*root       678  0.0  2.2  19964  1400 ?        Sl   Mar25   0:12 /root/bin/NANO
SYST,2014/04/07 21:23:18,*root       685  0.0  2.2  19960  1404 ?        Sl   Mar25   0:00 /root/bin/RESO
SYST,2014/04/07 21:23:18,*root      7880  0.0  0.9   1704   604 ?        S    21:17   0:00 grep root/bin
'''

uptime = 'System uptime\n 21:17:01 up 13 days, 20:11,  0 users,  load average: 0.00, 0.00, 0.00'
mem_stats = '''Memory stats
             total       used       free     shared    buffers     cached
Mem:         62888      18508      44380          0       2268       5120
-/+ buffers/cache:      11120      51768
Swap:            0          0          0'''
netstat = '''tcp        0      0 *:9337-commands         *:*                     LISTEN
tcp        0      0 *:9338-data             *:*                     LISTEN
udp        0      0 *:323                   *:*
udp        0      0 *:54361                 *:*
udp        0      0 *:mdns                  *:*
udp        0      0 *:ntp                   *:*'''
processes = '''root       643  0.0  2.2  20100  1436 ?        Sl   Mar25   0:01 /root/bin/COMMANDER
root       647  0.0  2.5  21124  1604 ?        Sl   Mar25   0:16 /root/bin/SEND_DATA
root       650  0.0  2.2  19960  1388 ?        Sl   Mar25   0:00 /root/bin/DIO_Rel1
root       654  0.0  2.1  19960  1360 ?        Sl   Mar25   0:02 /root/bin/HEAT
root       667  0.0  2.2  19960  1396 ?        Sl   Mar25   0:00 /root/bin/IRIS
root       672  0.0  2.2  19960  1396 ?        Sl   Mar25   0:01 /root/bin/LILY
root       678  0.0  2.2  19964  1400 ?        Sl   Mar25   0:12 /root/bin/NANO
root       685  0.0  2.2  19960  1404 ?        Sl   Mar25   0:00 /root/bin/RESO
root      7880  0.0  0.9   1704   604 ?        S    21:17   0:00 grep root/bin'''


###############################################################################
#                           DRIVER TEST MIXIN                                  #
#     Defines a set of constants and assert methods used for data particle    #
#     verification                                                               #
#                                                                             #
#  In python mixin classes are classes designed such that they wouldn't be    #
#  able to stand on their own, but are inherited by other classes generally   #
#  using multiple inheritance.                                                #
#                                                                             #
# This class defines a configuration structure for testing and common assert  #
# methods for validating data particles.                                      #
###############################################################################
class BOTPTTestMixinSub(DriverTestMixin):
    _Driver = InstrumentDriver
    _DataParticleType = DataParticleType
    _ProtocolState = ProtocolState
    _ProtocolEvent = ProtocolEvent
    _DriverParameter = DriverParameter
    _InstrumentCommand = InstrumentCommand
    _Capability = Capability
    _Protocol = Protocol

    TYPE = ParameterTestConfigKey.TYPE
    READONLY = ParameterTestConfigKey.READONLY
    STARTUP = ParameterTestConfigKey.STARTUP
    DA = ParameterTestConfigKey.DIRECT_ACCESS
    VALUE = ParameterTestConfigKey.VALUE
    REQUIRED = ParameterTestConfigKey.REQUIRED
    DEFAULT = ParameterTestConfigKey.DEFAULT
    STATES = ParameterTestConfigKey.STATES

    _driver_parameters = {
        # Parameters defined in the IOS
    }

    _driver_capabilities = {
        # capabilities defined in the IOS
        Capability.ACQUIRE_STATUS: {STATES: [ProtocolState.COMMAND]},
    }

    _capabilities = {
        ProtocolState.UNKNOWN: ['DRIVER_EVENT_DISCOVER'],
        ProtocolState.COMMAND: ['DRIVER_EVENT_ACQUIRE_STATUS',
                                'DRIVER_EVENT_GET',
                                'DRIVER_EVENT_SET',
                                'DRIVER_EVENT_START_DIRECT'],
        ProtocolState.DIRECT_ACCESS: ['DRIVER_EVENT_STOP_DIRECT',
                                      'EXECUTE_DIRECT']
    }

    _sample_chunks = [STATUS]

    _build_parsed_values_items = [
        (INVALID_SAMPLE, SYSTStatusParticle, False),
        (STATUS, SYSTStatusParticle, True),
    ]

    _test_handlers_items = [
        ('_handler_command_acquire_status', ProtocolState.COMMAND, None, STATUS.strip()),
    ]

    _command_response_items = [
        (STATUS, STATUS),
    ]

    _status_params = {
        SYSTStatusParticleKey.TIME: {TYPE: float, VALUE: 3605919798.0, REQUIRED: True},
        SYSTStatusParticleKey.NAME: {TYPE: unicode, VALUE: u'BOTPT BPR and tilt instrument controller', REQUIRED: True},
        SYSTStatusParticleKey.SERIAL_NUMBER: {TYPE: unicode, VALUE: u'ts7550n3', REQUIRED: True},
        SYSTStatusParticleKey.UPTIME: {TYPE: unicode, VALUE: uptime, REQUIRED: True},
        SYSTStatusParticleKey.MEM_STATS: {TYPE: unicode, VALUE: mem_stats, REQUIRED: True},
        SYSTStatusParticleKey.MEM_TOTAL: {TYPE: int, VALUE: 62888, REQUIRED: True},
        SYSTStatusParticleKey.MEM_FREE: {TYPE: int, VALUE: 44404, REQUIRED: True},
        SYSTStatusParticleKey.BUFFERS: {TYPE: int, VALUE: 2268, REQUIRED: True},
        SYSTStatusParticleKey.CACHED: {TYPE: int, VALUE: 5120, REQUIRED: True},
        SYSTStatusParticleKey.SWAP_CACHED: {TYPE: int, VALUE: 0, REQUIRED: True},
        SYSTStatusParticleKey.ACTIVE: {TYPE: int, VALUE: 9936, REQUIRED: True},
        SYSTStatusParticleKey.INACTIVE: {TYPE: int, VALUE: 3440, REQUIRED: True},
        SYSTStatusParticleKey.SWAP_TOTAL: {TYPE: int, VALUE: 0, REQUIRED: True},
        SYSTStatusParticleKey.SWAP_FREE: {TYPE: int, VALUE: 0, REQUIRED: True},
        SYSTStatusParticleKey.DIRTY: {TYPE: int, VALUE: 0, REQUIRED: True},
        SYSTStatusParticleKey.WRITEBACK: {TYPE: int, VALUE: 0, REQUIRED: True},
        SYSTStatusParticleKey.ANONPAGES: {TYPE: int, VALUE: 6008, REQUIRED: True},
        SYSTStatusParticleKey.MAPPED: {TYPE: int, VALUE: 3976, REQUIRED: True},
        SYSTStatusParticleKey.SLAB: {TYPE: int, VALUE: 3096, REQUIRED: True},
        SYSTStatusParticleKey.S_RECLAIMABLE: {TYPE: int, VALUE: 804, REQUIRED: True},
        SYSTStatusParticleKey.S_UNRECLAIMABLE: {TYPE: int, VALUE: 2292, REQUIRED: True},
        SYSTStatusParticleKey.PAGE_TABLES: {TYPE: int, VALUE: 512, REQUIRED: True},
        SYSTStatusParticleKey.NFS_UNSTABLE: {TYPE: int, VALUE: 0, REQUIRED: True},
        SYSTStatusParticleKey.BOUNCE: {TYPE: int, VALUE: 0, REQUIRED: True},
        SYSTStatusParticleKey.COMMIT_LIMIT: {TYPE: int, VALUE: 31444, REQUIRED: True},
        SYSTStatusParticleKey.COMMITTED_AS: {TYPE: int, VALUE: 167276, REQUIRED: True},
        SYSTStatusParticleKey.VMALLOC_TOTAL: {TYPE: int, VALUE: 188416, REQUIRED: True},
        SYSTStatusParticleKey.VMALLOC_USED: {TYPE: int, VALUE: 0, REQUIRED: True},
        SYSTStatusParticleKey.VMALLOC_CHUNK: {TYPE: int, VALUE: 188416, REQUIRED: True},
        SYSTStatusParticleKey.NETSTAT: {TYPE: unicode, VALUE: netstat, REQUIRED: True},
        SYSTStatusParticleKey.PROCESSES: {TYPE: unicode, VALUE: processes, REQUIRED: True},
    }

    def assert_sample_data_particle(self, data_particle):
        """
        Verify a particle is a know particle to this driver and verify the particle is
        correct
        @param data_particle: Data particle of unknown type produced by the driver
        """
        if isinstance(data_particle, RawDataParticle):
            self.assert_particle_raw(data_particle)
        else:
            log.error("Unknown Particle Detected: %s" % data_particle)
            self.assertFalse(True)

    def assert_status_particle(self, data_particle, verify_values=False):
        """
        Verify sample particle
        """
        self.assert_data_particle_keys(SYSTStatusParticleKey, self._status_params)
        self.assert_data_particle_header(data_particle, DataParticleType.STATUS, require_instrument_timestamp=True)
        self.assert_data_particle_parameters(data_particle, self._status_params, verify_values)


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
# noinspection PyProtectedMember
@attr('UNIT', group='mi')
class DriverUnitTest(BotptDriverUnitTest, BOTPTTestMixinSub):
    @staticmethod
    def my_send(driver):
        def inner(data):
            if data.startswith(InstrumentCommand.ACQUIRE_STATUS):
                my_response = STATUS
            else:
                my_response = None
            if my_response is not None:
                log.debug("my_send: data: %s, my_response: %s", data, my_response)
                driver._protocol._promptbuf += my_response
                driver._protocol._linebuf += my_response
                return len(my_response)

        return inner

    def test_got_data(self):
        """
        Verify sample data passed through the got data method produces the correct data particles
        """
        # Create and initialize the instrument driver with a mock port agent
        driver = self.test_connect()
        self.assert_raw_particle_published(driver, True)
        self.assert_particle_published(driver, STATUS, self.assert_status_particle, True)

    def test_status_01(self):
        driver = self.test_connect()
        self._send_port_agent_packet(driver, STATUS)


###############################################################################
#                            INTEGRATION TESTS                                #
#     Integration test test the direct driver / instrument interaction        #
#     but making direct calls via zeromq.                                     #
#     - Common Integration tests test the driver through the instrument agent #
#     and common for all drivers (minimum requirement for ION ingestion)      #
###############################################################################
@attr('INT', group='mi')
class DriverIntegrationTest(InstrumentDriverIntegrationTestCase, BOTPTTestMixinSub):
    def setUp(self):
        InstrumentDriverIntegrationTestCase.setUp(self)

    def test_acquire_status(self):
        """
        @brief Test for acquiring status
        """
        self.assert_initialize_driver()
        self.assert_particle_generation(ProtocolEvent.ACQUIRE_STATUS, DataParticleType.STATUS,
                                        self.assert_status_particle, delay=2)


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

    # Overridden because base class tries to do autosample
    def test_reset(self):
        """
        Verify the agent can be reset
        """
        self.assert_enter_command_mode()
        self.assert_reset()

        self.assert_enter_command_mode()
        self.assert_direct_access_start_telnet(inactivity_timeout=60, session_timeout=60)
        self.assert_state_change(ResourceAgentState.DIRECT_ACCESS, DriverProtocolState.DIRECT_ACCESS, 30)
        self.assert_reset()

    # Overridden because does not apply for this driver
    def test_discover(self):
        pass

    # Overridden because does not apply for this driver
    def test_poll(self):
        pass

    # Overridden because does not apply for this driver
    def test_get_set_parameters(self):
        pass

    def test_get_capabilities(self):
        """
        @brief Walk through all driver protocol states and verify capabilities
        returned by get_current_capabilities
        """
        self.assert_enter_command_mode()

        ##################
        #  Command Mode
        ##################
        capabilities = {
            AgentCapabilityType.AGENT_COMMAND: self._common_agent_commands(ResourceAgentState.COMMAND),
            AgentCapabilityType.AGENT_PARAMETER: self._common_agent_parameters(),
            AgentCapabilityType.RESOURCE_COMMAND: [
                ProtocolEvent.ACQUIRE_STATUS,
            ],
            AgentCapabilityType.RESOURCE_INTERFACE: None,
            AgentCapabilityType.RESOURCE_PARAMETER: self._driver_parameters.keys()
        }

        self.assert_capabilities(capabilities)

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

    def test_direct_access_telnet_mode(self):
        """
        @brief This test manually tests that the Instrument Driver properly supports
        direct access to the physical instrument. (telnet mode)
        """
        self.assert_direct_access_start_telnet()
        self.assertTrue(self.tcp_client)
        self.tcp_client.send_data(InstrumentCommand.ACQUIRE_STATUS + NEWLINE)
        result = self.tcp_client.expect('SYST,')
        self.assertTrue(result, msg='Failed to receive expected response in direct access mode.')
        self.assert_direct_access_stop_telnet()
        self.assert_state_change(ResourceAgentState.COMMAND, ProtocolState.COMMAND, 10)
