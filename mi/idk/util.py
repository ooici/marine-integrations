"""
@file mi/idk/util.py
@author Bill French
@brief Utility functions for the IDK
"""

import os
import shlex
import shutil
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

def remove_all_files(dir_name):
    """
    Remove all files from a directory.  Raise an exception if the directory contains something
    other than files.
    @param dir_name directory path to remove files.
    @raise RuntimeError if the directory contains anything except files.
    """
    for file_name in os.listdir(dir_name):
        file_path = os.path.join(dir_name, file_name)
        if os.path.isdir(file_path):
            shutil.rmtree(file_path)
        else:
            os.unlink(file_path)

    if os.path.exists(dir_name):
        for file_name in os.listdir(dir_name):
            file_path = os.path.join(dir_name, file_name)
            os.unlink(file_path)
