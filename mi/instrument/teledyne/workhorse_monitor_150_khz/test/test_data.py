from mi.instrument.teledyne.workhorse_monitor_150_khz.driver import NEWLINE

SAMPLE_RAW_DATA1 = \
"7F7FF002000612004D008E008001FA01740200003228C941000D041E0A002003000001FF09000F270000001F000000007D3D7103610305063200620028000006FED0FC090100F000A148000014800001000D0516120C355C00000000060900A714C5EE93EE28002409000000000000414A534A4A52829F80810088A3BE280200009C06000000140D0516120C355C000100800080008000800080008000800080008000800080008000800080008000800080008000800080008000800080008000800080008000800080008000800080008000800080008000800080008000800080008000800080008000800080008000800080008000800080008000800080008000800080008000800080008000800080008000800080008000800080008000800080008000800080008000800080008000800080008000800080008000800080008000800080008000800080008000800080008000800080008000800080008000800080008000800080008000800080008000800080008000800080008000022E5A384D100B0B0E0C0D0B0E0D0E0D0C0C0A0B0D0C0C0C0D0D0D0D0B0D0C0E0D0C0C0B0D110A120A0C0F0C0C0E0E0D0C0B00000D0D00000E0D00000A0E00000B0C00000D0E00000B0E00000F0C00000E0F00000B0E00000C0B00000E0B0000090000000000000000000000000000000000000000000000000003161722160B090D0B0B080C0A0B090C0A0B090C0A0B080C0A0B090C0A0B090C0A0B090D0A0B090C0A0B090C0A0B090C0A0B090C0A0B090C0A0B080C0A0B090C0A0B090C0A0B090C0A0B090C0A0B090C0A0B090C0A0B080C0A0B090C0A0B090C0A0B080C0A0B080C0A0B090C0A0B090D0A0B080C0A0B090C0A000400006400000064000000640000006400000064000000640000006400000064000000640000006400000064000000640000006400000064000000640000006400000064000000640000006400000064000000640000006400000064000000640000006400000064000000640000006400000064000000640098254F6E"
SAMPLE_RAW_DATA2 = \
"7F7FF002000612004D008E008001FA01740200003228C941000D041E0A002003000001FF09000F270000001F000000007D3D7103610305063200620028000006FED0FC090100F000A148000014800002000D0516120E355C000000000611009814C5EE93EE28002309000000000000414B534A4A52829F00000088A4BEFC060000D706000000140D0516120E355C00010080008000800080008000800080008000800080008000800080008000800080008000800080008000800080008000800080008000800080008000800080008000800080008000800080008000800080008000800080008000800080008000800080008000800080008000800080008000800080008000800080008000800080008000800080008000800080008000800080008000800080008000800080008000800080008000800080008000800080008000800080008000800080008000800080008000800080008000800080008000800080008000800080008000800080008000800080008000800080008000800002325B3B4D100A0C0E0D0C0A0B0D0E0C0D0C0D0D0C0D0D0B0B0C0D0C0A0B0E0D0D100D090A0C0C0A0C0C0D110D0D0C0E0D0D00000A0E00000F0C00000E0E00000C0B00000D0900000F0E00000F0C00000E0F00000D0F00000E0C00000A0F00000C0000000000000000000000000000000000000000000000000003161823160B090E0B0B090C0A0B090C0A0B090C0A0B090C0A0B080C0A0B090C0A0B090C0A0B090C0A0B080C0A0B090C0A0B090C0A0B090D0A0B080D0A0B090C0A0B090D0A0B090D0A0B080D0A0B090C0A0B090C0A0B090D0A0B090C0A0B090C0A0B080C0B0B090C0A0B090D0A0B090C0A0B090C0A0B090C0A00040000640000006400000064000000640000006400000064000000640000006400000064000000640000006400000064000000640000006400000064000000640000006400000064000000640000006400000064000000640000006400000064000000640000006400000064000000640000006400000064009B26786E"
SAMPLE_RAW_DATA3 = \
"7F7FF002000612004D008E008001FA01740200003228C941000D041E0A002003000001FF09000F270000001F000000007D3D7103610305063200620028000006FED0FC090100F000A148000014800003000D05161210355C000000000608008D14C5EE93EE28002309000000000000414A534A4A52829F00000088A4BE30010000D807000000140D05161210355C0001008000800080008000800080008000800080008000800080008000800080008000800080008000800080008000800080008000800080008000800080008000800080008000800080008000800080008000800080008000800080008000800080008000800080008000800080008000800080008000800080008000800080008000800080008000800080008000800080008000800080008000800080008000800080008000800080008000800080008000800080008000800080008000800080008000800080008000800080008000800080008000800080008000800080008000800080008000800080008000800080000236593E4B0F0A0D0A0B0D0D0B0D0C0B0B0C0B0D0D0D0E0E0A0C0D0C0C0C0B0D0C0C0D0F0C100F100B0C0C0B0E0E0D0C0E0D00000E0C00000E0F00000B0D00000B0D00000F0A00000D0E00000D0D00000B0D00000C0C00000C0E00000E1000000D0000000000000000000000000000000000000000000000000003161724160B090E0B0B090C0A0B090C0A0B090C0A0B090C0A0B090D0A0B090C0A0B090C0A0B090C0A0B090C0A0B090C0A0B090D0A0B090C0A0B080C0A0B080C0A0B090C0A0B080C0A0B090C0A0B090C0A0B090C0A0B090C0A0B090C0A0B090C0A0B090C0A0B090D0A0B090C0A0B090C0A0B090C0A0B080C0A00040000640000006400000064000000640000006400000064000000640000006400000064000000640000006400000064000000640000006400000064000000640000006400000064000000640000006400000064000000640000006400000064000000640000006400000064000000640000006400000064009C289E6D"
SAMPLE_RAW_DATA4 = \
"7F7FF002000612004D008E008001FA01740200003228C941000D041E0A002003000001FF09000F270000001F000000007D3D7103610305063200620028000006FED0FC090100F000A148000014800004000D05161212355C000000000609009414C5EE93EE28002309000000000000414B534A4A52829F00000088A4BE05030000D205000000140D05161212355C00010080008000800080008000800080008000800080008000800080008000800080008000800080008000800080008000800080008000800080008000800080008000800080008000800080008000800080008000800080008000800080008000800080008000800080008000800080008000800080008000800080008000800080008000800080008000800080008000800080008000800080008000800080008000800080008000800080008000800080008000800080008000800080008000800080008000800080008000800080008000800080008000800080008000800080008000800080008000800080008000800002365A384E0F0D0D100F0C0F0E0E0C0E0E0A100E0B0B0E0D0D0B090E0B0C0E0C0E0E0E0E0A0D0F0B0A0D100B0C0F0C0F100C00000B0D00000D0B00000F0F00000B0C00000E0D00000F0B00000F0F00000D0B00000B0D00000B0D00000B0A00000D0000000000000000000000000000000000000000000000000003161723160C090D0B0B090C0A0B090C0A0B090C0A0B090C0A0B090C0A0B090C0A0B090C0A0B090C0A0B090C0A0B080C0A0B090C0A0B090C0A0B090C0A0B090C0A0B080C0A0B090C0A0B080C0A0B080C0A0B090C0A0B090C0A0B090C0A0B080C0A0B090C0A0B090C0A0B090C0A0B090C0A0B090D0A0B090C0A00040000640000006400000064000000640000006400000064000000640000006400000064000000640000006400000064000000640000006400000064000000640000006400000064000000640000006400000064000000640000006400000064000000640000006400000064000000640000006400000064009E26856D"




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
"ACTIVE FLUXGATE CALIBRATION MATRICES in NVRAM" + NEWLINE + \
"               Calibration date and time: 9/22/2012  11:53:32" + NEWLINE + \
"                             S inverse" + NEWLINE + \
"          " + EF_CHAR + "                                                  " + EF_CHAR + NEWLINE + \
"     Bx   " + EF_CHAR + "   4.1275e-01  4.2168e-01 -2.0631e-02 -2.8440e-05 " + EF_CHAR + NEWLINE + \
"     By   " + EF_CHAR + "  -4.9163e-03  4.7625e-06 -2.7393e-03 -5.6853e-01 " + EF_CHAR + NEWLINE + \
"     Bz   " + EF_CHAR + "   2.1975e-01 -2.0662e-01 -3.0120e-01  2.7459e-03 " + EF_CHAR + NEWLINE + \
"     Err  " + EF_CHAR + "   4.8227e-01 -4.4007e-01  6.5367e-01 -7.3235e-03 " + EF_CHAR + NEWLINE + \
"          " + EF_CHAR + "                                                  " + EF_CHAR + NEWLINE + \
"                             Coil Offset" + NEWLINE + \
"                         " + EF_CHAR + "                " + EF_CHAR + NEWLINE + \
"                         " + EF_CHAR + "   3.3914e+04   " + EF_CHAR + NEWLINE + \
"                         " + EF_CHAR + "   3.3331e+04   " + EF_CHAR + NEWLINE + \
"                         " + EF_CHAR + "   3.4030e+04   " + EF_CHAR + NEWLINE + \
"                         " + EF_CHAR + "   3.4328e+04   " + EF_CHAR + NEWLINE + \
"                         " + EF_CHAR + "                " + EF_CHAR + NEWLINE + \
"                             Electrical Null" + NEWLINE + \
"                              " + EF_CHAR + "       " + EF_CHAR + NEWLINE + \
"                              " + EF_CHAR + " 33989 " + EF_CHAR + NEWLINE + \
"                              " + EF_CHAR + "       " + EF_CHAR + NEWLINE + \
"                    TILT CALIBRATION MATRICES in NVRAM" + NEWLINE + \
"                Calibration date and time: 9/22/2012  11:50:48" + NEWLINE + \
"              Average Temperature During Calibration was   25.7 " + EF_CHAR + "C" + NEWLINE + \
NEWLINE + \
"                   Up                              Down" + NEWLINE + \
NEWLINE + \
"        " + EF_CHAR + "                           " + EF_CHAR + "     " + EF_CHAR + "                           " + EF_CHAR + NEWLINE + \
" Roll   " + EF_CHAR + "  -1.7305e-07  -2.9588e-05 " + EF_CHAR + "     " + EF_CHAR + "   3.0294e-07   3.1274e-05 " + EF_CHAR + NEWLINE + \
" Pitch  " + EF_CHAR + "  -2.9052e-05  -5.6057e-07 " + EF_CHAR + "     " + EF_CHAR + "  -3.1059e-05  -5.2326e-07 " + EF_CHAR + NEWLINE + \
"        " + EF_CHAR + "                           " + EF_CHAR + "     " + EF_CHAR + "                           " + EF_CHAR + NEWLINE + \
NEWLINE + \
"        " + EF_CHAR + "                           " + EF_CHAR + "     " + EF_CHAR + "                           " + EF_CHAR + NEWLINE + \
" Offset " + EF_CHAR + "   3.2805e+04   3.2384e+04 " + EF_CHAR + "     " + EF_CHAR + "   3.3287e+04   3.1595e+04 " + EF_CHAR + NEWLINE + \
"        " + EF_CHAR + "                           " + EF_CHAR + "     " + EF_CHAR + "                           " + EF_CHAR + NEWLINE + \
NEWLINE + \
"                             " + EF_CHAR + "       " + EF_CHAR + NEWLINE + \
"                      Null   " + EF_CHAR + " 33272 " + EF_CHAR + NEWLINE + \
"                             " + EF_CHAR + "       " + EF_CHAR + NEWLINE + \
NEWLINE + \
NEWLINE + \
NEWLINE + \
NEWLINE + \
NEWLINE + \
">"

PS0_RAW_DATA = \
"Instrument S/N:  18593" + NEWLINE +\
"       Frequency:  153600 HZ" + NEWLINE +\
"   Configuration:  4 BEAM, JANUS" + NEWLINE +\
"     Match Layer:  10" + NEWLINE +\
"      Beam Angle:  20 DEGREES" + NEWLINE +\
"    Beam Pattern:  CONVEX" + NEWLINE +\
"     Orientation:  UP" + NEWLINE +\
"       Sensor(s):  HEADING  TILT 1  TILT 2  DEPTH  TEMPERATURE  PRESSURE" + NEWLINE +\
"Pressure Sens Coefficients:" + NEWLINE +\
"              c3 = +1.629386E-10" + NEWLINE +\
"              c2 = -1.886023E-06" + NEWLINE +\
"              c1 = +1.364779E+00" + NEWLINE +\
"          Offset = -2.457906E+01" + NEWLINE +\
NEWLINE +\
"Temp Sens Offset:  -0.17 degrees C" + NEWLINE +\
NEWLINE +\
"    CPU Firmware:  50.40 [0]" + NEWLINE +\
"   Boot Code Ver:  Required:  1.16   Actual:  1.16" + NEWLINE +\
"    DEMOD #1 Ver:  ad48, Type:  1f" + NEWLINE +\
"    DEMOD #2 Ver:  ad48, Type:  1f" + NEWLINE +\
"    PWRTIMG  Ver:  85d3, Type:   6" + NEWLINE +\
NEWLINE +\
"Board Serial Number Data:" + NEWLINE +\
"   98  00 00 06 FF 13 A0  09 HPI727-3007-00A" + NEWLINE +\
"   28  00 00 06 FE D0 FC  09 CPU727-2011-00E" + NEWLINE +\
"   0C  00 00 06 FF 13 BA  09 HPA727-3009-02B" + NEWLINE +\
"   E7  00 00 06 B2 C6 7D  09 REC727-1004-05A" + NEWLINE +\
"   70  00 00 06 F5 AF 73  09 DSP727-2001-05H" + NEWLINE +\
"   F0  00 00 06 F5 B2 EB  09 TUN727-1005-05A" + NEWLINE +\
">"


PS3_RAW_DATA = \
"Beam Width:   3.7 degrees" + NEWLINE +\
NEWLINE +\
"Beam     Elevation     Azimuth" + NEWLINE +\
"  1         -69.81      269.92" + NEWLINE +\
"  2         -70.00       89.92" + NEWLINE +\
"  3         -69.82        0.07" + NEWLINE +\
"  4         -69.89      180.08" + NEWLINE +\
NEWLINE +\
"Beam Directional Matrix (Down):" + NEWLINE +\
"  0.3453    0.0005    0.9385    0.2421" + NEWLINE +\
" -0.3421   -0.0005    0.9397    0.2444" + NEWLINE +\
" -0.0005   -0.3451    0.9386   -0.2429" + NEWLINE +\
"  0.0005    0.3438    0.9390   -0.2438" + NEWLINE +\
NEWLINE +\
"Instrument Transformation Matrix (Down):    Q14:" + NEWLINE +\
"  1.4587   -1.4508   -0.0010   -0.0051       23899  -23770     -16     -83" + NEWLINE +\
" -0.0008    0.0033   -1.4532    1.4500         -13      54  -23809   23757" + NEWLINE +\
"  0.2650    0.2676    0.2657    0.2667        4342    4384    4353    4370" + NEWLINE +\
"  1.0225    1.0323   -1.0257   -1.0297       16752   16913  -16805  -16871" + NEWLINE +\
"Beam Angle Corrections Are Loaded." + NEWLINE +\
">"

PS4_RAW_DATA = \
"Ping Sequence:  W W W W W W W W W W" + NEWLINE +\
">" 

FD_RAW_DATA = \
"Total Unique Faults   =     2" + NEWLINE +\
"Overflow Count        =     0" + NEWLINE +\
"Time of first fault:    12/11/29,19:40:37.02" + NEWLINE +\
"Time of last fault:     12/12/12,20:31:37.14" + NEWLINE +\
NEWLINE +\
"Fault Log:" + NEWLINE +\
"Entry #  0 Code=0a08h  Count=    2  Delta=112625967 Time=12/12/12,20:31:36.99" + NEWLINE +\
" Parameter = 00000000h" + NEWLINE +\
"  Tilt axis X over range." + NEWLINE +\
"Entry #  1 Code=0a09h  Count=    2  Delta=112625966 Time=12/12/12,20:31:37.14" + NEWLINE +\
" Parameter = 00000000h" + NEWLINE +\
"  Tilt axis Y over range." + NEWLINE +\
"End of fault log." + NEWLINE + NEWLINE +\
"Fault Log Dump:  addr=007EADC8" + NEWLINE +\
"a5 01 00 02 00 00 00 00 20 13 28 25 0b 1d 0c 06" + NEWLINE +\
"0e 14 1f 25 0c 0c 0c 05 01 f2 0a 08 00 00 00 02" + NEWLINE +\
"63 14 1f 24 0c 0c 0c 05 06 b6 89 2f 00 00 00 00" + NEWLINE +\
"02 6c 0a 09 00 00 00 02 0e 14 1f 25 0c 0c 0c 05" + NEWLINE +\
"06 b6 89 2e 00 00 00 00 02 18 00 00 00 00 00 00" + NEWLINE +\
"00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00" + NEWLINE +\
"00 01 00 00 00 00 00 00 00 00 00 00 00 00 00 00" + NEWLINE +\
"00 00 00 00 00 00 00 00 00 01 00 00 00 00 00 00" + NEWLINE +\
"00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00" + NEWLINE +\
"00 01 00 00 00 00 00 00 00 00 00 00 00 00 00 00" + NEWLINE +\
"00 00 00 00 00 00 00 00 00 01 00 00 00 00 00 00" + NEWLINE +\
"00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00" + NEWLINE +\
"00 01 00 00 00 00 00 00 00 00 00 00 00 00 00 00" + NEWLINE +\
"00 00 00 00 00 00 00 00 00 01 00 00 00 00 00 00" + NEWLINE +\
"00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00" + NEWLINE +\
"00 01 00 00 00 00 00 00 00 00 00 00 00 00 00 00" + NEWLINE +\
"00 00 00 00 00 00 00 00 00 01" + NEWLINE +\
">"



PT200_RAW_DATA = \
"Ambient  Temperature =    23.43 Degrees C" + NEWLINE +\
"  Attitude Temperature =    23.96 Degrees C" + NEWLINE +\
"  Internal Moisture    = 8C66h" + NEWLINE +\
NEWLINE +\
"Correlation Magnitude: Narrow Bandwidth" + NEWLINE +\
NEWLINE +\
"               Lag  Bm1  Bm2  Bm3  Bm4" + NEWLINE +\
"                 0  255  255  255  255" + NEWLINE +\
"                 1  140  159  178  149" + NEWLINE +\
"                 2   37   63   92   54" + NEWLINE +\
"                 3   15   17   42    9" + NEWLINE +\
"                 4   16    6   20    5" + NEWLINE +\
"                 5    7    4   12    4" + NEWLINE +\
"                 6   10    1   12    4" + NEWLINE +\
"                 7    8    2    9    4" + NEWLINE +\
NEWLINE +\
"  High Gain RSSI:    67   65   72   65" + NEWLINE +\
"   Low Gain RSSI:    11    8   12   10" + NEWLINE +\
NEWLINE +\
"  SIN Duty Cycle:    49   50   48   48" + NEWLINE +\
"  COS Duty Cycle:    50   50   50   49" + NEWLINE +\
NEWLINE +\
"Receive Test Results = 00000000 ... PASS" + NEWLINE +\
NEWLINE +\
"IXMT    =      0.8 Amps rms  [Data=45h]" + NEWLINE +\
"VXMT    =     43.8 Volts rms [Data=4ah]" + NEWLINE +\
"   Z    =     55.5 Ohms" + NEWLINE +\
"Transmit Test Results = $0 ... PASS" + NEWLINE +\
NEWLINE +\
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
"        38      12    13    12    10    14 Khz" + NEWLINE +\
"   results          PASS  PASS  PASS  PASS" + NEWLINE +\
"RSSI Time Constant:" + NEWLINE +\
NEWLINE +\
"RSSI Filter Strobe 1 =   38400 Hz" + NEWLINE +\
"  time   Bm1   Bm2   Bm3   Bm4" + NEWLINE +\
"  msec  cnts  cnts  cnts  cnts" + NEWLINE +\
"     1     5     7     6     7" + NEWLINE +\
"     2    11    14    11    12" + NEWLINE +\
"     3    15    19    15    17" + NEWLINE +\
"     4    19    23    19    22" + NEWLINE +\
"     5    22    27    22    25" + NEWLINE +\
"     6    25    29    25    28" + NEWLINE +\
"     7    27    32    27    30" + NEWLINE +\
"     8    29    33    29    32" + NEWLINE +\
"     9    31    35    31    34" + NEWLINE +\
"    10    32    36    32    35" + NEWLINE +\
"   nom    40    43    41    43" + NEWLINE +\
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
            NEWLINE +\
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
