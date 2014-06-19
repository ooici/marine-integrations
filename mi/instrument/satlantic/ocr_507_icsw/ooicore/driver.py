"""
@package mi.instrument.satlantic.ocr_507_icsw.ooicore.driver
@file marine-integrations/mi/instrument/satlantic/ocr_507_icsw/ooicore/driver.py
@author Godfrey Duke
@brief Instrument driver classes that provide structure towards interaction
with the Satlantic OCR507 ICSW w/ Midrange Bioshutter

TODO:
The basic interface (and, thus, driver) is very similar to that for PARAD. As a result this driver is based on the
PARAD driver. The following changes are required:
[ ] Rework regex
  [x] Sample pattern
  [ ] Header pattern
  [ ] Init pattern
  [ ] Configuration pattern
[-] Rework data particles
[ ] Add spkir_configuration_record stream
"""

__author__ = 'Godfrey Duke'
__license__ = 'Apache 2.0'

import re
import struct

from mi.core.log import get_logger

log = get_logger()

from mi.core.common import BaseEnum
from mi.core.instrument.instrument_driver import SingleConnectionInstrumentDriver
from mi.core.instrument.instrument_driver import DriverParameter
from mi.core.instrument.data_particle import CommonDataParticleType
from mi.core.exceptions import SampleException

from mi.core.instrument.data_particle import DataParticle, DataParticleKey

from mi.instrument.satlantic.ocr_507_icsw.driver import SatlanticInstrumentDriver
from mi.instrument.satlantic.ocr_507_icsw.driver import SatlanticInstrumentProtocol

####################################################################
# Module-wide values
####################################################################

SAMPLE_PATTERN = r'(?P<instrument_id>SATDI7)(?P<serial_number>\d{4})(?P<timer>\d{7}\.\d\d)(?P<binary_data>.{38})\r\n'
SAMPLE_REGEX = re.compile(SAMPLE_PATTERN, re.DOTALL)
CONFIG_PATTERN = '''Satlantic\ OCR.*?
            Firmware\ version:\ (?P<firmware_version>.*?)\s*
            Instrument:\ (?P<instrument_id>\w+)\s*
            S\/N:\ (?P<serial_number>\w+).*?
            Telemetry\ Baud\ Rate:\ (?P<telemetry_baud_rate>\d+)\ bps\s*
            Maximum\ Frame\ Rate:\ (?P<max_frame_rate>\d+)\ Hz\s*
            Initialize\ Silent\ Mode:\ (?P<initialize_silent_mode>off|on)\s*
            Initialize\ Power\ Down:\ (?P<initialize_power_down>off|on)\s*
            Initialize\ Automatic\ Telemetry:\ (?P<initialize_auto_telemetry>off|on)\s*
            Network\ Mode:\ (?P<network_mode>off|on)\s*
            Network\ Address:\ (?P<network_address>\d+)\s*
            Network\ Baud\ Rate:\ (?P<network_baud_rate>\d+)\ bps.*?
            \[Auto'''

CONFIG_REGEX = re.compile(CONFIG_PATTERN, re.DOTALL | re.VERBOSE)
init_pattern = r'Press <Ctrl\+C> for command console. \r\nInitializing system. Please wait...\r\n'
init_regex = re.compile(init_pattern)
WRITE_DELAY = 0.2
RESET_DELAY = 6
EOLN = "\r\n"
RETRY = 3


class DataParticleType(BaseEnum):
    RAW = CommonDataParticleType.RAW
    PARSED = 'spkir_data_record'
    CONFIG = 'spkir_a_configuration_record'


class PARSpecificDriverEvents(BaseEnum):
    # START_POLL = 'DRIVER_EVENT_START_POLL'
    # STOP_POLL = 'DRIVER_EVENT_STOP_POLL'
    RESET = "DRIVER_EVENT_RESET"


####################################################################
# Static enumerations for this class
####################################################################


class PARProtocolError(BaseEnum):
    INVALID_COMMAND = "Invalid command"


###############################################################################
# Satlantic PAR Sensor Driver.
###############################################################################

class SatlanticOCR507InstrumentDriver(SatlanticInstrumentDriver):
    """
    The InstrumentDriver class for the Satlantic PAR sensor PARAD.
    @note If using this via Ethernet, must use a delayed send
    or commands may not make it to the PAR successfully. A delay of 0.1
    appears to be sufficient for most 19200 baud operations (0.5 is more
    reliable), more may be needed for 9600. Note that control commands
    should not be delayed.
    """

    def __init__(self, evt_callback):
        """Instrument-specific enums
        @param evt_callback The callback function to use for events
        """
        SingleConnectionInstrumentDriver.__init__(self, evt_callback)

    def _build_protocol(self):
        """ Construct driver protocol state machine """
        self._protocol = SatlanticOCR507InstrumentProtocol(self._driver_event)


class SatlanticOCR507DataParticleKey(BaseEnum):
    INSTRUMENT_ID = "instrument_id"
    SERIAL_NUMBER = "serial_number"
    TIMER = "timer"
    SAMPLE_DELAY = "sample_delay"
    CH1_SAMPLE = "channel_1"
    CH2_SAMPLE = "channel_2"
    CH3_SAMPLE = "channel_3"
    CH4_SAMPLE = "channel_4"
    CH5_SAMPLE = "channel_5"
    CH6_SAMPLE = "channel_6"
    CH7_SAMPLE = "channel_7"
    REGULATED_INPUT_VOLTAGE = "vin_sense"
    ANALOG_RAIL_VOLTAGE = "va_sense"
    INTERNAL_TEMP = "internal_temperature"
    FRAME_COUNTER = "frame_counter"
    CHECKSUM = "checksum"


class SatlanticOCR507ConfigurationParticleKey(BaseEnum):
    FIRMWARE_VERSION = 'spkir_a_firmware_version'
    INSTRUMENT_ID = "instrument_id"
    SERIAL_NUMBER = "serial_number"
    TELEMETRY_BAUD_RATE = "telemetry_baud_rate"
    MAX_FRAME_RATE = "max_frame_rate"
    INIT_SILENT_MODE = "initialize_silent_mode"
    INIT_POWER_DOWN = "initialize_power_down"
    INIT_AUTO_TELEMETRY = "initialize_auto_telemetry"
    NETWORK_MODE = "network_mode"
    NETWORK_ADDRESS = "network_address"
    NETWORK_BAUD_RATE = "network_baud_rate"


class SatlanticOCR507DataParticle(DataParticle):
    """
    Routines for parsing raw data into a data particle structure for the
    Satlantic PAR sensor. Overrides the building of values, and the rest comes
    along for free.
    """
    _data_particle_type = DataParticleType.PARSED

    @staticmethod
    def regex():
        return SAMPLE_PATTERN

    @staticmethod
    def regex_compiled():
        return SAMPLE_REGEX

    def _build_parsed_values(self):
        """
        Take something in the sample format and split it into
        a PAR values (with an appropriate tag)

        @throws SampleException If there is a problem with sample creation
        """
        match = SAMPLE_REGEX.match(self.raw_data)

        if not match:
            raise SampleException("No regex match of parsed sample data: [%s]" %
                                  self.decoded_raw)

        # Parse the relevant ascii fields
        instrument_id = match.group('instrument_id')
        serial_number = match.group('serial_number')
        timer = float(match.group('timer'))

        # Ensure the expected values were present
        if not instrument_id:
            raise SampleException("No instrument id value parsed")
        if not serial_number:
            raise SampleException("No serial number value parsed")
        if not timer:
            raise SampleException("No timer value parsed")

        # Parse the relevant binary data
        """
        Field Name          Field Size (bytes)      Description         Format Char
        ----------          ------------------      -----------         -----------
        sample_delay                2               BS formatted value      h
        ch[1-7]_sample              4               BU formatted value      I
        regulated_input_voltage     2               BU formatted value      H
        analog_rail_voltage         2               BU formatted value      H
        internal_temp               2               BU formatted value      H
        frame_counter               1               BU formatted value      B
        checksum                    1               BU formatted value      B
        """
        try:
            sample_delay, ch1_sample, ch2_sample, ch3_sample, ch4_sample, ch5_sample, ch6_sample, ch7_sample, \
                regulated_input_voltage, analog_rail_voltage, internal_temp, frame_counter, checksum \
                = struct.unpack('!h7IHHHBB', match.group('binary_data'))
        except struct.error, e:
            raise SampleException(e)

        result = [{DataParticleKey.VALUE_ID: SatlanticOCR507DataParticleKey.INSTRUMENT_ID,
                   DataParticleKey.VALUE: instrument_id},
                  {DataParticleKey.VALUE_ID: SatlanticOCR507DataParticleKey.SERIAL_NUMBER,
                   DataParticleKey.VALUE: serial_number},
                  {DataParticleKey.VALUE_ID: SatlanticOCR507DataParticleKey.TIMER,
                   DataParticleKey.VALUE: timer},
                  {DataParticleKey.VALUE_ID: SatlanticOCR507DataParticleKey.SAMPLE_DELAY,
                   DataParticleKey.VALUE: sample_delay},
                  {DataParticleKey.VALUE_ID: SatlanticOCR507DataParticleKey.CH1_SAMPLE,
                   DataParticleKey.VALUE: ch1_sample},
                  {DataParticleKey.VALUE_ID: SatlanticOCR507DataParticleKey.CH2_SAMPLE,
                   DataParticleKey.VALUE: ch2_sample},
                  {DataParticleKey.VALUE_ID: SatlanticOCR507DataParticleKey.CH3_SAMPLE,
                   DataParticleKey.VALUE: ch3_sample},
                  {DataParticleKey.VALUE_ID: SatlanticOCR507DataParticleKey.CH4_SAMPLE,
                   DataParticleKey.VALUE: ch4_sample},
                  {DataParticleKey.VALUE_ID: SatlanticOCR507DataParticleKey.CH5_SAMPLE,
                   DataParticleKey.VALUE: ch5_sample},
                  {DataParticleKey.VALUE_ID: SatlanticOCR507DataParticleKey.CH6_SAMPLE,
                   DataParticleKey.VALUE: ch6_sample},
                  {DataParticleKey.VALUE_ID: SatlanticOCR507DataParticleKey.CH7_SAMPLE,
                   DataParticleKey.VALUE: ch7_sample},
                  {DataParticleKey.VALUE_ID: SatlanticOCR507DataParticleKey.REGULATED_INPUT_VOLTAGE,
                   DataParticleKey.VALUE: regulated_input_voltage},
                  {DataParticleKey.VALUE_ID: SatlanticOCR507DataParticleKey.ANALOG_RAIL_VOLTAGE,
                   DataParticleKey.VALUE: analog_rail_voltage},
                  {DataParticleKey.VALUE_ID: SatlanticOCR507DataParticleKey.INTERNAL_TEMP,
                   DataParticleKey.VALUE: internal_temp},
                  {DataParticleKey.VALUE_ID: SatlanticOCR507DataParticleKey.FRAME_COUNTER,
                   DataParticleKey.VALUE: frame_counter},
                  {DataParticleKey.VALUE_ID: SatlanticOCR507DataParticleKey.CHECKSUM,
                   DataParticleKey.VALUE: checksum}]

        return result


class SatlanticOCR507ConfigurationParticle(DataParticle):
    """
    Routines for parsing raw data into a data particle structure for the
    Satlantic PAR sensor. Overrides the building of values, and the rest comes
    along for free.
    """
    _data_particle_type = DataParticleType.CONFIG

    def _build_parsed_values(self):
        """
        Take something in the sample format and split it into
        a PAR values (with an appropriate tag)

        @throws SampleException If there is a problem with sample creation
        """
        match = CONFIG_REGEX.match(self.raw_data)

        if not match:
            raise SampleException("No regex match of parsed configuration data: [%s]" %
                                  self.decoded_raw)

        # Parse the relevant ascii fields
        firmware_version = match.group('firmware_version')
        instrument_id = match.group('instrument_id')
        serial_number = match.group('serial_number')
        telemetry_baud_rate = int(match.group('telemetry_baud_rate'))
        max_frame_rate = match.group('max_frame_rate')
        init_silent_mode = match.group('initialize_silent_mode')
        init_power_down = match.group('initialize_power_down')
        init_auto_telemetry = match.group('initialize_auto_telemetry')
        network_mode = match.group('network_mode')
        network_address = int(match.group('network_address'))
        network_baud_rate = int(match.group('network_baud_rate'))

        # Ensure the expected values were present
        if not firmware_version:
            raise SampleException("No firmware version value parsed")
        if not instrument_id:
            raise SampleException("No instrument id value parsed")
        if not serial_number:
            raise SampleException("No serial number value parsed")
        if not telemetry_baud_rate:
            raise SampleException("No telemetry baud rate value parsed")
        if not max_frame_rate:
            raise SampleException("No max frame rate value parsed")
        if not init_silent_mode:
            raise SampleException("No init silent mode value parsed")
        if not init_power_down:
            raise SampleException("No init power down value parsed")
        if not init_auto_telemetry:
            raise SampleException("No init auto telemetry value parsed")
        if not network_mode:
            raise SampleException("No network mode value parsed")
        if not network_address:
            raise SampleException("No network address value parsed")
        if not network_baud_rate:
            raise SampleException("No network baud rate value parsed")

        # Convert on/off strings to booleans
        init_silent_mode = 'on' == init_silent_mode
        init_power_down = 'on' == init_power_down
        init_auto_telemetry = 'on' == init_auto_telemetry
        network_mode = 'on' == network_mode

        result = [{DataParticleKey.VALUE_ID: SatlanticOCR507ConfigurationParticleKey.FIRMWARE_VERSION,
                   DataParticleKey.VALUE: firmware_version},
                  {DataParticleKey.VALUE_ID: SatlanticOCR507ConfigurationParticleKey.INSTRUMENT_ID,
                   DataParticleKey.VALUE: instrument_id},
                  {DataParticleKey.VALUE_ID: SatlanticOCR507ConfigurationParticleKey.SERIAL_NUMBER,
                   DataParticleKey.VALUE: serial_number},
                  {DataParticleKey.VALUE_ID: SatlanticOCR507ConfigurationParticleKey.TELEMETRY_BAUD_RATE,
                   DataParticleKey.VALUE: telemetry_baud_rate},
                  {DataParticleKey.VALUE_ID: SatlanticOCR507ConfigurationParticleKey.MAX_FRAME_RATE,
                   DataParticleKey.VALUE: max_frame_rate},
                  {DataParticleKey.VALUE_ID: SatlanticOCR507ConfigurationParticleKey.INIT_SILENT_MODE,
                   DataParticleKey.VALUE: init_silent_mode},
                  {DataParticleKey.VALUE_ID: SatlanticOCR507ConfigurationParticleKey.INIT_POWER_DOWN,
                   DataParticleKey.VALUE: init_power_down},
                  {DataParticleKey.VALUE_ID: SatlanticOCR507ConfigurationParticleKey.INIT_AUTO_TELEMETRY,
                   DataParticleKey.VALUE: init_auto_telemetry},
                  {DataParticleKey.VALUE_ID: SatlanticOCR507ConfigurationParticleKey.NETWORK_MODE,
                   DataParticleKey.VALUE: network_mode},
                  {DataParticleKey.VALUE_ID: SatlanticOCR507ConfigurationParticleKey.NETWORK_ADDRESS,
                   DataParticleKey.VALUE: network_address},
                  {DataParticleKey.VALUE_ID: SatlanticOCR507ConfigurationParticleKey.NETWORK_BAUD_RATE,
                   DataParticleKey.VALUE: network_baud_rate}]

        return result


####################################################################
# Satlantic PAR Sensor Protocol
####################################################################
class SatlanticOCR507InstrumentProtocol(SatlanticInstrumentProtocol):
    """The instrument protocol classes to deal with a Satlantic PAR sensor.
    The protocol is a very simple command/response protocol with a few show
    commands and a few set commands.
    Note protocol state machine must be called "self._protocol_fsm"

    @todo Check for valid state transitions and handle requests appropriately
    possibly using better exceptions from the fsm.on_event() method
    """
    _data_particle_type = SatlanticOCR507DataParticle
    _config_particle_type = SatlanticOCR507ConfigurationParticle
    _data_particle_regex = SAMPLE_REGEX
    _config_particle_regex = CONFIG_REGEX

    @staticmethod
    def sieve_function(raw_data):
        """ The method that splits samples
        """
        log.warn("Rawr Data: %r, len: %d", raw_data, len(raw_data))
        log.warn(SAMPLE_REGEX.pattern)
        matchers = [SAMPLE_REGEX, CONFIG_REGEX]
        return_list = []

        for matcher in matchers:
            for match in matcher.finditer(raw_data):
                log.warn("FOUND A MATCH for: %s...", raw_data[0:9])
                return_list.append((match.start(), match.end()))

        return return_list