"""
@package mi.dataset.driver.ctdpf_ckl.wfp_sio_mule.driver
@file marine-integrations/mi/dataset/driver/ctdpf_ckl/wfp_sio_mule/driver.py
@author cgoodrich
@brief Driver for the ctdpf_ckl_wfp_sio_mule
Release notes:

Initial Release
"""

__author__ = 'cgoodrich'
__license__ = 'Apache 2.0'

from mi.core.log import get_logger
log = get_logger()
from mi.core.common import BaseEnum
from mi.dataset.driver.sio_mule.sio_mule_driver import SioMuleDataSetDriver

from mi.dataset.dataset_driver import HarvesterType
from mi.dataset.harvester import SingleFileHarvester


from mi.dataset.parser.ctdpf_ckl_wfp_sio_mule import \
    CtdpfCklWfpSioMuleParser, \
    CtdpfCklWfpSioMuleDataParticle, \
    CtdpfCklWfpSioMuleMetadataParticle


class DataTypeKey(BaseEnum):
    CTDPF_CKL_WFP = 'ctdpf_ckl_wfp'
    CTDPF_CKL_WFP_SIO_MULE = 'ctdpf_ckl_wfp_sio_mule'


class CtdpfCklWfpDataSetDriver(SioMuleDataSetDriver):

    def __init__(self,
                 config,
                 memento,
                 data_callback,
                 state_callback,
                 event_callback,
                 exception_callback):

        # initialize the possible types of harvester/parser pairs for this driver
        data_keys = [DataTypeKey.CTDPF_CKL_WFP_SIO_MULE, DataTypeKey.CTDPF_CKL_WFP]

        # link the data keys to the harvester type, multiple or single file harvester
        harvester_type = {DataTypeKey.CTDPF_CKL_WFP_SIO_MULE: HarvesterType.SINGLE_FILE,
                          DataTypeKey.CTDPF_CKL_WFP: HarvesterType.SINGLE_DIRECTORY}

        super(CtdpfCklWfpDataSetDriver, self).__init__(config,
                                                       memento,
                                                       data_callback,
                                                       state_callback,
                                                       event_callback,
                                                       exception_callback,
                                                       data_keys,
                                                       harvester_type)

    @classmethod
    def stream_config(cls):
        return [CtdpfCklWfpSioMuleMetadataParticle.type(),
                CtdpfCklWfpSioMuleDataParticle.type()]

    def _build_parser(self, parser_state, infile, data_key=None):
        """
        Build and return the parser
        """
        config = self._parser_config
        config.update({
            'particle_module': 'mi.dataset.parser.ctdpf_ckl_wfp_sio_mule',
            'particle_class': ['CtdpfCklWfpSioMuleMetadataParticle',
                               'CtdpfCklWfpSioMuleDataParticle']
        })

        self._parser = CtdpfCklWfpSioMuleParser(
            config,
            parser_state,
            infile,
            lambda state:
                self._save_parser_state(state, DataTypeKey.CTDPF_CKL_WFP_SIO_MULE),
            self._data_callback,
            self._sample_exception_callback 
        )
        return self._parser

    def _build_harvester(self, driver_state):
        """
        Build and return the harvester
        """

        self._harvester = []
        if DataTypeKey.CTDPF_CKL_WFP_SIO_MULE in self._harvester_config:
            self.ctdpf_ckl_wfp_sio_mule_harvester = SingleFileHarvester(
                self._harvester_config.get(DataTypeKey.CTDPF_CKL_WFP_SIO_MULE),
                driver_state[DataTypeKey.CTDPF_CKL_WFP_SIO_MULE],
                lambda file_state:
                    self._file_changed_callback(file_state, DataTypeKey.CTDPF_CKL_WFP_SIO_MULE),
                self._exception_callback
            )
            self._harvester.append(self.ctdpf_ckl_wfp_sio_mule_harvester)
        else:
            log.warn('No configuration for ctdpf_ckl_wfp_sio_mule harvester, not building')

        return self._harvester
