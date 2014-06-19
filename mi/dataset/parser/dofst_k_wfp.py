#!/usr/bin/env python

"""
@package mi.dataset.parser.dofst_k_wfp
@file marine-integrations/mi/dataset/parser/dofst_k_wfp.py
@author Emily Hahn
@brief Parser for the dofst_k_wfp dataset driver
Release notes:

initial release
"""

__author__ = 'Emily Hahn'
__license__ = 'Apache 2.0'


from mi.core.log import get_logger
log = get_logger()


from mi.dataset.parser.wfp_c_file_common import WfpCFileCommonParser
from mi.dataset.dataset_driver import DataSetDriverConfigKeys


class DofstKWfpParser(WfpCFileCommonParser):
    """
    Make use of the common wfp C file type parser
    """
    def __init__(self,
                 config,
                 state,
                 stream_handle,
                 state_callback,
                 publish_callback,
                 exception_callback,
                 filesize,
                 *args, **kwargs):

        particle_classes_dict = config.get(DataSetDriverConfigKeys.PARTICLE_CLASSES_DICT)
        self._instrument_data_particle_class = particle_classes_dict.get('instrument_data_particle_class')
        self._metadata_particle_class = particle_classes_dict.get('metadata_particle_class')

        super(DofstKWfpParser, self).__init__(config,
                                              state,
                                              stream_handle,
                                              state_callback,
                                              publish_callback,
                                              exception_callback,
                                              filesize,
                                              *args, **kwargs)

    def extract_metadata_particle(self, raw_data, timestamp):
        """
        Class for extracting the metadata data particle
        @param raw_data raw data to parse, in this case a tuple of the time string to parse and the number of records
        @param timestamp timestamp in NTP64
        """
        sample = self._extract_sample(self._metadata_particle_class, None, raw_data, timestamp)
        return sample

    def extract_data_particle(self, raw_data, timestamp):
        """
        Class for extracting the data sample data particle
        @param raw_data the raw data to parse
        @param timestamp the timestamp in NTP64
        """
        sample = self._extract_sample(self._instrument_data_particle_class, None, raw_data, timestamp)
        return sample