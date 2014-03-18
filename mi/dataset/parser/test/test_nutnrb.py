#!/usr/bin/env python

"""
@package mi.dataset.parser.test.test_nutnrb
@file marine-integrations/mi/dataset/parser/test/test_nutnrb.py
@author Roger Unwin
@brief Test code for a Nutnrb data parser
"""

import gevent
from StringIO import StringIO
from nose.plugins.attrib import attr

from mi.core.log import get_logger ; log = get_logger()

from mi.core.exceptions import SampleException
from mi.dataset.test.test_parser import ParserUnitTestCase
from mi.dataset.dataset_driver import DataSetDriverConfigKeys
from mi.dataset.parser.nutnrb import NutnrbParser, NutnrbDataParticle, StateKey

# Add a mixin here if needed

@attr('UNIT', group='mi')
class NutnrbParserUnitTestCase(ParserUnitTestCase):
    """
    WFP Parser unit test suite
    """
    TEST_DATA = """
2012/12/13 15:29:20.362 [nutnr:DLOGP1]:Idle state, without initialize
2012/12/13 15:30:06.455 [nutnr:DLOGP1]:S
2012/12/13 15:30:06.676 [nutnr:DLOGP1]:O
2012/12/13 15:30:06.905 [nutnr:DLOGP1]:S
2012/12/13 15:30:07.130 [nutnr:DLOGP1]:Y
2012/12/13 15:30:07.355 [nutnr:DLOGP1]:1
2012/12/13 15:30:07.590 [nutnr:DLOGP1]:T
2012/12/13 15:30:07.829 [nutnr:DLOGP1]:Y
2012/12/13 15:30:08.052 [nutnr:DLOGP1]:3
2012/12/13 15:30:08.283 [nutnr:DLOGP1]:L
2012/12/13 15:30:08.524 [nutnr:DLOGP1]:Y
2012/12/13 15:30:08.743 [nutnr:DLOGP1]:1
2012/12/13 15:30:08.969 [nutnr:DLOGP1]:D
2012/12/13 15:30:09.194 [nutnr:DLOGP1]:Y
2012/12/13 15:30:09.413 [nutnr:DLOGP1]:0
2012/12/13 15:30:09.623 [nutnr:DLOGP1]:Q
2012/12/13 15:30:09.844 [nutnr:DLOGP1]:D
2012/12/13 15:30:10.096 [nutnr:DLOGP1]:O
2012/12/13 15:30:10.349 [nutnr:DLOGP1]:Y
2012/12/13 15:30:10.570 [nutnr:DLOGP1]:5
2012/12/13 15:30:10.779 [nutnr:DLOGP1]:Q
2012/12/13 15:30:10.990 [nutnr:DLOGP1]:Q
2012/12/13 15:30:11.223 [nutnr:DLOGP1]:Y
2012/12/13 15:30:11.703 [nutnr:DLOGP1]:Y
2012/12/13 15:30:12.841 [nutnr:DLOGP1]:2012/12/13 15:30:11
2012/12/13 15:30:13.261 [nutnr:DLOGP1]:Instrument started with initialize
2012/12/13 15:30:19.270 [nutnr:DLOGP1]:onds.
2012/12/13 15:30:20.271 [nutnr:DLOGP1]:ISUS will start in 7 seconds.
2012/12/13 15:30:21.272 [nutnr:DLOGP1]:ISUS will start in 6 seconds.
2012/12/13 15:30:22.272 [nutnr:DLOGP1]:ISUS will start in 5 seconds.
2012/12/13 15:30:23.273 [nutnr:DLOGP1]:ISUS will start in 4 seconds.
2012/12/13 15:30:24.273 [nutnr:DLOGP1]:ISUS will start in 3 seconds.
2012/12/13 15:30:25.274 [nutnr:DLOGP1]:ISUS will start in 2 seconds.
2012/12/13 15:30:26.275 [nutnr:DLOGP1]:ISUS will start in 1 seconds.
2012/12/13 15:30:27.275 [nutnr:DLOGP1]:ISUS will start in 0 seconds.
2012/12/13 15:30:28.309 [nutnr:DLOGP1]:12/13/2012 15:30:26: Message: Entering low power suspension, waiting for trigger.
2012/12/13 15:30:59.889 [nutnr:DLOGP1]: ++++++++++ charged
2012/12/13 15:31:00.584 [nutnr:DLOGP1]: ON Spectrometer.
2012/12/13 15:31:01.366 [nutnr:DLOGP1]:12/13/2012 15:30:59: Message: Spectrometer powered up.
2012/12/13 15:31:01.435 [nutnr:DLOGP1]:12/13/2012 15:30:59: Message: Turning ON UV light source.
2012/12/13 15:31:06.917 [nutnr:DLOGP1]:12/13/2012 15:31:04: Message: UV light source powered up.
2012/12/13 15:31:07.053 [nutnr:DLOGP1]:12/13/2012 15:31:04: Message: Data log file is 'DATA\SCH12348.DAT'.
2012/12/13 15:31:08.726 SATNDC0239,2012348,15.518322,0.00,0.00,0.00,0.00,0.000000
2012/12/13 15:31:10.065 SATNLC0239,2012348,15.518666,-5.48,20.38,-31.12,0.59,0.000231
2012/12/13 15:31:11.405 SATNLC0239,2012348,15.519024,-6.38,24.24,-37.41,0.61,0.000191
2012/12/13 15:31:12.720 SATNLC0239,2012348,15.519397,-6.77,24.80,-38.00,0.62,0.000203
2012/12/13 15:42:25.429 [nutnr:DLOGP1]:ISUS will start in 15 seconds.
2012/12/13 15:42:26.430 [nutnr:DLOGP1]:ISUS will start in 14 seconds.
2012/12/13 15:42:27.431 [nutnr:DLOGP1]:ISUS will start in 13 seconds.
2012/12/13 15:42:28.431 [nutnr:DLOGP1]:ISUS will start in 12 seconds.
2012/12/13 15:42:29.432 [nutnr:DLOGP1]:ISUS will start in 11 seconds.
2012/12/13 15:42:30.433 [nutnr:DLOGP1]:ISUS will start in 10 seconds.
2012/12/13 15:42:31.434 [nutnr:DLOGP1]:ISUS will start in 9 seconds.
2012/12/13 15:42:32.435 [nutnr:DLOGP1]:ISUS will start in 8 seconds.
2012/12/13 15:42:33.436 [nutnr:DLOGP1]:ISUS will start in 7 seconds.
2012/12/13 15:42:34.436 [nutnr:DLOGP1]:ISUS will start in 6 seconds.
2012/12/13 15:42:35.437 [nutnr:DLOGP1]:ISUS will start in 5 seconds.
2012/12/13 15:42:36.438 [nutnr:DLOGP1]:ISUS will start in 4 seconds.
2012/12/13 15:42:37.438 [nutnr:DLOGP1]:ISUS will start in 3 seconds.
2012/12/13 15:42:38.439 [nutnr:DLOGP1]:ISUS will start in 2 seconds.
2012/12/13 15:42:39.440 [nutnr:DLOGP1]:ISUS will start in 1 seconds.
2012/12/13 15:42:40.440 [nutnr:DLOGP1]:ISUS will start in 0 seconds.
2012/12/13 15:42:41.474 [nutnr:DLOGP1]:12/13/2012 15:42:38: Message: Entering low power suspension, waiting for trigger.
2012/12/13 15:45:26.795 [nutnr:DLOGP1]:Idle state, without initialize
2012/12/13 15:45:46.793 [nutnr:DLOGP1]:Instrument started
2012/12/13 17:51:53.412 [nutnr:DLOGP1]:S
2012/12/13 17:51:53.633 [nutnr:DLOGP1]:O
2012/12/13 17:51:53.862 [nutnr:DLOGP1]:S
2012/12/13 17:51:54.088 [nutnr:DLOGP1]:Y
2012/12/13 17:51:54.312 [nutnr:DLOGP1]:1
2012/12/13 17:51:54.548 [nutnr:DLOGP1]:T
2012/12/13 17:51:54.788 [nutnr:DLOGP1]:Y
2012/12/13 17:51:55.011 [nutnr:DLOGP1]:3
2012/12/13 17:51:55.243 [nutnr:DLOGP1]:L
2012/12/13 17:51:55.483 [nutnr:DLOGP1]:Y
2012/12/13 17:51:55.702 [nutnr:DLOGP1]:1
2012/12/13 17:51:55.928 [nutnr:DLOGP1]:D
2012/12/13 17:51:56.154 [nutnr:DLOGP1]:Y
2012/12/13 17:51:56.373 [nutnr:DLOGP1]:0
2012/12/13 17:51:56.582 [nutnr:DLOGP1]:Q
2012/12/13 17:51:56.803 [nutnr:DLOGP1]:D
2012/12/13 17:51:57.055 [nutnr:DLOGP1]:O
2012/12/13 17:51:57.308 [nutnr:DLOGP1]:Y
2012/12/13 17:51:57.529 [nutnr:DLOGP1]:5
2012/12/13 17:51:57.738 [nutnr:DLOGP1]:Q
2012/12/13 17:51:57.948 [nutnr:DLOGP1]:Q
2012/12/13 17:51:58.181 [nutnr:DLOGP1]:Y
2012/12/13 17:51:58.659 [nutnr:DLOGP1]:Y
2012/12/13 17:51:59.747 [nutnr:DLOGP1]:2012/12/13 17:51:58
2012/12/13 17:52:00.166 [nutnr:DLOGP1]:Instrument started with initialize
"""

    LONG_DATA = """
2012/12/13 15:29:20.362 [nutnr:DLOGP1]:Idle state, without initialize
2012/12/13 15:30:06.455 [nutnr:DLOGP1]:S
2012/12/13 15:30:06.676 [nutnr:DLOGP1]:O
2012/12/13 15:30:06.905 [nutnr:DLOGP1]:S
2012/12/13 15:30:07.130 [nutnr:DLOGP1]:Y
2012/12/13 15:30:07.355 [nutnr:DLOGP1]:1
2012/12/13 15:30:07.590 [nutnr:DLOGP1]:T
2012/12/13 15:30:07.829 [nutnr:DLOGP1]:Y
2012/12/13 15:30:08.052 [nutnr:DLOGP1]:3
2012/12/13 15:30:08.283 [nutnr:DLOGP1]:L
2012/12/13 15:30:08.524 [nutnr:DLOGP1]:Y
2012/12/13 15:30:08.743 [nutnr:DLOGP1]:1
2012/12/13 15:30:08.969 [nutnr:DLOGP1]:D
2012/12/13 15:30:09.194 [nutnr:DLOGP1]:Y
2012/12/13 15:30:09.413 [nutnr:DLOGP1]:0
2012/12/13 15:30:09.623 [nutnr:DLOGP1]:Q
2012/12/13 15:30:09.844 [nutnr:DLOGP1]:D
2012/12/13 15:30:10.096 [nutnr:DLOGP1]:O
2012/12/13 15:30:10.349 [nutnr:DLOGP1]:Y
2012/12/13 15:30:10.570 [nutnr:DLOGP1]:5
2012/12/13 15:30:10.779 [nutnr:DLOGP1]:Q
2012/12/13 15:30:10.990 [nutnr:DLOGP1]:Q
2012/12/13 15:30:11.223 [nutnr:DLOGP1]:Y
2012/12/13 15:30:11.703 [nutnr:DLOGP1]:Y
2012/12/13 15:30:12.841 [nutnr:DLOGP1]:2012/12/13 15:30:11
2012/12/13 15:30:13.261 [nutnr:DLOGP1]:Instrument started with initialize
2012/12/13 15:30:19.270 [nutnr:DLOGP1]:onds.
2012/12/13 15:30:20.271 [nutnr:DLOGP1]:ISUS will start in 7 seconds.
2012/12/13 15:30:21.272 [nutnr:DLOGP1]:ISUS will start in 6 seconds.
2012/12/13 15:30:22.272 [nutnr:DLOGP1]:ISUS will start in 5 seconds.
2012/12/13 15:30:23.273 [nutnr:DLOGP1]:ISUS will start in 4 seconds.
2012/12/13 15:30:24.273 [nutnr:DLOGP1]:ISUS will start in 3 seconds.
2012/12/13 15:30:25.274 [nutnr:DLOGP1]:ISUS will start in 2 seconds.
2012/12/13 15:30:26.275 [nutnr:DLOGP1]:ISUS will start in 1 seconds.
2012/12/13 15:30:27.275 [nutnr:DLOGP1]:ISUS will start in 0 seconds.
2012/12/13 15:30:28.309 [nutnr:DLOGP1]:12/13/2012 15:30:26: Message: Entering low power suspension, waiting for trigger.
2012/12/13 15:30:59.889 [nutnr:DLOGP1]: ++++++++++ charged
2012/12/13 15:31:00.584 [nutnr:DLOGP1]: ON Spectrometer.
2012/12/13 15:31:01.366 [nutnr:DLOGP1]:12/13/2012 15:30:59: Message: Spectrometer powered up.
2012/12/13 15:31:01.435 [nutnr:DLOGP1]:12/13/2012 15:30:59: Message: Turning ON UV light source.
2012/12/13 15:31:06.917 [nutnr:DLOGP1]:12/13/2012 15:31:04: Message: UV light source powered up.
2012/12/13 15:31:07.053 [nutnr:DLOGP1]:12/13/2012 15:31:04: Message: Data log file is 'DATA\SCH12348.DAT'.
2012/12/13 15:31:08.726 SATNDC0239,2012348,15.518322,0.00,0.00,0.00,0.00,0.000000
2012/12/13 15:31:10.065 SATNLC0239,2012348,15.518666,-5.48,20.38,-31.12,0.59,0.000231
2012/12/13 15:31:11.405 SATNLC0239,2012348,15.519024,-6.38,24.24,-37.41,0.61,0.000191
2012/12/13 15:31:12.720 SATNLC0239,2012348,15.519397,-6.77,24.80,-38.00,0.62,0.000203
2012/12/13 15:31:14.041 SATNLC0239,2012348,15.519770,-5.28,18.39,-27.76,0.59,0.000212
2012/12/13 15:31:15.350 SATNLC0239,2012348,15.520128,-7.57,32.65,-51.28,0.62,0.000186
2012/12/13 15:31:16.695 SATNLC0239,2012348,15.520501,-6.17,24.43,-37.71,0.60,0.000218
2012/12/13 15:31:18.015 SATNLC0239,2012348,15.520875,-5.59,18.68,-28.01,0.60,0.000166
2012/12/13 15:31:19.342 SATNLC0239,2012348,15.521232,-7.30,30.87,-48.21,0.62,0.000235
2012/12/13 15:31:20.704 SATNLC0239,2012348,15.521605,-7.52,31.35,-49.03,0.63,0.000240
2012/12/13 15:42:25.429 [nutnr:DLOGP1]:ISUS will start in 15 seconds.
2012/12/13 15:42:26.430 [nutnr:DLOGP1]:ISUS will start in 14 seconds.
2012/12/13 15:42:27.431 [nutnr:DLOGP1]:ISUS will start in 13 seconds.
2012/12/13 15:42:28.431 [nutnr:DLOGP1]:ISUS will start in 12 seconds.
2012/12/13 15:42:29.432 [nutnr:DLOGP1]:ISUS will start in 11 seconds.
2012/12/13 15:42:30.433 [nutnr:DLOGP1]:ISUS will start in 10 seconds.
2012/12/13 15:42:31.434 [nutnr:DLOGP1]:ISUS will start in 9 seconds.
2012/12/13 15:42:32.435 [nutnr:DLOGP1]:ISUS will start in 8 seconds.
2012/12/13 15:42:33.436 [nutnr:DLOGP1]:ISUS will start in 7 seconds.
2012/12/13 15:42:34.436 [nutnr:DLOGP1]:ISUS will start in 6 seconds.
2012/12/13 15:42:35.437 [nutnr:DLOGP1]:ISUS will start in 5 seconds.
2012/12/13 15:42:36.438 [nutnr:DLOGP1]:ISUS will start in 4 seconds.
2012/12/13 15:42:37.438 [nutnr:DLOGP1]:ISUS will start in 3 seconds.
2012/12/13 15:42:38.439 [nutnr:DLOGP1]:ISUS will start in 2 seconds.
2012/12/13 15:42:39.440 [nutnr:DLOGP1]:ISUS will start in 1 seconds.
2012/12/13 15:42:40.440 [nutnr:DLOGP1]:ISUS will start in 0 seconds.
2012/12/13 15:42:41.474 [nutnr:DLOGP1]:12/13/2012 15:42:38: Message: Entering low power suspension, waiting for trigger.
2012/12/13 15:45:26.795 [nutnr:DLOGP1]:Idle state, without initialize
2012/12/13 15:45:46.793 [nutnr:DLOGP1]:Instrument started
2012/12/13 17:51:53.412 [nutnr:DLOGP1]:S
2012/12/13 17:51:53.633 [nutnr:DLOGP1]:O
2012/12/13 17:51:53.862 [nutnr:DLOGP1]:S
2012/12/13 17:51:54.088 [nutnr:DLOGP1]:Y
2012/12/13 17:51:54.312 [nutnr:DLOGP1]:1
2012/12/13 17:51:54.548 [nutnr:DLOGP1]:T
2012/12/13 17:51:54.788 [nutnr:DLOGP1]:Y
2012/12/13 17:51:55.011 [nutnr:DLOGP1]:3
2012/12/13 17:51:55.243 [nutnr:DLOGP1]:L
2012/12/13 17:51:55.483 [nutnr:DLOGP1]:Y
2012/12/13 17:51:55.702 [nutnr:DLOGP1]:1
2012/12/13 17:51:55.928 [nutnr:DLOGP1]:D
2012/12/13 17:51:56.154 [nutnr:DLOGP1]:Y
2012/12/13 17:51:56.373 [nutnr:DLOGP1]:0
2012/12/13 17:51:56.582 [nutnr:DLOGP1]:Q
2012/12/13 17:51:56.803 [nutnr:DLOGP1]:D
2012/12/13 17:51:57.055 [nutnr:DLOGP1]:O
2012/12/13 17:51:57.308 [nutnr:DLOGP1]:Y
2012/12/13 17:51:57.529 [nutnr:DLOGP1]:5
2012/12/13 17:51:57.738 [nutnr:DLOGP1]:Q
2012/12/13 17:51:57.948 [nutnr:DLOGP1]:Q
2012/12/13 17:51:58.181 [nutnr:DLOGP1]:Y
2012/12/13 17:51:58.659 [nutnr:DLOGP1]:Y
2012/12/13 17:51:59.747 [nutnr:DLOGP1]:2012/12/13 17:51:58
2012/12/13 17:52:00.166 [nutnr:DLOGP1]:Instrument started with initialize
"""

    BAD_TEST_DATA = """
2012/12/13 15:29:20.362 [nutnr:DLOGP1]:Idle state, without initialize
2012/12/13 15:30:06.455 [nutnr:DLOGP1]:S
2012/12/13 15:30:06.676 [nutnr:DLOGP1]:O
2012/12/13 15:30:06.905 [nutnr:DLOGP1]:S
2012/12/13 15:30:07.130 [nutnr:DLOGP1]:Y
2012/12/13 15:30:07.355 [nutnr:DLOGP1]:1
2012/12/13 15:30:07.590 [nutnr:DLOGP1]:T
2012/12/13 15:30:07.829 [nutnr:DLOGP1]:Y
2012/12/13 15:30:08.052 [nutnr:DLOGP1]:3
2012/12/13 15:30:08.283 [nutnr:DLOGP1]:L
2012/12/13 15:30:08.524 [nutnr:DLOGP1]:Y
2012/12/13 15:30:08.743 [nutnr:DLOGP1]:1
2012/12/13 15:30:08.969 [nutnr:DLOGP1]:D
2012/12/13 15:30:09.194 [nutnr:DLOGP1]:Y
2012/12/13 15:30:09.413 [nutnr:DLOGP1]:0
2012/12/13 15:30:09.623 [nutnr:DLOGP1]:Q
2012/12/13 15:30:09.844 [nutnr:DLOGP1]:D
2012/12/13 15:30:10.096 [nutnr:DLOGP1]:O
2012/12/13 15:30:10.349 [nutnr:DLOGP1]:Y
2012/12/13 15:30:10.570 [nutnr:DLOGP1]:5
2012/12/13 15:30:10.779 [nutnr:DLOGP1]:Q
2012/12/13 15:30:10.990 [nutnr:DLOGP1]:Q
2012/12/13 15:30:11.223 [nutnr:DLOGP1]:Y
2012/12/13 15:30:11.703 [nutnr:DLOGP1]:Y
2012/12/13 15:30:12.841 [nutnr:DLOGP1]:2012/12/13 15:30:11
2012/12/13 15:30:13.261 [nutnr:DLOGP1]:Instrument started with initialize
2012/12/13 15:30:19.270 [nutnr:DLOGP1]:onds.
2012/12/13 15:30:20.271 [nutnr:DLOGP1]:ISUS will start in 7 seconds.
2012/12/13 15:30:21.272 [nutnr:DLOGP1]:ISUS will start in 6 seconds.
2012/12/13 15:30:22.272 [nutnr:DLOGP1]:ISUS will start in 5 seconds.
2012/12/13 15:30:23.273 [nutnr:DLOGP1]:ISUS will start in 4 seconds.
2012/12/13 15:30:24.273 [nutnr:DLOGP1]:ISUS will start in 3 seconds.
2012/12/13 15:30:25.274 [nutnr:DLOGP1]:ISUS will start in 2 seconds.
2012/12/13 15:30:26.275 [nutnr:DLOGP1]:ISUS will start in 1 seconds.
2012/12/13 15:30:27.275 [nutnr:DLOGP1]:ISUS will start in 0 seconds.
2012/12/13 15:30:28.309 [nutnr:DLOGP1]:12/13/2012 15:30:26: Message: Entering low power suspension, waiting for trigger.
2012/12/13 15:30:59.889 [nutnr:DLOGP1]: ++++++++++ charged
2012/12/13 15:31:00.584 [nutnr:DLOGP1]: ON Spectrometer.
2012/12/13 15:31:01.366 [nutnr:DLOGP1]:12/13/2012 15:30:59: Message: Spectrometer powered up.
2012/12/13 15:31:01.435 [nutnr:DLOGP1]:12/13/2012 15:30:59: Message: Turning ON UV light source.
2012/12/13 15:31:06.917 [nutnr:DLOGP1]:12/13/2012 15:31:04: Message: UV light source powered up.
2012/12/13 15:31:07.053 [nutnr:DLOGP1]:12/13/2012 15:31:04: Message: Data log file is 'DATA\SCH12348.DAT'.
2012\12\13 15:31:08.726 SATNDC0239,2012348,15.518322,0.00,0.00,0.00,0.00,0.000000
 SATNLC0239,2012348,15.518666,-5.48,20.38,-31.12,0.59,0.000231
2012/12/13 15:31:11.405 SATNLC0239,2012348,15.519024,-6.38,24.24,-37.41,0.61,0.000191
2012/12/13 15:31:12.720 SATNLC0239,2012348,15.519397,-6.77,24.80,-38.00,0.62,0.000203
2012/12/13 15:42:25.429 [nutnr:DLOGP1]:ISUS will start in 15 seconds.
2012/12/13 15:42:26.430 [nutnr:DLOGP1]:ISUS will start in 14 seconds.
2012/12/13 15:42:27.431 [nutnr:DLOGP1]:ISUS will start in 13 seconds.
2012/12/13 15:42:28.431 [nutnr:DLOGP1]:ISUS will start in 12 seconds.
2012/12/13 15:42:29.432 [nutnr:DLOGP1]:ISUS will start in 11 seconds.
2012/12/13 15:42:30.433 [nutnr:DLOGP1]:ISUS will start in 10 seconds.
2012/12/13 15:42:31.434 [nutnr:DLOGP1]:ISUS will start in 9 seconds.
2012/12/13 15:42:32.435 [nutnr:DLOGP1]:ISUS will start in 8 seconds.
2012/12/13 15:42:33.436 [nutnr:DLOGP1]:ISUS will start in 7 seconds.
2012/12/13 15:42:34.436 [nutnr:DLOGP1]:ISUS will start in 6 seconds.
2012/12/13 15:42:35.437 [nutnr:DLOGP1]:ISUS will start in 5 seconds.
2012/12/13 15:42:36.438 [nutnr:DLOGP1]:ISUS will start in 4 seconds.
2012/12/13 15:42:37.438 [nutnr:DLOGP1]:ISUS will start in 3 seconds.
2012/12/13 15:42:38.439 [nutnr:DLOGP1]:ISUS will start in 2 seconds.
2012/12/13 15:42:39.440 [nutnr:DLOGP1]:ISUS will start in 1 seconds.
2012/12/13 15:42:40.440 [nutnr:DLOGP1]:ISUS will start in 0 seconds.
2012/12/13 15:42:41.474 [nutnr:DLOGP1]:12/13/2012 15:42:38: Message: Entering low power suspension, waiting for trigger.
2012/12/13 15:45:26.795 [nutnr:DLOGP1]:Idle state, without initialize
2012/12/13 15:45:46.793 [nutnr:DLOGP1]:Instrument started
2012/12/13 17:51:53.412 [nutnr:DLOGP1]:S
2012/12/13 17:51:53.633 [nutnr:DLOGP1]:O
2012/12/13 17:51:53.862 [nutnr:DLOGP1]:S
2012/12/13 17:51:54.088 [nutnr:DLOGP1]:Y
2012/12/13 17:51:54.312 [nutnr:DLOGP1]:1
2012/12/13 17:51:54.548 [nutnr:DLOGP1]:T
2012/12/13 17:51:54.788 [nutnr:DLOGP1]:Y
2012/12/13 17:51:55.011 [nutnr:DLOGP1]:3
2012/12/13 17:51:55.243 [nutnr:DLOGP1]:L
2012/12/13 17:51:55.483 [nutnr:DLOGP1]:Y
2012/12/13 17:51:55.702 [nutnr:DLOGP1]:1
2012/12/13 17:51:55.928 [nutnr:DLOGP1]:D
2012/12/13 17:51:56.154 [nutnr:DLOGP1]:Y
2012/12/13 17:51:56.373 [nutnr:DLOGP1]:0
2012/12/13 17:51:56.582 [nutnr:DLOGP1]:Q
2012/12/13 17:51:56.803 [nutnr:DLOGP1]:D
2012/12/13 17:51:57.055 [nutnr:DLOGP1]:O
2012/12/13 17:51:57.308 [nutnr:DLOGP1]:Y
2012/12/13 17:51:57.529 [nutnr:DLOGP1]:5
2012/12/13 17:51:57.738 [nutnr:DLOGP1]:Q
2012/12/13 17:51:57.948 [nutnr:DLOGP1]:Q
2012/12/13 17:51:58.181 [nutnr:DLOGP1]:Y
2012/12/13 17:51:58.659 [nutnr:DLOGP1]:Y
2012/12/13 17:51:59.747 [nutnr:DLOGP1]:2012/12/13 17:51:58
2012/12/13 17:52:00.166 [nutnr:DLOGP1]:Instrument started with initialize
"""


    def state_callback(self, pos, file_ingested):
        """ Call back method to watch what comes in via the position callback """
        log.trace("SETTING state_callback_value to " + str(pos))
        self.position_callback_value = pos
        self.file_ingested = file_ingested

    def pub_callback(self, pub):
        """ Call back method to watch what comes in via the publish callback """
        log.trace("SETTING publish_callback_value to " + str(pub))
        self.publish_callback_value = pub

    def setUp(self):
        ParserUnitTestCase.setUp(self)
        self.config = {
            DataSetDriverConfigKeys.PARTICLE_MODULE: 'mi.dataset.parser.nutnrb',
            DataSetDriverConfigKeys.PARTICLE_CLASS: 'NutnrbDataParticle'
            }

        # not a DataSourceLocation...its just the parser
        self.position = {StateKey.POSITION: 0}

        self.particle_a = NutnrbDataParticle("2012/12/13 15:31:08.726 SATNDC0239,2012348,15.518322,0.00,0.00,0.00,0.00,0.000000\n")
        self.particle_b = NutnrbDataParticle("2012/12/13 15:31:10.065 SATNLC0239,2012348,15.518666,-5.48,20.38,-31.12,0.59,0.000231\n")
        self.particle_c = NutnrbDataParticle("2012/12/13 15:31:11.405 SATNLC0239,2012348,15.519024,-6.38,24.24,-37.41,0.61,0.000191\n")
        self.particle_d = NutnrbDataParticle("2012/12/13 15:31:12.720 SATNLC0239,2012348,15.519397,-6.77,24.80,-38.00,0.62,0.000203\n")
        self.particle_e = NutnrbDataParticle("2012/12/13 15:31:14.041 SATNLC0239,2012348,15.519770,-5.28,18.39,-27.76,0.59,0.000212\n")
        self.particle_z = NutnrbDataParticle("2012/12/13 15:31:20.704 SATNLC0239,2012348,15.521605,-7.52,31.35,-49.03,0.63,0.000240\n")

        self.position_callback_value = None
        self.publish_callback_value = None

    def assert_result(self, result, position, particle):
        self.assertEqual(result, [particle])

        self.assertEqual(self.parser._state[StateKey.POSITION], position)
        self.assertEqual(self.position_callback_value[StateKey.POSITION], position)

        self.assert_(isinstance(self.publish_callback_value, list))
        self.assertEqual(self.publish_callback_value[0], particle)

    def test_happy_path(self):
        """
        Test the happy path of operations where the parser takes the input
        and spits out a valid data particle given the stream.
        """
        new_state = {}
        self.stream_handle = StringIO(NutnrbParserUnitTestCase.TEST_DATA)
        self.parser = NutnrbParser(self.config, new_state, self.stream_handle,
                                   self.state_callback, self.pub_callback)

        result = self.parser.get_records(1)
        self.assert_result(result, 2458, self.particle_a)

        result = self.parser.get_records(1)
        self.assert_result(result, 2544, self.particle_b)
        result = self.parser.get_records(1)
        self.assert_result(result, 2630, self.particle_c)
        result = self.parser.get_records(1)
        self.assert_result(result, 2716, self.particle_d)

        # no data left, dont move the position
        result = self.parser.get_records(1)
        self.assertEqual(result, [])
        self.assertEqual(self.parser._state[StateKey.POSITION], 2716)
        self.assertEqual(self.position_callback_value[StateKey.POSITION], 2716)

        self.assert_(isinstance(self.publish_callback_value, list))
        self.assertEqual(self.publish_callback_value[0], self.particle_d)

    def test_get_many(self):
        new_state = {}
        self.stream_handle = StringIO(NutnrbParserUnitTestCase.TEST_DATA)
        self.parser = NutnrbParser(self.config, new_state, self.stream_handle,
                                   self.state_callback, self.pub_callback)

        result = self.parser.get_records(2)
        self.assertEqual(result, [self.particle_a, self.particle_b])
        self.assertEqual(self.parser._state[StateKey.POSITION], 2544)
        self.assertEqual(self.position_callback_value[StateKey.POSITION], 2544)

        self.assertEqual(self.publish_callback_value[0], self.particle_a)
        self.assertEqual(self.publish_callback_value[1], self.particle_b)

    def test_bad_data(self):
        # There's a bad sample in the data! Ack! Skip it!
        new_state = {}
        self.stream_handle = StringIO(NutnrbParserUnitTestCase.BAD_TEST_DATA)
        self.parser = NutnrbParser(self.config, new_state, self.stream_handle,
                                   self.state_callback, self.pub_callback)

        result = self.parser.get_records(1)
        self.assert_result(result, 2603, self.particle_c)

    def test_long_stream(self):
        new_state = {}
        self.stream_handle = StringIO(NutnrbParserUnitTestCase.LONG_DATA)
        self.parser = NutnrbParser(self.config, new_state, self.stream_handle,
                                   self.state_callback, self.pub_callback)

        result = self.parser.get_records(11)
        self.assertEqual(result[-1], self.particle_z)
        self.assertEqual(self.parser._state[StateKey.POSITION], 3232)
        self.assertEqual(self.position_callback_value[StateKey.POSITION], 3232)
        self.assertEqual(self.publish_callback_value[-1], self.particle_z)

    def test_mid_state_start(self):
        new_state = {StateKey.POSITION:2628}
        self.stream_handle = StringIO(NutnrbParserUnitTestCase.TEST_DATA)
        self.parser = NutnrbParser(self.config, new_state, self.stream_handle,
                                   self.state_callback, self.pub_callback)
        result = self.parser.get_records(1)
        self.assert_result(result, 2716, self.particle_d)

    def reset_parser(self, state = {}):
        self.state_callback_values = []
        self.publish_callback_values = []
        self.stream_handle = StringIO(NutnrbParserUnitTestCase.TEST_DATA)
        self.parser = NutnrbParser(self.config, state, self.stream_handle,
                                   self.state_callback, self.pub_callback)

    def test_set_state(self):
        new_state = {StateKey.POSITION: 2544}
        self.stream_handle = StringIO(NutnrbParserUnitTestCase.TEST_DATA)
        self.parser = NutnrbParser(self.config, self.position, self.stream_handle,
                                   self.state_callback, self.pub_callback)
        result = self.parser.get_records(1)
        self.assert_result(result, 2458, self.particle_a)

        self.reset_parser(new_state)
        self.parser.set_state(new_state) # seek to after particle_b
        result = self.parser.get_records(1)

        #
        # If particles C and D appear, but the position is off
        # it is because you are not consuming newlines in your 
        # DATA_REGEX pattern
        #
        self.assert_result(result, 2630,  self.particle_c)
        result = self.parser.get_records(1)
        self.assert_result(result, 2716, self.particle_d)
