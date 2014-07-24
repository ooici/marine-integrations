"""
@package mi.dataset.driver.sio_eng.sio_mule.driver
@file marine-integrations/mi/dataset/driver/sio_eng/sio_mule/driver.py
@author Mike Nicoletti
@brief Driver for the sio_eng_sio_mule
Release notes:

Starting SIO Engineering Driver
"""

__author__ = 'Mike Nicoletti'
__license__ = 'Apache 2.0'

import string

from mi.core.log import get_logger ; log = get_logger()


from mi.dataset.parser.sio_eng_sio_mule import SioEngSioMuleParser, SioEngSioMuleParserDataParticle
from mi.core.common import BaseEnum
from mi.core.exceptions import ConfigurationException
from mi.core.log import get_logger ; log = get_logger()
from mi.dataset.harvester import SingleFileHarvester
from mi.dataset.dataset_driver import HarvesterType, DataSetDriverConfigKeys
from mi.dataset.driver.sio_mule.sio_mule_driver import SioMuleDataSetDriver
from mi.dataset.parser.sio_eng_sio_mule import SioEngSioMuleParser, SioEngSioMuleParserDataParticle
from mi.dataset.parser.sio_mule_common import StateKey

class DataSourceKey(BaseEnum):
    """
    These are the possible harvester/parser pairs for this driver
    """
    SIO_ENG_SIO_MULE_TELEMETERED = 'sio_eng_control_status'
    SIO_ENG_SIO_MULE_RECOVERED = 'sio_eng_control_status_recovered'

class SioEngSioMuleDataSetDriver(SioMuleDataSetDriver):
    
    
    @classmethod
    def stream_config(cls):
        return [SioEngSioMuleParserDataParticle.type()]
    
    def __init__(self, config, memento, data_callback, state_callback, event_callback, exception_callback):
        # initialize the possible types of harvester/parser pairs for this driver
        data_keys = [DataSourceKey.SIO_ENG_SIO_MULE_TELEMETERED, DataSourceKey.SIO_ENG_SIO_MULE_RECOVERED]
        # link the data keys to the harvester type, multiple or single file harvester
        harvester_type = {DataSourceKey.SIO_ENG_SIO_MULE_TELEMETERED: HarvesterType.SINGLE_FILE,
                          DataSourceKey.SIO_ENG_SIO_MULE_RECOVERED: HarvesterType.SINGLE_DIRECTORY}
        super(SioEngSioMuleDataSetDriver, self).__init__(config, memento, data_callback, state_callback, event_callback,
                                                     exception_callback, data_keys, harvester_type=harvester_type)
        
    def _build_parser(self, parser_state, stream_in, data_key):
        """
        Build the telemetered or the recovered parser according to
        which data source is appropriate
        """
        parser = None
        if data_key == DataSourceKey.SIO_ENG_SIO_MULE_TELEMETERED:
            parser = self._build_telemetered_parser(parser_state, stream_in)
            log.debug("_build_parser::::  BUILT TELEMETERED PARSER, %s",type(parser) )
            
        elif data_key == DataSourceKey.SIO_ENG_SIO_MULE_RECOVERED:
            parser = self._build_recovered_parser(parser_state, stream_in)
            log.debug("_build_parser::::  BIULDING RECOVERED PARSER, %s",type(parser) )
        else:
            raise ConfigurationException("Bad data key: %s" % data_key)
            
        return parser
        
        
    def _build_telemetered_parser(self, parser_state, stream_in):
        """
        Build and return the telemetered parser
        @param parser_state starting parser state to pass to parser
        @param stream_in Handle of open file to pass to parser
        """
        
        config = self._parser_config[DataSourceKey.SIO_ENG_SIO_MULE_TELEMETERED]
        config.update({
            DataSetDriverConfigKeys.PARTICLE_MODULE: 'mi.dataset.parser.sio_eng_sio_mule',
            DataSetDriverConfigKeys.PARTICLE_CLASS: 'SioEngSioMuleParserDataParticle'
        })
        log.debug("My Config in _build_telemetered_parser: %s", config)
        parser = SioEngSioMuleParser(
            config,
            parser_state,
            stream_in,
            lambda state: self._save_parser_state(state, DataSourceKey.SIO_ENG_SIO_MULE_TELEMETERED),
            self._data_callback,
            self._sample_exception_callback
        )
        log.debug("_build_parser::::   Built parser, returning %s", type(parser))
        return parser
    
    #def _build_recovered_parser(self, parser_state, stream_in):
    #    """
    #    Build and return the telemetered parser
    #    @param parser_state starting parser state to pass to parser
    #    @param stream_in Handle of open file to pass to parser
    #    """
    #    config = self._parser_config[DataSourceKey.SIO_ENG_SIO_MULE_RECOVERED]
    #    config.update({
    #        DataSetDriverConfigKeys.PARTICLE_MODULE: 'mi.dataset.parser.sio_eng_sio_mule',
    #        DataSetDriverConfigKeys.PARTICLE_CLASS: 'SioEngSioMuleParserDataParticle'
    #    })
    #    log.debug("My Config: %s", config)
    #    parser = SioEngSioMuleParser(
    #        config,
    #        parser_state,
    #        infile,
    #        self._save_parser_state,
    #        self._data_callback,
    #        self._sample_exception_callback 
    #    )
    #    return parser
    
    def _build_harvester(self, driver_state):
        """
        Build and return the harvester
        """
        self._harvester = []
        if DataSourceKey.SIO_ENG_SIO_MULE_TELEMETERED in self._harvester_config:
            telemetered_harvester = SingleFileHarvester(
                self._harvester_config.get(DataSourceKey.SIO_ENG_SIO_MULE_TELEMETERED),
                driver_state[DataSourceKey.SIO_ENG_SIO_MULE_TELEMETERED],
                lambda file_state: self._file_changed_callback(file_state,
                    DataSourceKey.SIO_ENG_SIO_MULE_TELEMETERED),
                self._exception_callback
            )
            self._harvester.append(telemetered_harvester)
        else:
            log.warn('No configuration for telemetered harvester, not building')
        return self._harvester
