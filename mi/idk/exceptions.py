#!/usr/bin/env python

__author__ = 'Bill French'
__license__ = 'Apache 2.0'

from mi.core.log import get_logger ; log = get_logger()

class IDKException(Exception):
    """Base class for an exception related to IDK processes
    """
    
    def __init__ (self, msg=None, error_code=None):
        self.args = (error_code, msg)
        self.error_code = error_code
        self.msg = msg
        
        log.error(self)

class ParameterRequired(IDKException):
    """Command parameter required"""
    pass

class NoContainer(IDKException):
    """Capability Container not started"""
    pass

class TestNotInitialized(IDKException):
    """Test configuration singleton not configured"""
    pass

class PortAgentTimeout(IDKException):
    """The port agent failed to start"""
    pass

class DriverDoesNotExist(IDKException):
    """The driver specified doesn't exist"""
    pass
    
class TestNoCommConfig(IDKException):
    """Test can't find comm config yaml"""
    pass
    
class TestNoDeployFile(IDKException):
    """Can't find container deploy file"""
    pass

class ValidationFailure(IDKException):
    """egg generation validation failure"""
    pass

class InvalidParameters(IDKException):
    """Wrong parameters sent"""
    pass
    
class NoRoot(IDKException):
    """No python dirctory found"""
    pass
    
class NotPython(IDKException):
    """Not a python file"""
    pass
    
class ImportError(IDKException):
    """Snakefood failed an import"""
    pass
    
class FileNotFound(IDKException):
    """Missing file"""
    pass
    
class IDKWrongRunningDirectory(IDKException):
    """Some IDK processes need to be run from the base of the MI repo"""
    pass

class DriverNotStarted(IDKException):
    """No driver has been started, run start_driver"""
    pass

class IDKConfigMissing(IDKException):
    """the default IDK configuration file could not be found"""
    pass

class DriverParameterUndefined(IDKException):
    """A driver parameter is undefined in the metadata file"""
    pass

class MissingTemplate(IDKException):
    """An IDK template is missing for code generation"""
    pass

class UnknownDriver(IDKException):
    """Driver couldn't be found by make, model, and name"""
    pass

class NoConfigFileSpecified(IDKException):
    """No comm config filename was specified"""
    pass

class CommConfigReadFail(IDKException):
    """can't read comm config """
    pass

class InvalidCommType(IDKException):
    """Invalid Communication Configuration Type"""
    pass

class GitCommandException(IDKException):
    """not a git local repo"""
    pass

class InvalidGitRepo(IDKException):
    """not a git local repo"""
    pass

class WorkingRepoNotSet(IDKException):
    """The working_repo config parameter not set"""
    pass

class MissingExecutable(IDKException):
    """Can't find an executable"""
    pass

class MissingConfig(IDKException):
    """Missing and IDK configuration option"""
    pass

class FailedToLaunch(IDKException):
    """Could not launch external application"""
    pass

