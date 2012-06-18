#!/usr/bin/env python

"""
@file coi-services/mi.idk/config.py
@author Bill French
@brief Configuration object for the IDK.  It reads values from
and IDK yaml file and can write the user configuration to a file.

ConfigManager is the main configuration object and Config provides
a mechanism to access the CM singleton.

Usage:

from mi.core.log import log

Config().rebase()
repo = Config().working_repo()

"""

__author__ = 'Bill French'
__license__ = 'Apache 2.0'

import os
import sys
import yaml

import mi.core.common 

from mi.idk.exceptions import IDKWrongRunningDirectory
from mi.idk.exceptions import WorkingRepoNotSet

from mi.core.log import log
from mi.idk.common import Singleton

####
#    Config defaults.  These are hard coded because they shouldn't
#    be overrided
####
PATH = os.path.join(os.path.expanduser("~"), ".idk")
CONFIG_FILENAME = "idk.yml"

DEFAULT_CONFIG = "extern/ion-definitions/res/config/idk.yml"
IDK_YAML_GROUP = "idk"
YAML_CONFIG_WORKING_REPO = "working_repo"
YAML_CONFIG_TEMPLATE_DIR = "template_dir"

MI_REPO_NAME = "marine-integrations"

class ConfigManager(Singleton):
    """
    Config Manager.
    Creates a config file if it doesn't already exist.
    """
    def init(self, config_dir = PATH):
        self.yaml = dict()
        self.yaml[IDK_YAML_GROUP] = dict()

        log.debug("config dir: %s" % config_dir)
        self.config_dir = config_dir

        if not os.path.isdir(config_dir):
            try:
                os.mkdir(config_dir) # create dir if it doesn't exist
            except:
                raise IOError("Couldn't create \"" + config_dir + "\" folder. Check" \
                              " permissions")

        ## Initialize the config file if one doesn't exist
        cfgpath = os.path.join(config_dir, CONFIG_FILENAME)
        log.debug("config file: %s" % cfgpath)

        if not os.path.exists(cfgpath):
            log.debug("User IDK config doesn't exist: " + cfgpath)
            self.rebase()
            
        ## Read the user config file once to get the working repo dir, then again with the default and user config
        self.read_config([cfgpath])

        if not self.get("working_repo"):
            log.debug("working_repo config option doesn't exist: " + cfgpath)
            self.rebase()

        if not self.get("working_repo"):
            raise WorkingRepoNotSet()

        self.read_config([ os.path.join(self.get("working_repo"), DEFAULT_CONFIG),
                           cfgpath ])
        pass

    def read_config(self, config_list):
        config = mi.core.common.Config(config_list)
        self.yaml = config.as_dict()
        pass

    def rebase(self):
        """
        @brief determine if we are in the MI working git repo.  If so set the
               local yaml file with the path.  Note, this MUST be run from the
               root of the local git working directory.
        """
        log.debug("Rebase IDK working repository")
        idk_repo = os.getcwd();
        
        # We assume we are in the root of the local repository directory because
        # DEFAULT_CONFIG is a relative path from there
        log.debug("Check for GIT information in: " + os.curdir);
        # TODO add git check

        ### This would be nice to ultimately pull from the repo object, but the version of gitpython
        ### installed doesn't support remotes. 
        origin = idk_repo

        log.debug( "Does '%s' contain '%s'" % (origin, MI_REPO_NAME))
        if origin.find(MI_REPO_NAME) < 0:
            raise IDKWrongRunningDirectory(msg="Please run this process from the root your local MI git repository")
        
        self.set(YAML_CONFIG_WORKING_REPO, idk_repo)
           
    
    def write(self):
        """
        @brief write the current yaml config to the user 
        """
        cfgpath = os.path.join(self.config_dir, CONFIG_FILENAME)
        ofile = open(cfgpath, 'w')
        if ofile:
            log.debug( "Write config: %s" % cfgpath )
            cfg = yaml.dump(self.yaml, default_flow_style=False)
            log.debug( "Config:\n%s" % cfg)
            ofile.write(cfg)
            ofile.close()
        
    def set(self, name, path):
        """
        @brief change a value in the yaml file
        """
        self.yaml[IDK_YAML_GROUP][name] = path
        self.write()
        
    def get(self, config_name):
        """
        @brief get a named parameter from the yaml file
        @retval value from the yaml file
        """
        if self.yaml and self.yaml.get(IDK_YAML_GROUP):
            return self.yaml[IDK_YAML_GROUP].get(config_name)
        else:
            return None


class Config(object):
    """
    Config object.
    """
    def __init__(self, config_dir = PATH):
        log.debug("cfg: %s" % config_dir)
        self.cm = ConfigManager(config_dir) # ConfigManager instance
        if not config_dir == self.cm.config_dir:
            self.cm.init(config_dir)

    def get(self, name):
        """
        @brief get a named parameter from the yaml file
        @retval value from the yaml file
        """
        return self.cm.get(name)
        
    ###
    #    IDK Configuration Compositions
    ###
    def base_dir(self):
        """
        @brief base directory for the new driver
        @retval dir name
        """
        return self.cm.get(YAML_CONFIG_WORKING_REPO)
        
    def idk_config_dir(self):
        """
        @brief base directory for the new driver
        @retval dir name
        """
        return self.cm.config_dir

    def template_dir(self):
        """
        @brief directory where code templates are stored
        @retval template dir name
        """
        return self.cm.get(YAML_CONFIG_TEMPLATE_DIR)
        
    def rebase(self):
        """
        @brief reset the working repository directory
        """
        self.cm.rebase()


