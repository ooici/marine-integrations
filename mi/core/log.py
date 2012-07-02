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
import traceback

from mi.core.common import Singleton
from mi.core.common import Config


class LoggerConfig(object):
    """
    Logger configuration:
    - Use a primary file and then apply local overrides
    - Primary file is either $WORKING_DIR/res/config/mi-logging.yml,
      or if not found, $MI_INSTALL_DIR/config/logging.yml
      (this allows MI to provide a default, but local installation to override)
    - Local override will be either an MI-specific $WORKING_DIR/res/config/mi-logging.local.yml,
      or if not found, $WORKING_DIR/res/config/logging.local.yml
      (this allows one local config file to apply to both drivers and capability container,
       but separate overrides can be created by using two files if needed).
    """
    def __init__(self):
        primary_config = self.read_file('mi-logging.yml') or self.read_resource('config/logging.yml')
        local_override = self.read_file('mi-logging.local.yml') or self.read_file('logging.local.yml')
        self.config = Config(content = [primary_config, local_override]).as_dict()
        self.init_logging()

    def read_resource(self, resource_name):
        try:
            return resource_string(__name__, resource_name)
        except IOError, e:
            if e.errno != errno.ENOENT:
                print 'WARNING: error reading logging configuration resource ' + resource_name + ': ' + str(e)
        return None

    def read_file(self, filename):
        try:
            with open('res/config/' + filename, 'r') as infile:
                return infile.read()
        except IOError, e:
            if e.errno != errno.ENOENT:
                print 'WARNING: error reading logging configuration file ' + filename + ': ' + str(e)
        return None

    def init_logging(self):
        """Update the logging singleton with the new config dict"""
        # if there's no logging config, we can't configure it: the call requires version at a minimum
        if self.config:
            # Ensure the logging directories exist
            for handler in self.config.get('handlers', {}).itervalues():
                if 'filename' in handler:
                    log_dir = os.path.dirname(handler['filename'])
                    if not os.path.exists(log_dir):
                        os.makedirs(log_dir)

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

def remove_syspath(file):
    shortest = file
    for egg in sys.path:
        if file.startswith(egg):
            shorter = file[len(egg):]
            if len(shorter)<len(shortest):
                shortest = shorter
    while shortest.startswith('/'):
        shortest = shortest[1:]
    return shortest

_log = logging.getLogger(__name__)

def get_logger():
    for f in traceback.extract_stack(limit=4):
        file = f[0]
        module = remove_syspath(file).replace('/','.')
        if module.endswith('.py'):
            module = module[:-3]
        # first entry in stack that isn't a logging module should be the caller
        if not (module.endswith(__name__) or module=='pyon.util.log'):
            return logging.getLogger(module)

    # failed to create scoped logger -- use default instead
    _log.warn('using default logger ' + __name__ + ', could not identify caller from stack:\n' + '\n'.join([ '%s:%d\t%s'%(f[0],f[1],f[3]) for f in traceback.extract_stack() ]))
    return _log


