"""
@package mi.dataset.driver.cspp_eng.cspp.driver
@file marine-integrations/mi/dataset/driver/cspp_eng/cspp/driver.py
@author Jeff Roy
@brief Driver for the cspp_eng_cspp
Release notes:

initial release
"""

__author__ = 'Jeff Roy'
__license__ = 'Apache 2.0'


from mi.core.log import get_logger
log = get_logger()

from mi.core.exceptions import ConfigurationException

from mi.dataset.dataset_driver import MultipleHarvesterDataSetDriver
from mi.dataset.harvester import SingleDirectoryHarvester
from mi.dataset.dataset_driver import DataSetDriverConfigKeys


from mi.dataset.parser.dbg_pdbg_cspp import \
    DbgPdbgCsppParser, \
    DbgPdbgRecoveredGpsParticle, \
    DbgPdbgTelemeteredGpsParticle, \
    DbgPdbgRecoveredBatteryParticle, \
    DbgPdbgTelemeteredBatteryParticle, \
    DbgPdbgMetadataTelemeteredDataParticle, \
    DbgPdbgMetadataRecoveredDataParticle, \
    DbgPdbgDataTypeKey, \
    GPS_ADJUSTMENT_CLASS_KEY, \
    BATTERY_STATUS_CLASS_KEY

from mi.dataset.parser.wc_hmr_cspp import \
    WcHmrCsppParser, \
    WcHmrEngRecoveredDataParticle, \
    WcHmrEngTelemeteredDataParticle, \
    WcHmrMetadataRecoveredDataParticle, \
    WcHmrMetadataTelemeteredDataParticle, \
    WcHmrDataTypeKey

from mi.dataset.parser.wc_sbe_cspp import \
    WcSbeCsppParser, \
    WcSbeEngRecoveredDataParticle, \
    WcSbeEngTelemeteredDataParticle, \
    WcSbeMetadataRecoveredDataParticle, \
    WcSbeMetadataTelemeteredDataParticle, \
    WcSbeDataTypeKey

from mi.dataset.parser.wc_wm_cspp import \
    WcWmCsppParser, \
    WcWmEngRecoveredDataParticle, \
    WcWmEngTelemeteredDataParticle, \
    WcWmMetadataRecoveredDataParticle, \
    WcWmMetadataTelemeteredDataParticle, \
    WcWmDataTypeKey

from mi.dataset.parser.cspp_base import \
    METADATA_PARTICLE_CLASS_KEY, \
    DATA_PARTICLE_CLASS_KEY

# The following structure is a multi-layered dictionary used by _build_parser
# All of the values in lowest level dictionaries are classes.
#
# The primary key corresponds to the Data Type Key passed in defining which parser to build
# each value in the primary dictionary is a nested dictionary
#
# The secondary key defines the the parser to be built and a PARTICLE_CLASSES_DICT
#
# The tertiary key defines the particle types in the PARTICLE_CLASSES_DICT

PARSER_CONFIG_DICT = {
    DbgPdbgDataTypeKey.DBG_PDBG_CSPP_TELEMETERED:
        {DataSetDriverConfigKeys.PARTICLE_CLASSES_DICT:
             {METADATA_PARTICLE_CLASS_KEY: DbgPdbgMetadataTelemeteredDataParticle,
              BATTERY_STATUS_CLASS_KEY: DbgPdbgTelemeteredBatteryParticle,
              GPS_ADJUSTMENT_CLASS_KEY: DbgPdbgTelemeteredGpsParticle},
         DataSetDriverConfigKeys.PARSER: DbgPdbgCsppParser
        },
    DbgPdbgDataTypeKey.DBG_PDBG_CSPP_RECOVERED:
        {DataSetDriverConfigKeys.PARTICLE_CLASSES_DICT:
             {METADATA_PARTICLE_CLASS_KEY: DbgPdbgMetadataRecoveredDataParticle,
              BATTERY_STATUS_CLASS_KEY: DbgPdbgRecoveredBatteryParticle,
              GPS_ADJUSTMENT_CLASS_KEY: DbgPdbgRecoveredGpsParticle},
         DataSetDriverConfigKeys.PARSER: DbgPdbgCsppParser
        },
    WcHmrDataTypeKey.WC_HMR_CSPP_TELEMETERED:
        {DataSetDriverConfigKeys.PARTICLE_CLASSES_DICT:
             {METADATA_PARTICLE_CLASS_KEY: WcHmrMetadataTelemeteredDataParticle,
              DATA_PARTICLE_CLASS_KEY: WcHmrEngTelemeteredDataParticle},
         DataSetDriverConfigKeys.PARSER: WcHmrCsppParser
        },
    WcHmrDataTypeKey.WC_HMR_CSPP_RECOVERED:
        {DataSetDriverConfigKeys.PARTICLE_CLASSES_DICT:
             {METADATA_PARTICLE_CLASS_KEY: WcHmrMetadataRecoveredDataParticle,
              DATA_PARTICLE_CLASS_KEY: WcHmrEngRecoveredDataParticle},
         DataSetDriverConfigKeys.PARSER: WcHmrCsppParser
        },
    WcSbeDataTypeKey.WC_SBE_CSPP_TELEMETERED:
        {DataSetDriverConfigKeys.PARTICLE_CLASSES_DICT:
             {METADATA_PARTICLE_CLASS_KEY: WcSbeMetadataTelemeteredDataParticle,
              DATA_PARTICLE_CLASS_KEY: WcSbeEngTelemeteredDataParticle},
         DataSetDriverConfigKeys.PARSER: WcSbeCsppParser
        },
    WcSbeDataTypeKey.WC_SBE_CSPP_RECOVERED:
        {DataSetDriverConfigKeys.PARTICLE_CLASSES_DICT:
             {METADATA_PARTICLE_CLASS_KEY: WcSbeMetadataRecoveredDataParticle,
              DATA_PARTICLE_CLASS_KEY: WcSbeEngRecoveredDataParticle},
         DataSetDriverConfigKeys.PARSER: WcSbeCsppParser
        },
    WcWmDataTypeKey.WC_WM_CSPP_TELEMETERED:
        {DataSetDriverConfigKeys.PARTICLE_CLASSES_DICT:
             {METADATA_PARTICLE_CLASS_KEY: WcWmMetadataTelemeteredDataParticle,
              DATA_PARTICLE_CLASS_KEY: WcWmEngTelemeteredDataParticle},
         DataSetDriverConfigKeys.PARSER: WcWmCsppParser
        },
    WcWmDataTypeKey.WC_WM_CSPP_RECOVERED:
        {DataSetDriverConfigKeys.PARTICLE_CLASSES_DICT:
             {METADATA_PARTICLE_CLASS_KEY: WcWmMetadataRecoveredDataParticle,
              DATA_PARTICLE_CLASS_KEY: WcWmEngRecoveredDataParticle},
         DataSetDriverConfigKeys.PARSER: WcWmCsppParser
        }
}


class CsppEngCsppDataSetDriver(MultipleHarvesterDataSetDriver):
    
    @classmethod
    def stream_config(cls):
        return [DbgPdbgRecoveredGpsParticle.type(),
                DbgPdbgTelemeteredGpsParticle.type(),
                DbgPdbgRecoveredBatteryParticle.type(),
                DbgPdbgTelemeteredBatteryParticle.type(),
                DbgPdbgMetadataTelemeteredDataParticle.type(),
                DbgPdbgMetadataRecoveredDataParticle.type(),
                WcHmrEngRecoveredDataParticle.type(),
                WcHmrEngTelemeteredDataParticle.type(),
                WcHmrMetadataRecoveredDataParticle.type(),
                WcHmrMetadataTelemeteredDataParticle.type(),
                WcSbeEngRecoveredDataParticle.type(),
                WcSbeEngTelemeteredDataParticle.type(),
                WcSbeMetadataRecoveredDataParticle.type(),
                WcSbeMetadataTelemeteredDataParticle.type(),
                WcWmEngRecoveredDataParticle.type(),
                WcWmEngTelemeteredDataParticle.type(),
                WcWmMetadataRecoveredDataParticle.type(),
                WcWmMetadataTelemeteredDataParticle.type()
                ]

    def __init__(self, config, memento, data_callback, state_callback, event_callback, exception_callback):

        data_keys = DbgPdbgDataTypeKey.list() + WcHmrDataTypeKey.list() + \
                    WcSbeDataTypeKey.list() + WcWmDataTypeKey.list()

        log.debug("data keys in driver constructor are %s", data_keys)

        super(CsppEngCsppDataSetDriver, self).__init__(config, memento,
                                                       data_callback,
                                                       state_callback,
                                                       event_callback,
                                                       exception_callback,
                                                       data_keys)

    def _build_parser(self, parser_state, stream_in, data_key):
        """
        Build and return the parser
        """

        config = self._parser_config.get(data_key)

        if config is None:
            log.warn('Parser config does not exist for key = %s.  Not building parser', data_key)
            raise ConfigurationException

        if data_key not in PARSER_CONFIG_DICT:
            log.warn('Invalid Data_Key %s.  Not building parser', data_key)
            raise ConfigurationException

        try:
            config.update({
                DataSetDriverConfigKeys.PARTICLE_CLASS: None,
                DataSetDriverConfigKeys.PARTICLE_CLASSES_DICT:
                    PARSER_CONFIG_DICT[data_key][DataSetDriverConfigKeys.PARTICLE_CLASSES_DICT]
            })

            parser_class = PARSER_CONFIG_DICT[data_key][DataSetDriverConfigKeys.PARSER]

            log.debug('### build_parser Parser Class is %s', parser_class)

            parser = parser_class(
                config,
                parser_state,
                stream_in,
                lambda state, ingested:
                self._save_parser_state(state, data_key, ingested),
                self._data_callback,
                self._sample_exception_callback
            )
        except Exception as e:
            log.error('Something went wrong building Parser for key %s', data_key)
            parser = None
            self._exception_callback(e)

        return parser

    def _build_harvester(self, driver_state):
        """
        Build and return the harvester
        """

        harvesters = []

        for key in self._data_keys:

            if key in self._harvester_config:
                harvester = self.build_single_harvester(driver_state, key)
                log.debug('harvester for %s built', key)
                harvesters.append(harvester)
            else:
                log.warn('No configuration for %s harvester, not building', key)

        return harvesters

    def build_single_harvester(self, driver_state, key):

        harvester = SingleDirectoryHarvester(
            self._harvester_config.get(key),
            driver_state[key],
            lambda filename: self._new_file_callback(filename, key),
            lambda modified: self._modified_file_callback(modified, key),
            self._exception_callback)

        return harvester
