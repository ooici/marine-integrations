#!/usr/bin/env python

"""
@package mi.dataset.parser.wfp_parser WFP platform data set agent information
@file mi/dataset/parser/wfp_parser.py
@author Roger Unwin
@brief A WFP-specific data set agent package
This module should contain classes that handle parsers used with WFP dataset
files. It initially holds WFP-specific logic, ultimately more than that.
"""
__author__ = 'Roger Unwin'
__license__ = 'Apache 2.0'

import copy
import re
import time
import ntplib
from dateutil import parser
from functools import partial

from mi.core.log import get_logger ; log = get_logger()

from mi.core.common import BaseEnum
from mi.core.exceptions import SampleException, DatasetParserException
from mi.core.instrument.chunker import StringChunker
from mi.core.instrument.data_particle import DataParticle, DataParticleKey
from mi.dataset.dataset_parser import BufferLoadingParser



#TIME_REGEX = r'Vehicle began profiling at (\d{1,2})/(\d{1,2})/(\d{4})\s*(\d{1,2}):(\d{1,2}):(\d{1,2})'
#TIME_MATCHER = re.compile(TIME_REGEX, re.DOTALL)

# Date,[mA],[V],[dbar],Par[mV],scatSig,chlSig,CDOMSig
#DATA_REGEX = r'(\d{1,2}/\d{1,2}/\d{4}\s*\d{1,2}:\d{1,2}:\d{1,2}),([\-\d\.]+),([\-\d\.]+),([\-\d\.]+),([\-\d\.]+),([\-\d]+),([\-\d]+),([\-\d]+)'
DATA_REGEX = r'(\d*/\d*/\d*\s*\d*:\d*:\d*),([\-\d\.]*),([\-\d\.]*),([\-\d\.]*),([\-\d\.]*),([\-\d]*),([\-\d]*),([\-\d]*)'
DATA_MATCHER = re.compile(DATA_REGEX, re.DOTALL)

# MM-DD-YYYY HH:MM:SS    ,Sndm/s,TmpC,Heading,Pitch,Roll,magnHx,magnHy,magnHz,Beams,Cells,Beam1,Beam2,Beam3,Beam4,Beam5,Vel[0,0],Vel[1,0],Vel[2,0],Amp[0,0],Amp[1,0],Amp[2,0],Corr[0,0],Corr[1,0],Corr[2,0]
VEL_DATA_REGEX = r'(\d*\-\d*\-\d*\s*\d*:\d*:[\.\d]*),([\-\d\.]*),([\-\d\.]*),([\-\d\.]*),([\-\d\.]*),([\-\d\.]*),([\-\d\.]*),([\-\d\.]*),([\-\d\.]*),([\-\d\.]*),([\-\d\.]*),([\-\d\.]*),([\-\d\.]*),([\-\d\.]*),([\-\d\.]*),([\-\d\.]*),([\-\d\.]*),([\-\d\.]*),([\-\d\.]*),([\-\d\.]*),([\-\d\.]*),([\-\d\.]*),([\-\d\.]*),([\-\d\.]*)'
VEL_DATA_MATCHER = re.compile(VEL_DATA_REGEX, re.DOTALL)



class StateKey(BaseEnum):
    POSITION = "position"


class DataParticleType(BaseEnum):
    # Data particle types for the Wire Following Profiler E output files.
    WFP_PARADK = 'wfp_parad_k_parsed'
    WFP_FLORTK = 'wfp_flort_k_parsed'
    WFP_UNDEFINED = 'wfp_undefined'
    WFP_ENGINEERING = 'wfp_engineering_parsed'
    WFP_VEL3D = 'vel3dk_parsed'

class WfpParticleKey(BaseEnum):
    """
    Common WFP particle parameters
    """
    TIMESTAMP = 'timestamp'


class WfpParticle(DataParticle):
    _data_particle_type = DataParticleType.WFP_UNDEFINED

    def _build_parsed_values(self):
        match = DATA_MATCHER.match(self.raw_data)
        if not match:
            raise SampleException("WfpParserDataParticle: No regex match of parsed sample data: [%s]", self.raw_data)

        try:
            # Date,[mA],[V],[dbar],Par[mV],scatSig,chlSig,CDOMSig

            timestamp = self._convert_string_to_timestamp(match.group(1))
            current = float(match.group(2))
            voltage = float(match.group(3))
            #presure = float(match.group(4)) # nobody wants you!
            cdom = float(match.group(8))
            chl = float(match.group(7))
            scat_sig = float(match.group(6))
            par = float(match.group(5))

        except (ValueError, TypeError, IndexError) as ex:
            raise SampleException("Error (%s) while decoding parameters in data: [%s]"
                                  % (ex, self.raw_data))

        result = [{DataParticleKey.VALUE_ID: WfpParticleKey.TIMESTAMP,
                   DataParticleKey.VALUE: timestamp},
                  {DataParticleKey.VALUE_ID: WfpEngineeringDataParticleKey.CURRENT,
                   DataParticleKey.VALUE: current},
                  {DataParticleKey.VALUE_ID: WfpEngineeringDataParticleKey.VOLTAGE,
                   DataParticleKey.VALUE: voltage},
                  #{DataParticleKey.VALUE_ID: WfpEngineeringDataParticleKey.PRESURE,
                  # DataParticleKey.VALUE: presure},
                  {DataParticleKey.VALUE_ID: WfpFlortkDataParticleKey.CDOM,
                   DataParticleKey.VALUE: cdom},
                  {DataParticleKey.VALUE_ID: WfpFlortkDataParticleKey.CHL,
                   DataParticleKey.VALUE: chl},
                  {DataParticleKey.VALUE_ID: WfpFlortkDataParticleKey.SCAT_SIG,
                   DataParticleKey.VALUE: scat_sig},
                  {DataParticleKey.VALUE_ID: WfpParadkDataParticleKey.PAR,
                   DataParticleKey.VALUE: par}]
        log.trace('WfpParticle RETURNING %s', result)
        return result

    @staticmethod
    def _convert_string_to_timestamp(ts_string):
        """
        Convert passed in zulu timestamp string to a ntp timestamp float
        """
        log.trace("ts_string = " + ts_string)

        TS_REGEX = r'(\d{1,2})[/\-](\d{1,2})[/\-](\d{4})\s*(\d{1,2}):(\d{1,2}):(\d{1,2})'
        TS_MATCHER = re.compile(TS_REGEX, re.DOTALL)
        m = TS_MATCHER.match(ts_string)

        zulu_ts = "%04d-%02d-%02dT%02d:%02d:%02dZ" % (
            int(m.group(3)), int(m.group(1)), int(m.group(2)),
            int(m.group(4)), int(m.group(5)), int(m.group(6))
        )
        log.trace("converted ts '%s' to '%s'", ts_string, zulu_ts)

        localtime_offset = float(parser.parse("1970-01-01T00:00:00.00Z").strftime("%s.%f"))
        converted_time = float(parser.parse(zulu_ts).strftime("%s.%f"))
        adjusted_time = round(converted_time - localtime_offset)
        ntptime = ntplib.system_to_ntp_time(adjusted_time)

        return ntptime

    def __eq__(self, arg):
        """
        Quick equality check for testing purposes. If they have the same raw
        data, they are the same enough for this particle
        """
        if (self.raw_data == arg.raw_data):
            return True
        else:
            log.error("raw_data mismatch %s != %s",
                self.raw_data,
                arg.raw_data)
            return False


class WfpParadkDataParticleKey(WfpParticleKey):
    PAR = 'photosynthetically_active_radiation'
    TIMESTAMP = 'timestamp'


class WfpParadkDataParticle(WfpParticle):
    _data_particle_type = DataParticleType.WFP_PARADK

    def _build_parsed_values(self):
        """
        Extracts Paradk data from the WFP data dictionary initialized with
        the particle class and puts the data into a Paradk Data Particle.

        @param result A returned list with sub dictionaries of the data
        """
        self._data_particle_type = DataParticleType.WFP_PARADK

        result = []
        for item in super(WfpParadkDataParticle, self)._build_parsed_values():

            if item[DataParticleKey.VALUE_ID] in WfpParadkDataParticleKey.list():
                log.trace("MATCH " + repr(item[DataParticleKey.VALUE_ID]))
                result.append(item)

        log.trace("WfpParadkDataParticle RETURNING " + repr(result))
        return result


class WfpEngineeringDataParticleKey(BaseEnum):
    CURRENT = 'current'
    VOLTAGE = 'voltage'
    #PRESURE = 'pressure_dbar'
    TIMESTAMP = 'timestamp'


class WfpEngineeringDataParticle(WfpParticle):
    _data_particle_type = DataParticleType.WFP_ENGINEERING

    def _build_parsed_values(self):
        """
        Extracts Engineering data from the WFP data dictionary initialized with
        the particle class and puts the data into a Engineering Data Particle.

        @param result A returned list with sub dictionaries of the data
        """

        result = []
        for item in super(WfpEngineeringDataParticle, self)._build_parsed_values():

            if item[DataParticleKey.VALUE_ID] in WfpEngineeringDataParticleKey.list():
                log.error("MATCH " + repr(item[DataParticleKey.VALUE_ID]))
                result.append(item)

        log.error("WfpEngineeringDataParticle RETURNING " + repr(result))
        return result


class WfpFlortkDataParticleKey(WfpParticleKey):
    CDOM = 'colored_dissolved_organic_matter_concentration'
    CHL = 'fluorometric_chlorophyll_a_concentration'
    SCAT_SIG = 'total_volume_scattering_coefficient'
    TIMESTAMP = 'timestamp'


class WfpFlortkDataParticle(WfpParticle):
    _data_particle_type = DataParticleType.WFP_FLORTK

    def _build_parsed_values(self):
        """
        Extracts Flortk data from the WFP data dictionary initialized with
        the particle class and puts the data into a Flortk Data Particle.

        @param result A returned list with sub dictionaries of the data
        """

        result = []
        for item in super(WfpFlortkDataParticle, self)._build_parsed_values():

            if item[DataParticleKey.VALUE_ID] in WfpFlortkDataParticleKey.list():
                log.error("MATCH " + repr(item[DataParticleKey.VALUE_ID]))
                result.append(item)

        log.error("WfpFlortkDataParticle RETURNING " + repr(result))
        return result


class WfpParser(BufferLoadingParser):

    def __init__(self,
                 config,
                 state,
                 stream_handle,
                 state_callback,
                 publish_callback,
                 *args, **kwargs):


        self._timestamp = 0.0
        self._record_buffer = [] # holds tuples of (record, state)
        self._read_state = {StateKey.POSITION:0}

        super(WfpParser, self).__init__(config,
                                          stream_handle,
                                          state,
                                          partial(StringChunker.regex_sieve_function,
                                                  regex_list=[DATA_MATCHER]),
                                          state_callback,
                                          publish_callback,
                                          *args,
                                          **kwargs)

        if state:
            self.set_state(self._state)

    def parse_chunks(self):
        """
        Parse out any pending data chunks in the chunker. If
        it is a valid data piece, build a particle, update the position and
        timestamp. Go until the chunker has no more valid data.
        @retval a list of tuples with sample particles encountered in this
            parsing, plus the state. An empty list of nothing was parsed.
        """

        result_particles = []

        (timestamp, chunk, start, end) = self._chunker.get_next_data_with_index()
        non_data = None

        # sieve looks for timestamp, update and increment position
        while (chunk != None):
            log.trace("got A chunk -> " + str(chunk))
            data_match = DATA_MATCHER.match(chunk)

            if data_match:
                log.trace("DATA MATCH!")
                # particle-ize the data block received, return the record
                sample = self._extract_sample(self._particle_class, DATA_MATCHER, chunk, self._timestamp)
                if sample:
                    log.trace("SAMPLE!!!")

                    # create particle
                    self._increment_state(end)

                    result_particles.append((sample, copy.copy(self._read_state)))
            else:
                log.error("Unhandled chunk: %s", chunk)
                #raise SampleException("Unhandled chunk: %s", chunk)

            (timestamp, chunk, start, end) = self._chunker.get_next_data_with_index()
            (nd_timestamp, non_data) = self._chunker.get_next_non_data(clean=True)

        return result_particles

    def set_state(self, state_obj):
        """
        Set the value of the state object for this parser
        @param state_obj The object to set the state to. Should be a list with
        a StateKey.POSITION value and StateKey.TIMESTAMP value. The position is
        number of bytes into the file, the timestamp is an NTP4 format timestamp.
        @throws DatasetParserException if there is a bad state structure
        """
        log.trace("Attempting to set state to: %s", state_obj)
        if not isinstance(state_obj, dict):
            raise DatasetParserException("Invalid state structure")
        if not (StateKey.POSITION in state_obj):
            raise DatasetParserException("Invalid state keys")

        self._chunker.buffer = ""
        self._chunker.raw_chunk_list = []
        self._chunker.data_chunk_list = []
        self._chunker.nondata_chunk_list = []
        self._record_buffer = []
        self._state = state_obj
        self._read_state = state_obj

        self._stream_handle.seek(state_obj[StateKey.POSITION])

    def _increment_state(self, increment):
        """
        Increment the parser position by a certain amount in bytes. This
        indicates what has been READ from the file, not what has been published.

        @param increment Number of bytes to increment the parser position.
        """
        log.trace("Incrementing current state: %s with inc: %s",
                  self._read_state, increment)

        self._read_state[StateKey.POSITION] += increment
        log.trace("to new value of = " + str(self._read_state))

#
# ParadkParserDataParticle
#
class ParadkParser(WfpParser):
    """
    """


#
# ParadkParserDataParticle
#
class FlortkParser(WfpParser):
    """
    """


#
# ParadkParserDataParticle
#
class EngineeringParser(WfpParser):
    """
    """


class Vel3dkParserDataParticleKey(WfpParticleKey):
    SOUND_VELOCITY = "sound_velocity"
    TEMPERATURE = "temperature"
    HEADING = "heading"
    PITCH = "pitch"
    ROLL = "roll"
    MAGNETIC_H_X = "magnHx" # Henrys
    MAGNETIC_H_Y = "magnHy" # Henrys
    MAGNETIC_H_Z = "magnHz" # Henrys
    BEAMS = "beams"
    CELLS = "cells"
    BEAM_1 = "beam1"
    BEAM_2 = "beam2"
    BEAM_3 = "beam3"
    BEAM_4 = "beam4"
    BEAM_5 = "beam5"
    VEL_0_0 = "vel[0,0]"
    VEL_1_0 = "vel[1,0]"
    VEL_2_0 = "vel[2,0]"
    AMP_0_0 = "amp[0,0]"
    AMP_1_0 = "amp[1,0]"
    AMP_2_0 = "amp[2,0]"
    CORR_0_0 = "corr[0,0]"
    CORR_1_0 = "corr[1,0]"
    CORR_2_0 = "corr[2,0]"


class Vel3dkParserDataParticle(WfpParticle):
    """
    """
    def _build_parsed_values(self):
        match = VEL_DATA_MATCHER.match(self.raw_data)   
        if not match:
            raise SampleException("WfpParserDataParticle: No regex match of parsed sample data: [%s]", self.raw_data)

        try:
            # Date,[mA],[V],[dbar],Par[mV],scatSig,chlSig,CDOMSig

            timestamp = self._convert_string_to_timestamp(match.group(1))
            sound_velocity = float(match.group(2))
            temperature = float(match.group(3))
            heading = float(match.group(4))
            pitch = float(match.group(5))
            roll = float(match.group(6))
            magnHx = float(match.group(7))
            magnHy = float(match.group(8))
            magnHz = float(match.group(9))
            beams = float(match.group(10))
            cells = float(match.group(11))
            beam1 = float(match.group(12))
            beam2 = float(match.group(13))
            beam3 = float(match.group(14))
            beam4 = float(match.group(15))
            beam5 = float(match.group(16))
            vel_0_0 = float(match.group(17))
            vel_1_0 = float(match.group(18))
            vel_2_0 = float(match.group(19))
            amp_0_0 = float(match.group(20))
            amp_1_0 = float(match.group(21))
            amp_2_0 = float(match.group(22))
            corr_0_0 = float(match.group(23))
            corr_1_0 = float(match.group(24))
            corr_2_0 = float(match.group(25))

        except (ValueError, TypeError, IndexError) as ex:
            raise SampleException("Error (%s) while decoding parameters in data: [%s]"
                                  % (ex, self.raw_data))

        result = [{DataParticleKey.VALUE_ID: WfpParticleKey.TIMESTAMP,
                   DataParticleKey.VALUE: timestamp},
                  {DataParticleKey.VALUE_ID: Vel3dkParserDataParticleKey.SOUND_VELOCITY,
                   DataParticleKey.VALUE: sound_velocity},
                  {DataParticleKey.VALUE_ID: Vel3dkParserDataParticleKey.TEMPERATURE,
                   DataParticleKey.VALUE: temperature},
                  {DataParticleKey.VALUE_ID: Vel3dkParserDataParticleKey.HEADING,
                   DataParticleKey.VALUE: heading},
                  {DataParticleKey.VALUE_ID: Vel3dkParserDataParticleKey.PITCH,
                   DataParticleKey.VALUE: pitch},
                  {DataParticleKey.VALUE_ID: Vel3dkParserDataParticleKey.ROLL,
                   DataParticleKey.VALUE: roll},
                  {DataParticleKey.VALUE_ID: Vel3dkParserDataParticleKey.MAGNETIC_H_X,
                   DataParticleKey.VALUE: magnHx},
                  {DataParticleKey.VALUE_ID: Vel3dkParserDataParticleKey.MAGNETIC_H_Y,
                   DataParticleKey.VALUE: magnHy},
                  {DataParticleKey.VALUE_ID: Vel3dkParserDataParticleKey.MAGNETIC_H_Z,
                   DataParticleKey.VALUE: magnHy},
                  {DataParticleKey.VALUE_ID: Vel3dkParserDataParticleKey.BEAMS,
                   DataParticleKey.VALUE: beams},
                  {DataParticleKey.VALUE_ID: Vel3dkParserDataParticleKey.CELLS,
                   DataParticleKey.VALUE: cells},
                  {DataParticleKey.VALUE_ID: Vel3dkParserDataParticleKey.BEAM_1,
                   DataParticleKey.VALUE: beam1},
                  {DataParticleKey.VALUE_ID: Vel3dkParserDataParticleKey.BEAM_2,
                   DataParticleKey.VALUE: beam2},
                  {DataParticleKey.VALUE_ID: Vel3dkParserDataParticleKey.BEAM_3,
                   DataParticleKey.VALUE: beam3},
                  {DataParticleKey.VALUE_ID: Vel3dkParserDataParticleKey.BEAM_4,
                   DataParticleKey.VALUE: beam4},
                  {DataParticleKey.VALUE_ID: Vel3dkParserDataParticleKey.BEAM_5,
                   DataParticleKey.VALUE: beam5},
                  {DataParticleKey.VALUE_ID: Vel3dkParserDataParticleKey.VEL_0_0,
                   DataParticleKey.VALUE: vel_0_0},
                  {DataParticleKey.VALUE_ID: Vel3dkParserDataParticleKey.VEL_1_0,
                   DataParticleKey.VALUE: vel_1_0},
                  {DataParticleKey.VALUE_ID: Vel3dkParserDataParticleKey.VEL_2_0,
                   DataParticleKey.VALUE: vel_2_0},
                  {DataParticleKey.VALUE_ID: Vel3dkParserDataParticleKey.AMP_0_0,
                   DataParticleKey.VALUE: amp_0_0},
                  {DataParticleKey.VALUE_ID: Vel3dkParserDataParticleKey.AMP_1_0,
                   DataParticleKey.VALUE: amp_1_0},
                  {DataParticleKey.VALUE_ID: Vel3dkParserDataParticleKey.AMP_2_0,
                   DataParticleKey.VALUE: amp_2_0},
                  {DataParticleKey.VALUE_ID: Vel3dkParserDataParticleKey.CORR_0_0,
                   DataParticleKey.VALUE: corr_0_0},
                  {DataParticleKey.VALUE_ID: Vel3dkParserDataParticleKey.CORR_1_0,
                   DataParticleKey.VALUE: corr_1_0},
                  {DataParticleKey.VALUE_ID: Vel3dkParserDataParticleKey.CORR_2_0,
                   DataParticleKey.VALUE: corr_2_0}]
        log.trace('Vel3dkParserDataParticle RETURNING %s', result)
        return result


class Vel3dkParser(BufferLoadingParser):
    """
    """



