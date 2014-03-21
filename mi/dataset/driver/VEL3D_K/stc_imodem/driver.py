"""
@package mi.dataset.driver.VEL3D_K.stc_imodem.driver
@file marine-integrations/mi/dataset/driver/VEL3D_K/stc_imodem/driver.py
@author Steve Myerson (Raytheon)
@brief Driver for the VEL3D_K__stc_imodem
Release notes:

Initial Release
"""

__author__ = 'Steve Myerson (Raytheon)'
__license__ = 'Apache 2.0'

import string

from mi.core.log import get_logger ; log = get_logger()

from mi.dataset.dataset_driver import SimpleDataSetDriver

from mi.dataset.parser.vel3d_k__stc_imodem import Vel3d_k__stc_imodemParser
from mi.dataset.parser.vel3d_k__stc_imodem import Vel3d_k__stc_imodemTimeDataParticle
from mi.dataset.parser.vel3d_k__stc_imodem import Vel3d_k__stc_imodemVelocityDataParticle

from mi.dataset.harvester import SingleDirectoryHarvester

class VEL3D_K__stc_imodem_DataSetDriver(SimpleDataSetDriver):

    @classmethod
    def stream_config(cls):
        return [Vel3d_k__stc_imodemTimeDataParticle.type(),
                Vel3d_k__stc_imodemVelocityDataParticle.type()]

    def _build_parser(self, parser_state, infile):
        """
        Build and return the parser
        """
        config = self._parser_config
        config.update({
            'particle_module': 'mi.dataset.parser.vel3d_k__stc_imodem',
            'particle_class': ['Vel3d_k__stc_imodemTimeDataParticle',
                               'Vel3d_k__stc_imodemVelocityDataParticle']
        })
        log.debug("My Config: %s", config)
        self._parser = Vel3d_k__stc_imodemParser(
            config,
            infile,
            parser_state,
            self._save_parser_state,    # state_callback
            self._data_callback         # publish_callback
        )
        return self._parser

    def _build_harvester(self, driver_state):
        """
        Build and return the harvester
        """
        self._harvester = SingleDirectoryHarvester(
            self._harvester_config,
            driver_state,
            self._new_file_callback,
            self._modified_file_callback,
            self._exception_callback
        )        
        return self._harvester
