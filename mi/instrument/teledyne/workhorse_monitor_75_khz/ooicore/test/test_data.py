from mi.instrument.teledyne.workhorse_monitor_75_khz.ooicore.driver import NEWLINE

# From Lytle
SAMPLE_RAW_DATA = "7F7FF002000612004D008E008001FA01740200003228C941000D041E2D002003600101400900D0070\
114001F000000007D3DD104610301053200620028000006FED0FC090100FF00A148000014800001000C0C0D0D323862000000\
FF050800E014C5EE93EE2300040A000000000000454A4F4B4A4E829F80810088BDB09DFFFFFF9208000000140C0C0D0D323862\
000120FF570089000FFF0080008000800080008000800080008000800080008000800080008000800080008000800080008000\
800080008000800080008000800080008000800080008000800080008000800080008000800080008000800080008000800080\
00800080008000800080008000800080008000800080008000800080008000800080008000800080008000800080008000800\
0800080008000800080008000800080008000800080008000800080008000800080008000800080008000800080008000800080\
008000800080008000800080008000800080008000800080008000800080008000800080008000025D585068650D0D2C0C0D0\
C0E0C0E0C0D0C0E0D0C0C0E0E0B0D0E0D0D0D0C0C0C0C0E0F0E0C0D0F0C0D0E0F0D0C0C0D0D0D00000E0D00000D0B00000D0\
C00000C0C00000C0B00000E0C00000D0C00000D0C00000D0C00000C0C00000D0C00000C00000000000000000000000000000\
000000000000000000000035A52675150434B454341484142414841424148414241484142414841424148414241484142414\
8414241484142414741424148414241474142414841434148414241484142414841424148414241484142414841424148414\
24148414241484142414741424148414241484142414741424148414241484100040400005F00006400000064000000640000\
006400000064000000640000006400000064000000640000006400000064000000640000006400000064000000640000006400\
00006400000064000000640000006400000064000000640000006400000064000000640000006400000064000000640000006400\
FA604091"


break_success_str = NEWLINE + "[BREAK Wakeup A]" + NEWLINE +\
"WorkHorse Broadband ADCP Version 50.40" + NEWLINE +\
"Teledyne RD Instruments (c) 1996-2010" + NEWLINE +\
"All Rights Reserved." + NEWLINE +\
">"


break_alarm_str = NEWLINE + "[ALARM Wakeup A]" + NEWLINE +\
"WorkHorse Broadband ADCP Version 50.40" + NEWLINE +\
"Teledyne RD Instruments (c) 1996-2010" + NEWLINE +\
"All Rights Reserved." + NEWLINE +\
">"

EF_CHAR = '\xef'

CALIBRATION_RAW_DATA = \
"" + NEWLINE +\
"              ACTIVE FLUXGATE CALIBRATION MATRICES in NVRAM" + NEWLINE + \
"               Calibration date and time: 9/14/2012  09:25:32" + NEWLINE + \
"                             S inverse" + NEWLINE + \
"          " + EF_CHAR + "                                                  " + EF_CHAR + "" + NEWLINE + \
"     Bx   " + EF_CHAR + "   3.9218e-01  3.9660e-01 -3.1681e-02  6.4332e-03 " + EF_CHAR + "" + NEWLINE + \
"     By   " + EF_CHAR + "  -2.4320e-02 -1.0376e-02 -2.2428e-03 -6.0628e-01 " + EF_CHAR + "" + NEWLINE + \
"     Bz   " + EF_CHAR + "   2.2453e-01 -2.1972e-01 -2.7990e-01 -2.4339e-03 " + EF_CHAR + "" + NEWLINE + \
"     Err  " + EF_CHAR + "   4.6514e-01 -4.0455e-01  6.9083e-01 -1.4291e-02 " + EF_CHAR + "" + NEWLINE + \
"          " + EF_CHAR + "                                                  " + EF_CHAR + "" + NEWLINE + \
"                             Coil Offset" + NEWLINE + \
"                         " + EF_CHAR + "                " + EF_CHAR + "" + NEWLINE + \
"                         " + EF_CHAR + "   3.4233e+04   " + EF_CHAR + "" + NEWLINE + \
"                         " + EF_CHAR + "   3.4449e+04   " + EF_CHAR + "" + NEWLINE + \
"                         " + EF_CHAR + "   3.4389e+04   " + EF_CHAR + "" + NEWLINE + \
"                         " + EF_CHAR + "   3.4698e+04   " + EF_CHAR + "" + NEWLINE + \
"                         " + EF_CHAR + "                " + EF_CHAR + "" + NEWLINE + \
"                             Electrical Null" + NEWLINE + \
"                              " + EF_CHAR + "       " + EF_CHAR + "" + NEWLINE + \
"                              " + EF_CHAR + " 34285 " + EF_CHAR + "" + NEWLINE + \
"                              " + EF_CHAR + "       " + EF_CHAR + "" + NEWLINE + \
"                    TILT CALIBRATION MATRICES in NVRAM" + NEWLINE + \
"                Calibration date and time: 9/14/2012  09:14:45" + NEWLINE + \
"              Average Temperature During Calibration was   24.4 " + EF_CHAR + "C" + NEWLINE + \
"" + NEWLINE + \
"                   Up                              Down" + NEWLINE + \
"" + NEWLINE + \
"        " + EF_CHAR + "                           " + EF_CHAR + "     " + EF_CHAR + "                           " + EF_CHAR + "" + NEWLINE + \
" Roll   " + EF_CHAR + "   7.4612e-07  -3.1727e-05 " + EF_CHAR + "     " + EF_CHAR + "  -3.0054e-07   3.2190e-05 " + EF_CHAR + "" + NEWLINE + \
" Pitch  " + EF_CHAR + "  -3.1639e-05  -6.3505e-07 " + EF_CHAR + "     " + EF_CHAR + "  -3.1965e-05  -1.4881e-07 " + EF_CHAR + "" + NEWLINE + \
"        " + EF_CHAR + "                           " + EF_CHAR + "     " + EF_CHAR + "                           " + EF_CHAR + "" + NEWLINE + \
"" + NEWLINE + \
"        " + EF_CHAR + "                           " + EF_CHAR + "     " + EF_CHAR + "                           " + EF_CHAR + "" + NEWLINE + \
" Offset " + EF_CHAR + "   3.2808e+04   3.2568e+04 " + EF_CHAR + "     " + EF_CHAR + "   3.2279e+04   3.3047e+04 " + EF_CHAR + "" + NEWLINE + \
"        " + EF_CHAR + "                           " + EF_CHAR + "     " + EF_CHAR + "                           " + EF_CHAR + "" + NEWLINE + \
"" + NEWLINE + \
"                             " + EF_CHAR + "       " + EF_CHAR + "" + NEWLINE + \
"                      Null   " + EF_CHAR + " 33500 " + EF_CHAR + "" + NEWLINE + \
"                             " + EF_CHAR + "       " + EF_CHAR + "" + NEWLINE + \
"" + NEWLINE + \
"" + NEWLINE + \
"" + NEWLINE + \
"" + NEWLINE + \
"" + NEWLINE + \
">"

PS0_RAW_DATA = \
"Instrument S/N:  18444" + NEWLINE +\
"       Frequency:  76800 HZ" + NEWLINE +\
"   Configuration:  4 BEAM, JANUS" + NEWLINE +\
"     Match Layer:  10" + NEWLINE +\
"      Beam Angle:  20 DEGREES" + NEWLINE +\
"    Beam Pattern:  CONVEX" + NEWLINE +\
"     Orientation:  UP" + NEWLINE +\
"       Sensor(s):  HEADING  TILT 1  TILT 2  DEPTH  TEMPERATURE  PRESSURE" + NEWLINE +\
"Pressure Sens Coefficients:" + NEWLINE +\
"              c3 = -1.927850E-11" + NEWLINE +\
"              c2 = +1.281892E-06" + NEWLINE +\
"              c1 = +1.375793E+00" + NEWLINE +\
"          Offset = +2.813725E+00" + NEWLINE +\
"" + NEWLINE +\
"Temp Sens Offset:  -0.01 degrees C" + NEWLINE +\
"" + NEWLINE +\
"    CPU Firmware:  50.40 [0]" + NEWLINE +\
"   Boot Code Ver:  Required:  1.16   Actual:  1.16" + NEWLINE +\
"    DEMOD #1 Ver:  ad48, Type:  1f" + NEWLINE +\
"    DEMOD #2 Ver:  ad48, Type:  1f" + NEWLINE +\
"    PWRTIMG  Ver:  85d3, Type:   7" + NEWLINE +\
"" + NEWLINE +\
"Board Serial Number Data:" + NEWLINE +\
"   72  00 00 06 FE BC D8  09 HPA727-3009-00B" + NEWLINE +\
"   81  00 00 06 F5 CD 9E  09 REC727-1004-06A" + NEWLINE +\
"   A5  00 00 06 FF 1C 79  09 HPI727-3007-00A" + NEWLINE +\
"   82  00 00 06 FF 23 E5  09 CPU727-2011-00E" + NEWLINE +\
"   07  00 00 06 F6 05 15  09 TUN727-1005-06A" + NEWLINE +\
"   DB  00 00 06 F5 CB 5D  09 DSP727-2001-06H" + NEWLINE +\
">"


PS3_RAW_DATA = \
"Beam Width:   3.7 degrees" + NEWLINE +\
"" + NEWLINE +\
"Beam     Elevation     Azimuth" + NEWLINE +\
"  1         -70.00      270.00" + NEWLINE +\
"  2         -70.00       90.00" + NEWLINE +\
"  3         -70.00        0.01" + NEWLINE +\
"  4         -70.00      180.00" + NEWLINE +\
"" + NEWLINE +\
"Beam Directional Matrix (Down):" + NEWLINE +\
"  0.3420    0.0000    0.9397    0.2419" + NEWLINE +\
" -0.3420    0.0000    0.9397    0.2419" + NEWLINE +\
"  0.0000   -0.3420    0.9397   -0.2419" + NEWLINE +\
"  0.0000    0.3420    0.9397   -0.2419" + NEWLINE +\
"" + NEWLINE +\
"Instrument Transformation Matrix (Down):    Q14:" + NEWLINE +\
"  1.4619   -1.4619    0.0000    0.0000       23952  -23952       0       0" + NEWLINE +\
"  0.0000    0.0000   -1.4619    1.4619           0       0  -23952   23952" + NEWLINE +\
"  0.2661    0.2661    0.2661    0.2661        4359    4359    4359    4359" + NEWLINE +\
"  1.0337    1.0337   -1.0337   -1.0337       16936   16936  -16936  -16936" + NEWLINE +\
"Beam Angle Corrections Are Loaded." + NEWLINE +\
">"

PS4_RAW_DATA = \
"Ping Sequence:  W W" + NEWLINE +\
">" 

FD_RAW_DATA = \
"Total Unique Faults   =     2" + NEWLINE +\
"Overflow Count        =     0" + NEWLINE +\
"Time of first fault:    13/02/11,10:05:43.29" + NEWLINE +\
"Time of last fault:     13/02/22,12:59:26.80" + NEWLINE +\
"" + NEWLINE +\
"Fault Log:" + NEWLINE +\
"Entry #  0 Code=0a08h  Count=    5  Delta=7679898 Time=13/02/22,12:59:26.66" + NEWLINE +\
" Parameter = 00000000h" + NEWLINE +\
"  Tilt axis X over range." + NEWLINE +\
"Entry #  1 Code=0a09h  Count=    5  Delta=7679899 Time=13/02/22,12:59:26.80" + NEWLINE +\
" Parameter = 00000000h" + NEWLINE +\
"  Tilt axis Y over range." + NEWLINE +\
"End of fault log." + NEWLINE + NEWLINE +\
">"

"""
if fx is on...

Total Unique Faults   =     2
Overflow Count        =     0
Time of first fault:    13/02/26,08:43:51.39
Time of last fault:     13/02/26,08:43:51.54

Fault Log:
Entry #  0 Code=0a08h  Count=    1  Delta=    0 Time=13/02/26,08:43:51.39
 Parameter = 00000000h
  Tilt axis X over range.
Entry #  1 Code=0a09h  Count=    1  Delta=    0 Time=13/02/26,08:43:51.54
 Parameter = 00000000h
  Tilt axis Y over range.
End of fault log.

Fault Log Dump:  addr=007EADC8
a5 01 00 02 00 00 00 00 27 08 2b 33 02 1a 0d 01
36 08 2b 33 02 1a 0d 01 02 26 0a 08 00 00 00 01
27 08 2b 33 02 1a 0d 01 00 00 00 00 00 00 00 00
00 cb 0a 09 00 00 00 01 36 08 2b 33 02 1a 0d 01
00 00 00 00 00 00 00 00 00 db 00 00 00 00 00 00
00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00
00 01 00 00 00 00 00 00 00 00 00 00 00 00 00 00
00 00 00 00 00 00 00 00 00 01 00 00 00 00 00 00
00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00
00 01 00 00 00 00 00 00 00 00 00 00 00 00 00 00
00 00 00 00 00 00 00 00 00 01 00 00 00 00 00 00
00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00
00 01 00 00 00 00 00 00 00 00 00 00 00 00 00 00
00 00 00 00 00 00 00 00 00 01 00 00 00 00 00 00
00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00
00 01 00 00 00 00 00 00 00 00 00 00 00 00 00 00
00 00 00 00 00 00 00 00 00 01
"""

PT200_RAW_DATA = \
"Ambient  Temperature =    18.44 Degrees C" + NEWLINE +\
"  Attitude Temperature =    21.55 Degrees C" + NEWLINE +\
"  Internal Moisture    = 8F26h" + NEWLINE +\
"" + NEWLINE +\
"Correlation Magnitude: Narrow Bandwidth" + NEWLINE +\
"" + NEWLINE +\
"               Lag  Bm1  Bm2  Bm3  Bm4" + NEWLINE +\
"                 0  255  255  255  255" + NEWLINE +\
"                 1  153  136  134  164" + NEWLINE +\
"                 2   66   39   77   48" + NEWLINE +\
"                 3   54    3   43   43" + NEWLINE +\
"                 4   43   15   21   62" + NEWLINE +\
"                 5   29   17    8   38" + NEWLINE +\
"                 6   24    7    3   63" + NEWLINE +\
"                 7   15    7   12   83" + NEWLINE +\
"" + NEWLINE +\
"  High Gain RSSI:    63   58   74   73" + NEWLINE +\
"   Low Gain RSSI:     6    7   10    8" + NEWLINE +\
"" + NEWLINE +\
"  SIN Duty Cycle:    49   49   50   49" + NEWLINE +\
"  COS Duty Cycle:    50   48   50   49" + NEWLINE +\
"" + NEWLINE +\
"Receive Test Results = $00020000 ... FAIL" + NEWLINE +\
"" + NEWLINE +\
"IXMT    =      5.4 Amps rms  [Data=7bh]" + NEWLINE +\
"VXMT    =    387.2 Volts rms [Data=b9h]" + NEWLINE +\
"   Z    =     71.8 Ohms" + NEWLINE +\
"Transmit Test Results = $0 ... PASS" + NEWLINE +\
"" + NEWLINE +\
"    0    0    0    0" + NEWLINE +\
"    0    0    0    0" + NEWLINE +\
"    0    0    0    0" + NEWLINE +\
"   12   12   12   12" + NEWLINE +\
"  255  255  255  255" + NEWLINE +\
"    0    0    0    0" + NEWLINE +\
"   12   12   12   12" + NEWLINE +\
"  255  255  255  255" + NEWLINE +\
"    0    0    0    0" + NEWLINE +\
"    0    0    0    0" + NEWLINE +\
"   12   12   12   12" + NEWLINE +\
"  255  255  255  255" + NEWLINE +\
"Electronics Test Results = $00000000" + NEWLINE +\
"Receive Bandwidth:" + NEWLINE +\
"    Sample      bw    bw    bw    bw    bw" + NEWLINE +\
"      rate  expect   Bm1   Bm2   Bm3   Bm4" + NEWLINE +\
"        19       7     4     6     5     3 Khz" + NEWLINE +\
"   results          PASS  PASS  PASS  FAIL" + NEWLINE +\
"RSSI Time Constant:" + NEWLINE +\
"" + NEWLINE +\
"RSSI Filter Strobe 1 =   38400 Hz" + NEWLINE +\
"  time   Bm1   Bm2   Bm3   Bm4" + NEWLINE +\
"  msec  cnts  cnts  cnts  cnts" + NEWLINE +\
"     1     7     8     8     8" + NEWLINE +\
"     2    12    15    14    15" + NEWLINE +\
"     3    16    20    20    22" + NEWLINE +\
"     4    21    25    25    27" + NEWLINE +\
"     5    24    29    29    31" + NEWLINE +\
"     6    27    32    33    35" + NEWLINE +\
"     7    30    35    36    38" + NEWLINE +\
"     8    32    37    39    41" + NEWLINE +\
"     9    34    39    41    43" + NEWLINE +\
"    10    35    41    43    45" + NEWLINE +\
"   nom    45    49    54    55" + NEWLINE +\
"result    PASS  PASS  PASS  PASS" + NEWLINE +\
">" 



powering_down_str = NEWLINE +\
"Powering Down"

# typed CS, got samples
# sent a break 300
# instrument wokeup, but 10 minutes later had not sent below warning...
# From Lytle
self_deploy_str = NEWLINE +\
"System will self-deploy in 1 minute unless valid command entered!"

get_params_output = \
            "CI?" + NEWLINE +\
            "CI = 000 ----------------- Instrument ID (0-255)" + NEWLINE +\
            ">" + NEWLINE +\
            ">CP?" + NEWLINE +\
            "CP = 0 ------------------- PolledMode (1=ON, 0=OFF;  BREAK resets)" + NEWLINE +\
            ">" + NEWLINE +\
            ">CQ?" + NEWLINE +\
            "CQ = 255 ----------------- Xmt Power (0=Low, 255=High)" + NEWLINE +\
            ">" + NEWLINE +\
            ">TB?" + NEWLINE +\
            "TB 00:00:00.00 --------- Time per Burst (hrs:min:sec.sec/100)" + NEWLINE +\
            ">" + NEWLINE +\
            ">TC?" + NEWLINE +\
            "TC 00002 --------------- Ensembles Per Burst (0-65535)" + NEWLINE +\
            ">" + NEWLINE +\
            ">TE?" + NEWLINE +\
            "TE 01:00:00.00 --------- Time per Ensemble (hrs:min:sec.sec/100)" + NEWLINE +\
            ">" + NEWLINE +\
            ">TF?" + NEWLINE +\
            "TF **/**/**,**:**:** --- Time of First Ping (yr/mon/day,hour:min:sec)" + NEWLINE +\
            ">" + NEWLINE +\
            ">TG?" + NEWLINE +\
            "TG ****/**/**,**:**:** - Time of First Ping (CCYY/MM/DD,hh:mm:ss)" + NEWLINE +\
            ">" + NEWLINE +\
            ">TP?" + NEWLINE +\
            "TP 01:20.00 ------------ Time per Ping (min:sec.sec/100)" + NEWLINE +\
            ">" + NEWLINE +\
            ">TT?" + NEWLINE +\
            "TT 2013/02/28,07:55:33 - Time Set (CCYY/MM/DD,hh:mm:ss)" + NEWLINE +\
            ">" + NEWLINE +\
            ">TX?" + NEWLINE +\
            "TX 00:00:00 ------------ Buffer Output Period: (hh:mm:ss)" + NEWLINE +\
            ">" + NEWLINE +\
            ">WA?" + NEWLINE +\
            "WA 255,001 ------------- False Target Threshold (Max)(0-255),[Start Bin]" + NEWLINE +\
            ">" + NEWLINE +\
            ">WC?" + NEWLINE +\
            "WC 064 ----------------- Correlation Threshold" + NEWLINE +\
            ">" + NEWLINE +\
            ">WD?" + NEWLINE +\
            "WD 111100000 ----------- Data Out (Vel;Cor;Amp  PG;St;P0  P1;P2;P3)" + NEWLINE +\
            ">" + NEWLINE +\
            ">WE?" + NEWLINE +\
            "WE 5000 ---------------- Error Velocity Threshold (0-5000 mm/s)" + NEWLINE +\
            ">" + NEWLINE +\
            ">WF?" + NEWLINE +\
            "WF 0088 ---------------- Blank After Transmit (cm)" + NEWLINE +\
            ">" + NEWLINE +\
            ">WI?" + NEWLINE +\
            "WI 0 ------------------- Clip Data Past Bottom (0=OFF,1=ON)" + NEWLINE +\
            ">" + NEWLINE +\
            ">WJ?" + NEWLINE +\
            "WJ 1 ------------------- Rcvr Gain Select (0=Low,1=High)" + NEWLINE +\
            ">" + NEWLINE +\
            ">WL?" + NEWLINE +\
            "WL 001,005 ------------- Water Reference Layer:  Begin Cell (0=OFF), End Cell" + NEWLINE +\
            ">" + NEWLINE +\
            ">WM?" + NEWLINE +\
            "WM 1 ------------------- Profiling Mode (1-15)" + NEWLINE +\
            ">" + NEWLINE +\
            ">WN?" + NEWLINE +\
            "WN 030 ----------------- Number of depth cells (1-255)" + NEWLINE +\
            ">" + NEWLINE +\
            ">WP?" + NEWLINE +\
            "WP 00045 --------------- Pings per Ensemble (0-16384)" + NEWLINE +\
            ">" + NEWLINE +\
            ">WS?" + NEWLINE +\
            "WS 0800 ---------------- Depth Cell Size (cm)" + NEWLINE +\
            ">" + NEWLINE +\
            ">WT?" + NEWLINE +\
            "WT 0000 ---------------- Transmit Length (cm) [0 = Bin Length]" + NEWLINE +\
            ">" + NEWLINE +\
            ">WU?" + NEWLINE +\
            "WU 0 ------------------- Ping Weighting (0=Box,1=Triangle)" + NEWLINE +\
            ">" + NEWLINE +\
            ">WV?" + NEWLINE +\
            "WV 175 ----------------- Mode 1 Ambiguity Vel (cm/s radial)" + NEWLINE +\
            ">" + NEWLINE +\
            ">CC?" + NEWLINE +\
            "CC = 000 000 000 --------- Choose External Devices (x;x;x  x;x;x  x;x;SBMC)" + NEWLINE +\
            ">" + NEWLINE +\
            ">CH?" + NEWLINE +\
            "CH = 1 ------------------- Suppress Banner" + NEWLINE +\
            ">" + NEWLINE +\
            "CJ?" + NEWLINE +\
            "CJ = 0 ------------------- IMM Output Enable (0=Disable,1=Enable)" + NEWLINE +\
            ">" + NEWLINE +\
            ">CL?" + NEWLINE +\
            "CL = 0 ------------------- Sleep Enable (0 = Disable, 1 = Enable, 2 See Manual)" + NEWLINE +\
            ">" + NEWLINE +\
            ">CM?" + NEWLINE +\
            "CM = 0 ------------------- RS-232 Sync Master (0 = OFF, 1 = ON)" + NEWLINE +\
            ">" + NEWLINE +\
            ">CN?" + NEWLINE +\
            "CN = 1 ------------------- Save NVRAM to recorder (0 = ON, 1 = OFF)" + NEWLINE +\
            ">" + NEWLINE +\
            ">CW?" + NEWLINE +\
            "CW = 00250 --------------- Trigger Timeout (ms; 0 = no timeout)" + NEWLINE +\
            ">" + NEWLINE +\
            ">CX?" + NEWLINE +\
            "CX = 1 ------------------- Trigger Enable (0 = OFF, 1 = ON)" + NEWLINE +\
            ">" + NEWLINE +\
            ">EA?" + NEWLINE +\
            "EA = +00000 -------------- Heading Alignment (1/100 deg)" + NEWLINE +\
            ">" + NEWLINE +\
            ">EB?" + NEWLINE +\
            "EB = +00000 -------------- Heading Bias (1/100 deg)" + NEWLINE +\
            ">" + NEWLINE +\
            ">EC?" + NEWLINE +\
            "EC = 1500 ---------------- Speed Of Sound (m/s)" + NEWLINE +\
            ">" + NEWLINE +\
            ">ED?" + NEWLINE +\
            "ED = 00000 --------------- Transducer Depth (0 - 65535 dm)" + NEWLINE +\
            ">" + NEWLINE +\
            ">EH?" + NEWLINE +\
            "EH = 00000 --------------- Heading (1/100 deg)" + NEWLINE +\
            ">" + NEWLINE +\
            ">EP?" + NEWLINE +\
            "EP = +0000 --------------- Tilt 1 Sensor (1/100 deg)" + NEWLINE +\
            ">" + NEWLINE +\
            ">ER?" + NEWLINE +\
            "ER = +0000 --------------- Tilt 2 Sensor (1/100 deg)" + NEWLINE +\
            ">" + NEWLINE +\
            ">ES?" + NEWLINE +\
            "ES = 35 ------------------ Salinity (0-40 pp thousand)" + NEWLINE +\
            ">" + NEWLINE +\
            ">ET?" + NEWLINE +\
            "ET = +2500 --------------- Temperature (1/100 deg Celsius)" + NEWLINE +\
            ">" + NEWLINE +\
            ">EX?" + NEWLINE +\
            "EX = 00000 --------------- Coord Transform (Xform:Type; Tilts; 3Bm; Map)" + NEWLINE +\
            ">" + NEWLINE +\
            ">EZ?" + NEWLINE +\
            "EZ = 1111101 ------------- Sensor Source (C;D;H;P;R;S;T)" + NEWLINE +\
            ">" + NEWLINE +\
            ">PB?" + NEWLINE +\
            "PB = 001,000,1 ------------- PD12 Bin Select (first;num;sub)" + NEWLINE +\
            ">" + NEWLINE +\
            ">PD?" + NEWLINE +\
            "PD = 00 ------------------ Data Stream Select (0-18)" + NEWLINE +\
            ">" + NEWLINE +\
            ">PE?" + NEWLINE +\
            "PE = 00001 --------------- PD12 Ensemble Select (1-65535)" + NEWLINE +\
            ">" + NEWLINE +\
            ">PO?" + NEWLINE +\
            "PO = 1111 ---------------- PD12 Velocity Component Select (v1;v2;v3;v4)" + NEWLINE +\
            ">" + NEWLINE +\
            ">SA?" + NEWLINE +\
            "SA = 001 ----------------- Synch Before/After Ping/Ensemble Bottom/Water/Both" + NEWLINE +\
            ">" + NEWLINE +\
            ">SB?" + NEWLINE +\
            "SB = 1 ------------------- Channel B Break Interrupts are ENABLED" + NEWLINE +\
            ">" + NEWLINE +\
            ">SI?" + NEWLINE +\
            "SI = 00000 --------------- Synch Interval (0-65535)" + NEWLINE +\
            ">" + NEWLINE +\
            ">SM?" + NEWLINE +\
            "SM = 1 ------------------- Mode Select (0=OFF,1=MASTER,2=SLAVE,3=NEMO)" + NEWLINE +\
            ">" + NEWLINE +\
            ">SS?" + NEWLINE +\
            "SS = 0 ------------------- RDS3 Sleep Mode (0=No Sleep)" + NEWLINE +\
            ">" + NEWLINE +\
            ">ST?" + NEWLINE +\
            "ST = 00000 --------------- Slave Timeout (seconds,0=indefinite)" + NEWLINE +\
            ">" + NEWLINE +\
            ">SW?" + NEWLINE +\
            "SW = 00100 --------------- Synch Delay (1/10 msec)" + NEWLINE +\
            ">" + NEWLINE +\
            ">DW?" + NEWLINE +\
            "DW  0 ------------------ Current ID on RS-485 Bus" + NEWLINE +\
            ">" + NEWLINE +\
            ">RI?" + NEWLINE +\
            "" + NEWLINE +\
            "Deployment Auto Increment is ENABLED" + NEWLINE +\
            NEWLINE +\
            ">" + NEWLINE +\
            ">RN?" + NEWLINE +\
            NEWLINE +\
            "Current deployment name = _RDI_" + NEWLINE +\
            NEWLINE +\
            ">" + NEWLINE +\
            ">WB?" + NEWLINE +\
            "WB 1 ------------------- Bandwidth Control (0=Wid,1=Nar)" + NEWLINE +\
            ">" + NEWLINE +\
            ">WG?" + NEWLINE +\
            "WG 000 ----------------- Percent Good Minimum (1-100%)" + NEWLINE +\
            ">" + NEWLINE +\
            ">WQ?" + NEWLINE +\
            "WQ 0 ------------------- Sample Ambient Sound (0=OFF,1=ON)" + NEWLINE +\
            ">" + NEWLINE +\
            ">WW?" + NEWLINE +\
            "WW 004 ----------------- Mode 1 Pings before Mode 4 Re-acquire" + NEWLINE +\
            ">" + NEWLINE +\
            ">WZ?" + NEWLINE +\
            "WZ 010 ----------------- Mode 5 Ambiguity Velocity (cm/s radial)" + NEWLINE +\
            ">" + NEWLINE +\
            ">AZ?" + NEWLINE +\
            NEWLINE +\
            " 13.386345" + NEWLINE +\
            NEWLINE +\
            ">" + NEWLINE +\
            ">CB?" + NEWLINE +\
            "CB = 411 ----------------- Serial Port Control (Baud [4=9600]; Par; Stop)" + NEWLINE +\
            ">" + NEWLINE +\
            ">CD?" + NEWLINE +\
            "CD = 000 000 000 --------- Serial Data Out (Vel;Cor;Amp  PG;St;P0  P1;P2;P3)" + NEWLINE +\
            ">" + NEWLINE +\
            ">CF?" + NEWLINE +\
            "CF = 11110 --------------- Flow Ctrl (EnsCyc;PngCyc;Binry;Ser;Rec)" + NEWLINE +\
            ">" + NEWLINE +\
            ">DB?" + NEWLINE +\
            "DB 411 ----------------- RS-485 Port Control (Baud; N/U; N/U)" + NEWLINE +\
            ">" + NEWLINE