#!/usr/bin/env python

import _brttpkt as _brttpkt

class OrbReapThrError(Exception): pass
class SetToStopError(OrbReapThrError): pass
class StopAndWaitError(OrbReapThrError): pass
class IsStopped(OrbReapThrError): pass
class GetError(OrbReapThrError): pass
class NoData(OrbReapThrError): pass
class Timeout(OrbReapThrError): pass
class Stopped(OrbReapThrError): pass
class DestroyError(OrbReapThrError): pass

class OrbReapThr(object):
    def __init__(self, orbname, select=None, reject=None,
	            tafter=-1, timeout=-1, queuesize=64):
        self.orbname = orbname
        self._thread = _brttpkt._orbreapthr_new2(orbname, select, reject,
                                                tafter, timeout, queuesize)
        if not self._thread:
            raise OrbReapThrError()

    def stop_and_wait(self):
        rc = _brttpkt._orbreapthr_stop_and_wait(self._thread)
        if rc < 0:
            raise StopAndWaitError()

    def set_to_stop(self):
        rc = _brttpkt._orbreapthr_set_to_stop(self._thread)
        if rc < 0:
            raise SetToStopError()

    def is_stopped(self):
        rc = _brttpkt._orbreapthr_is_stopped(self._thread)
        if rc < 0:
            raise IsStoppedError()
        return bool(rc)

    def get(self):
        rc, pktid, srcname, pkttime, pkt, nbytes = _brttpkt._orbreapthr_get(
                                                                self._thread)
        if rc == _brttpkt.ORBREAPTHR_NODATA:
            raise NoData()
        if rc == _brttpkt.ORBREAPTHR_TIMEOUT:
            raise Timeout()
        if rc == _brttpkt.ORBREAPTHR_STOPPED:
            raise Stopped()
        if rc < 0:
            raise GetError()
        if rc != _brttpkt.ORBREAPTHR_OK:
            raise GetError()
        return pktid, srcname, pkttime, pkt

    def destroy(self):
        rc = _brttpkt._orbreapthr_destroy(self._thread)
        if rc < 0:
            raise DestroyError()

