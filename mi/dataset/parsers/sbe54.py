#!/usr/bin/env python

"""
@package mi.dataset.agents.sbe54 SBE54 data set agent information
@file mi/dataset/agents/sbe54.py
@author Steve Foley
@brief An SBE54-specific data set agent package
"""

__author__ = 'Steve Foley'
__license__ = 'Apache 2.0'

from mi.core.log import get_logger ; log = get_logger()

from mi.dataset.parser import FilteringParser
from mi.instrument.seabird.sbe54tps import Protocol
from mi.instrument.seabird.sbe54tps import SAMPLE_DATA_REGEX_MATCHER
from mi.instrument.seabird.sbe54tps import STATUS_DATA_REGEX_MATCHER
from mi.instrument.seabird.sbe54tps import CONFIGURATION_DATA_REGEX_MATCHER
from mi.instrument.seabird.sbe54tps import EVENT_COUNTER_DATA_REGEX_MATCHER
from mi.instrument.seabird.sbe54tps import HARDWARE_DATA_REGEX_MATCHER
from mi.instrument.seabird.sbe54tps import SAMPLE_REF_OSC_MATCHER
from mi.instrument.seabird.sbe54tps import SBE54tpsSampleDataParticle
from mi.instrument.seabird.sbe54tps import SBE54tpsStatusDataParticle
from mi.instrument.seabird.sbe54tps import SBE54tpsConfigurationDataParticle
from mi.instrument.seabird.sbe54tps import SBE54tpsEventCounterDataParticle
from mi.instrument.seabird.sbe54tps import SBE54tpsHardwareDataParticle
from mi.instrument.seabird.sbe54tps import SBE54tpsSampleRefOscDataParticle

class SBE54Parser(FilteringParser):
    
    def __init__(self, *args, **kwargs):
        super(SBE54Parser, self).__init__(*args, sieve_fn=Protocol.sieve_function, **kwargs)
        
    def get_records(self, max_count):
        # read in some more data
        for line in self.open_file.readline():
            self._chunker.add_chunk(line)

        if max_count < 1:
            return []
            
        result_particles = []
        chunk = self._chunker.get_next_data()
        while len(result_particles) < max_count:
            chunk = self._chunker.get_next_data()
            if not chunk:
                break
            
            # particalize the data block received, return the record
            sample = self._extract_sample(SBE54tpsSampleDataParticle, SAMPLE_DATA_REGEX_MATCHER, chunk)
            if sample:
                result_particles.append(sample)
                continue
            sample = self._extract_sample(SBE54tpsStatusDataParticle, STATUS_DATA_REGEX_MATCHER, chunk)
            if sample:
                result_particles.append(sample)
                continue
            sample = self._extract_sample(SBE54tpsConfigurationDataParticle, CONFIGURATION_DATA_REGEX_MATCHER, chunk)
            if sample:
                result_particles.append(sample)
                continue
            sample = self._extract_sample(SBE54tpsEventCounterDataParticle, EVENT_COUNTER_DATA_REGEX_MATCHER, chunk)
            if sample:
                result_particles.append(sample)
                continue
            sample = self._extract_sample(SBE54tpsHardwareDataParticle, HARDWARE_DATA_REGEX_MATCHER, chunk)
            if sample:
                result_particles.append(sample)
                continue
            sample = self._extract_sample(SBE54tpsSampleRefOscDataParticle, SAMPLE_REF_OSC_MATCHER, chunk)
            if sample:
                result_particles.append(sample)
                
        return result_particles
   
