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
import ion.agents.data.dataset_agent
from ion.agents.agent_stream_publisher import AgentStreamPublisher

from pyon.public import log

import json
import uuid

class IDKAgentStreamPublisher(AgentStreamPublisher):
    def _publish_stream_buffer(self, stream_name):
        """
        overloaded so that data particles are published not granules
        """
        try:
            buf_len = len(self._stream_buffers[stream_name])
            if buf_len == 0:
                return

            publisher = self._publishers[stream_name]

            for x in range(buf_len):
                particle = self._stream_buffers[stream_name].pop()
                publisher.publish(particle)

                log.info('Outgoing particle: %s', particle)

                log.info('Instrument agent %s published data particle on stream %s.',
                    self._agent._proc_name, stream_name)
                log.info('Connection id: %s, connection index: %i.',
                    self._connection_ID.hex, self._connection_index[stream_name])
        except:
            log.exception('Instrument agent %s could not publish data on stream %s.',
                self._agent._proc_name, stream_name)


class InstrumentAgent(ion.agents.instrument.instrument_agent.InstrumentAgent):
    """
    This instrument agent is used in qualification tests.  It overrides the
    default publishing mechanism so the agent publishes data particles.
    """
    def __init__(self, *args, **kwargs):
        ion.agents.instrument.instrument_agent.InstrumentAgent.__init__(self, *args, **kwargs)

    def on_init(self):
        """
        overloaded so we can change the stream publisher object
        """
        super(InstrumentAgent, self).on_init()

        # Set up streams.
        self._asp = IDKAgentStreamPublisher(self)

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
            
            self._asp.on_sample(val)

            log.debug('Instrument agent %s published data particle on stream %s.' % (self._proc_name, stream_name))
            log.trace('Published value: %s' % str(val))

        except Exception as e:
            log.error('Instrument agent %s could not publish data. Exception caught was %s',
                      self._proc_name, e)

    def _construct_packet_factories(self):
        '''
        We don't need the packet factories because we just pass the data particles through.
        Overloading this method clears some factory creation error messages.
        '''
        pass

class DatasetAgent(ion.agents.data.dataset_agent.DataSetAgent):
    """
    This instrument agent is used in qualification tests.  It overrides the
    default publishing mechanism so the agent publishes data particles.
    """
    def __init__(self, *args, **kwargs):
        ion.agents.data.dataset_agent.DataSetAgent.__init__(self, *args, **kwargs)

    def on_init(self):
        """
        overloaded so we can change the stream publisher object
        """
        super(DatasetAgent, self).on_init()

        # Set up streams.
        self._asp = IDKAgentStreamPublisher(self)

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

            self._asp.on_sample(val)

            log.debug('Dataset agent %s published data particle on stream %s.' % (self._proc_name, stream_name))
            log.trace('Published value: %s' % str(val))

        except Exception as e:
            log.error('Dataset agent %s could not publish data. Exception caught was %s',
                      self._proc_name, e)

    def _construct_packet_factories(self):
        '''
        We don't need the packet factories because we just pass the data particles through.
        Overloading this method clears some factory creation error messages.
        '''
        pass

class PublisherInstrumentAgent(ion.agents.instrument.instrument_agent.InstrumentAgent):
    """
    Override the default go active process of the agent so it is forced into command
    mode.  This is used for publication tests that mock input into the port agent and
    there for have not command/response behavior. It is used for testing publication
    """
    def _handler_inactive_go_active(self, *args, **kwargs):
        """
        Overload the default go active handler so it doesn't do a discover, but instead
        forces the agent into command mode.
        """
        next_state = ion.agents.instrument.instrument_agent.ResourceAgentState.COMMAND
        result = None

        # Set the driver config if passed as a parameter.
        try:
            self._dvr_config['comms_config'] = args[0]

        except IndexError:
            pass

        # Connect to the device.
        dvr_comms = self._dvr_config.get('comms_config', None)
        self._dvr_client.cmd_dvr('configure', dvr_comms)
        self._dvr_client.cmd_dvr('connect')

        # Reset the connection id and index.
        #self._connection_ID = uuid.uuid4()
        #self._connection_index = {key : 0 for key in self.aparam_streams.keys()}
        self._asp.reset_connection()

        return (next_state, result)

