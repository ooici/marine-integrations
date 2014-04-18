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
    Vel3dKWfpStcTimeDataParticle, \
    Vel3dKWfpStcVelocityDataParticle


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
                Vel3dKWfpStcTimeDataParticle.type(),
                Vel3dKWfpStcVelocityDataParticle.type()]

    def _build_parser(self, parser_state, file_handle, file_name=None, data_key=None):
        """
        Build and return the parser
        """
        if data_key == DataTypeKey.VEL3D_K_WFP:
            parser = self.build_vel3d_k_wfp_parser(parser_state, file_handle,
                                                   file_name)
        elif data_key == DataTypeKey.VEL3D_K_WFP_STC:
            parser = self.build_vel3d_k_wfp_stc_parser(parser_state, file_handle,
                                                       file_name)
        else:
            parser = None
        return parser

    def build_vel3d_k_wfp_parser(self, parser_state, file_handle, file_name):
        """
        Build and return the vel3d_k_wfp parser
        """
        config = self._parser_config
        config.update({
            'particle_module': 'mi.dataset.parser.vel3d_k_wfp',
            'particle_class': ['Vel3dKWfpInstrumentParticle',
                               'Vel3dKWfpMetadataParticle',
                               'Vel3dKWfpStringParticle']
        })
        log.debug("My Config: %s", config)
        parser = Vel3dKWfpParser(
            config,
            parser_state,
            file_handle,
            file_name,
            self._save_parser_state,
            self._data_callback,
            self._sample_exception_callback 
        )
        return parser

    def build_vel3d_k_wfp_stc_parser(self, parser_state, file_handle, file_name):
        """
        Build and return the vel3d_k_wfp_stc parser
        """
        config = self._parser_config
        config.update({
            'particle_module': 'mi.dataset.parser.vel3d_k_wfp_stc',
            'particle_class': ['Vel3dKWfpStcTimeDataParticle',
                               'Vel3dKWfpStcVelocityDataParticle']
        })
        log.debug("My Config: %s", config)
        parser = Vel3dKWfpStcParser(
            config,
            parser_state,
            file_handle,
            file_name,
            self._save_parser_state,
            self._data_callback,
            self._sample_exception_callback
        )
        return parser

    def _build_harvester(self, driver_state):
        """
        Build and return the harvesters
        """
        vel3d_k_wfp_harvester = SingleDirectoryHarvester(
            self._harvester_config.get(DataTypeKey.VEL3D_K_WFP),
            driver_state,
            self._new_vel3d_k_wfp_file_callback,
            self._modified_file_callback,
            self._exception_callback
        )

        vel3d_k_wfp_stc_harvester = SingleDirectoryHarvester(
            self._harvester_config.get(DataTypeKey.VEL3D_K_WFP_STC),
            driver_state,
            self._new_vel3d_k_wfp_stc_file_callback,
            self._modified_file_callback,
            self._exception_callback
        )

        self._harvester = [vel3d_k_wfp_harvester,
                           vel3d_k_wfp_stc_harvester]

        return self._harvester

    def _new_vel3d_k_wfp_file_callback(self, file_name):
        """
        Callback used by the vel3d_k_wfp single directory harvester
        called when a new file is detected.  Store the filename in a queue.
        @param file_name: file name of the found file.
        """
        self._new_file_callback(file_name, DataTypeKey.VEL3D_K_WFP)

    def _new_vel3d_k_wfp_stc_file_callback(self, file_name):
        """
        Callback used by the vel3d_k_wfp single directory harvester
        called when a new file is detected.  Store the filename in a queue.
        @param file_name: file name of the found file.
        """
        self._new_file_callback(file_name, DataTypeKey.VEL3D_K_WFP_STC)
