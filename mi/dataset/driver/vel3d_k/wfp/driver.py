"""
@package mi.dataset.driver.vel3d_k.wfp.driver
@file marine-integrations/mi/dataset/driver/vel3d_k/wfp/driver.py
@author Steve Myerson (Raytheon)
@brief Driver for the vel3d_k_wfp
This driver handles both telemetered and recovered data.
Release notes:

Initial Release
"""

__author__ = 'Steve Myerson (Raytheon)'
__license__ = 'Apache 2.0'

from mi.core.common import BaseEnum
from mi.core.log import get_logger; log = get_logger()

from mi.dataset.dataset_driver import MultipleHarvesterDataSetDriver
from mi.dataset.harvester import SingleDirectoryHarvester

#
# Recovered data parser and associated particles
#
from mi.dataset.parser.vel3d_k_wfp import \
    Vel3dKWfpParser, \
    Vel3dKWfpInstrumentParticle, \
    Vel3dKWfpMetadataParticle, \
    Vel3dKWfpStringParticle

#
# Telemetered data parser and associated particles
#
from mi.dataset.parser.vel3d_k_wfp_stc import \
    Vel3dKWfpStcParser, \
    Vel3dKWfpStcInstrumentParticle, \
    Vel3dKWfpStcMetadataParticle


class DataTypeKey(BaseEnum):
    VEL3D_K_WFP = 'vel3d_k_wfp'
    VEL3D_K_WFP_STC = 'vel3d_k_wfp_stc'


class Vel3dKWfp(MultipleHarvesterDataSetDriver):

    def __init__(self, config, memento, data_callback, state_callback,
                 event_callback, exception_callback):
        data_keys = [DataTypeKey.VEL3D_K_WFP, DataTypeKey.VEL3D_K_WFP_STC]
        super(Vel3dKWfp, self).__init__(config, memento, data_callback,
                                        state_callback, event_callback,
                                        exception_callback, data_keys)

    @classmethod
    def stream_config(cls):
        return [Vel3dKWfpInstrumentParticle.type(),
                Vel3dKWfpMetadataParticle.type(),
                Vel3dKWfpStringParticle.type(),
                Vel3dKWfpStcMetadataParticle.type(),
                Vel3dKWfpStcInstrumentParticle.type()]

    def _build_parser(self, parser_state, file_handle, data_key=None):
        """
        Build and return the specified parser as indicated by the data_key.
        """
        if data_key == DataTypeKey.VEL3D_K_WFP:
            parser = self.build_vel3d_k_wfp_parser(parser_state, file_handle)
        elif data_key == DataTypeKey.VEL3D_K_WFP_STC:
            parser = self.build_vel3d_k_wfp_stc_parser(parser_state, file_handle)
        else:
            parser = None
        return parser

    def build_vel3d_k_wfp_parser(self, parser_state, file_handle):
        """
        Build and return the vel3d_k_wfp parser.
        """
        config = self._parser_config
        config.update({
            'particle_module': 'mi.dataset.parser.vel3d_k_wfp',
            'particle_class': ['Vel3dKWfpInstrumentParticle',
                               'Vel3dKWfpMetadataParticle',
                               'Vel3dKWfpStringParticle']
        })

        parser = Vel3dKWfpParser(config, parser_state, file_handle,
            lambda state, ingested:
                self._save_parser_state(state, DataTypeKey.VEL3D_K_WFP, ingested),
            self._data_callback, self._sample_exception_callback)

        return parser

    def build_vel3d_k_wfp_stc_parser(self, parser_state, file_handle):
        """
        Build and return the vel3d_k_wfp_stc parser.
        """
        config = self._parser_config
        config.update({
            'particle_module': 'mi.dataset.parser.vel3d_k_wfp_stc',
            'particle_class': ['Vel3dKWfpStcMetadataParticle',
                               'Vel3dKWfpStcInstrumentDataParticle']
        })

        parser = Vel3dKWfpStcParser(config, parser_state, file_handle,
            lambda state, ingested:
                self._save_parser_state(state, DataTypeKey.VEL3D_K_WFP_STC, ingested),
            self._data_callback, self._sample_exception_callback)

        return parser

    def _build_harvester(self, driver_state):
        """
        Build and return the harvesters
        """

        harvesters = []

        wfp_harvester = self.build_single_harvester(driver_state,
                                                    DataTypeKey.VEL3D_K_WFP)
        if wfp_harvester is not None:
            harvesters.append(wfp_harvester)

        stc_harvester = self.build_single_harvester(driver_state,
                                                    DataTypeKey.VEL3D_K_WFP_STC)
        if stc_harvester is not None:
            harvesters.append(stc_harvester)

        return harvesters

    def build_single_harvester(self, driver_state, key):

        if key in self._harvester_config:
            harvester = SingleDirectoryHarvester(
                self._harvester_config.get(key),
                driver_state[key],
                lambda filename: self._new_file_callback(filename, key),
                lambda modified: self._modified_file_callback(modified, key),
                self._exception_callback)
        else:
            harvester = None

        return harvester
