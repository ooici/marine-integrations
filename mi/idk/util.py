"""
@file mi/idk/util.py
@author Bill French
@brief Utility functions for the IDK
"""

import shlex
import subprocess

from mi.idk.config import Config
from mi.core.log import get_logger ; log = get_logger()

def convert_enum_to_dict(obj):
    """
    @author Roger Unwin
    @brief  converts an enum to a dict
    """
    dic = {}
    for i in [v for v in dir(obj) if not callable(getattr(obj,v))]:
        if False == i.startswith('_'):
            dic[i] = getattr(obj, i)
    log.debug("enum dictionary = " + repr(dic))
    return dic


def launch_data_monitor(filename, launch_options = ''):
    """
    @brief launch a terminal tailing a file
    """
    cfg = Config()
    xterm = cfg.get("xterm")
    tail = cfg.get("tail")

    cmd = "%s %s -e %s -f %s" % (xterm, launch_options, tail, filename)
    args = shlex.split(cmd)
    process = subprocess.Popen(args)

    log.debug("run cmd: %s" % cmd)
    return process

def get_dict_value(dictobj, keys, default=None):
    """
    search dict for defined value. use an array to define keys to search for and
    first defined is returned.
    @param dictobj dict object to search
    @param key string or array with keys to search for
    @param default if no match return this
    @return found value or default
    """
    if not isinstance(dictobj, dict):
        raise TypeError("dictobj must be a dict")

    if not isinstance(keys, list):
        keys = [keys]

    for k in keys:
        if dictobj.has_key(k):
            return dictobj[k]

    return default

