#!/usr/bin/env python

"""
@package mi.dataset.parser.ctdpf_ckl_wfp_sio_mule
@file marine-integrations/mi/dataset/parser/ctdpf_ckl_wfp_sio_mule.py
@author cgoodrich
@brief Parser for the ctdpf_ckl_wfp_sio_mule dataset driver
Release notes:

Initial Release
"""

__author__ = 'cgoodrich'
__license__ = 'Apache 2.0'

import re
import struct
import ntplib

from mi.core.log import get_logger
log = get_logger()
from mi.core.common import BaseEnum
from mi.core.instrument.data_particle import DataParticle, DataParticleKey
from mi.core.exceptions import SampleException
from mi.dataset.parser.sio_mule_common import SioMuleParser
from mi.core.exceptions import UnexpectedDataException

DATA_RECORD_BYTES = 11  # Number of bytes in a WC-type file
TIME_RECORD_BYTES = 8   # Two four byte timestamps
ETX_BYTE = 1            # The 1 byte ETX marker (\x03)
HEADER_BYTES = 33       # Number of bytes in the SIO header
DECIMATION_SPACER = 2   # This may or may not be present in the input stream

FOOTER_BYTES = DATA_RECORD_BYTES + TIME_RECORD_BYTES + DECIMATION_SPACER + ETX_BYTE

WC_HEADER_REGEX = b'\x01(WC)[0-9]{7}_([0-9a-fA-F]{4})[a-zA-Z]([0-9a-fA-F]{8})_([0-9a-fA-F]{2})_([0-9a-fA-F]{4})\x02'
WC_HEADER_MATCHER = re.compile(WC_HEADER_REGEX)

STD_EOP_REGEX = b'(\xFF{11})([\x00-\xFF]{8})\x03'
STD_EOP_MATCHER = re.compile(STD_EOP_REGEX)

DECI_EOP_REGEX = b'(\xFF{11})([\x00-\xFF]{8})([\x00-\xFF]{2})\x03'
DECI_EOP_MATCHER = re.compile(DECI_EOP_REGEX)

DATA_REGEX = b'([\x00-\xFF]{11})'
DATA_MATCHER = re.compile(DATA_REGEX)

EOP_REGEX = b'(\xFF{11})'
EOP_MATCHER = re.compile(EOP_REGEX)


class DataParticleType(BaseEnum):
    DATA = 'ctdpf_ckl_wfp_instrument'
    METADATA = 'ctdpf_ckl_wfp_sio_mule_metadata'
    RECOVERED_DATA = 'ctdpf_ckl_wfp_instrument_recovered'
    RECOVERED_METADATA = 'ctdpf_ckl_wfp_metadata_recovered'

class CtdpfCklWfpSioMuleDataParticleKey(BaseEnum):
    CONDUCTIVITY = 'conductivity'
    TEMPERATURE = 'temperature'
    PRESSURE = 'pressure'


class CtdpfCklWfpSioMuleMetadataParticleKey(BaseEnum):
    WFP_TIME_ON = 'wfp_time_on'
    WFP_TIME_OFF = 'wfp_time_off'
    WFP_NUMBER_SAMPLES = 'wfp_number_samples'
    WFP_DECIMATION_FACTOR = 'wfp_decimation_factor'


class CtdpfCklWfpSioMuleDataParticle(DataParticle):
    """
    Class for creating the data particle
    """
    _data_particle_type = DataParticleType.DATA

    def _build_parsed_values(self):
        """
        Take something in the data format and turn it into an array of dictionaries defining the data in the particle
        with the appropriate tag.
        """
        result = [self._encode_value(CtdpfCklWfpSioMuleDataParticleKey.CONDUCTIVITY, self.raw_data[0], int),
                  self._encode_value(CtdpfCklWfpSioMuleDataParticleKey.TEMPERATURE, self.raw_data[1], int),
                  self._encode_value(CtdpfCklWfpSioMuleDataParticleKey.PRESSURE, self.raw_data[2], int)
        ]

        return result


class CtdpfCklWfpSioMuleMetadataParticle(DataParticle):
    """
    Class for creating the metadata particle
    """
    _data_particle_type = DataParticleType.METADATA

    def _build_parsed_values(self):
        """
        Take something in the data format and turn it into
        an array of dictionaries defining the data in the particle
        with the appropriate tag.
        """
        result = [self._encode_value(CtdpfCklWfpSioMuleMetadataParticleKey.WFP_TIME_ON,
                                     self.raw_data[0], int),
                  self._encode_value(CtdpfCklWfpSioMuleMetadataParticleKey.WFP_TIME_OFF,
                                     self.raw_data[1], int),
                  self._encode_value(CtdpfCklWfpSioMuleMetadataParticleKey.WFP_NUMBER_SAMPLES,
                                     self.raw_data[2], int)]

        # Have to split the result build due to a bug in the _encode_value code.
        if self.raw_data[3] is not None:
            result.append(self._encode_value(CtdpfCklWfpSioMuleMetadataParticleKey.WFP_DECIMATION_FACTOR,
                                             self.raw_data[3], int))
        else:
            result.append({DataParticleKey.VALUE_ID: CtdpfCklWfpSioMuleMetadataParticleKey.WFP_DECIMATION_FACTOR,
                           DataParticleKey.VALUE: None})

        return result


class CtdpfCklWfpSioMuleParser(SioMuleParser):
    """
    Make use of the common Sio Mule file parser
    """
    def __init__(self,
                 config,
                 state,
                 stream_handle,
                 state_callback,
                 publish_callback,
                 exception_callback):

        super(CtdpfCklWfpSioMuleParser, self).__init__(config,
                                                       stream_handle,
                                                       state,
                                                       self.sieve_function,
                                                       state_callback,
                                                       publish_callback,
                                                       exception_callback)
        self._metadataSent = False
        self._dataLength = 0
        self._startIndex = HEADER_BYTES + 1
        self._endIndex = 0
        self._goodHeader = False
        self._goodFooter = False
        self._numberOfRecords = 0
        self._recordNumber = 0.0
        self._timeIncrement = 1
        self._decimationFactor = None
        self._startTime = 0
        self._endTime = 0
        self._startData = 0
        self._footerData = None
        self._RecordData = None

    def extract_metadata_particle(self, raw_data, timestamp):
        """
        Class for extracting the metadata data particle
        @param raw_data raw data to parse, in this case a tuple of the time string to parse and the number of records
        @param timestamp timestamp in NTP64
        """
        sample = self._extract_sample(CtdpfCklWfpSioMuleMetadataParticle, None, raw_data, timestamp)
        return sample

    def extract_data_particle(self, raw_data, timestamp):
        """
        Class for extracting the data sample data particle
        @param raw_data the raw data to parse
        @param timestamp the timestamp in NTP64
        """
        sample = self._extract_sample(CtdpfCklWfpSioMuleDataParticle, None, raw_data, timestamp)
        return sample

    def process_header(self, chunk):
        """
        Determine if this is the header for a WC file
        @retval True (good header), False (bad header)
        """
        header = chunk[0:HEADER_BYTES]
        match = WC_HEADER_MATCHER.search(header)
        if match:
            self._dataLength = int(match.group(2), 16)
            self._startIndex = match.start(0)
            self._endIndex = match.end(0) + self._dataLength
            self._startData = match.end(0)
            self._goodHeader = True
        else:
            self._goodHeader = False

    def process_footer(self, chunk):
        """
        Determine if this footer has a decimation factor (and what it is) or not.
        Also determine the instrument start/stop times and the number of records in the chunk
        @retval True (good footer), False (bad footer)
        """
        footer = chunk[((self._endIndex - FOOTER_BYTES) + 1):self._endIndex + 1]
        std_match = STD_EOP_MATCHER.search(footer)
        deci_match = DECI_EOP_MATCHER.search(footer)
        final_match = deci_match
        if deci_match:
            self._numberOfRecords = ((self._dataLength + 1) - FOOTER_BYTES) / 11
            self._decimationFactor = struct.unpack('>H', final_match.group(3))[0]
            self._goodFooter = True
        elif std_match:
            footerStart = std_match.start(0)
            footerEnd = std_match.end(0)
            footer = footer[footerStart:footerEnd]
            final_match = STD_EOP_MATCHER.search(footer)
            self._numberOfRecords = ((self._dataLength + 1) - (FOOTER_BYTES - DECIMATION_SPACER)) / 11
            self._decimationFactor = 0
            self._goodFooter = True
        else:
            self._goodFooter = False
            log.warning('CTDPF_CKL_SIO_MULE: Bad footer detected, cannot parse chunk')

        if self._goodFooter:
            timefields = struct.unpack('>II', final_match.group(2))
            self._startTime = int(timefields[0])
            self._endTime = int(timefields[1])
            if self._numberOfRecords > 0:
                self._timeIncrement = float(self._endTime - self._startTime) / float(self._numberOfRecords)
            else:
                self._goodFooter = False
                log.warning('CTDPF_CKL_SIO_MULE: Bad footer detected, cannot parse chunk')

    # Overrides the parse_chunks routine in SioMuleCommon
    def parse_chunks(self):
        """
        Parse out any pending data chunks in the chunker. If it is a valid data piece, build a particle,
        update the position and timestamp. Go until the chunker has no more valid data.
        @retval a list of tuples
        """
        result_particles = []
        (timestamp, chunk, start, end) = self._chunker.get_next_data_with_index(clean=True)

        while chunk is not None:

            sample_count = 0

            self.process_header(chunk)

            if self._goodHeader:
                self.process_footer(chunk)

                if self._goodFooter:

                    timestamp = float(ntplib.system_to_ntp_time(self._startTime))
                    self._footerData = (self._startTime, self._endTime, self._numberOfRecords, self._decimationFactor)
                    sample = self.extract_metadata_particle(self._footerData, timestamp)
                    if sample is not None:
                        result_particles.append(sample)
                        sample_count = 1

                    moreRecords = True
                    dataRecord = chunk[self._startData:self._startData + DATA_RECORD_BYTES]
                    self._startData += DATA_RECORD_BYTES
                    self._recordNumber = 0.0
                    timestamp = float(ntplib.system_to_ntp_time(float(self._startTime) +
                                                                (self._recordNumber * self._timeIncrement)))

                    while moreRecords:
                        dataFields = struct.unpack('>I', '\x00' + dataRecord[0:3]) + \
                                     struct.unpack('>I', '\x00' + dataRecord[3:6]) + \
                                     struct.unpack('>I', '\x00' + dataRecord[6:9]) + \
                                     struct.unpack('>H', dataRecord[9:11])
                        self._RecordData = (dataFields[0], dataFields[1], dataFields[2])
                        sample = self.extract_data_particle(self._RecordData, timestamp)
                        if sample is not None:
                            result_particles.append(sample)
                            sample_count += 1

                        dataRecord = chunk[self._startData:self._startData + DATA_RECORD_BYTES]
                        self._recordNumber += 1.0
                        timestamp = float(ntplib.system_to_ntp_time(float(self._startTime) +
                                                                    (self._recordNumber * self._timeIncrement)))
                        eopMatch = EOP_MATCHER.search(dataRecord)
                        if eopMatch:
                            moreRecords = False
                        else:
                            self._startData += DATA_RECORD_BYTES

            self._chunk_sample_count.append(sample_count)
            (timestamp, chunk, start, end) = self._chunker.get_next_data_with_index(clean=True)

        return result_particles
