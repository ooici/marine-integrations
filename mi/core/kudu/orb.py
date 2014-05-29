#!/usr/bin/env python

import _orb
from _orb import ORBCURRENT, ORBPREV, ORBPREVSTASH, ORBNEXT, \
                          ORBNEXT_WAIT, ORBOLDEST,  ORBNEWEST, ORBSTASH

from mi.core.kudu.exc import check_error, OrbError
#from mi.core.kudu import _crap


class OpenError(OrbError): pass
class CloseError(OrbError): pass
class SelectError(OrbError): pass
class RejectError(OrbError): pass
class SeekError(OrbError): pass
class ReapError(OrbError): pass
class ReapTimeoutError(OrbError): pass
class GetError(OrbError): pass
class PutError(OrbError): pass
class PutXError(OrbError): pass

class NotConnected(OrbError): pass


class Orb(object):
    _fd = None

# TODO For some reason this causes infinite recursion.
#    def __repr__(self):
#        return "%s(%s, %s, %s, %s)" % ("Orb", self.orbname, self.permissions,
#                                self.select, self.reject)

    def _connected(f):
        def wrapper(self, *args, **kwargs):
            if self._fd is None:
                raise NotConnected()
            return f(self, *args, **kwargs)
        return wrapper

    def __init__(self, orbname, permissions, select=None, reject=None):
        self.select_str = select
        self.reject_str = reject
        self.orbname = orbname
        self.permissions = permissions

    def __enter__(self):
        if self._fd is None:
            self.connect()
        return self

    def __exit__(self, exc_type, exc_value, traceback):
        if self._fd is not None:
            self.close()

    def connect(self):
        _fd = _orb._orbopen(self.orbname, self.permissions)
        if _fd < 0:
            raise OpenError()
        self._fd = _fd
        if self.select_str is not None:
            self.select(self.select_str)
        if self.reject_str is not None:
            self.reject(self.reject_str)
        # TODO Add after-string

    @_connected
    def close(self):
        if self._fd is not None:
            r = _orb._orbclose(self._fd)
            self._fd = None
#            if r < 0:
#                raise CloseError()

#    def ping(self):
#        pass

#    def tell(self):
#        pass

    @_connected
    def select(self, match):
        check_error(_orb._orbselect(self._fd, match), SelectError)
        return self

    @_connected
    def reject(self, reject):
        check_error(_orb._orbreject(self._fd, reject), RejectError)
        return self

#    def position(self):
#        pass

    @_connected
    def seek(self, whichpkt):
        return check_error(_orb._orbseek(self._fd, whichpkt), SeekError)

#    def after(self):
#        pass

#    @_connected
#    def reap(self):
#        # Call our internal binding, because it releases the GIL and returns
#        # the result code.
#        r, pktid, srcname, pkttime, packetstr, nbytes = _crap.orbreap(self._fd)
#        check_error(r, ReapError)
#        return pktid, srcname, pkttime, packetstr, nbytes
#
#    @_connected
#    def reap_timeout(self, maxseconds):
#        # Call our internal binding, because it releases the GIL and returns
#        # the result code.
#        r, pktid, srcname, pkttime, packetstr, nbytes = _crap.orbreap_timeout(self._fd, maxseconds)
#        check_error(r, ReapTimeoutError)
#        return pktid, srcname, pkttime, packetstr, nbytes
#
#    @_connected
#    def get(self, whichpkt):
#        # Call our internal binding, because it releases the GIL and returns
#        # the result code.
#        r, pktid, srcname, pkttime, packetstr, nbytes = _crap.get(self._fd, whichpkt)
#        check_error(r, GetError)
#        return pktid, srcname, pkttime, packetstr, nbytes

    @_connected
    def put(self, srcname, time, packet):
        return check_error(_orb._orbput(self._fd, srcname, time, packet,
            len(packet)), PutError)

    @_connected
    def putx(self, srcname, time, packet):
        return check_error(_orb._orbputx(self._fd, srcname, time, packet,
            len(packet)), PutXError)

#    def lag(self):
#        pass
#    def stat(self):
#        pass
#    def sources(self):
#        pass
#    def clients(self):
#        pass
#    def resurrect(self):
#        pass
#    def bury(self):
#        pass


#def exhume(filename):
#    """Return a new Orb?"""
#    pass

