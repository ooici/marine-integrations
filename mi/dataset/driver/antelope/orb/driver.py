"""
@package mi.dataset.driver.ctdpf_ckl.wfp.driver
@file marine-integrations/mi/dataset/driver/ctdpf_ckl/wfp/driver.py
@author cgoodrich
@brief Driver for the ctdpf_ckl_wfp
Release notes:

initial release
"""

__author__ = 'Jeff Laughlin <jeff@jefflaughlinconsulting.com>'
__license__ = 'Apache 2.0'

import os, sys
import string
import gevent

from mi.core.log import get_logger ; log = get_logger()

from mi.core.exceptions import SampleException, ConfigurationException

from mi.dataset.dataset_driver import DataSetDriver, DriverStateKey, DataSourceConfigKey
from mi.dataset.parser.antelope_orb import AntelopeOrbParser, AntelopeOrbPacketParticle
from mi.dataset.parser.antelope_orb import ParserConfigKey


class AntelopeOrbDataSetDriver(DataSetDriver):
    _sampling = False

    def _poll(self):
        pass

    @classmethod
    def stream_config(cls):
        return [AntelopeOrbPacketParticle.type()]

    def __init__(self, config, memento, data_callback, state_callback, event_callback, exception_callback):
        super(AntelopeOrbDataSetDriver, self).__init__(config, memento, data_callback, state_callback,
                                                       event_callback, exception_callback)
        self._record_getter_greenlet = None
        self._parser = None
        self._driver_state = None

        self._init_state(memento)

        self._resource_id = self._config.get(DataSourceConfigKey.RESOURCE_ID)
        log.debug("Resource ID: %s", self._resource_id)

        self._file_in_process = '_'.join((self._parser_config[ParserConfigKey.ORBNAME],
                                          self._parser_config[ParserConfigKey.SELECT],
                                          self._parser_config[ParserConfigKey.REJECT]))

    def _verify_config(self):
        """
        Verify we have good configurations for the parser.
        @raise: ConfigurationException if configuration is invalid
        """
        errors = []
        log.debug("Driver Config: %s", self._config)

        self._parser_config = self._config.get(DataSourceConfigKey.PARSER)
        if not self._parser_config:
            errors.append("missing 'parser' config")
        if not ParserConfigKey.ORBNAME in self._parser_config:
            errors.append("parser config missing 'orbname'")
        if not ParserConfigKey.SELECT in self._parser_config:
            errors.append("parser config missing 'select'")
        if not ParserConfigKey.REJECT in self._parser_config:
            errors.append("parser config missing 'reject'")

        if errors:
            log.error("Driver configuration error: %r", errors)
            raise ConfigurationException("driver configuration errors: %r", errors)

    def _init_state(self, memento):
        """
        Initialize driver state
        @param memento: agent persisted memento containing driver state
        """
        if memento != None:
            if not isinstance(memento, dict): raise TypeError("memento must be a dict.")

            self._driver_state = memento
            if not self._driver_state:
                # if the state is empty, add a version
                self._driver_state = {DriverStateKey.VERSION: 0.1}
        else:
            # initialize the state since none was specified
            self._driver_state = {DriverStateKey.VERSION: 0.1}
        log.debug('initial driver state %s', self._driver_state)

    def _save_parser_state(self, state, file_ingested):
        """
        Callback to store the parser state in the driver object.
        @param state: Object used by the parser to indicate position
        """
        log.trace("saving parser state: %r", state)
        self._driver_state[DriverStateKey.PARSER_STATE] = state
        # check if file has been completely parsed by comparing the parsed position and file size
        self._state_callback(self._driver_state)

    def _save_parser_state_after_error(self):
        """
        If a file has a sample exception that has made it to the driver, this file is done,
        mark it as ingested and save the state
        """
        # TODO whut? maybe take this method out? we never fully ingest an orb.
        log.debug("File %s fully parsed", self._file_in_process)
#        self._driver_state[DriverStateKey.INGESTED] = True
        self._state_callback(self._driver_state)

    def _build_parser(self):
        """
        Build and return the parser
        """
        config = self._parser_config
        config.update({
            'particle_module': 'mi.dataset.parser.antelope_orb',
            'particle_class': ['AntelopeOrbPacketParticle']
        })
        log.debug("My Config: %s", config)
        log.debug("My parser state: %s", self._driver_state)
        self._parser = AntelopeOrbParser(
            config,
            self._driver_state.get(DriverStateKey.PARSER_STATE),
            self._save_parser_state,
            self._data_callback,
            self._sample_exception_callback,
        )
        return self._parser

    def _record_getter(self, parser):
        # greenlet to call get_records in loop
        # normally this is done in the context of the harvester greenlet, but
        # we have no harvester.
        # NOTE This is slightly different from what delay is used for in
        # SimpleDataSetDriver. There it's used to rate-limit particle
        # publication. Here it's used as a polling delay while we wait for more
        # data to arrive in the queue.
        # Rate limiting doesn't really make sense here because we are streaming
        # live data; we simply must keep up. The only odd case is when we are
        # playing back older data due to initial startup or recovery after
        # comms loss. If that hammers the system we may need to implement rate
        # limiting here.
        # NOTE change to zero when we go from polling to green-blocking
        delay = 1
        try:
            while True:
                result = parser.get_records()
                if result:
                    pass
                    log.trace("Record parsed: %r", result)
                else:
                    log.trace("No record, sleeping")
                    gevent.sleep(delay)
        except SampleException as e:
            # need to mark the bad file as ingested so we don't re-ingest it
            # no don't do that for antelope URLS
            self._save_parser_state_after_error()
            self._sample_exception_callback(e)

    def _start_sampling(self):
        try:
            log.warning("Start Sampling")
            self._sampling = True
            parser = self._parser = self._build_parser()
            self._record_getter_greenlet = gevent.spawn(self._record_getter, parser)
        except Exception as e:
            log.debug("Exception detected when starting sampling: %s", e, exc_info=True)
            self._exception_callback(e)
            self._sampling = False
            try:
                parser.kill_threads()
            except:
                pass
            try:
                self._record_getter_greenlet.kill()
            except:
                pass

    def _stop_sampling(self):
        log.warning("Stop Sampling")
        self._sampling = False
        if self._record_getter_greenlet is not None:
            self._record_getter_greenlet.kill()
            self._record_getter_greenlet = None
        if self._parser is not None:
            self._parser.kill_threads()
            self._parser = None

    def _is_sampling(self):
        """
        Currently the drivers only have two states, command and streaming and
        all resource commands are common, either start or stop autosample.
        Therefore we didn't implement an enitre state machine to manage states
        and commands.  If it does get more complex than this we should take the
        time to implement a state machine to add some flexibility
        """
        return self._sampling

