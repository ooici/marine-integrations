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
from mi.core.exceptions import SampleException, UnexpectedDataException, \
                               RecoverableSampleException
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
                                           NutnrJCsppRecoveredDataParticle, \
                                           DATA_MATCHER


RESOURCE_PATH = os.path.join(Config().base_dir(),
			     'mi', 'dataset', 'driver', 'nutnr_j', 'cspp', 'resource')

PARTICLE_A_POS = 4444
PARTICLE_B_POS = 6136
PARTICLE_C_POS = 7828
PARTICLE_D_POS = 9055
PARTICLE_E_POS = 10282
END_LONG_POS = 226490

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
        self.exception_callback_value.append(exception_val)

    def setUp(self):
        ParserUnitTestCase.setUp(self)

        # metadata header dictionary
        header_dict = {
            DefaultHeaderKey.SOURCE_FILE: 'D:\\Storage\\Programs\\OOI\\Group 5\\Correspondence\\07_18_14 sample files\\files\\11079419.SNA',
            DefaultHeaderKey.PROCESSED: '07/18/2014 13:49:01',
            DefaultHeaderKey.USING_VERSION: '1.11',
            DefaultHeaderKey.DEVICE: 'SNA',
            DefaultHeaderKey.START_DATE: '04/17/2014'}

        # from 3222:4444
        particle_a_match = DATA_MATCHER.match('1397774268.772\t0.000\ty\tSDB' \
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
            '\t0\t-1.000\t-1.000\t-1.000\t36\n')
        # metadata arguments is a tuple, 1st item header dictionary, 2nd item 1st particle data match
        self.meta_telem_particle = NutnrJCsppMetadataTelemeteredDataParticle((header_dict, particle_a_match))
        # generate the dictionary so the timestamp is set
        self.meta_telem_particle.generate_dict()

        # from 3222:4444
        self.telem_particle_a = NutnrJCsppTelemeteredDataParticle(particle_a_match)
        # generate the dictionary so the timestamp is set
        self.telem_particle_a.generate_dict()

        # from 4444:6136
        particle_b_match = DATA_MATCHER.match('1397774270.706\t0.000\ty\tSLB\t2014' \
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
        self.telem_particle_b = NutnrJCsppTelemeteredDataParticle(particle_b_match)
        # generate the dictionary so the timestamp is set
        self.telem_particle_b.generate_dict()

        # from 6136:7828
        particle_c_match = DATA_MATCHER.match('1397774271.656\t0.000\ty\tSLB\t2014' \
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
        self.telem_particle_c = NutnrJCsppTelemeteredDataParticle(particle_c_match)
        # generate the dictionary so the timestamp is set
        self.telem_particle_c.generate_dict()

        # from 7828:9055
        particle_d_match = DATA_MATCHER.match('1397774272.683\t0.000\tn\tSDB\t2014\t107\t22.628126\t0.000' \
            '\t0.000\t0.000\t0.000\t0.000\t479\t0\t1\t489\t492\t483\t477\t481\t481\t487\t474\t481\t486\t475' \
            '\t487\t492\t485\t491\t485\t478\t472\t486\t489\t477\t491\t478\t475\t469\t483\t486\t473\t483\t468' \
            '\t461\t469\t465\t489\t485\t488\t489\t491\t478\t486\t475\t482\t489\t489\t473\t481\t481\t467\t481' \
            '\t484\t482\t474\t481\t477\t483\t488\t478\t484\t481\t481\t477\t494\t497\t473\t471\t487\t473\t485' \
            '\t478\t467\t474\t485\t475\t491\t496\t485\t488\t478\t479\t483\t481\t471\t470\t487\t470\t471\t461' \
            '\t473\t478\t474\t475\t477\t497\t483\t471\t475\t477\t484\t480\t499\t485\t474\t487\t493\t480\t479' \
            '\t476\t467\t459\t487\t470\t471\t468\t487\t473\t490\t485\t485\t481\t477\t479\t482\t472\t471\t465' \
            '\t471\t458\t487\t482\t479\t487\t482\t477\t493\t477\t473\t491\t473\t478\t488\t481\t492\t490\t483' \
            '\t477\t484\t472\t475\t465\t477\t488\t477\t477\t491\t477\t475\t477\t474\t478\t473\t479\t468\t481' \
            '\t488\t478\t486\t473\t467\t467\t471\t458\t476\t461\t481\t488\t487\t479\t481\t486\t477\t473\t485' \
            '\t478\t485\t490\t489\t492\t483\t481\t480\t472\t469\t460\t471\t473\t472\t477\t489\t473\t481\t480' \
            '\t469\t471\t467\t473\t477\t469\t471\t484\t491\t478\t494\t484\t495\t485\t484\t471\t471\t467\t475' \
            '\t471\t477\t491\t483\t487\t471\t467\t470\t470\t472\t488\t490\t486\t490\t484\t473\t473\t464\t488' \
            '\t480\t479\t475\t483\t493\t487\t471\t481\t470\t461\t459\t462\t474\t474\t482\t467\t423\t11.438\t' \
            '11.063\t12.563\t246606\t35.799\t11.866\t11.963\t5.010\t112.953\t0.000\t0.000\t0.000\t0.000\t0.000' \
            '\t0\t-1.000\t-1.000\t-1.000\t16\n')
        self.telem_particle_d = NutnrJCsppTelemeteredDataParticle(particle_d_match)
        # generate the dictionary so the timestamp is set
        self.telem_particle_d.generate_dict()

        particle_e_match = DATA_MATCHER.match('1397774273.831\t0.000\ty\tSDB\t2014\t107\t22.628356\t0.000\t' \
            '0.000\t0.000\t0.000\t0.000\t481\t0\t1\t489\t486\t479\t477\t475\t492\t487\t488\t490\t501\t491\t' \
            '488\t484\t477\t471\t490\t474\t477\t477\t487\t490\t491\t497\t473\t491\t489\t483\t473\t481\t482\t' \
            '494\t489\t497\t492\t475\t477\t484\t485\t473\t485\t478\t471\t477\t472\t459\t471\t490\t476\t475\t' \
            '485\t477\t485\t480\t483\t473\t486\t491\t489\t473\t487\t491\t493\t503\t489\t485\t480\t477\t473\t' \
            '480\t487\t493\t477\t485\t477\t485\t470\t494\t484\t479\t489\t491\t485\t479\t503\t484\t487\t477\t' \
            '477\t483\t481\t486\t491\t493\t477\t487\t492\t500\t492\t494\t489\t480\t485\t484\t487\t483\t475\t' \
            '487\t490\t489\t481\t481\t485\t472\t471\t481\t477\t483\t477\t473\t468\t475\t474\t474\t471\t474\t' \
            '470\t469\t479\t477\t474\t485\t478\t477\t482\t469\t476\t482\t481\t481\t499\t482\t473\t473\t470\t' \
            '477\t468\t469\t481\t489\t486\t493\t478\t479\t483\t482\t474\t487\t478\t480\t472\t475\t489\t484\t' \
            '473\t483\t477\t477\t483\t486\t473\t473\t477\t480\t491\t477\t467\t483\t484\t493\t495\t487\t479\t' \
            '485\t482\t465\t491\t476\t485\t488\t477\t471\t467\t458\t471\t472\t489\t491\t489\t481\t494\t473\t' \
            '480\t471\t481\t474\t480\t482\t483\t485\t470\t475\t477\t473\t472\t485\t475\t481\t488\t477\t482\t' \
            '473\t471\t467\t483\t482\t493\t493\t483\t491\t493\t485\t471\t487\t482\t475\t474\t478\t482\t485\t' \
            '484\t472\t471\t476\t486\t489\t497\t481\t483\t497\t475\t473\t477\t477\t474\t473\t394\t11.438\t' \
            '11.125\t12.563\t246606\t35.805\t11.911\t11.965\t5.049\t111.832\t0.000\t0.000\t0.000\t0.000\t0.000' \
            '\t0\t-1.000\t-1.000\t-1.000\t93\n')
        self.telem_particle_e = NutnrJCsppTelemeteredDataParticle(particle_e_match)
        # generate the dictionary so the timestamp is set
        self.telem_particle_e.generate_dict()

        self.meta_telem_e = NutnrJCsppMetadataTelemeteredDataParticle((header_dict, particle_e_match))
        # generate the dictionary so the timestamp is set
        self.meta_telem_e.generate_dict()

        # the particle at the end of the long file 224798:226490
        particle_long_end_match = DATA_MATCHER.match('1397774471.010\t0.000\tn\tSLB\t2014\t107' \
            '\t22.683184\t0.717\t0.010\t-0.022\t-0.022\t0.000\t24747\t482\t1\t517\t517\t508\t506\t500\t515\t522\t' \
            '523\t522\t531\t527\t521\t541\t521\t511\t502\t505\t521\t517\t532\t579\t654\t801\t1074\t1555\t2280\t' \
            '3357\t4853\t6855\t9373\t12459\t16069\t20157\t24643\t29400\t34168\t38801\t42966\t46394\t48931\t50337' \
            '\t50690\t50177\t48948\t47287\t45540\t43811\t42299\t41061\t40156\t39572\t39341\t39376\t39706\t40324\t' \
            '41152\t42189\t43440\t44902\t46512\t48277\t50040\t51858\t53556\t55002\t56169\t56916\t57085\t56756\t' \
            '55800\t54332\t52490\t50237\t47824\t45403\t43002\t40749\t38656\t36759\t35078\t33608\t32339\t31264\t' \
            '30381\t29670\t29113\t28756\t28544\t28461\t28567\t28789\t29176\t29656\t30283\t31026\t31858\t32728\t' \
            '33637\t34534\t35337\t36071\t36609\t36939\t37031\t36856\t36417\t35738\t34859\t33819\t32720\t31517\t' \
            '30349\t29192\t28092\t27080\t26165\t25355\t24635\t24048\t23543\t23143\t22871\t22676\t22585\t22611\t' \
            '22698\t22893\t23145\t23489\t23900\t24345\t24859\t25459\t26070\t26725\t27465\t28224\t28995\t29793\t' \
            '30585\t31380\t32165\t32906\t33587\t34202\t34747\t35187\t35568\t35817\t35926\t35943\t35834\t35614\t' \
            '35248\t34794\t34238\t33620\t32904\t32195\t31461\t30669\t29921\t29156\t28419\t27700\t26972\t26264\t' \
            '25577\t24866\t24175\t23514\t22852\t22267\t21712\t21220\t20795\t20396\t20039\t19735\t19502\t19285\t' \
            '19096\t18946\t18786\t18646\t18514\t18358\t18247\t18175\t18048\t17932\t17837\t17756\t17702\t17653\t' \
            '17614\t17600\t17585\t17561\t17595\t17590\t17655\t17716\t17744\t17780\t17818\t17867\t17909\t17921\t' \
            '17911\t17912\t17898\t17854\t17789\t17715\t17626\t17497\t17367\t17221\t17075\t16923\t16727\t16456\t' \
            '16152\t15793\t15469\t15189\t14904\t14641\t14390\t14165\t13957\t13747\t13568\t13465\t13354\t13191\t' \
            '12936\t12676\t12460\t12258\t12053\t11863\t11717\t11582\t11506\t11437\t11349\t11225\t11093\t11037\t' \
            '10955\t10741\t10251\t9467\t8475\t12.313\t13.188\t13.188\t246633\t34.853\t11.745\t11.996\t4.988\t' \
            '493.629\t26.120\t0.411\t-3.311\t0.583\t0.000\t0\t-1.000\t-1.000\t-1.000\t43\n')
        self.telem_particle_long = NutnrJCsppTelemeteredDataParticle(particle_long_end_match)
        # generate the dictionary so the timestamp is set
        self.telem_particle_long.generate_dict()

        # recovered particles using the same data as telemetered particles
        self.meta_recov_particle = NutnrJCsppMetadataRecoveredDataParticle((header_dict, particle_a_match))
        self.meta_recov_particle.generate_dict()
        self.recov_particle_a = NutnrJCsppRecoveredDataParticle(particle_a_match)
        self.recov_particle_a.generate_dict()
        self.recov_particle_b = NutnrJCsppRecoveredDataParticle(particle_b_match)
        self.recov_particle_b.generate_dict()
        self.recov_particle_c = NutnrJCsppRecoveredDataParticle(particle_c_match)
        self.recov_particle_c.generate_dict()
        self.recov_particle_d = NutnrJCsppRecoveredDataParticle(particle_d_match)
        self.recov_particle_d.generate_dict()
        self.recov_particle_e = NutnrJCsppRecoveredDataParticle(particle_e_match)
        self.recov_particle_e.generate_dict()

        self.file_ingested_value = None
        self.state_callback_value = None
        self.publish_callback_value = None
        self.exception_callback_value = []

    def assert_equal_regex(self, match1, match2):
        """
        A data regex match cannot be directly equal to another data regex match,
        pull out the matching raw data result to see if the regexes matched the same
        data
        """
        self.assertEqual(match1.group(0), match2.group(0))

    def assert_result(self, result, position, particle, ingested, is_metadata=False):
        """
        Assert two particles and the states after that particle are equal
        """
        self.assert_(isinstance(self.publish_callback_value, list))
        if is_metadata:
            self.assert_metadata(result, particle)
        else:
            self.assert_data(result, particle)

        self.assert_timestamp(result, particle)
        self.assert_position(position)
        # compare if the file is ingested
        self.assertEqual(self.file_ingested_value, ingested)

    def assert_metadata(self, result, particle, result_index=0):
        """
        Assert two metadata particles raw data matches
        """
        # the data regex match is passed in as the second argument to the metadata,
        # need to pull out the string for comparison since regex results cannot be
        # directly compared
        self.assertEqual(result[result_index].raw_data[0], particle.raw_data[0])
        self.assert_equal_regex(result[result_index].raw_data[1], particle.raw_data[1])

        self.assertEqual(self.publish_callback_value[result_index].raw_data[0],
                         particle.raw_data[0])
        self.assert_equal_regex(self.publish_callback_value[result_index].raw_data[1],
                                particle.raw_data[1])

    def assert_data(self, result, particle, result_index=0):
        # the data regex match is passed in as the argument to the data particle,
        # need to pull out the string for comparison since regex results cannot be
        # directly compared
        self.assert_equal_regex(result[result_index].raw_data, particle.raw_data)
        self.assert_equal_regex(self.publish_callback_value[result_index].raw_data,
                                particle.raw_data)

    def assert_timestamp(self, result, particle, result_index=0):
        """
        Compare the timestamp of two particles
        """
        allowed_diff = .000001
        self.assertTrue(abs(result[result_index].contents[DataParticleKey.INTERNAL_TIMESTAMP] - \
                 particle.contents[DataParticleKey.INTERNAL_TIMESTAMP]) <= allowed_diff)

    def assert_data_and_timestamp(self, result, particle, result_index=0):
        """
        Combine asserting data and timestamp
        """
        self.assert_data(result, particle, result_index)
        self.assert_timestamp(result, particle, result_index)

    def assert_metadata_and_timestamp(self, result, particle, result_index=0):
        self.assert_metadata(result, particle, result_index)
        self.assert_timestamp(result, particle, result_index)

    def assert_position(self, position):
        """
        Assert that the position in the parser state and state callback match
        the expected position
        """
        self.assertEqual(self.parser._state[StateKey.POSITION], position)
        self.assertEqual(self.state_callback_value[StateKey.POSITION], position)

    def create_parser(self, stream_handle, telem_flag=True, state=None):
        """
        Initialize the parser with the given stream handle, using the
        telemetered config if the flag is set, recovered if it is not
        """
        if telem_flag:
            # use telemetered config
            config = {
                DataSetDriverConfigKeys.PARTICLE_MODULE: 'mi.dataset.parser.nutnr_j_cspp',
                DataSetDriverConfigKeys.PARTICLE_CLASS: None,
                DataSetDriverConfigKeys.PARTICLE_CLASSES_DICT: {
                    METADATA_PARTICLE_CLASS_KEY: NutnrJCsppMetadataTelemeteredDataParticle,
                    DATA_PARTICLE_CLASS_KEY: NutnrJCsppTelemeteredDataParticle
                }
            }
        else:
            # use recovered config
            config = {
                DataSetDriverConfigKeys.PARTICLE_MODULE: 'mi.dataset.parser.nutnr_j_cspp',
                DataSetDriverConfigKeys.PARTICLE_CLASS: None,
                DataSetDriverConfigKeys.PARTICLE_CLASSES_DICT: {
                    METADATA_PARTICLE_CLASS_KEY: NutnrJCsppMetadataRecoveredDataParticle,
                    DATA_PARTICLE_CLASS_KEY: NutnrJCsppRecoveredDataParticle
                }
            }

        self.parser = NutnrJCsppParser(config, state, stream_handle, 
                                  self.state_callback, self.pub_callback,
                                  self.exception_callback)

    def test_simple_telem(self):
        """
        Read test data and pull out data particles one at a time.
        Assert that the results are those we expected.
        """
        stream_handle = open(os.path.join(RESOURCE_PATH,
                                          'short_SNA_SNA.txt'), 'rb')

	self.create_parser(stream_handle)

        # get and compare the metadata particle
        result = self.parser.get_records(1)
        self.assert_result(result, 0, self.meta_telem_particle, False, is_metadata=True)
        # get and compare the first data particle
        result = self.parser.get_records(1)
        self.assert_result(result, PARTICLE_A_POS, self.telem_particle_a, False)
        result = self.parser.get_records(1)
        self.assert_result(result, PARTICLE_B_POS, self.telem_particle_b, False)
        result = self.parser.get_records(1)
        self.assert_result(result, PARTICLE_C_POS, self.telem_particle_c, False)
        result = self.parser.get_records(1)
        self.assert_result(result, PARTICLE_D_POS, self.telem_particle_d, False)
        result = self.parser.get_records(1)
        self.assert_result(result, PARTICLE_E_POS, self.telem_particle_e, True)

        # confirm no exceptions occurred
        self.assertEqual(self.exception_callback_value, [])

        stream_handle.close()

    def test_simple_recov(self):
        """
        Read test data and pull out data particles one at a time.
        Assert that the results are those we expected.
        """
        stream_handle = open(os.path.join(RESOURCE_PATH,
                                          'short_SNA_SNA.txt'), 'rb')

	self.create_parser(stream_handle, telem_flag=False)

        # get and compare the metadata particle
        result = self.parser.get_records(1)
        self.assert_result(result, 0, self.meta_recov_particle, False, is_metadata=True)
        # get and compare the first data particle
        result = self.parser.get_records(1)
        self.assert_result(result, PARTICLE_A_POS, self.recov_particle_a, False)
        result = self.parser.get_records(1)
        self.assert_result(result, PARTICLE_B_POS, self.recov_particle_b, False)
        result = self.parser.get_records(1)
        self.assert_result(result, PARTICLE_C_POS, self.recov_particle_c, False)
        result = self.parser.get_records(1)
        self.assert_result(result, PARTICLE_D_POS, self.recov_particle_d, False)
        result = self.parser.get_records(1)
        self.assert_result(result, PARTICLE_E_POS, self.recov_particle_e, True)

        # confirm no exceptions occurred
        self.assertEqual(self.exception_callback_value, [])

        stream_handle.close()

    def test_get_many(self):
        """
        Read test data and pull out multiple data particles at one time.
        Assert that the results are those we expected.
        """
        stream_handle = open(os.path.join(RESOURCE_PATH,
                                          'short_SNA_SNA.txt'), 'rb')

        self.create_parser(stream_handle)

        result = self.parser.get_records(6)

        self.assert_(isinstance(self.publish_callback_value, list))
        # compare particle raw data values
        self.assert_metadata_and_timestamp(result, self.meta_telem_particle)
        self.assert_data_and_timestamp(result, self.telem_particle_a, result_index=1)
        self.assert_data_and_timestamp(result, self.telem_particle_b, result_index=2)
        self.assert_data_and_timestamp(result, self.telem_particle_c, result_index=3)
        self.assert_data_and_timestamp(result, self.telem_particle_d, result_index=4)
        self.assert_data_and_timestamp(result, self.telem_particle_e, result_index=5)
        
        # compare position and file ingested from the state
        self.assert_position(PARTICLE_E_POS)
        self.assertEqual(self.file_ingested_value, True)
        # confirm no exceptions occurred
        self.assertEqual(self.exception_callback_value, [])

	stream_handle.close()

    def test_long_stream(self):
        """
        Test a long stream 
        """
        stream_handle = open(os.path.join(RESOURCE_PATH,
                                          '11079419_SNA_SNA.txt'), 'rb')

        self.create_parser(stream_handle)

        result = self.parser.get_records(172)
        self.assertEqual(len(result), 172)

        self.assert_(isinstance(self.publish_callback_value, list))
        # compare particle raw data values, check the particles we know from
        # the beginning, then the last particle in the file
        self.assert_metadata_and_timestamp(result, self.meta_telem_particle)
        self.assert_data_and_timestamp(result, self.telem_particle_a, result_index=1)
        self.assert_data_and_timestamp(result, self.telem_particle_b, result_index=2)
        self.assert_data_and_timestamp(result, self.telem_particle_c, result_index=3)
        self.assert_data_and_timestamp(result, self.telem_particle_d, result_index=4)
        self.assert_data_and_timestamp(result, self.telem_particle_e, result_index=5)
        self.assert_data_and_timestamp(result, self.telem_particle_long, result_index=-1)

        # compare position and file ingested from the state
        self.assert_position(END_LONG_POS)
        self.assertEqual(self.file_ingested_value, True)
        # confirm no exceptions occurred
        self.assertEqual(self.exception_callback_value, [])

	stream_handle.close()

    def test_mid_state_start(self):
        """
        Test starting the parser in a state in the middle of processing
        """
        # set the state so that the metadata, particle A and B have been read
        new_state = {StateKey.POSITION: PARTICLE_B_POS,
                     StateKey.METADATA_EXTRACTED: True}

        stream_handle = open(os.path.join(RESOURCE_PATH,
                                          'short_SNA_SNA.txt'), 'rb')

        self.create_parser(stream_handle, state=new_state)

        # ask for more records but should only get 3 back: c, d, and e
        result = self.parser.get_records(6)
        self.assertEqual(len(result), 3)

        self.assert_(isinstance(self.publish_callback_value, list))
        # compare particle raw data values
        self.assert_data_and_timestamp(result, self.telem_particle_c, result_index=0)
        self.assert_data_and_timestamp(result, self.telem_particle_d, result_index=1)
        self.assert_data_and_timestamp(result, self.telem_particle_e, result_index=2)

        # compare position and file ingested from the state
        self.assert_position(PARTICLE_E_POS)
        self.assertEqual(self.file_ingested_value, True)
        # confirm no exceptions occurred
        self.assertEqual(self.exception_callback_value, [])

	stream_handle.close()

    def test_set_state(self):
        """
        Test changing to a new state after initializing the parser and 
        reading data, as if new data has been found and the state has
        changed
        """
        # set the state so that the metadata, particle A, B, and C have been read
        new_state = {StateKey.POSITION: PARTICLE_C_POS,
                     StateKey.METADATA_EXTRACTED: True}

        stream_handle = open(os.path.join(RESOURCE_PATH,
                                          'short_SNA_SNA.txt'), 'r')

        self.create_parser(stream_handle)

        # get metadata and A
        result = self.parser.get_records(2)

        # compare particle raw data values and timestamp
        self.assert_metadata_and_timestamp(result, self.meta_telem_particle)
        self.assert_data_and_timestamp(result, self.telem_particle_a, result_index=1)

        # compare position and file ingested from the state
        self.assert_position(PARTICLE_A_POS)
        self.assertEqual(self.file_ingested_value, False)

        # now change the state to skip over B and C
        self.parser.set_state(new_state)

        # confirm we get D and E now
        result = self.parser.get_records(2)
        # compare particle raw data values and timestamp
        self.assert_data_and_timestamp(result, self.telem_particle_d, result_index=0)
        self.assert_data_and_timestamp(result, self.telem_particle_e, result_index=1)

        # compare position and file ingested from the state
        self.assert_position(PARTICLE_E_POS)
        self.assertEqual(self.file_ingested_value, True)

        # confirm no exceptions occurred
        self.assertEqual(self.exception_callback_value, [])

        stream_handle.close()

    def test_bad_data(self):
        """
        Ensure that bad data is skipped when it exists.
        """
        # bad data file has:
        # 1 bad status
        # particle A has bad timestamp
        # particle B has bad dark fit
        # particle C has bad frame type
        # particle D has bad year
        stream_handle = open(os.path.join(RESOURCE_PATH,
                                          'bad_SNA_SNA.txt'), 'r')

        self.create_parser(stream_handle)

        # get E, since it is first it will generate a metadata
        result = self.parser.get_records(1)
        self.assert_result(result, 0, self.meta_telem_e, False, is_metadata=True)
        result = self.parser.get_records(1)
        # bytes in file changed due to making file 'bad'
        self.assert_result(result, 10257, self.telem_particle_e, True)

        # should have had 5 exceptions by now
        self.assertEqual(len(self.exception_callback_value), 5)

	for exception in self.exception_callback_value:
	    self.assert_(isinstance(exception, RecoverableSampleException))

    def test_missing_source_file(self):
        """
        Test that a file with a missing source file path in the header
        fails to create a metadata particle and throws an exception
        """
        stream_handle = open(os.path.join(RESOURCE_PATH,
                                          'no_source_file_SNA_SNA.txt'), 'r')

        self.create_parser(stream_handle)

        # get A-E, without metadata
        result = self.parser.get_records(5)

        self.assert_data_and_timestamp(result, self.telem_particle_a, result_index=0)
        self.assert_data_and_timestamp(result, self.telem_particle_b, result_index=1)
        self.assert_data_and_timestamp(result, self.telem_particle_c, result_index=2)
        self.assert_data_and_timestamp(result, self.telem_particle_d, result_index=3)
        self.assert_data_and_timestamp(result, self.telem_particle_e, result_index=4)

        # compare file ingested from the state
        self.assertEqual(self.file_ingested_value, True)
        # confirm no exceptions occurred
        self.assertEqual(len(self.exception_callback_value), 1)
        self.assert_(isinstance(self.exception_callback_value[0], RecoverableSampleException))

        stream_handle.close()

    def test_no_header(self):
        """
        Test that a file with no header lines
        fails to create a metadata particle and throws an exception
        """
        stream_handle = open(os.path.join(RESOURCE_PATH,
                                          'no_header_SNA_SNA.txt'), 'r')

        self.create_parser(stream_handle)

        # get A-E, without metadata
        result = self.parser.get_records(5)

        self.assert_data_and_timestamp(result, self.telem_particle_a, result_index=0)
        self.assert_data_and_timestamp(result, self.telem_particle_b, result_index=1)
        self.assert_data_and_timestamp(result, self.telem_particle_c, result_index=2)
        self.assert_data_and_timestamp(result, self.telem_particle_d, result_index=3)
        self.assert_data_and_timestamp(result, self.telem_particle_e, result_index=4)

        # compare file ingested from the state
        self.assertEqual(self.file_ingested_value, True)
        # confirm no exceptions occurred
        self.assertEqual(len(self.exception_callback_value), 1)
        self.assert_(isinstance(self.exception_callback_value[0], RecoverableSampleException))

        stream_handle.close()
