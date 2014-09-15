#!/usr/bin/env python

"""
@package mi.dataset.test.test_parser Base dataset parser test code
@file mi/dataset/test/test_driver.py
@author Steve Foley
@brief Test code for the dataset parser base classes and common structures for
testing parsers.
"""
from mi.core.unit_test import MiUnitTestCase, MiIntTestCase

DATA_KEY = 'data'


# Make some stubs if we need to share among parser test suites
class ParserUnitTestCase(MiUnitTestCase):

    def assert_particle_yaml(self, expected_results, particle_data_list,
                             specific_index=None, expected_results_offset=0):
        """
        This method verifies expected results contained within a YAML file against
        actual particle data in a list.  It uses unit test assert calls to verify
        particle data.  The first assert failure will exit this method.
        @param expected_results Either a path to a YAML file containing the expected
        particle data, or a list of data particle objects
        @param particle_data_list A list of DataParticle objects containing the
        actual particle data
        @param specific_index The index of the list item to compare against.
        If None, all samples in particle_data_list will be compared.
        @param expected_results_offset An offset into the expected results data list
        loaded from the YAML file, defaults to 0.
        """
        if isinstance(expected_results, list):
            # expected results are already a list of particle data objects
            expected_particle_data = expected_results
        else:
            # if not a list, expected results should be a path to a yml file
            self.assertTrue(os.path.exists(results_yml_file))
            yml_data = self.get_dict_from_yml(results_yml_file)
            expected_particle_data = yml_data[DATA_KEY]

        for i in range(len(particle_data_list)):
            if specific_index is None or i==specific_index:
                self.assert_result(expected_particle_data[i + expected_results_offset]),
                                   particle_data_list[i])

    def assert_result(self, expected_particle_dict, received_particle):
        """
        This method verifies actual particle data against expected particle data.
        This method will use unittest assert calls to verify particle data.
        @param expected_particle_dict A dictionary containing the expected data particle
        @param received_particle The received DataParticle object
        """

        received_dict = received_particle.generate_dict()

        # for efficiency turn the particle values list of dictionaries into a dictionary
        received_values = {}
        for param in received_dict.get(DataParticleKey.VALUES):
            recieved_values[param[DataParticleKey.VALUE_ID]] = param[DataParticleKey.VALUE]

        # still in progress here
        # compare key groups to confirm the particle keys are the same
        #diff_keys = set(expected_particle_dict.keys()).intersection(received_dict.keys())
        #if diff_keys != []:
            
