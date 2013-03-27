#!/usr/bin/env python

"""
@package ion.services.mi.exceptions Exception classes for MI work
@file ion/services/mi/exceptions.py
@author Edward Hunter
@brief Common exceptions used in the MI work. Specific ones can be subclassed
in the driver code.
"""

__author__ = 'Edward Hunter'
__license__ = 'Apache 2.0'

from mi.core.log import get_logger
log = get_logger()

from mi.core.common import BaseEnum
from ooi.exception import ApplicationException

BadRequest = 400
Timeout = 408
Conflict = 409
ResourceError = 700
ServerError = 500

class InstrumentException(ApplicationException):
    """Base class for an exception related to physical instruments or their
    representation in ION.
    """
    def __init__ (self, msg=None, error_code=ResourceError):
        super(InstrumentException,self).__init__()
        self.args = (error_code, msg)
        self.error_code = error_code
        self.msg = msg

    def get_triple(self):
        """ get exception info without depending on MI exception classes """
        return ( self.error_code, "%s: %s" % (self.__class__.__name__, self.msg), self._stacks )
    
class InstrumentConnectionException(InstrumentException):
    """Exception related to connection with a physical instrument"""

class InstrumentProtocolException(InstrumentException):
    """Exception related to an instrument protocol problem
    
    These are generally related to parsing or scripting of what is supposed
    to happen when talking at the lowest layer protocol to a device.
    @todo Add partial result property?
    """

class InstrumentStateException(InstrumentException):
    """Exception related to an instrument state of any sort"""
    def __init__ (self, msg=None):
        super(InstrumentStateException,self).__init__(msg=msg, error_code=Conflict)

class InstrumentTimeoutException(InstrumentException):
    """Exception related to a command, request, or communication timing out"""
    def __init__ (self, msg=None):
        super(InstrumentTimeoutException,self).__init__(msg=msg, error_code=Timeout)

class InstrumentDataException(InstrumentException):
    """Exception related to the data returned by an instrument or developed
    along the path of handling that data"""

class TestModeException(InstrumentException):
    """Attempt to run a test command while not in test mode"""

class InstrumentCommandException(InstrumentException):
    """A problem with the command sent toward the instrument"""

class InstrumentParameterException(InstrumentException):
    """A required parameter is not supplied"""
    def __init__ (self, msg=None):
        super(InstrumentParameterException,self).__init__(msg=msg, error_code=BadRequest)

class NotImplementedException(InstrumentException):
    """ A driver function is not implemented. """

class ReadOnlyException(InstrumentException):
    pass

class SampleException(InstrumentException):
    """ An expected sample could not be extracted. """

class SchedulerException(InstrumentException):
    """ An error occurred in the scheduler """

class UnexpectedError(InstrumentException):
    """ wrapper to send non-MI exceptions over zmq """
    def __init__ (self, msg=None):
        super(UnexpectedError,self).__init__(msg=msg, error_code=ServerError)
