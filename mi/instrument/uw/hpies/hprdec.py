#!/usr/bin/env python2
# hprdec.py -- decode and plot ascii files of raw data from hprtst.py and hefcf2.py
# hprtst.py is a real-time program for hpies-rsn
# hefcf2.py converts binary compact flash files from hefrun.c to ascii files like hprtst.py makes
# see ../man/users-manual.txt for a description of the files
# John Dunlap, dunlap@apl.uw.edu
# updated April 22, 2014

"""
./hprdec.py -e -s 10 -l 60 -n 15 -p 3 hefcf2-odir/H[12345]-{010,050,100,150,200,250,300,350}.gz
  Plots 15 half-cycles (each 240 s) of raw ef data in each frame.
  Also plots above minus 3rd-order polynomial fit to unpinched data.
  First 15 s (-s 10 scans at 1.5 s each) not shown.
  Note that 15 s is 5 time-constants of preamp which has 1 pole RC at 3 s.
  pdf/raw-ef-cat

./hprdec.py -c -s 10 hefcf2-odir/H[12345]-{010,050,100,150,200,250,300,350}.gz
  plots resistance check (aka cal), one half-cycle per pdf
  pdf/raw-cal/

./hprdec.py -e -s 10 -l 10 hefcf2-odir/H[12345]-{010,050,100,150,200,250,300,350}.gz
  plots raw ef, one half-cycle per pdf
  pdf/raw-ef/

./hprdec.py -m -l 10 hefcf2-odir/H[12345]-{010,050,100,150,200,250,300,350}.gz
  plots raw motor current, one half-cycle per pdf
  pdf/raw-mot/

./hprdec.py -n 10 -m -l 50 hefcf2-odir/H[12345]-{010,050,100,150,200,250,300,350}.gz
  plots concatenated raw motor current
  pdf/raw-mot-cat/

./hprdec.py -a -s 10 hefcf2-odir/H[12345]-{010,050,100,150,200,250,300,350}.gz
  plots averages, skipping first 15 s after each pinch
  pdf/hef-avg/

./hprdec.py run1
./hprdec.py -s 10 -o hefcf2-odir/H2-010

./hprdec.py -m -l 10 tests/apr15a       # raw motor current
./hprdec.py -c -s 3 tests/apr15a       # raw cal
./hprdec.py -e -s 3 tests/apr15a       # raw ef
./hprdec.py -e -s 3 -n 5 tests/apr15a  # raw ef concatenated for several HCY
  Tests Apr 15, 2014 mods to stm and hef firmware on HEF-006, IES-309

"""

from __future__ import print_function

import os
import sys
from optparse import OptionParser
import collections
import gzip
from datetime import datetime, timedelta
import glob

import numpy as np

import matplotlib.pyplot as plt
from matplotlib.ticker import MaxNLocator
from crclib import crc3kerm
from okmc_info import okmc_info


def check_crc(line):
    global count_bad_crc_check, count_crc_ok, count_crc_missing

    i = line.find('#')
    j = line.rfind('*')
    if i < 0 or j < 0:
        count_crc_missing += 1
        return
    sect = line[i:j]
    # print('i=',i,'j=',j,'tst=['+tst+']')
    crc_computed = crc3kerm(sect)

    try:
        crc_rcv = int(line[j + 1:j + 5], 16)
    except:
        crc_rcv = None
        print('bad crc decode, lineno=', lineno, 'linein=[' + linein + ']')
        count_bad_crc_decode += 1

    if crc_rcv != None:
        if crc_computed != crc_rcv:
            print('crc error, lineno=', lineno, 'linein=[' + linein + ']')
            count_bad_crc_check += 1
        else:
            count_crc_ok += 1


def split_aux(line):
    global aux_split
    global ies_secs_diff

    i = line.find('AUX,')
    j = line.rfind('*')
    if i < 0 or j < 0:
        aux_split = None
        #   print('bad AUX line')
        #   print_info_and_exit()
        return
    aux_split = line[i:j].split(',')
    if len(aux_split) != 13:
        print('AUX wrong split len:', len(aux_split))
        print('discarded aux_split:', aux_split)
        print_info_and_exit()
    try:
        ies_secs_diff = int(aux_split[1]) - int(aux_split[12])
    except:
        print('cannot decode aux split')
        print_info_and_exit()


def split_tod(line):
    global tod_split
    global stm_secs_diff
    i = line.find('#')
    j = line.rfind('*')
    if i < 0 or j < 0:
        print('bad TOD line')
        print_info_and_exit()
    #   tod_split = None
    #   return
    tod_split = line[i:j].split(',')
    if len(tod_split) == 3:
        try:
            stm_secs_diff = int(tod_split[2]) - int(tod_split[1])
        except:
            print('cannot decode TOD line')
            print_info_and_exit()


def split_hef(line):
    global hef_split
    i = line.find('#')
    j = line.rfind('*')
    if i < 0 or j < 0:
        print('bad HEF line')
        print_info_and_exit()
    #   hef_split = None
    #   return
    hef_split = line[i:j].split()


def decode_hef_hdr():
    global count_EC
    global count_M, count_E
    global count_C, count_hef_unknown
    global navg_mot, navg_ef, navg_cal
    global ab, navg
    global nscan, iscan
    global iend, uxt_ibeg
    global off_ef, off_cal, sf_ef, sf_cal, sf_mot

    if len(hef_split) < 1:
        print('len(hef_split)=', len(hef_split))
        print_info_and_exit()

    # check if this is a header for EF, cal or motor
    if hef_split[0].find('#3__HE') == 0:
        if hef_split[0] == '#3__HE04':
            if len(hef_split) != 12:
                print('HE04 wrong split len:', len(hef_split))
                print('hef_split:', hef_split)
                print_info_and_exit()

            try:
                typ = hef_split[1]
                ab = hef_split[2]
                ibeg = int(hef_split[3])
                iend = int(hef_split[4])
                hcno = int(hef_split[5])
                uxt = int(hef_split[6])
                ticks = int(hef_split[7])
                navg_mot = int(hef_split[8])
                navg_ef = int(hef_split[9])
                navg_cal = int(hef_split[10])
            except:
                print('error decoding HE04')
                print_info_and_exit()

            global nskip_ef, nskip_cal
            nskip_ef = int(options.tskip / (navg_ef * tsamp_ef))
            nskip_cal = int(options.tskip / (navg_cal * tsamp_ef))

            global tskip_ef, tskip_cal
            tskip_ef = nskip_ef * navg_ef * tsamp_ef
            tskip_cal = nskip_cal * navg_cal * tsamp_ef

            vref = 2.5  # ADC Vref
            preamp = 800  # preamp gain
            divider = 0.1773  # resistor network at ADC input
            off_ef = pow(2, 15) * navg_ef
            off_cal = pow(2, 15) * navg_cal
            sf_ef = vref / pow(2, 16) / preamp / divider * 1e6 / navg_ef  # uV
            sf_cal = vref / pow(2, 16) / preamp / divider * 1e6 / navg_cal  # uV
            sf_mot = vref / pow(2, 16) * 1e3 / navg_mot  # mA

            if uxt < 1372636800:  # July 1, 2013
                uxt_ibeg = uxt - (iend - ibeg) * tsamp_ef  # OKMC & before
            elif uxt > 1396310400:  # April 1, 2014
                uxt_ibeg = uxt  # RSN & later
            else:
                print('not sure how to compute uxt_ibeg between OKMC and RSN')
                print_info_and_exit()

            if uxt_poly_ref:
                # align HEF time to IES time using polynomial fits
                uxt_ibeg = uxt_ibeg - np.polyval(uxt_poly_coef, uxt_ibeg - uxt_poly_ref)

            if typ == 'f' or typ == 'r':
                count_M += 1
                navg = navg_mot
            elif typ == 'E':
                count_E += 1
                count_EC += 1
                navg = navg_ef
            elif typ == 'C':
                count_C += 1
                count_EC += 1
                navg = navg_cal
            else:
                count_hef_unknown += 1
                print('unknown HEF hdr type')
                print_info_and_exit()

            if ab != 'a' and ab != 'b':
                print('ab should be a or b')
                print_info_and_exit()

            if navg_mot < 1 or navg_ef < 1 or navg_cal < 1:
                print('navg_mot, navg_ef, navg_cal must all be > 0')
                print_info_and_exit()

            nscan = int((iend - ibeg) / navg)
            iscan = 0

        else:
            print('unknown hef_hdr')
            print_info_and_exit()


def decode_cal_status():
    global CAL_STATUS, plot_raw_cal_flag

    if hef_split[0].find('#3__SC') == 0:
        CAL_STATUS = collections.namedtuple('CAL_STATUS', [])
        if len(hef_split) != 4:
            print('cal status header record should have 4 tokens')
            print('cal status hdr:', hef_split)
            print_info_and_exit()
        CAL_STATUS.i0 = int(hef_split[1])
        CAL_STATUS.ns = int(hef_split[2])
        CAL_STATUS.nl = int(hef_split[3])
        CAL_STATUS.lno = 0
        CAL_STATUS.j = []
        CAL_STATUS.s = []

    if hef_split[0].find('#3__Sc') == 0:
        if len(hef_split) != 3:
            print('cal status data record should have 3 tokens')
            print('cal status data:', hef_split)
            print_info_and_exit()
        CAL_STATUS.lno += 1
        CAL_STATUS.j.append(int(hef_split[1]))
        CAL_STATUS.s.append(int(hef_split[2]))

        if CAL_STATUS.lno == CAL_STATUS.nl:
            expand_cal_status()
            if plot_raw_cal_flag:
                plot_raw_cal_flag = False
                if options.limEC == 0 or count_EC <= options.limEC:
                    if options.ncat == 0:
                        plot_raw_cal()
                    else:
                        plot_raw_cal_cat()


def expand_cal_status():
    global CAL_STATUS

    CAL_STATUS.stat_fast = np.tile(np.nan, CAL_STATUS.ns)
    jn = 0
    sn = CAL_STATUS.s[0]
    for i in range(1, CAL_STATUS.nl):
        jp = jn
        jn = CAL_STATUS.j[i]
        sp = sn
        sn = CAL_STATUS.s[i]
        CAL_STATUS.stat_fast[range(jp, jn)] = np.tile(sp, jn - jp)
    CAL_STATUS.stat_fast[range(jn, CAL_STATUS.ns)] = np.tile(sn, CAL_STATUS.ns - jn)
    if len(CAL_STATUS.stat_fast) != CAL_STATUS.ns:
        print('CAL_STATUS.stat_fast has wrong length')
        print_info_and_exit()
    jnz = np.nonzero(np.isnan(CAL_STATUS.stat_fast))[0]
    if len(jnz) > 0:
        print('not all CAL_STATUS.stat_fast filled in')
        print('  len(jnz)=', len(jnz))
        print('  jnz=', jnz)
        print_info_and_exit()
    try:
        CAL_STATUS.stat_pick = CAL_STATUS.stat_fast[HCYC.ind];
    except:
        print('cannot compute CAL_STATUS.stat_pick')
        print_info_and_exit()
    j16 = np.nonzero(CAL_STATUS.stat_pick == 16)[0]
    j17 = np.nonzero(CAL_STATUS.stat_pick == 17)[0]
    if len(j16) + len(j17) != len(CAL_STATUS.stat_pick):
        print('some unknown values in CAL_STATUS.stat_pick')
        print_info_and_exit()


def decode_mot_status():
    global MOT_STATUS, plot_raw_mot_flag

    if hef_split[0].find('#3__SM') == 0:
        MOT_STATUS = collections.namedtuple('MOT_STATUS', [])
        if len(hef_split) != 4:
            print('mot status header record should have 4 tokens')
            print('mot status hdr:', hef_split)
            print_info_and_exit()
        MOT_STATUS.i0 = int(hef_split[1])
        MOT_STATUS.ns = int(hef_split[2])
        MOT_STATUS.nl = int(hef_split[3])
        MOT_STATUS.lno = 0
        MOT_STATUS.j = []
        MOT_STATUS.s = []

    if hef_split[0].find('#3__Sm') == 0:
        if len(hef_split) != 3:
            print('mot status data record should have 3 tokens')
            print('mot status data:', hef_split)
            print_info_and_exit()
        MOT_STATUS.lno += 1
        # j is index where s first appears:
        MOT_STATUS.j.append(int(hef_split[1]))
        MOT_STATUS.s.append(int(hef_split[2]))

        if MOT_STATUS.lno == MOT_STATUS.nl:
            expand_mot_status()
            if plot_raw_mot_flag:
                plot_raw_mot_flag = False
                if options.limEC == 0 or count_EC <= options.limEC:
                    if options.ncat == 0:
                        plot_raw_mot()
                    else:
                        plot_raw_mot_cat()


def expand_mot_status():
    global MOT_STATUS

    MOT_STATUS.stat_fast = np.tile(np.nan, MOT_STATUS.ns)
    jn = 0
    sn = MOT_STATUS.s[0]
    for i in range(1, MOT_STATUS.nl):
        jp = jn
        jn = MOT_STATUS.j[i]
        sp = sn
        sn = MOT_STATUS.s[i]
        # now jn is index where sn first appears
        MOT_STATUS.stat_fast[range(jp, jn)] = np.tile(sp, jn - jp)
    MOT_STATUS.stat_fast[range(jn, MOT_STATUS.ns)] = np.tile(sn, MOT_STATUS.ns - jn)
    if len(MOT_STATUS.stat_fast) != MOT_STATUS.ns:
        print('MOT_STATUS.stat_fast has wrong length')
        print_info_and_exit()
    jnz = np.nonzero(np.isnan(MOT_STATUS.stat_fast))[0]
    if len(jnz) > 0:
        print('not all MOT_STATUS.stat_fast filled in')
        print('  len(jnz)=', len(jnz))
        print('  jnz=', jnz)
        print_info_and_exit()
    try:
        MOT_STATUS.stat_pick = MOT_STATUS.stat_fast[HCYM.ind];
    except:
        print('cannot compute MOT_STATUS.stat_pick')
        print_info_and_exit()


def append_hef_data():
    global mot_ind_a, mot_cur_a
    global mot_ind_b, mot_cur_b
    global hef_ind_a, hef_e1a_a, hef_e1b_a, hef_e2a_a, hef_e2b_a
    global hef_ind_b, hef_e1a_b, hef_e1b_b, hef_e2a_b, hef_e2b_b
    global cal_ind_a, cal_e1a_a, cal_e1b_a, cal_e1c_a, cal_e2a_a, cal_e2b_a, cal_e2c_a
    global cal_ind_b, cal_e1a_b, cal_e1b_b, cal_e1c_b, cal_e2a_b, cal_e2b_b, cal_e2c_b
    global iscan
    global HCYE  # half-cycle EF
    global HCYC  # half-cycle CAL
    global HCYM  # half-cycle MOT
    global plot_raw_cal_flag
    global plot_raw_mot_flag

    # if ab == None:
    #   print('ab is None')
    #   print_info_and_exit()
    #   return

    # header for EF, cal or motor
    if hef_split[0].find('#3__HE') == 0:
        # add gaps at each HEF header to signify a break in the sampling
        mot_ind_a.append(None)
        mot_cur_a.append(None)
        hef_ind_a.append(None)
        hef_e1a_a.append(None)
        hef_e1b_a.append(None)
        hef_e2a_a.append(None)
        hef_e2b_a.append(None)
        cal_ind_a.append(None)
        cal_e1a_a.append(None)
        cal_e1b_a.append(None)
        cal_e1c_a.append(None)
        cal_e2a_a.append(None)
        cal_e2b_a.append(None)
        cal_e2c_a.append(None)

        mot_ind_b.append(None)
        mot_cur_b.append(None)
        hef_ind_b.append(None)
        hef_e1a_b.append(None)
        hef_e1b_b.append(None)
        hef_e2a_b.append(None)
        hef_e2b_b.append(None)
        cal_ind_b.append(None)
        cal_e1a_b.append(None)
        cal_e1b_b.append(None)
        cal_e1c_b.append(None)
        cal_e2a_b.append(None)
        cal_e2b_b.append(None)
        cal_e2c_b.append(None)

    # motor current data
    if hef_split[0] == '#3__DM':

        try:
            ind = int(hef_split[1])
            cur = int(hef_split[2]) * sf_mot
        except:
            print('cannot decode motor current data')
            print_info_and_exit()

        if ab == 'a':
            mot_ind_a.append(ind)
            mot_cur_a.append(cur)
        elif ab == 'b':
            mot_ind_b.append(ind)
            mot_cur_b.append(cur)
        else:
            print('error ab=', ab, 'wrong')
            print_info_and_exit()

        # half-cycle arrays
        if iscan == 0:
            HCYM = collections.namedtuple('HCYM', [])
            HCYM.ind = []
            HCYM.cur = []
        HCYM.ind.append(ind)
        HCYM.cur.append(cur)

        iscan += 1

        if iscan == nscan:
            HCYM.ab = ab

            # HEF UXT of start of motor move:
            HCYM.uxt0 = uxt_ibeg

            # elapsed seconds of each data point since start of motor move:
            HCYM.secs = np.array(HCYM.ind, dtype='double') * tsamp_motor

            # UXT of of each sample:
            HCYM.uxt = HCYM.secs + HCYM.uxt0
            HCYM.cur = np.array(HCYM.cur, dtype='double')

        if iscan == nscan and options.do_plot_raw_mot:
            if options.limEC == 0 or count_EC <= options.limEC:
                plot_raw_mot_flag = True  # defer plot_raw_mot() until get status

    # EF data
    elif hef_split[0] == '#3__DE':
        try:
            # convert ADC counts to microvolts at preamp input
            # flip sign of "b" because "b" preamp input opposite of "a"
            ind = int(hef_split[1])
            e1a = (int(hef_split[2]) - off_ef) * sf_ef
            e1b = -(int(hef_split[3]) - off_ef) * sf_ef
            e2a = (int(hef_split[4]) - off_ef) * sf_ef
            e2b = -(int(hef_split[5]) - off_ef) * sf_ef
        except:
            print('EF data decode failed, lineno=', lineno, 'linein=', linein)
            print_info_and_exit()

        # file-length arrays
        if ab == 'a':
            hef_ind_a.append(ind)
            hef_e1a_a.append(e1a)
            hef_e1b_a.append(e1b)
            hef_e2a_a.append(e2a)
            hef_e2b_a.append(e2b)
        if ab == 'b':
            hef_ind_b.append(ind)
            hef_e1a_b.append(e1a)
            hef_e1b_b.append(e1b)
            hef_e2a_b.append(e2a)
            hef_e2b_b.append(e2b)

        # half-cycle arrays
        if iscan == 0:
            HCYE = collections.namedtuple('HCYE', [])
            HCYE.ind = []
            HCYE.e1a = []
            HCYE.e1b = []
            HCYE.e2a = []
            HCYE.e2b = []
        HCYE.ind.append(ind)
        HCYE.e1a.append(e1a)
        HCYE.e1b.append(e1b)
        HCYE.e2a.append(e2a)
        HCYE.e2b.append(e2b)

        iscan += 1

        if iscan == nscan:
            HCYE.ab = ab

            # HEF UXT of end of motor move:
            HCYE.uxt0 = uxt_ibeg

            # elapsed seconds of each data point since motor move:
            HCYE.secs = np.array(HCYE.ind, dtype='double') * tsamp_ef

            # HEF UXT of of each sample:
            HCYE.uxt = HCYE.secs + HCYE.uxt0

            HCYE.e1a = np.array(HCYE.e1a, dtype='double')
            HCYE.e1b = np.array(HCYE.e1b, dtype='double')
            HCYE.e2a = np.array(HCYE.e2a, dtype='double')
            HCYE.e2b = np.array(HCYE.e2b, dtype='double')

        if iscan == nscan and options.do_extra:
            print_uxt_ies_chk()

        if iscan == nscan and options.do_plot_raw_ef:
            if options.limEC == 0 or count_EC <= options.limEC:
                if options.ncat == 0:
                    plot_raw_ef()
                else:
                    plot_raw_ef_cat()

        # compute averages
        if iscan == nscan and nskip_ef < nscan:
            #     print('iscan=',iscan,'nscan=',nscan)

            j = np.array(range(nskip_ef, nscan))

            global AVG
            AVG.nuse.append(j.size)
            AVG.ab.append(ab)
            AVG.uxt.append(np.mean(HCYE.uxt[j]))
            AVG.e1a.append(np.mean(HCYE.e1a[j]))
            AVG.e1b.append(np.mean(HCYE.e1b[j]))
            AVG.e2a.append(np.mean(HCYE.e2a[j]))
            AVG.e2b.append(np.mean(HCYE.e2b[j]))
            AVG.e1a_std.append(np.std(HCYE.e1a[j]))
            AVG.e1b_std.append(np.std(HCYE.e1b[j]))
            AVG.e2a_std.append(np.std(HCYE.e2a[j]))
            AVG.e2b_std.append(np.std(HCYE.e2b[j]))

            t = HCYE.uxt[j] - np.mean(HCYE.uxt[j])
            e1a_poly = np.polyfit(t, HCYE.e1a[j], 1)
            e1b_poly = np.polyfit(t, HCYE.e1b[j], 1)
            e2a_poly = np.polyfit(t, HCYE.e2a[j], 1)
            e2b_poly = np.polyfit(t, HCYE.e2b[j], 1)
            e1a_fit = np.polyval(e1a_poly, t)
            e1b_fit = np.polyval(e1b_poly, t)
            e2a_fit = np.polyval(e2a_poly, t)
            e2b_fit = np.polyval(e2b_poly, t)
            HCYE.e1a_res = HCYE.e1a[j] - e1a_fit
            HCYE.e1b_res = HCYE.e1b[j] - e1b_fit
            HCYE.e2a_res = HCYE.e2a[j] - e2a_fit
            HCYE.e2b_res = HCYE.e2b[j] - e2b_fit
            AVG.e1a_poly_std.append(np.std(HCYE.e1a_res))
            AVG.e1b_poly_std.append(np.std(HCYE.e1b_res))
            AVG.e2a_poly_std.append(np.std(HCYE.e2a_res))
            AVG.e2b_poly_std.append(np.std(HCYE.e2b_res))

        if iscan > nscan:
            print('iscan > nscan')
            print_info_and_exit()

    # calibration data (resistance check)
    elif hef_split[0] == '#3__DC':
        #   print('#3__DC: iscan=',iscan)
        try:
            # convert ADC counts to microvolts at preamp input
            # flip sign of "b" because "b" preamp input opposite of "a"
            ind = int(hef_split[1])
            e1c = (int(hef_split[2]) - off_cal) * sf_cal
            e1a = (int(hef_split[3]) - off_cal) * sf_cal
            e1b = -(int(hef_split[4]) - off_cal) * sf_cal
            e2c = (int(hef_split[5]) - off_cal) * sf_cal
            e2a = (int(hef_split[6]) - off_cal) * sf_cal
            e2b = -(int(hef_split[7]) - off_cal) * sf_cal
        except:
            print('cannot decode cal data')
            print_info_and_exit()

        # half-cycle arrays of cal data
        if iscan == 0:
            HCYC = collections.namedtuple('HCYC', [])
            HCYC.ind = []
            HCYC.e1c = []
            HCYC.e1a = []
            HCYC.e1b = []
            HCYC.e2c = []
            HCYC.e2a = []
            HCYC.e2b = []
        HCYC.ind.append(ind)
        HCYC.e1c.append(e1c)
        HCYC.e1a.append(e1a)
        HCYC.e1b.append(e1b)
        HCYC.e2c.append(e2c)
        HCYC.e2a.append(e2a)
        HCYC.e2b.append(e2b)

        iscan += 1

        if iscan == nscan:
            #     print('len(HCYC.ind)=',len(HCYC.ind))

            HCYC.ab = ab
            HCYC.uxt0 = uxt_ibeg
            HCYC.secs = np.array(HCYC.ind, dtype='double') * tsamp_ef
            HCYC.uxt = HCYC.secs + HCYC.uxt0
            HCYC.e1c = np.array(HCYC.e1c, dtype='double')
            HCYC.e1a = np.array(HCYC.e1a, dtype='double')
            HCYC.e1b = np.array(HCYC.e1b, dtype='double')
            HCYC.e2c = np.array(HCYC.e2c, dtype='double')
            HCYC.e2a = np.array(HCYC.e2a, dtype='double')
            HCYC.e2b = np.array(HCYC.e2b, dtype='double')

        if iscan == nscan and options.do_plot_raw_cal:
            if options.limEC == 0 or count_EC <= options.limEC:
                plot_raw_cal_flag = True  # defer plot_raw_cal() until get status

        if ab == 'a':
            cal_ind_a.append(ind)
            cal_e1c_a.append(e1c)
            cal_e1a_a.append(e1a)
            cal_e1b_a.append(e1b)
            cal_e2c_a.append(e2c)
            cal_e2a_a.append(e2a)
            cal_e2b_a.append(e2b)
        if ab == 'b':
            cal_ind_b.append(ind)
            cal_e1c_b.append(e1c)
            cal_e1a_b.append(e1a)
            cal_e1b_b.append(e1b)
            cal_e2c_b.append(e2c)
            cal_e2a_b.append(e2a)
            cal_e2b_b.append(e2b)


# else:
#   print('unknown data, lineno=',lineno,'linein',linein)
#   print_info_and_exit()

def check_hef_time():
    global hef_secs_diff

    # header for EF, cal or motor
    if hef_split[0] == '#3__HE04':
        try:
            hef_secs_diff = int(hef_split[6]) - int(hef_split[11])
        except:
            print('bad HE04 hef_secs_diff')
            print_info_and_exit()
        if options.verbose:
            print('hefsecs=', hefsecs, 'now=', secsnow, 'dif=', hef_secs_diff)


def append_compass():
    global comp_uxt, comp_hdg, comp_pitch, comp_roll, comp_temp
    global count_compass

    if len(hef_split) < 1:
        return

    # compass data
    if hef_split[0].find('#3__HC') == 0:
        if hef_split[0] == '#3__HC03':
            if len(hef_split) != 8:
                print('HC03 wrong split len:', len(hef_split))
                print('hef_split:', hef_split)
                print_info_and_exit()
            count_compass += 1
        else:
            print('unknown compass header')
            print_info_and_exit()

        try:
            uxt_HC = int(hef_split[1])
            hdg = int(hef_split[3])
            pitch = int(hef_split[4])
            roll = int(hef_split[5])
            temp = int(hef_split[6])
        except:
            print('error in decoding compass data')
            print_info_and_exit()

        comp_uxt.append(uxt_HC)
        comp_hdg.append(hdg)
        comp_pitch.append(pitch)
        comp_roll.append(roll)
        comp_temp.append(temp)


def append_aux():
    global aux_uxt, aux_tt1, aux_tt2, aux_tt4, aux_tt4
    global aux_pres, aux_temp, aux_btemp, aux_bfreq
    global aux_uxt_xfr
    global uxt_aux, aux_flag

    if aux_split == None:
        return

    if len(aux_split) != 13:
        print('len(aux_split) wrong: ', len(aux_split))
        print('aux_split:', aux_split)

    try:
        aux_flag = True
        uxt_aux = int(aux_split[1])  # IES time of beginning of 10-min sequence
        ntt = int(aux_split[2])
        tt1 = int(aux_split[3])
        tt2 = int(aux_split[4])
        tt3 = int(aux_split[5])
        tt4 = int(aux_split[6])
        pres = int(aux_split[7])
        temp = int(aux_split[8])
        btemp = int(aux_split[9])
        bfreq = float(aux_split[10])
        uxt_xfr = int(aux_split[12])  # STM time of data reception from IES's AUX
    except:
        print('cannot decode aux port data')
        print_info_and_exit()

    if ntt != 4:
        print('ntt=', ntt, 'is wrong')
        print_info_and_exit()

    aux_uxt.append(uxt_aux)
    aux_tt1.append(tt1)
    aux_tt2.append(tt2)
    aux_tt3.append(tt3)
    aux_tt4.append(tt4)
    aux_pres.append(pres)
    aux_temp.append(temp)
    aux_btemp.append(btemp)
    aux_bfreq.append(bfreq)
    aux_uxt_xfr.append(uxt_xfr)


def plot_test():
    x = [1, 2, 3, 4, 5]
    y = [1, 2, 3, 4, 5]
    x = np.array(x, dtype='double')
    y = np.array(y, dtype='double')
    y = y * 5

    fig = plt.figure()
    if options.interactive:
        fig.canvas.set_window_title('Test')
    fig.suptitle('testing some matplotlib calls')

    ax = fig.add_subplot(1, 1, 1)
    ax.plot(x, y, 'ro-')
    ax.grid(True)
    plt.xlabel('x')
    plt.title('plot test')
    plt.draw()


def plot_ef_avg_std():
    uxt = np.array(AVG.uxt)
    ab = np.array(AVG.ab)
    e1a = np.array(AVG.e1a)
    e1b = np.array(AVG.e1b)
    e2a = np.array(AVG.e2a)
    e2b = np.array(AVG.e2b)

    e1a_std = np.array(AVG.e1a_std)
    e1b_std = np.array(AVG.e1b_std)
    e2a_std = np.array(AVG.e2a_std)
    e2b_std = np.array(AVG.e2b_std)

    e1a_poly_std = np.array(AVG.e1a_poly_std)
    e1b_poly_std = np.array(AVG.e1b_poly_std)
    e2a_poly_std = np.array(AVG.e2a_poly_std)
    e2b_poly_std = np.array(AVG.e2b_poly_std)

    t = uxt - uxt[0]
    ja = np.where(ab == 'a')  # indices when A tube is pinched
    jb = np.where(ab == 'b')  # indices when B tube is pinched

    # connect to ocean when pinch on same side as preamp
    e1ap = e1a[ja]
    e1bp = e1b[jb]
    e2ap = e2a[ja]
    e2bp = e2b[jb]
    e1ap_std = e1a_std[ja]
    e1bp_std = e1b_std[jb]
    e2ap_std = e2a_std[ja]
    e2bp_std = e2b_std[jb]
    e1ap_poly_std = e1a_poly_std[ja]
    e1bp_poly_std = e1b_poly_std[jb]
    e2ap_poly_std = e2a_poly_std[ja]
    e2bp_poly_std = e2b_poly_std[jb]

    # self potential when unpinch on same side as preamp
    e1au = e1a[jb]
    e1bu = e1b[ja]
    e2au = e2a[jb]
    e2bu = e2b[ja]
    e1au_std = e1a_std[jb]
    e1bu_std = e1b_std[ja]
    e2au_std = e2a_std[jb]
    e2bu_std = e2b_std[ja]
    e1au_poly_std = e1a_poly_std[jb]
    e1bu_poly_std = e1b_poly_std[ja]
    e2au_poly_std = e2a_poly_std[jb]
    e2bu_poly_std = e2b_poly_std[ja]

    # interpolate self potentials to ocean times
    e1aui = np.interp(t[ja], t[jb], e1au)
    e1bui = np.interp(t[jb], t[ja], e1bu)
    e2aui = np.interp(t[ja], t[jb], e2au)
    e2bui = np.interp(t[jb], t[ja], e2bu)

    # ocean estimate = pinch minus interpolated unpinch
    e1ao = e1ap - e1aui  # t[ja]
    e1bo = e1bp - e1bui  # t[jb]
    e2ao = e2ap - e2aui  # t[ja]
    e2bo = e2bp - e2bui  # t[jb]

    pdfdir = './pdf/hef-avg/'
    pyt = datetime(1970, 1, 1, 0, 0, 0) + timedelta(0, uxt[0])
    pytstr = pyt.strftime('%Y-%m-%d %H:%M:%S')

    # plot ocean data
    fig = plt.figure()
    pltnam = '{0}-hef-ocean'.format(leafname)

    if options.interactive:
        fig.canvas.set_window_title('HEF Ocean Averages')

    fig.suptitle('{0}, {1}\ntskip={2:.1f} s, red:A, blu:B'.
                 format(pltnam, pytstr, tskip_ef))

    ax = fig.add_subplot(2, 1, 1)
    ax.plot(t[ja], e1ao, 'r.-')
    ax.hold(True)
    ax.plot(t[jb], e1bo, 'b.-')
    ax.hold(False)
    fixlims(ax)
    plt.ylabel('e1o, uV')

    ax = fig.add_subplot(2, 1, 2)
    ax.plot(t[ja], e2ao, 'r.-')
    ax.hold(True)
    ax.plot(t[jb], e2bo, 'b.-')
    ax.hold(False)
    fixlims(ax)
    plt.ylabel('e2o, uV')

    # plt.draw()

    if options.interactive:
        fig.show()
        print('Click figure window to continue')
        plt.waitforbuttonpress()
    else:
        pdffile = pdfdir + pltnam + '.pdf'
        print(pdffile)
        plt.savefig(pdffile)
        os.system('updateframe.run ' + pdfdir)

    # plot standard deviations
    fig = plt.figure()
    pltnam = '{0}-hef-std-dev'.format(leafname)

    fig.suptitle('{0}, {1}\ntskip={2:.1f} s, red:pinched, blu:unpinched'.format(pltnam, pytstr, tskip_ef))

    ylim = [0, 1]

    ax = fig.add_subplot(4, 1, 1)
    ax.plot(t[jb], e1au_std, 'b.-')
    ax.hold(True)
    ax.plot(t[ja], e1ap_std, 'r.-')
    ax.hold(False)
    ax.set_ylim(ylim)
    fixlims(ax)
    plt.ylabel('e1a, uV')

    ax = fig.add_subplot(4, 1, 2)
    ax.plot(t[ja], e1bu_std, 'b.-')
    ax.hold(True)
    ax.plot(t[jb], e1bp_std, 'r.-')
    ax.hold(False)
    ax.set_ylim(ylim)
    fixlims(ax)
    plt.ylabel('e1b, uV')

    ax = fig.add_subplot(4, 1, 3)
    ax.plot(t[jb], e2au_std, 'b.-')
    ax.hold(True)
    ax.plot(t[ja], e2ap_std, 'r.-')
    ax.hold(False)
    ax.set_ylim(ylim)
    fixlims(ax)
    plt.ylabel('e2a, uV')

    ax = fig.add_subplot(4, 1, 4)
    ax.plot(t[ja], e2bu_std, 'b.-')
    ax.hold(True)
    ax.plot(t[jb], e2bp_std, 'r.-')
    ax.hold(False)
    ax.set_ylim(ylim)
    fixlims(ax)
    plt.ylabel('e2b, uV')

    # plt.draw()

    if options.interactive:
        fig.show()
        print('Click figure window to continue')
        plt.waitforbuttonpress()
    else:
        pdffile = pdfdir + pltnam + '.pdf'
        print(pdffile)
        plt.savefig(pdffile)
        os.system('updateframe.run ' + pdfdir)

    # plot standard deviations of data minus polynomial fit
    fig = plt.figure()
    pltnam = '{0}-hef-std-dev-poly'.format(leafname)

    fig.suptitle('{0}, {1}\ntskip={2:.1f} s, red:pinched, blu:unpinched'.format(pltnam, pytstr, tskip_ef))

    ylim = [0, 1]

    ax = fig.add_subplot(4, 1, 1)
    ax.plot(t[jb], e1au_poly_std, 'b.-')
    ax.hold(True)
    ax.plot(t[ja], e1ap_poly_std, 'r.-')
    ax.hold(False)
    ax.set_ylim(ylim)
    fixlims(ax)
    plt.ylabel('e1a, uV')

    ax = fig.add_subplot(4, 1, 2)
    ax.plot(t[ja], e1bu_poly_std, 'b.-')
    ax.hold(True)
    ax.plot(t[jb], e1bp_poly_std, 'r.-')
    ax.hold(False)
    ax.set_ylim(ylim)
    fixlims(ax)
    plt.ylabel('e1b, uV')

    ax = fig.add_subplot(4, 1, 3)
    ax.plot(t[jb], e2au_poly_std, 'b.-')
    ax.hold(True)
    ax.plot(t[ja], e2ap_poly_std, 'r.-')
    ax.hold(False)
    ax.set_ylim(ylim)
    fixlims(ax)
    plt.ylabel('e2a, uV')

    ax = fig.add_subplot(4, 1, 4)
    ax.plot(t[ja], e2bu_poly_std, 'b.-')
    ax.hold(True)
    ax.plot(t[jb], e2bp_poly_std, 'r.-')
    ax.hold(False)
    ax.set_ylim(ylim)
    fixlims(ax)
    plt.ylabel('e2b, uV')

    # plt.draw()

    if options.interactive:
        fig.show()
        print('Click figure window to continue')
        plt.waitforbuttonpress()
    else:
        pdffile = pdfdir + pltnam + '.pdf'
        print(pdffile)
        plt.savefig(pdffile)
        os.system('updateframe.run ' + pdfdir)

    # plot self potentials
    fig = plt.figure()
    pltnam = '{0}-hef-self-pot'.format(leafname)

    fig.suptitle('{0}, {1}\ntskip={2:.1f} s'.format(pltnam, pytstr, tskip_ef))

    ax = fig.add_subplot(4, 1, 1)
    ax.plot(t[jb], e1au, 'b.-')
    fixlims(ax)
    plt.ylabel('e1au, uV')

    ax = fig.add_subplot(4, 1, 2)
    ax.plot(t[ja], e1bu, 'b.-')
    fixlims(ax)
    plt.ylabel('e1bu, uV')

    ax = fig.add_subplot(4, 1, 3)
    ax.plot(t[jb], e2au, 'b.-')
    fixlims(ax)
    plt.ylabel('e2au, uV')

    ax = fig.add_subplot(4, 1, 4)
    ax.plot(t[ja], e2bu, 'b.-')
    fixlims(ax)
    plt.ylabel('e2bu, uV')

    # plt.draw()

    if options.interactive:
        fig.show()
        print('Click figure window to continue')
        plt.waitforbuttonpress()
    else:
        pdffile = pdfdir + pltnam + '.pdf'
        print(pdffile)
        plt.savefig(pdffile)
        os.system('updateframe.run ' + pdfdir)


def plot_tt():
    if len(aux_uxt) == 0:
        return

    uxt = np.array(aux_uxt, dtype='double')
    age = uxt - uxt[-1]
    tt1 = np.array(aux_tt1, dtype='double') * 1e-5
    tt2 = np.array(aux_tt2, dtype='double') * 1e-5
    tt3 = np.array(aux_tt3, dtype='double') * 1e-5
    tt4 = np.array(aux_tt4, dtype='double') * 1e-5

    fig = plt.figure()
    if options.interactive:
        fig.canvas.set_window_title('Travel Times')
    fig.suptitle(leafname + ' plot_tt')

    ax = fig.add_subplot(4, 1, 1)
    ax.plot(age, tt1, 'bo-')
    ax.grid(True)
    plt.ylabel('TT1, s')
    plt.title('IES Travel Times')

    ax = fig.add_subplot(4, 1, 2)
    ax.plot(age, tt2, 'bo-')
    ax.grid(True)
    plt.ylabel('TT2, s')

    ax = fig.add_subplot(4, 1, 3)
    ax.plot(age, tt3, 'bo-')
    ax.grid(True)
    plt.ylabel('TT3, s')

    ax = fig.add_subplot(4, 1, 4)
    ax.plot(age, tt4, 'bo-')
    ax.grid(True)
    plt.ylabel('TT4, s')
    plt.xlabel('Time, s')

    plt.draw()


def plot_pres_temp():
    if len(aux_uxt) == 0:
        return

    uxt = np.array(aux_uxt, dtype='double')
    age = uxt - uxt[-1]
    pres = np.array(aux_pres, dtype='double') * 1e-5
    temp = np.array(aux_temp, dtype='double') * 1e-3

    fig = plt.figure()
    if options.interactive:
        fig.canvas.set_window_title('IES pressure & temperature')
    fig.suptitle(leafname + ' plot_pres_temp')

    ax = fig.add_subplot(2, 1, 1)
    ax.plot(age, pres, 'bo-')
    ax.grid('on')
    plt.ylabel('P, dbar')
    plt.title('IES Pressure & Temperature')

    ax = fig.add_subplot(2, 1, 2)
    ax.plot(age, temp, 'bo-')
    ax.grid('on')
    plt.xlabel('Time, s')
    plt.ylabel('T, C')
    plt.draw()


def plot_bliley():
    if len(aux_uxt) == 0:
        return

    uxt = np.array(aux_uxt, dtype='double')
    age = uxt - uxt[-1]
    btemp = np.array(aux_btemp, dtype='double') * 0.001
    bfreq = np.array(aux_bfreq, dtype='double')

    fig = plt.figure()
    if options.interactive:
        fig.canvas.set_window_title('IES Bliley Oscillator')
    fig.suptitle(leafname + ' plot_bliley')

    ax = fig.add_subplot(2, 1, 1)
    ax.plot(age, btemp, 'bo-')
    ax.grid('on')
    plt.ylabel('T, C')
    plt.title('Bliley Oscillator')

    ax = fig.add_subplot(2, 1, 2)
    ax.plot(age, bfreq - 4e6, 'bo-')
    ax.grid('on')
    plt.ylabel('Freq - 4e6, Hz')
    plt.xlabel('Time, s')
    plt.draw()


def plot_mot_overlay():
    # global mot_ind_a, mot_cur_a
    # global mot_ind_b, mot_cur_b
    # global navg_mot

    if len(mot_ind_a) == 0 and len(mot_ind_b) == 0:
        return

    secs_a = np.array(mot_ind_a, dtype='double') * tsamp_motor
    secs_b = np.array(mot_ind_b, dtype='double') * tsamp_motor
    cur_a = np.array(mot_cur_a, dtype='double')
    cur_b = np.array(mot_cur_b, dtype='double')

    fig = plt.figure()
    if options.interactive:
        fig.canvas.set_window_title('HEF Motor')
    fig.suptitle(leafname + ' plot_mot_overlay')

    ax = fig.add_subplot(2, 1, 1)
    ax.plot(secs_a, cur_a, 'b.-')
    ax.grid('on')
    plt.ylabel('A, mA')
    plt.title('Motor Current')

    ax = fig.add_subplot(2, 1, 2)
    ax.plot(secs_b, cur_b, 'b.-')
    ax.grid('on')
    plt.ylabel('B, mA')
    plt.xlabel('time, s (' + ifile + ')')

    plt.draw()


# For OKMC, check that computed time of IES cycle start
# is same as the time from the AUX record
# The last column printed should be integer multiple of 600
def print_uxt_ies_chk():
    uxt_ies_fake = np.arange(0, 240, 1.024) + HCYE.uxt0
    tmod_fake = np.mod(uxt_ies_fake, 600)
    j0_fake = np.nonzero(np.diff(tmod_fake) < 0)[0] + 1
    if len(j0_fake) == 1 and aux_flag:
        uxt_ies_j0 = uxt_ies_fake[j0_fake][0]
        print('uxt_ies_j0={0:.1f}'.format(uxt_ies_j0), \
              'uxt_aux={0:.1f}'.format(uxt_aux), \
              'uxt_ies_j0-uxt_aux={0:5.1f}'.format(uxt_ies_j0 - uxt_aux))


def plot_raw_mot():
    pyt = datetime(1970, 1, 1, 0, 0, 0) + timedelta(0, HCYM.uxt0)
    pytstr = pyt.strftime('%Y-%m-%d %H:%M:%S')
    pltnam = str.format('{0}-{1:04d}-raw-mot', leafname, count_EC)

    fig = plt.figure(num=1, figsize=(10, 7))
    fig.clf()
    if options.interactive:
        fig.canvas.set_window_title('Raw Motor')
    fig.suptitle(pltnam + ' ' + pytstr)

    ax = fig.add_subplot(2, 1, 1)
    ax.plot(HCYM.secs, HCYM.cur, 'b.-')
    fixlims(ax)
    ax.grid('on')
    ax.xaxis.set_ticklabels([])
    plt.ylabel('MotCur, mA')
    plt.title('Raw Motor Current, tavg={0:.3f} s, red=A pinched, blu=B pinched'.format(navg_mot * tsamp_motor))

    ax = fig.add_subplot(2, 1, 2)
    t = np.arange(0, len(MOT_STATUS.stat_fast)) * tsamp_motor
    ax.plot(t, MOT_STATUS.stat_fast, 'b.-')
    fixlims(ax)
    ax.grid('on')
    plt.ylabel('stat_fast')
    plt.xlabel('time, s')

    if options.interactive:
        fig.show()
        print('Click figure window to continue')
        plt.waitforbuttonpress()
    else:
        pdffile = './pdf/raw-mot/' + pltnam + '.pdf'
        print(pdffile)
        plt.savefig(pdffile)
        os.system('updateframe.run pdf/raw-mot')


# plot concatinated motor current to see trends
def plot_raw_mot_cat():
    global NCYM
    global count_raw_mot_cat

    HCYM.AB = HCYM.ab.upper()

    uxt = HCYM.uxt
    cur = HCYM.cur

    abi = np.tile(ord(HCYM.AB), len(HCYM.uxt))
    sta = MOT_STATUS.stat_pick
    tpl = uxt - HCYM.uxt0

    count_raw_mot_cat += 1

    if len(uxt) < 2:
        print('plot_raw_mot_cat() len(uxt) too short')

    if count_raw_mot_cat == 1:
        NCYM = collections.namedtuple('NCYM', [])
        NCYM.uxt0 = HCYM.uxt0
        NCYM.uxt_cat = uxt
        NCYM.cur_cat = cur

        NCYM.abi_cat = abi
        NCYM.sta_cat = sta
        NCYM.tpl_cat = tpl
    else:
        if len(NCYM.tpl_cat) > 0 and np.isfinite(NCYM.tpl_cat[-1]):
            tpl_off = NCYM.tpl_cat[-1] + 5
        else:
            tpl_off = 0

        if len(uxt) > 0:
            # insert nan to lift pen during motor runs
            NCYM.uxt_cat = np.append(NCYM.uxt_cat, np.nan)
            NCYM.cur_cat = np.append(NCYM.cur_cat, np.nan)

            NCYM.tpl_cat = np.append(NCYM.tpl_cat, np.nan)
            NCYM.abi_cat = np.append(NCYM.abi_cat, np.nan)
            NCYM.sta_cat = np.append(NCYM.sta_cat, np.nan)

            NCYM.uxt_cat = np.append(NCYM.uxt_cat, uxt)
            NCYM.cur_cat = np.append(NCYM.cur_cat, cur)

            NCYM.abi_cat = np.append(NCYM.abi_cat, abi)
            NCYM.sta_cat = np.append(NCYM.sta_cat, sta)
            NCYM.tpl_cat = np.append(NCYM.tpl_cat, tpl + tpl_off)

    if count_raw_mot_cat == options.ncat:
        count_raw_mot_cat = 0

        pyt = datetime(1970, 1, 1, 0, 0, 0) + timedelta(0, uxt0)
        pytstr = pyt.strftime('%Y-%m-%d %H:%M:%S')
        pltnam = str.format('{0}-{1:04d}-raw-mot-cat{2}', leafname, count_EC, options.ncat)

        # zap cur_cat unless running
        jz = np.nonzero((sta_cat != 3) & (sta_cat != 48))
        NCYM.cur_cat[jz] = np.nan

        # include the nan values to lift pen between motor runs
        ja = np.nonzero((NCYM.abi_cat == ord('A')) | np.isnan(NCYM.abi_cat))[0]
        jb = np.nonzero((NCYM.abi_cat == ord('B')) | np.isnan(NCYM.abi_cat))[0]

        fig = plt.figure(num=1, figsize=(10, 7))
        fig.clf()
        if options.interactive:
            fig.canvas.set_window_title('Motor Current')
        fig.suptitle(pltnam + ' ' + pytstr)

        ax = fig.add_subplot(1, 1, 1)
        ax.hold(True)
        ax.plot(NCYM.tpl_cat[ja], NCYM.cur_cat[ja], 'r.-')
        ax.plot(NCYM.tpl_cat[jb], NCYM.cur_cat[jb], 'b.-')
        ax.hold(False)
        fixlims(ax)
        ax.grid('on')
        # ax.xaxis.set_ticklabels([])
        plt.ylabel('mA')
        plt.title('Raw Motor Current, tavg={0:.3f} s, red=A pinched, blu=B pinched'.format(navg_mot * tsamp_motor))
        plt.xlabel('seconds')

        if options.interactive:
            fig.show()
            print('Click figure window to continue')
            plt.waitforbuttonpress()
        else:
            pdfdir = './pdf/raw-mot-cat'
            pdffile = pdfdir + '/' + pltnam + '.pdf'
            print(pdffile)
            plt.savefig(pdffile)
            os.system('updateframe.run ' + pdfdir)


def plot_raw_ef():
    global HCYE

    HCYE.AB = HCYE.ab.upper()

    if HCYE.ab == 'a':
        HCYE.ma = 'r'
        HCYE.mb = 'b'
    elif HCYE.ab == 'b':
        HCYE.ma = 'b'
        HCYE.mb = 'r'
    else:
        print('unknown ab')
        print_info_and_exit()

    # indices which lop off first nskip points
    j = np.arange(nskip_ef, len(HCYE.secs), dtype=int)

    # find indices which occur during IES comms with HEF
    # HEF data xfr'd to IES 1:41 (101 s) after IES 10 minute mark
    uxtmj = np.mod(HCYE.uxt[j], 600)
    HCYE.jjm = np.nonzero(np.logical_and(uxtmj > 98, uxtmj < 108))[0]

    HCYE.tj = HCYE.secs[j]
    HCYE.tjjm = HCYE.tj[HCYE.jjm]

    HCYE.jjjm = j[HCYE.jjm]

    pyt = datetime(1970, 1, 1, 0, 0, 0) + timedelta(0, HCYE.uxt0)
    pytstr = pyt.strftime('%Y-%m-%d %H:%M:%S')
    pltnam = str.format('{0}-{1:04d}-raw-ef', leafname, count_EC)

    if len(HCYE.tj) < options.fit_order + 1:
        print('len(HCYE.tj) too small, pltnam=', pltnam)
        return

    e1a_poly = np.polyfit(HCYE.tj, HCYE.e1a[j], options.fit_order)
    e1b_poly = np.polyfit(HCYE.tj, HCYE.e1b[j], options.fit_order)
    e2a_poly = np.polyfit(HCYE.tj, HCYE.e2a[j], options.fit_order)
    e2b_poly = np.polyfit(HCYE.tj, HCYE.e2b[j], options.fit_order)
    e1a_fit = np.polyval(e1a_poly, HCYE.tj)
    e1b_fit = np.polyval(e1b_poly, HCYE.tj)
    e2a_fit = np.polyval(e2a_poly, HCYE.tj)
    e2b_fit = np.polyval(e2b_poly, HCYE.tj)
    HCYE.e1a_res = HCYE.e1a[j] - e1a_fit
    HCYE.e1b_res = HCYE.e1b[j] - e1b_fit
    HCYE.e2a_res = HCYE.e2a[j] - e2a_fit
    HCYE.e2b_res = HCYE.e2b[j] - e2b_fit

    fig = plt.figure(num=1, figsize=(10, 7))
    fig.clf()
    if options.interactive:
        fig.canvas.set_window_title('HEF with IES pings')

    fig.suptitle(pltnam + ' ' + pytstr + ' red:pinched, blu:unpinched')

    ax = fig.add_subplot(4, 2, 1)
    ax.plot(HCYE.tj, HCYE.e1a[j], HCYE.ma)
    ax.hold(True)
    ax.plot(HCYE.tjjm, HCYE.e1a[HCYE.jjjm], 'go')
    ax.hold(False)
    ax.grid('on')
    ax.xaxis.set_ticklabels([])
    plt.ylabel('e1a, uV')
    plt.title('raw EF, ' + HCYE.AB + ' pinched')

    ax = fig.add_subplot(4, 2, 3)
    ax.plot(HCYE.tj, HCYE.e1b[j], HCYE.mb)
    ax.hold(True)
    ax.plot(HCYE.tjjm, HCYE.e1b[HCYE.jjjm], 'go')
    ax.hold(False)
    ax.grid('on')
    ax.xaxis.set_ticklabels([])
    plt.ylabel('e1b, uV')

    ax = fig.add_subplot(4, 2, 5)
    ax.plot(HCYE.tj, HCYE.e2a[j], HCYE.ma)
    ax.hold(True)
    ax.plot(HCYE.tjjm, HCYE.e2a[HCYE.jjjm], 'go')
    ax.hold(False)
    ax.grid('on')
    ax.xaxis.set_ticklabels([])
    plt.ylabel('e2a, uV')

    ax = fig.add_subplot(4, 2, 7)
    ax.plot(HCYE.tj, HCYE.e2b[j], HCYE.mb)
    ax.hold(True)
    ax.plot(HCYE.tjjm, HCYE.e2b[HCYE.jjjm], 'go')
    ax.hold(False)
    ax.grid('on')
    plt.ylabel('e2b, uV')
    plt.xlabel('time, s')

    ax = fig.add_subplot(4, 2, 2)
    ax.plot(HCYE.tj, HCYE.e1a_res, HCYE.ma)
    ax.hold(True)
    ax.plot(HCYE.tjjm, HCYE.e1a_res[HCYE.jjm], 'go')
    ax.hold(False)
    ax.grid('on')
    ax.xaxis.set_ticklabels([])
    plt.ylabel('e1a-fit, uV')
    plt.title('raw EF minus fit(order={0})'.format(options.fit_order))

    ax = fig.add_subplot(4, 2, 4)
    ax.plot(HCYE.tj, HCYE.e1b_res, HCYE.mb)
    ax.hold(True)
    ax.plot(HCYE.tjjm, HCYE.e1b_res[HCYE.jjm], 'go')
    ax.hold(False)
    ax.grid('on')
    ax.xaxis.set_ticklabels([])
    plt.ylabel('e1b-fit, uV')

    ax = fig.add_subplot(4, 2, 6)
    ax.plot(HCYE.tj, HCYE.e2a_res, HCYE.ma)
    ax.hold(True)
    ax.plot(HCYE.tjjm, HCYE.e2a_res[HCYE.jjm], 'go')
    ax.hold(False)
    ax.grid('on')
    ax.xaxis.set_ticklabels([])
    plt.ylabel('e2a-fit, uV')

    ax = fig.add_subplot(4, 2, 8)
    ax.plot(HCYE.tj, HCYE.e2b_res, HCYE.mb)
    ax.hold(True)
    ax.plot(HCYE.tjjm, HCYE.e2b_res[HCYE.jjm], 'go')
    ax.hold(False)
    ax.grid('on')
    plt.ylabel('e2b-fit, uV')
    plt.xlabel('time, s')

    # plt.draw()

    if options.interactive:
        fig.show()
        print('Click figure window to continue')
        plt.waitforbuttonpress()
    else:
        pdffile = './pdf/raw-ef/' + pltnam + '.pdf'
        print(pdffile)
        plt.savefig(pdffile)
        os.system('updateframe.run pdf/raw-ef')


# plot concatinated EF data to see trends
def plot_raw_ef_cat():
    global NCYE, count_raw_ef_cat


    # indices which lop off first nskip_ef points
    j = np.arange(nskip_ef, len(HCYE.secs), dtype=int)
    uxt = HCYE.uxt[j]
    e1a = HCYE.e1a[j]
    e1b = HCYE.e1b[j]
    e2a = HCYE.e2a[j]
    e2b = HCYE.e2b[j]

    abi = np.tile(ord(HCYE.ab), len(uxt))

    # print("count_EC=",count_EC)

    count_raw_ef_cat += 1

    # if len(uxt) < 2:
    #   print('uxt too short: count_raw_ef_cat=',count_raw_ef_cat)

    if count_raw_ef_cat == 1:
        NCYE = collections.namedtuple('NCYE', [])
        NCYE.uxt0 = HCYE.uxt0

        NCYE.uxt_cat = uxt
        NCYE.e1a_cat = e1a
        NCYE.e1b_cat = e1b
        NCYE.e2a_cat = e2a
        NCYE.e2b_cat = e2b

        NCYE.abi_cat = abi
    else:
        if len(uxt) > 0:
            # insert nan to lift pen during motor runs
            NCYE.uxt_cat = np.append(NCYE.uxt_cat, np.nan)
            NCYE.e1a_cat = np.append(NCYE.e1a_cat, np.nan)
            NCYE.e1b_cat = np.append(NCYE.e1b_cat, np.nan)
            NCYE.e2a_cat = np.append(NCYE.e2a_cat, np.nan)
            NCYE.e2b_cat = np.append(NCYE.e2b_cat, np.nan)

            NCYE.abi_cat = np.append(NCYE.abi_cat, np.nan)

            NCYE.uxt_cat = np.append(NCYE.uxt_cat, uxt)
            NCYE.e1a_cat = np.append(NCYE.e1a_cat, e1a)
            NCYE.e1b_cat = np.append(NCYE.e1b_cat, e1b)
            NCYE.e2a_cat = np.append(NCYE.e2a_cat, e2a)
            NCYE.e2b_cat = np.append(NCYE.e2b_cat, e2b)

            NCYE.abi_cat = np.append(NCYE.abi_cat, abi)

    if count_raw_ef_cat == options.ncat:
        count_raw_ef_cat = 0

        # find indices which occur during IES comms with HEF
        # HEF data xfr'd to IES 1:41 (101 s) after IES 10 minute mark
        tmod = np.mod(NCYE.uxt_cat, 600)
        jies = np.nonzero(np.logical_and(tmod > 98, tmod < 108))[0]

        j = np.nonzero(np.isfinite(NCYE.uxt_cat))[0]
        ja = np.nonzero(NCYE.abi_cat == ord('a'))[0]
        jb = np.nonzero(NCYE.abi_cat == ord('b'))[0]
        if len(j) != len(ja) + len(jb):
            print('plot_raw_cal_cat(): len(j) should equal len(ja) + len(jb)')
            print_info_and_exit()

        tj_cat = NCYE.uxt_cat - NCYE.uxt0

        pyt = datetime(1970, 1, 1, 0, 0, 0) + timedelta(0, NCYE.uxt0)
        pytstr = pyt.strftime('%Y-%m-%d %H:%M:%S')
        pltnam = str.format('{0}-{1:04d}-raw-ef-cat{2}', leafname, count_EC, options.ncat)

        if (len(jb) < options.fit_order + 1) | (len(ja) < options.fit_order + 1):
            print('too few ja or jb, pltnam=', pltnam)
            return

        e1a_poly = np.polyfit(tj_cat[jb], NCYE.e1a_cat[jb], options.fit_order)
        e1b_poly = np.polyfit(tj_cat[ja], NCYE.e1b_cat[ja], options.fit_order)
        e2a_poly = np.polyfit(tj_cat[jb], NCYE.e2a_cat[jb], options.fit_order)
        e2b_poly = np.polyfit(tj_cat[ja], NCYE.e2b_cat[ja], options.fit_order)
        e1a_fit = np.tile(np.nan, len(tj_cat))
        e1b_fit = np.tile(np.nan, len(tj_cat))
        e2a_fit = np.tile(np.nan, len(tj_cat))
        e2b_fit = np.tile(np.nan, len(tj_cat))
        e1a_fit[j] = np.polyval(e1a_poly, tj_cat[j])
        e1b_fit[j] = np.polyval(e1b_poly, tj_cat[j])
        e2a_fit[j] = np.polyval(e2a_poly, tj_cat[j])
        e2b_fit[j] = np.polyval(e2b_poly, tj_cat[j])
        NCYE.e1a_res_cat = NCYE.e1a_cat - e1a_fit
        NCYE.e1b_res_cat = NCYE.e1b_cat - e1b_fit
        NCYE.e2a_res_cat = NCYE.e2a_cat - e2a_fit
        NCYE.e2b_res_cat = NCYE.e2b_cat - e2b_fit

        ja = np.nonzero((NCYE.abi_cat == ord('a')) | np.isnan(NCYE.abi_cat))[0]
        jb = np.nonzero((NCYE.abi_cat == ord('b')) | np.isnan(NCYE.abi_cat))[0]

        mrkp = 'r'
        mrku = 'c'
        mrki = 'k.'

        fig = plt.figure(num=1, figsize=(10, 7))
        fig.clf()
        if options.interactive:
            fig.canvas.set_window_title('HEF with IES pings')
        fig.suptitle(pltnam + ' ' + pytstr + ' red:pinched, cyan:unpinched, blk:IES comms')

        axlist = []

        ax = fig.add_subplot(4, 2, 1)
        ax.hold(True)
        ax.plot(tj_cat[jies], NCYE.e1a_cat[jies], mrki)
        ax.plot(tj_cat[ja], NCYE.e1a_cat[ja], mrkp)
        ax.plot(tj_cat[jb], NCYE.e1a_cat[jb], mrku)
        ax.hold(False)
        fixlims(ax)
        ax.grid('on')
        ax.xaxis.set_ticklabels([])
        plt.ylabel('e1a, uV')
        plt.title('raw EF, tskip={0:.1f} s'.format(tskip_ef))
        axlist.append(ax)

        ax = fig.add_subplot(4, 2, 3)
        ax.hold(True)
        ax.plot(tj_cat[jies], NCYE.e1b_cat[jies], mrki)
        ax.plot(tj_cat[ja], NCYE.e1b_cat[ja], mrku)
        ax.plot(tj_cat[jb], NCYE.e1b_cat[jb], mrkp)
        ax.hold(False)
        fixlims(ax)
        ax.grid('on')
        ax.xaxis.set_ticklabels([])
        plt.ylabel('e1b, uV')
        axlist.append(ax)

        ax = fig.add_subplot(4, 2, 5)
        ax.hold(True)
        ax.plot(tj_cat[jies], NCYE.e2a_cat[jies], mrki)
        ax.plot(tj_cat[ja], NCYE.e2a_cat[ja], mrkp)
        ax.plot(tj_cat[jb], NCYE.e2a_cat[jb], mrku)
        ax.hold(False)
        fixlims(ax)
        ax.grid('on')
        ax.xaxis.set_ticklabels([])
        plt.ylabel('e2a, uV')
        axlist.append(ax)

        ax = fig.add_subplot(4, 2, 7)
        ax.hold(True)
        ax.plot(tj_cat[jies], NCYE.e2b_cat[jies], mrki)
        ax.plot(tj_cat[ja], NCYE.e2b_cat[ja], mrku)
        ax.plot(tj_cat[jb], NCYE.e2b_cat[jb], mrkp)
        ax.hold(False)
        fixlims(ax)
        ax.grid('on')
        plt.ylabel('e2b, uV')
        plt.xlabel('time, s')
        axlist.append(ax)

        ax = fig.add_subplot(4, 2, 2)
        ax.hold(True)
        ax.plot(tj_cat[jies], NCYE.e1a_res_cat[jies], mrki)
        ax.plot(tj_cat[ja], NCYE.e1a_res_cat[ja], mrkp)
        ax.plot(tj_cat[jb], NCYE.e1a_res_cat[jb], mrku)
        ax.hold(False)
        fixlims(ax)
        ax.grid('on')
        ax.xaxis.set_ticklabels([])
        plt.ylabel('e1a-fit, uV')
        plt.title('raw EF minus fit(order={0})'.format(options.fit_order))
        ylim2 = ax.get_ylim()
        ax2 = ax
        axlist.append(ax)

        ax = fig.add_subplot(4, 2, 4)
        ax.hold(True)
        ax.plot(tj_cat[jies], NCYE.e1b_res_cat[jies], mrki)
        ax.plot(tj_cat[ja], NCYE.e1b_res_cat[ja], mrku)
        ax.plot(tj_cat[jb], NCYE.e1b_res_cat[jb], mrkp)
        ax.hold(False)
        fixlims(ax)
        ax.grid('on')
        ax.xaxis.set_ticklabels([])
        plt.ylabel('e1b-fit, uV')
        ylim4 = ax.get_ylim()
        ax4 = ax
        axlist.append(ax)

        ylim = [min(ylim2[0], ylim4[0]), max(ylim2[1], ylim4[1])]
        ax2.set_ylim(ylim)
        ax4.set_ylim(ylim)

        ax = fig.add_subplot(4, 2, 6)
        ax.hold(True)
        ax.plot(tj_cat[jies], NCYE.e2a_res_cat[jies], mrki)
        ax.plot(tj_cat[ja], NCYE.e2a_res_cat[ja], mrkp)
        ax.plot(tj_cat[jb], NCYE.e2a_res_cat[jb], mrku)
        ax.hold(False)
        fixlims(ax)
        ax.grid('on')
        ax.xaxis.set_ticklabels([])
        plt.ylabel('e2a-fit, uV')
        ylim6 = ax.get_ylim()
        ax6 = ax
        axlist.append(ax)

        ax = fig.add_subplot(4, 2, 8)
        ax.hold(True)
        ax.plot(tj_cat[jies], NCYE.e2b_res_cat[jies], mrki)
        ax.plot(tj_cat[ja], NCYE.e2b_res_cat[ja], mrku)
        ax.plot(tj_cat[jb], NCYE.e2b_res_cat[jb], mrkp)
        ax.hold(False)
        fixlims(ax)
        ax.grid('on')
        plt.ylabel('e2b-fit, uV')
        plt.xlabel('time, s')
        ylim8 = ax.get_ylim()
        ax8 = ax
        axlist.append(ax)

        ylim = [min(ylim6[0], ylim8[0]), max(ylim6[1], ylim8[1])]
        ax6.set_ylim(ylim)
        ax8.set_ylim(ylim)

        #   for ax in [ax2,ax4,ax6,ax8]:
        for ax in axlist:
            xlim = ax.get_xlim()
            ylim = ax.get_ylim()
            i0 = int((xlim[0] + NCYE.uxt0 - 101) / 600) + 1
            i1 = int((xlim[1] + NCYE.uxt0 - 101) / 600) + 1
            ax.hold(True)
            for i in range(i0, i1):
                tplt = i * 600 - NCYE.uxt0 + 101
                ax.plot(tplt, ylim[0], 'kd')
                ax.plot(tplt, ylim[1], 'kd')
            ax.hold(False)
            fixlims(ax)

        # plt.draw()

        if options.interactive:
            fig.show()
            print('Click figure window to continue')
            plt.waitforbuttonpress()
        else:
            pdfdir = './pdf/raw-ef-cat'
            pdffile = pdfdir + '/' + pltnam + '.pdf'
            print(pdffile)
            plt.savefig(pdffile)
            os.system('updateframe.run ' + pdfdir)


def compute_raw_cal():
    global HCYC

    HCYC.AB = HCYC.ab.upper()

    if HCYC.ab == 'a':
        HCYC.ma = 'r'
        HCYC.mb = 'b'
    elif HCYC.ab == 'b':
        HCYC.ma = 'b'
        HCYC.mb = 'r'
    else:
        print('unknown ab')
        print_info_and_exit()

    # indices which lop off first nskip_cal points
    j = np.arange(nskip_cal, len(HCYC.secs), dtype=int)

    # find indices which occur during IES comms with HEF
    # HEF data xfr'd to IES about 101 s after IES 10 minute mark
    uxtmj = np.mod(HCYC.uxt[j], 600)
    HCYC.jjm = np.nonzero(np.logical_and(uxtmj > 98, uxtmj < 108))[0]

    HCYC.tj = HCYC.secs[j]
    HCYC.tjjm = HCYC.tj[HCYC.jjm]
    HCYC.j = j

    HCYC.jjjm = j[HCYC.jjm]

    if len(HCYC.tj) > options.fit_order + 1:
        e1a_poly = np.polyfit(HCYC.tj, HCYC.e1a[j], options.fit_order)
        e1b_poly = np.polyfit(HCYC.tj, HCYC.e1b[j], options.fit_order)
        e1c_poly = np.polyfit(HCYC.tj, HCYC.e1c[j], options.fit_order)
        e2a_poly = np.polyfit(HCYC.tj, HCYC.e2a[j], options.fit_order)
        e2b_poly = np.polyfit(HCYC.tj, HCYC.e2b[j], options.fit_order)
        e2c_poly = np.polyfit(HCYC.tj, HCYC.e2c[j], options.fit_order)
        e1a_fit = np.polyval(e1a_poly, HCYC.tj)
        e1b_fit = np.polyval(e1b_poly, HCYC.tj)
        e1c_fit = np.polyval(e1c_poly, HCYC.tj)
        e2a_fit = np.polyval(e2a_poly, HCYC.tj)
        e2b_fit = np.polyval(e2b_poly, HCYC.tj)
        e2c_fit = np.polyval(e2c_poly, HCYC.tj)
        HCYC.e1a_res = HCYC.e1a[j] - e1a_fit
        HCYC.e1b_res = HCYC.e1b[j] - e1b_fit
        HCYC.e1c_res = HCYC.e1c[j] - e1c_fit
        HCYC.e2a_res = HCYC.e2a[j] - e2a_fit
        HCYC.e2b_res = HCYC.e2b[j] - e2b_fit
        HCYC.e2c_res = HCYC.e2c[j] - e2c_fit
    else:
        HCYC.tj = None
        HCYC.e1a_res = None
        HCYC.e1b_res = None
        HCYC.e1c_res = None
        HCYC.e2a_res = None
        HCYC.e2b_res = None
        HCYC.e2c_res = None


def plot_raw_cal():
    compute_raw_cal()

    pyt = datetime(1970, 1, 1, 0, 0, 0) + timedelta(0, HCYC.uxt0)
    pytstr = pyt.strftime('%Y-%m-%d %H:%M:%S')
    pltnam = str.format('{0}-{1:04d}-raw-cal', leafname, count_EC)

    j = HCYC.j

    if HCYC.tj == None:
        print('HCYC.tj == None, pltnam=', pltnam)
        return

    fig = plt.figure(num=1, figsize=(10, 7))
    fig.clf()
    if options.interactive:
        fig.canvas.set_window_title('CAL with IES pings')
    fig.suptitle(pltnam + ' ' + pytstr + ' red:pinched, blu:unpinched')

    ax = fig.add_subplot(7, 2, 1)
    ax.plot(HCYC.tj, HCYC.e1a[j], HCYC.ma)
    ax.hold(True)
    ax.plot(HCYC.tjjm, HCYC.e1a[HCYC.jjjm], 'go')
    ax.hold(False)
    fixlims(ax)
    ax.yaxis.set_major_locator(MaxNLocator(5))
    ax.grid('on')
    ax.xaxis.set_ticklabels([])
    plt.ylabel('e1a, uV')
    plt.title('raw CAL, ' + HCYC.AB + ' pinched')

    ax = fig.add_subplot(7, 2, 3)
    ax.plot(HCYC.tj, HCYC.e1b[j], HCYC.mb)
    ax.hold(True)
    ax.plot(HCYC.tjjm, HCYC.e1b[HCYC.jjjm], 'go')
    ax.hold(False)
    fixlims(ax)
    ax.yaxis.set_major_locator(MaxNLocator(5))
    ax.grid('on')
    ax.xaxis.set_ticklabels([])
    plt.ylabel('e1b, uV')

    ax = fig.add_subplot(7, 2, 5)
    ax.plot(HCYC.tj, HCYC.e1c[j], 'k')
    ax.hold(True)
    ax.plot(HCYC.tjjm, HCYC.e1c[HCYC.jjjm], 'go')
    ax.hold(False)
    fixlims(ax)
    ax.yaxis.set_major_locator(MaxNLocator(5))
    ax.grid('on')
    ax.xaxis.set_ticklabels([])
    plt.ylabel('e1c, uV')

    ax = fig.add_subplot(7, 2, 7)
    ax.plot(HCYC.tj, HCYC.e2a[j], HCYC.ma)
    ax.hold(True)
    ax.plot(HCYC.tjjm, HCYC.e2a[HCYC.jjjm], 'go')
    ax.hold(False)
    fixlims(ax)
    ax.yaxis.set_major_locator(MaxNLocator(5))
    ax.grid('on')
    ax.xaxis.set_ticklabels([])
    plt.ylabel('e2a, uV')

    ax = fig.add_subplot(7, 2, 9)
    ax.plot(HCYC.tj, HCYC.e2b[j], HCYC.mb)
    ax.hold(True)
    ax.plot(HCYC.tjjm, HCYC.e2b[HCYC.jjjm], 'go')
    ax.hold(False)
    fixlims(ax)
    ax.yaxis.set_major_locator(MaxNLocator(5))
    ax.grid('on')
    ax.xaxis.set_ticklabels([])
    plt.ylabel('e2b, uV')

    ax = fig.add_subplot(7, 2, 11)
    ax.plot(HCYC.tj, HCYC.e2c[j], 'k')
    ax.hold(True)
    ax.plot(HCYC.tjjm, HCYC.e2c[HCYC.jjjm], 'go')
    ax.hold(False)
    fixlims(ax)
    ax.yaxis.set_major_locator(MaxNLocator(5))
    ax.grid('on')
    plt.ylabel('e2c, uV')
    plt.xlabel('time, s')

    ax = fig.add_subplot(7, 2, 2)
    ax.plot(HCYC.tj, HCYC.e1a_res, HCYC.ma)
    ax.hold(True)
    ax.plot(HCYC.tjjm, HCYC.e1a_res[HCYC.jjm], 'go')
    ax.hold(False)
    fixlims(ax)
    ax.yaxis.set_major_locator(MaxNLocator(5))
    ax.grid('on')
    ax.xaxis.set_ticklabels([])
    plt.ylabel('e1a-fit, uV')
    plt.title('raw CAL minus fit(order={0})'.format(options.fit_order))

    ax = fig.add_subplot(7, 2, 4)
    ax.plot(HCYC.tj, HCYC.e1b_res, HCYC.mb)
    ax.hold(True)
    ax.plot(HCYC.tjjm, HCYC.e1b_res[HCYC.jjm], 'go')
    ax.hold(False)
    fixlims(ax)
    ax.yaxis.set_major_locator(MaxNLocator(5))
    ax.grid('on')
    ax.xaxis.set_ticklabels([])
    plt.ylabel('e1b-fit, uV')

    ax = fig.add_subplot(7, 2, 6)
    ax.plot(HCYC.tj, HCYC.e1c_res, 'k')
    ax.hold(True)
    ax.plot(HCYC.tjjm, HCYC.e1c_res[HCYC.jjm], 'go')
    ax.hold(False)
    fixlims(ax)
    ax.yaxis.set_major_locator(MaxNLocator(5))
    ax.grid('on')
    ax.xaxis.set_ticklabels([])
    plt.ylabel('e1c-fit, uV')

    ax = fig.add_subplot(7, 2, 8)
    ax.plot(HCYC.tj, HCYC.e2a_res, HCYC.ma)
    ax.hold(True)
    ax.plot(HCYC.tjjm, HCYC.e2a_res[HCYC.jjm], 'go')
    ax.hold(False)
    fixlims(ax)
    ax.yaxis.set_major_locator(MaxNLocator(5))
    ax.grid('on')
    ax.xaxis.set_ticklabels([])
    plt.ylabel('e2a-fit, uV')

    ax = fig.add_subplot(7, 2, 10)
    ax.plot(HCYC.tj, HCYC.e2b_res, HCYC.mb)
    ax.hold(True)
    ax.plot(HCYC.tjjm, HCYC.e2b_res[HCYC.jjm], 'go')
    ax.hold(False)
    fixlims(ax)
    ax.yaxis.set_major_locator(MaxNLocator(5))
    ax.grid('on')
    ax.xaxis.set_ticklabels([])
    plt.ylabel('e2b-fit, uV')

    ax = fig.add_subplot(7, 2, 12)
    ax.plot(HCYC.tj, HCYC.e2c_res, 'k')
    ax.hold(True)
    ax.plot(HCYC.tjjm, HCYC.e2c_res[HCYC.jjm], 'go')
    ax.hold(False)
    fixlims(ax)
    ax.yaxis.set_major_locator(MaxNLocator(5))
    ax.grid('on')
    plt.ylabel('e2c-fit, uV')
    plt.xlabel('time, s')

    t = np.arange(0, len(CAL_STATUS.stat_fast)) * tsamp_ef
    ax.plot(t, CAL_STATUS.stat_fast, 'b')
    ax.grid('on')
    plt.ylabel('stat_fast')
    plt.xlabel('time, s')
    fixlims(ax)

    ax = fig.add_subplot(7, 2, 14)
    ax.plot(HCYC.secs, CAL_STATUS.stat_pick, 'b')
    ax.grid('on')
    plt.ylabel('stat_pick')
    plt.xlabel('time, s')
    fixlims(ax)

    if options.interactive:
        fig.show()
        print('Click figure window to continue')
        plt.waitforbuttonpress()
    else:
        pdffile = './pdf/raw-cal/' + pltnam + '.pdf'
        print(pdffile)
        plt.savefig(pdffile)
        os.system('updateframe.run pdf/raw-cal')


def plot_raw_cal_cat():
    global NCYC
    global count_raw_cal_cat

    # compute_raw_cal()


    # indices which lop off first nskip_cal points
    j = np.arange(nskip_cal, len(HCYC.secs), dtype=int)
    uxt = HCYC.uxt[j]
    e1a = HCYC.e1a[j]
    e1b = HCYC.e1b[j]
    e1c = HCYC.e1c[j]
    e2a = HCYC.e2a[j]
    e2b = HCYC.e2b[j]
    e2c = HCYC.e2c[j]

    abi = np.tile(ord(HCYC.ab), len(j))
    sta = CAL_STATUS.stat_pick[j]
    tpl = uxt - HCYC.uxt0
    stf = CAL_STATUS.stat_fast
    tpf = np.arange(0, len(stf)) * tsamp_ef

    count_raw_cal_cat += 1

    # if len(uxt) < 2:
    #   print('uxt too short: count_raw_cal_cat=',count_raw_cal_cat)
    #   print('  nskip_cal=',nskip_cal)
    #   print('  len(HCYC.secs)=',len(HCYC.secs))
    #   print('  HCYC.secs=',HCYC.secs)
    #   print('  len(j)=',len(j))
    #   print('  tsamp_ef=',tsamp_ef)
    #   print('  tskip_cal=',tskip_cal)
    #   print('  navg_cal=',navg_cal)

    if count_raw_cal_cat == 1:
        NCYC = collections.namedtuple('NCYC', [])
        NCYC.uxt0 = HCYC.uxt0

        NCYC.uxt_cat = uxt
        NCYC.e1a_cat = e1a
        NCYC.e1b_cat = e1b
        NCYC.e1c_cat = e1c
        NCYC.e2a_cat = e2a
        NCYC.e2b_cat = e2b
        NCYC.e2c_cat = e2c

        NCYC.abi_cat = abi
        NCYC.sta_cat = sta
        NCYC.stf_cat = stf
        NCYC.tpl_cat = tpl
        NCYC.tpf_cat = tpf
    else:
        if len(NCYC.tpl_cat) > 0 and np.isfinite(NCYC.tpl_cat[-1]):
            tpl_off = NCYC.tpl_cat[-1] + 5
            tpf_off = NCYC.tpf_cat[-1] + 5
        else:
            tpl_off = 0
            tpf_off = 0

        if len(uxt) > 0:
            # insert nan to lift pen during motor runs
            NCYC.uxt_cat = np.append(NCYC.uxt_cat, np.nan)
            NCYC.e1a_cat = np.append(NCYC.e1a_cat, np.nan)
            NCYC.e1b_cat = np.append(NCYC.e1b_cat, np.nan)
            NCYC.e1c_cat = np.append(NCYC.e1c_cat, np.nan)
            NCYC.e2a_cat = np.append(NCYC.e2a_cat, np.nan)
            NCYC.e2b_cat = np.append(NCYC.e2b_cat, np.nan)
            NCYC.e2c_cat = np.append(NCYC.e2c_cat, np.nan)

            NCYC.abi_cat = np.append(NCYC.abi_cat, np.nan)
            NCYC.sta_cat = np.append(NCYC.sta_cat, np.nan)
            NCYC.stf_cat = np.append(NCYC.stf_cat, np.nan)
            NCYC.tpl_cat = np.append(NCYC.tpl_cat, np.nan)
            NCYC.tpf_cat = np.append(NCYC.tpf_cat, np.nan)

            NCYC.uxt_cat = np.append(NCYC.uxt_cat, uxt)
            NCYC.e1a_cat = np.append(NCYC.e1a_cat, e1a)
            NCYC.e1b_cat = np.append(NCYC.e1b_cat, e1b)
            NCYC.e1c_cat = np.append(NCYC.e1c_cat, e1c)
            NCYC.e2a_cat = np.append(NCYC.e2a_cat, e2a)
            NCYC.e2b_cat = np.append(NCYC.e2b_cat, e2b)
            NCYC.e2c_cat = np.append(NCYC.e2c_cat, e2c)

            NCYC.abi_cat = np.append(NCYC.abi_cat, abi)
            NCYC.sta_cat = np.append(NCYC.sta_cat, sta)
            NCYC.stf_cat = np.append(NCYC.stf_cat, stf)
            NCYC.tpl_cat = np.append(NCYC.tpl_cat, tpl + tpl_off)
            NCYC.tpf_cat = np.append(NCYC.tpf_cat, tpf + tpf_off)

    if count_raw_cal_cat == options.ncat:
        count_raw_cal_cat = 0

        # find indices which occur during IES comms with HEF
        # HEF data xfr'd to IES 1:41 (101 s) after IES 10 minute mark
        tmod = np.mod(NCYC.uxt_cat, 600)
        jies = np.nonzero(np.logical_and(tmod > 98, tmod < 108))[0]

        j = np.nonzero(np.isfinite(NCYC.uxt_cat))[0]
        ja = np.nonzero(NCYC.abi_cat == ord('a'))[0]
        jb = np.nonzero(NCYC.abi_cat == ord('b'))[0]
        if len(j) != len(ja) + len(jb):
            print('plot_raw_cal_cat(): len(j) should equal len(ja) + len(jb)')
            print_info_and_exit()

        tj_cat = NCYC.uxt_cat - NCYC.uxt0

        pyt = datetime(1970, 1, 1, 0, 0, 0) + timedelta(0, NCYC.uxt0)
        pytstr = pyt.strftime('%Y-%m-%d %H:%M:%S')
        pltnam = str.format('{0}-{1:04d}-raw-cal-cat{2}', leafname, count_EC, options.ncat)

        if (len(jb) < options.fit_order + 1) | (len(ja) < options.fit_order + 1):
            print('too few ja or jb, pltnam=', pltnam)
            return

        e1a_poly = np.polyfit(tj_cat[jb], NCYC.e1a_cat[jb], options.fit_order)
        e1b_poly = np.polyfit(tj_cat[ja], NCYC.e1b_cat[ja], options.fit_order)
        e1c_poly = np.polyfit(tj_cat[ja], NCYC.e1c_cat[ja], options.fit_order)
        e2a_poly = np.polyfit(tj_cat[jb], NCYC.e2a_cat[jb], options.fit_order)
        e2b_poly = np.polyfit(tj_cat[ja], NCYC.e2b_cat[ja], options.fit_order)
        e2c_poly = np.polyfit(tj_cat[ja], NCYC.e2c_cat[ja], options.fit_order)
        e1a_fit = np.tile(np.nan, len(tj_cat))
        e1b_fit = np.tile(np.nan, len(tj_cat))
        e1c_fit = np.tile(np.nan, len(tj_cat))
        e2a_fit = np.tile(np.nan, len(tj_cat))
        e2b_fit = np.tile(np.nan, len(tj_cat))
        e2c_fit = np.tile(np.nan, len(tj_cat))
        e1a_fit[j] = np.polyval(e1a_poly, tj_cat[j])
        e1b_fit[j] = np.polyval(e1b_poly, tj_cat[j])
        e1c_fit[j] = np.polyval(e1c_poly, tj_cat[j])
        e2a_fit[j] = np.polyval(e2a_poly, tj_cat[j])
        e2b_fit[j] = np.polyval(e2b_poly, tj_cat[j])
        e2c_fit[j] = np.polyval(e2c_poly, tj_cat[j])
        NCYC.e1a_res_cat = NCYC.e1a_cat - e1a_fit
        NCYC.e1b_res_cat = NCYC.e1b_cat - e1b_fit
        NCYC.e1c_res_cat = NCYC.e1c_cat - e1c_fit
        NCYC.e2a_res_cat = NCYC.e2a_cat - e2a_fit
        NCYC.e2b_res_cat = NCYC.e2b_cat - e2b_fit
        NCYC.e2c_res_cat = NCYC.e2c_cat - e2c_fit

        # include the nan values to lift pen between motor runs
        ja = np.nonzero((NCYC.abi_cat == ord('a')) | np.isnan(NCYC.abi_cat))[0]
        jb = np.nonzero((NCYC.abi_cat == ord('b')) | np.isnan(NCYC.abi_cat))[0]

        mrkp = 'r'  # marker for pinched EF
        mrku = 'c'  # marker for unpinched EF
        mrki = 'k.'  # marker for IES comms

        fig = plt.figure(num=1, figsize=(10, 7))
        fig.clf()
        if options.interactive:
            fig.canvas.set_window_title('CAL with IES pings')
        fig.suptitle(pltnam + ' ' + pytstr + ' red:pinched, cyan:unpinched, blk:IES comms')

        axlist = []

        ax = fig.add_subplot(7, 2, 1)
        ax.hold(True)
        ax.plot(NCYC.tpl_cat[jies], NCYC.e1a_cat[jies], mrki)
        ax.plot(NCYC.tpl_cat[ja], NCYC.e1a_cat[ja], mrkp)
        ax.plot(NCYC.tpl_cat[jb], NCYC.e1a_cat[jb], mrku)
        ax.hold(False)
        ax.grid('on')
        ax.xaxis.set_ticklabels([])
        plt.ylabel('e1a, uV')
        plt.title('raw CAL, tskip={0:.1f} s'.format(tskip_cal))
        ax.yaxis.set_major_locator(MaxNLocator(5))
        fixlims(ax)
        xlim1 = ax.get_xlim()
        axlist.append(ax)

        ax = fig.add_subplot(7, 2, 3)
        ax.hold(True)
        ax.plot(NCYC.tpl_cat[jies], NCYC.e1b_cat[jies], mrki)
        ax.plot(NCYC.tpl_cat[ja], NCYC.e1b_cat[ja], mrku)
        ax.plot(NCYC.tpl_cat[jb], NCYC.e1b_cat[jb], mrkp)
        ax.hold(False)
        ax.grid('on')
        ax.xaxis.set_ticklabels([])
        plt.ylabel('e1b, uV')
        ax.yaxis.set_major_locator(MaxNLocator(5))
        fixlims(ax)
        axlist.append(ax)

        ax = fig.add_subplot(7, 2, 5)
        ax.hold(True)
        ax.plot(NCYC.tpl_cat[jies], NCYC.e1c_cat[jies], mrki)
        ax.plot(NCYC.tpl_cat, NCYC.e1c_cat, mrku)
        ax.hold(False)
        ax.grid('on')
        ax.xaxis.set_ticklabels([])
        plt.ylabel('e1c, uV')
        ax.yaxis.set_major_locator(MaxNLocator(5))
        fixlims(ax)
        axlist.append(ax)

        ax = fig.add_subplot(7, 2, 7)
        ax.hold(True)
        ax.plot(NCYC.tpl_cat[jies], NCYC.e2a_cat[jies], mrki)
        ax.plot(NCYC.tpl_cat[ja], NCYC.e2a_cat[ja], mrkp)
        ax.plot(NCYC.tpl_cat[jb], NCYC.e2a_cat[jb], mrku)
        ax.hold(False)
        ax.grid('on')
        ax.xaxis.set_ticklabels([])
        plt.ylabel('e2a, uV')
        ax.yaxis.set_major_locator(MaxNLocator(5))
        fixlims(ax)
        axlist.append(ax)

        ax = fig.add_subplot(7, 2, 9)
        ax.hold(True)
        ax.plot(NCYC.tpl_cat[jies], NCYC.e2b_cat[jies], mrki)
        ax.plot(NCYC.tpl_cat[ja], NCYC.e2b_cat[ja], mrku)
        ax.plot(NCYC.tpl_cat[jb], NCYC.e2b_cat[jb], mrkp)
        ax.hold(False)
        ax.grid('on')
        ax.xaxis.set_ticklabels([])
        plt.ylabel('e2b, uV')
        ax.yaxis.set_major_locator(MaxNLocator(5))
        fixlims(ax)
        axlist.append(ax)

        ax = fig.add_subplot(7, 2, 11)
        ax.hold(True)
        ax.plot(NCYC.tpl_cat[jies], NCYC.e2c_cat[jies], mrki)
        ax.plot(NCYC.tpl_cat, NCYC.e2c_cat, mrku)
        ax.hold(False)
        ax.grid('on')
        ax.xaxis.set_ticklabels([])
        plt.ylabel('e2c, uV')
        ax.yaxis.set_major_locator(MaxNLocator(5))
        fixlims(ax)
        xlim11 = ax.get_xlim()
        axlist.append(ax)

        ax = fig.add_subplot(7, 2, 2)
        ax.hold(True)
        ax.plot(NCYC.tpl_cat[jies], NCYC.e1a_res_cat[jies], mrki)
        ax.plot(NCYC.tpl_cat[ja], NCYC.e1a_res_cat[ja], mrkp)
        ax.plot(NCYC.tpl_cat[jb], NCYC.e1a_res_cat[jb], mrku)
        ax.hold(False)
        ax.grid('on')
        ax.xaxis.set_ticklabels([])
        plt.ylabel('e1a-fit, uV')
        plt.title('raw CAL minus fit(order={0})'.format(options.fit_order))
        fixlims(ax)
        ax.yaxis.set_major_locator(MaxNLocator(5))
        axlist.append(ax)

        ax = fig.add_subplot(7, 2, 4)
        ax.hold(True)
        ax.plot(NCYC.tpl_cat[jies], NCYC.e1b_res_cat[jies], mrki)
        ax.plot(NCYC.tpl_cat[ja], NCYC.e1b_res_cat[ja], mrku)
        ax.plot(NCYC.tpl_cat[jb], NCYC.e1b_res_cat[jb], mrkp)
        ax.hold(False)
        ax.grid('on')
        ax.xaxis.set_ticklabels([])
        plt.ylabel('e1b-fit, uV')
        ax.yaxis.set_major_locator(MaxNLocator(5))
        fixlims(ax)
        axlist.append(ax)

        ax = fig.add_subplot(7, 2, 6)
        ax.hold(True)
        ax.plot(NCYC.tpl_cat[jies], NCYC.e1c_res_cat[jies], mrki)
        ax.plot(NCYC.tpl_cat, NCYC.e1c_res_cat, mrku)
        ax.hold(False)
        ax.grid('on')
        ax.xaxis.set_ticklabels([])
        plt.ylabel('e1c-fit, uV')
        ax.yaxis.set_major_locator(MaxNLocator(5))
        fixlims(ax)
        axlist.append(ax)

        ax = fig.add_subplot(7, 2, 8)
        ax.hold(True)
        ax.plot(NCYC.tpl_cat[jies], NCYC.e2a_res_cat[jies], mrki)
        ax.plot(NCYC.tpl_cat[ja], NCYC.e2a_res_cat[ja], mrkp)
        ax.plot(NCYC.tpl_cat[jb], NCYC.e2a_res_cat[jb], mrku)
        ax.hold(False)
        ax.grid('on')
        ax.xaxis.set_ticklabels([])
        plt.ylabel('e2a-fit, uV')
        ax.yaxis.set_major_locator(MaxNLocator(5))
        fixlims(ax)
        axlist.append(ax)

        ax = fig.add_subplot(7, 2, 10)
        ax.hold(True)
        ax.plot(NCYC.tpl_cat[jies], NCYC.e2b_res_cat[jies], mrki)
        ax.plot(NCYC.tpl_cat[ja], NCYC.e2b_res_cat[ja], mrku)
        ax.plot(NCYC.tpl_cat[jb], NCYC.e2b_res_cat[jb], mrkp)
        ax.hold(False)
        ax.grid('on')
        ax.xaxis.set_ticklabels([])
        plt.ylabel('e2b-fit, uV')
        ax.yaxis.set_major_locator(MaxNLocator(5))
        fixlims(ax)
        axlist.append(ax)

        ax = fig.add_subplot(7, 2, 12)
        ax.hold(True)
        ax.plot(NCYC.tpl_cat[jies], NCYC.e2c_res_cat[jies], mrki)
        ax.plot(NCYC.tpl_cat, NCYC.e2c_res_cat, mrku)
        ax.hold(False)
        ax.grid('on')
        ax.xaxis.set_ticklabels([])
        plt.ylabel('e2c-fit, uV')
        ax.yaxis.set_major_locator(MaxNLocator(5))
        fixlims(ax)
        axlist.append(ax)

        ax = fig.add_subplot(7, 2, 13)
        #   print('len(NCYC.tpf_cat)=',len(NCYC.tpf_cat),'len(NCYC.stf_cat)=',len(NCYC.stf_cat))
        ax.plot(NCYC.tpf_cat, NCYC.stf_cat, 'b')
        ax.grid('on')
        plt.ylabel('stat_fast')
        plt.xlabel('time, s')
        ax.set_xlim(xlim11)
        fixlims(ax)
        axlist.append(ax)

        ax = fig.add_subplot(7, 2, 14)
        ax.plot(NCYC.tpl_cat, NCYC.sta_cat, 'b')
        ax.grid('on')
        plt.ylabel('stat_pick')
        plt.xlabel('time, s')
        fixlims(ax)
        axlist.append(ax)

        for ax in axlist:
            ax.set_xlim(xlim1)

        if options.interactive:
            fig.show()
            print('Click figure window to continue')
            plt.waitforbuttonpress()
        else:
            pdffile = './pdf/raw-cal-cat/' + pltnam + '.pdf'
            print(pdffile)
            plt.savefig(pdffile)
            os.system('updateframe.run pdf/raw-cal-cat')


def plot_hef_overlay():
    if len(hef_ind_a) == 0 and len(hef_ind_b) == 0:
        return

    # convert ADC counts to microvolts at preamp input
    # flip sign of "b" because "b" preamp input opposite of "a"

    secs_a = np.array(hef_ind_a, dtype='double') * tsamp_ef
    e1a_a = np.array(hef_e1a_a, dtype='double')
    e1b_a = np.array(hef_e1b_a, dtype='double')
    e2a_a = np.array(hef_e2a_a, dtype='double')
    e2b_a = np.array(hef_e2b_a, dtype='double')

    secs_b = np.array(hef_ind_b, dtype='double') * tsamp_ef
    e1a_b = np.array(hef_e1a_b, dtype='double')
    e1b_b = np.array(hef_e1b_b, dtype='double')
    e2a_b = np.array(hef_e2a_b, dtype='double')
    e2b_b = np.array(hef_e2b_b, dtype='double')

    fig = plt.figure()
    if options.interactive:
        fig.canvas.set_window_title('HEF Ocean')
    fig.suptitle(leafname + ' red:A, blu:B')

    ax = fig.add_subplot(4, 2, 1)
    ax.plot(secs_a, e1a_a, 'r.-')
    ax.grid('on')
    plt.ylabel('e1a, uV')
    plt.title('A pinched')

    ax = fig.add_subplot(4, 2, 3)
    ax.plot(secs_a, e1b_a, 'b.-')
    ax.grid('on')
    plt.ylabel('e1b, uV')

    ax = fig.add_subplot(4, 2, 5)
    ax.plot(secs_a, e2a_a, 'r.-')
    ax.grid('on')
    plt.ylabel('e2a, uV')

    ax = fig.add_subplot(4, 2, 7)
    ax.plot(secs_a, e2b_a, 'b.-')
    ax.grid('on')
    plt.ylabel('e2b, uV')
    plt.xlabel('time, s')

    ax = fig.add_subplot(4, 2, 2)
    ax.plot(secs_b, e1a_b, 'r.-')
    ax.grid('on')
    plt.title('B pinched')

    ax = fig.add_subplot(4, 2, 4)
    ax.plot(secs_b, e1b_b, 'b.-')
    ax.grid('on')

    ax = fig.add_subplot(4, 2, 6)
    ax.plot(secs_b, e2a_b, 'r.-')
    ax.grid('on')

    ax = fig.add_subplot(4, 2, 8)
    ax.plot(secs_b, e2b_b, 'b.-')
    ax.grid('on')
    plt.xlabel('time, s')

    plt.draw()


def plot_cal():
    if len(cal_ind_a) == 0 and len(cal_ind_b) == 0:
        return

    # convert ADC counts to microvolts at preamp input
    # flip sign of "b" because "b" preamp input opposite of "a"

    secs_a = np.array(cal_ind_a, dtype='double') * tsamp_ef
    e1c_a = np.array(cal_e1c_a, dtype='double')
    e1a_a = np.array(cal_e1a_a, dtype='double')
    e1b_a = np.array(cal_e1b_a, dtype='double')
    e2c_a = np.array(cal_e2c_a, dtype='double')
    e2a_a = np.array(cal_e2a_a, dtype='double')
    e2b_a = np.array(cal_e2b_a, dtype='double')

    secs_b = np.array(cal_ind_b, dtype='double') * tsamp_ef
    e1c_b = np.array(cal_e1c_b, dtype='double')
    e1a_b = np.array(cal_e1a_b, dtype='double')
    e1b_b = np.array(cal_e1b_b, dtype='double')
    e2c_b = np.array(cal_e2c_b, dtype='double')
    e2a_b = np.array(cal_e2a_b, dtype='double')
    e2b_b = np.array(cal_e2b_b, dtype='double')

    fig = plt.figure()
    if options.interactive:
        fig.canvas.set_window_title('HEF Cal Data')
    fig.suptitle(leafname + ' red:A, blu:B, grn:C')

    ax = fig.add_subplot(2, 2, 1)
    ax.plot(secs_a, e1a_a, 'r.-')
    ax.hold('on')
    ax.plot(secs_a, e1b_a, 'b.-')
    ax.plot(secs_a, e1c_a, 'g.-')
    ax.hold('off')
    ax.grid('on')
    plt.ylabel('e1, uV')
    plt.title('A pinched')

    ax = fig.add_subplot(2, 2, 2)
    ax.plot(secs_b, e1a_b, 'r.-')
    ax.hold('on')
    ax.plot(secs_b, e1b_b, 'b.-')
    ax.plot(secs_b, e1c_b, 'g.-')
    ax.hold('off')
    ax.grid('on')
    plt.title('B pinched')

    ax = fig.add_subplot(2, 2, 3)
    ax.plot(secs_a, e2a_a, 'r.-')
    ax.hold('on')
    ax.plot(secs_a, e2b_a, 'b.-')
    ax.plot(secs_a, e2c_a, 'g.-')
    ax.hold('off')
    ax.grid('on')
    plt.ylabel('e2, uV')

    ax = fig.add_subplot(2, 2, 4)
    ax.plot(secs_b, e2a_b, 'r.-')
    ax.hold('on')
    ax.plot(secs_b, e2b_b, 'b.-')
    ax.plot(secs_b, e2c_b, 'g.-')
    ax.hold('off')
    ax.grid('on')

    plt.draw()


def plot_compass():
    secs = np.array(comp_uxt, dtype='double')
    secs = secs - secs[-1]

    hdg = np.array(comp_hdg, dtype='double') * 360.0 / 4096.0
    pitch = np.array(comp_pitch, dtype='double') * 90.0 / 4096.0
    roll = np.array(comp_roll, dtype='double') * 180.0 / 4096.0
    temp = np.array(comp_temp, dtype='double') * 0.1

    fig = plt.figure()
    if options.interactive:
        fig.canvas.set_window_title('Compass')
    fig.suptitle(leafname + ' plot_compass')

    ax = fig.add_subplot(4, 1, 1)
    ax.plot(secs, hdg, 'ro-')
    ax.grid('on')
    plt.ylabel('Hdg')

    ax = fig.add_subplot(4, 1, 2)
    ax.plot(secs, pitch, 'bo-')
    ax.grid('on')
    plt.ylabel('Pitch')

    ax = fig.add_subplot(4, 1, 3)
    ax.plot(secs, roll, 'bo-')
    ax.grid('on')
    plt.ylabel('Roll')

    ax = fig.add_subplot(4, 1, 4)
    ax.plot(secs, temp, 'bo-')
    ax.grid('on')
    plt.ylabel('Temp')

    plt.xlabel('Time, s')
    plt.draw()


def initbufs():
    global aux_uxt, aux_tt1, aux_tt2, aux_tt3, aux_tt4
    global aux_pres, aux_temp, aux_btemp, aux_bfreq
    global aux_uxt_xfr
    aux_uxt = []
    aux_tt1 = []
    aux_tt2 = []
    aux_tt3 = []
    aux_tt4 = []
    aux_pres = []
    aux_temp = []
    aux_btemp = []
    aux_bfreq = []
    aux_uxt_xfr = []

    global comp_uxt, comp_hdg, comp_pitch, comp_roll, comp_temp
    comp_uxt = []
    comp_hdg = []
    comp_pitch = []
    comp_roll = []
    comp_temp = []

    global mot_ind_a, mot_cur_a, mot_ind_b, mot_cur_b
    mot_ind_a = []
    mot_ind_b = []
    mot_cur_a = []
    mot_cur_b = []

    global hef_ind_a, hef_ind_b
    hef_ind_a = []
    hef_ind_b = []

    global hef_e1a_a, hef_e1b_a, hef_e2a_a, hef_e2b_a
    hef_e1a_a = []
    hef_e1b_a = []
    hef_e2a_a = []
    hef_e2b_a = []

    global hef_e1a_b, hef_e1b_b, hef_e2a_b, hef_e2b_b
    hef_e1a_b = []
    hef_e1b_b = []
    hef_e2a_b = []
    hef_e2b_b = []

    global cal_ind_a, cal_ind_b
    cal_ind_a = []
    cal_ind_b = []

    global cal_e1a_a, cal_e1b_a, cal_e1c_a
    cal_e1a_a = []
    cal_e1b_a = []
    cal_e1c_a = []

    global cal_e2a_a, cal_e2b_a, cal_e2c_a
    cal_e2a_a = []
    cal_e2b_a = []
    cal_e2c_a = []

    global cal_e1a_b, cal_e1b_b, cal_e1c_b
    cal_e1a_b = []
    cal_e1b_b = []
    cal_e1c_b = []

    global cal_e2a_b, cal_e2b_b, cal_e2c_b
    cal_e2a_b = []
    cal_e2b_b = []
    cal_e2c_b = []


def initcounts():
    global count_tod, count_hef, count_aux
    count_tod = 0
    count_hef = 0
    count_aux = 0

    global count_crc_ok, count_bad_crc_check, count_bad_crc_decode
    count_crc_ok = 0
    count_bad_crc_check = 0
    count_bad_crc_decode = 0

    global count_crc_missing;
    count_crc_missing = 0

    global count_M
    count_M = 0

    global count_EC
    count_EC = 0

    global count_E
    count_E = 0

    global count_compass
    count_compass = 0

    global count_C
    count_C = 0

    global count_hef_unknown
    count_hef_unknown = 0

    global lineno, count_lineok, count_skipped
    lineno = 0
    count_lineok = 0
    count_skipped = 0


def printcounts():
    print('lineno              =', lineno)
    print('count_skipped      =', count_skipped)
    print('count_lineok        =', count_lineok)
    print('count_crc_ok        =', count_crc_ok)
    print('count_crc_missing   =', count_crc_missing)
    print('count_bad_crc_check =', count_bad_crc_check)
    print('count_bad_crc_decode=', count_bad_crc_decode)
    print('count_tod=', count_tod)
    print('count_hef=', count_hef)
    print('count_aux=', count_aux)
    print('count_EC =', count_EC)
    print('count_E  =', count_E)
    print('count_C  =', count_C)
    print('count_M  =', count_M)
    print('count_compass=', count_compass)
    print('count_hef_unknown=', count_hef_unknown)


def printsizes():
    print('len(aux_uxt  )=', len(aux_uxt))
    if options.verbose:
        print('len(aux_tt1   )=', len(aux_tt1))
        print('len(aux_tt2   )=', len(aux_tt2))
        print('len(aux_tt3   )=', len(aux_tt3))
        print('len(aux_tt4   )=', len(aux_tt4))
        print('len(aux_pres  )=', len(aux_pres))
        print('len(aux_temp  )=', len(aux_temp))
        print('len(aux_btemp )=', len(aux_btemp))
        print('len(aux_bfreq )=', len(aux_bfreq))

    print('len(comp_uxt )=', len(comp_uxt))
    if options.verbose:
        print('len(comp_hdg  )=', len(comp_hdg))
        print('len(comp_pitch)=', len(comp_pitch))
        print('len(comp_roll )=', len(comp_roll))
        print('len(comp_temp )=', len(comp_temp))

    print('len(mot_ind_a )=', len(mot_ind_a))
    if options.verbose:
        print('len(mot_cur_a )=', len(mot_cur_a))

    print('len(mot_ind_b )=', len(mot_ind_b))
    if options.verbose:
        print('len(mot_cur_b )=', len(mot_cur_b))

    print('len(hef_ind_a )=', len(hef_ind_a))
    if options.verbose:
        print('len(hef_e1a_a )=', len(hef_e1a_a))
        print('len(hef_e1b_a )=', len(hef_e1b_a))
        print('len(hef_e2a_a )=', len(hef_e2a_a))
        print('len(hef_e2b_a )=', len(hef_e2b_a))

    print('len(hef_ind_b )=', len(hef_ind_b))
    if options.verbose:
        print('len(hef_e1a_b )=', len(hef_e1a_b))
        print('len(hef_e1b_b )=', len(hef_e1b_b))
        print('len(hef_e2a_b )=', len(hef_e2a_b))
        print('len(hef_e2b_b )=', len(hef_e2b_b))

    print('len(cal_ind_a )=', len(cal_ind_a))
    if options.verbose:
        print('len(cal_e1a_a )=', len(cal_e1a_a))
        print('len(cal_e1b_a )=', len(cal_e1b_a))
        print('len(cal_e1c_a )=', len(cal_e1c_a))
        print('len(cal_e2a_a )=', len(cal_e2a_a))
        print('len(cal_e2b_a )=', len(cal_e2b_a))
        print('len(cal_e2c_a )=', len(cal_e2c_a))

    print('len(cal_ind_b )=', len(cal_ind_b))
    if options.verbose:
        print('len(cal_e1a_b )=', len(cal_e1a_b))
        print('len(cal_e1b_b )=', len(cal_e1b_b))
        print('len(cal_e1c_b )=', len(cal_e1c_b))
        print('len(cal_e2a_b )=', len(cal_e2a_b))
        print('len(cal_e2b_b )=', len(cal_e2b_b))
        print('len(cal_e2c_b )=', len(cal_e2c_b))


def print_info_and_exit():
    print('ERROR:')
    print('  ifile=', ifile)
    print('  lineno=', lineno)
    print('  linein=', linein)
    sys.exit(1)


def gz_open(ifile):
    if ifile[-3:] == '.gz':
        try:
            ifd = gzip.open(ifile, 'rt')
        except:
            print('cannot open ifile=', ifile)
            sys.exit(1)
    else:
        try:
            ifd = gzip.open(ifile + '.gz', 'rt')
        except:
            try:
                ifd = open(ifile, 'rt')
            except:
                print('cannot open ifile=', ifile)
                sys.exit(1)
    return ifd


def larger_axlim(axlim):
    """ argument axlim expects 2-tuple 
        returns slightly larger 2-tuple """
    axmin, axmax = axlim
    axrng = axmax - axmin
    new_min = axmin - 0.03 * axrng
    new_max = axmax + 0.03 * axrng
    return new_min, new_max


def fixlims(ax):
    ax.set_xlim(larger_axlim(ax.get_xlim()))
    ax.set_ylim(larger_axlim(ax.get_ylim()))


def initAVG():
    global AVG
    AVG = collections.namedtuple('AVG', [])
    AVG.nuse = []
    AVG.ab = []
    AVG.uxt = []
    AVG.e1a = []
    AVG.e1b = []
    AVG.e2a = []
    AVG.e2b = []
    AVG.e1a_std = []
    AVG.e1b_std = []
    AVG.e2a_std = []
    AVG.e2b_std = []
    AVG.e1a_poly_std = []
    AVG.e1b_poly_std = []
    AVG.e2a_poly_std = []
    AVG.e2b_poly_std = []

# main
if __name__ == '__main__':

    aux_flag = False
    plot_raw_cal_flag = False
    plot_raw_mot_flag = False

    tsamp_motor = 0.025
    tsamp_ef = 0.1024

    parser = OptionParser(
        usage="%prog [Options] ifile[s]",
        version="%prog 1.0")

    parser.add_option("-v", "--verbose", dest="verbose",
                      action="store_true", default=False,
                      help="print debug info to stdout")

    parser.add_option("-i", "--interactive", dest="interactive",
                      action="store_true", default=False,
                      help="interactive plotting")

    parser.add_option("-x", "--extra", dest="do_extra",
                      action="store_true", default=False,
                      help="print counts and sizes")

    parser.add_option("-o", "--plot_overlay", dest="do_plot_overlay",
                      action="store_true", default=False,
                      help="plot data after each pinch on same axis")

    parser.add_option("-a", "--plot_avgs", dest="do_plot_avgs",
                      action="store_true", default=False,
                      help="plot avg data [default: %default]")

    parser.add_option("-e", "--plot_raw_ef", dest="do_plot_raw_ef",
                      action="store_true", default=False,
                      help="plot raw hef, green = IES data request times")

    parser.add_option("-c", "--plot_raw_cal", dest="do_plot_raw_cal",
                      action="store_true", default=False,
                      help="plot raw cal, green = IES data request times")

    parser.add_option("-m", "--plot_raw_mot", dest="do_plot_raw_mot",
                      action="store_true", default=False,
                      help="plot raw motor current")

    parser.add_option("-n", "--ncat", dest="ncat",
                      type="int", metavar="N", default=0,
                      help="number of half cycles for raw plots [default: %default]")

    parser.add_option("-l", "--limEC", dest="limEC",
                      type="int", metavar="N", default=0,
                      help="Limit to count_EC per file for raw plots [default: %default]")

    parser.add_option("-s", "--tskip", dest="tskip",
                      type="float", metavar="T", default=0,
                      help="skip T seconds [default: %default]")

    parser.add_option("-p", "--polynomial_fit_order", dest="fit_order",
                      type="int", metavar="N", default=1,
                      help="fitting order for ef_raw residual plots [default: %default]")

    (options, args) = parser.parse_args()

    if options.interactive:
        try:
            __IPYTHON__
        except:
            print('cannot use "--interactive" unless running in ipython')
            sys.exit()

    if len(args) < 1:
        parser.print_help()
        sys.exit()

    print('tskip=', options.tskip, 'seconds')
    print('fit_order=', options.fit_order)

    ab = None
    iscan = 0
    nscan = 0

    ifiles = []
    for arg in args:
        for ifile in glob.glob(arg):
            ifiles.append(ifile)
        for ifile in glob.glob(arg + '.gz'):
            ifiles.append(ifile)

    print('len(ifiles)=', len(ifiles))

    for ifile in sorted(ifiles):
        print('ifile=', ifile)

        ifd = gz_open(ifile)

        leafname = os.path.basename(ifile)

        i = leafname.find('.gz')
        if i > 0:
            leafname = leafname[:i]

        runid, uxt_poly_ref, uxt_poly_coef = okmc_info(leafname)
        print('runid=', runid)

        count_raw_mot_cat = 0
        count_raw_cal_cat = 0
        count_raw_ef_cat = 0

        initbufs()
        initcounts()
        initAVG()

        for linein in ifd:
            lineno += 1

            # use only those lines with iso8601 time followed by #N_
            if linein.find('T') != 8 or linein.find(' #') != 15 or linein.find('_') != 18:
                count_skipped += 1
                continue

            iso = linein[:15]
            line = linein[16:]

            count_lineok += 1

            # time of day from RSN
            if line[0:3] == '#2_':
                check_crc(line)
                split_tod(line)
                count_tod += 1

            # HEF data
            if line[0:3] == '#3_':
                check_crc(line)
                split_hef(line)
                if hef_split != None:
                    decode_hef_hdr()
                    check_hef_time()
                    append_hef_data()  # also plots raw ef
                    decode_cal_status()  # also plots raw cal
                    decode_mot_status()  # also plots raw mot
                    append_compass()
                    count_hef += 1

            # IES data from its AUX2 port
            if line[0:3] == '#5_':
                check_crc(line)
                split_aux(line)
                append_aux()
                count_aux += 1

        ifd.close()

        if options.do_extra:
            printcounts()
            printsizes()

        if count_lineok == 0:
            print('no data found')
            sys.exit(1)

        if options.do_plot_overlay:
            plot_mot_overlay()
            plot_hef_overlay()
            plot_cal()
            plot_compass()
            plot_tt()
            plot_pres_temp()
            plot_bliley()
            plt.show()

        if options.do_plot_avgs:
            plot_ef_avg_std()
            # plt.show()
