#! /usr/bin/env python

"""
@file coi-services/ion/idk/data_set_agent/unit_test.py
@author Bill French
@brief Base classes for data set agent tests.
"""

from mi.idk.unit_test import InstrumentDriverTestConfig
from mi.idk.unit_test import InstrumentDriverTestCase
from mi.idk.unit_test import InstrumentDriverUnitTestCase
from mi.idk.unit_test import InstrumentDriverIntegrationTestCase
from mi.idk.unit_test import InstrumentDriverQualificationTestCase

class DataSetDriverTestConfig(InstrumentDriverTestConfig):
    """
    Singleton driver test config object.
    """
    pass


class DataSetDriverUnitTestCase(InstrumentDriverUnitTestCase):
    """
    Base class for instrument driver unit tests
    """
    pass

class DataSetDriverIntegrationTestCase(InstrumentDriverIntegrationTestCase):
    """
    Base class for instrument driver unit tests
    """
    pass

class DataSetDriverQualificationTestCase(DataSetDriverQualificationTestCase):
    """
    Base class for instrument driver unit tests
    """
    pass


