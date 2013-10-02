#!/usr/bin/env python

"""
@package mi.core.sequencer
@file mi/core/sequencer.py
@author Bill French
@brief Object to track current record sequence information for publishing

Generate and store unique sequence identifiers then store the current
record number.
"""

__author__ = 'Bill French'
__license__ = 'Apache 2.0'

from mi.core.log import get_logger ; log = get_logger()

import uuid

class Sequencer(object):
    """
    Object to store sequence ids and indexes
    """
    _sequence_id = None
    _last_sequence_index = None

    def __init__(self):
        self.reset_sequence_id()

    def reset_sequence_id(self):
        """
        Reset the sequence id and next record index
        """
        self._sequence_id = str(uuid.uuid4()).upper()
        self.reset_sequence_index()

    def reset_sequence_index(self):
        """
        Reset the sequence index
        """
        self._last_sequence_index = None

    def get_sequence_id(self):
        """
        Return the current sequence ID
        """
        return self._sequence_id

    def increment_sequence_index(self):
        """
        Increment the sequence index and return the value
        """
        if self._last_sequence_index is None:
            self._last_sequence_index = 0
        else:
            self._last_sequence_index += 1

        return self.get_last_sequence_index()

    def get_last_sequence_index(self):
        return self._last_sequence_index


