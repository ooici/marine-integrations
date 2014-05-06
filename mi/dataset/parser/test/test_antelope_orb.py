#!/usr/bin/env python

"""
@package mi.dataset.parser.test.test_antelope_orb
@file mi/dataset/parser/test/test_antelope_orb.py
@author Jeff Laughlin <jeff@jefflaughlinconsulting.com>
@brief Test code for antelope_orb data parser.
"""

import logging
from mi.core.log import get_logger
log = get_logger()
#log.setLevel(logging.TRACE)

from nose.plugins.attrib import attr

from mock import patch, MagicMock

from mi.core.exceptions import SampleException
from mi.dataset.test.test_parser import ParserUnitTestCase

from mi.dataset.parser.antelope_orb import AntelopeOrbParser, StateKey
from mi.dataset.parser.antelope_orb import AntelopeOrbPacketParticleKey
from mi.dataset.parser.antelope_orb import AntelopeOrbPacketParticleChannelKey
from mi.dataset.parser.antelope_orb import ParserConfigKey

import _Pkt as _pkt
from mi.core.kudu.brttpkt import GetError


@attr('UNIT', group='mi')
class AntelopeOrbParserUnitTestCase(ParserUnitTestCase):

    def state_callback(self, state, file_ingested):
        """ Call back method to watch what comes in via the state callback """
        log.trace("SETTING state_callback_value to " + str(state))
        self.state_callback_values.append(state)
        self.file_ingested = file_ingested

    def pub_callback(self, particle):
        """ Call back method to watch what comes in via the publish callback """
        log.trace("SETTING publish_callback_value to " + str(particle))
        self.publish_callback_values.append(particle)

    def error_callback(self, error):
        """ Call back method to watch what comes in via the state callback """
        log.trace("SETTING error_callback_value to " + str(error))
        self.error_callback_values.append(error)

    def setUp(self):
        ParserUnitTestCase.setUp(self)

        self.error_callback_values = []
        self.state_callback_values = []
        self.publish_callback_values = []

        self.parser_config = {
            ParserConfigKey.ORBNAME: ParserConfigKey.ORBNAME,
            ParserConfigKey.SELECT: ParserConfigKey.SELECT,
            ParserConfigKey.REJECT: ParserConfigKey.REJECT,
        }

        self.parser_state = None

        self.PKT_ID = PKT_ID = 123
        self.PKT_TYPE = PKT_TYPE = 'GENC'
        self.PKT_DATA = PKT_DATA = 1,2,3,4
        self.PKT_TIME = PKT_TIME = 999
        self.PKT_SAMPRATE = PKT_SAMPRATE = 666
        self.PKT_NET = PKT_NET = 'net'
        self.PKT_STA = PKT_STA = 'sta'
        self.PKT_CHAN = PKT_CHAN = 'chan'
        self.PKT_LOC = PKT_LOC = 'loc'

        pkt = _pkt._newPkt()
        _pkt._Pkt_pkttype_set(pkt, PKT_TYPE)
        pktchan = _pkt._newPktChannel()
        _pkt._PktChannel_data_set(pktchan, PKT_DATA)
        _pkt._PktChannel_samprate_set(pktchan, PKT_SAMPRATE)
        _pkt._PktChannel_time_set(pktchan, PKT_TIME)
        _pkt._PktChannel_net_set(pktchan, PKT_NET)
        _pkt._PktChannel_sta_set(pktchan, PKT_STA)
        _pkt._PktChannel_chan_set(pktchan, PKT_CHAN)
        _pkt._PktChannel_loc_set(pktchan, PKT_LOC)
        _pkt._Pkt_channels_set(pkt, [pktchan,])
        pkttype, packet, srcname, time = _pkt._stuffPkt(pkt)
        _pkt._freePkt(pkt)

        with patch('mi.core.kudu.brttpkt.OrbReapThr') as MockOrbReapThr:
            self.parser = AntelopeOrbParser(self.parser_config, self.parser_state,
                            self.state_callback, self.pub_callback,
                            self.error_callback)
        self.parser._orbreapthr.get = MagicMock(return_value=(PKT_ID, srcname, time, packet))

    def test_get_records(self):
        r = self.parser.get_records()
        self.assert_(r is not None)
        self.assertEqual(len(self.publish_callback_values), 1)

    def get_data_value(self, data_dict, key):
        for value in data_dict['values']:
            if value['value_id'] == key:
                return value['value']
        raise KeyError(key)

    def test_build_parsed_values(self):
        self.parser.get_records()
        r = self.publish_callback_values[0][0].generate_dict()
        log.trace(r)
        self.assertEquals(self.PKT_ID, self.get_data_value(r, AntelopeOrbPacketParticleKey.ID))
        self.assertEquals(self.PKT_TYPE, self.get_data_value(r, AntelopeOrbPacketParticleKey.TYPE)[1])
        channels = self.get_data_value(r, AntelopeOrbPacketParticleKey.CHANNELS)
        self.assertEquals(len(channels), 1)
        chan = channels[0]
        self.assertEquals(self.PKT_DATA, chan[AntelopeOrbPacketParticleChannelKey.DATA])
        self.assertEquals(self.PKT_TIME, chan[AntelopeOrbPacketParticleChannelKey.TIME])
        self.assertEquals(self.PKT_SAMPRATE, chan[AntelopeOrbPacketParticleChannelKey.SAMPRATE])
        self.assertEquals(self.PKT_NET, chan[AntelopeOrbPacketParticleChannelKey.NET])
        self.assertEquals(self.PKT_STA, chan[AntelopeOrbPacketParticleChannelKey.STA])
        self.assertEquals(self.PKT_CHAN, chan[AntelopeOrbPacketParticleChannelKey.CHAN])
        self.assertEquals(self.PKT_LOC, chan[AntelopeOrbPacketParticleChannelKey.LOC])

    def assert_state(self, expected_tafter):
        """
        Verify the state
        """
        state = self.parser._state
        log.debug("Current state: %s", state)

        position = state.get(StateKey.TAFTER)
        self.assertEqual(position, expected_tafter)

    def test_set_state(self):
        self.parser.get_records()
        self.assert_state(self.PKT_TIME)

    def test_get_exception(self):
        def f(*args, **kwargs):
            raise Exception()
        self.parser._orbreapthr.get = f
        self.assertRaises(Exception, self.parser.get_records)

    def test_get_error(self):
        def f(*args, **kwargs):
            raise GetError()
        self.parser._orbreapthr.get = f
        self.parser.get_records()

    def test_sample_exception(self):
        self.parser._orbreapthr.get = MagicMock(return_value=(0, '', 0, 'asdf'))
        self.parser.get_records()
        self.assertRaises(SampleException, self.publish_callback_values[0][0]._build_parsed_values)


