#!/usr/bin/env python

"""
@package mi.dataset.parser.test.test_dosta_ln_wfp_sio_mule
@file marine-integrations/mi/dataset/parser/test/test_dosta_ln_wfp_sio_mule.py
@author Christopher Fortin
@brief Test code for a dosta_ln_wfp_sio_mule data parser
"""
#!/usr/bin/env python

import os
import ntplib, struct
from nose.plugins.attrib import attr

from mi.core.exceptions import SampleException, UnexpectedDataException
from mi.core.log import get_logger ; log = get_logger()
from mi.dataset.test.test_parser import ParserUnitTestCase
from mi.dataset.dataset_driver import DataSetDriverConfigKeys
from mi.dataset.parser.sio_mule_common import StateKey

from mi.dataset.parser.dosta_ln_wfp_sio_mule import DostaLnWfpSioMuleParser
from mi.dataset.parser.dosta_ln_wfp_sio_mule import DostaLnWfpSioMuleParserDataParticle

from mi.idk.config import Config

RESOURCE_PATH = os.path.join(Config().base_dir(), 'mi',
                             'dataset', 'driver', 'dosta_ln',
                             'wfp_sio_mule', 'resource')


@attr('UNIT', group='mi')
class DostaLnWfpSioParserUnitTestCase(ParserUnitTestCase):

    def state_callback(self, state):
        """ Call back method to watch what comes in via the position callback """
        self.state_callback_value = state

    def pub_callback(self, pub):
        """ Call back method to watch what comes in via the publish callback """
        self.publish_callback_value = pub

    def exception_callback(self, exception):
        """ Call back method to watch what comes in via the exception callback """
        self.exception_callback_value = exception

    def setUp(self):
        ParserUnitTestCase.setUp(self)
        self.config = {
            DataSetDriverConfigKeys.PARTICLE_MODULE: 'mi.dataset.parser.dosta_ln_wfp_sio_mule',
            DataSetDriverConfigKeys.PARTICLE_CLASS: 'DostaLnWfpSioMuleParserDataParticle'
            }

        
        # First 'WE' SIO header in noe58p1.dat, first record.        
        self.timestamp_1a = self.timestamp_to_ntp('Q\xf2W.') # The record timestamp should be 2986504401
        log.debug("Converted timestamp 1a: %s",self.timestamp_1a)
        self.particle_1a = DostaLnWfpSioMuleParserDataParticle(b'Q\xf2W.\x00\x00\x00\x00A9Y' \
            '\xb4\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x009\x00e\x02:', internal_timestamp = self.timestamp_1a)
        
        # First 'WE' SIO header in noe58p1.dat, second record.
        self.timestamp_1b = self.timestamp_to_ntp('Q\xf2Xq')
        log.debug("Converted timestamp 1b: %s",self.timestamp_1b)
        self.particle_1b = DostaLnWfpSioMuleParserDataParticle(b'Q\xf2XqB\x8f\x83DA5\x1e\xb8D' \
            '\xfd\x85qB\x82\x83\x12?\xf9\xba^\x009\x00d\x028',  internal_timestamp = self.timestamp_1b)
        
        # First 'WE' SIO header in noe58p1.dat, third record.
        self.timestamp_1c = self.timestamp_to_ntp('Q\xf2Z\xd3')
        log.debug("Converted timestamp 1c: %s",self.timestamp_1c)
        self.particle_1c = DostaLnWfpSioMuleParserDataParticle(b'Q\xf2Z\xd3B\x84\x06GA2\x9a\xd4E' \
            '\t\xd3\xd7B\x9b\xdc)?\xec\xac\x08\x00:\x00d\x027', internal_timestamp = self.timestamp_1c)    
        
        # Second 'WE' SIO header in noe58p1.dat, first record.
        self.timestamp_2a  = self.timestamp_to_ntp('Q\xf2\x8fn')
        log.debug("Converted timestamp 2a: %s",self.timestamp_2a)
        self.particle_2a = DostaLnWfpSioMuleParserDataParticle(b'Q\xf2\x8fn\x00\x00\x00\x00A7\xd5f' \
            '\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x008\x00a\x02=', internal_timestamp = self.timestamp_2a)
        
        # Last 'WE' SIO header in node58p1.dat, last record (when reading 12).
        self.timestamp_1l = self.timestamp_to_ntp('Q\xf2\x99q')
        log.debug("Converted timestamp 1l: %s",self.timestamp_1l)
        self.particle_1l = DostaLnWfpSioMuleParserDataParticle(b'Q\xf2\x99qC"\t\xceA/\x9alEM\x07\\C' \
            '\x07\xd7\n?\xc3\x95\x81\x007\x00_\x02;', internal_timestamp = self.timestamp_1l)
        

        # Last 'WE' SIO header in node58p1.dat[0:300000], second to last record.
        self.timestamp_1k  = self.timestamp_to_ntp('Q\xf2\x981')
        
        log.debug("Converted timestamp 1k: %s",self.timestamp_1k)
        self.particle_1k = DostaLnWfpSioMuleParserDataParticle(b'Q\xf2\x981C\x10\xe5kA/\xe4&EG\x8c\x00C' \
            '\x04\xc2\x8f?\xc4\xfd\xf4\x006\x00_\x02;', internal_timestamp = self.timestamp_1k)
        
        # Last record of second 'WE' SIO header, the last record when pulling 5000 bytes. 
        self.timestamp_m = self.timestamp_to_ntp('Q\xf2\xa5\xc9')
        log.debug("Converted timestamp m2: %s",self.timestamp_m)
        
        
        self.state_callback_value = None
        self.publish_callback_value = None
        self.exception_callback_value = None
        

    def assert_result(self, result, in_process_data, unprocessed_data, particle):
        self.assertEqual(result, [particle])
        self.assert_state(in_process_data, unprocessed_data) 
        self.assert_(isinstance(self.publish_callback_value, list))
        self.assertEqual(self.publish_callback_value[0], particle)

    def assert_state(self, in_process_data, unprocessed_data):
        self.assertEqual(self.parser._state[StateKey.IN_PROCESS_DATA], in_process_data)
        self.assertEqual(self.parser._state[StateKey.UNPROCESSED_DATA], unprocessed_data)
        self.assertEqual(self.state_callback_value[StateKey.IN_PROCESS_DATA], in_process_data)
        self.assertEqual(self.state_callback_value[StateKey.UNPROCESSED_DATA], unprocessed_data)

    def timestamp_to_ntp(self, hex_timestamp):
        fields = struct.unpack('>I', hex_timestamp)
        timestamp = float(fields[0])
        return ntplib.system_to_ntp_time(timestamp)

    def test_simple(self):
        """
        Read test data from the file and pull out data particles one at a time.
        Assert that the results are those we expected.
        """
        log.debug('------------------------------------------------------Starting test_simple')
        self.stream_handle = open(os.path.join(RESOURCE_PATH,
                                               'node58p1.dat'))
        # NOTE: using the unprocessed data state of 0,5000 limits the file to reading
        # just 5000 bytes, so even though the file is longer it only reads the first
        # 5000
        self.state = {StateKey.UNPROCESSED_DATA:[[0, 5000]],
            StateKey.IN_PROCESS_DATA:[],
            StateKey.FILE_SIZE: 1939566}
        self.parser = DostaLnWfpSioMuleParser(self.config, self.state, self.stream_handle,
                                  self.state_callback, self.pub_callback, self.exception_callback)

        result = self.parser.get_records(1)
        
        log.debug("IN_PROCESS_DATA: %s", self.parser._state[StateKey.IN_PROCESS_DATA])
        log.debug("Unprocessed: %s", self.parser._state[StateKey.UNPROCESSED_DATA])
        # An extra byte exists between SIO headers([4058:4059] and [7423,7424])
        self.assert_result(result, [[2818,2982,3,1], [4059,4673,18,0]],
                           [[2818,2982], [4058,5000]], self.particle_1a)
        
        result = self.parser.get_records(1)
        self.assert_result(result, [[2818,2982,3,2], [4059,4673,18,0]],
                           [[2818,2982], [4058,5000]], self.particle_1b)
        
        result = self.parser.get_records(1)
        self.assert_result(result, [[4059,4673,18,0]],
                           [[4058,5000]], self.particle_1c)
                
        result = self.parser.get_records(1)
        self.assert_result(result, [[4059,4673,18,1]],
                           [[4058,5000]], self.particle_2a)     
        self.stream_handle.close()
        
        
    def test_get_many(self):
        """
        Read test data from the file and pull out multiple data particles at one time.
        Assert that the results are those we expected.
        """
            
        
        log.debug('--------------------------------------------------------Starting test_get_many')
        self.state = {StateKey.UNPROCESSED_DATA:[[0, 5000]],
            StateKey.IN_PROCESS_DATA:[],
            StateKey.FILE_SIZE: 1939566}
        self.stream_handle = open(os.path.join(RESOURCE_PATH,
                                               'node58p1.dat'))
        self.parser = DostaLnWfpSioMuleParser(self.config, self.state, self.stream_handle,
                                  self.state_callback, self.pub_callback, self.exception_callback) 

        result = self.parser.get_records(4)
        self.assertEqual(result,
                         [self.particle_1a, self.particle_1b, self.particle_1c, self.particle_2a])

	
        self.assertEqual(self.publish_callback_value[0], self.particle_1a)
        self.assertEqual(self.publish_callback_value[1], self.particle_1b)
        self.assertEqual(self.publish_callback_value[2], self.particle_1c)
        self.assertEqual(self.publish_callback_value[3], self.particle_2a)
        self.assert_state([[4059,4673,18,1]],[[4058,5000]])
        self.stream_handle.close()
    
    def test_long_stream(self):
        """
        Test a long stream 
        """

        log.debug('---------------------------------------------------------Starting test_long_stream')
        self.stream_handle = open(os.path.join(RESOURCE_PATH,
                                               'node58p1.dat'))
        self.stream_handle.seek(0)
        self.state = {StateKey.UNPROCESSED_DATA:[[0, 5000]],
            StateKey.IN_PROCESS_DATA:[],
            StateKey.FILE_SIZE: 1939566}
        self.parser = DostaLnWfpSioMuleParser(self.config, self.state, self.stream_handle,
                                  self.state_callback, self.pub_callback, self.exception_callback)

        result = self.parser.get_records(12)

        self.assertEqual(result[0], self.particle_1a)
        self.assertEqual(result[1], self.particle_1b)
        self.assertEqual(result[2], self.particle_1c)
        self.assertEqual(result[-2], self.particle_1k)
        self.assertEqual(result[-1], self.particle_1l)

        self.assertEqual(self.publish_callback_value[-2], self.particle_1k)
        self.assertEqual(self.publish_callback_value[-1], self.particle_1l)

        self.assert_state([[4059,4673,18,9]],[[4058,5000]])
        self.stream_handle.close()        


    def test_mid_state_start(self):
        """
        Test starting the parser in a state in the middle of processing
        """

        log.debug('-----------------------------------------------------------Starting test_mid_state_start')
        new_state = {StateKey.IN_PROCESS_DATA:[],
            StateKey.UNPROCESSED_DATA:[[2818,2982]],
            StateKey.FILE_SIZE: 1939566}
        self.stream_handle = open(os.path.join(RESOURCE_PATH, 'node58p1.dat'))
        self.parser = DostaLnWfpSioMuleParser(self.config, new_state, self.stream_handle,
                                  self.state_callback, self.pub_callback, self.exception_callback)
        result = self.parser.get_records(1)
        self.assert_result(result, [[2818,2982,3,1]],
                           [[2818,2982]], self.particle_1a)
        result = self.parser.get_records(1)
        self.assert_result(result, [[2818,2982,3,2]],
                           [[2818,2982]], self.particle_1b)
        result = self.parser.get_records(1)
        self.assert_result(result, [], [], self.particle_1c)

        self.stream_handle.close()


    def test_bad_data(self):
        """
        Ensure that the bad record ( in this case a currupted status message ) causes a sample exception
        """
        self.stream_handle = open(os.path.join(RESOURCE_PATH, 'node58p1_BADFLAGS.dat'))
        self.state = {StateKey.UNPROCESSED_DATA:[[0, 5000]],
            StateKey.IN_PROCESS_DATA:[],
            StateKey.FILE_SIZE: 1939566}
        log.debug('-------------------------------------------------------------Starting test_bad_data')
        self.parser = DostaLnWfpSioMuleParser(self.config, self.state, self.stream_handle,
                                              self.state_callback, self.pub_callback, self.exception_callback)
        result = self.parser.get_records(1)
        self.assert_(isinstance(self.exception_callback_value, UnexpectedDataException))


    def test_in_process_start(self):
        """
        test starting a parser with a state in the middle of processing
        """
        log.debug('-------------------------------------------------------------Starting test_in_process_start')
        #[2818:2982] contains the first WE SIO header
        new_state = {StateKey.IN_PROCESS_DATA:[[2818,2982,3,0], [4059,4673,18,0]],
            StateKey.UNPROCESSED_DATA:[[2818,2982], [4058,5000]],
            StateKey.FILE_SIZE: 1939566}
        self.stream_handle = open(os.path.join(RESOURCE_PATH, 'node58p1.dat'))
        self.parser = DostaLnWfpSioMuleParser(self.config, new_state, self.stream_handle,
                                  self.state_callback, self.pub_callback, self.exception_callback)

        result = self.parser.get_records(1)
        self.assert_result(result, [[2818,2982,3,1], [4059,4673,18,0]],
                           [[2818,2982], [4058,5000]], self.particle_1a) 

        result = self.parser.get_records(2)
        self.assertEqual(result[0], self.particle_1b)
        self.assertEqual(result[1], self.particle_1c)
        self.assert_state([[4059,4673,18,0]], [[4058,5000]])
        self.assertEqual(self.publish_callback_value[-1], self.particle_1c)

        result = self.parser.get_records(1)
        self.assert_result(result, [[4059,4673,18,1]],
                           [[4058,5000]], self.particle_2a) 

        self.stream_handle.close()     
        
    
    def test_set_state(self):
        """
        Test changing to a new state after initializing the parser and 
        reading data, as if new data has been found and the state has
        changed
        """
        log.debug('-------------------------------------------------Starting test_set_state')
        self.state = {StateKey.UNPROCESSED_DATA:[[4059, 4673]],
            StateKey.IN_PROCESS_DATA:[],
            StateKey.FILE_SIZE: 1939566}
        new_state = {StateKey.UNPROCESSED_DATA:[[2818, 2982], [4058, 4059], [4673, 5000]],
            StateKey.IN_PROCESS_DATA:[[2818, 2982, 3, 0]],
            StateKey.FILE_SIZE: 1939566}

        self.stream_handle = open(os.path.join(RESOURCE_PATH,
                                               'node58p1.dat'))
        self.parser = DostaLnWfpSioMuleParser(self.config, self.state, self.stream_handle,
                                  self.state_callback, self.pub_callback, self.exception_callback)

        # only 18 left in file at this point.  Drain them, and make sure the next fetch fails
        result = self.parser.get_records(17)
        self.assert_state([[4059, 4673, 18, 17]],[[4059, 4673]])
        result = self.parser.get_records(1)
        result = self.parser.get_records(1)
        self.assertEqual(result, [])      

        self.parser.set_state(new_state)

        result = self.parser.get_records(1)
        self.assert_result(result,
                           [[2818, 2982, 3, 1]],
                           [[2818, 2982], [4058, 4059], [4673, 5000]],
                           self.particle_1a)
        self.stream_handle.close()

       
    def test_update(self):
        """
        Test a file which has had a section of data replaced by 0s, as if a block of data has not been received yet,
        then using the returned state make a new parser with the test data that has the 0s filled in
        """

        log.debug('------------------------------------------------------Starting test_update')
        self.state = {StateKey.UNPROCESSED_DATA:[[0, 5000]],
            StateKey.IN_PROCESS_DATA:[],
            StateKey.FILE_SIZE: 1939566}
        # this file has first block of WE data replaced by 0s
        self.stream_handle = open(os.path.join(RESOURCE_PATH,
                                               'node58p1_1stWE0d.dat'))
        self.parser = DostaLnWfpSioMuleParser(self.config, self.state, self.stream_handle,
                                  self.state_callback, self.pub_callback, self.exception_callback)

        result = self.parser.get_records(1)
        self.assert_result(result,
                           [[4059,4673,18,1]],
                           [[2818, 2982], [4058, 5000]],
                           self.particle_2a)    
        self.stream_handle.close()

        next_state = self.parser._state

        self.stream_handle = open(os.path.join(RESOURCE_PATH,
                                               'node58p1.dat'))        
        self.parser = DostaLnWfpSioMuleParser(self.config, next_state, self.stream_handle,
                                  self.state_callback, self.pub_callback, self.exception_callback)

        # first get the old 'in process' records
        # Once those are done, the un processed data will be checked
 

        # there are 18 valid records in the second WE chunk.  We read one above, now we need
        # to drain the remaining 17 to trigger the reparsing of the earlier block
        for kk in range(0, 17):
            result = self.parser.get_records(1)

        # so now, the next fetch should find the now-replaced earlier data
        result = self.parser.get_records(1)
        self.assert_result(result,
                           [[2818, 2982, 3, 1]],
                           [[2818, 2982], [4058, 4059], [4673, 5000]],
                           self.particle_1a)


        # this should be the first of the newly filled in particles from
        result = self.parser.get_records(1)
        self.assert_result(result,
                           [[2818, 2982, 3, 2]],
                           [[2818, 2982], [4058, 4059], [4673, 5000]],
                           self.particle_1b)
        self.stream_handle.close()


    def test_bad_e_record(self):
	"""
	Ensure that the bad record causes a sample exception. The file 'bad_e_record.dat'
	includes a record containing one byte less than the expected 30 for the
	flord_l_wfp_sio_mule. The 'Number of Data Bytes' and the 'CRC Checksum' values in the
	SIO Mule header have been modified accordingly.
	"""
	self.stream_handle = open(os.path.join(RESOURCE_PATH, 'bad_e_record.dat'))
	self.state = {StateKey.UNPROCESSED_DATA:[[0, 5000]],
	    StateKey.IN_PROCESS_DATA:[], StateKey.FILE_SIZE:[]}
    
	self.parser = DostaLnWfpSioMuleParser(self.config, self.state, self.stream_handle,
				      self.state_callback, self.pub_callback, self.exception_callback)
	result = self.parser.get_records(1)
	self.assert_(isinstance(self.exception_callback_value, UnexpectedDataException)) 
