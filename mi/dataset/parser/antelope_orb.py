#!/usr/bin/env python

"""
@package mi.dataset.parser.antelope_orb
@file marine-integrations/mi/dataset/parser/antelope_orb.py
@author Jeff Laughlin <jeff@jefflaughlinconsulting.com>
@brief Parser for the antelope_orb dataset driver
Release notes:

Initial Release
"""

__author__ = 'Jeff Laughlin <jeff@jefflaughlinconsulting.com>'
__license__ = 'Apache 2.0'


import logging
from mi.core.log import get_logger
log = get_logger()
#log.setLevel(logging.TRACE)

from mi.core.common import BaseEnum
from mi.core.instrument.data_particle import DataParticle, DataParticleKey
from mi.core.exceptions import SampleException

from mi.dataset.dataset_parser import Parser

from mi.core.kudu.brttpkt import OrbReapThr, GetError
import _Pkt as _pkt


class ParserConfigKey(BaseEnum):
    ORBNAME = "orbname"
    SELECT  = "select"
    REJECT  = "reject"


class StateKey(BaseEnum):
    TAFTER = 'tafter' # timestamp of last orb pkt read


class DataParticleType(BaseEnum):
    ANTELOPE_ORB_PACKET = 'antelope_orb_packet'


class AntelopeOrbPacketParticleKey(BaseEnum):
    ID = 'id'
    CHANNELS = 'channels'
    DB = 'db'
    DFILE = 'dfile'
    PF = 'pf'
    SRCNAME = 'srcname'
    STRING = 'string'
    TIME = 'time'
    TYPE = 'type'
    VERSION = 'version'


# Packet channel fields
class AntelopeOrbPacketParticleChannelKey(BaseEnum):
    CALIB = 'calib'
    CALPER = 'calper'
    CHAN = 'chan'
    CUSER1 = 'cuser1'
    CUSER2 = 'cuser2'
    DATA = 'data'
    DUSER1 = 'duser1'
    DUSER2 = 'duser2'
    IUSER1 = 'iuser1'
    IUSER2 = 'iuser2'
    IUSER3 = 'iuser3'
    LOC = 'loc'
    NET = 'net'
    SAMPRATE = 'samprate'
    SEGTYPE = 'segtype'
    STA = 'sta'
    TIME = 'time'


class AntelopeOrbPacketParticle(DataParticle):
    """
    Class for parsing data from the antelope_orb data set
    """

    _data_particle_type = DataParticleType.ANTELOPE_ORB_PACKET

    def _build_parsed_values(self):
        """
        Take something in the data format and turn it into
        an array of dictionaries defining the data in the particle
        with the appropriate tag.
        @throws SampleException If there is a problem with sample creation
        """
        log.trace("_build_parsed_values")
        pktid, srcname, orbtimestamp, raw_packet = self.raw_data

        result = []
        pk = AntelopeOrbPacketParticleKey
        vid = DataParticleKey.VALUE_ID
        v = DataParticleKey.VALUE

        pkt = None
        try:
            pkttype, pkt = _pkt._unstuffPkt(srcname, orbtimestamp, raw_packet)
            if pkttype < 0:
                raise SampleException("Failed to unstuff ORB packet")

            result.append({vid: pk.ID, v: pktid})
            result.append({vid: pk.DB, v: _pkt._Pkt_db_get(pkt)})
            result.append({vid: pk.DFILE, v: _pkt._Pkt_dfile_get(pkt)})
            result.append({vid: pk.SRCNAME, v: _pkt._Pkt_srcnameparts_get(pkt)})
            result.append({vid: pk.VERSION, v: _pkt._Pkt_version_get(pkt)})
            result.append({vid: pk.STRING, v: _pkt._Pkt_string_get(pkt)})
            result.append({vid: pk.TIME, v: _pkt._Pkt_time_get(pkt)})
            result.append({vid: pk.TYPE, v: _pkt._Pkt_pkttype_get(pkt)})

            pf = None
            pfptr = _pkt._Pkt_pfptr_get(pkt)
            if pfptr != None:
                try:
                    pf = _stock._pfget(pfptr, None)
                finally:
                    _stock._pffree(pfptr)
            result.append({vid: pk.PF, v: pf})

            # channels
            channels = []
            ck = AntelopeOrbPacketParticleChannelKey
            for pktchan in _pkt._Pkt_channels_get(pkt):
                channel = {}
                channels.append(channel)
                channel[ck.CALIB] = _pkt._PktChannel_calib_get(pktchan)
                channel[ck.CALPER] = _pkt._PktChannel_calper_get(pktchan)
                channel[ck.CHAN] = _pkt._PktChannel_chan_get(pktchan)
                channel[ck.CUSER1] = _pkt._PktChannel_cuser1_get(pktchan)
                channel[ck.CUSER2] = _pkt._PktChannel_cuser2_get(pktchan)
                channel[ck.DATA] = _pkt._PktChannel_data_get(pktchan)
                channel[ck.DUSER1] = _pkt._PktChannel_duser1_get(pktchan)
                channel[ck.DUSER2] = _pkt._PktChannel_duser2_get(pktchan)
                channel[ck.IUSER1] = _pkt._PktChannel_iuser1_get(pktchan)
                channel[ck.IUSER2] = _pkt._PktChannel_iuser2_get(pktchan)
                channel[ck.IUSER3] = _pkt._PktChannel_iuser3_get(pktchan)
                channel[ck.LOC] = _pkt._PktChannel_loc_get(pktchan)
                channel[ck.NET] = _pkt._PktChannel_net_get(pktchan)
                channel[ck.SAMPRATE] = _pkt._PktChannel_samprate_get(pktchan)
                channel[ck.SEGTYPE] = _pkt._PktChannel_segtype_get(pktchan)
                channel[ck.STA] = _pkt._PktChannel_sta_get(pktchan)
                channel[ck.TIME] = _pkt._PktChannel_time_get(pktchan)

            result.append({vid: pk.CHANNELS, v: channels})

        finally:
            if pkt is not None:
                _pkt._freePkt(pkt)

        return result

class AntelopeOrbParser(Parser):
    """
    Pseudo-parser for Antelope ORB data.

    This class doesn't really parse anything, but it fits into the DSA
    architecture in the same place as the other parsers, so leaving it named
    parser for consistency.

    What this class does do is connect to an Antelope ORB and get packets from
    it.
    """

    def __init__(self, config, state,
                 state_callback, publish_callback, exception_callback = None):
        super(AntelopeOrbParser, self).__init__(config,
                                           None,

City Budget

Nancy Wolfe – Park St

My main concern with the city budget ( and I did vote for it) is with the police and particularly the fire department budget. How can Barre Town get along with only volunteer fireman which cost the town only $53,000 last year-- while, the City, with approximately the same # of people to protect, has the same number paid full time for a budget of $1,300,000. Why can't we have some volunteers so, instead of calling in 2 fireman every time a call comes in, we could have volunteers who wouldn't be paid for 2 hours even if the call turns out to be a false alarm? Is this all about unions? I have also noticed over the years that Montpelier has hired interns for a year in their various offices while Barre City is not able to do so because of union contract..

Email Author Reply to Forum
 
                                           state,
                                           None,
                                           state_callback,
                                           publish_callback,
                                           exception_callback)

        # NOTE Still need this?
        self.stop = False

        self._state = {StateKey.TAFTER: 0}
        if state:
            self._state = state

        orbname = self._config[ParserConfigKey.ORBNAME]
        select = self._config[ParserConfigKey.SELECT]
        reject = self._config[ParserConfigKey.REJECT]
        tafter = self._state[StateKey.TAFTER]

        self._orbreapthr = OrbReapThr(orbname, select, reject, tafter, timeout=0, queuesize=100)
        log.info("Connected to ORB %s %s %s" % (orbname, select, reject))

    def kill_threads(self):
        self.orbreapthr.stop_and_wait()
        self.orbreapthr.destroy()

    def get_records(self):
        """
        Go ahead and execute the data parsing loop up to a point. This involves
        getting data from the file, stuffing it in to the chunker, then parsing
        it and publishing.
        @param num_records The number of records to gather
        @retval Return the list of particles requested, [] if none available
        """
        try:
            if self.stop:
                return
            get_r = self._orbreapthr.get()
            pktid, srcname, orbtimestamp, raw_packet = get_r
            # timestamp = ntp.now()
            # make particle here
            particle = AntelopeOrbPacketParticle(
                get_r,
                preferred_timestamp = DataParticleKey.INTERNAL_TIMESTAMP
            )
            self._publish_sample(particle)
            # TODO rate limit state updates?
            self._state[StateKey.TAFTER] = orbtimestamp
            log.debug("State: ", self._state)
            self._state_callback(self._state, False) # push new state to driver
        except (GetError), e:
            log.debug("orbreapthr.get exception %r" % type(e))
            return None
        return get_r

