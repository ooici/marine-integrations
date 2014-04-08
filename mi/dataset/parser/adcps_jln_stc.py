#!/usr/bin/env python

"""
@package mi.dataset.parser.adcps_jln_stc
@file marine-integrations/mi/dataset/parser/adcps_jln_stc.py
@author Maria Lutz
<<<<<<< HEAD
@brief Parser for the ADCPS_JLN__stc_imodem dataset driver
=======
@brief Parser for the adcps_jln_stc dataset driver
>>>>>>> upstream/master
Release notes:

Initial Release
"""

__author__ = 'Maria Lutz'
__license__ = 'Apache 2.0'

import copy
import re
import ntplib
import struct
import time
import binascii
import calendar
<<<<<<< HEAD
=======
from functools import partial
from dateutil import parser
>>>>>>> upstream/master

from mi.core.log import get_logger ; log = get_logger()
from mi.core.common import BaseEnum
from mi.core.instrument.data_particle import DataParticle, DataParticleKey
<<<<<<< HEAD
from mi.core.exceptions import SampleException, DatasetParserException
from mi.dataset.dataset_parser import BufferLoadingParser
from mi.core.instrument.chunker import BinaryChunker
from functools import partial
from dateutil import parser
=======
from mi.core.instrument.chunker import BinaryChunker
from mi.core.exceptions import SampleException, DatasetParserException, UnexpectedDataException

from mi.dataset.dataset_parser import BufferLoadingParser
>>>>>>> upstream/master

# *** Defining regexes for this parser ***
HEADER_REGEX = b'#UIMM Status.+DateTime: (\d{8}\s\d{6}).+#ID=(\d+).+#SN=(\d+).+#Volts=(\d+\.\d{2}).+#Records=(\d+).+#Length=(\d+).+#Events=(\d+).+UIMM Data\r\n'
HEADER_MATCHER = re.compile(HEADER_REGEX, re.DOTALL)

FOOTER_REGEX = b'#End UIMM Data, (\d+) samples written\r\n'
FOOTER_MATCHER = re.compile(FOOTER_REGEX)

HEADER_FOOTER_REGEX =  b'#UIMM Status.+DateTime: (\d{8}\s\d{6}).+#ID=(\d+).+#SN=(\d+).+#Volts=(\d+\.\d{2}).+#Records=(\d+).+#Length=(\d+).+#Events=(\d+).+UIMM Data\r\n#End UIMM Data, (\d+) samples written\r\n'
HEADER_FOOTER_MATCHER = re.compile(HEADER_FOOTER_REGEX, re.DOTALL)

<<<<<<< HEAD
DATA_REGEX = b'Record\[\d+\]:([\x00-\xFF]+?)(Record|#End U)'
DATA_MATCHER = re.compile(DATA_REGEX)
DATA_REGEX_B = b'Record\[\d+\]:([\x00-\xFF]+)'
DATA_MATCHER_B = re.compile(DATA_REGEX_B)

RX_FAILURE_REGEX = b'Record\[\d+\]:ReceiveFailure'
RX_FAILURE_MATCHER = re.compile(RX_FAILURE_REGEX)

RECORD_REGEX = b'Record\[\d+\]:'
RECORD_MATCHER = re.compile(RECORD_REGEX)

HEADER_BYTES = 1024 
FOOTER_BYTES = 1024
=======
DATA_REGEX = b'(Record\[\d+\]:)([\x00-\xFF]+?)\r\n(Record|#End U)'
DATA_MATCHER = re.compile(DATA_REGEX)

DATA_REGEX_B = b'(Record\[\d+\]:)([\x00-\xFF]+?)\r\n'
DATA_MATCHER_B = re.compile(DATA_REGEX_B)

RX_FAILURE_REGEX = b'Record\[\d+\]:ReceiveFailure\r\n'
RX_FAILURE_MATCHER = re.compile(RX_FAILURE_REGEX)

HEADER_BYTES = 200
FOOTER_BYTES = 43
>>>>>>> upstream/master

class DataParticleType(BaseEnum):
    ADCPS_JLN_INS = 'adcps_jln_stc_instrument'
    ADCPS_JLN_META = 'adcps_jln_stc_metadata'

<<<<<<< HEAD
class Adcps_jln_stc_instrumentParserDataParticleKey(BaseEnum):
=======
class AdcpsJlnStcInstrumentParserDataParticleKey(BaseEnum):
>>>>>>> upstream/master
    # params collected for adcps_jln_stc_instrument stream:
    ADCPS_JLN_RECORD = 'adcps_jln_record'
    ADCPS_JLN_NUMBER = 'adcps_jln_number'
    ADCPS_JLN_UNIT_ID = 'adcps_jln_unit_id'
    ADCPS_JLN_FW_VERS = 'adcps_jln_fw_vers'
    ADCPS_JLN_FW_REV = 'adcps_jln_fw_rev'
    ADCPS_JLN_YEAR = 'adcps_jln_year'
    ADCPS_JLN_MONTH = 'adcps_jln_month'
    ADCPS_JLN_DAY = 'adcps_jln_day'
    ADCPS_JLN_HOUR = 'adcps_jln_hour'
    ADCPS_JLN_MINUTE = 'adcps_jln_minute'
    ADCPS_JLN_SECOND = 'adcps_jln_second'
    ADCPS_JLN_HSEC = 'adcps_jln_hsec'
    ADCPS_JLN_HEADING = 'adcps_jln_heading'
<<<<<<< HEAD
=======
    ADCPS_JLN_PITCH = 'adcps_jln_pitch'
>>>>>>> upstream/master
    ADCPS_JLN_ROLL = 'adcps_jln_roll'
    ADCPS_JLN_TEMP = 'adcps_jln_temp'
    ADCPS_JLN_PRESSURE = 'adcps_jln_pressure'
    ADCPS_JLN_STARTBIN = 'adcps_jln_startbin'
    ADCPS_JLN_BINS = 'adcps_jln_bins'
    ADCPS_JLN_VEL_ERROR = 'adcps_jln_vel_error'
    ADCPS_JLN_VEL_UP = 'adcps_jln_vel_up'
    ADCPS_JLN_VEL_NORTH = 'adcps_jln_vel_north'
    ADCPS_JLN_VEL_EAST = 'adcps_jln_vel_east'
<<<<<<< HEAD

class StateKey(BaseEnum):
    POSITION = "position"

class Adcps_jln_stc_instrumentParserDataParticle(DataParticle):
    """
    Class for parsing data from the Adcps_jln_stc data set
    """
=======
    
class StateKey(BaseEnum):
    POSITION='position' # holds the file position

class AdcpsJlnStcInstrumentParserDataParticle(DataParticle):
    """
    Class for parsing data from the adcps_jln_stc data set
    """

>>>>>>> upstream/master
    _data_particle_type = DataParticleType.ADCPS_JLN_INS
    
    def _build_parsed_values(self):
        """
        Take something in the data format and turn it into
<<<<<<< HEAD
        a particle with the appropriate tag.
        @throws SampleException If there is a problem with sample creation
        """
        
        match = DATA_MATCHER_B.search(self.raw_data)
            
        if not match:
            raise SampleException("Adcps_jln_stcParserDataParticle: No regex match of \
                                  parsed sample data [%s]", self.raw_data)
        try:
            record_match = RECORD_MATCHER.search(match)
            record_match.strip('Record\[')
            record_match.strip('\]:')
            asciiRecordNumber = int(record_match)
            
            match = match.strip('Record\[....\]:') 
            fields = struct.unpack('<HhIBBBdhhhhIbBB', match.group(0)[0:34])
            
            # ID field should always be 7F6E
            log.debug('ID field: %s', fields[0])
            if fields[0] != '0x7F6E':
                raise ValueError('ID field does not equal 7F6E.')
            
            num_bytes = fields[1]
            if len(match.group(0)) - 2 != num_bytes:
                raise ValueError('num bytes %d does not match data length %d'
                          % (num_bytes, len(match.group(0))))
            
=======
        an array of dictionaries defining the data in the particle
        with the appropriate tag.
        @throws SampleException If there is a problem with sample creation
        """
        match = DATA_MATCHER_B.search(self.raw_data)
        if not match:
            raise SampleException("AdcpsJlnStcInstrumentParserDataParticle: No regex match of \
                                  parsed sample data [%s]", self.raw_data)
        try:            
            record_str = match.group(1).strip('Record\[').strip('\]:')

            fields = struct.unpack('<HHIBBBdhhhHIBBB', match.group(2)[0:34])

            # ID field should always be 7F6E
            if fields[0] != int('0x7F6E', 16):
                raise ValueError('ID field does not equal 7F6E.')

            num_bytes = fields[1]
            if len(match.group(2)) - 2 != num_bytes:
                raise ValueError('num bytes %d does not match data length %d'
                          % (num_bytes, len(match.group(2)) - 2))

>>>>>>> upstream/master
            nbins = fields[14]
            if len(match.group(0)) < (36+(nbins*8)):
                raise ValueError('Number of bins %d does not fit in data length %d'%(nbins,
                                                                                     len(match.group(0))))
<<<<<<< HEAD
            date_fields = struct.unpack('HBBBBBB', match.group(0)[11:19])
            
            # create a string with the right number of shorts to unpack
            struct_format = '>'
            for i in range(0,nbins):
                struct_format = struct_format + 'h'
            
            bin_len = nbins*2
            adcps_jln_vel_error = struct.unpack(struct_format, match.group(0)[34:[34+bin_len]])
            adcps_jln_vel_up = struct.unpack(struct_format, match.group(0)[(34+bin_len):(34+(bin_len*2))])
            adcps_jln_vel_north = struct.unpack(struct_format, match.group(0)[(34+(bin_len*2)):(34+(bin_len*3))])
            adcps_jln_vel_east = struct.unpack(struct_format, match.group(0)[(34+(bin_len*3)):(34+(bin_len*4))])        
                          
        except (ValueError, TypeError, IndexError) as ex:
            raise SampleException("Error (%s) while decoding parameters in data: [%s]"
                                  % (ex, match.group(0)))
        result = [{DataParticleKey.VALUE_ID: Adcps_jln_stc_instrumentParserDataParticleKey.ADCPS_JLN_RECORD,
                   DataParticleKey.VALUE: asciiRecordNumber},
                {DataParticleKey.VALUE_ID: Adcps_jln_stc_instrumentParserDataParticleKey.ADCPS_JLN_NUMBER,
                 DataParticleKey.VALUE: int(fields[2])},
                {DataParticleKey.VALUE_ID: Adcps_jln_stc_instrumentParserDataParticleKey.ADCPS_JLN_UNIT_ID,
                 DataParticleKey.VALUE: int(fields[3])},
                {DataParticleKey.VALUE_ID: Adcps_jln_stc_instrumentParserDataParticleKey.ADCPS_JLN_FW_VERS,
                 DataParticleKey.VALUE: int(fields[4])},
                {DataParticleKey.VALUE_ID: Adcps_jln_stc_instrumentParserDataParticleKey.ADCPS_JLN_FW_REV,
                 DataParticleKey.VALUE: (fields[5])},
                {DataParticleKey.VALUE_ID: Adcps_jln_stc_instrumentParserDataParticleKey.ADCPS_JLN_YEAR,
                 DataParticleKey.VALUE: int(date_fields[0])},
                {DataParticleKey.VALUE_ID: Adcps_jln_stc_instrumentParserDataParticleKey.ADCPS_JLN_MONTH,
                 DataParticleKey.VALUE: int(date_fields[1])},
                {DataParticleKey.VALUE_ID: Adcps_jln_stc_instrumentParserDataParticleKey.ADCPS_JLN_DAY,
                 DataParticleKey.VALUE: int(date_fields[2])},
                {DataParticleKey.VALUE_ID: Adcps_jln_stc_instrumentParserDataParticleKey.ADCPS_JLN_HOUR,
                 DataParticleKey.VALUE: int(date_fields[3])},
                {DataParticleKey.VALUE_ID: Adcps_jln_stc_instrumentParserDataParticleKey.ADCPS_JLN_MINUTE,
                 DataParticleKey.VALUE: int(date_fields[4])},
                {DataParticleKey.VALUE_ID: Adcps_jln_stc_instrumentParserDataParticleKey.ADCPS_JLN_SECOND,
                 DataParticleKey.VALUE: int(date_fields[5])},
                {DataParticleKey.VALUE_ID: Adcps_jln_stc_instrumentParserDataParticleKey.ADCPS_JLN_HSEC,
                 DataParticleKey.VALUE: int(date_fields[6])},
                {DataParticleKey.VALUE_ID: Adcps_jln_stc_instrumentParserDataParticleKey.ADCPS_JLN_HEADING,
                 DataParticleKey.VALUE: int(fields[7])},
                {DataParticleKey.VALUE_ID: Adcps_jln_stc_instrumentParserDataParticleKey.ADCPS_JLN_ROLL,
                 DataParticleKey.VALUE: int(fields[9])},
                {DataParticleKey.VALUE_ID: Adcps_jln_stc_instrumentParserDataParticleKey.ADCPS_JLN_TEMP,
                 DataParticleKey.VALUE: int(fields[10])},
                {DataParticleKey.VALUE_ID: Adcps_jln_stc_instrumentParserDataParticleKey.ADCPS_JLN_PRESSURE,
                 DataParticleKey.VALUE: int(fields[11])},
                {DataParticleKey.VALUE_ID: Adcps_jln_stc_instrumentParserDataParticleKey.ADCPS_JLN_STARTBIN,
                 DataParticleKey.VALUE: int(fields[13])},
                {DataParticleKey.VALUE_ID: Adcps_jln_stc_instrumentParserDataParticleKey.ADCPS_JLN_BINS,
                 DataParticleKey.VALUE: int(fields[14])},
                {DataParticleKey.VALUE_ID: Adcps_jln_stc_instrumentParserDataParticleKey.ADCPS_JLN_VEL_ERROR,
                 DataParticleKey.VALUE: list(adcps_jln_vel_error)},
                {DataParticleKey.VALUE_ID: Adcps_jln_stc_instrumentParserDataParticleKey.ADCPS_JLN_VEL_UP,
                 DataParticleKey.VALUE: list(adcps_jln_vel_up)},
                {DataParticleKey.VALUE_ID: Adcps_jln_stc_instrumentParserDataParticleKey.ADCPS_JLN_VEL_NORTH,
                 DataParticleKey.VALUE: list(adcps_jln_vel_north)},
                {DataParticleKey.VALUE_ID: Adcps_jln_stc_instrumentParserDataParticleKey.ADCPS_JLN_VEL_EAST,
                 DataParticleKey.VALUE: list(adcps_jln_vel_east)},]
        
        return result

    def __eq__(self, arg):
        """
        Quick equality check for testing purposes. If they have the same raw
        data, timestamp, and new sequence, they are the same enough for this 
        particle
        """
        if ((self.raw_data == arg.raw_data) and \
            (self.contents[DataParticleKey.INTERNAL_TIMESTAMP] == \
             arg.contents[DataParticleKey.INTERNAL_TIMESTAMP])):
            return True
        else:
            if self.raw_data != arg.raw_data:
                log.debug('Raw data does not match')
            elif self.contents[DataParticleKey.INTERNAL_TIMESTAMP] != \
                 arg.contents[DataParticleKey.INTERNAL_TIMESTAMP]:
                log.debug('Timestamp does not match')
            return False
        
=======
            date_fields = struct.unpack('HBBBBBB', match.group(2)[11:19])

            # create a string with the right number of shorts to unpack
            struct_format = '<'
            for i in range(0,nbins):
                struct_format = struct_format + 'h'

            bin_len = nbins*2
            adcps_jln_vel_error = struct.unpack(struct_format, match.group(2)[34:34+bin_len])
            adcps_jln_vel_up = struct.unpack(struct_format, match.group(2)[(34+bin_len):(34+(bin_len*2))])
            adcps_jln_vel_north = struct.unpack(struct_format, match.group(2)[(34+(bin_len*2)):(34+(bin_len*3))])
            adcps_jln_vel_east = struct.unpack(struct_format, match.group(2)[(34+(bin_len*3)):(34+(bin_len*4))])      
                          
        except (ValueError, TypeError, IndexError) as ex:
            raise SampleException("Error (%s) while decoding parameters in data: [0x%s]"
                                  % (ex, binascii.hexlify(match.group(0))))
        result = [self._encode_value(AdcpsJlnStcInstrumentParserDataParticleKey.ADCPS_JLN_RECORD, record_str, int),
                  self._encode_value(AdcpsJlnStcInstrumentParserDataParticleKey.ADCPS_JLN_NUMBER, fields[2], int),
                  self._encode_value(AdcpsJlnStcInstrumentParserDataParticleKey.ADCPS_JLN_UNIT_ID, fields[3], int),
                  self._encode_value(AdcpsJlnStcInstrumentParserDataParticleKey.ADCPS_JLN_FW_VERS, fields[4], int),
                  self._encode_value(AdcpsJlnStcInstrumentParserDataParticleKey.ADCPS_JLN_FW_REV, fields[5], int),
                  self._encode_value(AdcpsJlnStcInstrumentParserDataParticleKey.ADCPS_JLN_YEAR, date_fields[0], int),
                  self._encode_value(AdcpsJlnStcInstrumentParserDataParticleKey.ADCPS_JLN_MONTH, date_fields[1], int),
                  self._encode_value(AdcpsJlnStcInstrumentParserDataParticleKey.ADCPS_JLN_DAY, date_fields[2], int),
                  self._encode_value(AdcpsJlnStcInstrumentParserDataParticleKey.ADCPS_JLN_HOUR, date_fields[3], int),
                  self._encode_value(AdcpsJlnStcInstrumentParserDataParticleKey.ADCPS_JLN_MINUTE, date_fields[4], int),
                  self._encode_value(AdcpsJlnStcInstrumentParserDataParticleKey.ADCPS_JLN_SECOND, date_fields[5], int),
                  self._encode_value(AdcpsJlnStcInstrumentParserDataParticleKey.ADCPS_JLN_HSEC, date_fields[6], int),
                  self._encode_value(AdcpsJlnStcInstrumentParserDataParticleKey.ADCPS_JLN_HEADING, fields[7], int),
                  self._encode_value(AdcpsJlnStcInstrumentParserDataParticleKey.ADCPS_JLN_PITCH, fields[8], int),
                  self._encode_value(AdcpsJlnStcInstrumentParserDataParticleKey.ADCPS_JLN_ROLL, fields[9], int),
                  self._encode_value(AdcpsJlnStcInstrumentParserDataParticleKey.ADCPS_JLN_TEMP, fields[10], int),
                  self._encode_value(AdcpsJlnStcInstrumentParserDataParticleKey.ADCPS_JLN_PRESSURE, fields[11], int),
                  self._encode_value(AdcpsJlnStcInstrumentParserDataParticleKey.ADCPS_JLN_STARTBIN, fields[13], int),
                  self._encode_value(AdcpsJlnStcInstrumentParserDataParticleKey.ADCPS_JLN_BINS, fields[14], int),
                  self._encode_value(AdcpsJlnStcInstrumentParserDataParticleKey.ADCPS_JLN_VEL_ERROR, adcps_jln_vel_error, list),
                  self._encode_value(AdcpsJlnStcInstrumentParserDataParticleKey.ADCPS_JLN_VEL_UP, adcps_jln_vel_up, list),
                  self._encode_value(AdcpsJlnStcInstrumentParserDataParticleKey.ADCPS_JLN_VEL_NORTH, adcps_jln_vel_north, list),
                  self._encode_value(AdcpsJlnStcInstrumentParserDataParticleKey.ADCPS_JLN_VEL_EAST, adcps_jln_vel_east, list)]

        return result
    
>>>>>>> upstream/master
    @staticmethod
    def unpack_date(data):
        fields = struct.unpack('HBBBBBB', data)
        zulu_ts = "%04d-%02d-%02dT%02d:%02d:%02d.%02dZ" % (
            fields[0], fields[1], fields[2], fields[3],
            fields[4], fields[5], fields[6])
        return zulu_ts
    
<<<<<<< HEAD
class Adcps_jln_stc_metadataParserDataParticleKey(BaseEnum):
=======
class AdcpsJlnStcMetadataParserDataParticleKey(BaseEnum):
>>>>>>> upstream/master
    # params collected for adcps_jln_stc_metatdata stream:
    ADCPS_JLN_TIMESTAMP = 'adcps_jln_timestamp'
    ADCPS_JLN_ID = 'adcps_jln_id'
    ADCPS_JLN_SERIAL_NUMBER = 'adcps_jln_serial_number'
    ADCPS_JLN_VOLTS = 'adcps_jln_volts'
    ADCPS_JLN_RECORDS = 'adcps_jln_records'
    ADCPS_JLN_LENGTH = 'adcps_jln_length'
    ADCPS_JLN_EVENTS = 'adcps_jln_events'
    ADCPS_JLN_SAMPLES_WRITTEN = 'adcps_jln_samples_written'
    
<<<<<<< HEAD
class Adcps_jln_stc_metadataParserDataParticle(DataParticle):
=======
class AdcpsJlnStcMetadataParserDataParticle(DataParticle):
>>>>>>> upstream/master
    _data_particle_type = DataParticleType.ADCPS_JLN_META
    
    def _build_parsed_values(self):
        """
        Take something in the data format and turn it into
        a particle with the appropriate tag.
        @throws SampleException If there is a problem with sample creation
        """
        match = HEADER_FOOTER_MATCHER.search(self.raw_data) 
        if not match:
<<<<<<< HEAD
            raise SampleException("Adcps_jln_stc_metadataParserDataParticle: No regex match of \
                                  parsed sample data [%s]", self.raw_data)
        try:
            timestamp = match.group(1)   
            id_number = int(match.group(2))
            serial_number = int(match.group(3))
            voltage = float(match.group(4))  # this needs to be output with two decimal places
            num_records = int(match.group(5))
            length = int(match.group(6))
            num_events = int(match.group(7))
            samples_written = int(match.group(8))
    
        except (ValueError, TypeError, IndexError) as ex:
            raise SampleException("Error (%s) while decoding parameters in data: [%s]"
                                  % (ex, match.group(0)))
        result = [{DataParticleKey.VALUE_ID: Adcps_jln_stc_metadataParserDataParticleKey.ADCPS_JLN_TIMESTAMP,
                        DataParticleKey.VALUE: timestamp},
                    {DataParticleKey.VALUE_ID: Adcps_jln_stc_metadataParserDataParticleKey.ADCPS_JLN_ID,
                     DataParticleKey.VALUE: id_number},
                    {DataParticleKey.VALUE_ID: Adcps_jln_stc_metadataParserDataParticleKey.ADCPS_JLN_SERIAL_NUMBER,
                     DataParticleKey.VALUE: serial_number},
                    {DataParticleKey.VALUE_ID: Adcps_jln_stc_metadataParserDataParticleKey.ADCPS_JLN_VOLTS,
                     DataParticleKey.VALUE: voltage},
                    {DataParticleKey.VALUE_ID: Adcps_jln_stc_metadataParserDataParticleKey.ADCPS_JLN_RECORDS,
                     DataParticleKey.VALUE: num_records},
                    {DataParticleKey.VALUE_ID: Adcps_jln_stc_metadataParserDataParticleKey.ADCPS_JLN_LENGTH,
                     DataParticleKey.VALUE: length},
                    {DataParticleKey.VALUE_ID: Adcps_jln_stc_metadataParserDataParticleKey.ADCPS_JLN_EVENTS,
                     DataParticleKey.VALUE: num_events},
                    {DataParticleKey.VALUE_ID: Adcps_jln_stc_metadataParserDataParticleKey.ADCPS_JLN_SAMPLES_WRITTEN,
                     DataParticleKey.VALUE: samples_written}]
            
        return result

    def __eq__(self, arg):
        """
        Quick equality check for testing purposes. If they have the same raw
        data, timestamp, and new sequence, they are the same enough for this 
        particle
        """
        if ((self.raw_data == arg.raw_data) and \
            (self.contents[DataParticleKey.INTERNAL_TIMESTAMP] == \
             arg.contents[DataParticleKey.INTERNAL_TIMESTAMP])):
            return True
        else:
            if self.raw_data != arg.raw_data:
                log.debug('Raw data does not match')
            elif self.contents[DataParticleKey.INTERNAL_TIMESTAMP] != \
                 arg.contents[DataParticleKey.INTERNAL_TIMESTAMP]:
                log.debug('Timestamp does not match')
            return False


class Adcps_jln_stcParser(BufferLoadingParser):
=======
            raise SampleException("AdcpsJlnStcMetadataParserDataParticle: No regex match of \
                                  parsed sample data [%s]", self.raw_data)

        result = [self._encode_value(AdcpsJlnStcMetadataParserDataParticleKey.ADCPS_JLN_TIMESTAMP, match.group(1), str),
                  self._encode_value(AdcpsJlnStcMetadataParserDataParticleKey.ADCPS_JLN_ID, match.group(2), int),
                  self._encode_value(AdcpsJlnStcMetadataParserDataParticleKey.ADCPS_JLN_SERIAL_NUMBER, match.group(3), int),
                  self._encode_value(AdcpsJlnStcMetadataParserDataParticleKey.ADCPS_JLN_VOLTS, match.group(4), float),
                  self._encode_value(AdcpsJlnStcMetadataParserDataParticleKey.ADCPS_JLN_RECORDS, match.group(5), int),
                  self._encode_value(AdcpsJlnStcMetadataParserDataParticleKey.ADCPS_JLN_LENGTH, match.group(6), int),
                  self._encode_value(AdcpsJlnStcMetadataParserDataParticleKey.ADCPS_JLN_EVENTS, match.group(7), int),
                  self._encode_value(AdcpsJlnStcMetadataParserDataParticleKey.ADCPS_JLN_SAMPLES_WRITTEN, match.group(8), int),
                  ]
        return result


class AdcpsJlnStcParser(BufferLoadingParser):
>>>>>>> upstream/master
    def __init__(self,
                 config,
                 state,
                 stream_handle,
                 state_callback,
                 publish_callback,
<<<<<<< HEAD
                 *args, **kwargs):
        self._saved_header = None
        self._timestamp = 0.0 # need this? yes!
        self._record_buffer = [] # holds tuples of (record, state)`
        self._read_state = {StateKey.POSITION: 0}
        super(Adcps_jln_stcParser, self).__init__(config,
=======
                 exception_callback,
                 *args, **kwargs):
        self._saved_header = None
        self._read_state = {StateKey.POSITION: 0}
        super(AdcpsJlnStcParser, self).__init__(config,
>>>>>>> upstream/master
                                          stream_handle,
                                          state,
                                          self.sieve_function, 
                                          state_callback,
                                          publish_callback,
<<<<<<< HEAD
                                          *args,
                                          **kwargs)
        if state:
	    self.set_state(state)
	    if state[StateKey.POSITION] == 0:
		self._parse_header()
	else:
	    self._parse_header()     
    
    def set_state(self, state_obj):
        """
        initialize the state
        """
        log.trace("Attempting to set state to: %s", state_obj)
=======
                                          exception_callback,
                                          *args,
                                          **kwargs)
        if state:
            self.set_state(state)
            if state[StateKey.POSITION] == 0:
                self._parse_header()
        else:
            self._parse_header()

    def set_state(self, state_obj):
        """
        Set the value of the state object for this parser
        @param state_obj The object to set the state to. 
        @throws DatasetParserException if there is a bad state structure
        """
>>>>>>> upstream/master
        if not isinstance(state_obj, dict):
            raise DatasetParserException("Invalid state structure")
        if not (StateKey.POSITION in state_obj):
            raise DatasetParserException("Invalid state keys")
<<<<<<< HEAD
	self._chunker.clean_all_chunks()
	self._record_buffer = []
	self._saved_header = None
        self._state = state_obj
        self._read_state = state_obj
        self._stream_handle.seek(state_obj[StateKey.POSITION])
        
=======
        self._chunker.clean_all_chunks()
        self._record_buffer = []
        self._saved_header = None
        self._state = state_obj
        self._read_state = state_obj
        self._stream_handle.seek(state_obj[StateKey.POSITION])

>>>>>>> upstream/master
    def sieve_function(self, raw_data):
        """
        Sort through the raw data to identify new blocks of data that need processing.
        @param raw_data The raw data to search
        @retval list of matched start,end index found in raw_data
        """
        return_list = []
        st_idx = 0
        while st_idx < len(raw_data): 
            # Find a match, then advance
<<<<<<< HEAD
            match = DATA_MATCHER.match(raw_data[st_idx:])
            if match:
                end_packet_idx = match.end(0) - 6 + st_idx # string "Record" is length 6
                
                if end_packet_idx < len(raw_data):
                    # Skip record if "ReceiveFailure" marking exists.
                    match_rx_failure = RX_FAILURE_MATCHER.match(raw_data[st_idx:])
                    if not match_rx_failure and self.compare_checksum(match.group(1)[0:-2]):
                        return_list.append((match.start(0)+ st_idx, end_packet_idx))
                    if match_rx_failure:
                        log.debug("Record is marked with ReceiveFailure. Skipping record.")
                    if  not self.compare_checksum(match.group(1)[0:-2]):
                        # Extra noise is possible, so when checksums do not match, we log a message and continue parsing.
                        log.debug("Calculated checksum != received checksum")                     
=======
            fail_match = RX_FAILURE_MATCHER.match(raw_data[st_idx:])
            match = DATA_MATCHER.match(raw_data[st_idx:])
            if fail_match:
                # found a marked receive failure match, still add this to the chunks so it is not non-data
                end_packet_idx = fail_match.end(0) + st_idx
                return_list.append((fail_match.start(0) + st_idx, end_packet_idx))
                st_idx = end_packet_idx
            elif match:
                # found a real record match
                end_packet_idx = match.end(0) - 6 + st_idx # string "Record" or "#End U" is length 6
                if end_packet_idx < len(raw_data):
                    # Record "ReceiveFailure" and checksum are checked in parse_chunks
                    return_list.append((match.start(0)+ st_idx, end_packet_idx))                   
>>>>>>> upstream/master
                st_idx = end_packet_idx         
            else:
                st_idx += 1    
        return return_list
<<<<<<< HEAD
    
=======

>>>>>>> upstream/master
    def compare_checksum(self, raw_bytes):
        rcv_chksum = struct.unpack('<H', raw_bytes[-2:])
        calc_chksum = self.calc_checksum(raw_bytes[:-2])
        if rcv_chksum[0] == calc_chksum:
            return True
        return False
<<<<<<< HEAD
    
=======

>>>>>>> upstream/master
    def calc_checksum(self, raw_bytes):
        n_bytes = len(raw_bytes)
        # unpack raw bytes into unsigned chars
        unpack_str = '<'
        for i in range(0, n_bytes):
            unpack_str = unpack_str + 'B'
        fields = struct.unpack(unpack_str, raw_bytes)
        sum_fields = sum(fields)
        # since we are summing as unsigned short, limit range to 0 to 65535
        while sum_fields > 65535:
            sum_fields -= 65536
        return sum_fields

    def _parse_header(self):
        """
        Parse required parameters from the header and the footer.
        """
<<<<<<< HEAD
	# read the first bytes from the file
	header = self._stream_handle.read(HEADER_BYTES)

        # read the last 1024 bytes from the file       
=======
        # read the first bytes from the file
        header = self._stream_handle.read(HEADER_BYTES)
        if len(header) < HEADER_BYTES:
            log.error("File is not long enough to read header")
            raise SampleException("File is not long enough to read header")

        # read the last 43 bytes from the file     
>>>>>>> upstream/master
        self._stream_handle.seek(-FOOTER_BYTES,2)
        footer = self._stream_handle.read() 
        footer_match = FOOTER_MATCHER.search(footer)
        
<<<<<<< HEAD
	# parse the header to get the timestamp
        if HEADER_MATCHER.search(header):
=======
        # parse the header to get the timestamp
        if footer_match and HEADER_MATCHER.search(header):
>>>>>>> upstream/master
            header_match = HEADER_MATCHER.search(header)
            self._stream_handle.seek(len(header_match.group(0)))        
            timestamp_struct = time.strptime(header_match.group(1), "%Y%m%d %H%M%S") 
            timestamp_s = calendar.timegm(timestamp_struct) 
            self._timestamp = float(ntplib.system_to_ntp_time(timestamp_s))
            
            header_footer = header_match.group(0) + footer_match.group(0) 
            
<<<<<<< HEAD
            sample = self._extract_sample(Adcps_jln_stc_metadataParserDataParticle, HEADER_FOOTER_MATCHER,
=======
            sample = self._extract_sample(AdcpsJlnStcMetadataParserDataParticle, HEADER_FOOTER_MATCHER,
>>>>>>> upstream/master
                                          header_footer, self._timestamp)  
            
            if sample:
                # increment by the length of the matched header and save the header          
<<<<<<< HEAD
		self._increment_state(len(header_match.group(0)))
                self._saved_header = (sample, copy.copy(self._read_state))
        else:
            raise SampleException("File header does not match header regex")
        
=======
                self._increment_state(len(header_match.group(0)))
                self._saved_header = (sample, copy.copy(self._read_state))
        else:
            log.error("File header or footer does not match header regex")
            raise SampleException("File header or footer does not match header regex")

>>>>>>> upstream/master
    def _increment_state(self, increment):
        """
        Increment the parser position by the given increment in bytes.
        This indicates what has been read from the file, not what has
        been published.
        @ param increment number of bytes to increment parser position
        """
        self._read_state[StateKey.POSITION] += increment
<<<<<<< HEAD
        
=======
>>>>>>> upstream/master

    def parse_chunks(self):
        """
        Parse out any pending data chunks in the chunker. If
        it is a valid data piece, build a particle, update the position and
        timestamp. Go until the chunker has no more valid data.
        @retval a list of tuples with sample particles encountered in this
            parsing, plus the state. An empty list of nothing was parsed.
<<<<<<< HEAD
        """
        result_particles = []
        
        # header gets read in initialization, but need to send it back from parse_chunks
	if self._saved_header:
	    result_particles.append(self._saved_header)
	    self._saved_header = None
        
        (nd_timestamp, non_data, non_start, non_end) = self._chunker.get_next_non_data_with_index(clean=False)
        (timestamp, chunk, start, end) = self._chunker.get_next_data_with_index()
        non_data_flag = False
        if non_data is not None and non_end <= start:
            log.debug('start setting non_data_flag')
            non_data_flag = True
    
        while (chunk != None):
            
            data_match = DATA_MATCHER_B.match(chunk)
            if data_match:
                
                # pull out the date string from the data
                date_str = Adcps_jln_stc_instrumentParserDataParticle.unpack_date(data_match.group(1)[11:19])
                
                # convert to ntp
                converted_time = float(parser.parse(date_str).strftime("%s.%f"))
                adjusted_time = converted_time - time.timezone
                self._timestamp = ntplib.system_to_ntp_time(adjusted_time)
                # round to ensure the timestamps match
                self._timestamp = round(self._timestamp*100)/100
                log.debug("Converted time \"%s\" (unix: %10.9f) into %10.9f", date_str, adjusted_time, self._timestamp)
                
                # particle-ize the data block received, return the record
                # set timestamp here, converted to ntp64. pull out timestamp for this record               
                sample = self._extract_sample(Adcps_jln_stc_instrumentParserDataParticle, DATA_MATCHER_B, chunk, self._timestamp)
                       
                if sample:
                    # create particle
                    log.trace("Extracting sample chunk %s with read_state: %s", chunk, self._read_state)
                    if non_data == None:
                        non_data_length = 0
                    else:
                        non_data_length = len(non_data)
                    self._increment_state(len(chunk) + non_data_length)
                    result_particles.append((sample, copy.copy(self._read_state)))
                    
            (nd_timestamp, non_data, non_start, non_end) = self._chunker.get_next_non_data_with_index(clean=False)
            (timestamp, chunk, start, end) = self._chunker.get_next_data_with_index()

            # need to set a flag in case we read a chunk not matching the instrument ID and overwrite the non_data                    
            if non_data is not None and non_end <= start:
                log.debug('setting non_data_flag')
                non_data_flag = True
                
        return result_particles



=======
        """            
        result_particles = []

         # header gets read in initialization, but need to send it back from parse_chunks
        if self._saved_header:
            result_particles.append(self._saved_header)
            self._saved_header = None

        (nd_timestamp, non_data, non_start, non_end) = self._chunker.get_next_non_data_with_index(clean=False)
        (timestamp, chunk, start, end) = self._chunker.get_next_data_with_index(clean=True)
        self.handle_non_data(non_data, non_end, start)

        while (chunk != None):
            match_rx_failure = RX_FAILURE_MATCHER.match(chunk)
            # ignore marked failure records
            if not match_rx_failure:
                data_match = DATA_MATCHER_B.match(chunk)
                if data_match:
                    if self.compare_checksum(data_match.group(2)):
                        # pull out the date string from the data
                        date_str = AdcpsJlnStcInstrumentParserDataParticle.unpack_date(data_match.group(2)[11:19])

                        # convert to ntp
                        converted_time = float(parser.parse(date_str).strftime("%s.%f"))
                        adjusted_time = converted_time - time.timezone
                        self._timestamp = ntplib.system_to_ntp_time(adjusted_time)
                        # round to ensure the timestamps match
                        self._timestamp = round(self._timestamp*100)/100

                        # particle-ize the data block received, return the record
                        # set timestamp here, converted to ntp64. pull out timestamp for this record               
                        sample = self._extract_sample(AdcpsJlnStcInstrumentParserDataParticle, DATA_MATCHER_B, chunk, self._timestamp)

                        if sample:
                            # create particle
                            log.trace("Extracting sample chunk %s with read_state: %s", chunk, self._read_state)
                            self._increment_state(len(chunk))
                            result_particles.append((sample, copy.copy(self._read_state)))
                    else:
                        log.info("Found record whose checksum doesn't match")
                        self._exception_callback(SampleException("Found record whose checksum doesn't match"))
            else:
                log.info("Found RecieveFailure record, ignoring")

            (nd_timestamp, non_data, non_start, non_end) = self._chunker.get_next_non_data_with_index(clean=False)
            (timestamp, chunk, start, end) = self._chunker.get_next_data_with_index(clean=True)
            self.handle_non_data(non_data, non_end, start)

        return result_particles

    def handle_non_data(self, non_data, non_end, start):
        """
        Handle any non-data that is found in the file
        """
        # rx failure matches are expected non data, otherwise it is an error
        if non_data is not None and non_end <= start:
            # this non-data is an error, send an UnexpectedDataException and increment the state
            self._increment_state(len(non_data))
            log.debug("Found %d bytes of unexpected non-data" % len(non_data))
            # if non-data is a fatal error, directly call the exception, if it is not use the _exception_callback
            self._exception_callback(UnexpectedDataException("Found %d bytes of un-expected non-data %s" % (len(non_data), non_data)))
>>>>>>> upstream/master
