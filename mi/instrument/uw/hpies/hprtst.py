#!/usr/bin/env python2
# hprtst.py -- test HPIES-RSN
# John Dunlap, APL/UW
# updated Mar 21, 2014

"""
Add network to ohm (Linux):
  sudo /sbin/ifconfig eth0:1 10.180.80.91 netmask 255.255.255.0
  ./hprtst.py -j 10.180.80.174

Add network to Windows:
  ifconfig # find name of LAN to use.  If it's "Local Area Connection 5" then:
  netsh interface ip add address "Local Area Connection 5" 10.180.80.xxx  255.255.255.0
  hprtst.py -j 10.180.80.174

Adjust DigiOneSP via its web interface:
  http://10.180.10.174/
  User Name: root
  Password: dbps
  Serial Port
  Basic Serial Settings
  Advanced Serial Settings

Using DigiConnect's DigiOneSP with C-Kermit on Linux:
  ohm: kermit
  ohm: C-Kermit> set host 10.180.80.174:2101 /raw-socket
  ohm: C-Kermit> set tcp nodelay on
  ohm: C-Kermit> connect

To allow ohm to use henry:/dev/ttyR1 using socat:
  ohm: ssh -L 9101:localhost:9999 henry.apl.uw.edu
  henry: socat TCP4-LISTEN:9999,reuseaddr,fork /dev/ttyR1,raw,echo=0 &
  henry: ./hprtod.py & # sends time-of-day strings to /dev/ttyR2
  ohm: ./hprtst.py -j localhost:9101
or
  ohm: kermit
  ohm: C-Kermit> set host localhost:9101 /raw-socket
  ohm: C-Kermit> set tcp nodelay on
  ohm: C-Kermit> connect

To install boot loader see ohm:stm32/trunk/gnicl/flashing.txt
Move jumper boot0 to two pins closest to console port
Apply power
cd ~/stm32/trunk/iap/
../../tools/stm32load.py -p /dev/ttyRP1 -w -e -v iap_F1_38400.bin

"""

from __future__ import print_function


# todo:
#  add UTC times to plots
#  load old data into queues on request
#  HEF & IES clocks should be set from 1pps stream
#  add cmds and clicks to logfile

import Tkinter
import time
import threading
import Queue
import serial
import sys
from calendar import timegm
from datetime import datetime
import socket
import shlex
import subprocess
from collections import deque
import numpy as np
import matplotlib.pyplot as plt
import os
from optparse import OptionParser

from crclib import crc3kerm, chksumnmea
from locktty import lock_tty, unlock_tty

py_debug = 0
crc_bad_count = 0
crc_ok_count = 0
aux_line_count = 0
hef_line_count = 0
hef_hdr_mot_count = 0
hef_hdr_ef_count = 0
hef_hdr_cal_count = 0
hef_hdr_unknown_count = 0
hef_compass_count = 0

# convert string to printable characters
def mkpr(s):
    o = []
    o.append('[')
    for i in range(len(s)):
        c = s[i]
        k = ord(c)
        if k >= 32 and k <= 127:
            o.append(c)
        elif c == '\r':
            o.append('\\r')
        elif c == '\n':
            o.append('\\n')
        elif c == '\t':
            o.append('\\t')
        else:
            o.append('<{0:02X}>'.format(k))
    o.append(']')
    return ''.join(o)


# return current date/time in ISO8601 format
def iso8601now():
    return datetime.utcnow().strftime('%Y%m%dT%H%M%S')


def uxtnow():
    utcnow = datetime.utcnow()
    return timegm(utcnow.timetuple()) + utcnow.microsecond * 1e-6


def lockall():
    lock_tty(stm_tty)
    lock_tty(tod_tty)
    lock_tty(hef_tty)
    lock_tty(ies_tty)
    lock_tty(aux_tty)


def closeall():
    global stm_ser

    if jbox_tcp:
        jbox_tcp.close()
        print('jbox_tcp closed')
    if stm_ser:
        stm_ser.close()
        stm_ser = None
        unlock_tty(stm_tty)
        print('stm_ser closed')
    if tod_ser:
        tod_ser.close()
        unlock_tty(tod_tty)
        print('tod_ser closed')
    if hef_ser:
        hef_ser.close()
        unlock_tty(hef_tty)
        print('hef_ser closed')
    if ies_ser:
        ies_ser.close()
        unlock_tty(ies_tty)
        print('ies_ser closed')
    if aux_ser:
        aux_ser.close()
        unlock_tty(aux_tty)
        print('aux_ser closed')


def cleanup():
    # print('cleanup()')

    if termem_mode:
        termem_stop()
    closeall()

    # use this instead of sys.exit() when there are several threads
    if is_linux:
        os._exit(0)
    else:
        sys.exit('cleanup() done, perhaps press return')


def py_debug_increment():
    global py_debug
    py_debug += 1
    print('py_debug=', py_debug)


def py_debug_off():
    global py_debug
    py_debug = 0
    print('py_debug=', py_debug)


class GuiPart:
    def __init__(self, master, queue, my_quit):
        self.queue = queue
        # Set up the GUI

        A1 = Tkinter.Button(master, text='Reboot STM', command=reboot_stm32)
        A1.grid(row=1, column=1, sticky=Tkinter.W)

        A7 = Tkinter.Button(master, text='Comm Stats', command=comm_stats)
        A7.grid(row=7, column=1, columnspan=2, sticky=Tkinter.W)

        A9 = Tkinter.Button(master, text='Open All STM Ports', command=open_all)
        A9.grid(row=9, column=1, sticky=Tkinter.W)

        A10 = Tkinter.Button(master, text='Close All STM Ports', command=close_all)
        A10.grid(row=10, column=1, sticky=Tkinter.W)

        A12 = Tkinter.Button(master, text='Term Em Start', command=termem_start)
        A12.grid(row=12, column=1, sticky=Tkinter.W)

        A13 = Tkinter.Button(master, text='Term Em Stop', command=termem_stop)
        A13.grid(row=13, column=1, sticky=Tkinter.W)

        A20 = Tkinter.Button(master, text='STM Debug ++', command=stm_debug_increment)
        A20.grid(row=20, column=1, sticky=Tkinter.W)

        A21 = Tkinter.Button(master, text='STM Debug Off', command=stm_debug_off)
        A21.grid(row=21, column=1, sticky=Tkinter.W)

        A8 = Tkinter.Button(master, text='STM Dir', command=stm32_dir)
        A8.grid(row=8, column=1, sticky=Tkinter.W)

        B1 = Tkinter.Button(master, text='STM DAQ Start', command=stm_daq_start)
        B1.grid(row=1, column=2, columnspan=1, sticky=Tkinter.E)

        B2 = Tkinter.Button(master, text='HEF Opto On', command=hef_opto_on)
        B2.grid(row=2, column=2, columnspan=1, sticky=Tkinter.E)

        B3 = Tkinter.Button(master, text='HEF Power On', command=hef_pwr_on)
        B3.grid(row=3, column=2, sticky=Tkinter.E)

        B4 = Tkinter.Button(master, text='HEF Wake', command=hef_wake)
        B4.grid(row=4, column=2, columnspan=1, sticky=Tkinter.E)

        C1 = Tkinter.Button(master, text='STM DAQ Stop', command=stm_daq_stop)
        C1.grid(row=1, column=3, columnspan=1, sticky=Tkinter.W)

        C2 = Tkinter.Button(master, text='HEF Opto Off', command=hef_opto_off)
        C2.grid(row=2, column=3, columnspan=4, sticky=Tkinter.W)

        C3 = Tkinter.Button(master, text='HEF Power Off', command=hef_pwr_off)
        C3.grid(row=3, column=3, sticky=Tkinter.W)

        B7 = Tkinter.Button(master, text='IES Power On', command=ies_pwr_on)
        B7.grid(row=7, column=2, sticky=Tkinter.E)

        C7 = Tkinter.Button(master, text='IES Power Off', command=ies_pwr_off)
        C7.grid(row=7, column=3, sticky=Tkinter.W)

        B6 = Tkinter.Button(master, text='IES Opto On', command=ies_opto_on)
        B6.grid(row=6, column=2, sticky=Tkinter.E)

        C6 = Tkinter.Button(master, text='IES Opto Off', command=ies_opto_off)
        C6.grid(row=6, column=3, sticky=Tkinter.W)

        B8 = Tkinter.Button(master, text='IES Space Bar', command=ies_space_bar)
        B8.grid(row=8, column=2, sticky=Tkinter.E)

        A22 = Tkinter.Button(master, text='PY Debug ++', command=py_debug_increment)
        A22.grid(row=22, column=1, sticky=Tkinter.W)

        A23 = Tkinter.Button(master, text='PY Debug Off', command=py_debug_off)
        A23.grid(row=23, column=1, sticky=Tkinter.W)

        A24 = Tkinter.Button(master, text='Exit hprtst.py', command=my_quit)
        A24.grid(row=24, column=1, sticky=Tkinter.W)

        B10e = Tkinter.Entry(master, width=10)
        B10e.delete(0, Tkinter.END)
        B10e.insert(0, '3 30')
        B10e.grid(row=10, column=3, columnspan=1, sticky=Tkinter.W)
        B10e.focus_set()

        def B10_call_back():
            args = B10e.get()
            print('PY: samp stats on', args)
            hef_cmd('samp stats on ' + args)

        B10 = Tkinter.Button(master, text='HEF Samp Stats', command=B10_call_back)
        B10.grid(row=10, column=2, columnspan=1, sticky=Tkinter.E)

        B11 = Tkinter.Button(master, text='HEF Samp Stats Off', command=hef_samp_stats_off)
        B11.grid(row=11, column=2, columnspan=2, sticky=Tkinter.W)

        B12e = Tkinter.Entry(master, width=10)
        B12e.delete(0, Tkinter.END)
        B12e.insert(0, '15 3')
        B12e.grid(row=12, column=3, columnspan=1, sticky=Tkinter.W)
        B12e.focus_set()

        def B12_call_back():
            args = B12e.get()
            hef_cmd('samp cal on ' + args)

        B12 = Tkinter.Button(master, text='HEF Cal Test', command=B12_call_back)
        B12.grid(row=12, column=2, columnspan=1, sticky=Tkinter.E)

        B13e = Tkinter.Entry(master, width=10)
        B13e.delete(0, Tkinter.END)
        B13e.insert(0, '10')
        B13e.grid(row=13, column=3, columnspan=1, sticky=Tkinter.W)
        B13e.focus_set()

        def B13_call_back():
            args = B13e.get()
            clear_cal()
            hef_cmd('send cal data ' + args)

        B13 = Tkinter.Button(master, text='Get Cal Data', command=B13_call_back)
        B13.grid(row=13, column=2, columnspan=1, sticky=Tkinter.E)

        B14 = Tkinter.Button(master, text='Plot Cal E1', command=plot_cal_e1)
        B14.grid(row=14, column=2, columnspan=1, sticky=Tkinter.E)

        B14 = Tkinter.Button(master, text='Plot Cal E2', command=plot_cal_e2)
        B14.grid(row=14, column=3, columnspan=1, sticky=Tkinter.W)

        B20 = Tkinter.Button(master, text='Show HEF Params', command=hef_params)
        B20.grid(row=20, column=2, columnspan=1, sticky=Tkinter.W)

        B21e = Tkinter.Entry(master, width=10)
        B21e.grid(row=21, column=3, columnspan=1, sticky=Tkinter.W)
        B21e.insert(0, 'mmmddx')
        B21e.focus_set()

        def B21_call_back():
            hef_prefix = B21e.get()
            print('PY: hef_prefix:', hef_prefix)
            hef_cmd('prefix ' + hef_prefix)

        B21 = Tkinter.Button(master, text='Set HEF Prefix:', command=B21_call_back)
        B21.grid(row=21, column=2, columnspan=1, sticky=Tkinter.E)

        B22 = Tkinter.Button(master, text='HEF Start', command=hef_mission_start)
        B22.grid(row=22, column=2, columnspan=1, sticky=Tkinter.E)

        B23 = Tkinter.Button(master, text='HEF Stats', command=hef_stats)
        B23.grid(row=23, column=2, columnspan=1, sticky=Tkinter.E)

        C22 = Tkinter.Button(master, text='HEF Stop', command=hef_mission_stop)
        C22.grid(row=22, column=3, columnspan=1, sticky=Tkinter.W)

        A15e = Tkinter.Entry(master, width=30)
        A15e.grid(row=15, column=2, columnspan=3, sticky=Tkinter.W)
        A15e.focus_set()

        def A15_call_back():
            stm_str = A15e.get()
            print('PY: stm_str:', stm_str)
            stm_cmd(stm_str)

        A15 = Tkinter.Button(master, text='STM Cmd:', command=A15_call_back)
        A15.grid(row=15, column=1, columnspan=1, sticky=Tkinter.E)

        A16e = Tkinter.Entry(master, width=30)
        A16e.grid(row=16, column=2, columnspan=3, sticky=Tkinter.W)
        A16e.focus_set()

        def A16_call_back():
            hef_str = A16e.get()
            print('PY: hef_str:', hef_str)
            hef_cmd(hef_str)

        A16 = Tkinter.Button(master, text='HEF Cmd:', command=A16_call_back)
        A16.grid(row=16, column=1, columnspan=1, sticky=Tkinter.E)

        A17e = Tkinter.Entry(master, width=30)
        A17e.grid(row=17, column=2, columnspan=3, sticky=Tkinter.W)
        A17e.focus_set()

        def A17_call_back():
            ies_str = A17e.get()
            ies_cmd(ies_str)

        A17 = Tkinter.Button(master, text='IES Cmd:', command=A17_call_back)
        A17.grid(row=17, column=1, columnspan=1, sticky=Tkinter.E)

        A18e = Tkinter.Entry(master, width=30)
        A18e.grid(row=18, column=2, columnspan=3, sticky=Tkinter.W)
        A18e.focus_set()

        def A18_call_back():
            linux_str = A18e.get()
            lin_cmd(linux_str)

        A18 = Tkinter.Button(master, text='Linux Cmd:', command=A18_call_back)
        A18.grid(row=18, column=1, columnspan=1, sticky=Tkinter.E)

        A19e = Tkinter.Entry(master, width=30)
        A19e.delete(0, Tkinter.END)
        if options.jbox_hostname:
            lbl = options.jbox_hostname
        else:
            lbl = str.format('{0}', stm_baud)
        A19e.insert(0, lbl)
        A19e.grid(row=19, column=2, columnspan=2, sticky=Tkinter.W)
        A19e.focus_set()

        def A19_call_back():
            baud_str = A19e.get()
            new_baud(baud_str)

        if options.jbox_hostname:
            lbl = 'Jbox host:port'
        else:
            lbl = 'STM Baud Rate'
        A19 = Tkinter.Button(master, text=lbl, command=A19_call_back)
        A19.grid(row=19, column=1, columnspan=1, sticky=Tkinter.E)

        A3 = Tkinter.Button(master, text='Set STM Time', command=set_stm_time)
        A3.grid(row=3, column=1, columnspan=4, sticky=Tkinter.W)

        A4 = Tkinter.Button(master, text='Set HEF Time', command=set_hef_time)
        A4.grid(row=4, column=1, columnspan=1, sticky=Tkinter.W)

        A5 = Tkinter.Button(master, text='Time Diffs', command=show_time_diffs)
        A5.grid(row=5, column=1, columnspan=1, sticky=Tkinter.W)

        R1 = Tkinter.Button(master, text='Plot Test', command=plot_test)
        R1.grid(row=1, column=16, columnspan=2, sticky=Tkinter.W)

        R2 = Tkinter.Button(master, text='Plot Travel Times', command=plot_tt)
        R2.grid(row=2, column=16, columnspan=2, sticky=Tkinter.W)

        T2 = Tkinter.Button(master, text='Clear IES', command=clear_ies)
        T2.grid(row=2, column=20, columnspan=2, sticky=Tkinter.W)

        R3 = Tkinter.Button(master, text='Plot Pres & Temp', command=plot_pres_temp)
        R3.grid(row=3, column=16, columnspan=2, sticky=Tkinter.W)

        R4 = Tkinter.Button(master, text='Plot Bliley', command=plot_bliley)
        R4.grid(row=4, column=16, columnspan=2, sticky=Tkinter.W)

        R5 = Tkinter.Button(master, text='Plot Motor Current', command=plot_mot)
        R5.grid(row=5, column=16, columnspan=2, sticky=Tkinter.W)

        T5 = Tkinter.Button(master, text='Clear Motor', command=clear_mot)
        T5.grid(row=5, column=20, columnspan=2, sticky=Tkinter.W)

        R6 = Tkinter.Button(master, text='Plot HEF', command=plot_hef)
        R6.grid(row=6, column=16, columnspan=2, sticky=Tkinter.W)

        T6 = Tkinter.Button(master, text='Clear HEF', command=clear_hef)
        T6.grid(row=6, column=20, columnspan=2, sticky=Tkinter.W)

        R7 = Tkinter.Button(master, text='Plot Cal', command=plot_cal)
        R7.grid(row=7, column=16, columnspan=2, sticky=Tkinter.W)

        R7 = Tkinter.Button(master, text='Clear Cal', command=clear_cal)
        R7.grid(row=7, column=20, columnspan=2, sticky=Tkinter.W)

        R8 = Tkinter.Button(master, text='Plot Compass', command=plot_compass)
        R8.grid(row=8, column=16, columnspan=2, sticky=Tkinter.W)

        T8 = Tkinter.Button(master, text='Clear Compass', command=clear_compass)
        T8.grid(row=8, column=20, columnspan=2, sticky=Tkinter.W)

        R10 = Tkinter.Button(master, text='Compass Test', command=compass_test)
        R10.grid(row=10, column=16, columnspan=2, sticky=Tkinter.W)

        R11 = Tkinter.Button(master, text='Mag Cal Off', command=mag_cal_off)
        R11.grid(row=11, column=16, columnspan=2, sticky=Tkinter.W)

        R12 = Tkinter.Button(master, text='Mag Cal Reset', command=mag_cal_reset)
        R12.grid(row=12, column=16, columnspan=2, sticky=Tkinter.W)

        R13 = Tkinter.Button(master, text='Mag Cal Auto', command=mag_cal_auto)
        R13.grid(row=13, column=16, columnspan=2, sticky=Tkinter.W)

        R14 = Tkinter.Button(master, text='Mag Cal Manual', command=mag_cal_manual)
        R14.grid(row=14, column=16, columnspan=2, sticky=Tkinter.W)

        R15 = Tkinter.Button(master, text='Mag Cal Hdg', command=mag_cal_hdg)
        R15.grid(row=15, column=16, columnspan=2, sticky=Tkinter.W)

        R16 = Tkinter.Button(master, text='Mag Cal Err', command=mag_cal_err)
        R16.grid(row=16, column=16, columnspan=2, sticky=Tkinter.W)

        R17 = Tkinter.Button(master, text='', command=do_nothing)
        R17.grid(row=17, column=16, columnspan=2, sticky=Tkinter.W)

        R9 = Tkinter.Button(master, text='', command=do_nothing)
        R9.grid(row=9, column=16, columnspan=2, sticky=Tkinter.W)

        R18 = Tkinter.Button(master, text='m1adj', command=m1adj)
        R18.grid(row=18, column=16, columnspan=1, sticky=Tkinter.W)

        S18 = Tkinter.Button(master, text='m2adj', command=m2adj)
        S18.grid(row=18, column=17, columnspan=1, sticky=Tkinter.W)

        R19 = Tkinter.Button(master, text='m1b', command=m1b)
        R19.grid(row=19, column=16, columnspan=1, sticky=Tkinter.W)

        S19 = Tkinter.Button(master, text='m2b', command=m2b)
        S19.grid(row=19, column=17, columnspan=1, sticky=Tkinter.W)

        R20 = Tkinter.Button(master, text='m1btu', command=m1btu)
        R20.grid(row=20, column=16, columnspan=1, sticky=Tkinter.W)

        S20 = Tkinter.Button(master, text='m2btu', command=m2btu)
        S20.grid(row=20, column=17, columnspan=1, sticky=Tkinter.W)

        R21 = Tkinter.Button(master, text='m1gfa', command=m1gfa)
        R21.grid(row=21, column=16, columnspan=1, sticky=Tkinter.W)

        S21 = Tkinter.Button(master, text='m2gfa', command=m2gfa)
        S21.grid(row=21, column=17, columnspan=1, sticky=Tkinter.W)

        R22 = Tkinter.Button(master, text='m1gfb', command=m1gfb)
        R22.grid(row=22, column=16, columnspan=1, sticky=Tkinter.W)

        S22 = Tkinter.Button(master, text='m2gfb', command=m2gfb)
        S22.grid(row=22, column=17, columnspan=1, sticky=Tkinter.W)

        R23 = Tkinter.Button(master, text='Get Last Motor Data', command=get_last_motor_data)
        R23.grid(row=23, column=16, columnspan=2, sticky=Tkinter.W)

        R24 = Tkinter.Button(master, text='Plot Last Motor Data', command=plot_last_motor_data)
        R24.grid(row=24, column=16, columnspan=2, sticky=Tkinter.W)

        T10 = Tkinter.Button(master, text='Extra Mode On', command=extra_mode_on)
        T10.grid(row=10, column=20, columnspan=1, sticky=Tkinter.W)

        T11 = Tkinter.Button(master, text='Extra Mode Off', command=extra_mode_off)
        T11.grid(row=11, column=20, columnspan=1, sticky=Tkinter.W)

        T12 = Tkinter.Button(master, text='Cal Pwr On', command=cal_pwr_on)
        T12.grid(row=12, column=20, columnspan=1, sticky=Tkinter.W)

        T13 = Tkinter.Button(master, text='Cal Pwr Off', command=cal_pwr_off)
        T13.grid(row=13, column=20, columnspan=1, sticky=Tkinter.W)

        T14 = Tkinter.Button(master, text='Cal Connect', command=cal_connect)
        T14.grid(row=14, column=20, columnspan=1, sticky=Tkinter.W)

        T15 = Tkinter.Button(master, text='Cal Disconnect', command=cal_disconnect)
        T15.grid(row=15, column=20, columnspan=1, sticky=Tkinter.W)

        T16 = Tkinter.Button(master, text='Cal Start', command=cal_start)
        T16.grid(row=16, column=20, columnspan=1, sticky=Tkinter.E)

        T17 = Tkinter.Button(master, text='Cal Stop', command=cal_stop)
        T17.grid(row=17, column=20, columnspan=1, sticky=Tkinter.W)

        # Add more GUI stuff here

    def processIncoming(self):
        # Handle all the messages currently in the queue (if any).

        global stm_ibuf, tod_ibuf, hef_ibuf, ies_ibuf, aux_ibuf, logfd

        # append incoming bytes to various ibuf according to the
        # first three characters of the queue
        while self.queue.qsize():
            try:
                msg = self.queue.get(0)

                # only 'stm' messages arrive in production
                # hef, ies, aux are used when simulating those instruments

                if msg[0:3] == 'stm':
                    stm_msg = msg[3:]
                    stm_ibuf = stm_ibuf + stm_msg

                if msg[0:3] == 'hef':
                    hef_msg = msg[3:]
                    hef_ibuf = hef_ibuf + hef_msg

                if msg[0:3] == 'ies':
                    ies_msg = msg[3:]
                    ies_ibuf = ies_ibuf + ies_msg

                if msg[0:3] == 'aux':
                    aux_msg = msg[3:]
                    aux_ibuf = aux_ibuf + aux_msg

            except Queue.Empty:
                pass

        # stm_ibuf contains all the data from the STM console port
        # process one or more lines terminated with a '\r\n'
        while len(stm_ibuf) > 0 and stm_ibuf.count('\r\n'):
            i = stm_ibuf.find('\r\n')
            stm_line = stm_ibuf[0:i]
            stm_ibuf = stm_ibuf[i + 2:]
            iso = iso8601now()

            if options.do_hef_direct:
                stm_line = '#3_' + stm_line
                if stm_line[0:6] == '#3__HE' or stm_line[0:6] == '#3__HC':
                    stm_line = stm_line + str.format(' {0:.0f}', uxtnow())
                stm_line = stm_line + str.format('*{0:04x}', crc3kerm(stm_line))

            logfd.write(iso + ' ' + stm_line + '\r\n')
            logfd.flush()

            # print only non-standard lines if not debugging
            if py_debug:
                print(iso, 'dbg:', mkpr(stm_line))
            else:
                do_print = True
                if stm_line.find('#3__') >= 0:
                    do_print = False
                if stm_line.find('#2_TOD,') >= 0:
                    do_print = False
                if stm_line.find('#5_') >= 0:
                    if stm_line.find('#5_\\r*bc1e') >= 0:
                        do_print = False
                    if stm_line.find('AUX,') > 2:
                        do_print = False
                    if stm_line.find('T:') > 2:
                        do_print = False
                    if stm_line.find('P:') > 2:
                        do_print = False
                    if stm_line.find('F:') > 2:
                        do_print = False
                    if stm_line.find('E:') > 2:
                        do_print = False
                if do_print:
                    print(iso, stm_line)

            check_crc(stm_line)

            if stm_line.find('#2_TOD,') >= 0:
                global tod_split, stm_secs_diff
                split_tod(stm_line)

            if stm_line[0:3] == '#3_':
                global hef_line_count
                hef_line_count += 1
                split_hef(stm_line)
                if hef_split:
                    decode_fin_mot()
                    decode_hef_hdr()
                    check_hef_time(stm_line)
                    append_hef()
                    append_comp()

            if stm_line[0:3] == '#5_':
                global aux_line_count
                aux_line_count += 1
                split_aux(stm_line)
                append_aux()

        # special case for STM prompt
        if stm_ibuf == 'STM> ':
            iso = iso8601now()
            logfd.write(iso + ' ' + stm_ibuf + '\r\n')
            logfd.flush()
            print(iso, stm_ibuf)
            stm_ibuf = ''

        # special case for HEF prompt
        if options.do_hef_direct and stm_ibuf == 'HEF C> ':
            iso = iso8601now()
            logfd.write(iso + ' ' + stm_ibuf + '\r\n')
            logfd.flush()
            print(iso, stm_ibuf)
            stm_ibuf = ''

        if hef_ser:
            # Simulate responses to STM from HEF
            # 'hef_ibuf' is the command from the STM32 which normally
            # goes to the HEF console but comes to this python code
            # while simulating the HEF console.
            while len(hef_ibuf) > 0 and hef_ibuf.count('\r') > 0:
                i = hef_ibuf.find('\r')
                hef_line = hef_ibuf[0:i]
                hef_ibuf = hef_ibuf[i + 1:]
                if hef_line == 'hello':
                    hef_ser.write('simulated response to hello command\r\n')
                else:
                    hef_ser.write('unknown command: ' + hef_line + '\r\n')
                hef_ser.write('simulated HEF Prompt: ')
                hef_ser.flush()

        if ies_ser:
            # Simulate responses from the IES to the STM32.
            # 'ies_ibuf' is the command from the STM32 which normally
            # goes to the IES console but comes to this python code
            # while simulating the IES console.
            while len(ies_ibuf) > 0 and ies_ibuf.count('\r') > 0:
                i = ies_ibuf.find('\r')
                ies_line = ies_ibuf[0:i]
                ies_ibuf = ies_ibuf[i + 1:]
                if ies_line == 'hello':
                    ies_ser.write('simulated response to hello command\r\n')
                else:
                    ies_ser.write('unknown command: ' + ies_line + '\r\n')
                ies_ser.write('simulated IES Prompt: ')
                ies_ser.flush()


class ThreadedClient:
    '''
    Launch the main part of the GUI and the worker thread. periodicCall and
    endApplication could reside in the GUI part, but putting them here
    means that you have all the thread controls in a single place.
    '''

    def __init__(self, master):
        '''
        Start the GUI and the asynchronous threads. We are in the main
        (original) thread of the application, which will later be used by
        the GUI. We spawn a new thread for the worker.
        '''
        self.master = master

        # Create the queue
        self.queue = Queue.Queue()

        # Set up the GUI part, my_quit <==> self.endApplication
        self.gui = GuiPart(master, self.queue, self.endApplication)

        # Set up the thread to do asynchronous I/O
        # More can be made if necessary
        self.running = 1

        if is_linux:
            self.thread1 = threading.Thread(target=self.workerThread1_select)
            self.thread1.start()
        else:
            self.thread1 = threading.Thread(target=self.workerThread1_noselect)
            self.thread1.start()
            self.thread2 = threading.Thread(target=self.workerThread2_noselect)
            self.thread2.start()

        # Start the periodic call in the GUI to check if the queue contains
        # anything
        self.periodicCall()

    def periodicCall(self):
        # Runs every 100 ms if there is something new in the queue.

        # check if any bytes arrived
        self.gui.processIncoming()

        if not self.running:
            # This is the brutal stop of the system. You may want to do
            # some cleanup before actually shutting it down.
            print('\r\nPY: Quitting')
            cleanup()
            return

        # simulate time of day to STM from RSN network
        if tod_ser:
            global count_tod
            count_tod += 1
            if count_tod >= 10:
                count_tod = 0
                # $GPZDA,hhmmss.ss,dd,mm,yyyy,xx,yy*CC
                s = datetime.utcnow().strftime('GPZDA,%H%M%S.xx%fyy,%d,%m,%Y,00,00')
                i = s.find('xx')
                j = s.find('yy')
                s = s[0:i] + s[i + 2:i + 4] + s[j + 2:]
                s = '$' + s + '*' + str.format('{0:02X}', chksumnmea(s))
                # print(mkpr(s))
                tod_ser.write(s + '\r\n')

        # simulate data to STM from IES AUX2
        if aux_ser:
            global secsnextaux
            utcnow = datetime.utcnow()
            secsnow = timegm(utcnow.timetuple()) + utcnow.microsecond * 1e-6
            if secsnow >= secsnextaux:
                secsnextaux = secsnow - secsnow % auxrepsecs + auxrepsecs + auxrepsecs / 3
                global count_aux
                count_aux += 1
                hr = int(secsnow / 3600)

                s = str.format('T:{0:d} ', hr)
                for i in range(0, 24):
                    s = s + str.format('{0:d} ', 999900 + i)
                aux_ser.write('\r\r' + s + '\r\n')

                s = str.format('P:{0:d} ', hr)
                for i in range(0, 6):
                    s = s + str.format('{0:d} ', 11740 + i)
                    s = s + str.format('{0:d} ', 20440 + i)
                aux_ser.write('\r\r' + s + '\r\n')

                s = str.format('F:{0:d} ', hr)
                for i in range(0, 6):
                    s = s + str.format('{0:d} ', 33197500 + i)
                    s = s + str.format('{0:d} ', 171688080 + i)
                aux_ser.write('\r\r' + s + '\r\n')

                s = str.format('E:{0:d} ', hr)
                s = s + '2.85 0.01 0.00 14.00 6.91 4.96 21.01 0.0000 11808 19729 33197.523 171687.094 0.328 '
                aux_ser.write('\r\r' + s + '\r\n')

                # <CR><CR>AUX,<TIME>,<nT>,<T1>,<T2>,..,<T24>,<P>,<T>,<BTemp>,<Fb>,<CRC><CR><LF>
                s = str.format('AUX,{0:.0f},04',
                               secsnow - secsnow % auxrepsecs)  # time is beginning of 10-minute interval
                s = s + str.format(',{0:06.0f}', 1.11111 * 1e5)  # TT1
                s = s + str.format(',{0:06.0f}', 2.22222 * 1e5)  # TT2
                s = s + str.format(',{0:06.0f}', 3.33333 * 1e5)  # TT3
                s = s + str.format(',{0:06.0f}', 4.44444 * 1e5)  # TT4
                s = s + str.format(',{0:07.0f}', 555.555 * 1e3)  # P
                s = s + str.format(',{0:06.0f}', 26.666 * 1e3)  # T
                s = s + str.format(',{0:06.0f}', 27.777 * 1e3)  # BTemp
                s = s + str.format(',{0:012.3f}', 4000008.888)  # BFreq
                s = s + ','
                s = s + str.format('{0:04X}', crc3kerm(s))
                aux_ser.write('\r\r' + s + '\r\n')

        # simulate input to STM from HEF
        if hef_ser:
            global count_hef
            count_hef += 1
            if count_hef >= 50:  # 5 s
                count_hef = 0
                s = str.format('HEF,{0:.0f}', time.time())
                hef_ser.write(s + '\r\n')

        # restart to do next period
        self.master.after(100, self.periodicCall)

    def workerThread1_noselect(self):
        while self.running:
            time.sleep(0.1)  # prevents 100% CPU

            if jbox_tcp:
                try:
                    msg = jbox_tcp.recv(1024)
                except:
                    # print('jbox_tcp.recv prob')
                    msg = []
                if len(msg):
                    if termem_mode:
                        os.write(cono, msg)
                    #           sys.stdout.write(msg)
                    else:
                        self.queue.put('stm' + msg)

            if stm_ser:
                try:
                    msg = stm_ser.read(9999)
                except:
                    print('workerThread1_noselect(): cannot read stm_ser')
                    cleanup()

                if len(msg):
                    if termem_mode:
                        os.write(cono, msg)
                    #           sys.stdout.write(msg)
                    else:
                        self.queue.put('stm' + msg)

            if hef_ser:
                msg = hef_ser.read(9999)
                if len(msg):
                    self.queue.put('hef' + msg)

            if ies_ser:
                msg = ies_ser.read(9999)
                if len(msg):
                    self.queue.put('ies' + msg)

            if aux_ser:
                msg = aux_ser.read(9999)
                if len(msg):
                    self.queue.put('aux' + msg)

    def workerThread2_noselect(self):
        import msvcrt

        while self.running:
            time.sleep(0.1)  # prevents 100% CPU

            if termem_mode:
                if is_linux:
                    msg = os.read(coni, 1)  # this blocks
                    #       msg = sys.stdin.read(1) # this blocks
                else:
                    if msvcrt.kbhit():
                        msg = msvcrt.getch()  # this blocks (kbhit() could be used)
                    else:
                        msg = []
                if len(msg):
                    if jbox_tcp:
                        jbox_tcp.send(msg)
                    if stm_ser:
                        stm_ser.write(msg)


    def workerThread1_select(self):
        import select

        #   print('workerThread1_select starting, self.running=',self.running)

        inputs = []
        if jbox_tcp:
            inputs.append(jbox_tcp)
        if stm_ser:
            inputs.append(stm_ser)
        if hef_ser:
            inputs.append(hef_ser)
        if ies_ser:
            inputs.append(ies_ser)
        if aux_ser:
            inputs.append(aux_ser)
        if coni >= 0:
            inputs.append(coni)

        outputs = []

        # outgoing message queues used only when in termem_mode
        message_queues = {}
        message_queues[jbox_tcp] = Queue.Queue()
        message_queues[stm_ser] = Queue.Queue()
        message_queues[cono] = Queue.Queue()

        while self.running:

            readable, writable, exceptional = select.select(inputs, outputs, inputs)

            if not termem_mode:
                for R in readable:
                    if R is jbox_tcp:
                        msg = jbox_tcp.recv(1024)
                        if len(msg):
                            self.queue.put('stm' + msg)
                    if R is stm_ser:
                        msg = stm_ser.read(9999)
                        if len(msg):
                            self.queue.put('stm' + msg)
                    if R is hef_ser:
                        msg = hef_ser.read(9999)
                        if len(msg):
                            self.queue.put('hef' + msg)
                    if R is ies_ser:
                        msg = ies_ser.read(9999)
                        if len(msg):
                            self.queue.put('ies' + msg)
                    if R is aux_ser:
                        msg = aux_ser.read(9999)
                        if len(msg):
                            self.queue.put('aux' + msg)

            if termem_mode:
                for R in readable:
                    if R is coni:
                        msg = os.read(coni, 1)
                        #           msg = sys.stdin.read(1)
                        if jbox_tcp:
                            message_queues[jbox_tcp].put(msg)
                            if jbox_tcp not in outputs:
                                outputs.append(jbox_tcp)
                        if stm_ser:
                            message_queues[stm_ser].put(msg)
                            if stm_ser not in outputs:
                                outputs.append(stm_ser)
                    elif R is jbox_tcp:
                        msg = jbox_tcp.recv(1024)
                        if msg:
                            message_queues[cono].put(msg)
                            if cono not in outputs:
                                outputs.append(cono)
                        else:
                            print('jbox_tcp.recv indicates closed. exiting.')
                            cleanup()
                    elif R is stm_ser:
                        msg = stm_ser.read(9999)
                        if msg:
                            message_queues[cono].put(msg)
                            if cono not in outputs:
                                outputs.append(cono)
                    elif R is hef_ser:
                        msg = hef_ser.read(9999)
                        print('unexpected hef_ser=', mkpr(msg), '\r')
                    elif R is tod_ser:
                        msg = tod_ser.read(9999)
                        print('unexpected tod_ser=', mkpr(msg), '\r')
                    elif R is ies_ser:
                        msg = ies_ser.read(9999)
                        print('unexpected ies_ser=', mkpr(msg), '\r')
                    elif R is aux_ser:
                        msg = aux_ser.read(9999)
                        print('unexpected aux_ser=', mkpr(msg), '\r')
                    else:
                        print('unknown R\r')

            if termem_mode:
                for W in writable:
                    try:
                        msg = message_queues[W].get_nowait()
                    except Queue.Empty:
                        outputs.remove(W)
                    else:
                        if W is jbox_tcp:
                            jbox_tcp.send(msg)
                        elif W is stm_ser:
                            stm_ser.write(msg)
                        elif W is cono:
                            os.write(cono, msg)
                        #             sys.stdout.write(msg)
                        else:
                            print('unknown W')

            for E in exceptional:
                if E is jbox_tcp:
                    print('exceptional = jbox_tcp')
                elif E is stm_ser:
                    print('exceptional = stm_ser')
                elif E is cono:
                    print('exceptional = cono')
                elif E is coni:
                    print('exceptional = coni')
                else:
                    print('unknown E')

    def endApplication(self):
        self.running = 0


def stm_write(buf):
    if stm_ser:
        stm_ser.write(buf)
    if jbox_tcp:
        jbox_tcp.send(buf)


def stm_cmd(s):
    s = '#1_' + s
    s = s + str.format('*{0:04x}', crc3kerm(s))
    stm_write(s + '\r')
    logfd.write(iso8601now() + ' stm_cmd: ' + s + '\r\n')
    logfd.flush()


def hef_cmd(s):
    if not options.do_hef_direct:
        #   s = '#3_' + s + '\\r'
        s = '#3_' + s
        s = s + str.format('*{0:04x}', crc3kerm(s))
        print('hef_cmd: s=', s)
    if py_debug:
        print('hef_cmd(', s, ')')
    stm_write(s + '\r')
    logfd.write(iso8601now() + ' hef_cmd: ' + s + '\r\n')
    logfd.flush()


def ies_cmd(s):
    # s = '#4_' + s + '\\r'
    s = '#4_' + s
    s = s + str.format('*{0:04x}', crc3kerm(s))
    stm_write(s + '\r')
    logfd.write(iso8601now() + ' ies_cmd: ' + s + '\r\n')
    logfd.flush()


def lin_cmd(s):
    if sys.platform == 'linux2':
        print('lin_cmd(' + s + ')')
        args = shlex.split(s)
        print('args=', args)
        p = subprocess.Popen(args)
        logfd.write(iso8601now() + ' lin_cmd: ' + s + '\r\n')
        logfd.flush()


def hef_opto_on():
    stm_cmd('hef_opto_on')


def hef_opto_off():
    stm_cmd('hef_opto_off')


def ies_opto_on():
    stm_cmd('ies_opto_on')


def ies_opto_off():
    stm_cmd('ies_opto_off')


def ies_space_bar():
    ies_cmd(' ')


def stm_daq_start():
    stm_cmd('daq_start')


def stm_daq_stop():
    stm_cmd('daq_stop')


def new_baud(baud_str):
    global stm_baud, stm_ser

    if stm_ser == None:
        return

    if len(baud_str) == 0:
        stm_cmd('baud')
    try:
        baud = int(baud_str)
    except:
        print('cannot convert', baud_str, 'to integer')

    if baud == 4800 \
            or baud == 9600 \
            or baud == 19200 \
            or baud == 38400:
        stm_cmd(str.format('baud {0}', baud))
        stm_baud = baud
        time.sleep(0.5)
        stm_ser.baudrate = stm_baud
        time.sleep(0.5)
        for i in range(3):
            stm_ser.write('\r')
            time.sleep(0.1)
        print('new baud rate=', stm_baud)
    else:
        print('Baud rate', baud, 'not allowed.  Try 4800, 9600, 19200 or 38400')


def comm_stats():
    global crc_ok_count, crc_bad_count, hef_line_count, aux_line_count
    global hef_hdr_mot_count, hef_hdr_ef_count, hef_hdr_cal_count, hef_hdr_unknown_count
    global hef_compass_count
    print(iso8601now(), 'Comm Stats:')
    print('  crc_ok_count:   ', crc_ok_count)
    print('  crc_bad_count:  ', crc_bad_count)
    print('  aux_line_count: ', aux_line_count)
    print('  hef_line_count: ', hef_line_count)
    print('  hef_hdr_mot_count:     ', hef_hdr_mot_count)
    print('  hef_hdr_ef_count:      ', hef_hdr_ef_count)
    print('  hef_hdr_cal_count:     ', hef_hdr_cal_count)
    print('  hef_hdr_unknown_count: ', hef_hdr_unknown_count)
    print('  hef_compass_count: ', hef_compass_count)
    stm_cmd('tod_stats')


def set_stm_time():
    stm_cmd('force_RTC_update')


def stm_debug_increment():
    stm_cmd('debug++')


def stm_debug_off():
    stm_cmd('debug0')


def stm32_dir():
    stm_cmd('dir')


def hef_pwr_on():
    stm_cmd('hef_pwr_on')


def hef_pwr_off():
    stm_cmd('hef_pwr_off')


def ies_pwr_on():
    stm_cmd('ies_pwr_on')


def ies_pwr_off():
    stm_cmd('ies_pwr_off')


def reboot_stm32():
    stm_cmd('reboot')


def open_all():
    stm_cmd('open_all')


def close_all():
    stm_cmd('close_all')


def hef_wake():
    print('PY: waking HEF ...')
    if options.do_hef_direct:
        stm_ser.sendBreak(duration=0.500)
    else:
        stm_cmd('hef_break')
    time.sleep(1.0)
    hef_cmd('')


def hef_reset():
    print('PY: Resetting HEF')
    stm_cmd('hef_do_reset')


def hef_samp_stats_on():
    hef_cmd('samp stats on')


def hef_samp_stats_off():
    hef_cmd('samp stats off')


def get_cal_data():
    clear_cal()
    hef_cmd('send cal data')


def compass_test():
    hef_cmd('compass test')


def mag_cal_off():
    hef_cmd('mag cal off')


def mag_cal_reset():
    hef_cmd('mag cal reset')


def mag_cal_manual():
    hef_cmd('mag cal manual')


def mag_cal_auto():
    hef_cmd('mag cal auto')


def mag_cal_hdg():
    hef_cmd('mag cal hdg')


def do_nothing():
    pass


def mag_cal_err():
    hef_cmd('mag cal err')


def mot_cmd(cmd):
    global last_motor_cmd
    last_motor_cmd = cmd
    hef_cmd(cmd)


def m1adj():
    mot_cmd('m1adj')


def m2adj():
    mot_cmd('m2adj')


def m1b():
    mot_cmd('m1b')


def m2b():
    mot_cmd('m2b')


def m1btu():
    mot_cmd('m1btu')


def m2btu():
    mot_cmd('m2btu')


def m1gfa():
    mot_cmd('m1gfa')


def m1gfb():
    mot_cmd('m1gfb')


def m2gfa():
    mot_cmd('m2gfa')


def m2gfb():
    mot_cmd('m2gfb')


def get_last_motor_data():
    clear_mot()
    hef_cmd('send motor data')


def extra_mode_on():
    hef_cmd('extra mode on')


def extra_mode_off():
    hef_cmd('extra mode off')


def cal_pwr_on():
    hef_cmd('cal pwr on')


def cal_pwr_off():
    hef_cmd('cal pwr off')


def cal_connect():
    hef_cmd('cal conn')


def cal_disconnect():
    hef_cmd('cal disc')


def cal_start():
    hef_cmd('cal start')


def cal_stop():
    hef_cmd('cal stop')


def hef_mission_start():
    hef_cmd('mission start')


def hef_mission_stop():
    hef_cmd('mission stop')


def hef_stats():
    hef_cmd('stats')


def hef_params():
    hef_cmd('params')


def check_crc(line):
    i = line.find('#')
    j = line.rfind('*')
    if i < 0 or j < 0:
        return
    sect = line[i:j]
    # print('i=',i,'j=',j,'tst=['+tst+']')
    crc_get = crc3kerm(sect)
    try:
        crc_rcv = int(line[j + 1:], 16)
    except:
        crc_rcv = None
        print('bad crc decode:', mkpr(line))

    if crc_rcv:
        global crc_bad_count, crc_ok_count
        if crc_get != crc_rcv:
            print('crc error, line=', mkpr(line))
            crc_bad_count += 1
        else:
            crc_ok_count += 1


def split_aux(line):
    global aux_split
    global ies_secs_diff

    i = line.find('AUX,')
    j = line.rfind('*')
    if i < 0 or j < 0:
        aux_split = None
        return
    aux_split = line[i:j].split(',')
    if len(aux_split) != 13:
        print('AUX wrong split len:', len(aux_split))
        print('discarded aux_split:', aux_split)
        aux_split = None
        return
    try:
        ies_secs_diff = int(aux_split[1]) - int(aux_split[12])
    except:
        print(iso8601now(), 'bad AUX seconds:', mkpr(line), aux_split)


def split_tod(line):
    global tod_split
    global stm_secs_diff
    i = line.find('#')
    j = line.rfind('*')
    if i < 0 or j < 0:
        tod_split = None
        return
    tod_split = line[i:j].split(',')
    if len(tod_split) == 3:
        try:
            stm_secs_diff = int(tod_split[2]) - int(tod_split[1])
        except:
            print(iso8601now(), 'bad TOD seconds:', mkpr(line), tod_split)


def split_hef(line):
    global hef_split
    i = line.find('#')
    if i < 0:
        hef_split = None
        return
    j = line.rfind('\\r\\n*')
    if j < 0:
        j = line.rfind('\\r*')
        if j < 0:
            j = line.rfind('*')
    if j < 0:
        hef_split = None
        return
    hef_split = line[i:j].split()


def decode_fin_mot():
    global uxt_finmot
    if hef_split[0] == '#3_finmot':
        try:
            uxt_finmot = int(hef_split[4])
        except:
            uxt_finmot = None
        print('uxt_finmot=', uxt_finmot)


def decode_hef_hdr():
    global hef_hdr_mot_count, hef_hdr_ef_count
    global hef_hdr_cal_count, hef_hdr_unknown_count
    global hef_split
    global uxt_hefhdr, ticks_hefhdr, navg_mot, navg_ef, navg_cal

    if len(hef_split) > 0 and hef_split[0] == HEcmpstr:
        if len(hef_split) != 12:
            print('HE04 wrong split len:', len(hef_split))
            print('hef_split:', hef_split)
            return
        if hef_split[1] == 'f' or hef_split[1] == 'r':
            hef_hdr_mot_count += 1
        elif hef_split[1] == 'E':
            hef_hdr_ef_count += 1
        elif hef_split[1] == 'C':
            hef_hdr_cal_count += 1
        else:
            hef_hdr_unknown_count += 1

        global abu
        abu = hef_split[2]

        ibeg = int(hef_split[3])
        iend = int(hef_split[4])
        hcno = int(hef_split[5])

        #   uxt_hefhdr   = int(hef_split[6]) - (iend-ibeg)*0.1024
        uxt_hefhdr = int(hef_split[6])
        ticks_hefhdr = int(hef_split[7])

        navg_mot = float(hef_split[8])
        navg_ef = float(hef_split[9])
        navg_cal = float(hef_split[10])


def check_hef_time(line):
    global hef_split
    global hef_secs_diff

    if hef_split[0] == HEcmpstr:
        try:
            hef_secs_diff = int(hef_split[6]) - int(hef_split[11])
        except:
            print('bad HE04 hef_secs_diff, hef_line:', mkpr(line))
        if py_debug > 1:
            print('hefsecs=', hefsecs, 'now=', secsnow, 'dif=', hef_secs_diff)


def show_time_diffs():
    global stm_secs_diff
    global ies_secs_diff
    global hef_secs_diff
    print(iso8601now(), 'Time diff seconds:')
    print('  STM-TOD:', stm_secs_diff)
    print('  HEF-STM:', hef_secs_diff)
    print('  HEF-TOD:', hef_secs_diff + stm_secs_diff)
    print('  IES-STM:', ies_secs_diff)
    print('  IES-TOD:', ies_secs_diff + stm_secs_diff)


def set_hef_time():
    utcnow = datetime.utcnow()
    secsnow = timegm(utcnow.timetuple()) + utcnow.microsecond * 1e-6
    hef_cmd(datetime.utcnow().strftime('set_date_time %Y %m %d %H %M %S'))


def append_comp():
    global hef_split
    global comp_secs, comp_hdg, comp_pitch, comp_roll, comp_temp
    global hef_compass_count

    if len(hef_split) > 0 and hef_split[0] == HCcmpstr:
        if len(hef_split) != 8:
            print('HC03 wrong split len:', len(hef_split))
            print('hef_split:', hef_split)
            return
        hef_compass_count += 1

        try:
            secs = int(hef_split[1])
        except:
            secs = None

        try:
            hdg = int(hef_split[3])
        except:
            hdg = None

        try:
            pitch = int(hef_split[4])
        except:
            pitch = None

        try:
            roll = int(hef_split[5])
        except:
            roll = None

        try:
            temp = int(hef_split[6])
        except:
            temp = None

        comp_secs.append(secs)
        comp_hdg.append(hdg)
        comp_pitch.append(pitch)
        comp_roll.append(roll)
        comp_temp.append(temp)


def append_aux():
    global aux_split
    global aux_secs, aux_tt1, aux_tt2, aux_tt4, aux_tt4
    global aux_pres, aux_temp, aux_btemp, aux_bfreq

    if aux_split == None:
        return

    if len(aux_split) != 13:
        print('len(aux_split) wrong: ', len(aux_split))
        print('aux_split:', aux_split)

    try:
        secs = int(aux_split[1])
    except:
        secs = None

    try:
        ntt = int(aux_split[2])
    except:
        ntt = None

    if ntt != 4:
        print('ntt=' + ntt, 'is wrong')
        return

    try:
        tt1 = int(aux_split[3])
    except:
        tt1 = None
    try:
        tt2 = int(aux_split[4])
    except:
        tt2 = None
    try:
        tt3 = int(aux_split[5])
    except:
        tt3 = None
    try:
        tt4 = int(aux_split[6])
    except:
        tt4 = None
    try:
        pres = int(aux_split[7])
    except:
        pres = None
    try:
        temp = int(aux_split[8])
    except:
        temp = None
    try:
        btemp = int(aux_split[9])
    except:
        btemp = None
    try:
        bfreq = float(aux_split[10])
    except:
        bfreq = None

    aux_secs.append(secs)
    aux_tt1.append(tt1)
    aux_tt2.append(tt2)
    aux_tt3.append(tt3)
    aux_tt4.append(tt4)
    aux_pres.append(pres)
    aux_temp.append(temp)
    aux_btemp.append(btemp)
    aux_bfreq.append(bfreq)


def plot_test():
    fig.clf()
    x = [1, 2, 3, 4, 5]
    y = [1, 2, 3, 4, 5]
    x = np.array(x, dtype='double')
    y = np.array(y, dtype='double')
    y = y * 5
    ax = fig.add_subplot(1, 1, 1)
    ax.plot(x, y, 'ro-')
    ax.grid(True)
    plt.xlabel('x')
    plt.title('plot test')
    fig.show()


def plot_tt():
    global aux_secs, aux_tt1, aux_tt2, aux_tt3, aux_tt4

    if len(aux_secs) == 0:
        return

    secs = np.array(aux_secs, dtype='double')
    secs = secs - secs[-1]
    tt1 = np.array(aux_tt1, dtype='double') * 1e-5
    tt2 = np.array(aux_tt2, dtype='double') * 1e-5
    tt3 = np.array(aux_tt3, dtype='double') * 1e-5
    tt4 = np.array(aux_tt4, dtype='double') * 1e-5

    fig.clf()
    ax = fig.add_subplot(4, 1, 1)
    ax.plot(secs, tt1, 'bo-')
    ax.grid(True)
    plt.ylabel('TT1, s')
    plt.title('IES Travel Times')

    ax = fig.add_subplot(4, 1, 2)
    ax.plot(secs, tt2, 'bo-')
    ax.grid(True)
    plt.ylabel('TT2, s')

    ax = fig.add_subplot(4, 1, 3)
    ax.plot(secs, tt3, 'bo-')
    ax.grid(True)
    plt.ylabel('TT3, s')

    ax = fig.add_subplot(4, 1, 4)
    ax.plot(secs, tt4, 'bo-')
    ax.grid(True)
    plt.ylabel('TT4, s')
    plt.xlabel('Time, s')

    fig.show()


def plot_pres_temp():
    global aux_secs, aux_pres, aux_temp

    if len(aux_secs) == 0:
        return

    secs = np.array(aux_secs, dtype='double')
    secs = secs - secs[-1]
    pres = np.array(aux_pres, dtype='double') * 1e-5
    temp = np.array(aux_temp, dtype='double') * 1e-3

    fig.clf()
    ax = fig.add_subplot(2, 1, 1)
    ax.plot(secs, pres, 'ro-')
    ax.grid('on')
    plt.ylabel('P, dbar')
    plt.title('IES Pressure & Temperature')

    ax = fig.add_subplot(2, 1, 2)
    ax.plot(secs, temp, 'bo-')
    ax.grid('on')
    plt.xlabel('Time, s')
    plt.ylabel('T, C')
    fig.show()


def plot_bliley():
    global aux_secs, aux_btemp, aux_bfreq

    if len(aux_secs) == 0:
        return

    secs = np.array(aux_secs, dtype='double')
    secs = secs - secs[-1]
    btemp = np.array(aux_btemp, dtype='double') * 0.001
    bfreq = np.array(aux_bfreq, dtype='double')

    fig.clf()
    ax = fig.add_subplot(2, 1, 1)
    ax.plot(secs, btemp, 'ro-')
    ax.grid('on')
    plt.ylabel('T, C')
    plt.title('Bliley Oscillator')

    ax = fig.add_subplot(2, 1, 2)
    ax.plot(secs, bfreq - 4e6, 'bo-')
    ax.grid('on')
    plt.ylabel('Freq - 4e6, Hz')
    plt.xlabel('Time, s')
    fig.show()


def append_hef():
    global hef_split
    global abu
    global mot_ind_a, mot_cur_a
    global mot_ind_b, mot_cur_b
    global hef_uxt_a, hef_uxt_b
    global hef_ind_a, hef_e1a_a, hef_e1b_a, hef_e2a_a, hef_e2b_a
    global hef_ind_b, hef_e1a_b, hef_e1b_b, hef_e2a_b, hef_e2b_b
    global cal_uxt_a, cal_ind_a, cal_e1a_a, cal_e1b_a, cal_e1c_a, cal_e2a_a, cal_e2b_a, cal_e2c_a
    global cal_uxt_b, cal_ind_b, cal_e1a_b, cal_e1b_b, cal_e1c_b, cal_e2a_b, cal_e2b_b, cal_e2c_b
    global cal_uxt_u, cal_ind_u, cal_e1a_u, cal_e1b_u, cal_e1c_u, cal_e2a_u, cal_e2u_u, cal_e2c_u

    if hef_split[0] == HEcmpstr:
        mot_ind_a.append(None)
        mot_cur_a.append(None)

        hef_uxt_a.append(None)
        hef_ind_a.append(None)
        hef_e1a_a.append(None)
        hef_e1b_a.append(None)
        hef_e2a_a.append(None)
        hef_e2b_a.append(None)

        cal_uxt_a.append(None)
        cal_ind_a.append(None)
        cal_e1a_a.append(None)
        cal_e1b_a.append(None)
        cal_e1c_a.append(None)
        cal_e2a_a.append(None)
        cal_e2b_a.append(None)
        cal_e2c_a.append(None)

        mot_ind_b.append(None)
        mot_cur_b.append(None)

        hef_uxt_b.append(None)
        hef_ind_b.append(None)
        hef_e1a_b.append(None)
        hef_e1b_b.append(None)
        hef_e2a_b.append(None)
        hef_e2b_b.append(None)

        cal_uxt_b.append(None)
        cal_ind_b.append(None)
        cal_e1a_b.append(None)
        cal_e1b_b.append(None)
        cal_e1c_b.append(None)
        cal_e2a_b.append(None)
        cal_e2b_b.append(None)
        cal_e2c_b.append(None)

        cal_uxt_u.append(None)
        cal_ind_u.append(None)
        cal_e1a_u.append(None)
        cal_e1b_u.append(None)
        cal_e1c_u.append(None)
        cal_e2a_u.append(None)
        cal_e2b_u.append(None)
        cal_e2c_u.append(None)

    if hef_split[0] == DMcmpstr:
        try:
            ind = int(hef_split[1])
        except:
            ind = None
        try:
            cur = int(hef_split[2])
        except:
            cur = None

        if abu == 'a':
            mot_ind_a.append(ind)
            mot_cur_a.append(cur)
        if abu == 'b':
            mot_ind_b.append(ind)
            mot_cur_b.append(cur)

    if hef_split[0] == DEcmpstr:
        try:
            ind = int(hef_split[1])
        except:
            ind = None
        try:
            e1a = int(hef_split[2])
        except:
            e1a = None
        try:
            e1b = int(hef_split[3])
        except:
            e1b = None
        try:
            e2a = int(hef_split[4])
        except:
            e2a = None
        try:
            e2b = int(hef_split[5])
        except:
            e2b = None

        if abu == 'a':
            hef_uxt_a.append(uxt_hefhdr)
            hef_ind_a.append(ind)
            hef_e1a_a.append(e1a)
            hef_e1b_a.append(e1b)
            hef_e2a_a.append(e2a)
            hef_e2b_a.append(e2b)
        if abu == 'b':
            hef_uxt_b.append(uxt_hefhdr)
            hef_ind_b.append(ind)
            hef_e1a_b.append(e1a)
            hef_e1b_b.append(e1b)
            hef_e2a_b.append(e2a)
            hef_e2b_b.append(e2b)

    if hef_split[0] == DCcmpstr:
        try:
            ind = int(hef_split[1])
        except:
            ind = None
        try:
            e1c = int(hef_split[2])
        except:
            e1c = None
        try:
            e1a = int(hef_split[3])
        except:
            e1a = None
        try:
            e1b = int(hef_split[4])
        except:
            e1b = None

        try:
            e2c = int(hef_split[5])
        except:
            e2c = None
        try:
            e2a = int(hef_split[6])
        except:
            e2a = None
        try:
            e2b = int(hef_split[7])
        except:
            e2b = None

        if abu == 'a':
            cal_uxt_a.append(uxt_hefhdr)
            cal_ind_a.append(ind)
            cal_e1a_a.append(e1a)
            cal_e1b_a.append(e1b)
            cal_e1c_a.append(e1c)
            cal_e2a_a.append(e2a)
            cal_e2b_a.append(e2b)
            cal_e2c_a.append(e2c)
        if abu == 'b':
            cal_uxt_b.append(uxt_hefhdr)
            cal_ind_b.append(ind)
            cal_e1a_b.append(e1a)
            cal_e1b_b.append(e1b)
            cal_e1c_b.append(e1c)
            cal_e2a_b.append(e2a)
            cal_e2b_b.append(e2b)
            cal_e2c_b.append(e2c)

        cal_uxt_u.append(uxt_hefhdr)
        cal_ind_u.append(ind)
        cal_e1a_u.append(e1a)
        cal_e1b_u.append(e1b)
        cal_e1c_u.append(e1c)
        cal_e2a_u.append(e2a)
        cal_e2b_u.append(e2b)
        cal_e2c_u.append(e2c)


def plot_mot():
    global mot_ind_a, mot_cur_a
    global mot_ind_b, mot_cur_b
    global navg_mot

    if len(mot_ind_a) == 0 and len(mot_ind_b) == 0:
        return

    vref = 2.5  # ADC Vref
    sf = vref / pow(2, 16) / navg_mot * 1e3

    secs_a = np.array(mot_ind_a, dtype='double') / 40
    cur_a = np.array(mot_cur_a, dtype='double') * sf
    secs_b = np.array(mot_ind_b, dtype='double') / 40
    cur_b = np.array(mot_cur_b, dtype='double') * sf

    fig.clf()

    ax = fig.add_subplot(2, 1, 1)
    ax.plot(secs_a, cur_a, 'b.-')
    ax.grid('on')
    plt.ylabel('Mot Cur A pinched, mA')

    ax = fig.add_subplot(2, 1, 2)
    ax.plot(secs_b, cur_b, 'b.-')
    ax.grid('on')
    plt.ylabel('Mot Cur B pinched, mA')
    plt.xlabel('time, s')

    fig.show()


def plot_last_motor_data():
    if len(mot_ind_a) == 0 and len(mot_ind_b) == 0:
        return

    vref = 2.5  # ADC Vref
    sf = vref / pow(2, 16) / navg_mot * 1e3

    if abu == 'a':
        secs = np.array(mot_ind_a, dtype='double') / 40
        cur = np.array(mot_cur_a, dtype='double') * sf
    elif abu == 'b':
        secs = np.array(mot_ind_b, dtype='double') / 40
        cur = np.array(mot_cur_b, dtype='double') * sf
    else:
        print('warning: abu=' + abu + ' should be a or b')
        return

    fig.clf()

    ax = fig.add_subplot(1, 1, 1)
    ax.plot(secs, cur, 'b.-')
    ax.grid('on')
    plt.title('Motor Current, ' + last_motor_cmd)
    plt.ylabel('mA')
    plt.xlabel('time, s')

    fig.show()


def plot_hef():
    global hef_uxt_a, hef_uxt_b
    global hef_ind_a, hef_e1a_a, hef_e1b_a, hef_e2a_a, hef_e2b_a
    global hef_ind_b, hef_e1a_b, hef_e1b_b, hef_e2a_b, hef_e2b_b
    global navg_ef

    if len(hef_ind_a) == 0 and len(hef_ind_b) == 0:
        return

    vref = 2.5  # ADC Vref
    preamp = 800  # preamp gain
    divider = 0.1773  # resistor network at ADC input
    sf = vref / pow(2, 16) / preamp / divider * 1e6 / navg_ef
    off = pow(2, 15) * navg_ef

    secs_a = np.array(hef_ind_a, dtype='double') * 0.1024
    e1a_a = (np.array(hef_e1a_a, dtype='double') - off ) * sf
    e1b_a = (np.array(hef_e1b_a, dtype='double') - off ) * sf
    e2a_a = (np.array(hef_e2a_a, dtype='double') - off ) * sf
    e2b_a = (np.array(hef_e2b_a, dtype='double') - off ) * sf

    secs_b = np.array(hef_ind_b, dtype='double') * 0.1024
    e1a_b = (np.array(hef_e1a_b, dtype='double') - off ) * sf
    e1b_b = (np.array(hef_e1b_b, dtype='double') - off ) * sf
    e2a_b = (np.array(hef_e2a_b, dtype='double') - off ) * sf
    e2b_b = (np.array(hef_e2b_b, dtype='double') - off ) * sf

    fig.clf()

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

    fig.show()


def plot_cal_e1():
    plot_cal_e12(1)


def plot_cal_e2():
    plot_cal_e12(2)


def plot_cal_e12(e12):
    if len(cal_ind_u) == 0:
        print('no cal_ind_u')
        return

    vref = 2.5  # ADC Vref
    preamp = 800  # preamp gain
    divider = 0.1773  # resistor network at ADC input
    sf = vref / pow(2, 16) / preamp / divider * 1e6 / navg_cal
    off = pow(2, 15) * navg_cal

    secs = np.array(cal_ind_u, dtype='double') * 0.1024
    if e12 == 1:
        ea = (np.array(cal_e1a_u, dtype='double') - off) * sf
        eb = (np.array(cal_e1b_u, dtype='double') - off) * sf
        ec = (np.array(cal_e1c_u, dtype='double') - off) * sf
    elif e12 == 2:
        ea = (np.array(cal_e2a_u, dtype='double') - off) * sf
        eb = (np.array(cal_e2b_u, dtype='double') - off) * sf
        ec = (np.array(cal_e2c_u, dtype='double') - off) * sf
    else:
        print('e12 should be 1 or 2')
        return

    # compute data minus fit for plotting
    j = np.nonzero(np.isfinite(secs) & (secs > 10))
    secs = secs[j]
    ea = ea[j]
    eb = eb[j]
    ec = ec[j]
    t = secs - np.mean(secs)
    fitord = 1
    ea_coef = np.polyfit(t, ea, fitord);
    eb_coef = np.polyfit(t, eb, fitord);
    ec_coef = np.polyfit(t, ec, fitord);
    ea_res = ea - np.polyval(ea_coef, t);
    eb_res = eb - np.polyval(eb_coef, t);
    ec_res = ec - np.polyval(ec_coef, t);

    if abu == 'a':
        mrka = 'b.-'
        mrkb = 'r.-'
    elif abu == 'b':
        mrka = 'r.-'
        mrkb = 'b.-'
    else:
        mrka = 'b.-'
        mrkb = 'b.-'
    ybg = 500
    ysm = 10

    fig.clf()

    ax = fig.add_subplot(3, 2, 1)
    ax.plot(secs, ea, mrka)
    ax.grid('on')
    plt.ylabel('ea, uV')
    try:
        delay = float(uxt_hefhdr - uxt_finmot)
    except:
        delay = float('nan')
    plt.title('E{0:d}, pinched={1:s}, delay={2:.1f} s\n'.format(e12, abu.upper(), delay))

    ax = fig.add_subplot(3, 2, 3)
    ax.plot(secs, eb, mrkb)
    ax.grid('on')
    plt.ylabel('eb, uV')

    ax = fig.add_subplot(3, 2, 5)
    ax.plot(secs, ec, 'b.-')
    ax.grid('on')
    plt.ylabel('ec, uV')

    ax = fig.add_subplot(3, 2, 2)
    ax.plot(secs, ea_res, mrka)
    if abu == 'a':
        ax.set_ylim(-ybg, ybg)
    if abu == 'b':
        ax.set_ylim(-ysm, ysm)
    ax.grid('on')
    plt.ylabel('ea-fit, uV')
    plt.title('Data - Fit, order={0}'.format(fitord))

    ax = fig.add_subplot(3, 2, 4)
    ax.plot(secs, eb_res, mrkb)
    if abu == 'a':
        ax.set_ylim(-ysm, ysm)
    if abu == 'b':
        ax.set_ylim(-ybg, ybg)
    ax.grid('on')
    plt.ylabel('eb-fit, uV')

    ax = fig.add_subplot(3, 2, 6)
    ax.plot(secs, ec_res, 'b.-')
    ax.set_ylim(-ybg, ybg)
    ax.grid('on')
    plt.ylabel('ec-fit, uV')

    plt.subplots_adjust(hspace=0.3, wspace=0.3)

    fig.show()


def plot_cal():
    # global cal_ind_a, cal_e1a_a, cal_e1b_a, cal_e2a_a, cal_e2b_a
    # global cal_ind_b, cal_e1a_b, cal_e1b_b, cal_e2a_b, cal_e2b_b
    # global navg_cal

    if len(cal_ind_a) == 0 and len(cal_ind_b) == 0:
        return

    vref = 2.5  # ADC Vref
    preamp = 800  # preamp gain
    divider = 0.1773  # resistor network at ADC input
    sf = vref / pow(2, 16) / preamp / divider * 1e6 / navg_cal
    off = pow(2, 15) * navg_cal

    secs_a = np.array(cal_ind_a, dtype='double') * 0.1024
    e1a_a = (np.array(cal_e1a_a, dtype='double') - off) * sf
    e1b_a = (np.array(cal_e1b_a, dtype='double') - off) * sf
    e1c_a = (np.array(cal_e1c_a, dtype='double') - off) * sf
    e2a_a = (np.array(cal_e2a_a, dtype='double') - off) * sf
    e2b_a = (np.array(cal_e2b_a, dtype='double') - off) * sf
    e2c_a = (np.array(cal_e2c_a, dtype='double') - off) * sf

    secs_b = np.array(cal_ind_b, dtype='double') * 0.1024
    e1a_b = (np.array(cal_e1a_b, dtype='double') - off) * sf
    e1b_b = (np.array(cal_e1b_b, dtype='double') - off) * sf
    e1c_b = (np.array(cal_e1c_b, dtype='double') - off) * sf
    e2a_b = (np.array(cal_e2a_b, dtype='double') - off) * sf
    e2b_b = (np.array(cal_e2b_b, dtype='double') - off) * sf
    e2c_b = (np.array(cal_e2c_b, dtype='double') - off) * sf

    fig.clf()

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

    fig.show()


def plot_compass():
    # global comp_secs, comp_hdg, comp_pitch, comp_roll, comp_temp

    if len(comp_secs) < 1:
        return

    secs = np.array(comp_secs, dtype='double')
    secs = secs - secs[-1]

    hdg = np.array(comp_hdg, dtype='double') * 360.0 / 4096.0
    pitch = np.array(comp_pitch, dtype='double') * 90.0 / 4096.0
    roll = np.array(comp_roll, dtype='double') * 180.0 / 4096.0
    temp = np.array(comp_temp, dtype='double') * 0.1

    fig.clf()
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
    fig.show()


def clear_ies():
    aux_secs.clear()
    aux_tt1.clear()
    aux_tt2.clear()
    aux_tt3.clear()
    aux_tt4.clear()
    aux_pres.clear()
    aux_temp.clear()
    aux_btemp.clear()
    aux_bfreq.clear()


def clear_compass():
    comp_secs.clear()
    comp_hdg.clear()
    comp_pitch.clear()
    comp_roll.clear()
    comp_temp.clear()


def clear_mot():
    mot_ind_a.clear()
    mot_cur_a.clear()
    mot_ind_b.clear()
    mot_cur_b.clear()


def clear_hef():
    hef_uxt_a.clear()
    hef_ind_a.clear()
    hef_e1a_a.clear()
    hef_e1b_a.clear()
    hef_e2a_a.clear()
    hef_e2b_a.clear()

    hef_uxt_b.clear()
    hef_ind_b.clear()
    hef_e1a_b.clear()
    hef_e1b_b.clear()
    hef_e2a_b.clear()
    hef_e2b_b.clear()


def clear_cal():
    cal_uxt_a.clear()
    cal_ind_a.clear()
    cal_e1a_a.clear()
    cal_e1b_a.clear()
    cal_e1c_a.clear()
    cal_e2a_a.clear()
    cal_e2b_a.clear()
    cal_e2c_a.clear()

    cal_uxt_b.clear()
    cal_ind_b.clear()
    cal_e1a_b.clear()
    cal_e1b_b.clear()
    cal_e1c_b.clear()
    cal_e2a_b.clear()
    cal_e2b_b.clear()
    cal_e2c_b.clear()

    cal_uxt_u.clear()
    cal_ind_u.clear()
    cal_e1a_u.clear()
    cal_e1b_u.clear()
    cal_e1c_u.clear()
    cal_e2a_u.clear()
    cal_e2b_u.clear()
    cal_e2c_u.clear()


def termem_start():
    if is_linux:
        termem_start_linux()
    else:
        termem_start_windows()


def termem_start_linux():
    import tty
    import termios
    import fcntl
    from fcntl import F_GETFL, F_SETFL  # , O_NDELAY

    global attr_coni_save, attr_cono, termem_mode, coni, cono, flags_save

    attr_coni_save = termios.tcgetattr(coni)
    # print('attr_coni_save=',attr_coni_save)

    # attr_cono = termios.tcgetattr(cono)
    # print('attr_cono=',attr_cono)

    if False:
        attr = termios.tcgetattr(coni)
        attr[3] = attr[3] & ~termios.ICANON & ~termios.ECHO
        # attr[3] = attr[3] & ~termios.ICANON & ~termios.ECHO & ~termios.ISIG
        # attr[6][termios.VMIN] = 1
        # attr[6][termios.VTIME] = 0
        termios.tcsetattr(coni, termios.TCSAFLUSH, attr)
        # print('attr=',attr)

        flags_save = fcntl.fcntl(coni, F_GETFL)
        fcntl.fcntl(coni, F_SETFL, flags_save | os.O_NONBLOCK)
    else:
        tty.setraw(coni)
    #   tty.setraw(cono)

    termem_mode = True
    print('termem_mode=', termem_mode, '\r')


def termem_stop():
    if is_linux:
        termem_stop_linux()
    else:
        termem_stop_windows()


def termem_stop_linux():
    global attr_coni_save, attr_cono, termem_mode, coni, cono
    import termios
    import fcntl

    if termem_mode == False:
        return

    termios.tcsetattr(coni, termios.TCSAFLUSH, attr_coni_save)
    # termios.tcsetattr(cono, termios.TCSAFLUSH, attr_cono)

    if False:
        fcntl.fcntl(coni, fcntl.F_SETFL, flags_save)

    termem_mode = False
    print('termem_mode=', termem_mode)


def termem_start_windows():
    global termem_mode
    termem_mode = True
    print('termem_mode=', termem_mode)


def termem_stop_windows():
    global termem_mode
    termem_mode = False
    print('termem_mode=', termem_mode)


# main

if __name__ == '__main__':


    HEcmpstr = '#3__HE04'
    HCcmpstr = '#3__HC03'
    DMcmpstr = '#3__DM'
    DCcmpstr = '#3__DC'
    DEcmpstr = '#3__DE'

    parser = OptionParser(usage="%prog [Options]", version="%prog 1.0")

    parser.add_option("-v", "--verbose",
                      action="store_true", dest="verbose", default=False,
                      help="print status messages to stdout")

    parser.add_option("-d", "--do_hef_direct",
                      action="store_true", dest="do_hef_direct", default=False,
                      help="direct connection to HEF instead of STM")

    # for DigiConnect in office use: '-j 10.180.80.174'
    # for Linux: sudo /sbin/ifconfig eth0:1 10.180.80.xxx where xxx is not used
    parser.add_option("-j", "--jbox_hostname", dest="jbox_hostname", default=None,
                      help="RSN junction box hostname or IP number", metavar="JBOX_HOSTNAME")

    (options, args) = parser.parse_args()

    if options.do_hef_direct:
        stm_baud = 9600  # this is really the HEF
    else:
        stm_baud = 38400

    last_motor_cmd = ''

    global count_tod, count_aux, count_hef
    global stm_ibuf, tod_ibuf, hef_ibuf, ies_ibuf, aux_ibuf, logfd
    global hef_secs_diff, ies_secs_diff, stm_secs_diff
    global aux_secs, aux_tt1, aux_tt4, aux_tt4, aux_tt4, aux_pres, aux_temp

    global abu
    global mot_ind_a, mot_cur_a
    global mot_ind_b, mot_cur_b
    global hef_ind_a, hef_uxt_a
    global hef_e1a_a, hef_e1b_a, hef_e2a_a, hef_e2b_a
    global hef_ind_b, hef_uxt_b
    global hef_e1a_b, hef_e1b_b, hef_e2a_b, hef_e2b_b
    global cal_ind_a, cal_uxt_a
    global cal_e1a_a, cal_e1b_a, cal_e1c_a
    global cal_e2a_a, cal_e2b_a, cal_e2c_a
    global cal_ind_b, cal_uxt_b
    global cal_e1a_b, cal_e1b_b, cal_e1c_b
    global cal_e2a_b, cal_e2b_b, cal_e2c_b
    global cal_ind_u
    global cal_e1a_u, cal_e1b_u, cal_e1c_u
    global cal_e2a_u, cal_e2b_u, cal_e2c_u

    print('sys.platform:', sys.platform)
    print('os.name:', os.name)

    abu = 'x'
    termem_mode = False
    uxt_finmot = None

    hef_secs_diff = float('nan')
    ies_secs_diff = float('nan')
    stm_secs_diff = float('nan')

    count_tod = 0
    count_aux = 0
    count_hef = 0

    stm_ibuf = ''
    tod_ibuf = ''
    hef_ibuf = ''
    ies_ibuf = ''
    aux_ibuf = ''

    logfile = './hprtst.out'
    logfd = open(logfile, 'at')

    logfd.write(iso8601now() + ' hprtst.py started' + '\r\n')
    logfd.flush()

    stm_tty = None
    tod_tty = None
    hef_tty = None
    ies_tty = None
    aux_tty = None

    jbox_tcp = None
    stm_ser = None
    tod_ser = None
    hef_ser = None
    ies_ser = None
    aux_ser = None

    if sys.platform == 'win32':
        is_linux = False
        this_host = socket.gethostname()
        print('Win32: this_host=', this_host)
        stm_tty = 'COM1:'

    elif sys.platform.find('linux') >= 0:
        is_linux = True
        this_host = socket.gethostname().split('.')[0]
        print('Linux: this_host:', this_host)

        if this_host.find('ohm') >= 0:
            stm_tty = '/dev/ttyRP1'  # stm32 console
            tod_tty = '/dev/ttyRP2'  # time of day
            #   hef_tty = '/dev/ttyRP3' # hef console
            ies_tty = '/dev/ttyRP4'  # ies console
            aux_tty = '/dev/ttyRP5'  # ies aux2
        elif this_host.find('oersted') >= 0:
            stm_tty = '/dev/ttyRP1'  # stm32 console
            #   tod_tty = '/dev/ttyRP2' # time of day
            #   hef_tty = '/dev/ttyRP3' # hef console
            #   ies_tty = '/dev/ttyRP4' # ies console
            #   aux_tty = '/dev/ttyRP5' # ies aux2
        elif this_host.find('henry') >= 0:
            stm_tty = '/dev/ttyR1'  # stm32 console
            tod_tty = '/dev/ttyR2'  # time of day
        elif this_host.find('tesla') >= 0:
            stm_tty = '/dev/ttyR3'  # stm32 console
            tod_tty = '/dev/ttyR2'  # time of day
        elif this_host.find('lt5') >= 0:
            stm_tty = '/dev/ttyS0'  # stm32 console
        else:
            print('unknown this_host:', this_host)
            cleanup()

    else:
        print('unknown sys.platform=', sys.platform)
        cleanup()

    coni = sys.stdin.fileno()
    cono = sys.stdout.fileno()

    if options.jbox_hostname:
        stm_tty = None
        i = options.jbox_hostname.find(':')
        if i < 0:
            jbox_hostname = options.jbox_hostname
            jbox_portnum = 2101
        else:
            jbox_hostname = options.jbox_hostname[0:i]
            jbox_portnum = int(options.jbox_hostname[i + 1:])
        # lock_tty(options.jbox_hostname)
        try:
            jbox_tcp = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            jbox_tcp.connect((jbox_hostname, jbox_portnum))
            jbox_tcp.setblocking(0)
        except:
            jbox_tcp = None
            print('cannot setup jbox hostname=', jbox_hostname, 'portnum=', jbox_portnum)
            cleanup()
    else:
        jbox_tcp = None

    if stm_tty:
        lock_tty(stm_tty)
        try:
            stm_ser = serial.Serial(stm_tty, stm_baud, timeout=0)
        except:
            print('cannot open stm_ser')
            cleanup()
    else:
        stm_ser = None

    if tod_tty:
        lock_tty(tod_tty)
        tod_ser = serial.Serial(tod_tty, 9600, timeout=0)
    else:
        tod_ser = None

    if hef_tty:
        lock_tty(hef_tty)
        hef_ser = serial.Serial(hef_tty, 9600, timeout=0)
    else:
        hef_ser = None

    if ies_tty:
        lock_tty(ies_tty)
        ies_ser = serial.Serial(ies_tty, 9600, timeout=0)
    else:
        ies_ser = None

    if aux_tty:
        lock_tty(aux_tty)
        aux_ser = serial.Serial(aux_tty, 9600, timeout=0)
    else:
        aux_ser = None

    """
    print('coni=',coni)
    print('cono=',cono)
    print('stm_ser=',stm_ser)
    print('aux_ser=',aux_ser)
    print('jbox_tcp=',jbox_tcp)
    """

    date_begin = datetime.utcnow()

    # allocate fifo buffers
    nqueue = 100

    aux_secs = deque(maxlen=nqueue)
    aux_tt1 = deque(maxlen=nqueue)
    aux_tt2 = deque(maxlen=nqueue)
    aux_tt3 = deque(maxlen=nqueue)
    aux_tt4 = deque(maxlen=nqueue)
    aux_pres = deque(maxlen=nqueue)
    aux_temp = deque(maxlen=nqueue)
    aux_btemp = deque(maxlen=nqueue)
    aux_bfreq = deque(maxlen=nqueue)

    comp_secs = deque(maxlen=nqueue)
    comp_hdg = deque(maxlen=nqueue)
    comp_pitch = deque(maxlen=nqueue)
    comp_roll = deque(maxlen=nqueue)
    comp_temp = deque(maxlen=nqueue)

    nqueue = 1000
    mot_ind_a = deque(maxlen=nqueue)
    mot_cur_a = deque(maxlen=nqueue)

    mot_ind_b = deque(maxlen=nqueue)
    mot_cur_b = deque(maxlen=nqueue)

    hef_uxt_a = deque(maxlen=nqueue)
    hef_ind_a = deque(maxlen=nqueue)
    hef_e1a_a = deque(maxlen=nqueue)
    hef_e1b_a = deque(maxlen=nqueue)
    hef_e2a_a = deque(maxlen=nqueue)
    hef_e2b_a = deque(maxlen=nqueue)

    hef_uxt_b = deque(maxlen=nqueue)
    hef_ind_b = deque(maxlen=nqueue)
    hef_e1a_b = deque(maxlen=nqueue)
    hef_e1b_b = deque(maxlen=nqueue)
    hef_e2a_b = deque(maxlen=nqueue)
    hef_e2b_b = deque(maxlen=nqueue)

    cal_uxt_a = deque(maxlen=nqueue)
    cal_ind_a = deque(maxlen=nqueue)
    cal_e1a_a = deque(maxlen=nqueue)
    cal_e1b_a = deque(maxlen=nqueue)
    cal_e1c_a = deque(maxlen=nqueue)
    cal_e2a_a = deque(maxlen=nqueue)
    cal_e2b_a = deque(maxlen=nqueue)
    cal_e2c_a = deque(maxlen=nqueue)

    cal_uxt_b = deque(maxlen=nqueue)
    cal_ind_b = deque(maxlen=nqueue)
    cal_e1a_b = deque(maxlen=nqueue)
    cal_e1b_b = deque(maxlen=nqueue)
    cal_e1c_b = deque(maxlen=nqueue)
    cal_e2a_b = deque(maxlen=nqueue)
    cal_e2b_b = deque(maxlen=nqueue)
    cal_e2c_b = deque(maxlen=nqueue)

    cal_uxt_u = deque(maxlen=nqueue)
    cal_ind_u = deque(maxlen=nqueue)
    cal_e1a_u = deque(maxlen=nqueue)
    cal_e1b_u = deque(maxlen=nqueue)
    cal_e1c_u = deque(maxlen=nqueue)
    cal_e2a_u = deque(maxlen=nqueue)
    cal_e2b_u = deque(maxlen=nqueue)
    cal_e2c_u = deque(maxlen=nqueue)

    tref = 0

    fig = plt.figure(num=1, figsize=(10, 7))

    root = Tkinter.Tk()
    root.wm_title('HPIES RSN TEST')
    # root.geometry('500x150')

    auxrepsecs = 100
    utcnow = datetime.utcnow()
    secsnow = timegm(utcnow.timetuple()) + utcnow.microsecond * 1e-6
    secsnextaux = secsnow - secsnow % auxrepsecs + + auxrepsecs + auxrepsecs / 3

    client = ThreadedClient(root)
    root.mainloop()
