#!/usr/bin/env python

ORB_EOF         = -9
ORB_INCOMPLETE  = -2

class AntelopeError(Exception):
    pass

# TODO Tack on additional info from the antelope error handling jazz.
class OrbError(AntelopeError): pass
class OrbEOF(OrbError): pass
class OrbIncomplete(OrbError): pass

def check_error(r, default_exc=AntelopeError ):
    if r < 0:
        if r == ORB_EOF:
            raise OrbEOF()
        elif r == ORB_INCOMPLETE:
            raise OrbIncomplete()
        else:
            raise default_exc()
    else:
        return r



