#!/usr/bin/env python

from antelope import _Pkt as _pkt
from antelope import _stock

from kudu.exc import check_error, AntelopeError

class PktError(AntelopeError): pass
class UnstuffError(PktError): pass


class Pkt(object):
    db = None
    dfile = None
    nchannels = None
    channels = None
    pfdict = None
    string = None
    time = None
    type = None
    version = None
    pkt_raw = None
    pkttype = None
    channels = None

    _pkttypefields = [ 'content',
                       'name',
                       'suffix',
                       'hdrcode',
                       'bodycode',
                       'desc' ]

    _srcnamefields = [ 'net',
                       'sta',
                       'chan',
                       'loc',
                       'suffix',
                       'subcode' ]

    def __init__(self, srcname=None, time=None, raw_packet=None):
        self.srcnameparts = dict([(k, None) for k in self._srcnamefields])
        self.pkttype = dict([(k, None) for k in self._pkttypefields])
        self.channels = []
        if srcname and time and raw_packet:
            self.unstuff(srcname, time, raw_packet)

    def unstuff(self, srcname, time, raw_packet):
        pkt = None
        try:
            type, pkt = _pkt._unstuffPkt(srcname, time, raw_packet)
            check_error(type, UnstuffError)
            self.string = _pkt._Pkt_string_get(pkt)
            self.pkttype.update(dict(zip(self._pkttypefields,
                _pkt._Pkt_pkttype_get(pkt))))
            if _pkt._Pkt_type_get(pkt) == _pkt.Pkt_pf:
                pfptr = _pkt._Pkt_pfptr_get(pkt)
                if pfptr != None:
                    try:
                        self.pfdict = _stock._pfget(pfptr, None)
                    finally:
                        _stock._pffree(pfptr)
            self.time = time
        finally:
            if pkt is not None:
                _pkt._freePkt(pkt)

    def stuff(self):
        # create Packet struct HERE and ALWAYS free it
        # how does this report failure? I guess the only conceivable failure
        # mode is OOM.
        pkt = None
        pfptr = None
        try:
            pkt = _pkt.newPkt()
            if pkt is None:
                raise RuntimeError("newPkt failure")
            # set pkt fields using raw api
            _pkt._Pkt_pkttype_set(pkt, self.pkttype['suffix'])
            _pkt._Pkt_srcnameparts_set(pkt, *[self.srcnameparts[k] for k in
                self._srcnamefields])
            _pkt._Pkt.time_set(pkt, self.time)
            # stuff packet
            if self.pfdict is not None:
                # make a new pf
                pfptr = _stock.pfnew()
                if pfptr is None:
                    raise RuntimeError("pfnew")
                # copy pfdict into new pf
                # TODO this might not actually work, might have to iterate over
                # items and put each one.
                _stock.pfput(None, self.pfdict, pfptr)
                # attach pfptr to pkt
                _pkt._Pkt_pfptr_set(pkt, pfptr)
            type, packet, srcname, time = _pkt._stuffPkt(pkt)
            return type, packet, srcname, time
        finally:
            if pkt is not None:
                _pkt._freePkt(pkt)
            if pfptr is not None:
                _stock.pffree(pfptr)

       _pkt._Pkt_channels_get (pkt)
       _pkt._Pkt_channels_chan_get (pkt)
       _pkt._Pkt_db_get (pkt)
       _pkt._Pkt_dfile_get (pkt)
       _pkt._Pkt_hook_get (pkt)
       _pkt._Pkt_nchannels_get (pkt)
       _pkt._Pkt_nchannels_get (pkt)
       _pkt._Pkt_pfptr_get (pkt)
       _pkt._Pkt_pkttype_get (pkt)
       _pkt._Pkt_srcnameparts_get (pkt)
       _pkt._Pkt_string_get (pkt)
       _pkt._Pkt_time_get (pkt)
       _pkt._Pkt_type_get (pkt)
       _pkt._Pkt_version_get (pkt)

       _pkt._newPktChannel ()
       _pkt._clrPktChannel (pktchan)
       _pkt._freePktChannel (pktchan)

       _pkt._PktChannel_calib_get (pktchan)
       _pkt._PktChannel_calper_get (pktchan)
       _pkt._PktChannel_chan_get (pktchan)
       _pkt._PktChannel_cuser1_get (pktchan)
       _pkt._PktChannel_cuser2_get (pktchan)
       _pkt._PktChannel_data_get (pktchan)
       _pkt._PktChannel_duser1_get (pktchan)
       _pkt._PktChannel_duser2_get (pktchan)
       _pkt._PktChannel_hook_get (pkt)
       _pkt._PktChannel_isfloat_get (pktchan)
       _pkt._PktChannel_iuser1_get (pktchan)
       _pkt._PktChannel_iuser2_get (pktchan)
       _pkt._PktChannel_iuser3_get (pktchan)
       _pkt._PktChannel_loc_get (pktchan)
       _pkt._PktChannel_net_get (pktchan)
       _pkt._PktChannel_nsamp_get (pktchan)
       _pkt._PktChannel_samprate_get (pktchan)
       _pkt._PktChannel_segtype_get (pktchan)
       _pkt._PktChannel_sta_get (pktchan)
       _pkt._PktChannel_time_get (pktchan)

       _pkt._join_srcname (net, sta, chan, loc, suffix, subcode)
       _pkt._split_srcname (srcname)
       _pkt._suffix2pkttype (suffix)

