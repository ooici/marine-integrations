"""
MI logging can be configured using a combination of two of four files.
there is first a "base" configuration, and then a "local" set of overrides.

the base configuration is res/config/mi-logging.yml (ie, users can set MI-specific configuration for drivers run from pycc container)
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
import os.path
import pkg_resources

from mi.core.common import Singleton
from ooi.logging import config, log

LOGGING_PRIMARY_FROM_FILE='res/config/mi-logging.yml'
LOGGING_PRIMARY_FROM_EGG='logging.yml'
LOGGING_MI_OVERRIDE='res/config/mi-logging.local.yml'
LOGGING_CONTAINER_OVERRIDE='res/config/logging.local.yml'

class LoggerManager(Singleton):
    """
    Logger Manager.  Provides an interface to configure logging at runtime.
    """
    def init(self):
        """Initialize logging for MI.  Because this is a singleton it will only be initialized once."""
        if os.path.isfile(LOGGING_PRIMARY_FROM_FILE):
            config.replace_configuration(LOGGING_PRIMARY_FROM_FILE)
        else:
            path = pkg_resources.resource_filename('config', LOGGING_PRIMARY_FROM_EGG)
            config.replace_configuration(path)

        if os.path.isfile(LOGGING_MI_OVERRIDE):
            config.add_configuration(LOGGING_MI_OVERRIDE)
        elif os.path.isfile(LOGGING_CONTAINER_OVERRIDE):
            config.add_configuration(LOGGING_CONTAINER_OVERRIDE)

def get_logger():
    return log


