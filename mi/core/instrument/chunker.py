#!/usr/bin/env python

"""
@package mi.core.instrument.chunker Chunking buffer for MI work
@file mi/core/instrument/chunker.py
@author Steve Foley
@brief A buffer structure that allows for combining fragments and breaking
    apart multiple instances of the same data from an instrument's data stream.
"""

__author__ = 'Steve Foley'
__license__ = 'Apache 2.0'

from ooi.logging import log

class Chunker(object):
    """
    A great big buffer that ingests incoming data from an instrument, then
    sieves it out into different streams for recognized data segments and non
    data. In the process it aggregates data fragments into whole chunks and
    breaks apart collections of data segments so they can be broken into
    individual blocks.
    """
    def __init__(self, data_sieve_fn):
        """
        Initialize the buffer and indexing structures 
        The lists keep track of the start and stop index values (inclusive)
        of the particular type in the data buffer. The lists are tuples with
        (start, stop)
        
        @param data_sieve_fn A function that takes in a chunk of raw data (in
            whatever format is needed by the Chunker subclass) and spits out
            a list of (start_index, end_index) tuples. start_index is the
            array index of the first item in the data list, end_index is one more
            than the last item's index. This allows
            buffer[start_index:end_index] to properly describe the data block.
            If no data is present, return and empty list. If multiple data
            blocks are found, the returned list will contain multiple tuples,
            IN SEQUENTIAL ORDER and WITHOUT OVERLAP.
        """
        self.sieve = data_sieve_fn
        
        self.raw_chunk_list = []
        self.data_chunk_list = []
        self.nondata_chunk_list = []
        
        """ To be filled out by the subclass """
        self.buffer = None
        
    def add_chunk(self, raw_data):
        """
        Adds a chunk of data to the end of the buffer, includes the new indices
        in the raw_chunk_list. This base class method handles strings and lists.
        Improve or subclass for more capabilities.
        
        @param raw_data The bunch of raw data as a list (or something that can be
            treated as a list...like a string)
        """
        assert isinstance(self.buffer, str) or isinstance(self.buffer, list)
        # Append raw
        start_index = len(self.buffer)
        
        if self.data_chunk_list == []:
            last_data_index = 0
        else:
            last_data_index = self.data_chunk_list[-1][1] 
        end_index = start_index + len(raw_data)
        
        if isinstance(self.buffer, str):
            self.buffer += raw_data
        else:
            self.buffer.append(raw_data)
            
        self.raw_chunk_list.append((start_index, end_index))

        # find data
        result = self._generate_data_lists(start_index=last_data_index)
        assert result != None
        
        # rebase onto existing buffer
        for (s, e) in result['data_chunk_list']:
            self.data_chunk_list.append((s, e))
        
            # remove first fragment part from non-data array if we completed a fragment
            for (nds, nde) in self.nondata_chunk_list:
                if (nds == s):
                    self.nondata_chunk_list.remove((nds, nde))
        
        # splice non-data blocks in, combining with
        # other blocks as needed
        if result['non_data_chunk_list'] != []:
            new_nondata_list = []
            (first_new_s, first_new_e) = result['non_data_chunk_list'][0]
            
            if self.nondata_chunk_list == []:
                self.nondata_chunk_list = result['non_data_chunk_list']
                log.debug("Added chunk, data_chunk_list: %s, nondata_chunk_list: %s",
                      self.data_chunk_list, self.nondata_chunk_list)
                return
            for (s, e) in self.nondata_chunk_list:
                if e >= first_new_s:
                    new_nondata_list.append((s, first_new_e))
                    result['non_data_chunk_list'].pop(0) # already used it
                    break
                if e < first_new_s:
                    new_nondata_list.append((s, e))
            # all done, merging, so add the rest of what is left
            new_nondata_list.extend(result['non_data_chunk_list'])
            
            self.nondata_chunk_list = new_nondata_list
            log.debug("Added chunk, data_chunk_list: %s, nondata_chunk_list: %s",
                      self.data_chunk_list, self.nondata_chunk_list)
         
    def _generate_data_lists(self, start_index=0):
        """
        From some starting place in the raw data buffer, go through and
        find the blocks of data and non-data in the list.
        
        @param start_index The beginning index to start generating lists from.
            Default is the beginning of the buffer
        @retval A dict with keys "data_chunk_list" and "non_data_chunk_list"
            that include the full data chunk lists for this block of data.
            Indices are respect to the buffer, not the chunk
        """
        log.debug("Generating data lists with start index %s", start_index)
        return_list = {'data_chunk_list':[], 'non_data_chunk_list':[]}
        result = self.sieve(self.buffer[start_index:])

        # rebase to buffer coordinates
        return_list['data_chunk_list'] = [(s+start_index, e+start_index) for (s, e) in result]
        
        if result == []:
            return_list['non_data_chunk_list'].append((start_index,
                                                       len(self.buffer)))
        previous_end = start_index        
        for (s, e) in result:
            # rebase to buffer as long as we are walking through
            s += start_index
            e += start_index
            assert(s >= previous_end)
            if (s == previous_end):
                previous_end = e
            elif (s > previous_end):
                return_list['non_data_chunk_list'].append((previous_end, s))
                previous_end = e

        log.debug("Generated return list: %s", return_list)
        return return_list    
    
    def get_next_data(self, clean=True):
        """
        Get the next chunk of data from the buffer. By default, it clears all
        that comes before it.
        
        @param clean If set to false, do not clear the buffer when fetching the
            data, but simply return the data block and make no further changes.
        @return A chunk of data
        """
        if self.data_chunk_list == []:
            return None

        if clean:    
            (next_start, next_end) = self.data_chunk_list.pop(0)
        else:
            (next_start, next_end) = self.data_chunk_list[0]
        
        next_block = self.buffer[next_start:next_end]

        if clean:    
            self._clean_buffer(next_end)
            self.raw_chunk_list = self._clean_chunk_list(self.raw_chunk_list,
                                                         next_end)
            self.data_chunk_list = self._clean_chunk_list(self.data_chunk_list,
                                                         next_end)
            self.nondata_chunk_list = self._clean_chunk_list(self.nondata_chunk_list,
                                                             next_end)
                
        return next_block
    
    def _clean_chunk_list(self, list, end_index):
        """
        Cleans up the given chunk list based on the start and end indexes of
        that are being removed. The idea is to keep the given list of indices
        in sync with other lists that are having elements removed from them.
        For example, if the list looks like [(3, 5), (8, 12), (20, 25)]
        and the end index is 10, the resulting list will be:
        [(0, 2), (10, 15)] as items up to 10 have been removed (only [10:25] remain)
        and popped off the front so they are now [0:2] and [10:15].
        
        @param list A list of (start, end) tuples of indices that needs to be
            cleaned up.
        @param end_index The end index of what is being removed.
        @retval The new list after it has been cleaned
        """
        return_list = []
        for (s, e) in list:
            if s >= end_index:
                return_list.append((s-end_index, e-end_index))
            else:
                if e > end_index:
                    return_list.append((0,e-end_index))
        return return_list
    
    def _clean_data_list(self, index):
        """
        Clean up the data list in place so that it, if a fragment is consumed
        by a get_next_raw call, the data chunk is remove and added back to the
        non-data list.
        
        @param index The index that things are being cleared up to
        """
        new_nondata_list = []

        log.debug("Cleaning data chunk, data_chunk_list: %s, nondata_chunk_list: %s",
                  self.data_chunk_list, self.nondata_chunk_list)

        for (s, e) in self.data_chunk_list:
            if (e <= index):
                self.data_chunk_list.remove((s, e))
                
            if (e > index):
                self.data_chunk_list.remove((s, e))
                # add remaining to non data
                for (nds, nde) in self.nondata_chunk_list:
                    if (nde < s):
                        new_nondata_list.append((nds, nde))
                    elif (nde == s):
                        new_nondata_list.append((nds, e))
                    elif (nde > s):
                        new_nondata_list.append((nds, nde))
        
        self.nondata_chunk_list = new_nondata_list
    
    def _clean_buffer(self, end_index):
        """
        Clean up the buffer only...usually followed by some list cleaning
        @param end_index the last index used...clean up to here
        """
        # Clean up buffer
        if isinstance(self.buffer, str):
            self.buffer = self.buffer[end_index:]
        else:
            self.buffer[0:end_index] = []
        
    def get_next_non_data(self, clean=True):
        """
        Get the next chunk of non-data from the buffer, clearing all that comes
        before it. Default behavior is to clear the buffer before and including
        this data.
        
        @param clean Remove the buffer contents before and including this data
        @return A chunk of data, None if no data
        """
        if self.nondata_chunk_list == []:
            return None

        if clean:    
            (next_start, next_end) = self.nondata_chunk_list.pop(0)
        else:
            (next_start, next_end) = self.nondata_chunk_list[0]
        
        next_block = self.buffer[next_start:next_end]

        if clean:    
            self._clean_buffer(next_end)
            self.raw_chunk_list = self._clean_chunk_list(self.raw_chunk_list,
                                                         next_end)
            self.data_chunk_list = self._clean_chunk_list(self.data_chunk_list,
                                                         next_end)
            self.nondata_chunk_list = self._clean_chunk_list(self.nondata_chunk_list,
                                                             next_end)
                        
        return next_block
    
    def get_next_raw(self, clean=True):
        """
        Get the next chunk of raw characters from the buffer, clearing all
        that comes before it. Default behavior is to clear the buffer before and including
        this data.

        @param clean Remove the buffer contents before and including this data        
        @return A chunk of data, None if empty list
        """
        if self.raw_chunk_list == []:
            return None

        if clean:    
            (next_start, next_end) = self.raw_chunk_list.pop(0)
        else:
            (next_start, next_end) = self.raw_chunk_list[0]
        
        next_block = self.buffer[next_start:next_end]

        if clean:
            self._clean_buffer(next_end)
            self.raw_chunk_list = self._clean_chunk_list(self.raw_chunk_list,
                                                         next_end)
            self._clean_data_list(next_end)
            self.nondata_chunk_list = self._clean_chunk_list(self.nondata_chunk_list,
                                                             next_end)

        return next_block
    
class StringChunker(Chunker):
    """
    A version of the chunker that handles a string buffer. Methods are tuned
    for easy interaction with strings instead of binary byte blocks.
    """
    def __init__(self, data_sieve_fn):
        Chunker.__init__(self, data_sieve_fn)
        self.buffer = ""
    
    
class BinaryChunker(Chunker):
    """
    A version of the chunker that handles a binary buffer and therefore
    binary data blocks that fall out of it.
    """
    def __init__(self, data_sieve_fn):
        Chunker.__init__(self, data_sieve_fn)
        self.buffer = []
    