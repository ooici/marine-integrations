#!/usr/bin/env python

"""
@package mi.dataset.parser.test.test_nutnr_j_cspp
@file marine-integrations/mi/dataset/parser/test/test_nutnr_j_cspp.py
@author Emily Hahn
@brief Test code for a nutnr_j_cspp data parser
"""
import os

from nose.plugins.attrib import attr

from mi.core.log import get_logger ; log = get_logger()
from mi.core.exceptions import SampleException
from mi.core.instrument.data_particle import DataParticleKey

from mi.idk.config import Config

from mi.dataset.test.test_parser import ParserUnitTestCase
from mi.dataset.dataset_driver import DataSetDriverConfigKeys
from mi.dataset.parser.cspp_base import StateKey, DefaultHeaderKey, \
                                        METADATA_PARTICLE_CLASS_KEY, \
                                        DATA_PARTICLE_CLASS_KEY
from mi.dataset.parser.nutnr_j_cspp import NutnrJCsppParser, \
                                           NutnrJCsppMetadataTelemeteredDataParticle, \
                                           NutnrJCsppTelemeteredDataParticle, \
                                           NutnrJCsppMetadataRecoveredDataParticle, \
                                           NutnrJCsppRecoveredDataParticle


RESOURCE_PATH = os.path.join(Config().base_dir(),
			     'mi', 'dataset', 'driver', 'nutnr_j', 'cspp', 'resource')

@attr('UNIT', group='mi')
class NutnrJCsppParserUnitTestCase(ParserUnitTestCase):
    """
    nutnr_j_cspp Parser unit test suite
    """
    def state_callback(self, state, file_ingested):
        """ Call back method to watch what comes in via the position callback """
        self.state_callback_value = state
        self.file_ingested_value = file_ingested

    def pub_callback(self, pub):
        """ Call back method to watch what comes in via the publish callback """
        self.publish_callback_value = pub

    def exception_callback(self, exception_val):
        """ Call back method to watch what comes in via the exception callback """
        self.exception_callback_value = exception_val

    def setUp(self):
        ParserUnitTestCase.setUp(self)
        self.telem_config = {
            DataSetDriverConfigKeys.PARTICLE_MODULE: 'mi.dataset.parser.nutnr_j_cspp',
            DataSetDriverConfigKeys.PARTICLE_CLASS: None,
            DataSetDriverConfigKeys.PARTICLE_CLASSES_DICT: {
                METADATA_PARTICLE_CLASS_KEY: NutnrJCsppMetadataTelemeteredDataParticle,
                DATA_PARTICLE_CLASS_KEY: NutnrJCsppTelemeteredDataParticle
            }
        }

        self.recov_config = {
            DataSetDriverConfigKeys.PARTICLE_MODULE: 'mi.dataset.parser.nutnr_j_cspp',
            DataSetDriverConfigKeys.PARTICLE_CLASS: None,
            DataSetDriverConfigKeys.PARTICLE_CLASSES_DICT: {
                METADATA_PARTICLE_CLASS_KEY: NutnrJCsppMetadataRecoveredDataParticle,
                DATA_PARTICLE_CLASS_KEY: NutnrJCsppRecoveredDataParticle
            }
        }

        # metadata header dictionary
        self.header_dict = {
            DefaultHeaderKey.SOURCE_FILE: 'D:\Storage\Programs\OOI\Group 5\Correspondence\07_18_14 sample files\files\11079364.SNA',
            DefaultHeaderKey.PROCESSED: '07/18/2014 13:49:01',
            DefaultHeaderKey.USING_VERSION: '1.11',
            DefaultHeaderKey.DEVICE: 'SNA',
            DefaultHeaderKey.START_DATE: '04/17/2014'}

        # from 3222:4444
        self.particle_a_str = '1397774268.772\t0.000\ty\tSDB' \
            '\t2014\t107\t22.627037\t0.000\t0.000\t0.000\t0.000\t0.000\t484\t0\t1\t497\t490\t484\t' \
            '494\t481\t490\t486\t473\t495\t496\t503\t493\t494\t486\t480\t503\t482\t484\t494\t488\t' \
            '493\t503\t485\t493\t492\t484\t483\t486\t491\t481\t485\t485\t493\t481\t483\t490\t490\t' \
            '485\t488\t483\t499\t501\t489\t488\t488\t481\t487\t479\t491\t485\t496\t488\t495\t474\t' \
            '485\t474\t484\t482\t487\t497\t501\t489\t492\t485\t486\t488\t481\t477\t497\t478\t493\t' \
            '488\t491\t488\t491\t484\t485\t493\t493\t477\t487\t483\t485\t487\t485\t473\t461\t460\t' \
            '462\t482\t485\t489\t485\t489\t484\t492\t481\t490\t491\t482\t481\t487\t467\t483\t480\t' \
            '488\t474\t487\t490\t483\t469\t483\t489\t486\t481\t489\t482\t481\t477\t484\t487\t489\t' \
            '471\t471\t486\t468\t481\t488\t484\t481\t482\t489\t483\t485\t482\t489\t500\t488\t488\t' \
            '496\t483\t484\t481\t480\t499\t492\t503\t482\t482\t486\t481\t477\t490\t473\t491\t484\t' \
            '489\t493\t470\t469\t467\t468\t483\t478\t483\t482\t485\t481\t485\t491\t473\t491\t478\t' \
            '484\t490\t480\t491\t470\t475\t474\t465\t483\t473\t483\t464\t477\t479\t478\t491\t483\t' \
            '493\t480\t487\t482\t480\t481\t487\t485\t485\t477\t483\t501\t484\t491\t473\t487\t478\t' \
            '486\t499\t489\t485\t476\t480\t490\t493\t489\t482\t489\t470\t487\t482\t482\t488\t479\t' \
            '481\t485\t489\t480\t482\t465\t467\t474\t475\t485\t488\t487\t477\t477\t483\t480\t479\t' \
            '483\t474\t486\t482\t475\t483\t485\t492\t484\t483\t490\t478\t468\t475\t408\t0.000\t0.000' \
            '\t0.000\t246604\t35.657\t11.969\t0.092\t5.039\t57.381\t0.000\t0.000\t0.000\t0.000\t0.000' \
            '\t0\t-1.000\t-1.000\t-1.000\t36\n'
        # metadata arguments is a tuple, 1st item header dictionary, 2nd item 1st particle data match
        self.meta_telem_particle = NutnrJCsppMetadataTelemeteredDataParticle((self.header_dict, self.particle_a_str))

        # from 3222:4444
        self.telem_particle_a = NutnrJCsppTelemeteredDataParticle(self.particle_a_str)
        # from 4444:6136
        self.telem_particle_b = NutnrJCsppTelemeteredDataParticle('1397774270.706\t0.000\ty\tSLB\t2014' \
            '\t107\t22.627543\t11.962\t0.168\t-0.029\t-0.027\t0.000\t24886\t484\t1\t516\t515\t511\t515' \
            '\t523\t529\t528\t517\t531\t512\t515\t519\t537\t521\t517\t518\t519\t521\t528\t544\t569\t621' \
            '\t743\t999\t1388\t2020\t2951\t4265\t6010\t8258\t11016\t14300\t18061\t22265\t26749\t31334\t' \
            '35848\t40005\t43493\t46201\t47859\t48525\t48346\t47436\t46097\t44624\t43146\t41812\t40772' \
            '\t40016\t39545\t39401\t39552\t39975\t40661\t41554\t42696\t44017\t45536\t47208\t49022\t50842' \
            '\t52696\t54441\t55934\t57125\t57914\t58107\t57764\t56797\t55317\t53413\t51132\t48700\t46208' \
            '\t43741\t41442\t39306\t37373\t35653\t34187\t32882\t31780\t30855\t30151\t29578\t29201\t28970' \
            '\t28898\t28982\t29196\t29597\t30070\t30705\t31448\t32312\t33195\t34092\t35017\t35836\t36571' \
            '\t37108\t37426\t37533\t37352\t36905\t36209\t35337\t34291\t33155\t31949\t30740\t29591\t28465\t' \
            '27451\t26551\t25702\t24994\t24394\t23877\t23495\t23189\t23013\t22920\t22918\t23001\t23200\t' \
            '23481\t23800\t24218\t24708\t25230\t25829\t26463\t27147\t27884\t28640\t29406\t30237\t31060\t' \
            '31856\t32633\t33373\t34075\t34701\t35240\t35707\t36087\t36347\t36461\t36470\t36346\t36112\t' \
            '35790\t35288\t34739\t34113\t33394\t32685\t31936\t31123\t30329\t29575\t28812\t28077\t27350\t' \
            '26626\t25929\t25210\t24519\t23847\t23193\t22583\t22006\t21510\t21067\t20653\t20296\t19991\t' \
            '19733\t19515\t19318\t19179\t19022\t18897\t18752\t18617\t18512\t18389\t18273\t18160\t18060\t' \
            '17966\t17896\t17857\t17828\t17796\t17799\t17773\t17792\t17809\t17867\t17908\t17940\t17970\t' \
            '18012\t18050\t18081\t18113\t18103\t18110\t18098\t18051\t17997\t17927\t17815\t17691\t17550\t' \
            '17393\t17242\t17096\t16896\t16622\t16315\t15969\t15632\t15331\t15063\t14804\t14547\t14319\t' \
            '14112\t13884\t13699\t13607\t13496\t13336\t13064\t12810\t12586\t12391\t12173\t11995\t11838\t' \
            '11702\t11617\t11557\t11461\t11339\t11214\t11163\t11075\t10838\t10362\t9568\t8565\t11.438\t' \
            '11.063\t12.563\t246606\t35.743\t11.677\t12.002\t4.991\t511.803\t24.446\t2.634\t-2.808\t0.052' \
            '\t0.000\t0\t-1.000\t-1.000\t-1.000\t8D\n')
	# from 6136:7828
	self.telem_particle_c = NutnrJCsppTelemeteredDataParticle('1397774271.656\t0.000\ty\tSLB\t2014' \
	    '\t107\t22.627810\t12.084\t0.169\t-0.029\t-0.027\t0.000\t24863\t484\t1\t514\t501\t507\t510\t' \
	    '515\t516\t523\t525\t517\t515\t512\t512\t511\t535\t531\t531\t531\t535\t536\t550\t565\t641\t' \
	    '764\t978\t1375\t1990\t2923\t4245\t6006\t8238\t10990\t14277\t18028\t22218\t26677\t31248\t' \
	    '35767\t39910\t43402\t46121\t47783\t48422\t48259\t47374\t46036\t44554\t43076\t41750\t40702' \
	    '\t39941\t39488\t39373\t''39523\t39932\t40613\t41498\t42629\t43944\t45464\t47144\t48960\t' \
	    '50781\t52636\t54380\t55870\t57061\t57856\t58049\t57683\t56725\t55255\t53330\t51063\t48617' \
	    '\t46149\t43706\t41403\t39264\t37357\t35633\t34135\t32843\t31742\t30833\t30106\t29544\t29186' \
	    '\t28937\t28873\t28963\t29177\t29553\t30049\t30670\t31424\t32272\t33147\t34090\t34981\t35812' \
	    '\t36553\t37089\t37447\t37530\t37347\t36881\t36196\t35306\t34260\t33108\t31918\t30721\t29553' \
	    '\t28439\t27419\t26513\t25672\t24961\t24349\t23872\t23453\t23163\t22972\t22893\t22913\t22986' \
	    '\t23169\t23457\t23785\t24203\t24686\t25210\t25796\t26434\t27104\t27841\t28617\t29394\t30211' \
	    '\t31027\t31825\t32605\t33348\t34050\t34670\t35216\t35666\t36060\t36285\t36411\t36419\t36321' \
	    '\t36066\t35751\t35258\t34701\t34076\t33355\t32640\t31899\t31105\t30313\t29550\t28787\t28058' \
	    '\t27331\t26616\t25917\t25197\t24496\t23827\t23179\t22557\t21981\t21485\t21050\t20646\t20300' \
	    '\t19987\t19755\t19530\t19349\t19185\t19031\t18884\t18745\t18603\t18478\t18380\t18275\t18147' \
	    '\t18055\t17972\t17921\t17865\t17821\t17799\t17789\t17757\t17787\t17800\t17852\t17908\t17934' \
	    '\t17973\t17997\t18055\t18073\t18123\t18105\t18100\t18105\t18048\t17978\t17902\t17803\t17672' \
	    '\t17542\t17402\t17262\t17101\t16890\t16599\t16315\t15956\t15623\t15329\t15042\t14796\t14532' \
	    '\t14322\t14112\t13897\t13725\t13605\t13505\t13330\t13064\t12793\t12577\t12377\t12169\t11989' \
	    '\t11836\t11693\t11606\t11555\t11470\t11341\t11216\t11159\t11064\t10839\t10361\t9578\t8554\t' \
	    '11.438\t11.063\t12.563\t246607\t35.873\t11.739\t11.970\t5.032\t517.250\t24.266\t3.037\t-2.909' \
	    '\t0.118\t0.000\t0\t-1.000\t-1.000\t-1.000\tD9\n')

        self.meta_recov_particle = NutnrJCsppMetadataRecoveredDataParticle((self.header_dict, self.particle_a_str))
        self.recov_particle_a = NutnrJCsppRecoveredDataParticle(self.particle_a_str)

        self.file_ingested_value = None
        self.state_callback_value = None
        self.publish_callback_value = None
        self.exception_callback_value = None
        
    def assert_metadata(self, result, particle):
        log.debug('result data %s', result[0].raw_data[1].group(0))
        log.debug('particle data %s', particle.raw_data[1])
        self.assertEqual(result[0].raw_data[0], particle.raw_data[0])
        self.assertEqual(result[0].raw_data[1].group(0), particle.raw_data[1])
        
    def assert_result(self, result, position, particle, ingested, is_metadata=False):
        if is_metadata:
            log.debug('result data %s', result[0].raw_data[0])
            log.debug('particle data %s', particle.raw_data[0])
            self.assertEqual(result[0].raw_data[0], particle.raw_data[0])
            self.assertEqual(result[0].raw_data[1].group(0), particle.raw_data[1])
        else:
            self.assertEqual(result, [particle])
        self.assertEqual(self.file_ingested_value, ingested)

        self.assertEqual(self.parser._state[StateKey.POSITION], position)
        self.assertEqual(self.state_callback_value[StateKey.POSITION], position)

        self.assert_(isinstance(self.publish_callback_value, list))
        self.assertEqual(self.publish_callback_value[0], particle)

    def test_simple(self):
        """
        Read test data and pull out data particles one at a time.
        Assert that the results are those we expected.
        """
        stream_handle = open(os.path.join(RESOURCE_PATH,
                                          'short_SNA_SNA.txt'), 'rb')

        self.parser = NutnrJCsppParser(self.telem_config, None, stream_handle, 
                                  self.state_callback, self.pub_callback,
                                  self.exception_callback)

        result = self.parser.get_records(1)
	self.assert_result(result, 4444, self.meta_telem_particle, False, is_metadata=True)

    def test_get_many(self):
        """
        Read test data and pull out multiple data particles at one time.
        Assert that the results are those we expected.
        """
        pass

    def test_long_stream(self):
        """
        Test a long stream 
        """
        pass

    def test_mid_state_start(self):
        """
        Test starting the parser in a state in the middle of processing
        """
        pass

    def test_set_state(self):
        """
        Test changing to a new state after initializing the parser and 
        reading data, as if new data has been found and the state has
        changed
        """
        pass

    def test_bad_data(self):
        """
        Ensure that bad data is skipped when it exists.
        """
        pass
