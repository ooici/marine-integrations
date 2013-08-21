#!/usr/bin/env python

"""
@package mi.dataset.drivers.hypm SBE54 data set agent information
@file mi/dataset/drivers/hypm.py
@author Steve Foley
@brief An HYPM mooring specific data set agent package
"""

__author__ = 'Steve Foley'
__license__ = 'Apache 2.0'

from mi.core.log import get_logger ; log = get_logger()

from mi.dataset.parser.sbe54 import SBE54Parser
from mi.dataset.harvester import AdditiveSequentialFileHarvester
from mi.dataset.driver import DatasetDriver

"""
This should work with a stock TwoDelegateDatasetAgent DSA and a config that
is something like:

{
 'poller':{'module':'mi.dataset',
           'class':'AdditiveSequentialFilePoller',
           'uri':'egg-name?',
           'directory':'/foo/datafiles',
           'pattern':'*.dat',
           'frequency':60}
          },

 'parser':{'module':'mi.dataset.agents.sbe54',
           'class':'SBE54Parser',
           'uri':'egg-name?',
          }
}
"""

class HypmSppCtdDatasetDriver(DatasetDriver):
    """
    The HypmSppCtdDatasetDriver class handles a single data harvester and a
    single parser to get data from the CTD (an SBE54 unit) from the HYPM's
    SPP node.
    """
    def __init__(self, *args, **kwargs):
        super(HypmSppCtdDatasetDriver, self).__init__(*args, **kwargs)
        self.parsers.add(SBE54Parser())
        self.harvesters.add(AdditiveSequentialFileHarvester())
        
    # Setup some callbacks and error backs?
    