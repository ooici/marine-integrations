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
from mi.core.instrument.chunker import Chunker

class Parser(object):
    """ abstract class to show API needed for plugin poller objects """
    def __init__(self, config, open_file, parser_after):  
        self.config = config
        self.open_file = open_file
        self.parser_after = parser_after
        pass

    def get_records(self, max_count):
        """
        Returns a list of particles (following the instrument driver structure).
        """
        pass
    

class FilteringParser(Parser):
    """
    This class filters data from a file-like stream according to the sieve
    function that is passed in. It is intended to be used in data set agents.
    """
    def __init__(self, open_file, parser_after, sieve_fn):
        """
        @param open_file An already open file-like filehandle
        @param parser_after The location in the file to start parsing from
        @param sieve_fn A sieve function that might be added to a handler
           to appropriate filter out the data
        """
        self._chunker = Chunker(sieve_fn)
        self.input_stream = open_file
        self.last_parsed = parser_after

    @staticmethod
    def _extract_sample(particle_class, regex, line):
        """
        Extract sample from a response line if present and publish
        parsed particle

        @param particle_class The class to instantiate for this specific
            data particle. Parameterizing this allows for simple, standard
            behavior from this routine
        @param regex The regular expression that matches a data sample
        @param line string to match for sample.
        @param timestamp port agent timestamp to include with the particle
        @retval return a parsed sample if one was found, else None
        """
        parsed_sample = None
        if regex.match(line):
            particle = particle_class(line)
            parsed_sample = particle.generate()
        
        return parsed_sample
