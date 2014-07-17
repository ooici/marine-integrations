__author__ = 'Pete Cable'

NEWLINE = '\n'

INVALID_SAMPLE = "This is an invalid sample; it had better cause an exception." + NEWLINE
LILY_VALID_SAMPLE_01 = "LILY,2013/06/24 23:36:02,-235.500,  25.930,194.30, 26.04,11.96,N9655" + NEWLINE
LILY_VALID_SAMPLE_02 = "LILY,2013/06/24 23:36:04,-235.349,  26.082,194.26, 26.04,11.96,N9655" + NEWLINE
HEAT_VALID_SAMPLE_01 = "HEAT,2013/04/19 22:54:11,-001,0001,0025" + NEWLINE
HEAT_VALID_SAMPLE_02 = "HEAT,2013/04/19 22:54:11,001,0001,0025" + NEWLINE
IRIS_VALID_SAMPLE_01 = "IRIS,2013/05/29 00:25:34, -0.0882, -0.7524,28.45,N8642" + NEWLINE
IRIS_VALID_SAMPLE_02 = "IRIS,2013/05/29 00:25:36, -0.0885, -0.7517,28.49,N8642" + NEWLINE
NANO_VALID_SAMPLE_01 = "NANO,V,2013/08/22 22:48:36.013,13.888533,26.147947328" + NEWLINE
NANO_VALID_SAMPLE_02 = "NANO,P,2013/08/22 23:13:36.000,13.884067,26.172926006" + NEWLINE
LEVELING_STATUS = "LILY,2013/07/24 20:36:27,*  14.667,  81.642,185.21, 33.67,11.59,N9651"
LEVELED_STATUS = "LILY,2013/06/28 17:29:21,*  -2.277,  -2.165,190.81, 25.69,,Leveled!11.87,N9651"
SWITCHING_STATUS = "LILY,2013/06/28 18:04:41,*  -7.390, -14.063,190.91, 25.83,,Switching to Y!11.87,N9651"
X_OUT_OF_RANGE = "LILY,2013/03/22 19:07:28,*-330.000,-330.000,185.45," + \
                 "-6.45,,X Axis out of range, switching to Y!11.37,N9651"
Y_OUT_OF_RANGE = "LILY,2013/03/22 19:07:29,*-330.000,-330.000,184.63, -6.43,,Y Axis out of range!11.34,N9651"

BOTPT_FIREHOSE_01 = \
"""NANO,P,2013/05/16 17:03:22.000,14.858126,25.243003840
HEAT,2013/04/19 22:54:11,-001,0001,0025
IRIS,2013/05/29 00:25:34, -0.0882, -0.7524,28.45,N8642
NANO,P,2013/05/16 17:03:22.000,14.858126,25.243003840
LILY,2013/06/24 23:36:02,-235.500,  25.930,194.30, 26.04,11.96,N9655
HEAT,2013/04/19 22:54:11,-001,0001,0025"""

BOTPT_FIREHOSE_02 = \
"""NANO,P,2013/05/16 17:03:22.000,14.858126,25.243003840",
HEAT,2013/04/19 22:54:11,-001,0001,0025
LILY,2013/06/24 22:36:02,-235.500,  25.930,194.30, 26.04,11.96,N9655
IRIS,2013/05/29 00:25:34, -0.0882, -0.7524,28.45,N8642
NANO,P,2013/05/16 17:03:22.000,14.858126,25.243003840
LILY,2013/06/24 23:36:02,-235.500,  25.930,194.30, 26.04,11.96,N9655
HEAT,2013/04/19 22:54:11,-001,0001,0025"""

LILY_STATUS1 = \
"""LILY,2014/06/09 18:13:50,*APPLIED GEOMECHANICS LILY Firmware V2.1 SN-N9651 ID01
LILY,2014/06/09 18:13:50,*01: Vbias= 0.0000 0.0000 0.0000 0.0000
LILY,2014/06/09 18:13:50,*01: Vgain= 0.0000 0.0000 0.0000 0.0000
LILY,2014/06/09 18:13:50,*01: Vmin:  -2.50  -2.50   2.50   2.50
LILY,2014/06/09 18:13:50,*01: Vmax:   2.50   2.50   2.50   2.50
LILY,2014/06/09 18:13:50,*01: a0=    0.00000    0.00000    0.00000    0.00000    0.00000    0.00000
LILY,2014/06/09 18:13:50,*01: a1=    0.00000    0.00000    0.00000    0.00000    0.00000    0.00000
LILY,2014/06/09 18:13:50,*01: a2=    0.00000    0.00000    0.00000    0.00000    0.00000    0.00000
LILY,2014/06/09 18:13:50,*01: a3=    0.00000    0.00000    0.00000    0.00000    0.00000    0.00000
LILY,2014/06/09 18:13:50,*01: Tcoef 0: Ks=           0 Kz=           0 Tcal=           0
LILY,2014/06/09 18:13:51,*01: Tcoef 1: Ks=           0 Kz=           0 Tcal=           0
LILY,2014/06/09 18:13:51,*01: N_SAMP=  28 Xzero=  0.00 Yzero=  0.00
LILY,2014/06/09 18:13:51,*01: TR-PASH-OFF E99-ON  SO-NMEA-SIM XY-EP 19200 baud FV-
LILY,2014/06/09 18:13:51,*9900XY-DUMP-SETTINGS"""

LILY_STATUS2 = \
"""LILY,2014/06/09 18:04:32,*01: TBias: 3.00
LILY,2014/06/09 18:04:32,*01: Above 0.00(KZMinTemp): kz[0]=           0, kz[1]=           0
LILY,2014/06/09 18:04:32,*01: Below 0.00(KZMinTemp): kz[2]=           0, kz[3]=           0
LILY,2014/06/09 18:04:32,*01: ADCDelay:  310
LILY,2014/06/09 18:04:32,*01: PCA Model: 84833-14
LILY,2014/06/09 18:04:32,*01: Firmware Version: 2.1 Rev D
LILY,2014/06/09 18:04:32,*01: X Ch Gain= 1.0000, Y Ch Gain= 1.0000, Temperature Gain= 1.0000
LILY,2014/06/09 18:04:32,*01: Calibrated in uRadian, Current Output Mode: uRadian
LILY,2014/06/09 18:04:32,*01: Using RS232
LILY,2014/06/09 18:04:32,*01: Real Time Clock: Installed
LILY,2014/06/09 18:04:32,*01: Use RTC for Timing: Yes
LILY,2014/06/09 18:04:32,*01: External Flash: 2162688 Bytes Installed
LILY,2014/06/09 18:04:32,*01: Flash Status (in Samples) (Used/Total): (107/55424)
LILY,2014/06/09 18:04:32,*01: Low Power Logger Data Rate: -1 Seconds per Sample
LILY,2014/06/09 18:04:32,*01: Calibration method: Dynamic
LILY,2014/06/09 18:04:32,*01: Positive Limit=330.00   Negative Limit=-330.00
LILY,2014/06/09 18:04:32,*01: Calibration Points:023  X: Enabled  Y: Enabled
LILY,2014/06/09 18:04:32,*01: Uniaxial (x2) Sensor Type (1)
LILY,2014/06/09 18:04:32,*01: ADC: 16-bit(external)
LILY,2014/06/09 18:04:32,*01: Compass: Installed   Magnetic Declination: 0.000000
LILY,2014/06/09 18:04:32,*01: Compass: Xoffset:  124, Yoffset:  196, Xrange: 1349, Yrange: 1364
LILY,2014/06/09 18:04:32,*01: PID Coeff: iMax:100.0, iMin:-100.0, iGain:0.0150, pGain: 2.50, dGain: 10.0
LILY,2014/06/09 18:04:32,*01: Motor I_limit: 90.0mA
LILY,2014/06/09 18:04:33,*01: Current Time: 12/12/00 00:32:30
LILY,2014/06/09 18:04:33,*01: Supply Voltage: 11.87 Volts
LILY,2014/06/09 18:04:33,*01: Memory Save Mode: Off
LILY,2014/06/09 18:04:33,*01: Outputting Data: No
LILY,2014/06/09 18:04:33,*01: Auto Power-Off Recovery Mode: On
LILY,2014/06/09 18:04:33,*01: Advanced Memory Mode: Off, Delete with XY-MEMD: No
LILY,2014/06/09 18:04:33,*9900XY-DUMP2"""

IRIS_STATUS1 = \
"""IRIS,2013/06/19 21:13:00,*APPLIED GEOMECHANICS Model MD900-T Firmware V5.2 SN-N3616 ID01
IRIS,2013/06/12 18:03:44,*01: Vbias= 0.0000 0.0000 0.0000 0.0000
IRIS,2013/06/12 18:03:44,*01: Vgain= 0.0000 0.0000 0.0000 0.0000
IRIS,2013/06/12 18:03:44,*01: Vmin:  -2.50  -2.50   2.50   2.50
IRIS,2013/06/12 18:03:44,*01: Vmax:   2.50   2.50   2.50   2.50
IRIS,2013/06/12 18:03:44,*01: a0=    0.00000    0.00000    0.00000    0.00000    0.00000    0.00000
IRIS,2013/06/12 18:03:44,*01: a1=    0.00000    0.00000    0.00000    0.00000    0.00000    0.00000
IRIS,2013/06/12 18:03:44,*01: a2=    0.00000    0.00000    0.00000    0.00000    0.00000    0.00000
IRIS,2013/06/12 18:03:44,*01: a3=    0.00000    0.00000    0.00000    0.00000    0.00000    0.00000
IRIS,2013/06/12 18:03:44,*01: Tcoef 0: Ks=           0 Kz=           0 Tcal=           0
HEAT,2013/06/12 18:04:02,-001,0001,0024
IRIS,2013/06/12 18:03:44,*01: Tcoef 1: Ks=           0 Kz=           0 Tcal=           0
IRIS,2013/06/12 18:03:44,*01: N_SAMP= 460 Xzero=  0.00 Yzero=  0.00
IRIS,2013/06/12 18:03:44,*01: TR-PASH-OFF E99-ON  SO-NMEA-SIM XY-EP  9600 baud FV-
IRIS,2013/06/12 18:03:44,*9900XY-DUMP-SETTINGS"""

IRIS_STATUS2 = \
"""IRIS,2013/06/12 23:55:09,*01: TBias: 8.85
IRIS,2013/06/12 23:55:09,*Above 0.00(KZMinTemp): kz[0]=           0, kz[1]=           0
IRIS,2013/06/12 23:55:09,*Below 0.00(KZMinTemp): kz[2]=           0, kz[3]=           0
IRIS,2013/06/12 18:04:01,*01: ADCDelay:  310
IRIS,2013/06/12 18:04:01,*01: PCA Model: 90009-01
IRIS,2013/06/12 18:04:01,*01: Firmware Version: 5.2 Rev N
LILY,2013/06/12 18:04:01,-330.000,-247.647,290.73, 24.50,11.88,N9656
IRIS,2013/06/12 18:04:01,*01: X Ch Gain= 1.0000, Y Ch Gain= 1.0000, Temperature Gain= 1.0000
IRIS,2013/06/12 18:04:01,*01: Output Mode: Degrees
IRIS,2013/06/12 18:04:01,*01: Calibration performed in Degrees
IRIS,2013/06/12 18:04:01,*01: Control: Off
IRIS,2013/06/12 18:04:01,*01: Using RS232
IRIS,2013/06/12 18:04:01,*01: Real Time Clock: Not Installed
IRIS,2013/06/12 18:04:01,*01: Use RTC for Timing: No
IRIS,2013/06/12 18:04:01,*01: External Flash Capacity: 0 Bytes(Not Installed)
IRIS,2013/06/12 18:04:01,*01: Relay Thresholds:
IRIS,2013/06/12 18:04:01,*01:   Xpositive= 1.0000   Xnegative=-1.0000
IRIS,2013/06/12 18:04:01,*01:   Ypositive= 1.0000   Ynegative=-1.0000
IRIS,2013/06/12 18:04:01,*01: Relay Hysteresis:
IRIS,2013/06/12 18:04:01,*01:   Hysteresis= 0.0000
IRIS,2013/06/12 18:04:01,*01: Calibration method: Dynamic
IRIS,2013/06/12 18:04:01,*01: Positive Limit=26.25   Negative Limit=-26.25
IRIS,2013/06/12 18:04:02,*01: Calibration Points:025  X: Disabled  Y: Disabled
IRIS,2013/06/12 18:04:02,*01: Biaxial Sensor Type (0)
IRIS,2013/06/12 18:04:02,*01: ADC: 12-bit (internal)
IRIS,2013/06/12 18:04:02,*01: DAC Output Scale Factor: 0.10 Volts/Degree
HEAT,2013/06/12 18:04:02,-001,0001,0024
IRIS,2013/06/12 18:04:02,*01: Total Sample Storage Capacity: 372
IRIS,2013/06/12 18:04:02,*01: BAE Scale Factor:  2.88388 (arcseconds/bit)
IRIS,2013/06/12 18:04:02,*9900XY-DUMP2"""

NANO_STATUS = \
"""NANO,*______________________________________________________________
NANO,*PAROSCIENTIFIC SMT SYSTEM INFORMATION
NANO,*Model Number: 42.4K-265
NANO,*Serial Number: 120785
NANO,*Firmware Revision: R5.20
NANO,*Firmware Release Date: 03-25-13
NANO,*PPS status: V : PPS signal NOT detected.
NANO,*--------------------------------------------------------------
NANO,*AA:7.161800     AC:7.290000     AH:160.0000     AM:0
NANO,*AP:0            AR:160.0000     BL:0            BR1:115200
NANO,*BR2:115200      BV:10.9         BX:112          C1:-9747.897
HEAT,2013/06/12 18:04:02,-001,0001,0024
NANO,*C2:288.5739     C3:27200.78     CF:BA0F         CM:4
NANO,*CS:7412         D1:.0572567     D2:.0000000     DH:2000.000
NANO,*DL:0            DM:0            DO:0            DP:6
NANO,*DZ:.0000000     EM:0            ET:0            FD:.153479
NANO,*FM:0            GD:0            GE:2            GF:0
NANO,*GP::            GT:1            IA1:8           IA2:12
NANO,*IB:0            ID:1            IE:0            IK:46
NANO,*IM:0            IS:5            IY:0            KH:0
NANO,*LH:2250.000     LL:.0000000     M1:13.880032    M3:14.090198
NANO,*MA:             MD:0            MU:             MX:0
NANO,*NO:0            OI:0            OP:2100.000     OR:1.00
NANO,*OY:1.000000     OZ:0            PA:.0000000     PC:.0000000
NANO,*PF:2000.000     PI:25           PL:2400.000     PM:1.000000
NANO,*PO:0            PR:238          PS:0            PT:N
NANO,*PX:3            RE:0            RS:5            RU:0
NANO,*SD:12           SE:0            SI:OFF          SK:0
NANO,*SL:0            SM:OFF          SP:0            ST:10
NANO,*SU:0            T1:30.00412     T2:1.251426     T3:50.64434
NANO,*T4:134.5816     T5:.0000000     TC:.6781681     TF:.00
NANO,*TH:1,P4;>OK     TI:25           TJ:2            TP:0
NANO,*TQ:1            TR:952          TS:1            TU:0
NANO,*U0:5.839037     UE:0            UF:1.000000
NANO,*UL:                             UM:user         UN:1
NANO,*US:0            VP:4            WI:Def=15:00-061311
NANO,*XC:8            XD:A            XM:1            XN:0
NANO,*XS:0011         XX:1            Y1:-3818.141    Y2:-10271.53
NANO,*Y3:.0000000     ZE:0            ZI:0            ZL:0
NANO,*ZM:0            ZS:0            ZV:.0000000"""

SYST_STATUS = \
"""SYST,2014/04/07 20:46:35,*BOTPT BPR and tilt instrument controller
SYST,2014/04/07 20:46:35,*ts7550n3
SYST,2014/04/07 20:46:35,*System uptime
SYST,2014/04/07 20:46:35,* 20:17:02 up 13 days, 19:11,  0 users,  load average: 0.00, 0.00, 0.00
SYST,2014/04/07 20:46:35,*Memory stats
SYST,2014/04/07 20:46:35,*             total       used       free     shared    buffers     cached
SYST,2014/04/07 20:46:35,*Mem:         62888      18520      44368          0       2260       5120
SYST,2014/04/07 20:46:35,*-/+ buffers/cache:      11140      51748
SYST,2014/04/07 20:46:35,*Swap:            0          0          0
SYST,2014/04/07 20:46:35,*MemTotal:        62888 kB
SYST,2014/04/07 20:46:35,*MemFree:         44392 kB
SYST,2014/04/07 20:46:35,*Buffers:          2260 kB
SYST,2014/04/07 20:46:35,*Cached:           5120 kB
SYST,2014/04/07 20:46:35,*SwapCached:          0 kB
SYST,2014/04/07 20:46:35,*Active:          10032 kB
SYST,2014/04/07 20:46:35,*Inactive:         3328 kB
SYST,2014/04/07 20:46:35,*SwapTotal:           0 kB
SYST,2014/04/07 20:46:35,*SwapFree:            0 kB
SYST,2014/04/07 20:46:35,*Dirty:               0 kB
SYST,2014/04/07 20:46:35,*Writeback:           0 kB
SYST,2014/04/07 20:46:35,*AnonPages:        6000 kB
SYST,2014/04/07 20:46:35,*Mapped:           3976 kB
SYST,2014/04/07 20:46:35,*Slab:             3128 kB
SYST,2014/04/07 20:46:35,*SReclaimable:      800 kB
SYST,2014/04/07 20:46:35,*SUnreclaim:       2328 kB
SYST,2014/04/07 20:46:35,*PageTables:        512 kB
SYST,2014/04/07 20:46:35,*NFS_Unstable:        0 kB
SYST,2014/04/07 20:46:35,*Bounce:              0 kB
SYST,2014/04/07 20:46:35,*CommitLimit:     31444 kB
SYST,2014/04/07 20:46:35,*Committed_AS:   167276 kB
SYST,2014/04/07 20:46:35,*VmallocTotal:   188416 kB
SYST,2014/04/07 20:46:35,*VmallocUsed:         0 kB
SYST,2014/04/07 20:46:35,*VmallocChunk:   188416 kB
SYST,2014/04/07 20:46:35,*Listening network services
SYST,2014/04/07 20:46:35,*tcp        0      0 *:9337-commands         *:*                     LISTEN
SYST,2014/04/07 20:46:35,*tcp        0      0 *:9338-data             *:*                     LISTEN
SYST,2014/04/07 20:46:35,*udp        0      0 *:323                   *:*
SYST,2014/04/07 20:46:35,*udp        0      0 *:54361                 *:*
SYST,2014/04/07 20:46:35,*udp        0      0 *:mdns                  *:*
SYST,2014/04/07 20:46:35,*udp        0      0 *:ntp                   *:*
SYST,2014/04/07 20:46:35,*Data processes
SYST,2014/04/07 20:46:35,*root       643  0.0  2.2  20100  1436 ?        Sl   Mar25   0:01 /root/bin/COMMANDER
SYST,2014/04/07 20:46:35,*root       647  0.0  2.5  21124  1604 ?        Sl   Mar25   0:16 /root/bin/SEND_DATA
SYST,2014/04/07 20:46:35,*root       650  0.0  2.2  19960  1388 ?        Sl   Mar25   0:00 /root/bin/DIO_Rel1
SYST,2014/04/07 20:46:35,*root       654  0.0  2.1  19960  1360 ?        Sl   Mar25   0:02 /root/bin/HEAT
SYST,2014/04/07 20:46:35,*root       667  0.0  2.2  19960  1396 ?        Sl   Mar25   0:00 /root/bin/IRIS
SYST,2014/04/07 20:46:35,*root       672  0.0  2.2  19960  1396 ?        Sl   Mar25   0:01 /root/bin/LILY
SYST,2014/04/07 20:46:35,*root       678  0.0  2.2  19964  1400 ?        Sl   Mar25   0:12 /root/bin/NANO
SYST,2014/04/07 20:46:35,*root       685  0.0  2.2  19960  1396 ?        Sl   Mar25   0:00 /root/bin/RESO
SYST,2014/04/07 20:46:35,*root      7860  0.0  0.9   1704   604 ?        S    20:17   0:00 grep root/bin"""

LILY_FILTERED_STATUS1 = NEWLINE.join([line for line in LILY_STATUS1.split(NEWLINE) if line.startswith('LILY')])
LILY_FILTERED_STATUS2 = NEWLINE.join([line for line in LILY_STATUS2.split(NEWLINE) if line.startswith('LILY')])
IRIS_FILTERED_STATUS1 = NEWLINE.join([line for line in IRIS_STATUS1.split(NEWLINE) if line.startswith('IRIS')])
IRIS_FILTERED_STATUS2 = NEWLINE.join([line for line in IRIS_STATUS2.split(NEWLINE) if line.startswith('IRIS')])
NANO_FILTERED_STATUS = NEWLINE.join([line for line in NANO_STATUS.split(NEWLINE) if line.startswith('NANO')])
SYST_FILTERED_STATUS = NEWLINE.join([line for line in SYST_STATUS.split(NEWLINE) if line.startswith('SYST')])
