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

from mi.core.log import get_logger ; log = get_logger()

from mi.core.exceptions import SampleException

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
        
    def add_chunk(self, raw_data, timestamp):
        """
        Adds a chunk of data to the end of the buffer, includes the new indices
        in the raw_chunk_list. This base class method handles strings and lists.
        Improve or subclass for more capabilities.
        
        @param raw_data The bunch of raw data as a list (or something that can be
            treated as a list...like a string)
        @param timestamp The time (in NTP4 float format) that the data was
            collected at the port agent
        """
        assert isinstance(self.buffer, str) or isinstance(self.buffer, list)
        assert isinstance(timestamp, float)
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
            
        self.raw_chunk_list.append((start_index, end_index, timestamp))

        # find data
        result = self._generate_data_lists(timestamp,
                                           start_index=last_data_index)
        assert result != None
        
        # rebase onto existing buffer
        for (s, e, t) in result['data_chunk_list']:
            self.data_chunk_list.append((s, e, t))
        
            # remove first fragment part from non-data array if we completed a fragment
            for (nds, nde, ndt) in self.nondata_chunk_list:
                if (nds == s):
                    self.nondata_chunk_list.remove((nds, nde, ndt))
        
        # splice non-data blocks in, combining with
        # other blocks as needed
        if result['non_data_chunk_list'] != []:
            new_nondata_list = []
            (first_new_s, first_new_e, first_new_t) = result['non_data_chunk_list'][0]
            
            if self.nondata_chunk_list == []:
                self.nondata_chunk_list = result['non_data_chunk_list']
                log.debug("Added chunk, data_chunk_list: %s, nondata_chunk_list: %s",
                      self.data_chunk_list, self.nondata_chunk_list)
                return
            for (s, e, t) in self.nondata_chunk_list:
                if e >= first_new_s:
                    new_nondata_list.append((s, first_new_e, t))
                    result['non_data_chunk_list'].pop(0) # already used it
                    break
                if e < first_new_s:
                    new_nondata_list.append((s, e, t))
            # all done, merging, so add the rest of what is left
            new_nondata_list.extend(result['non_data_chunk_list'])
            
            self.nondata_chunk_list = new_nondata_list
            log.debug("Added chunk, data_chunk_list: %s, nondata_chunk_list: %s",
                      self.data_chunk_list, self.nondata_chunk_list)
         
    def _generate_data_lists(self, timestamp, start_index=0):
        """
        From some starting place in the raw data buffer, go through and
        find the blocks of data and non-data in the list.
        
        @param timestamp The timestamp to use if an empty non_data_chunk list
            is encountered. Essentially the timestamp to use for a fragment or
            other non-data chunk that is being entered for the first time.
        @param start_index The beginning index to start generating lists from.
            Default is the beginning of the buffer
        @retval A dict with keys "data_chunk_list" and "non_data_chunk_list"
            that include the full data chunk lists for this block of data.
            Indices are respect to the buffer, not the chunk
        """
        log.debug("Generating data lists with start index %s", start_index)
        return_list = {'data_chunk_list':[], 'non_data_chunk_list':[]}
        result = self.sieve(self.buffer[start_index:])
        # assert no overlap!
        if (self.overlaps(result)):
            raise SampleException("Overlapping blocks in sieve list: %s" % result)
        # sort to protect us from some sloppy sieve code
        result.sort()

        # rebase to buffer coordinates
        return_list['data_chunk_list'] = [(s+start_index, e+start_index) for (s, e) in result]
        return_list['data_chunk_list'] = self.add_timestamps(return_list['data_chunk_list'])
        # Look up the timestamps from the old list - could be made more efficient
        
        if result == []:
            return_list['non_data_chunk_list'].append((start_index,
                                                       len(self.buffer),
                                                       timestamp))
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

        return_list['non_data_chunk_list'] = self.add_timestamps(return_list['non_data_chunk_list'])
        log.debug("Generated return list: %s", return_list)
        return return_list    
    
    def add_timestamps(self, start_end_list):
        """
        Add timestamps to a list of (start, end) tuples that are normalized to
        coincide with the raw block list indices.
        
        @param start_end_list The list of (start, end) tuples such as:
            [(15, 20), (35, 37)]
        @retval The timestamps associated with these based on the values in
            the raw block list. For example, if the raw block list is
            [(0, 14, 123.456), (15, 20, 234.567), (21, 37, 345.784)], then the
            result will be [(15, 20, 234.567), (35, 37, 345.784)]
        """
        result_list = []
                    
        for item in start_end_list:
            # simple case if it already has a timestamp
            if (len(item) == 3):
                result_list.append(item)
                break
            elif (len(item) == 2):
                (s, e) = (item[0], item[1])
            else:
                raise SampleException("Invalid pair encountered!")
                
            for (raw_s, raw_e, raw_t) in self.raw_chunk_list:
                if (s >= raw_e):
                    continue
                else:
                    result_list.append((s, e, raw_t))
                    break
                    
        log.trace("add_timestamp returning result_list: %s", result_list)
        return result_list
    
    @staticmethod
    def overlaps(data_list):
        """
        Looks for overlapping data blocks from the sieve function
        
        @param data_list A list of entries
        @return True if overlap exists
        """
        list_length = len(data_list)
        
        if list_length < 2:
            return False
        
        data_list.sort()
        for index in range(1,len(data_list)):
            (s1, e1) = data_list[index-1]
            (s2, e2) = data_list[index]
            if (s2 < e1):
                return True
            
        return False
    
    def get_next_data(self, clean=True):
        """
        Get the next chunk of data from the buffer. By default, it clears all
        that comes before it. This method does not return the start and end indices in
        the resulting tuple.
        
        @param clean If set to false, do not clear the buffer when fetching the
            data, but simply return the data block and make no further changes.
        @return A tuple of (timestamp, data_chunk) where timestamp is in NTP4
            float format and data chunk is a section of buffer with indices
            between (start, end). If no data, returns (None, None)
        """
        (time, result, start, end) = self.get_next_data_with_index(clean)
        return (time, result)
        
    def get_next_data_with_index(self, clean=True):
        """
        Get the next chunk of data from the buffer. By default, it clears all
        that comes before it. This method returns the start and end indices in
        the resulting tuple.
        
        @param clean If set to false, do not clear the buffer when fetching the
            data, but simply return the data block and make no further changes.
        @return A tuple of (timestamp, data_chunk, start_index, end_index) where timestamp is in NTP4
            float format and data chunk is a section of buffer with indices
            between (start, end). If no data, returns (None, None, None, None)
        """
        if self.data_chunk_list == []:
            return (None, None, None, None)

        if clean:    
            (next_start, next_end, timestamp) = self.data_chunk_list.pop(0)
        else:
            (next_start, next_end, timestamp) = self.data_chunk_list[0]
        
        next_block = self.buffer[next_start:next_end]

        if clean:    
            self._clean_buffer(next_end)
            self.raw_chunk_list = self._clean_chunk_list(self.raw_chunk_list,
                                                         next_end)
            self.data_chunk_list = self._clean_chunk_list(self.data_chunk_list,
                                                         next_end)
            self.nondata_chunk_list = self._clean_chunk_list(self.nondata_chunk_list,
                                                             next_end)
                
        return (timestamp, next_block, next_start, next_end)
    
    def _clean_chunk_list(self, list, end_index):
        """
        Cleans up the given chunk list based on the start and end indexes of
        that are being removed. The idea is to keep the given list of indices
        in sync with other lists that are having elements removed from them.
        For example, if the list looks like
        [(3, 5, time), (8, 12, time), (20, 25, time)]
        and the end index is 10, the resulting list will be:
        [(0, 2, time), (10, 15, time)]
        as items up to 10 have been removed (only [10:25] remain)
        and popped off the front so they are now [0:2] and [10:15].
        
        @param list A list of (start, end) tuples of indices that needs to be
            cleaned up.
        @param end_index The end index of what is being removed.
        @retval The new list after it has been cleaned
        """
        return_list = []
        for (s, e, time) in list:
            if s >= end_index:
                return_list.append((s-end_index, e-end_index, time))
            else:
                if e > end_index:
                    return_list.append((0,e-end_index, time))
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

        for (s, e, t) in self.data_chunk_list:
            if (e <= index):
                self.data_chunk_list.remove((s, e, t))
                
            if (e > index):
                self.data_chunk_list.remove((s, e, t))
                # add remaining to non data
                for (nds, nde, ndt) in self.nondata_chunk_list:
                    if (nde < s):
                        new_nondata_list.append((nds, nde, ndt))
                    elif (nde == s):
                        new_nondata_list.append((nds, e, ndt))
                    elif (nde > s):
                        new_nondata_list.append((nds, nde, ndt))
        
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
        
    def get_next_non_data_with_index(self, clean=True):
        """
        Get the next chunk of non-data from the buffer, clearing all that comes
        before it. Default behavior is to clear the buffer before and including
        this data.
        
        @param clean Remove the buffer contents before and including this data
        @return A tuple of (timestamp, data_chunk, next_start, next_end) 
            where timestamp is in NTP4 float format and data chunk is a 
            (start, end) tuple, (None, None) if no data
        """
        if self.nondata_chunk_list == []:
            return (None, None, None, None)

        if clean:    
            (next_start, next_end, next_time) = self.nondata_chunk_list.pop(0)
        else:
            (next_start, next_end, next_time) = self.nondata_chunk_list[0]
        
        next_block = self.buffer[next_start:next_end]

        if clean:    
            self._clean_buffer(next_end)
            self.raw_chunk_list = self._clean_chunk_list(self.raw_chunk_list,
                                                         next_end)
            self.data_chunk_list = self._clean_chunk_list(self.data_chunk_list,
                                                         next_end)
            self.nondata_chunk_list = self._clean_chunk_list(self.nondata_chunk_list,
                                                             next_end)
                        
        return (next_time, next_block, next_start, next_end)

    def get_next_non_data(self, clean=True):
        """
        Get the next chunk of non-data from the buffer, clearing all that comes
        before it. Default behavior is to clear the buffer before and including
        this data.

        @param clean Remove the buffer contents before and including this data
        @return A tuple of (timestamp, data_chunk) where timestamp is in NTP4
            float format and data chunk is a (start, end) tuple,
            (None, None) if no data
        """
        (time, result, start, end) = self.get_next_non_data_with_index(clean)
        return (time, result)
    
    def get_next_raw(self, clean=True):
        """
        Get the next chunk of raw characters from the buffer, clearing all
        that comes before it. Default behavior is to clear the buffer before and including
        this data.

        @param clean Remove the buffer contents before and including this data        
        @return A tuple of (timestamp, data_chunk) where timestamp is in NTP4
            float format and data chunk is a (start, end) tuple,
            (None, None) if empty list
        """
        if self.raw_chunk_list == []:
            return (None, None)

        if clean:    
            (next_start, next_end, next_time) = self.raw_chunk_list.pop(0)
        else:
            (next_start, next_end, next_time) = self.raw_chunk_list[0]
        
        next_block = self.buffer[next_start:next_end]

        if clean:
            self._clean_buffer(next_end)
            self.raw_chunk_list = self._clean_chunk_list(self.raw_chunk_list,
                                                         next_end)
            self._clean_data_list(next_end)
            self.nondata_chunk_list = self._clean_chunk_list(self.nondata_chunk_list,
                                                             next_end)

        return (next_time, next_block)

    def clean_all_chunks(self):
        """
        Clean all data out of the non_data, raw, and data lists
        """
        # clear out any non matching data.
        (nd_timestamp, non_data) = self.get_next_non_data(clean=True)
        while non_data is not None:
            (nd_timestamp, non_data) = self.get_next_non_data(clean=True)
        # clean out raw data
        (nd_timestamp, raw_data) = self.get_next_raw(clean=True)
        while raw_data is not None:
            (nd_timestamp, raw_data) = self.get_next_raw(clean=True)
        # clean out data
        (nd_timestamp, data) = self.get_next_data(clean=True)
        while data is not None:
            (nd_timestamp, data) = self.get_next_data(clean=True)

    @staticmethod
    def regex_sieve_function(raw_data, regex_list=[]):
        """
        Simple method to take a list of regexes to use in a sieve and run the
        incoming data through them. Use this with functools.partial() to
        pre-complete the regex list and make this look like a normal sieve
        function interface. For example, create a chunker like so:
        StringChunker(partial(self._chunker.regex_sieve_function, regex_list=[regex]))
        @param raw_data The raw data to run through this regex sieve
        @param regex_list a list of pre-compiled regexes that will identify some
        flavor of a pattern in the raw data for matching.
        @retval A list of (start, end) tuples for each match the regexs find
        @use
        """
        return_list = []
    
        sieve_matchers = regex_list
        
        for matcher in sieve_matchers:
            for match in matcher.finditer(raw_data):
                return_list.append((match.start(), match.end()))
    
        return return_list

    
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
    