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
from mi.core.instrument.test.test_strings import TestUnitStringsDict 
from mi.core.exceptions import InstrumentParameterException
from mi.core.instrument.protocol_cmd_dict import ProtocolCommandDict
from mi.core.instrument.protocol_cmd_dict import CommandDictType
from mi.core.instrument.protocol_cmd_dict import CommandDictKey
from mi.core.instrument.protocol_cmd_dict import Command
from mi.core.instrument.protocol_cmd_dict import CommandArgument

from mi.core.log import get_logger ; log = get_logger()


@attr('UNIT', group='mi')
class TestUnitProtocolCommandDict(TestUnitStringsDict):
    """
    Test cases for instrument driver class. Functions in this class provide
    instrument driver unit tests and provide a tutorial on use of
    the driver interface.
    """
    
    __test__ = True
    
    def setUp(self):
        #self.param_dict = None
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
        self.param_dict = self.cmd_dict # link for ease of parent class operation
        
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

        self.test_yaml = '''
        parameters: {
          dummy: stuff
          }
          
        commands: {
         cmd1: {
            arguments: {
                coeff: {
                    description: "Cmd1Coeff", 
                    display_name: "C1co", 
                    value: {
                        description: "C1coDesc",
                        units: "counts",
                        type: "float"
                    }
                },
            },
            description: "C1Desc", 
            display_name: "C1", 
            return: {
                description: "C1Ret", 
                type: "C1RetType", 
                units: "C1RetUnit"
            }, 
         },
         cmd2: {
            arguments: {
                trigger: {
                    description: "C2TriggerDesc", 
                    display_name: "C2TriggerDisp",  
                    value: {
                        description: "C2TriggerValueDesc", 
                        type: "C2TriggerType",
                        units: "C2Units"
                    }
                },
                test: {
                    description: "C2TestDesc",
                    display_name: "C2TestDisp",  
                    value: {
                        description: "C2TestValueDesc", 
                        type: "C2TestType",
                        units: "C2TestUnits"
                    }
                },                    
            }, 
            description: "C2Desc", 
            display_name: "C2Disp", 
            return: {
                description: "C2RetDesc", 
                type: "C2RetType", 
                units: "C2RetUnits"
            }, 
         }
        }
        
        driver: {
          dummy: stuff
          }
        '''


        
    def test_sub_schema_generation(self):
        result_dict = self.cmd2_arg1.generate_dict()
        self.assertEqual(json.dumps(result_dict, indent=4, sort_keys=True),
                         self.target_arg_schema)            
        result_dict = self.cmd2.generate_dict() 
        self.assertEqual(json.dumps(result_dict, indent=4, sort_keys=True),
                         self.target_cmd_schema)            
                                
        
    def test_schema_dict_generation(self):
        """
        Tests that a dict is created that can then be JSONified
        """
        result = self.cmd_dict.generate_dict()
        json_result = json.dumps(result, indent=4, sort_keys=True)
        self.assertEqual(json_result, self.target_schema)
        
    def test_empty_schema(self):
        self.cmd_dict = ProtocolCommandDict()
        result = self.cmd_dict.generate_dict()
        self.assertEqual(result, {})

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

    def _assert_metadata_change(self):
        new_dict = self.param_dict.generate_dict()
        log.debug("Generated dictionary: %s", new_dict)
        self.assertEqual(new_dict["cmd1"][CommandDictKey.DESCRIPTION], "C1Desc")
        self.assertEqual(new_dict["cmd1"][CommandDictKey.DISPLAY_NAME], "C1")        
        self.assertEqual(new_dict["cmd1"][CommandDictKey.ARGUMENTS]['coeff'][CommandDictKey.DESCRIPTION], "Cmd1Coeff")
        self.assertEqual(new_dict["cmd1"][CommandDictKey.ARGUMENTS]['coeff'][CommandDictKey.DISPLAY_NAME], "C1co")
        self.assertEqual(new_dict["cmd1"][CommandDictKey.ARGUMENTS]['coeff'][CommandDictKey.VALUE][CommandDictKey.UNITS], "counts")
        self.assertEqual(new_dict["cmd1"][CommandDictKey.ARGUMENTS]['coeff'][CommandDictKey.VALUE][CommandDictKey.DESCRIPTION], "C1coDesc")
        self.assertEqual(new_dict["cmd1"][CommandDictKey.ARGUMENTS]['coeff'][CommandDictKey.VALUE][CommandDictKey.TYPE], "float")
        # Should come from hard code
        self.assertEqual(new_dict["cmd1"][CommandDictKey.ARGUMENTS]['delay'][CommandDictKey.DESCRIPTION], "The delay time to wait before executing")
        self.assertEqual(new_dict["cmd1"][CommandDictKey.ARGUMENTS]['delay'][CommandDictKey.DISPLAY_NAME], "delay time")
        self.assertEqual(new_dict["cmd1"][CommandDictKey.ARGUMENTS]['delay'][CommandDictKey.VALUE][CommandDictKey.UNITS], "seconds")
        self.assertEqual(new_dict["cmd1"][CommandDictKey.ARGUMENTS]['delay'][CommandDictKey.VALUE][CommandDictKey.DESCRIPTION], "Should be between 1.0 and 3.3 in increments of 0.1")
        self.assertEqual(new_dict["cmd1"][CommandDictKey.ARGUMENTS]['delay'][CommandDictKey.VALUE][CommandDictKey.TYPE], "float")
        # Command 1 return values
        self.assertEqual(new_dict["cmd1"][CommandDictKey.RETURN][CommandDictKey.DESCRIPTION], "C1Ret")
        self.assertEqual(new_dict["cmd1"][CommandDictKey.RETURN][CommandDictKey.UNITS], "C1RetUnit")
        self.assertEqual(new_dict["cmd1"][CommandDictKey.RETURN][CommandDictKey.TYPE], "C1RetType")

        self.assertEqual(new_dict["cmd2"][CommandDictKey.DESCRIPTION], "C2Desc")
        self.assertEqual(new_dict["cmd2"][CommandDictKey.DISPLAY_NAME], "C2Disp")        
        self.assertEqual(new_dict["cmd2"][CommandDictKey.ARGUMENTS]['trigger'][CommandDictKey.DESCRIPTION], "C2TriggerDesc")
        self.assertEqual(new_dict["cmd2"][CommandDictKey.ARGUMENTS]['trigger'][CommandDictKey.DISPLAY_NAME], "C2TriggerDisp")
        self.assertEqual(new_dict["cmd2"][CommandDictKey.ARGUMENTS]['trigger'][CommandDictKey.VALUE][CommandDictKey.DESCRIPTION], "C2TriggerValueDesc")
        self.assertEqual(new_dict["cmd2"][CommandDictKey.ARGUMENTS]['trigger'][CommandDictKey.VALUE][CommandDictKey.TYPE], "C2TriggerType")
        self.assertEqual(new_dict["cmd2"][CommandDictKey.ARGUMENTS]['trigger'][CommandDictKey.VALUE][CommandDictKey.UNITS], "C2Units")
        # Should come from hard code
        # Command 2 return values
        self.assertEqual(new_dict["cmd2"][CommandDictKey.RETURN][CommandDictKey.DESCRIPTION], "C2RetDesc")
        self.assertEqual(new_dict["cmd2"][CommandDictKey.RETURN][CommandDictKey.UNITS], "C2RetUnits")
        self.assertEqual(new_dict["cmd2"][CommandDictKey.RETURN][CommandDictKey.TYPE], "C2RetType")
        # shouldnt be any extra arguments, either
        self.assertFalse('test' in new_dict["cmd2"][CommandDictKey.ARGUMENTS])
