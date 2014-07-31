#!/usr/bin/env python

"""
@package mi.dataset.parser.cspp_eng_cspp
@file marine-integrations/mi/dataset/parser/cspp_eng_cspp.py
@author Jeff Roy
@brief Parser for the cspp_eng_cspp dataset driver
Release notes: This is one of 4 parsers that make up that driver

initial release
"""

__author__ = 'Jeff Roy'
__license__ = 'Apache 2.0'

import copy
import re
import ntplib

from mi.core.log import get_logger
log = get_logger()

from mi.core.common import BaseEnum
from mi.core.instrument.data_particle import DataParticle, DataParticleKey
from mi.core.exceptions import SampleException, DatasetParserException, UnexpectedDataException

from mi.dataset.parser.cspp_base import \
    CsppParser, \
    FLOAT_REGEX, \
    INT_REGEX, \
    Y_OR_N_REGEX, \
    MULTIPLE_TAB_REGEX, \
    END_OF_LINE_REGEX, \
    CsppMetadataDataParticle, \
    MetadataRawDataKey, \
    PARTICLE_KEY_INDEX, \
    DATA_MATCHES_GROUP_NUMBER_INDEX, \
    TYPE_ENCODING_INDEX, \
    encode_y_or_n

# *** Need to define data regex for this parser ***
DATA_REGEX = ''
DATA_MATCHER = re.compile(DATA_REGEX)

class DataParticleType(BaseEnum):
    SAMPLE = 'cspp_eng_cspp_parsed'

class CsppEngCsppParserDataParticleKey(BaseEnum):

class StateKey(BaseEnum):
    POSITION='position' # holds the file position

class CsppEngCsppParserDataParticle(DataParticle):
    """
    Class for parsing data from the cspp_eng_cspp data set
    """

    _data_particle_type = DataParticleType.SAMPLE
    
    def _build_parsed_values(self):
        """
        Take something in the data format and turn it into
        an array of dictionaries defining the data in the particle
        with the appropriate tag.
        @throws SampleException If there is a problem with sample creation
        """
        pass

class CsppEngCsppParser(CsppParser):

    def __init__(self,
                 config,
                 state,
                 stream_handle,
                 state_callback,
                 publish_callback,
                 exception_callback,
                 *args, **kwargs):
        """
        This method is a constructor that will instantiate an CsppEngCsppParser object.
        @param config The configuration for this CsppEngCsppParser parser
        @param state The state the CsppEngCsppParser should use to initialize itself
        @param stream_handle The handle to the data stream containing the cspp_eng_cspp data
        @param state_callback The function to call upon detecting state changes
        @param publish_callback The function to call to provide particles
        @param exception_callback The function to call to report exceptions
        """

        # Call the superclass constructor
        super(SpkirAbjCsppParser, self).__init__(config,
                                                 state,
                                                 stream_handle,
                                                 state_callback,
                                                 publish_callback,
                                                 exception_callback,
                                                 DATA_REGEX,
                                                 ignore_matcher=IGNORE_MATCHER,
                                                 *args, **kwargs)
