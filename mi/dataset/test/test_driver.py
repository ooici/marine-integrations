#!/usr/bin/env python

"""
@package mi.dataset.test.test_driver Base dataset driver test code
@file mi/dataset/test/test_driver.py
@author Steve Foley
@brief Test code for the dataset driver base classes
"""

from nose.plugins.attrib import attr

from mi.core.unit_test import MiUnitTestCase
from mi.core.exceptions import DataSourceLocationException
from mi.dataset.dataset_driver import DataSourceLocation

@attr('UNIT', group='mi')
class DataSourceLocationUnitTestCase(MiUnitTestCase):
    """
    Test the DataSourceLocation structure
    """
    
    def test_create_and_update(self):
        """
        Test the creation and update of a DataSourceLocation object
        """
        harvester_pos1 = "filename_1.dat"
        harvester_pos2 = "filename_2.dat"
        parser_pos1 = 123
        parser_pos2 = 456
        
        dsl = DataSourceLocation()
        self.assertEqual(dsl.harvester_position, None)
        self.assertEqual(dsl.parser_position, None)
        dsl.update(harvester_position=harvester_pos1,
                   parser_position=parser_pos1)
        self.assertEqual(dsl.harvester_position, harvester_pos1)
        self.assertEqual(dsl.parser_position, parser_pos1)
        with self.assertRaises(DataSourceLocationException):
            dsl.update()
        dsl.update(parser_position=parser_pos2)
        self.assertEqual(dsl.harvester_position, harvester_pos1)
        self.assertEqual(dsl.parser_position, parser_pos2)
        with self.assertRaises(DataSourceLocationException):
            dsl.update(harvester_position=harvester_pos2)

        dsl = DataSourceLocation(harvester_position=harvester_pos1,
                                 parser_position=parser_pos1)
        self.assertEqual(dsl.harvester_position, harvester_pos1)
        self.assertEqual(dsl.parser_position, parser_pos1)
        
        dsl = DataSourceLocation(harvester_position=harvester_pos1)
        self.assertEqual(dsl.harvester_position, harvester_pos1)
        self.assertEqual(dsl.parser_position, None)
        
        dsl = DataSourceLocation(parser_position=parser_pos1)
        self.assertEqual(dsl.harvester_position, None)
        self.assertEqual(dsl.parser_position, parser_pos1)
        
        
                