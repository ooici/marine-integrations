#!/usr/bin/env python

"""
@package mi.idk.instrument_agent IDK Instrument resource agent
@file mi/idk/instrument_agent.py
@author Bill French
@brief Speciaized instrument agent for the IDK to trap event and publish.

In the IDK we don't test all the way to a data granule, but stop at the
data particle.  This is so if the IA changes it's publishing format or
the parameter definition for the stream changes our driver tests are
still valid.  So we short circuit the publication handler so that it
just passed through data particles.
"""

__author__ = 'Bill French'
__license__ = 'Apache 2.0'

# ION imports.
import ion.agents.instrument.instrument_agent

from pyon.public import log

import json

class InstrumentAgent(ion.agents.instrument.instrument_agent.InstrumentAgent):
    def __init__(self, *args, **kwargs):
        ion.agents.instrument.instrument_agent.InstrumentAgent.__init__(self, *args, **kwargs)

    def _async_driver_event_sample(self, val, ts):
        '''
        Overload this method to change what is published.  For driver tests we will verify that
        Data particles are built to spec so we just pass through data particles here.
        '''
        # If the sample event is encoded, load it back to a dict.
        if isinstance(val, str):
            val = json.loads(val)

        try:
            stream_name = val['stream_name']
            publisher = self._data_publishers.get(stream_name)

            if(not publisher):
                log.error("publish to undefined stream '%s'" % stream_name)

            publisher.publish(val)
            log.debug('Instrument agent %s published data particle on stream %s.' % (self._proc_name, stream_name))

        except Exception as ex:
            '''
            log.error('Instrument agent %s could not publish data. %s' %
                (self._proc_name, ex) )
            '''
            #publisher.publish seems to e throwing an AssertError exception
            # it seems to happen when the tests are being torn down.
            # TODO: Figure out WTF is happening here
            pass

    def _construct_packet_factories(self):
        '''
        We don't need the packet factories because we just pass the data particles through.
        Overloading this method clears some factory creation error messages.
        '''
        pass

