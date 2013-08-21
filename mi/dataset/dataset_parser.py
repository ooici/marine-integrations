#!/usr/bin/env python

"""
@package mi.dataset.parser A collection of parsers that strip data blocks
out of files and feed them into the system.
@file mi/dataset/parser.py
@author Steve Foley
@brief Base classes for data set agent parsers
"""

__author__ = 'Steve Foley'
__license__ = 'Apache 2.0'

from mi.core.log import get_logger ; log = get_logger()
from mi.core.instrument.chunker import StringChunker
from mi.core.instrument.data_particle import DataParticleKey


class Parser(object):
    """ abstract class to show API needed for plugin poller objects """

    def __init__(self, config, open_file, parser_after, sieve_fn,
                 state_callback, publish_callback):
        """
        @param config The configuration parameters to feed into the parser
        @param open_file An already open file-like filehandle
        @param parser_after The location in the file to start parsing from.
           This reflects what has already been published.
        @param sieve_fn A sieve function that might be added to a handler
           to appropriate filter out the data
        @param state_callback The callback method from the agent driver
           (ultimately the agent) to call back when a state needs to be
           updated
        @param publish_callback The callback from the agent driver (and
           ultimately from the agent) where we send our sample particle to
           be published into ION
        """
        self._chunker = StringChunker(sieve_fn)
        self._stream_handle = open_file
        self._state = parser_after
        self._state_callback = state_callback
        self._publish_callback = publish_callback
        self._config = config

    def get_records(self, max_count):
        """
        Returns a list of particles (following the instrument driver structure).
        """
        pass

    def _publish_sample(self, samples):
        """
        Publish the samples with the given publishing callback.
        @param samples The list of data particle to publish up to the system
        """
        if isinstance(samples, list):
            self._publish_callback(samples)
        else:
            self._publish_callback([samples])
        
    @staticmethod
    def _extract_sample(particle_class, regex, line, timestamp):
        """
        Extract sample from a response line if present and publish
        parsed particle

        @param particle_class The class to instantiate for this specific
            data particle. Parameterizing this allows for simple, standard
            behavior from this routine
        @param regex The regular expression that matches a data sample
        @param line string to match for sample.
        @retval return a raw particle if a sample was found, else None
        """
        #parsed_sample = None
        particle = None
        if regex.match(line):
            particle = particle_class(line, internal_timestamp=timestamp,
                                      preferred_timestamp=DataParticleKey.INTERNAL_TIMESTAMP)
            #parsed_sample = particle.generate()
        
        return particle
    
