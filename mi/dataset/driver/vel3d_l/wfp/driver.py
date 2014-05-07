"""
@package mi.dataset.driver.vel3d_l.wfp.driver
@file marine-integrations/mi/dataset/driver/vel3d_l/wfp/driver.py
@author Steve Myerson (Raytheon)
@brief Driver for the vel3d_l_wfp
This driver handles both telemetered and recovered data.
Release notes:

Initial Release
"""

__author__ = 'Steve Myerson (Raytheon)'
__license__ = 'Apache 2.0'


import string

from mi.core.common import BaseEnum
from mi.core.log import get_logger; log = get_logger()

from mi.dataset.dataset_driver import MultipleHarvesterDataSetDriver
from mi.dataset.driver.mflm.driver import MflmDataSetDriver
from mi.dataset.harvester import SingleDirectoryHarvester, SingleFileHarvester

#
# Telemetered data parser, Recovered data parser and associated particles
#
from mi.dataset.parser.vel3d_l_wfp import \
    Vel3dLWfpParser, \
    Vel3dLWfpSioMuleParser, \
    Vel3dLWfpInstrumentParticle, \
    Vel3dLWfpMetadataParticle


class DataTypeKey(BaseEnum):
    VEL3D_L_WFP = 'vel3d_l_wfp'
    VEL3D_L_WFP_SIO_MULE = 'vel3d_l_wfp_sio_mule'


class Vel3dLWfp(MultipleHarvesterDataSetDriver):

    def __init__(self, config, memento, data_callback, state_callback,
                 event_callback, exception_callback):

        data_keys = [DataTypeKey.VEL3D_L_WFP_SIO_MULE,
                     DataTypeKey.VEL3D_L_WFP]

        super(Vel3dLWfp, self).__init__(config, memento, data_callback,
                                        state_callback, event_callback,
                                        exception_callback, data_keys)
    
    @classmethod
    def stream_config(cls):
        return [Vel3dLWfpInstrumentParticle.type(),
                Vel3dLWfpMetadataParticle.type()]

    def _build_parser(self, parser_state, file_handle, filename=None, data_key=None):
        """
        Build and return the parsers
        """
        if data_key == DataTypeKey.VEL3D_L_WFP:
            log.info("XXXXXXXX  Build WFP parser")
            parser = self.build_vel3d_l_wfp_parser(parser_state, file_handle)
        elif data_key == DataTypeKey.VEL3D_L_WFP_SIO_MULE:
            log.info("ZZZZZZZZ Build MULE Parser")
            parser = self.build_vel3d_l_wfp_sio_mule_parser(parser_state, file_handle)
        else:
            parser = None
        return parser

    def build_vel3d_l_wfp_parser(self, parser_state, file_handle):
        """
        Build and return the vel3d_l_wfp parser
        """
        config = self._parser_config
        config.update({
            'particle_module': 'mi.dataset.parser.vel3d_l_wfp',
            'particle_class': ['Vel3dKWfpInstrumentParticle',
                               'Vel3dKWfpMetadataParticle']
        })

        log.debug("My Config: %s", config)
        parser = Vel3dLWfpParser(
            config,
            parser_state,
            file_handle,
            self._save_parser_state,
            self._data_callback,
            self._exception_callback
        )
        return parser

    def build_vel3d_l_wfp_sio_mule_parser(self, parser_state, file_handle):
        """
        Build and return the vel3d_l_wfp_sio_mule parser
        """
        config = self._parser_config
        config.update({
            'particle_module': 'mi.dataset.parser.vel3d_l_wfp_sio_mule',
            'particle_class': ['Vel3dKWfpInstrumentParticle',
                               'Vel3dKWfpMetadataParticle']
        })
        log.debug("My Config: %s", config)
        parser = Vel3dLWfpSioMuleParser(
            config,
            parser_state,
            file_handle,
            self._save_parser_state,
            self._data_callback,
            self._exception_callback
        )
        return parser

    def _build_harvester(self, driver_state):
        """
        Build and return the harvesters
        """

        vel3d_l_wfp_harvester = SingleDirectoryHarvester(
            self._harvester_config.get(DataTypeKey.VEL3D_L_WFP),
            driver_state,
            self._new_vel3d_l_wfp_file_callback,
            self._modified_file_callback,
            self._exception_callback
        )

        log.info("XXXXXXXX  Build Harvester")

        vel3d_l_wfp_sio_mule_harvester = SingleDirectoryHarvester(
            self._harvester_config.get(DataTypeKey.VEL3D_L_WFP_SIO_MULE),
            driver_state,
            self._new_vel3d_l_wfp_sio_mule_file_callback,
            self._modified_file_callback,
            self._exception_callback
        )

        self._harvester = [vel3d_l_wfp_harvester,
                           vel3d_l_wfp_sio_mule_harvester]

        return self._harvester

    def _new_vel3d_l_wfp_file_callback(self, file_name):
        """
        Callback used by the vel3d_l_wfp single directory harvester
        called when a new file is detected.  Store the filename in a queue.
        @param file_name: file name of the found file.
        """
        self._new_file_callback(file_name, DataTypeKey.VEL3D_L_WFP)

    def _new_vel3d_l_wfp_sio_mule_file_callback(self, file_name):
        """
        Callback used by the vel3d_l_wfp single directory harvester
        called when a new file is detected.  Store the filename in a queue.
        @param file_name: file name of the found file.
        """
        self._new_file_callback(file_name, DataTypeKey.VEL3D_L_WFP_SIO_MULE)
