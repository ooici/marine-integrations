#!/usr/bin/env python

"""
@package mi.dataset.parser.adcps
@file mi/dataset/parser/adcps.py
@author Emily Hahn
@brief An adcps-specific dataset agent parser
"""

__author__ = 'Emily Hahn'
__license__ = 'Apache 2.0'

import re
import struct
import ntplib
import time
import datetime
import binascii
from dateutil import parser

from mi.core.log import get_logger; log = get_logger()
from mi.dataset.parser.sio_mule_common import SioMuleParser, SIO_HEADER_MATCHER
from mi.core.common import BaseEnum
from mi.core.exceptions import SampleException, RecoverableSampleException
from mi.core.exceptions import DatasetParserException, UnexpectedDataException
from mi.core.instrument.data_particle import DataParticle, DataParticleKey, DataParticleValue
from mi.core.time import string_to_ntp_date_time

class DataParticleType(BaseEnum):
    SAMPLE = 'adcps_jln_sio_mule_instrument'

class AdcpsParserDataParticleKey(BaseEnum):
    CONTROLLER_TIMESTAMP = 'controller_timestamp'
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
    ADCPS_JLN_PITCH = 'adcps_jln_pitch'
    ADCPS_JLN_ROLL = 'adcps_jln_roll'
    ADCPS_JLN_TEMP = 'adcps_jln_temp'
    ADCPS_JLN_PRESSURE = 'adcps_jln_pressure'
    VELOCITY_PO_ERROR_FLAG = 'velocity_po_error_flag'
    VELOCITY_PO_UP_FLAG = 'velocity_po_up_flag'
    VELOCITY_PO_NORTH_FLAG = 'velocity_po_north_flag'
    VELOCITY_PO_EAST_FLAG = 'velocity_po_east_flag'
    SUBSAMPLING_PARAMETER = 'subsampling_parameter'
    ADCPS_JLN_STARTBIN = 'adcps_jln_startbin'
    ADCPS_JLN_BINS = 'adcps_jln_bins'
    ADCPS_JLN_VEL_EAST = 'adcps_jln_vel_east'
    ADCPS_JLN_VEL_NORTH = 'adcps_jln_vel_north'
    ADCPS_JLN_VEL_UP = 'adcps_jln_vel_up'
    ADCPS_JLN_VEL_ERROR = 'adcps_jln_vel_error'

DATA_WRAPPER_REGEX = b'<Executing/>\x0d\x0a<SampleData ID=\'0x[0-9a-f]+\' LEN=\'[0-9]+\' ' \
                     'CRC=\'(0x[0-9a-f]+)\'>([\x00-\xFF]+)</SampleData>\x0d\x0a<Executed/>\x0d\x0a'
DATA_WRAPPER_MATCHER = re.compile(DATA_WRAPPER_REGEX)
DATA_FAIL_REGEX = b'<ERROR type=(.+) msg=(.+)/>\x0d\x0a'
DATA_FAIL_MATCHER = re.compile(DATA_FAIL_REGEX)
DATA_REGEX = b'\x6e\x7f[\x00-\xFF]{32}([\x00-\xFF]+)([\x00-\xFF]{2})'
DATA_MATCHER = re.compile(DATA_REGEX)

CRC_TABLE = [0, 1996959894, 3993919788, 2567524794, 124634137, 1886057615, 3915621685, 2657392035,
249268274, 2044508324, 3772115230, 2547177864, 162941995, 2125561021, 3887607047, 2428444049,
498536548, 1789927666, 4089016648, 2227061214, 450548861, 1843258603, 4107580753, 2211677639,
325883990, 1684777152, 4251122042, 2321926636, 335633487, 1661365465, 4195302755, 2366115317,
997073096, 1281953886, 3579855332, 2724688242, 1006888145, 1258607687, 3524101629, 2768942443,
901097722, 1119000684, 3686517206, 2898065728, 853044451, 1172266101, 3705015759, 2882616665,
651767980, 1373503546, 3369554304, 3218104598, 565507253, 1454621731, 3485111705, 3099436303,
671266974, 1594198024, 3322730930, 2970347812, 795835527, 1483230225, 3244367275, 3060149565,
1994146192, 31158534, 2563907772, 4023717930, 1907459465, 112637215, 2680153253, 3904427059,
2013776290, 251722036, 2517215374, 3775830040, 2137656763, 141376813, 2439277719, 3865271297,
1802195444, 476864866, 2238001368, 4066508878, 1812370925, 453092731, 2181625025, 4111451223,
1706088902, 314042704, 2344532202, 4240017532, 1658658271, 366619977, 2362670323, 4224994405,
1303535960, 984961486, 2747007092, 3569037538, 1256170817, 1037604311, 2765210733, 3554079995,
1131014506, 879679996, 2909243462, 3663771856, 1141124467, 855842277, 2852801631, 3708648649,
1342533948, 654459306, 3188396048, 3373015174, 1466479909, 544179635, 3110523913, 3462522015,
1591671054, 702138776, 2966460450, 3352799412, 1504918807, 783551873, 3082640443, 3233442989,
3988292384, 2596254646, 62317068, 1957810842, 3939845945, 2647816111, 81470997, 1943803523,
3814918930, 2489596804, 225274430, 2053790376, 3826175755, 2466906013, 167816743, 2097651377,
4027552580, 2265490386, 503444072, 1762050814, 4150417245, 2154129355, 426522225, 1852507879,
4275313526, 2312317920, 282753626, 1742555852, 4189708143, 2394877945, 397917763, 1622183637,
3604390888, 2714866558, 953729732, 1340076626, 3518719985, 2797360999, 1068828381, 1219638859,
3624741850, 2936675148, 906185462, 1090812512, 3747672003, 2825379669, 829329135, 1181335161,
3412177804, 3160834842, 628085408, 1382605366, 3423369109, 3138078467, 570562233, 1426400815,
3317316542, 2998733608, 733239954, 1555261956, 3268935591, 3050360625, 752459403, 1541320221,
2607071920, 3965973030, 1969922972, 40735498, 2617837225, 3943577151, 1913087877, 83908371,
2512341634, 3803740692, 2075208622, 213261112, 2463272603, 3855990285, 2094854071, 198958881,
2262029012, 4057260610, 1759359992, 534414190, 2176718541, 4139329115, 1873836001, 414664567,
2282248934, 4279200368, 1711684554, 285281116, 2405801727, 4167216745, 1634467795, 376229701,
2685067896, 3608007406, 1308918612, 956543938, 2808555105, 3495958263, 1231636301, 1047427035,
2932959818, 3654703836, 1088359270, 936918000, 2847714899, 3736837829, 1202900863, 817233897,
3183342108, 3401237130, 1404277552, 615818150, 3134207493, 3453421203, 1423857449, 601450431,
3009837614, 3294710456, 1567103746, 711928724, 3020668471, 3272380065, 1510334235, 755167117 ]

class AdcpsParserDataParticle(DataParticle):
    """
    Class for parsing data from the ADCPS instrument on a MSFM platform node
    """
    
    _data_particle_type = DataParticleType.SAMPLE
    
    def __init__(self, raw_data,
                 port_timestamp=None,
                 internal_timestamp=None,
                 preferred_timestamp=DataParticleKey.PORT_TIMESTAMP,
                 quality_flag=DataParticleValue.OK,
                 new_sequence=None):
        super(AdcpsParserDataParticle, self).__init__(raw_data,
                                                      port_timestamp=None,
                                                      internal_timestamp=None,
                                                      preferred_timestamp=DataParticleKey.PORT_TIMESTAMP,
                                                      quality_flag=DataParticleValue.OK,
                                                      new_sequence=None)
        self._data_match = DATA_MATCHER.match(self.raw_data[8:])
        if not self._data_match:
            raise RecoverableSampleException("AdcpsParserDataParticle: No regex match of "\
                                              "parsed sample data [%s]" % self.raw_data[8:])
        date_str = self.unpack_date(self._data_match.group(0)[11:19])
        # convert to unix
        converted_time = float(parser.parse(date_str).strftime("%s.%f"))
        adjusted_time = converted_time - time.timezone
        self.set_internal_timestamp(unix_time=adjusted_time)
    
    def _build_parsed_values(self):
        """
        Take something in the binary data values and turn it into a
        particle with the appropriate tag.
        throws SampleException If there is a problem with sample creation
        """
        # raw data includes the sio controller timestamp at the start
        # match the data inside the wrapper
        result = []
        if self._data_match:
            match = self._data_match
            try:
                fields = struct.unpack('<HHIBBBdHhhhIbBB', match.group(0)[0:34])
                num_bytes = fields[1]
                if len(match.group(0)) - 2 != num_bytes:
                    raise ValueError('num bytes %d does not match data length %d'
                              % (num_bytes, len(match.group(0))))
                nbins = fields[14]
                if len(match.group(0)) < (36+(nbins*8)):
                    raise ValueError('Number of bins %d does not fit in data length %d'%(nbins,
                                                                                         len(match.group(0))))
                date_fields = struct.unpack('HBBBBBB', match.group(0)[11:19])
    
                # create a string with the right number of shorts to unpack
                struct_format = '>'
                for i in range(0,nbins):
                    struct_format = struct_format + 'h'
    
                bin_len = nbins*2
                vel_err = struct.unpack(struct_format, match.group(0)[34:(34+bin_len)])
                vel_up = struct.unpack(struct_format, match.group(0)[(34+bin_len):(34+(bin_len*2))])
                vel_north = struct.unpack(struct_format, match.group(0)[(34+(bin_len*2)):(34+(bin_len*3))])
                vel_east = struct.unpack(struct_format, match.group(0)[(34+(bin_len*3)):(34+(bin_len*4))])
    
                checksum = struct.unpack('<H', match.group(0)[(34+(bin_len*4)):(36+(bin_len*4))])
                calculated_checksum = self.calc_inner_checksum(match.group(0)[:-2])
                if checksum[0] != calculated_checksum:
                    raise ValueError("Inner checksum %s does not match %s" % (checksum[0], calculated_checksum))
            except (ValueError, TypeError, IndexError) as ex:
                # we can recover and read additional samples after this, just this one is missed
                log.warn("Error %s while decoding parameters in data [%s]", ex, match.group(0))
                raise RecoverableSampleException("Error (%s) while decoding parameters in data: [%s]" % 
                                                (ex, match.group(0)))
    
            result = [self._encode_value(AdcpsParserDataParticleKey.CONTROLLER_TIMESTAMP, self.raw_data[0:8],
                                         AdcpsParserDataParticle.encode_int_16),
                      self._encode_value(AdcpsParserDataParticleKey.ADCPS_JLN_NUMBER, fields[2], int),
                      self._encode_value(AdcpsParserDataParticleKey.ADCPS_JLN_UNIT_ID, fields[3], int),
                      self._encode_value(AdcpsParserDataParticleKey.ADCPS_JLN_FW_VERS, fields[4], int),
                      self._encode_value(AdcpsParserDataParticleKey.ADCPS_JLN_FW_REV, fields[5], int),
                      self._encode_value(AdcpsParserDataParticleKey.ADCPS_JLN_YEAR, date_fields[0], int),
                      self._encode_value(AdcpsParserDataParticleKey.ADCPS_JLN_MONTH, date_fields[1], int),
                      self._encode_value(AdcpsParserDataParticleKey.ADCPS_JLN_DAY, date_fields[2], int),
                      self._encode_value(AdcpsParserDataParticleKey.ADCPS_JLN_HOUR, date_fields[3], int),
                      self._encode_value(AdcpsParserDataParticleKey.ADCPS_JLN_MINUTE, date_fields[4], int),
                      self._encode_value(AdcpsParserDataParticleKey.ADCPS_JLN_SECOND, date_fields[5], int),
                      self._encode_value(AdcpsParserDataParticleKey.ADCPS_JLN_HSEC, date_fields[6], int),
                      self._encode_value(AdcpsParserDataParticleKey.ADCPS_JLN_HEADING, fields[7], int),
                      self._encode_value(AdcpsParserDataParticleKey.ADCPS_JLN_PITCH, fields[8], int),
                      self._encode_value(AdcpsParserDataParticleKey.ADCPS_JLN_ROLL, fields[9], int),
                      self._encode_value(AdcpsParserDataParticleKey.ADCPS_JLN_TEMP, fields[10], int),
                      self._encode_value(AdcpsParserDataParticleKey.ADCPS_JLN_PRESSURE, fields[11], int),
                      self._encode_value(AdcpsParserDataParticleKey.VELOCITY_PO_ERROR_FLAG, fields[12]&1, int),
                      self._encode_value(AdcpsParserDataParticleKey.VELOCITY_PO_UP_FLAG, (fields[12]&2) >> 1, int),
                      self._encode_value(AdcpsParserDataParticleKey.VELOCITY_PO_NORTH_FLAG, (fields[12]&4) >> 2, int),
                      self._encode_value(AdcpsParserDataParticleKey.VELOCITY_PO_EAST_FLAG, (fields[12]&8) >> 3, int),
                      self._encode_value(AdcpsParserDataParticleKey.SUBSAMPLING_PARAMETER, (fields[12]&240) >> 4, int),
                      self._encode_value(AdcpsParserDataParticleKey.ADCPS_JLN_STARTBIN, fields[13], int),
                      self._encode_value(AdcpsParserDataParticleKey.ADCPS_JLN_BINS, fields[14], int),
                      self._encode_value(AdcpsParserDataParticleKey.ADCPS_JLN_VEL_ERROR, vel_err, list),
                      self._encode_value(AdcpsParserDataParticleKey.ADCPS_JLN_VEL_UP, vel_up, list),
                      self._encode_value(AdcpsParserDataParticleKey.ADCPS_JLN_VEL_NORTH, vel_north, list),
                      self._encode_value(AdcpsParserDataParticleKey.ADCPS_JLN_VEL_EAST, vel_east, list)]

        log.trace('AdcpsParserDataParticle: particle=%s', result)
        return result

    def unpack_date(self, data):
        fields = struct.unpack('HBBBBBB', data)
        #log.debug('Unpacked data into date fields %s', fields)
        zulu_ts = "%04d-%02d-%02dT%02d:%02d:%02d.%02dZ" % (
            fields[0], fields[1], fields[2], fields[3],
            fields[4], fields[5], fields[6])
        return zulu_ts

    @staticmethod
    def encode_int_16(hex_str):
        return int(hex_str, 16)

    def calc_inner_checksum(self, data_block):
        """
        calculate the checksum on the adcps data block, which occurs at the end of the data block
        """
        crc = 0
        # sum all bytes and take last 2 bytes
        for i in range(0, len(data_block)):
            val = struct.unpack('<B', data_block[i])
            crc += int(val[0])
            # values are "unsigned short", wrap around if we go outside
            if crc < 0:
                crc += 65536
            elif crc > 65536:
                crc -= 65536
        return crc

class AdcpsParser(SioMuleParser):

    def __init__(self,
                 config,
                 state,
                 stream_handle,
                 state_callback,
                 publish_callback,
                 exception_callback,
                 *args, **kwargs):
        super(AdcpsParser, self).__init__(config,
                                          stream_handle,
                                          state,
                                          self.sieve_function,
                                          state_callback,
                                          publish_callback,
                                          exception_callback,
                                          *args,
                                          **kwargs)

    def parse_chunks(self):
        """
        Parse out any pending data chunks in the chunker. If
        it is a valid data piece, build a particle, update the position and
        timestamp. Go until the chunker has no more valid data.
        @retval a list of tuples with sample particles encountered in this
            parsing, plus the state. An empty list of nothing was parsed.
        """            
        result_particles = []
        (nd_timestamp, non_data) = self._chunker.get_next_non_data(clean=False)
        (timestamp, chunk) = self._chunker.get_next_data()

        sample_count = 0

        while (chunk != None):
            header_match = SIO_HEADER_MATCHER.match(chunk)
            sample_count = 0
            if header_match.group(1) == 'AD':
                log.debug("matched chunk header %s", chunk[1:32])
                # start at 33
                chunk_idx = 33
                end_idx_okay = 33
                while chunk_idx <= len(chunk):
                    data_fail_match = DATA_FAIL_MATCHER.match(chunk[chunk_idx:])
                    data_wrapper_match = DATA_WRAPPER_MATCHER.match(chunk[chunk_idx:])
                    if data_wrapper_match:
                        calculated_xml_checksum = self.calc_xml_checksum(data_wrapper_match.group(2))
                        xml_checksum = int(data_wrapper_match.group(1), 16)
                        if calculated_xml_checksum == xml_checksum:
                            data_match = DATA_MATCHER.search(data_wrapper_match.group(2))
                            if data_match:
                                if end_idx_okay != chunk_idx:
                                    log.info("Unexpected data found from index %d to %d, %s", end_idx_okay,
                                             chunk_idx, chunk[end_idx_okay:chunk_idx])
                                    self._exception_callback(UnexpectedDataException("Unexpected data found %s" % 
                                                                                      chunk[end_idx_okay:chunk_idx]))
                                log.debug('Found data match in chunk %s', chunk[1:32])
                                # particle-ize the data block received, return the record
                                sample = self._extract_sample(AdcpsParserDataParticle, None,
                                                              header_match.group(3) + data_match.group(0),
                                                              None)
                                if sample:
                                    # create particle
                                    result_particles.append(sample)
                                    sample_count += 1
                            else:
                                self._exception_callback(RecoverableSampleException("Matched adcps xml wrapper but not data inside, %s" % 
                                                                                    data_wrapper_match.group(0)))
                        else:
                            self._exception_callback(RecoverableSampleException("Xml checksum %s does not match calculated %s" % 
                                                                                (xml_checksum, calculated_xml_checksum)))
                        chunk_idx += len(data_wrapper_match.group(0))
                        end_idx_okay = chunk_idx
                    elif data_fail_match:
                        # we found an adcps failure message, no data in here just an error
                        if end_idx_okay != chunk_idx:
                            log.info("Unexpected data found from index %d to %d, %s", end_idx_okay,
                                     chunk_idx, chunk[end_idx_okay:chunk_idx])
                            self._exception_callback(UnexpectedDataException("Unexpected data found %s" % 
                                                                              chunk[end_idx_okay:chunk_idx]))
                        self._exception_callback(RecoverableSampleException("Found adcps error type %s exception %s" % 
                                                                            (data_fail_match.group(1), data_fail_match.group(2))))
                        chunk_idx += len(data_fail_match.group(0))
                        end_idx_okay = chunk_idx
                    else:
                        # if we have to skip bytes, we have unexplained data
                        chunk_idx += 1
            self._chunk_sample_count.append(sample_count)

            (nd_timestamp, non_data) = self._chunker.get_next_non_data(clean=False)
            (timestamp, chunk) = self._chunker.get_next_data()

        return result_particles
    
    def calc_xml_checksum(self, data_block):
        """
        calculate the checksum to compare to the xml wrapper around adcps block of data
        """
        # corresponds to 0xFFFFFFFF
        crc = 4294967295
        for i in range(0, len(data_block)):
            val = struct.unpack('<b', data_block[i])
            table_idx = (crc ^ int(val[0])) &  255
            crc = CRC_TABLE[table_idx] ^ (crc >> 8)
        return crc
