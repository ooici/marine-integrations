"""
MI logging can be configured using a combination of two of four files.
there is first a "base" configuration, and then a "local" set of overrides.

the base configuration is from the file specified in the environment variable MI_LOGGING_CONFIG
or res/config/mi-logging.yml (ie, users can set MI-specific configuration for drivers run from pycc container)
or config/logging.yml from within the MI egg (default to use if no mi-logging.yml was created)

then the local override may be res/config/mi-logging.local.yml (for overrides specific to MI),
or if this is not found, then res/config/logging.local.yml,
or if this is not found then no overrides.

The get_logger function is obsolete but kept to simplify transition to the ooi.logging code.

USAGE:
to configure logging from the standard MI configuration files:

    from mi.core.log import LoggerManager
    LoggerManager()

to create a logger automatically scoped with the calling package and ready to use:

    from ooi.logging import log    # no longer need get_logger at all

"""
import inspect
import logging
import os
import sys
import yaml
import pkg_resources
from types import FunctionType
from functools import wraps

from mi.core.common import Singleton
from ooi.logging import config, log

LOGGING_CONFIG_ENVIRONMENT_VARIABLE="MI_LOGGING_CONFIG"

LOGGING_PRIMARY_FROM_FILE='res/config/mi-logging.yml'
LOGGING_PRIMARY_FROM_EGG='mi-logging.yml'
LOGGING_MI_OVERRIDE='res/config/mi-logging.local.yml'
LOGGING_CONTAINER_OVERRIDE='res/config/logging.local.yml'


class LoggerManager(Singleton):
    """
    Logger Manager.  Provides an interface to configure logging at runtime.
    """
    def init(self, debug=False):
        """Initialize logging for MI.  Because this is a singleton it will only be initialized once."""
        path = os.environ[LOGGING_CONFIG_ENVIRONMENT_VARIABLE] if LOGGING_CONFIG_ENVIRONMENT_VARIABLE in os.environ else None
        haveenv = path and os.path.isfile(path)
        if path and not haveenv:
            print >> os.stderr, 'WARNING: %s was set but %s was not found (using default configuration files instead)' % (LOGGING_CONFIG_ENVIRONMENT_VARIABLE, path)
        if path and haveenv:
            config.replace_configuration(path)
            if debug:
                print >> sys.stderr, str(os.getpid()) + ' configured logging from ' + path
        elif os.path.isfile(LOGGING_PRIMARY_FROM_FILE):
            config.replace_configuration(LOGGING_PRIMARY_FROM_FILE)
            if debug:
                print >> sys.stderr, str(os.getpid()) + ' configured logging from ' + LOGGING_PRIMARY_FROM_FILE
        else:
            logconfig = pkg_resources.resource_string('mi', LOGGING_PRIMARY_FROM_EGG)
            parsed = yaml.load(logconfig)
            config.replace_configuration(parsed)
            if debug:
                print >> sys.stderr, str(os.getpid()) + ' configured logging from config/' + LOGGING_PRIMARY_FROM_FILE

        if os.path.isfile(LOGGING_MI_OVERRIDE):
            config.add_configuration(LOGGING_MI_OVERRIDE)
            if debug:
                print >> sys.stderr, str(os.getpid()) + ' supplemented logging from ' + LOGGING_MI_OVERRIDE
        elif os.path.isfile(LOGGING_CONTAINER_OVERRIDE):
            config.add_configuration(LOGGING_CONTAINER_OVERRIDE)
            if debug:
                print >> sys.stderr, str(os.getpid()) + ' supplemented logging from ' + LOGGING_CONTAINER_OVERRIDE


def get_logging_metaclass(log_level='trace'):
    class LoggingMetaClass(type):
        def __new__(mcs, class_name, bases, class_dict):
            wrapper = log_method(class_name=class_name, log_level=log_level)
            new_class_dict = {}
            for attributeName, attribute in class_dict.items():
                if type(attribute) == FunctionType:
                    attribute = wrapper(attribute)
                new_class_dict[attributeName] = attribute
            return type.__new__(mcs, class_name, bases, new_class_dict)
    return LoggingMetaClass


def log_method(class_name=None, log_level='trace'):
    name = "UNKNOWN_MODULE_NAME"
    stack = inspect.stack()
    # step through the stack until we leave mi.core.log
    for frame in stack:
        module = inspect.getmodule(frame[0])
        if module:
            name = module.__name__
            if name != 'mi.core.log':
                break
    logger = logging.getLogger(name)

    def wrapper(func):
        if class_name is not None:
            func_name = '%s.%s' % (class_name, func.__name__)
        else:
            func_name = func.__name__

        @wraps(func)
        def inner(*args, **kwargs):
            getattr(logger, log_level)('entered %s | args: %r | kwargs: %r', func_name, args, kwargs)
            r = func(*args, **kwargs)
            getattr(logger, log_level)('exiting %s | returning %r', func_name, r)
            return r
        return inner

    return wrapper


def get_logger():
    return log
