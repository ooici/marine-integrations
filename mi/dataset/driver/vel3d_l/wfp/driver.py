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


#import string

from mi.core.common import BaseEnum
from mi.core.log import get_logger; log = get_logger()

from mi.dataset.dataset_driver import \
    HarvesterType, \
    MultipleHarvesterDataSetDriver

from mi.dataset.harvester import \
    SingleDirectoryHarvester, \
    SingleFileHarvester

#
# Vel3dLWfpParser - Recovered data parser (single directory)
# Vel3dLWfpSioMuleParser - Telemetered data parser (single file)
# Associated data particles
#
from mi.dataset.parser.vel3d_l_wfp import \
    Vel3dLWfpParser, \
    Vel3dLWfpSioMuleParser, \
    Vel3dLWfpInstrumentParticle, \
    Vel3dLWfpMetadataParticle, \
    Vel3dLWfpSioMuleMetadataParticle


class DataTypeKey(BaseEnum):
    VEL3D_L_WFP = 'vel3d_l_wfp'
    VEL3D_L_WFP_SIO_MULE = 'vel3d_l_wfp_sio_mule'


class Vel3dLWfp(MultipleHarvesterDataSetDriver):

    def __init__(self, config, memento, data_callback, state_callback,
                 event_callback, exception_callback):

        data_keys = [DataTypeKey.VEL3D_L_WFP, DataTypeKey.VEL3D_L_WFP_SIO_MULE]

        harvester_type = {
            DataTypeKey.VEL3D_L_WFP: HarvesterType.SINGLE_DIRECTORY,
            DataTypeKey.VEL3D_L_WFP_SIO_MULE: HarvesterType.SINGLE_FILE
        }

        super(Vel3dLWfp, self).__init__(config, memento, data_callback,
                                        state_callback, event_callback,
                                        exception_callback,
                                        data_keys, harvester_type)
    
    @classmethod
    def stream_config(cls):
        return [Vel3dLWfpInstrumentParticle.type(),
                Vel3dLWfpMetadataParticle.type(),
                Vel3dLWfpSioMuleMetadataParticle.type()]

    def _build_parser(self, parser_state, file_handle, data_key=None):
        """
        Build and return the specified parser as indicated by the data_key.
        """
        #
        # If the key is VEL3D_L_WFP, build the WFP parser.
        #
        if data_key == DataTypeKey.VEL3D_L_WFP:
            config = self._parser_config
            config.update({
                'particle_module': 'mi.dataset.parser.vel3d_l_wfp',
                'particle_class': ['Vel3dKWfpInstrumentParticle',
                                   'Vel3dKWfpMetadataParticle']
            })

            log.info('BUILDING PARSER Vel3dLWfpParser')
            parser = Vel3dLWfpParser(config, parser_state, file_handle,
                lambda state, ingested:
                    self._save_parser_state(state, data_key, ingested),
                self._data_callback,
                self._sample_exception_callback)

        #
        # If the key is VEL3D_L_WFP_SIO_MULE, build the WFP SIO Mule parser.
        #
        elif data_key == DataTypeKey.VEL3D_L_WFP_SIO_MULE:
            config = self._parser_config
            config.update({
                'particle_module': 'mi.dataset.parser.vel3d_l_wfp',
                'particle_class': ['Vel3dKWfpInstrumentParticle',
                                   'Vel3dLWfpSioMuleMetadataParticle']
            })

            log.info('BUILDING PARSER Vel3dLWfpSioMuleParser')
            parser = Vel3dLWfpSioMuleParser(config, parser_state, file_handle,
                lambda state:
                    self._save_parser_state(state, data_key),
                self._data_callback,
                self._sample_exception_callback)

        #
        # If the key is one that we're not expecting, don't build any parser.
        #
        else:
            parser = None

        return parser

    def _build_harvester(self, driver_state):
        """
        Build and return the harvesters
        """

        harvesters = []    # list of harvesters to be returned

        log.info('BUILD HARVESTER %s', self._harvester_config)

        #
        # Verify that the WFP harvester has been configured.
        # If so, build the harvester and add it to the list of harvesters.
        #
        if DataTypeKey.VEL3D_L_WFP in self._harvester_config:
            log.info('BUILDING WFP HARVESTER')
            wfp_harvester = SingleDirectoryHarvester(
                self._harvester_config.get(DataTypeKey.VEL3D_L_WFP),
                driver_state[DataTypeKey.VEL3D_L_WFP],
                lambda filename:
                    self._new_file_callback(filename, DataTypeKey.VEL3D_L_WFP),
                lambda modified:
                    self._modified_file_callback(modified, DataTypeKey.VEL3D_L_WFP),
                self._exception_callback)

            if wfp_harvester is not None:
                harvesters.append(wfp_harvester)
                log.info('WFP HARVESTER BUILT')

        #
        # Verify that the SIO Mule harvester has been configured.
        # If so, build the harvester and add it to the list of harvesters.
        #
        if DataTypeKey.VEL3D_L_WFP_SIO_MULE in self._harvester_config:
            log.info('BUILDING SIO HARVESTER')
            sio_harvester = SingleFileHarvester(
                self._harvester_config.get(DataTypeKey.VEL3D_L_WFP_SIO_MULE),
                driver_state[DataTypeKey.VEL3D_L_WFP_SIO_MULE],
                lambda file_state:
                    self._file_changed_callback(file_state, DataTypeKey.VEL3D_L_WFP_SIO_MULE),
                self._exception_callback)

            if sio_harvester is not None:
                harvesters.append(sio_harvester)
                log.info('SIO HARVESTER BUILT')
            else:
                log.info('SIO HARVESTER NOT BUILT')

        return harvesters
