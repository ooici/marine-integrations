#!/usr/bin/env python

"""
@author Bill French
@brief Setup logging for the drivers
"""

__author__ = 'Bill French'
__license__ = 'Apache 2.0'

import os
import sys
import logging

from mi.core.common import Singleton

DEFAULT_LOG_LEVEL  = logging.DEBUG
DEFAULT_LOG_FORMAT = '%(levelname)-10s %(module)-25s %(lineno)-4d %(process)-6d %(threadName)-15s - %(message)s'

class LoggerManager(Singleton):
    """
    Logger Manager.
    Handles all logging files.
    """
    def init(self):
        self.logger = logging.getLogger()
        handler = logging.StreamHandler()
        self.logger.setLevel(DEFAULT_LOG_LEVEL)
        formatter = logging.Formatter(DEFAULT_LOG_FORMAT)
        handler.setFormatter(formatter)
        self.logger.addHandler(handler)

    def debug(self, loggername, msg):
        self.logger = logging.getLogger(loggername)
        self.logger.debug(msg)

    def error(self, loggername, msg):
        self.logger = logging.getLogger(loggername)
        self.logger.error(msg)

    def warn(self, loggername, msg):
        self.logger = logging.getLogger(loggername)
        self.logger.warn(msg)

    def info(self, loggername, msg):
        self.logger = logging.getLogger(loggername)
        self.logger.info(msg)

    def warning(self, loggername, msg):
        self.logger = logging.getLogger(loggername)
        self.logger.warning(msg)

class Logger(object):
    """
    Logger object.
    """
    def __init__(self, loggername="root"):
        self.lm = LoggerManager() # LoggerManager instance
        self.loggername = loggername # logger name

    def debug(self, msg):
        self.lm.debug(self.loggername, msg)

    def warn(self, msg):
        self.lm.warn(self.loggername, msg)

    def error(self, msg):
        self.lm.error(self.loggername, msg)

    def info(self, msg):
        self.lm.info(self.loggername, msg)

    def warning(self, msg):
        self.lm.warning(self.loggername, msg)

Log = Logger()
