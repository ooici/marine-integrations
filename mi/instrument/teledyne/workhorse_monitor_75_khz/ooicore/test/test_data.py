


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


CALIBRATION_RAW_DATA = \
"" + NEWLINE +\
"              ACTIVE FLUXGATE CALIBRATION MATRICES in NVRAM" + NEWLINE + \
"               Calibration date and time: 9/14/2012  09:25:32" + NEWLINE + \
"                             S inverse" + NEWLINE + \
"          �                                                  �" + NEWLINE + \
"     Bx   �   3.9218e-01  3.9660e-01 -3.1681e-02  6.4332e-03 �" + NEWLINE + \
"     By   �  -2.4320e-02 -1.0376e-02 -2.2428e-03 -6.0628e-01 �" + NEWLINE + \
"     Bz   �   2.2453e-01 -2.1972e-01 -2.7990e-01 -2.4339e-03 �" + NEWLINE + \
"     Err  �   4.6514e-01 -4.0455e-01  6.9083e-01 -1.4291e-02 �" + NEWLINE + \
"          �                                                  �" + NEWLINE + \
"                             Coil Offset" + NEWLINE + \
"                         �                �" + NEWLINE + \
"                         �   3.4233e+04   �" + NEWLINE + \
"                         �   3.4449e+04   �" + NEWLINE + \
"                         �   3.4389e+04   �" + NEWLINE + \
"                         �   3.4698e+04   �" + NEWLINE + \
"                         �                �" + NEWLINE + \
"                             Electrical Null" + NEWLINE + \
"                              �       �" + NEWLINE + \
"                              � 34285 �" + NEWLINE + \
"                              �       �" + NEWLINE + \
"                    TILT CALIBRATION MATRICES in NVRAM" + NEWLINE + \
"                Calibration date and time: 9/14/2012  09:14:45" + NEWLINE + \
"              Average Temperature During Calibration was   24.4 �C" + NEWLINE + \
"" + NEWLINE + \
"                   Up                              Down" + NEWLINE + \
"" + NEWLINE + \
"        �                           �     �                           �" + NEWLINE + \
" Roll   �   7.4612e-07  -3.1727e-05 �     �  -3.0054e-07   3.2190e-05 �" + NEWLINE + \
" Pitch  �  -3.1639e-05  -6.3505e-07 �     �  -3.1965e-05  -1.4881e-07 �" + NEWLINE + \
"        �                           �     �                           �" + NEWLINE + \
"" + NEWLINE + \
"        �                           �     �                           �" + NEWLINE + \
" Offset �   3.2808e+04   3.2568e+04 �     �   3.2279e+04   3.3047e+04 �" + NEWLINE + \
"        �                           �     �                           �" + NEWLINE + \
"" + NEWLINE + \
"                             �       �" + NEWLINE + \
"                      Null   � 33500 �" + NEWLINE + \
"                             �       �" + NEWLINE + \
"" + NEWLINE + \
"" + NEWLINE + \
"" + NEWLINE + \
"" + NEWLINE + \
"" + NEWLINE + \
">"

PS0_RAW_DATA = \
"  Instrument S/N:  18444" + NEWLINE +\
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


PT200_RAW_DATA = \
"  Ambient  Temperature =    18.44 Degrees C" + NEWLINE +\
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
 