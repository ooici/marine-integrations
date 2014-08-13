"""
@package mi.dataset.driver.mflm.dosta.driver
@file marine-integrations/mi/dataset/driver/mflm/dosta/driver.py
@author Emily Hahn
@brief Driver for the mflm_dosta
Release notes:

initial release
"""

__author__ = 'Emily Hahn'
__license__ = 'Apache 2.0'

import string

from mi.core.common import BaseEnum
from mi.core.exceptions import ConfigurationException
from mi.core.log import get_logger ; log = get_logger()
from mi.dataset.harvester import SingleFileHarvester, SingleDirectoryHarvester
from mi.dataset.dataset_driver import HarvesterType, DataSetDriverConfigKeys
from mi.dataset.driver.sio_mule.sio_mule_driver import SioMuleDataSetDriver
from mi.dataset.parser.dostad import DostadParser, DostadParserRecovered
from mi.dataset.parser.dostad import StateKey
from mi.dataset.parser.dostad import DostadParserRecoveredDataParticle
from mi.dataset.parser.dostad import DostadParserTelemeteredDataParticle
from mi.dataset.parser.dostad import DostadParserRecoveredMetadataDataParticle
from mi.dataset.parser.dostad import DostadParserTelemeteredMetadataDataParticle

class DataTypeKey(BaseEnum):
    """
    These are the possible harvester/parser pairs for this driver
    """
    DOSTA_ABCDJM_SIO_TELEMETERED = 'dosta_abcdjm_sio_mule_telemetered'
    DOSTA_ABCDJM_SIO_RECOVERED = 'dosta_abcdjm_sio_mule_recovered'


class MflmDOSTADDataSetDriver(SioMuleDataSetDriver):
    
    @classmethod
    def stream_config(cls):
        # Fill in below with particle stream
        return [DostadParserRecoveredDataParticle.type(),
                DostadParserTelemeteredDataParticle.type(),
                DostadParserRecoveredMetadataDataParticle.type(),
                DostadParserTelemeteredMetadataDataParticle.type()]


    def __init__(self, config, memento, data_callback, state_callback, event_callback, exception_callback):
        # initialize the possible types of harvester/parser pairs for this driver
        data_keys = [DataTypeKey.DOSTA_ABCDJM_SIO_TELEMETERED,
                     DataTypeKey.DOSTA_ABCDJM_SIO_RECOVERED]
        
        # link the data keys to the harvester type, multiple or single file harvester
        harvester_type = {
            DataTypeKey.DOSTA_ABCDJM_SIO_TELEMETERED: HarvesterType.SINGLE_FILE,
            DataTypeKey.DOSTA_ABCDJM_SIO_RECOVERED: HarvesterType.SINGLE_DIRECTORY
        }
        
        super(MflmDOSTADDataSetDriver, self).__init__(config, memento, data_callback, state_callback, event_callback,
                                                     exception_callback, data_keys, harvester_type=harvester_type)


    def _build_parser(self, parser_state, stream_in, data_key=None):
        """
        Build and return the parser
        """

        config = self._parser_config.get(data_key)

        #
        # If the key is DOSTA_ABCDJM_SIO_RECOVERED, build the WFP parser.
        #
        if data_key == DataTypeKey.DOSTA_ABCDJM_SIO_RECOVERED:
            config.update({
                DataSetDriverConfigKeys.PARTICLE_MODULE: 'mi.dataset.parser.dostad',
                DataSetDriverConfigKeys.PARTICLE_CLASS: None,
                DataSetDriverConfigKeys.PARTICLE_CLASSES_DICT: {
                    METADATA_PARTICLE_CLASS_KEY: DostadParserRecoveredMetadataDataParticle,
                    DATA_PARTICLE_CLASS_KEY: DostadParserRecoveredDataParticle
                }
            })

            parser = DostadParserRecovered(
                config,
                parser_state,
                infile,
                lambda state, ingested: self._save_parser_state(state, data_key, ingested),
                self._data_callback,
                self._sample_exception_callback)
    
            return parser

        #
        # If the key is DOSTA_ABCDJM_SIO_TELEMETERED, build the WFP SIO Mule parser.
        #
        elif data_key == DataTypeKey.DOSTA_ABCDJM_SIO_TELEMETERED:
            config.update({
                DataSetDriverConfigKeys.PARTICLE_MODULE: 'mi.dataset.parser.dostad',
                DataSetDriverConfigKeys.PARTICLE_CLASS: None,
                DataSetDriverConfigKeys.PARTICLE_CLASSES_DICT: {
                    METADATA_PARTICLE_CLASS_KEY: DostadParserTelemeteredMetadataDataParticle,
                    DATA_PARTICLE_CLASS_KEY: DostadParserTelemeteredDataParticle
                }
            })
            
            parser = DostadParser(
                config,
                parser_state,
                infile,
                lambda state, ingested: self._save_parser_state(state, data_key, ingested),
                self._data_callback,
                self._sample_exception_callback)
    
            return parser

        #
        # If the key is one that we're not expecting, don't build any parser.
        #
        else:
            raise ConfigurationException("Invalid data_key supplied to build parser")



    def _build_harvester(self, driver_state):
        """
        Build the harvester
        @param driver_state The starting driver state
        """
        self._harvester = []
        if DataTypeKey.DOSTA_ABCDJM_SIO_TELEMETERED in self._harvester_config:
            telemetered_harvester = SingleFileHarvester(
                self._harvester_config.get(DataTypeKey.DOSTA_ABCDJM_SIO_TELEMETERED),
                driver_state[DataTypeKey.DOSTA_ABCDJM_SIO_TELEMETERED],
                lambda file_state: self._file_changed_callback(file_state, DataTypeKey.DOSTA_ABCDJM_SIO_TELEMETERED),
                self._exception_callback
            )
            self._harvester.append(telemetered_harvester)
        else:
            log.warn('No configuration for telemetered harvester, not building')

        if DataTypeKey.DOSTA_ABCDJM_SIO_RECOVERED in self._harvester_config:
            recovered_harvester = SingleDirectoryHarvester(
                self._harvester_config.get(DataTypeKey.DOSTA_ABCDJM_SIO_RECOVERED),
                driver_state[DataTypeKey.DOSTA_ABCDJM_SIO_RECOVERED],
                lambda filename: self._new_file_callback(filename, DataTypeKey.DOSTA_ABCDJM_SIO_RECOVERED),
                lambda modified: self._modified_file_callback(modified, DataTypeKey.DOSTA_ABCDJM_SIO_RECOVERED),
                self._exception_callback
            )
            self._harvester.append(recovered_harvester)
        else:
            log.warn('No configuration for recovered harvester, not building')
        return self._harvester

