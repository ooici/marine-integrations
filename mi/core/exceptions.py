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

from mi.core.common import BaseEnum
from ooi.exception import ApplicationException

import traceback

class IONExceptionCodes(BaseEnum):
    BadRequest = 400
    Unauthorized = 401
    NotFound = 404
    Timeout = 408
    Conflict = 409
    Inconsistent = 410
    FilesystemError = 411
    StreamingError = 412
    CorruptionError = 413
    ServerError = 500
    ServiceUnavailable = 503
    ConfigNotFound = 540
    IonInstrumentError = 600
    InstConnectionError = 610
    InstNotImplementedError = 620
    InstParameterError = 630
    InstProtocolError = 640
    InstSampleError = 650
    InstStateError = 660
    InstUnknownCommandError = 670
    InstDriverError = 680
    InstTimeoutError = 690
    ResourceError = 700

# Default Error
DEFAULT_ION_ERROR_CODE = IONExceptionCodes.ResourceError

class InstrumentException(ApplicationException):
    """Base class for an exception related to physical instruments or their
    representation in ION.
    """
    def __init__ (self, msg=None, error_code=None):
        self.args = (error_code, msg)
        self.error_code = error_code
        self.ion_error_code = None
        self.msg = msg
    
class InstrumentConnectionException(InstrumentException):
    """Exception related to connection with a physical instrument"""
    ion_error_code = DEFAULT_ION_ERROR_CODE

class InstrumentProtocolException(InstrumentException):
    """Exception related to an instrument protocol problem
    
    These are generally related to parsing or scripting of what is supposed
    to happen when talking at the lowest layer protocol to a device.
    @todo Add partial result property?
    """
    ion_error_code = DEFAULT_ION_ERROR_CODE

class InstrumentStateException(InstrumentException):
    """Exception related to an instrument state of any sort"""
    ion_error_code = IONExceptionCodes.Conflict

class InstrumentTimeoutException(InstrumentException):
    """Exception related to a command, request, or communication timing out"""
    ion_error_code = IONExceptionCodes.Timeout

class InstrumentDataException(InstrumentException):
    """Exception related to the data returned by an instrument or developed
    along the path of handling that data"""
    ion_error_code = DEFAULT_ION_ERROR_CODE

class TestModeException(InstrumentException):
    """Attempt to run a test command while not in test mode"""
    ion_error_code = DEFAULT_ION_ERROR_CODE

class InstrumentCommandException(InstrumentException):
    """A problem with the command sent toward the instrument"""
    ion_error_code = DEFAULT_ION_ERROR_CODE

class InstrumentParameterException(InstrumentException):
    """A required parameter is not supplied"""
    ion_error_code = IONExceptionCodes.BadRequest

class NotImplementedException(InstrumentException):
    """
    A driver function is not implemented.
    """
    ion_error_code = DEFAULT_ION_ERROR_CODE

class ReadOnlyException(InstrumentException):
    """
    A driver function is not implemented.
    """
    ion_error_code = DEFAULT_ION_ERROR_CODE

class SampleException(InstrumentException):
    """
    An expected sample could not be extracted.
    """
    ion_error_code = DEFAULT_ION_ERROR_CODE

class SchedulerException(InstrumentException):
    """
    An error occurred in the scheduler
    """
    ion_error_code = DEFAULT_ION_ERROR_CODE
