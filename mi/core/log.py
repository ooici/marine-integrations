#!/usr/bin/env python
"""
@file mi/core/log.py
@author Bill French
@brief Log mechanism for the MI repository.  The log facility is
pretty much a copy paste from pyon.util.log and pyon.util.config.
I've also added a log manager which which uses a singleton to
ensure the mi logger is only initialized once.  It also provides
methods to set the log level and file dynamically at runtime.

Usage:

from pyon.util.log import log, log_manager

# Note that this only changes the log level for the MI logger
log_manager.set_log_level("DEBUG")

# Dynamically change the log file
log_manager.set_log_file("/tmp/file")

# Write a log message
log.critical("message")
log.error("message")
log.warn("message")
log.info("message")
log.debug("message")
"""
__author__ = 'Bill French'
__license__ = 'Apache 2.0'

import __builtin__
import logging
import os
import sys
import errno
from pkg_resources import resource_string

from mi.core.common import Singleton
from mi.core.common import Config


class LoggerConfig(object):
    """
    Logger Config.  Reads a logger config yml file as well as the logger config local file to overload system settings.
    files are read using pkg_resources.resource_string so that the configuration can also be read when running from an
    egg.
    """
    def __init__(self):
        system_log_config = None
        local_log_config = None

        # Allows for relative pathing starting from this file in a package.  This will work with zip_safe egg files
        system_log_config = resource_string(__name__, '../../extern/ion-definitions/res/config/logging.yml')

        try:
            local_log_config = resource_string(__name__, '../../extern/ion-definitions/res/config/logging.local.yml')
        except IOError, e:
            if e.errno == errno.ENOENT:
                local_log_config = None
            else:
                raise e

        self.config = Config(content = [system_log_config, local_log_config]).as_dict()

        # Save and initialize the logger
        self.initialize_logging()

    def initialize_logging(self):
        """Update the logging singleton with the new config dict"""

        # Ensure the logging directories exist
        for handler in self.config.get('handlers', {}).itervalues():
            if 'filename' in handler:
                log_dir = os.path.dirname(handler['filename'])
                if not os.path.exists(log_dir):
                    os.makedirs(log_dir)

        # if there's no logging config, we can't configure it: the call requires version at a minimum
        if self.config:
            logging.config.dictConfig(self.config)

    def set_log_file(self, filename):
        """Change the log file for all handlers"""
        for handler in self.config.get('handlers', {}).itervalues():
            if 'filename' in handler:
                handler['filename'] = filename
        self.initialize_logging()

    def set_log_level(self, level):
        """Change the log level for the MI logger"""

        # Do we need to update this to change all log levels?
        self.config['loggers']['mi']['level'] = level
        #for logger in self.config.get('loggers', {}).itervalues():
        #    if 'level' in logger:
        #        logger['level'] = level
        self.initialize_logging()

class LoggerManager(Singleton):
    """
    Logger Manager.  Provides an interface to configure logging at runtime.
    """
    def init(self):
        """Initialize logging for MI.  Because this is a singleton it will only be initialized once."""
        self.config = LoggerConfig()

    def set_log_level(self, level):
        """Change the current log level"""
        self.config.set_log_level(level)

    def set_log_file(self, filename):
        """Change the current log file"""
        self.config.set_log_file(filename)


# Create a singleton for the log manager.  This way the log configuration files are only ready once.
log_manager = LoggerManager()


####
##   The code below is pretty much a copy and paste from pyon.util.log.  While I generally would not copy and paste code
##   it was required in this case because a driver can't have and CI dependencies outside of the MI repository
####

# List of module names that will pass-through for the magic import scoping. This can be modified.
import_paths = [__name__]

def get_logger(loggername=__name__):
    """
    Creates an instance of a logger.
    Adds any registered handlers with this factory.

    Note: as this method is called typically on module load, if you haven't
    registered a handler at this time, that instance of a logger will not
    have that handler.
    """
    logger = logging.getLogger(loggername)

    return logger

# Special placeholder object, to be swapped out for each module that imports this one
log = None

def get_scoped_log(framestoskip=1):
    frame = sys._getframe(framestoskip)
    name = frame.f_locals.get('__name__', None)

    while name in import_paths and frame.f_back:
        frame = frame.f_back
        name = frame.f_locals.get('__name__', None)

    log = get_logger(name) if name else None
    return log

_orig___import__ = __import__
def _import(name, globals=None, locals=None, fromlist=None, level=-1):
    """
    Magic import mechanism  to get a logger that's auto-scoped to the importing module. Example:
    from pyon.public import scoped_log as log

    Inspects the stack; should be harmless since this is just syntactic sugar for module declarations.
    """
    kwargs = dict()
    if globals:
        kwargs['globals'] = globals
    if locals:
        kwargs['locals'] = locals
    if fromlist:
        kwargs['fromlist'] = fromlist
    kwargs['level'] = level
    module = _orig___import__(name, **kwargs)
    if name in import_paths and ('log' in fromlist or '*' in fromlist):
        log = get_scoped_log(2)
        setattr(module, 'log', log)

    return module
__builtin__.__import__ = _import

# Workaround a quirk in python 2.7 with custom imports
from logging.config import BaseConfigurator
BaseConfigurator.importer = staticmethod(_import)

log = get_scoped_log()

