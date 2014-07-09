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

from mi.core.common import BaseEnum
from mi.core.log import get_logger; log = get_logger()

from mi.core.exceptions import \
    ConfigurationException

from mi.dataset.dataset_driver import \
    DataSetDriverConfigKeys, \
    HarvesterType

from mi.dataset.driver.sio_mule.sio_mule_driver import \
    SioMuleDataSetDriver

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
    Vel3dLWfpInstrumentRecoveredParticle, \
    Vel3dLWfpMetadataRecoveredParticle, \
    Vel3dLWfpSioMuleMetadataParticle


class DataTypeKey(BaseEnum):
    VEL3D_L_WFP = 'vel3d_l_wfp'
    VEL3D_L_WFP_SIO_MULE = 'vel3d_l_wfp_sio_mule'


class Vel3dLWfp(SioMuleDataSetDriver):

    def __init__(self, config, memento, data_callback, state_callback,
                 event_callback, exception_callback):

        data_keys = DataTypeKey.list()

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
                Vel3dLWfpInstrumentRecoveredParticle.type(),
                Vel3dLWfpMetadataRecoveredParticle.type(),
                Vel3dLWfpSioMuleMetadataParticle.type()]

    def _build_parser(self, parser_state, file_handle, data_key=None):
        """
        Build and return the specified parser as indicated by the data_key.
        """
        #
        # If the key is VEL3D_L_WFP, build the WFP parser.
        #
        if data_key == DataTypeKey.VEL3D_L_WFP:
            config = self._parser_config[data_key]
            config.update({
                DataSetDriverConfigKeys.PARTICLE_MODULE:
                    'mi.dataset.parser.vel3d_l_wfp',
                DataSetDriverConfigKeys.PARTICLE_CLASS:
                    ['Vel3dKWfpInstrumentRecoveredParticle',
                     'Vel3dKWfpMetadataRecoveredParticle']
            })

            parser = Vel3dLWfpParser(config, parser_state, file_handle,
                lambda state, ingested:
                    self._save_parser_state(state, data_key, ingested),
                self._data_callback,
                self._sample_exception_callback)

            if parser is None:
                raise ConfigurationException('Unable to build Vel3d_L_Wfp Parser')

        #
        # If the key is VEL3D_L_WFP_SIO_MULE, build the WFP SIO Mule parser.
        #
        elif data_key == DataTypeKey.VEL3D_L_WFP_SIO_MULE:
            config = self._parser_config[data_key]
            config.update({
                DataSetDriverConfigKeys.PARTICLE_MODULE:
                    'mi.dataset.parser.vel3d_l_wfp',
                DataSetDriverConfigKeys.PARTICLE_CLASS:
                    ['Vel3dKWfpInstrumentParticle',
                     'Vel3dLWfpSioMuleMetadataParticle']
            })

            parser = Vel3dLWfpSioMuleParser(config, parser_state, file_handle,
                lambda state:
                    self._save_parser_state(state, data_key),
                self._data_callback,
                self._sample_exception_callback)

            if parser is None:
                raise ConfigurationException('Unable to build Vel3d_L_Wfp_Sio_Mule Parser')

        #
        # If the key is one that we're not expecting, don't build any parser.
        #
        else:
            raise ConfigurationException('Vel3d_L Parser configuration key incorrect %s',
                                         data_key)

        return parser

    def _build_harvester(self, driver_state):
        """
        Build and return the harvesters
        """

        harvesters = []    # list of harvesters to be returned

        #
        # Verify that the WFP harvester has been configured.
        # If so, build the harvester and add it to the list of harvesters.
        #
        if DataTypeKey.VEL3D_L_WFP in self._harvester_config:
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

        else:
            log.warn('Missing harvester configuration for key %s',
                     DataTypeKey.VEL3D_L_WFP)

        #
        # Verify that the SIO Mule harvester has been configured.
        # If so, build the harvester and add it to the list of harvesters.
        #
        if DataTypeKey.VEL3D_L_WFP_SIO_MULE in self._harvester_config:
            sio_harvester = SingleFileHarvester(
                self._harvester_config.get(DataTypeKey.VEL3D_L_WFP_SIO_MULE),
                driver_state[DataTypeKey.VEL3D_L_WFP_SIO_MULE],
                lambda file_state:
                    self._file_changed_callback(file_state, DataTypeKey.VEL3D_L_WFP_SIO_MULE),
                self._exception_callback)

            if sio_harvester is not None:
                harvesters.append(sio_harvester)

        else:
            log.warn('Missing harvester configuration for key %s',
                     DataTypeKey.VEL3D_L_WFP)

        return harvesters
