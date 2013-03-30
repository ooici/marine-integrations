#!/usr/bin/env python

"""
@package mi.core.instrument.test.test_protocol_cmd_dict
@file mi/core/instrument/test/test_protocol_cmd_dict.py
@author Steve Foley
@brief Test cases for the base protocol command dictionary module
"""

__author__ = 'Steve Foley'
__license__ = 'Apache 2.0'

import json

from nose.plugins.attrib import attr
from mi.core.unit_test import MiUnitTestCase
from mi.core.exceptions import InstrumentParameterException
from mi.core.instrument.protocol_cmd_dict import ProtocolCommandDict
from mi.core.instrument.protocol_cmd_dict import CommandDictType
from mi.core.instrument.protocol_cmd_dict import Command
from mi.core.instrument.protocol_cmd_dict import CommandArgument

from mi.core.log import get_logger ; log = get_logger()


@attr('UNIT', group='mi')
class TestUnitProtocolCommandDict(MiUnitTestCase):

    """
    Test cases for instrument driver class. Functions in this class provide
    instrument driver unit tests and provide a tutorial on use of
    the driver interface.
    """ 
    def setUp(self):
        self.cmd_dict = ProtocolCommandDict()
                
        self.cmd_dict.add("cmd1",
                          timeout=60,
                          display_name="Command 1",
                          description="Execute a foo on the instrument",
                          return_type="bool",
                          return_units="Success",
                          return_description="Success (true) or failure (false)",
                          arguments=[CommandArgument(
                                     name="coeff",
                                     required=True,
                                     display_name="coefficient",
                                     description="The coefficient to use for calculation",
                                     type=CommandDictType.FLOAT,
                                     value_description="Should be between 1.97 and 2.34"
                                     ),
                                     CommandArgument(
                                     name="delay",
                                     required=False,
                                     display_name="delay time",
                                     description="The delay time to wait before executing",
                                     type=CommandDictType.FLOAT,
                                     units="seconds",
                                     value_description="Should be between 1.0 and 3.3 in increments of 0.1"
                                     )
                                    ]
                         )
        # different way of creating things, possibly more clear in some cases
        # and allows for testing arg and command later
        self.cmd2_arg1 = CommandArgument(name="trigger",
                                        required=True,
                                        display_name="sensor trigger",
                                        description="The trigger value to use for calculation",
                                        type=CommandDictType.INT,
                                        value_description="Should be between 1 and 20"
                                        )
        self.cmd2 = Command("cmd2",
                            display_name="Command 2",
                            description="The second test command",
                            return_type=CommandDictType.INT,
                            return_units="counts",
                            return_description="The number of items encountered during the run.",
                            arguments=[self.cmd2_arg1])
        self.cmd_dict.add_command(self.cmd2)
        
        self.target_arg_schema = """{
    "description": "The trigger value to use for calculation", 
    "display_name": "sensor trigger", 
    "required": true, 
    "value": {
        "description": "Should be between 1 and 20", 
        "type": "int"
    }
}"""

        self.target_cmd_schema = """{
    "arguments": {
        "trigger": {
            "description": "The trigger value to use for calculation", 
            "display_name": "sensor trigger", 
            "required": true, 
            "value": {
                "description": "Should be between 1 and 20", 
                "type": "int"
            }
        }
    }, 
    "description": "The second test command", 
    "display_name": "Command 2", 
    "return": {
        "description": "The number of items encountered during the run.", 
        "type": "int", 
        "units": "counts"
    }, 
    "timeout": 10
}"""

        self.target_schema = """{
    "cmd1": {
        "arguments": {
            "coeff": {
                "description": "The coefficient to use for calculation", 
                "display_name": "coefficient", 
                "required": true, 
                "value": {
                    "description": "Should be between 1.97 and 2.34", 
                    "type": "float"
                }
            }, 
            "delay": {
                "description": "The delay time to wait before executing", 
                "display_name": "delay time", 
                "required": false, 
                "value": {
                    "description": "Should be between 1.0 and 3.3 in increments of 0.1", 
                    "type": "float", 
                    "units": "seconds"
                }
            }
        }, 
        "description": "Execute a foo on the instrument", 
        "display_name": "Command 1", 
        "return": {
            "description": "Success (true) or failure (false)", 
            "type": "bool", 
            "units": "Success"
        }, 
        "timeout": 60
    }, 
    "cmd2": {
        "arguments": {
            "trigger": {
                "description": "The trigger value to use for calculation", 
                "display_name": "sensor trigger", 
                "required": true, 
                "value": {
                    "description": "Should be between 1 and 20", 
                    "type": "int"
                }
            }
        }, 
        "description": "The second test command", 
        "display_name": "Command 2", 
        "return": {
            "description": "The number of items encountered during the run.", 
            "type": "int", 
            "units": "counts"
        }, 
        "timeout": 10
    }
}"""
        
    def test_sub_schema_generation(self):
        result_dict = self.cmd2_arg1.generate_dict()
        self.assertEqual(json.dumps(result_dict, indent=4, sort_keys=True),
                         self.target_arg_schema)            
        result_dict = self.cmd2.generate_dict() 
        self.assertEqual(json.dumps(result_dict, indent=4, sort_keys=True),
                         self.target_cmd_schema)            
                                
        
    def test_schema_generation(self):
        result = self.cmd_dict.generate_schema()
        # Make sure we have a reasonable length, first
        self.assert_(len(result) > 100)
        self.assertEqual(result, self.target_schema)
        
    def test_argument_exceptions(self):
        self.assertRaises(InstrumentParameterException,
                          Command,
                            "foo", arguments="bad_arg")
        
        self.assertRaises(InstrumentParameterException,
                          Command,
                            "foo", arguments=["bad arg"])

    def test_add_get(self):
        good_cmd = Command(name="some_name")
        
        result = self.cmd_dict.get_command("some_name")
        self.assert_(not isinstance(result, Command))
        self.cmd_dict.add_command(good_cmd)
        result = self.cmd_dict.get_command("some_name")
        self.assert_(isinstance(result, Command))

        # exception cases
        bad_cmd = Command(name=1)
        self.assertRaises(InstrumentParameterException,
                          self.cmd_dict.add_command,
                            bad_cmd)
        
        self.assertRaises(InstrumentParameterException,
                          self.cmd_dict.add_command,
                            "bad_command")
        
        self.assertEqual(self.cmd_dict.get_command(None), None)
        self.assertEqual(self.cmd_dict.get_command("bad"), None)
