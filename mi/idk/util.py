"""
@file mi/idk/util.py
@author Bill French
@brief Utility functions for the IDK
"""

import shlex
import subprocess

from mi.idk.config import Config
from mi.core.log import get_logger ; log = get_logger()

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

