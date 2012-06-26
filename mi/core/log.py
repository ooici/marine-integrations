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

from mi.core.log import log, log_manager

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
import os
import sys
import errno
import logging
import logging.config
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
        try:
            system_log_config = resource_string(__name__, '../../res/config/logging.yml')
            pass
        except IOError, e:
            if e.errno == errno.ENOENT:
                system_log_config = None
            else:
                raise e
        '''
        try:
            if not system_log_config:
                system_log_config = self.read_file('res/config/logging.yml')
        except IOError, e:
            if e.errno == errno.ENOENT:
                system_log_config = None
            else:
                raise e
        '''
        try:
            local_log_config = resource_string(__name__, '../../res/config/logging.local.yml')
        except IOError, e:
            if e.errno == errno.ENOENT:
                local_log_config = None
            else:
                raise e
        '''
        try:
            if not local_log_config:
                local_log_config = self.read_file('res/config/logging.local.yml')
        except IOError, e:
            if e.errno == errno.ENOENT:
                local_log_config = None
            else:
                raise e
        '''

        self.config = Config(content = [system_log_config, local_log_config]).as_dict()

        # Save and initialize the logger
        self.init_logging()

    def read_file(self, filename):
        content = None
        try:
            infile = open(filename, 'r')
            content = infile.read()
        except IOError, e:
            if e.errno == errno.ENOENT:
                pass
            else:
                raise e

        return content

    def init_logging(self):
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
        self.init_logging()

    def set_log_level(self, level):
        """Change the log level for the MI logger"""

        # Do we need to update this to change all log levels?
        self.config['loggers']['mi']['level'] = level
        #for logger in self.config.get('loggers', {}).itervalues():
        #    if 'level' in logger:
        #        logger['level'] = level
        self.init_logging()

class LoggerManager(Singleton):
    """
    Logger Manager.  Provides an interface to configure logging at runtime.
    """
    def init(self):
        """Initialize logging for MI.  Because this is a singleton it will only be initialized once."""
        self.log_config = LoggerConfig()

    def set_log_level(self, level):
        """Change the current log level"""
        self.log_config.set_log_level(level)

    def set_log_file(self, filename):
        """Change the current log file"""
        self.log_config.set_log_file(filename)


# Create a singleton for the log manager.  This way the log configuration files are only ready once.
log_manager = LoggerManager()

# TODO: Update to use scoped logger like used in pyon.util.log.  When the code was here it caused problems when
# pyon.util.log and mi.core.log were both imported.  So for now we will defer to a non-scoped log
log = logging.getLogger('mi.core.log')

