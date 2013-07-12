#!/usr/bin/env python

"""
@package mi.core.instrument.test.test_strings
@file mi/core/instrument/test/test_strings.py
@author Steve Foley
@brief Base class with some common test cases and support methods for the
parameter, command, and driver dictionary modules
"""

__author__ = 'Steve Foley'
__license__ = 'Apache 2.0'

from nose.plugins.attrib import attr
from mi.core.unit_test import MiUnitTestCase

from mi.core.log import get_logger ; log = get_logger()

@attr('UNIT', group='mi')
class TestUnitStringsDict(MiUnitTestCase):

    __test__ = False
    
    def test_metadata_load(self):
        """
        Test to make sure the metadata can be loaded from the default filename
        to both override current values and add new ones. Expects a
        driver_metadata.yml to look like:
        
        parameters: {
          dummy: stuff
          }
          
        commands: {
          cmd2: {
            arguments: {
              trigger: {
                description: "C2TriggerDesc", 
                display_name: "C2TriggerDisp",  
                value: {
                  description: "C2TriggerValueDesc", 
                  type: "C2TriggerType"
                }
            }
        }, 
        description: "C2Desc", 
        display_name: "C2Disp", 
        return: {
            description: "C2RetDesc", 
            type: "C2RetType", 
            units: "C2RetUnits"
           }, 
        }          }
          
        driver: {
          dummy: stuff
          }
        """
        # test bad file name        
        result = self.param_dict.load_strings(filename="bad_filename.yml")
        self.assertFalse(result) # defaulted to hardcoded strings

        # Write the yml out to a file for testing, then load it
        wfile = open("/tmp/test.yml", "w+")
        if wfile:
            log.debug("Printing dumping YAML string to file: %s", wfile)
            print  >>wfile, self.test_yaml
            wfile.close()
                
        # test good filename
        result = self.param_dict.load_strings(filename="/tmp/test.yml")
        self.assertTrue(result)
        self._assert_metadata_change()        
        
    def test_metadata_load_devel_path(self):
        # test bad paths
        result = self.param_dict.load_strings(devel_path="foo/resource/strings.yml")
        self.assertFalse(result)
        result = self.param_dict.load_strings(devel_path="../resource/strings.yml")
        self.assertFalse(result)
        result = self.param_dict.load_strings(devel_path="strings.yml")
        self.assertFalse(result)
        # test good path
        result = self.param_dict.load_strings(devel_path="resource/test_strings.yml")
        self.assertTrue(result)
        self._assert_metadata_change()

    def test_metadata_load_default(self):
        # if you dont have an argument, you only have a chance of looking in an egg
        result = self.param_dict.load_strings()
        self.assertFalse(result)


