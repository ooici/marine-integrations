#!/usr/bin/env python

"""
@package mi.dataset.parser.cg_stc_eng_stc
@file marine-integrations/mi/dataset/parser/cg_stc_eng_stc.py
@author Mike Nicoletti
@brief Parser for the cg_stc_eng_stc dataset driver
Release notes:

Starting the cg_stc_eng_stc driver
"""

__author__ = 'Mike Nicoletti'
__license__ = 'Apache 2.0'

import copy
import re
import ntplib

from mi.core.log import get_logger ; log = get_logger()
from mi.core.common import BaseEnum
from mi.core.instrument.data_particle import DataParticle, DataParticleKey
from mi.core.exceptions import SampleException, DatasetParserException, SampleEncodingException
from mi.dataset.dataset_parser import Parser
from mi.dataset.param_dict import DatasetParameterDict

class CgDataParticleType(BaseEnum):
    SAMPLE = 'cg_stc_eng_stc'

class CgStcEngStcParserDataParticleKey(BaseEnum):
    CG_ENG_PLATFORM_TIME = 'cg_eng_platform_time'
    CG_ENG_PLATFORM_UTIME = 'cg_eng_platform_utime'
    CG_ENG_MSG_CNTS_C_GPS = 'cg_eng_msg_cnts_c_gps'
    CG_ENG_MSG_CNTS_C_NTP = 'cg_eng_msg_cnts_c_ntp'
    CG_ENG_MSG_CNTS_C_PPS = 'cg_eng_msg_cnts_c_pps'
    CG_ENG_MSG_CNTS_C_POWER_SYS = 'cg_eng_msg_cnts_c_power_sys'
    CG_ENG_MSG_CNTS_C_SUPERV = 'cg_eng_msg_cnts_c_superv'
    CG_ENG_MSG_CNTS_C_TELEM = 'cg_eng_msg_cnts_c_telem'
    CG_ENG_ERR_C_GPS = 'cg_eng_err_c_gps'
    CG_ENG_ERR_C_PPS = 'cg_eng_err_c_pps'
    CG_ENG_ERR_C_CTL = 'cg_eng_err_c_ctl'
    CG_ENG_ERR_C_STATUS = 'cg_eng_err_c_status'
    CG_ENG_ERR_SUPERV = 'cg_eng_err_superv'
    CG_ENG_ERR_C_POWER_SYS = 'cg_eng_err_c_power_sys'
    CG_ENG_ERR_C_TELEM_SYS = 'cg_eng_err_c_telem_sys'
    CG_ENG_ERR_C_IRID = 'cg_eng_err_c_irid'
    CG_ENG_ERR_C_IMM = 'cg_eng_err_c_imm'
    CG_ENG_ERR_CPM1 = 'cg_eng_err_cpm1'
    CG_ENG_ERR_D_CTL = 'cg_eng_err_d_ctl'
    CG_ENG_ERR_D_STATUS = 'cg_eng_err_d_status'
    CG_ENG_ERR_DLOG_MGR = 'cg_eng_err_dlog_mgr'
    CG_ENG_ERR_DLOGP1 = 'cg_eng_err_dlogp1'
    CG_ENG_ERR_DLOGP2 = 'cg_eng_err_dlogp2'
    CG_ENG_ERR_DLOGP3 = 'cg_eng_err_dlogp3'
    CG_ENG_ERR_DLOGP4 = 'cg_eng_err_dlogp4'
    CG_ENG_ERR_DLOGP5 = 'cg_eng_err_dlogp5'
    CG_ENG_ERR_DLOGP6 = 'cg_eng_err_dlogp6'
    CG_ENG_ERR_DLOGP7 = 'cg_eng_err_dlogp7'
    CG_ENG_ERR_DLOGP8 = 'cg_eng_err_dlogp8'
    CG_ENG_ERR_RCMD = 'cg_eng_err_rcmd'
    CG_ENG_ERR_BCMD = 'cg_eng_err_bcmd'
    CG_ENG_ERRMSG_C_GPS = 'cg_eng_errmsg_c_gps'
    CG_ENG_ERRMSG_C_PPS = 'cg_eng_errmsg_c_pps'
    CG_ENG_ERRMSG_C_CTL = 'cg_eng_errmsg_c_ctl'
    CG_ENG_ERRMSG_C_STATUS = 'cg_eng_errmsg_c_status'
    CG_ENG_ERRMSG_SUPERV = 'cg_eng_errmsg_superv'
    CG_ENG_ERRMSG_C_POWER_SYS = 'cg_eng_errmsg_c_power_sys'
    CG_ENG_ERRMSG_C_TELEM_SYS = 'cg_eng_errmsg_c_telem_sys'
    CG_ENG_ERRMSG_C_IRID = 'cg_eng_errmsg_c_irid'
    CG_ENG_ERRMSG_C_IMM = 'cg_eng_errmsg_c_imm'
    CG_ENG_ERRMSG_CPM1 = 'cg_eng_errmsg_cpm1'
    CG_ENG_ERRMSG_D_CTL = 'cg_eng_errmsg_d_ctl'
    CG_ENG_ERRMSG_D_STATUS = 'cg_eng_errmsg_d_status'
    CG_ENG_ERRMSG_DLOG_MGR = 'cg_eng_errmsg_dlog_mgr'
    CG_ENG_ERRMSG_DLOGP1 = 'cg_eng_errmsg_dlogp1'
    CG_ENG_ERRMSG_DLOGP2 = 'cg_eng_errmsg_dlogp2'
    CG_ENG_ERRMSG_DLOGP3 = 'cg_eng_errmsg_dlogp3'
    CG_ENG_ERRMSG_DLOGP4 = 'cg_eng_errmsg_dlogp4'
    CG_ENG_ERRMSG_DLOGP5 = 'cg_eng_errmsg_dlogp5'
    CG_ENG_ERRMSG_DLOGP6 = 'cg_eng_errmsg_dlogp6'
    CG_ENG_ERRMSG_DLOGP7 = 'cg_eng_errmsg_dlogp7'
    CG_ENG_ERRMSG_DLOGP8 = 'cg_eng_errmsg_dlogp8'
    CG_ENG_ERRMSG_RCMD = 'cg_eng_errmsg_rcmd'
    CG_ENG_ERRMSG_BCMD = 'cg_eng_errmsg_bcmd'
    CG_ENG_CPU_UPTIME = 'cg_eng_cpu_uptime'
    CG_ENG_CPU_LOAD1 = 'cg_eng_cpu_load1'
    CG_ENG_CPU_LOAD5 = 'cg_eng_cpu_load5'
    CG_ENG_CPU_LOAD15 = 'cg_eng_cpu_load15'
    CG_ENG_MEMORY_RAM = 'cg_eng_memory_ram'
    CG_ENG_MEMORY_FREE = 'cg_eng_memory_free'
    CG_ENG_NPROC = 'cg_eng_nproc'
    CG_ENG_MPIC_EFLAG = 'cg_eng_mpic_eflag'
    CG_ENG_MPIC_MAIN_V = 'cg_eng_mpic_main_v'
    CG_ENG_MPIC_MAIN_C = 'cg_eng_mpic_main_c'
    CG_ENG_MPIC_BAT_V = 'cg_eng_mpic_bat_v'
    CG_ENG_MPIC_BAT_C = 'cg_eng_mpic_bat_c'
    CG_ENG_MPIC_TEMP1 = 'cg_eng_mpic_temp1'
    CG_ENG_MPIC_TEMP2 = 'cg_eng_mpic_temp2'
    CG_ENG_MPIC_HUMID = 'cg_eng_mpic_humid'
    CG_ENG_MPIC_PRESS = 'cg_eng_mpic_press'
    CG_ENG_MPIC_GF_ENA = 'cg_eng_mpic_gf_ena'
    CG_ENG_MPIC_GFLT1 = 'cg_eng_mpic_gflt1'
    CG_ENG_MPIC_GFLT2 = 'cg_eng_mpic_gflt2'
    CG_ENG_MPIC_GFLT3 = 'cg_eng_mpic_gflt3'
    CG_ENG_MPIC_GFLT4 = 'cg_eng_mpic_gflt4'
    CG_ENG_MPIC_LD_ENA = 'cg_eng_mpic_ld_ena'
    CG_ENG_MPIC_LDET1 = 'cg_eng_mpic_ldet1'
    CG_ENG_MPIC_LDET2 = 'cg_eng_mpic_ldet2'
    CG_ENG_MPIC_WSRC = 'cg_eng_mpic_wsrc'
    CG_ENG_MPIC_IRID = 'cg_eng_mpic_irid'
    CG_ENG_MPIC_IRID_V = 'cg_eng_mpic_irid_v'
    CG_ENG_MPIC_IRID_C = 'cg_eng_mpic_irid_c'
    CG_ENG_MPIC_IRID_E = 'cg_eng_mpic_irid_e'
    CG_ENG_MPIC_FW_WIFI = 'cg_eng_mpic_fw_wifi'
    CG_ENG_MPIC_FW_WIFI_V = 'cg_eng_mpic_fw_wifi_v'
    CG_ENG_MPIC_FW_WIFI_C = 'cg_eng_mpic_fw_wifi_c'
    CG_ENG_MPIC_FW_WIFI_E = 'cg_eng_mpic_fw_wifi_e'
    CG_ENG_MPIC_GPS = 'cg_eng_mpic_gps'
    CG_ENG_MPIC_SBD = 'cg_eng_mpic_sbd'
    CG_ENG_MPIC_SBD_CE_MSG = 'cg_eng_mpic_sbd_ce_msg'
    CG_ENG_MPIC_PPS = 'cg_eng_mpic_pps'
    CG_ENG_MPIC_DCL = 'cg_eng_mpic_dcl'
    CG_ENG_MPIC_ESW = 'cg_eng_mpic_esw'
    CG_ENG_MPIC_DSL = 'cg_eng_mpic_dsl'
    CG_ENG_MPIC_HBEAT_ENABLE = 'cg_eng_mpic_hbeat_enable'
    CG_ENG_MPIC_HBEAT_DTIME = 'cg_eng_mpic_hbeat_dtime'
    CG_ENG_MPIC_HBEAT_THRESHOLD = 'cg_eng_mpic_hbeat_threshold'
    CG_ENG_MPIC_WAKE_CPM = 'cg_eng_mpic_wake_cpm'
    CG_ENG_MPIC_WPC = 'cg_eng_mpic_wpc'
    CG_ENG_MPIC_EFLAG2 = 'cg_eng_mpic_eflag2'
    CG_ENG_MPIC_LAST_UPDATE = 'cg_eng_mpic_last_update'
    CG_ENG_GPS_MSG_DATE = 'cg_eng_gps_msg_date'
    CG_ENG_GPS_MSG_TIME = 'cg_eng_gps_msg_time'
    CG_ENG_GPS_DATE = 'cg_eng_gps_date'
    CG_ENG_GPS_TIME = 'cg_eng_gps_time'
    CG_ENG_GPS_LATSTR = 'cg_eng_gps_latstr'
    CG_ENG_GPS_LONSTR = 'cg_eng_gps_lonstr'
    CG_ENG_GPS_LAT = 'cg_eng_gps_lat'
    CG_ENG_GPS_LON = 'cg_eng_gps_lon'
    CG_ENG_GPS_SPD = 'cg_eng_gps_spd'
    CG_ENG_GPS_COG = 'cg_eng_gps_cog'
    CG_ENG_GPS_FIX = 'cg_eng_gps_fix'
    CG_ENG_GPS_NSAT = 'cg_eng_gps_nsat'
    CG_ENG_GPS_HDOP = 'cg_eng_gps_hdop'
    CG_ENG_GPS_ALT = 'cg_eng_gps_alt'
    CG_ENG_GPS_LAST_UPDATE = 'cg_eng_gps_last_update'
    CG_ENG_NTP_REFID = 'cg_eng_ntp_refid'
    CG_ENG_NTP_OFFSET = 'cg_eng_ntp_offset'
    CG_ENG_NTP_JITTER = 'cg_eng_ntp_jitter'
    CG_ENG_PPS_LOCK = 'cg_eng_pps_lock'
    CG_ENG_PPS_DELTA = 'cg_eng_pps_delta'
    CG_ENG_PPS_DELTAMIN = 'cg_eng_pps_deltamin'
    CG_ENG_PPS_DELTAMAX = 'cg_eng_pps_deltamax'
    CG_ENG_PPS_BAD_PULSE = 'cg_eng_pps_bad_pulse'
    CG_ENG_PPS_TIMESTAMP = 'cg_eng_pps_timestamp'
    CG_ENG_PPS_LAST_UPDATE = 'cg_eng_pps_last_update'
    CG_ENG_LOADSHED_STATUS = 'cg_eng_loadshed_status'
    CG_ENG_LOADSHED_LAST_UPDATE = 'cg_eng_loadshed_last_update'
    CG_ENG_SBC_ETH0 = 'cg_eng_sbc_eth0'
    CG_ENG_SBC_ETH1 = 'cg_eng_sbc_eth1'
    CG_ENG_SBC_LED0 = 'cg_eng_sbc_led0'
    CG_ENG_SBC_LED1 = 'cg_eng_sbc_led1'
    CG_ENG_SBC_LED2 = 'cg_eng_sbc_led2'
    CG_ENG_SBC_GPO0 = 'cg_eng_sbc_gpo0'
    CG_ENG_SBC_GPO1 = 'cg_eng_sbc_gpo1'
    CG_ENG_SBC_GPO2 = 'cg_eng_sbc_gpo2'
    CG_ENG_SBC_GPO3 = 'cg_eng_sbc_gpo3'
    CG_ENG_SBC_GPO4 = 'cg_eng_sbc_gpo4'
    CG_ENG_SBC_GPIO0 = 'cg_eng_sbc_gpio0'
    CG_ENG_SBC_GPIO1 = 'cg_eng_sbc_gpio1'
    CG_ENG_SBC_GPIO2 = 'cg_eng_sbc_gpio2'
    CG_ENG_SBC_GPIO3 = 'cg_eng_sbc_gpio3'
    CG_ENG_SBC_GPIO4 = 'cg_eng_sbc_gpio4'
    CG_ENG_SBC_GPIO5 = 'cg_eng_sbc_gpio5'
    CG_ENG_SBC_FB1 = 'cg_eng_sbc_fb1'
    CG_ENG_SBC_FB2 = 'cg_eng_sbc_fb2'
    CG_ENG_SBC_CE_LED = 'cg_eng_sbc_ce_led'
    CG_ENG_SBC_WDT = 'cg_eng_sbc_wdt'
    CG_ENG_SBC_BID = 'cg_eng_sbc_bid'
    CG_ENG_SBC_BSTR = 'cg_eng_sbc_bstr'
    CG_ENG_MSG_CNTS_D_GPS = 'cg_eng_msg_cnts_d_gps'
    CG_ENG_MSG_CNTS_D_NTP = 'cg_eng_msg_cnts_d_ntp'
    CG_ENG_MSG_CNTS_D_PPS = 'cg_eng_msg_cnts_d_pps'
    CG_ENG_MSG_CNTS_D_SUPERV = 'cg_eng_msg_cnts_d_superv'
    CG_ENG_MSG_CNTS_D_DLOG_NGR = 'cg_eng_msg_cnts_d_dlog_ngr'
    CG_ENG_DCLP1_ENABLE = 'cg_eng_dclp1_enable'
    CG_ENG_DCLP1_VOLT = 'cg_eng_dclp1_volt'
    CG_ENG_DCLP1_CURRENT = 'cg_eng_dclp1_current'
    CG_ENG_DCLP1_EFLAG = 'cg_eng_dclp1_eflag'
    CG_ENG_DCLP1_VSEL = 'cg_eng_dclp1_vsel'
    CG_ENG_DCLP1_CLIM = 'cg_eng_dclp1_clim'
    CG_ENG_DCLP1_PROT = 'cg_eng_dclp1_prot'
    CG_ENG_DCLP2_ENABLE = 'cg_eng_dclp2_enable'
    CG_ENG_DCLP2_VOLT = 'cg_eng_dclp2_volt'
    CG_ENG_DCLP2_CURRENT = 'cg_eng_dclp2_current'
    CG_ENG_DCLP2_EFLAG = 'cg_eng_dclp2_eflag'
    CG_ENG_DCLP2_VSEL = 'cg_eng_dclp2_vsel'
    CG_ENG_DCLP2_CLIM = 'cg_eng_dclp2_clim'
    CG_ENG_DCLP2_PROT = 'cg_eng_dclp2_prot'
    CG_ENG_DCLP3_ENABLE = 'cg_eng_dclp3_enable'
    CG_ENG_DCLP3_VOLT = 'cg_eng_dclp3_volt'
    CG_ENG_DCLP3_CURRENT = 'cg_eng_dclp3_current'
    CG_ENG_DCLP3_EFLAG = 'cg_eng_dclp3_eflag'
    CG_ENG_DCLP3_VSEL = 'cg_eng_dclp3_vsel'
    CG_ENG_DCLP3_CLIM = 'cg_eng_dclp3_clim'
    CG_ENG_DCLP3_PROT = 'cg_eng_dclp3_prot'
    CG_ENG_DCLP4_ENABLE = 'cg_eng_dclp4_enable'
    CG_ENG_DCLP4_VOLT = 'cg_eng_dclp4_volt'
    CG_ENG_DCLP4_CURRENT = 'cg_eng_dclp4_current'
    CG_ENG_DCLP4_EFLAG = 'cg_eng_dclp4_eflag'
    CG_ENG_DCLP4_VSEL = 'cg_eng_dclp4_vsel'
    CG_ENG_DCLP4_CLIM = 'cg_eng_dclp4_clim'
    CG_ENG_DCLP4_PROT = 'cg_eng_dclp4_prot'
    CG_ENG_DCLP5_ENABLE = 'cg_eng_dclp5_enable'
    CG_ENG_DCLP5_VOLT = 'cg_eng_dclp5_volt'
    CG_ENG_DCLP5_CURRENT = 'cg_eng_dclp5_current'
    CG_ENG_DCLP5_EFLAG = 'cg_eng_dclp5_eflag'
    CG_ENG_DCLP5_VSEL = 'cg_eng_dclp5_vsel'
    CG_ENG_DCLP5_CLIM = 'cg_eng_dclp5_clim'
    CG_ENG_DCLP5_PROT = 'cg_eng_dclp5_prot'
    CG_ENG_DCLP6_ENABLE = 'cg_eng_dclp6_enable'
    CG_ENG_DCLP6_VOLT = 'cg_eng_dclp6_volt'
    CG_ENG_DCLP6_CURRENT = 'cg_eng_dclp6_current'
    CG_ENG_DCLP6_EFLAG = 'cg_eng_dclp6_eflag'
    CG_ENG_DCLP6_VSEL = 'cg_eng_dclp6_vsel'
    CG_ENG_DCLP6_CLIM = 'cg_eng_dclp6_clim'
    CG_ENG_DCLP6_PROT = 'cg_eng_dclp6_prot'
    CG_ENG_DCLP7_ENABLE = 'cg_eng_dclp7_enable'
    CG_ENG_DCLP7_VOLT = 'cg_eng_dclp7_volt'
    CG_ENG_DCLP7_CURRENT = 'cg_eng_dclp7_current'
    CG_ENG_DCLP7_EFLAG = 'cg_eng_dclp7_eflag'
    CG_ENG_DCLP7_VSEL = 'cg_eng_dclp7_vsel'
    CG_ENG_DCLP7_CLIM = 'cg_eng_dclp7_clim'
    CG_ENG_DCLP7_PROT = 'cg_eng_dclp7_prot'
    CG_ENG_DCLP8_ENABLE = 'cg_eng_dclp8_enable'
    CG_ENG_DCLP8_VOLT = 'cg_eng_dclp8_volt'
    CG_ENG_DCLP8_CURRENT = 'cg_eng_dclp8_current'
    CG_ENG_DCLP8_EFLAG = 'cg_eng_dclp8_eflag'
    CG_ENG_DCLP8_VSEL = 'cg_eng_dclp8_vsel'
    CG_ENG_DCLP8_CLIM = 'cg_eng_dclp8_clim'
    CG_ENG_DCLP8_PROT = 'cg_eng_dclp8_prot'
    CG_ENG_DCL_PORT_STATUS = 'cg_eng_dcl_port_status'
    CG_ENG_PORT_DLOG1_NAME = 'cg_eng_port_dlog1_name'
    CG_ENG_PORT_DLOG1_STATE = 'cg_eng_port_dlog1_state'
    CG_ENG_PORT_DLOG1_TX = 'cg_eng_port_dlog1_tx'
    CG_ENG_PORT_DLOG1_RX = 'cg_eng_port_dlog1_rx'
    CG_ENG_PORT_DLOG1_LOG = 'cg_eng_port_dlog1_log'
    CG_ENG_PORT_DLOG1_GOOD = 'cg_eng_port_dlog1_good'
    CG_ENG_PORT_DLOG1_BAD = 'cg_eng_port_dlog1_bad'
    CG_ENG_PORT_DLOG1_BB = 'cg_eng_port_dlog1_bb'
    CG_ENG_PORT_DLOG1_LD = 'cg_eng_port_dlog1_ld'
    CG_ENG_PORT_DLOG1_LC = 'cg_eng_port_dlog1_lc'
    CG_ENG_PORT_DLOG1_LU = 'cg_eng_port_dlog1_lu'
    CG_ENG_PORT_DLOG2_NAME = 'cg_eng_port_dlog2_name'
    CG_ENG_PORT_DLOG2_STATE = 'cg_eng_port_dlog2_state'
    CG_ENG_PORT_DLOG2_TX = 'cg_eng_port_dlog2_tx'
    CG_ENG_PORT_DLOG2_RX = 'cg_eng_port_dlog2_rx'
    CG_ENG_PORT_DLOG2_LOG = 'cg_eng_port_dlog2_log'
    CG_ENG_PORT_DLOG2_GOOD = 'cg_eng_port_dlog2_good'
    CG_ENG_PORT_DLOG2_BAD = 'cg_eng_port_dlog2_bad'
    CG_ENG_PORT_DLOG2_BB = 'cg_eng_port_dlog2_bb'
    CG_ENG_PORT_DLOG2_LD = 'cg_eng_port_dlog2_ld'
    CG_ENG_PORT_DLOG2_LC = 'cg_eng_port_dlog2_lc'
    CG_ENG_PORT_DLOG2_LU = 'cg_eng_port_dlog2_lu'
    CG_ENG_PORT_DLOG3_NAME = 'cg_eng_port_dlog3_name'
    CG_ENG_PORT_DLOG3_STATE = 'cg_eng_port_dlog3_state'
    CG_ENG_PORT_DLOG3_TX = 'cg_eng_port_dlog3_tx'
    CG_ENG_PORT_DLOG3_RX = 'cg_eng_port_dlog3_rx'
    CG_ENG_PORT_DLOG3_LOG = 'cg_eng_port_dlog3_log'
    CG_ENG_PORT_DLOG3_GOOD = 'cg_eng_port_dlog3_good'
    CG_ENG_PORT_DLOG3_BAD = 'cg_eng_port_dlog3_bad'
    CG_ENG_PORT_DLOG3_BB = 'cg_eng_port_dlog3_bb'
    CG_ENG_PORT_DLOG3_LD = 'cg_eng_port_dlog3_ld'
    CG_ENG_PORT_DLOG3_LC = 'cg_eng_port_dlog3_lc'
    CG_ENG_PORT_DLOG3_LU = 'cg_eng_port_dlog3_lu'
    CG_ENG_PORT_DLOG4_NAME = 'cg_eng_port_dlog4_name'
    CG_ENG_PORT_DLOG4_STATE = 'cg_eng_port_dlog4_state'
    CG_ENG_PORT_DLOG4_TX = 'cg_eng_port_dlog4_tx'
    CG_ENG_PORT_DLOG4_RX = 'cg_eng_port_dlog4_rx'
    CG_ENG_PORT_DLOG4_LOG = 'cg_eng_port_dlog4_log'
    CG_ENG_PORT_DLOG4_GOOD = 'cg_eng_port_dlog4_good'
    CG_ENG_PORT_DLOG4_BAD = 'cg_eng_port_dlog4_bad'
    CG_ENG_PORT_DLOG4_BB = 'cg_eng_port_dlog4_bb'
    CG_ENG_PORT_DLOG4_LD = 'cg_eng_port_dlog4_ld'
    CG_ENG_PORT_DLOG4_LC = 'cg_eng_port_dlog4_lc'
    CG_ENG_PORT_DLOG4_LU = 'cg_eng_port_dlog4_lu'
    CG_ENG_PORT_DLOG5_NAME = 'cg_eng_port_dlog5_name'
    CG_ENG_PORT_DLOG5_STATE = 'cg_eng_port_dlog5_state'
    CG_ENG_PORT_DLOG5_TX = 'cg_eng_port_dlog5_tx'
    CG_ENG_PORT_DLOG5_RX = 'cg_eng_port_dlog5_rx'
    CG_ENG_PORT_DLOG5_LOG = 'cg_eng_port_dlog5_log'
    CG_ENG_PORT_DLOG5_GOOD = 'cg_eng_port_dlog5_good'
    CG_ENG_PORT_DLOG5_BAD = 'cg_eng_port_dlog5_bad'
    CG_ENG_PORT_DLOG5_BB = 'cg_eng_port_dlog5_bb'
    CG_ENG_PORT_DLOG5_LD = 'cg_eng_port_dlog5_ld'
    CG_ENG_PORT_DLOG5_LC = 'cg_eng_port_dlog5_lc'
    CG_ENG_PORT_DLOG5_LU = 'cg_eng_port_dlog5_lu'
    CG_ENG_PORT_DLOG6_NAME = 'cg_eng_port_dlog6_name'
    CG_ENG_PORT_DLOG6_STATE = 'cg_eng_port_dlog6_state'
    CG_ENG_PORT_DLOG6_TX = 'cg_eng_port_dlog6_tx'
    CG_ENG_PORT_DLOG6_RX = 'cg_eng_port_dlog6_rx'
    CG_ENG_PORT_DLOG6_LOG = 'cg_eng_port_dlog6_log'
    CG_ENG_PORT_DLOG6_GOOD = 'cg_eng_port_dlog6_good'
    CG_ENG_PORT_DLOG6_BAD = 'cg_eng_port_dlog6_bad'
    CG_ENG_PORT_DLOG6_BB = 'cg_eng_port_dlog6_bb'
    CG_ENG_PORT_DLOG6_LD = 'cg_eng_port_dlog6_ld'
    CG_ENG_PORT_DLOG6_LC = 'cg_eng_port_dlog6_lc'
    CG_ENG_PORT_DLOG6_LU = 'cg_eng_port_dlog6_lu'
    CG_ENG_PORT_DLOG7_NAME = 'cg_eng_port_dlog7_name'
    CG_ENG_PORT_DLOG7_STATE = 'cg_eng_port_dlog7_state'
    CG_ENG_PORT_DLOG7_TX = 'cg_eng_port_dlog7_tx'
    CG_ENG_PORT_DLOG7_RX = 'cg_eng_port_dlog7_rx'
    CG_ENG_PORT_DLOG7_LOG = 'cg_eng_port_dlog7_log'
    CG_ENG_PORT_DLOG7_GOOD = 'cg_eng_port_dlog7_good'
    CG_ENG_PORT_DLOG7_BAD = 'cg_eng_port_dlog7_bad'
    CG_ENG_PORT_DLOG7_BB = 'cg_eng_port_dlog7_bb'
    CG_ENG_PORT_DLOG7_LD = 'cg_eng_port_dlog7_ld'
    CG_ENG_PORT_DLOG7_LC = 'cg_eng_port_dlog7_lc'
    CG_ENG_PORT_DLOG7_LU = 'cg_eng_port_dlog7_lu'
    CG_ENG_PORT_DLOG8_NAME = 'cg_eng_port_dlog8_name'
    CG_ENG_PORT_DLOG8_STATE = 'cg_eng_port_dlog8_state'
    CG_ENG_PORT_DLOG8_TX = 'cg_eng_port_dlog8_tx'
    CG_ENG_PORT_DLOG8_RX = 'cg_eng_port_dlog8_rx'
    CG_ENG_PORT_DLOG8_LOG = 'cg_eng_port_dlog8_log'
    CG_ENG_PORT_DLOG8_GOOD = 'cg_eng_port_dlog8_good'
    CG_ENG_PORT_DLOG8_BAD = 'cg_eng_port_dlog8_bad'
    CG_ENG_PORT_DLOG8_BB = 'cg_eng_port_dlog8_bb'
    CG_ENG_PORT_DLOG8_LC = 'cg_eng_port_dlog8_lc'
    CG_ENG_PORT_DLOG8_LD = 'cg_eng_port_dlog8_ld'
    CG_ENG_PORT_DLOG8_LU = 'cg_eng_port_dlog8_lu'
    CG_ENG_DMGRSTATUS_DATE = 'cg_eng_dmgrstatus_date'
    CG_ENG_DMGRSTATUS_TIME = 'cg_eng_dmgrstatus_time'
    CG_ENG_DMGRSTATUS_ACTIVE = 'cg_eng_dmgrstatus_active'
    CG_ENG_DMGRSTATUS_STARTED = 'cg_eng_dmgrstatus_started'
    CG_ENG_DMGRSTATUS_HALTED = 'cg_eng_dmgrstatus_halted'
    CG_ENG_DMGRSTATUS_FAILED = 'cg_eng_dmgrstatus_failed'
    CG_ENG_DMGRSTATUS_MAP = 'cg_eng_dmgrstatus_map'
    CG_ENG_DMGRSTATUS_UPDATE = 'cg_eng_dmgrstatus_update'

class CgStcEngStcParserDataParticle(DataParticle):
    """
    Class for parsing data from the cg_stc_eng_stc data set
    """
    _data_particle_type = CgDataParticleType.SAMPLE

    def _build_parsed_values(self):
        """
        Take something in the data format and turn it into
        a particle with the appropriate tag.
        @throws SampleException If there is a problem with sample creation
        """
        result = []
        # Instantiate the param_dict 
        params = self._build_param_dict()
        
        # Go through the param_dict dictionary for every definition
        params.update(self.raw_data)
        encoding_errors = params.get_encoding_errors()
        self._encoding_errors = encoding_errors
        all_params = params.get_all()
        for (key, value) in all_params.iteritems():
            result.append({DataParticleKey.VALUE_ID: key, DataParticleKey.VALUE: value})
        log.debug("CgStcEngStcParserDataParticle %s", result)
        return result

    def _build_param_dict(self):
        """
        Populate the parameter dictionary with cg_stc_eng_stc parameters.
        For each parameter key, add match stirng, match lambda function,
        and value formatting function.
        """
        # Add parameter handlers to parameter dict.
        p = DatasetParameterDict()
        p.add(CgStcEngStcParserDataParticleKey.CG_ENG_PLATFORM_UTIME,
              r'Platform.utime=(\d+\.\d+)',
              lambda match : float(match.group(1)),
              float)
        p.add(CgStcEngStcParserDataParticleKey.CG_ENG_PLATFORM_TIME,
              r'Platform.time=(.+?)(\r\n?|\n)',
              lambda match : match.group(1),
              str)
        # msg
        msg_cnts_regex = r'STATUS\.msg_cnts=C_GPS=(\d+),\D+=(\d+),\D+=(\d+),\D+\=(\d+),\D+=(\d+),\D+=(\d+)(\r\n?|\n)'
        p.add(CgStcEngStcParserDataParticleKey.CG_ENG_MSG_CNTS_C_GPS,
              msg_cnts_regex, lambda match : int(match.group(1)), int)
        p.add(CgStcEngStcParserDataParticleKey.CG_ENG_MSG_CNTS_C_NTP,
              msg_cnts_regex, lambda match : int(match.group(2)), int)
        p.add(CgStcEngStcParserDataParticleKey.CG_ENG_MSG_CNTS_C_PPS,
              msg_cnts_regex, lambda match : int(match.group(3)), int)
        p.add(CgStcEngStcParserDataParticleKey.CG_ENG_MSG_CNTS_C_POWER_SYS,
              msg_cnts_regex, lambda match : int(match.group(4)), int)
        p.add(CgStcEngStcParserDataParticleKey.CG_ENG_MSG_CNTS_C_SUPERV,
              msg_cnts_regex, lambda match : int(match.group(5)), int)
        p.add(CgStcEngStcParserDataParticleKey.CG_ENG_MSG_CNTS_C_TELEM,
              msg_cnts_regex, lambda match : int(match.group(6)), int)
        # err cnts
        p.add(CgStcEngStcParserDataParticleKey.CG_ENG_ERR_C_GPS,
              self.gen_err_cnts('C_GPS'), lambda match : int(match.group(1)), int)
        p.add(CgStcEngStcParserDataParticleKey.CG_ENG_ERR_C_PPS,
              self.gen_err_cnts('C_PPS'), lambda match : int(match.group(1)), int)
        p.add(CgStcEngStcParserDataParticleKey.CG_ENG_ERR_C_CTL,
              self.gen_err_cnts('C_CTL'), lambda match : int(match.group(1)), int)
        p.add(CgStcEngStcParserDataParticleKey.CG_ENG_ERR_C_STATUS,
              self.gen_err_cnts('C_STATUS'), lambda match : int(match.group(1)), int)
        p.add(CgStcEngStcParserDataParticleKey.CG_ENG_ERR_SUPERV,
              self.gen_err_cnts('SUPERV'), lambda match : int(match.group(1)), int)
        p.add(CgStcEngStcParserDataParticleKey.CG_ENG_ERR_C_POWER_SYS,
              self.gen_err_cnts('C_POWER_SYS'), lambda match : int(match.group(1)), int)
        p.add(CgStcEngStcParserDataParticleKey.CG_ENG_ERR_C_TELEM_SYS,
              self.gen_err_cnts('C_TELEM_SYS'), lambda match : int(match.group(1)), int)
        p.add(CgStcEngStcParserDataParticleKey.CG_ENG_ERR_C_IRID,
              self.gen_err_cnts('C_IRID'), lambda match : int(match.group(1)), int)
        p.add(CgStcEngStcParserDataParticleKey.CG_ENG_ERR_C_IMM,
              self.gen_err_cnts('C_IMM'), lambda match : int(match.group(1)), int)
        p.add(CgStcEngStcParserDataParticleKey.CG_ENG_ERR_CPM1,
              self.gen_err_cnts('CPM1'), lambda match : int(match.group(1)), int)
        p.add(CgStcEngStcParserDataParticleKey.CG_ENG_ERR_D_CTL,
              self.gen_err_cnts('D_CTL'), lambda match : int(match.group(1)), int)
        p.add(CgStcEngStcParserDataParticleKey.CG_ENG_ERR_D_STATUS,
              self.gen_err_cnts('D_STATUS'), lambda match : int(match.group(1)), int)
        p.add(CgStcEngStcParserDataParticleKey.CG_ENG_ERR_DLOG_MGR,
              self.gen_err_cnts('DLOG_MGR'), lambda match : int(match.group(1)), int)
        p.add(CgStcEngStcParserDataParticleKey.CG_ENG_ERR_DLOGP1,
              self.gen_err_cnts('DLOGP1'), lambda match : int(match.group(1)), int)
        p.add(CgStcEngStcParserDataParticleKey.CG_ENG_ERR_DLOGP2,
              self.gen_err_cnts('DLOGP2'), lambda match : int(match.group(1)), int)
        p.add(CgStcEngStcParserDataParticleKey.CG_ENG_ERR_DLOGP3,
              self.gen_err_cnts('DLOGP3'), lambda match : int(match.group(1)), int)
        p.add(CgStcEngStcParserDataParticleKey.CG_ENG_ERR_DLOGP4,
              self.gen_err_cnts('DLOGP4'), lambda match : int(match.group(1)), int)
        p.add(CgStcEngStcParserDataParticleKey.CG_ENG_ERR_DLOGP5,
              self.gen_err_cnts('DLOGP5'), lambda match : int(match.group(1)), int)
        p.add(CgStcEngStcParserDataParticleKey.CG_ENG_ERR_DLOGP6,
              self.gen_err_cnts('DLOGP6'), lambda match : int(match.group(1)), int)
        p.add(CgStcEngStcParserDataParticleKey.CG_ENG_ERR_DLOGP7,
              self.gen_err_cnts('DLOGP7'), lambda match : int(match.group(1)), int)
        p.add(CgStcEngStcParserDataParticleKey.CG_ENG_ERR_DLOGP8,
              self.gen_err_cnts('DLOGP8'), lambda match : int(match.group(1)), int)
        p.add(CgStcEngStcParserDataParticleKey.CG_ENG_ERR_RCMD,
              self.gen_err_cnts('RCMD'), lambda match : int(match.group(1)), int)
        p.add(CgStcEngStcParserDataParticleKey.CG_ENG_ERR_BCMD,
              self.gen_err_cnts('BCMD'), lambda match : int(match.group(1)), int)
        # errmsg
        p.add(CgStcEngStcParserDataParticleKey.CG_ENG_ERRMSG_C_GPS,
              self.gen_errmsg('C_GPS'), lambda match : match.group(1), str)
        p.add(CgStcEngStcParserDataParticleKey.CG_ENG_ERRMSG_C_PPS,
              self.gen_errmsg('C_PPS'), lambda match : match.group(1), str)
        p.add(CgStcEngStcParserDataParticleKey.CG_ENG_ERRMSG_C_CTL,
              self.gen_errmsg('C_CTL'), lambda match : match.group(1), str)
        p.add(CgStcEngStcParserDataParticleKey.CG_ENG_ERRMSG_C_STATUS,
              self.gen_errmsg('C_STATUS'), lambda match : match.group(1), str)
        p.add(CgStcEngStcParserDataParticleKey.CG_ENG_ERRMSG_SUPERV,
              self.gen_errmsg('SUPERV'), lambda match : match.group(1), str)
        p.add(CgStcEngStcParserDataParticleKey.CG_ENG_ERRMSG_C_POWER_SYS,
              self.gen_errmsg('C_POWER_SYS'), lambda match : match.group(1), str)
        p.add(CgStcEngStcParserDataParticleKey.CG_ENG_ERRMSG_C_TELEM_SYS,
              self.gen_errmsg('C_TELEM_SYS'), lambda match : match.group(1), str)
        p.add(CgStcEngStcParserDataParticleKey.CG_ENG_ERRMSG_C_IRID,
              self.gen_errmsg('C_IRID'), lambda match : match.group(1), str)
        p.add(CgStcEngStcParserDataParticleKey.CG_ENG_ERRMSG_C_IMM,
              self.gen_errmsg('C_IMM'), lambda match : match.group(1), str)
        p.add(CgStcEngStcParserDataParticleKey.CG_ENG_ERRMSG_CPM1,
              self.gen_errmsg('CPM1'), lambda match : match.group(1), str)
        p.add(CgStcEngStcParserDataParticleKey.CG_ENG_ERRMSG_D_CTL,
              self.gen_errmsg('D_CTL'), lambda match : match.group(1), str)
        p.add(CgStcEngStcParserDataParticleKey.CG_ENG_ERRMSG_D_STATUS,
              self.gen_errmsg('D_STATUS'), lambda match : match.group(1), str)
        p.add(CgStcEngStcParserDataParticleKey.CG_ENG_ERRMSG_DLOG_MGR,
              self.gen_errmsg('DLOG_MGR'), lambda match : match.group(1), str)
        p.add(CgStcEngStcParserDataParticleKey.CG_ENG_ERRMSG_DLOGP1,
              self.gen_errmsg('DLOGP1'), lambda match : match.group(1), str)
        p.add(CgStcEngStcParserDataParticleKey.CG_ENG_ERRMSG_DLOGP2,
              self.gen_errmsg('DLOGP2'), lambda match : match.group(1), str)
        p.add(CgStcEngStcParserDataParticleKey.CG_ENG_ERRMSG_DLOGP3,
              self.gen_errmsg('DLOGP3'), lambda match : match.group(1), str)
        p.add(CgStcEngStcParserDataParticleKey.CG_ENG_ERRMSG_DLOGP4,
              self.gen_errmsg('DLOGP4'), lambda match : match.group(1), str)
        p.add(CgStcEngStcParserDataParticleKey.CG_ENG_ERRMSG_DLOGP5,
              self.gen_errmsg('DLOGP5'), lambda match : match.group(1), str)
        p.add(CgStcEngStcParserDataParticleKey.CG_ENG_ERRMSG_DLOGP6,
              self.gen_errmsg('DLOGP6'), lambda match : match.group(1), str)
        p.add(CgStcEngStcParserDataParticleKey.CG_ENG_ERRMSG_DLOGP7,
              self.gen_errmsg('DLOGP7'), lambda match : match.group(1), str)
        p.add(CgStcEngStcParserDataParticleKey.CG_ENG_ERRMSG_DLOGP8,
              self.gen_errmsg('DLOGP8'), lambda match : match.group(1), str)
        p.add(CgStcEngStcParserDataParticleKey.CG_ENG_ERRMSG_RCMD,
              self.gen_errmsg('RCMD'), lambda match : match.group(1), str)
        p.add(CgStcEngStcParserDataParticleKey.CG_ENG_ERRMSG_BCMD,
              self.gen_errmsg('BCMD'), lambda match : match.group(1), str)
        # cpu
        p.add(CgStcEngStcParserDataParticleKey.CG_ENG_CPU_UPTIME,
              r'CPU\.uptime=(.+?)(\r\n?|\n)',
              lambda match : match.group(1),
              str)
        p.add(CgStcEngStcParserDataParticleKey.CG_ENG_CPU_LOAD1,
              r'CPU\.load=(-?\d+\.\d+) (-?\d+\.\d+) (-?\d+\.\d+)(\r\n?|\n)',
              lambda match: float(match.group(1)),
              float)
        p.add(CgStcEngStcParserDataParticleKey.CG_ENG_CPU_LOAD5,
              r'CPU\.load=(-?\d+\.\d+) (-?\d+\.\d+) (-?\d+\.\d+)(\r\n?|\n)',
              lambda match: float(match.group(2)),
              float)
        p.add(CgStcEngStcParserDataParticleKey.CG_ENG_CPU_LOAD15,
              r'CPU\.load=(-?\d+\.\d+) (-?\d+\.\d+) (-?\d+\.\d+)(\r\n?|\n)',
              lambda match: float(match.group(3)),
              float)
        # memory
        p.add(CgStcEngStcParserDataParticleKey.CG_ENG_MEMORY_RAM,
              'CPU\.memory=Ram: (\d+)k  Free: (.+)k',
              lambda match: int(match.group(1)),
              int)
        p.add(CgStcEngStcParserDataParticleKey.CG_ENG_MEMORY_FREE,
              'CPU\.memory=Ram: (\d+)k  Free: (.+)k',
              lambda match: int(match.group(2)),
              int)           
        p.add(CgStcEngStcParserDataParticleKey.CG_ENG_NPROC,
              'CPU\.nproc=(\d+)(\r\n?|\n)',
              lambda match: int(match.group(1)),
              int)
        # mpic
        p.add(CgStcEngStcParserDataParticleKey.CG_ENG_MPIC_EFLAG,
              'MPIC\.eflag=(.+?)(\r\n?|\n)',
              lambda match: int('0x'+match.group(1),0),
              int)
        p.add(CgStcEngStcParserDataParticleKey.CG_ENG_MPIC_MAIN_V,
              'MPIC\.main_v=(-?\d+\.\d+)(\r\n?|\n)',
              lambda match: float(match.group(1)),
              float)
        p.add(CgStcEngStcParserDataParticleKey.CG_ENG_MPIC_MAIN_C,
              'MPIC\.main_c=(-?\d+\.\d+)(\r\n?|\n)',
              lambda match: float(match.group(1)),
              float)
        p.add(CgStcEngStcParserDataParticleKey.CG_ENG_MPIC_BAT_V,
              'MPIC\.bbat_v=(-?\d+\.\d+)(\r\n?|\n)',
              lambda match: float(match.group(1)),
              float)
        p.add(CgStcEngStcParserDataParticleKey.CG_ENG_MPIC_BAT_C,
              'MPIC\.bbat_c=(-?\d+\.\d+)(\r\n?|\n)',
              lambda match: float(match.group(1)),
              float)
        p.add(CgStcEngStcParserDataParticleKey.CG_ENG_MPIC_TEMP1,
              r'MPIC\.temp=(-?\d+\.\d+) (-?\d+\.\d+)(\r\n?|\n)',
              lambda match: float(match.group(1)),
              float)
        p.add(CgStcEngStcParserDataParticleKey.CG_ENG_MPIC_TEMP2,
              r'MPIC\.temp=(-?\d+\.\d+) (-?\d+\.\d+)(\r\n?|\n)',
              lambda match: float(match.group(2)),
              float)
        p.add(CgStcEngStcParserDataParticleKey.CG_ENG_MPIC_HUMID,
              r'MPIC\.humid=(-?\d+\.\d+)(\r\n?|\n)',
              lambda match: float(match.group(1)),
              float)
        p.add(CgStcEngStcParserDataParticleKey.CG_ENG_MPIC_PRESS,
              r'MPIC\.press=(-?\d+\.\d+)(\r\n?|\n)',
              lambda match: float(match.group(1)),
              float)
        p.add(CgStcEngStcParserDataParticleKey.CG_ENG_MPIC_GF_ENA,
              r'MPIC\.gf_ena=(.+?)(\r\n?|\n)',
              lambda match: int('0x'+match.group(1),0),
              int)
        #gflt
        gflt_regex = r'MPIC\.gflt=(-?\d+\.\d+) (-?\d+\.\d+) (-?\d+\.\d+) (-?\d+\.\d+)'
        p.add(CgStcEngStcParserDataParticleKey.CG_ENG_MPIC_GFLT1,
              gflt_regex, lambda match: float(match.group(1)), float)
        p.add(CgStcEngStcParserDataParticleKey.CG_ENG_MPIC_GFLT2,
              gflt_regex, lambda match: float(match.group(2)), float)
        p.add(CgStcEngStcParserDataParticleKey.CG_ENG_MPIC_GFLT3,
              gflt_regex, lambda match: float(match.group(3)), float)
        p.add(CgStcEngStcParserDataParticleKey.CG_ENG_MPIC_GFLT4,
              gflt_regex, lambda match: float(match.group(4)), float)
        p.add(CgStcEngStcParserDataParticleKey.CG_ENG_MPIC_LD_ENA,
              r'MPIC\.ld_ena=(.+?)(\r\n?|\n)',
              lambda match: int('0x'+match.group(1),0),
              int)
        p.add(CgStcEngStcParserDataParticleKey.CG_ENG_MPIC_LDET1,
              r'MPIC\.ldet=(-?\d+\.\d+) (-?\d+\.\d+)(\r\n?|\n)',
              lambda match: float(match.group(1)),
              float)
        p.add(CgStcEngStcParserDataParticleKey.CG_ENG_MPIC_LDET2,
              r'MPIC\.ldet=(-?\d+\.\d+) (-?\d+\.\d+)(\r\n?|\n)',
              lambda match: float(match.group(2)),
              float)
        # mpic hotel
        mpic_hotel_regex = r'MPIC\.hotel=wake (\d+) ir (\d+) (-?\d+\.\d+) (-?\d+\.\d+) (\d+) ' \
                'fwwf (\d+) (-?\d+\.\d+) (-?\d+\.\d+) (\d+) gps (\d+) sbd (\d+) (\d+) pps (\d+) ' \
                'dcl (\w\w) esw (\w) dsl (\w)'
        p.add(CgStcEngStcParserDataParticleKey.CG_ENG_MPIC_WSRC,
              mpic_hotel_regex, lambda match: int(match.group(1)), int)
        p.add(CgStcEngStcParserDataParticleKey.CG_ENG_MPIC_IRID, 
              mpic_hotel_regex, lambda match: int(match.group(2)), int)
        p.add(CgStcEngStcParserDataParticleKey.CG_ENG_MPIC_IRID_V,
              mpic_hotel_regex, lambda match: float(match.group(3)), float)
        p.add(CgStcEngStcParserDataParticleKey.CG_ENG_MPIC_IRID_C,
              mpic_hotel_regex, lambda match: float(match.group(4)), float)
        p.add(CgStcEngStcParserDataParticleKey.CG_ENG_MPIC_IRID_E,
              mpic_hotel_regex, lambda match: int(match.group(5)), int)
        p.add(CgStcEngStcParserDataParticleKey.CG_ENG_MPIC_FW_WIFI,
              mpic_hotel_regex, lambda match: int(match.group(6)), int)
        p.add(CgStcEngStcParserDataParticleKey.CG_ENG_MPIC_FW_WIFI_V,
              mpic_hotel_regex,  lambda match: float(match.group(7)), float)
        p.add(CgStcEngStcParserDataParticleKey.CG_ENG_MPIC_FW_WIFI_C,
              mpic_hotel_regex, lambda match: float(match.group(8)), float)
        p.add(CgStcEngStcParserDataParticleKey.CG_ENG_MPIC_FW_WIFI_E,
              mpic_hotel_regex, lambda match: int(match.group(9)), int)
        p.add(CgStcEngStcParserDataParticleKey.CG_ENG_MPIC_GPS,
              mpic_hotel_regex, lambda match: int(match.group(10)), int)
        p.add(CgStcEngStcParserDataParticleKey.CG_ENG_MPIC_SBD,
              mpic_hotel_regex, lambda match: int(match.group(11)), int)
        p.add(CgStcEngStcParserDataParticleKey.CG_ENG_MPIC_SBD_CE_MSG,
              mpic_hotel_regex, lambda match: int(match.group(12)), int)
        p.add(CgStcEngStcParserDataParticleKey.CG_ENG_MPIC_PPS,
              mpic_hotel_regex, lambda match: int(match.group(13)), int)
        p.add(CgStcEngStcParserDataParticleKey.CG_ENG_MPIC_DCL,
              mpic_hotel_regex, lambda match: int(match.group(14)), int)
        p.add(CgStcEngStcParserDataParticleKey.CG_ENG_MPIC_ESW,
              mpic_hotel_regex, lambda match: int(match.group(15)), int)
        p.add(CgStcEngStcParserDataParticleKey.CG_ENG_MPIC_DSL,
              mpic_hotel_regex, lambda match: int(match.group(16)), int)
        
        p.add(CgStcEngStcParserDataParticleKey.CG_ENG_MPIC_HBEAT_ENABLE,
              r'MPIC\.cpm_hb=enable (\d+) dtime (\d+) threshold (\d+)',
              lambda match: int(match.group(1)),
              int)
        p.add(CgStcEngStcParserDataParticleKey.CG_ENG_MPIC_HBEAT_DTIME,
              r'MPIC\.cpm_hb=enable (\d+) dtime (\d+) threshold (\d+)',
              lambda match: int(match.group(2)),
              int)
        p.add(CgStcEngStcParserDataParticleKey.CG_ENG_MPIC_HBEAT_THRESHOLD,
              r'MPIC\.cpm_hb=enable (\d+) dtime (\d+) threshold (\d+)',
              lambda match: int(match.group(3)),
              int)
        p.add(CgStcEngStcParserDataParticleKey.CG_ENG_MPIC_WAKE_CPM,
              r'MPIC\.wake_cpm=wtc (-?\d+\.\d+) wpc (\d+)(\r\n?|\n)',
              lambda match: float(match.group(1)),
              float)
        p.add(CgStcEngStcParserDataParticleKey.CG_ENG_MPIC_WPC,
              r'MPIC\.wake_cpm=wtc (\d+\.\d+) wpc (\d+)(\r\n?|\n)',
              lambda match: int(match.group(2)),
              int)
        p.add(CgStcEngStcParserDataParticleKey.CG_ENG_MPIC_EFLAG2,
              r'MPIC\.stc_eflag2=(.+?)(\r\n?|\n)',
              lambda match: int('0x'+match.group(1),0),
              int)
        p.add(CgStcEngStcParserDataParticleKey.CG_ENG_MPIC_LAST_UPDATE,
              r'MPIC\.last_update=(-?\d+\.\d+)(\r\n?|\n)',
              lambda match: float(match.group(1)),
              float)
        # gps
        p.add(CgStcEngStcParserDataParticleKey.CG_ENG_GPS_MSG_DATE,
              r'GPS\.timestamp=(\d{4}/\d{2}/\d{2}) (\d{2}:\d{2}:\d{2}\.\d{3})',
              lambda match: match.group(1),
              str)
        p.add(CgStcEngStcParserDataParticleKey.CG_ENG_GPS_MSG_TIME,
              r'GPS\.timestamp=(\d{4}/\d{2}/\d{2}) (\d{2}:\d{2}:\d{2}\.\d{3})',
              lambda match: match.group(2),
              str)
        p.add(CgStcEngStcParserDataParticleKey.CG_ENG_GPS_DATE,
              r'GPS.date=(.+?)(\r\n?|\n)',
              lambda match: int(match.group(1)),
              int)
        p.add(CgStcEngStcParserDataParticleKey.CG_ENG_GPS_TIME,
              r'GPS.time=(.+?)(\r\n?|\n)',
              lambda match: int(match.group(1)),
              int)
        p.add(CgStcEngStcParserDataParticleKey.CG_ENG_GPS_LATSTR,
              r'GPS.lat_str=(.+?)(\r\n?|\n)',
              lambda match: match.group(1),
              str)
        p.add(CgStcEngStcParserDataParticleKey.CG_ENG_GPS_LONSTR,
              r'GPS.lon_str=(.+?)(\r\n?|\n)',
              lambda match: match.group(1),
              str)
        p.add(CgStcEngStcParserDataParticleKey.CG_ENG_GPS_LAT,
              r'GPS.lat=(-?\d+\.\d+)(\r\n?|\n)',
              lambda match: float(match.group(1)),
              float)
        p.add(CgStcEngStcParserDataParticleKey.CG_ENG_GPS_LON,
              r'GPS.lon=(-?\d+\.\d+)(\r\n?|\n)',
              lambda match: float(match.group(1)),
              float)
        p.add(CgStcEngStcParserDataParticleKey.CG_ENG_GPS_SPD,
              r'GPS.spd=(-?\d+\.\d+)(\r\n?|\n)',
              lambda match: float(match.group(1)),
              float)
        p.add(CgStcEngStcParserDataParticleKey.CG_ENG_GPS_COG,
              r'GPS\.cog=(-?\d+\.\d+)(\r\n?|\n)',
              lambda match: float(match.group(1)),
              float)
        p.add(CgStcEngStcParserDataParticleKey.CG_ENG_GPS_FIX,
              r'GPS\.fix_q=(\d+)(\r\n?|\n)',
              lambda match: int(match.group(1)),
              int)
        p.add(CgStcEngStcParserDataParticleKey.CG_ENG_GPS_NSAT,
              r'GPS\.nsat=(\d+)(\r\n?|\n)',
              lambda match: int(match.group(1)),
              int)
        p.add(CgStcEngStcParserDataParticleKey.CG_ENG_GPS_HDOP,
              r'GPS\.hdop=(-?\d+\.\d+)(\r\n?|\n)',
              lambda match: float(match.group(1)),
              float)
        p.add(CgStcEngStcParserDataParticleKey.CG_ENG_GPS_ALT,
              r'GPS\.alt=(-?\d+\.\d+)(\r\n?|\n)',
              lambda match: float(match.group(1)),
              float)
        p.add(CgStcEngStcParserDataParticleKey.CG_ENG_GPS_LAST_UPDATE,
              r'GPS\.last_update=(-?\d+\.\d+)(\r\n?|\n)',
              lambda match: float(match.group(1)),
              float)
        # ntp
        p.add(CgStcEngStcParserDataParticleKey.CG_ENG_NTP_REFID,
              r'NTP\.refid=(.+?)(\r\n?|\n)',
              lambda match: match.group(1),
              str)
        p.add(CgStcEngStcParserDataParticleKey.CG_ENG_NTP_OFFSET,
              r'NTP\.offset=(-?\d+\.\d+)(\r\n?|\n)',
              lambda match: float(match.group(1)),
              float)
        p.add(CgStcEngStcParserDataParticleKey.CG_ENG_NTP_JITTER,
              r'NTP\.jitter=(-?\d+\.\d+)(\r\n?|\n)',
              lambda match: float(match.group(1)),
              float)
        # pps status
        pps_regex = r'PPS\.status=C_PPS: NMEA_Lock: (.+)  Delta: (.+) DeltaMin: ' \
                     '(.+) DeltaMax: (.+) BadPulses: (.+) TS: (.+?)(\r\n?|\n)'
        p.add(CgStcEngStcParserDataParticleKey.CG_ENG_PPS_LOCK,
              pps_regex, lambda match: match.group(1), str)
        p.add(CgStcEngStcParserDataParticleKey.CG_ENG_PPS_DELTA,
              pps_regex, lambda match: int(match.group(2)), int)
        p.add(CgStcEngStcParserDataParticleKey.CG_ENG_PPS_DELTAMIN,
              pps_regex, lambda match: int(match.group(3)), int)
        p.add(CgStcEngStcParserDataParticleKey.CG_ENG_PPS_DELTAMAX,
              pps_regex, lambda match: int(match.group(4)), int)
        p.add(CgStcEngStcParserDataParticleKey.CG_ENG_PPS_BAD_PULSE,
              pps_regex, lambda match: int(match.group(5)), int)
        p.add(CgStcEngStcParserDataParticleKey.CG_ENG_PPS_TIMESTAMP,
              pps_regex, lambda match: match.group(6), str)

        p.add(CgStcEngStcParserDataParticleKey.CG_ENG_PPS_LAST_UPDATE,
              r'PPS\.last_update=(-?\d+\.\d+)(\r\n?|\n)',
              lambda match: float(match.group(1)),
              float)
        p.add(CgStcEngStcParserDataParticleKey.CG_ENG_LOADSHED_STATUS,
              r'LoadShed\.status=(.+?)(\r\n?|\n)',
              lambda match: match.group(1),
              str)
        p.add(CgStcEngStcParserDataParticleKey.CG_ENG_LOADSHED_LAST_UPDATE,
              r'LoadShed\.last_update=(-?\d+\.\d+)(\r\n?|\n)',
              lambda match: float(match.group(1)),
              float)
        p.add(CgStcEngStcParserDataParticleKey.CG_ENG_SBC_ETH0,
              r'sbc\.eth0=(\d)(\r\n?|\n)',
              lambda match: int(match.group(1)),
              int)         
        p.add(CgStcEngStcParserDataParticleKey.CG_ENG_SBC_ETH1,
              r'sbc\.eth1=(\d)(\r\n?|\n)',
              lambda match: int(match.group(1)),
              int)
        p.add(CgStcEngStcParserDataParticleKey.CG_ENG_SBC_LED0,
              r'sbc\.led0=(\d)(\r\n?|\n)',
              lambda match: int(match.group(1)),
              int)
        p.add(CgStcEngStcParserDataParticleKey.CG_ENG_SBC_LED1,
              r'sbc\.led1=(\d)(\r\n?|\n)',
              lambda match: int(match.group(1)),
              int)
        p.add(CgStcEngStcParserDataParticleKey.CG_ENG_SBC_LED2,
              r'sbc\.led2=(\d)(\r\n?|\n)',
              lambda match: int(match.group(1)),
              int)
        p.add(CgStcEngStcParserDataParticleKey.CG_ENG_SBC_GPO0,
              r'sbc\.gpo0=(\d)(\r\n?|\n)',
              lambda match: int(match.group(1)),
              int)
        p.add(CgStcEngStcParserDataParticleKey.CG_ENG_SBC_GPO1,
              r'sbc\.gpo1=(\d)(\r\n?|\n)',
              lambda match: int(match.group(1)),
              int)
        p.add(CgStcEngStcParserDataParticleKey.CG_ENG_SBC_GPO2,
              r'sbc\.gpo2=(\d)(\r\n?|\n)',
              lambda match: int(match.group(1)),
              int)
        p.add(CgStcEngStcParserDataParticleKey.CG_ENG_SBC_GPO3,
              r'sbc\.gpo3=(\d)(\r\n?|\n)',
              lambda match: int(match.group(1)),
              int)
        p.add(CgStcEngStcParserDataParticleKey.CG_ENG_SBC_GPO4,
              r'sbc\.gpo4=(\d)(\r\n?|\n)',
              lambda match: int(match.group(1)),
              int)
        p.add(CgStcEngStcParserDataParticleKey.CG_ENG_SBC_GPIO0,
              r'sbc\.gpi0=(\d)(\r\n?|\n)',
              lambda match: int(match.group(1)),
              int)
        p.add(CgStcEngStcParserDataParticleKey.CG_ENG_SBC_GPIO1,
              r'sbc\.gpi1=(\d)(\r\n?|\n)',
              lambda match: int(match.group(1)),
              int)
        p.add(CgStcEngStcParserDataParticleKey.CG_ENG_SBC_GPIO2,
              r'sbc\.gpi2=(\d)(\r\n?|\n)',
              lambda match: int(match.group(1)),
              int)
        p.add(CgStcEngStcParserDataParticleKey.CG_ENG_SBC_GPIO3,
              r'sbc\.gpi3=(\d)(\r\n?|\n)',
              lambda match: int(match.group(1)),
              int)
        p.add(CgStcEngStcParserDataParticleKey.CG_ENG_SBC_GPIO4,
              r'sbc\.gpi4=(\d)(\r\n?|\n)',
              lambda match: int(match.group(1)),
              int)
        p.add(CgStcEngStcParserDataParticleKey.CG_ENG_SBC_GPIO5,
              r'sbc\.gpi5=(\d)(\r\n?|\n)',
              lambda match: int(match.group(1)),
              int)
        p.add(CgStcEngStcParserDataParticleKey.CG_ENG_SBC_FB1,
              r'sbc\.fb1=(\d)(\r\n?|\n)',
              lambda match: int(match.group(1)),
              int)
        p.add(CgStcEngStcParserDataParticleKey.CG_ENG_SBC_FB2,
              r'sbc\.fb2=(\d)(\r\n?|\n)',
              lambda match: int(match.group(1)),
              int)  
        p.add(CgStcEngStcParserDataParticleKey.CG_ENG_SBC_CE_LED,
              r'sbc\.ce_led=(\d)(\r\n?|\n)',
              lambda match: int(match.group(1)),
              int)
        p.add(CgStcEngStcParserDataParticleKey.CG_ENG_SBC_WDT,
              r'sbc\.wdt=(0x.+)(\r\n?|\n)',
              lambda match: int(match.group(1),0),
              int)
        p.add(CgStcEngStcParserDataParticleKey.CG_ENG_SBC_BID,
              r'sbc\.bid=(0x.+)(\r\n?|\n)',
              lambda match: int(match.group(1),0),
              int)
        p.add(CgStcEngStcParserDataParticleKey.CG_ENG_SBC_BSTR,
              r'sbc\.bstr=(0x.+)(\r\n?|\n)',
              lambda match: int(match.group(1),0),
              int)
        # msg cnts d
        msg_cnts_d_regex = r'STATUS.msg_cnts=D_GPS=(\d+), NTP=(\d+), D_PPS=(\d+), ' \
                            'SUPERV=(\d+), DLOG_MGR=(\d+)'
        p.add(CgStcEngStcParserDataParticleKey.CG_ENG_MSG_CNTS_D_GPS,
              msg_cnts_d_regex,
              lambda match: int(match.group(1)),
              int)
        p.add(CgStcEngStcParserDataParticleKey.CG_ENG_MSG_CNTS_D_NTP,
              msg_cnts_d_regex,
              lambda match: int(match.group(2)),
              int)
        p.add(CgStcEngStcParserDataParticleKey.CG_ENG_MSG_CNTS_D_PPS,
              msg_cnts_d_regex,
              lambda match: int(match.group(3)),
              int)
        p.add(CgStcEngStcParserDataParticleKey.CG_ENG_MSG_CNTS_D_SUPERV,
              msg_cnts_d_regex,
              lambda match: int(match.group(4)),
              int)
        p.add(CgStcEngStcParserDataParticleKey.CG_ENG_MSG_CNTS_D_DLOG_NGR,
              msg_cnts_d_regex,
              lambda match: int(match.group(5)),
              int)
        # dclp1
        dclp1_regex = self.gen_dclp_regex(1)
        p.add(CgStcEngStcParserDataParticleKey.CG_ENG_DCLP1_ENABLE,
              dclp1_regex, lambda match: int(match.group(1)), int)
        p.add(CgStcEngStcParserDataParticleKey.CG_ENG_DCLP1_VOLT,
              dclp1_regex, lambda match: float(match.group(2)), float)
        p.add(CgStcEngStcParserDataParticleKey.CG_ENG_DCLP1_CURRENT,
              dclp1_regex, lambda match: float(match.group(3)), float)
        p.add(CgStcEngStcParserDataParticleKey.CG_ENG_DCLP1_EFLAG,
              dclp1_regex, lambda match: int(match.group(4)), int)
        p.add(CgStcEngStcParserDataParticleKey.CG_ENG_DCLP1_VSEL,
              dclp1_regex, lambda match: int(match.group(5)), int)
        p.add(CgStcEngStcParserDataParticleKey.CG_ENG_DCLP1_CLIM,
              dclp1_regex, lambda match: int(match.group(6)), int)
        p.add(CgStcEngStcParserDataParticleKey.CG_ENG_DCLP1_PROT,
              dclp1_regex, lambda match: int(match.group(7)), int)
        # dclp2
        dclp2_regex = self.gen_dclp_regex(2)
        p.add(CgStcEngStcParserDataParticleKey.CG_ENG_DCLP2_ENABLE,
              dclp2_regex, lambda match: int(match.group(1)), int)
        p.add(CgStcEngStcParserDataParticleKey.CG_ENG_DCLP2_VOLT,
              dclp2_regex, lambda match: float(match.group(2)), float)
        p.add(CgStcEngStcParserDataParticleKey.CG_ENG_DCLP2_CURRENT,
              dclp2_regex, lambda match: float(match.group(3)), float)
        p.add(CgStcEngStcParserDataParticleKey.CG_ENG_DCLP2_EFLAG,
              dclp2_regex, lambda match: int(match.group(4)), int)
        p.add(CgStcEngStcParserDataParticleKey.CG_ENG_DCLP2_VSEL,
              dclp2_regex, lambda match: int(match.group(5)), int)
        p.add(CgStcEngStcParserDataParticleKey.CG_ENG_DCLP2_CLIM,
              dclp2_regex, lambda match: int(match.group(6)), int)
        p.add(CgStcEngStcParserDataParticleKey.CG_ENG_DCLP2_PROT,
              dclp2_regex, lambda match: int(match.group(7)), int)
        # dclp3
        dclp3_regex = self.gen_dclp_regex(3)
        p.add(CgStcEngStcParserDataParticleKey.CG_ENG_DCLP3_ENABLE,
              dclp3_regex, lambda match: int(match.group(1)), int)
        p.add(CgStcEngStcParserDataParticleKey.CG_ENG_DCLP3_VOLT,
              dclp3_regex, lambda match: float(match.group(2)), float)
        p.add(CgStcEngStcParserDataParticleKey.CG_ENG_DCLP3_CURRENT,
              dclp3_regex, lambda match: float(match.group(3)), float)
        p.add(CgStcEngStcParserDataParticleKey.CG_ENG_DCLP3_EFLAG,
              dclp3_regex, lambda match: int(match.group(4)), int)
        p.add(CgStcEngStcParserDataParticleKey.CG_ENG_DCLP3_VSEL,
              dclp3_regex, lambda match: int(match.group(5)), int)
        p.add(CgStcEngStcParserDataParticleKey.CG_ENG_DCLP3_CLIM,
              dclp3_regex, lambda match: int(match.group(6)), int)
        p.add(CgStcEngStcParserDataParticleKey.CG_ENG_DCLP3_PROT,
              dclp3_regex, lambda match: int(match.group(7)), int)
        # dclp4
        dclp4_regex = self.gen_dclp_regex(4)
        p.add(CgStcEngStcParserDataParticleKey.CG_ENG_DCLP4_ENABLE,
              dclp4_regex, lambda match: int(match.group(1)), int)
        p.add(CgStcEngStcParserDataParticleKey.CG_ENG_DCLP4_VOLT,
              dclp4_regex, lambda match: float(match.group(2)), float)
        p.add(CgStcEngStcParserDataParticleKey.CG_ENG_DCLP4_CURRENT,
              dclp4_regex, lambda match: float(match.group(3)), float)
        p.add(CgStcEngStcParserDataParticleKey.CG_ENG_DCLP4_EFLAG,
              dclp4_regex, lambda match: int(match.group(4)), int)
        p.add(CgStcEngStcParserDataParticleKey.CG_ENG_DCLP4_VSEL,
              dclp4_regex, lambda match: int(match.group(5)), int)
        p.add(CgStcEngStcParserDataParticleKey.CG_ENG_DCLP4_CLIM,
              dclp4_regex, lambda match: int(match.group(6)), int)
        p.add(CgStcEngStcParserDataParticleKey.CG_ENG_DCLP4_PROT,
              dclp4_regex, lambda match: int(match.group(7)), int)
        # dclp5
        dclp5_regex = self.gen_dclp_regex(5)
        p.add(CgStcEngStcParserDataParticleKey.CG_ENG_DCLP5_ENABLE,
              dclp5_regex, lambda match: int(match.group(1)), int)
        p.add(CgStcEngStcParserDataParticleKey.CG_ENG_DCLP5_VOLT,
              dclp5_regex, lambda match: float(match.group(2)), float)
        p.add(CgStcEngStcParserDataParticleKey.CG_ENG_DCLP5_CURRENT,
              dclp5_regex, lambda match: float(match.group(3)), float)
        p.add(CgStcEngStcParserDataParticleKey.CG_ENG_DCLP5_EFLAG,
              dclp5_regex, lambda match: int(match.group(4)), int)
        p.add(CgStcEngStcParserDataParticleKey.CG_ENG_DCLP5_VSEL,
              dclp5_regex, lambda match: int(match.group(5)), int)
        p.add(CgStcEngStcParserDataParticleKey.CG_ENG_DCLP5_CLIM,
              dclp5_regex, lambda match: int(match.group(6)), int)
        p.add(CgStcEngStcParserDataParticleKey.CG_ENG_DCLP5_PROT,
              dclp5_regex, lambda match: int(match.group(7)), int)
        # dclp6
        dclp6_regex = self.gen_dclp_regex(6)
        p.add(CgStcEngStcParserDataParticleKey.CG_ENG_DCLP6_ENABLE,
              dclp6_regex, lambda match: int(match.group(1)), int)
        p.add(CgStcEngStcParserDataParticleKey.CG_ENG_DCLP6_VOLT,
              dclp6_regex, lambda match: float(match.group(2)), float)
        p.add(CgStcEngStcParserDataParticleKey.CG_ENG_DCLP6_CURRENT,
              dclp6_regex, lambda match: float(match.group(3)), float)
        p.add(CgStcEngStcParserDataParticleKey.CG_ENG_DCLP6_EFLAG,
              dclp6_regex, lambda match: int(match.group(4)), int)
        p.add(CgStcEngStcParserDataParticleKey.CG_ENG_DCLP6_VSEL,
              dclp6_regex, lambda match: int(match.group(5)), int)
        p.add(CgStcEngStcParserDataParticleKey.CG_ENG_DCLP6_CLIM,
              dclp6_regex, lambda match: int(match.group(6)), int)
        p.add(CgStcEngStcParserDataParticleKey.CG_ENG_DCLP6_PROT,
              dclp6_regex, lambda match: int(match.group(7)), int)
        # dclp7
        dclp7_regex = self.gen_dclp_regex(7)
        p.add(CgStcEngStcParserDataParticleKey.CG_ENG_DCLP7_ENABLE,
              dclp7_regex, lambda match: int(match.group(1)), int)
        p.add(CgStcEngStcParserDataParticleKey.CG_ENG_DCLP7_VOLT,
              dclp7_regex, lambda match: float(match.group(2)), float)
        p.add(CgStcEngStcParserDataParticleKey.CG_ENG_DCLP7_CURRENT,
              dclp7_regex, lambda match: float(match.group(3)), float)
        p.add(CgStcEngStcParserDataParticleKey.CG_ENG_DCLP7_EFLAG,
              dclp7_regex, lambda match: int(match.group(4)), int)
        p.add(CgStcEngStcParserDataParticleKey.CG_ENG_DCLP7_VSEL,
              dclp7_regex, lambda match: int(match.group(5)), int)
        p.add(CgStcEngStcParserDataParticleKey.CG_ENG_DCLP7_CLIM,
              dclp7_regex, lambda match: int(match.group(6)), int)
        p.add(CgStcEngStcParserDataParticleKey.CG_ENG_DCLP7_PROT,
              dclp7_regex, lambda match: int(match.group(7)), int)
        # dclp8
        dclp8_regex = self.gen_dclp_regex(8)
        p.add(CgStcEngStcParserDataParticleKey.CG_ENG_DCLP8_ENABLE,
              dclp8_regex, lambda match: int(match.group(1)), int)
        p.add(CgStcEngStcParserDataParticleKey.CG_ENG_DCLP8_VOLT,
              dclp8_regex, lambda match: float(match.group(2)), float)
        p.add(CgStcEngStcParserDataParticleKey.CG_ENG_DCLP8_CURRENT,
              dclp8_regex, lambda match: float(match.group(3)), float)
        p.add(CgStcEngStcParserDataParticleKey.CG_ENG_DCLP8_EFLAG,
              dclp8_regex, lambda match: int(match.group(4)), int)
        p.add(CgStcEngStcParserDataParticleKey.CG_ENG_DCLP8_VSEL,
              dclp8_regex, lambda match: int(match.group(5)), int)
        p.add(CgStcEngStcParserDataParticleKey.CG_ENG_DCLP8_CLIM,
              dclp8_regex, lambda match: int(match.group(6)), int)
        p.add(CgStcEngStcParserDataParticleKey.CG_ENG_DCLP8_PROT,
              dclp8_regex, lambda match: int(match.group(7)), int)

        p.add(CgStcEngStcParserDataParticleKey.CG_ENG_DCL_PORT_STATUS,
              r'DCL.pstatus.last_update=(-?\d+\.\d+)',
              lambda match: float(match.group(1)),    
              float)

        DLOG_REGEX = r'(.+) (.+)  tx: (\d+)  rx: (\d+)  log: (\d+)  '\
                       'good: (\d+)  bad: (\d+)  bb: (\d+)  ld: '\
                       '([-\d]+)\s+(lc:\s+([-\d]+))?\s+lu:\s?([-\d.]+)(\r\n?|\n)'
        DLOG_LC_REGEX = r'(.+) (.+)  tx: (\d+)  rx: (\d+)  log: (\d+)  '\
                       'good: (\d+)  bad: (\d+)  bb: (\d+)  ld: '\
                       '([-\d]+)\s+(lc:\s+([-\d]+))\s+lu:\s?([-\d.]+)(\r\n?|\n)'
        #1
        dlogp1_regex = r'DLOGP1=' + DLOG_REGEX
        p.add(CgStcEngStcParserDataParticleKey.CG_ENG_PORT_DLOG1_NAME,
              dlogp1_regex,lambda match: match.group(1),str)
        p.add(CgStcEngStcParserDataParticleKey.CG_ENG_PORT_DLOG1_STATE,
              dlogp1_regex,lambda match: match.group(2),str)
        p.add(CgStcEngStcParserDataParticleKey.CG_ENG_PORT_DLOG1_TX,
              dlogp1_regex,lambda match: long(match.group(3)),long)
        p.add(CgStcEngStcParserDataParticleKey.CG_ENG_PORT_DLOG1_RX,
              dlogp1_regex,lambda match: long(match.group(4)),long)
        p.add(CgStcEngStcParserDataParticleKey.CG_ENG_PORT_DLOG1_LOG,
              dlogp1_regex,lambda match: long(match.group(5)),long)
        p.add(CgStcEngStcParserDataParticleKey.CG_ENG_PORT_DLOG1_GOOD,
              dlogp1_regex,lambda match: long(match.group(6)),long)
        p.add(CgStcEngStcParserDataParticleKey.CG_ENG_PORT_DLOG1_BAD,
              dlogp1_regex,lambda match: long(match.group(7)),long)
        p.add(CgStcEngStcParserDataParticleKey.CG_ENG_PORT_DLOG1_BB,
              dlogp1_regex,lambda match: long(match.group(8)),long)
        p.add(CgStcEngStcParserDataParticleKey.CG_ENG_PORT_DLOG1_LD,
              dlogp1_regex,lambda match: long(match.group(9)),long)
        p.add(CgStcEngStcParserDataParticleKey.CG_ENG_PORT_DLOG1_LC,
              r'DLOGP1='+DLOG_LC_REGEX,lambda match: float(match.group(11)),float)
        p.add(CgStcEngStcParserDataParticleKey.CG_ENG_PORT_DLOG1_LU,
              dlogp1_regex,lambda match: float(match.group(12)),float)
        #2
        dlogp2_regex = r'DLOGP2=' + DLOG_REGEX
        p.add(CgStcEngStcParserDataParticleKey.CG_ENG_PORT_DLOG2_NAME,
              dlogp2_regex,lambda match: match.group(1),str)
        p.add(CgStcEngStcParserDataParticleKey.CG_ENG_PORT_DLOG2_STATE,
              dlogp2_regex,lambda match: match.group(2),str)
        p.add(CgStcEngStcParserDataParticleKey.CG_ENG_PORT_DLOG2_TX,
              dlogp2_regex,lambda match: long(match.group(3)),long)
        p.add(CgStcEngStcParserDataParticleKey.CG_ENG_PORT_DLOG2_RX,
              dlogp2_regex,lambda match: long(match.group(4)),long)
        p.add(CgStcEngStcParserDataParticleKey.CG_ENG_PORT_DLOG2_LOG,
              dlogp2_regex,lambda match: long(match.group(5)),long)
        p.add(CgStcEngStcParserDataParticleKey.CG_ENG_PORT_DLOG2_GOOD,
              dlogp2_regex,lambda match: long(match.group(6)),long)
        p.add(CgStcEngStcParserDataParticleKey.CG_ENG_PORT_DLOG2_BAD,
              dlogp2_regex,lambda match: long(match.group(7)),long)
        p.add(CgStcEngStcParserDataParticleKey.CG_ENG_PORT_DLOG2_BB,
              dlogp2_regex,lambda match: long(match.group(8)),long)
        p.add(CgStcEngStcParserDataParticleKey.CG_ENG_PORT_DLOG2_LD,
              dlogp2_regex,lambda match: long(match.group(9)),long)
        p.add(CgStcEngStcParserDataParticleKey.CG_ENG_PORT_DLOG2_LC,
              r'DLOGP2='+DLOG_LC_REGEX,lambda match: float(match.group(11)),float)
        p.add(CgStcEngStcParserDataParticleKey.CG_ENG_PORT_DLOG2_LU,
              dlogp2_regex,lambda match: float(match.group(12)),float)
        #3
        dlogp3_regex = r'DLOGP3='+DLOG_REGEX
        p.add(CgStcEngStcParserDataParticleKey.CG_ENG_PORT_DLOG3_NAME,
              dlogp3_regex,lambda match: match.group(1),str)
        p.add(CgStcEngStcParserDataParticleKey.CG_ENG_PORT_DLOG3_STATE,
              dlogp3_regex,lambda match: match.group(2),str)
        p.add(CgStcEngStcParserDataParticleKey.CG_ENG_PORT_DLOG3_TX,
              dlogp3_regex,lambda match: long(match.group(3)),long)
        p.add(CgStcEngStcParserDataParticleKey.CG_ENG_PORT_DLOG3_RX,
              dlogp3_regex,lambda match: long(match.group(4)),long)
        p.add(CgStcEngStcParserDataParticleKey.CG_ENG_PORT_DLOG3_LOG,
              dlogp3_regex,lambda match: long(match.group(5)),long)
        p.add(CgStcEngStcParserDataParticleKey.CG_ENG_PORT_DLOG3_GOOD,
              dlogp3_regex,lambda match: long(match.group(6)),long)
        p.add(CgStcEngStcParserDataParticleKey.CG_ENG_PORT_DLOG3_BAD,
              dlogp3_regex,lambda match: long(match.group(7)),long)
        p.add(CgStcEngStcParserDataParticleKey.CG_ENG_PORT_DLOG3_BB,
              dlogp3_regex,lambda match: long(match.group(8)),long)
        p.add(CgStcEngStcParserDataParticleKey.CG_ENG_PORT_DLOG3_LD,
              dlogp3_regex,lambda match: long(match.group(9)),long)
        p.add(CgStcEngStcParserDataParticleKey.CG_ENG_PORT_DLOG3_LC,
              r'DLOGP3='+DLOG_LC_REGEX,lambda match: float(match.group(11)),float)
        p.add(CgStcEngStcParserDataParticleKey.CG_ENG_PORT_DLOG3_LU,
              dlogp3_regex,lambda match: float(match.group(12)),float)
        #4
        dlogp4_regex = r'DLOGP4='+DLOG_REGEX
        p.add(CgStcEngStcParserDataParticleKey.CG_ENG_PORT_DLOG4_NAME,
              dlogp4_regex,lambda match: match.group(1),str)
        p.add(CgStcEngStcParserDataParticleKey.CG_ENG_PORT_DLOG4_STATE,
              dlogp4_regex,lambda match: match.group(2),str)
        p.add(CgStcEngStcParserDataParticleKey.CG_ENG_PORT_DLOG4_TX,
              dlogp4_regex,lambda match: long(match.group(3)),long)
        p.add(CgStcEngStcParserDataParticleKey.CG_ENG_PORT_DLOG4_RX,
              dlogp4_regex,lambda match: long(match.group(4)),long)
        p.add(CgStcEngStcParserDataParticleKey.CG_ENG_PORT_DLOG4_LOG,
              dlogp4_regex,lambda match: long(match.group(5)),long)
        p.add(CgStcEngStcParserDataParticleKey.CG_ENG_PORT_DLOG4_GOOD,
              dlogp4_regex,lambda match: long(match.group(6)),long)
        p.add(CgStcEngStcParserDataParticleKey.CG_ENG_PORT_DLOG4_BAD,
              dlogp4_regex,lambda match: long(match.group(7)),long)
        p.add(CgStcEngStcParserDataParticleKey.CG_ENG_PORT_DLOG4_BB,
              dlogp4_regex,lambda match: long(match.group(8)),long)
        p.add(CgStcEngStcParserDataParticleKey.CG_ENG_PORT_DLOG4_LD,
              dlogp4_regex,lambda match: long(match.group(9)),long)
        p.add(CgStcEngStcParserDataParticleKey.CG_ENG_PORT_DLOG4_LC,
              r'DLOGP4='+DLOG_LC_REGEX,lambda match: float(match.group(11)),float)
        p.add(CgStcEngStcParserDataParticleKey.CG_ENG_PORT_DLOG4_LU,
              dlogp4_regex,lambda match: float(match.group(12)),float)
        #5
        dlogp5_regex = r'DLOGP5='+DLOG_REGEX
        p.add(CgStcEngStcParserDataParticleKey.CG_ENG_PORT_DLOG5_NAME,
              dlogp5_regex,lambda match: match.group(1),str)
        p.add(CgStcEngStcParserDataParticleKey.CG_ENG_PORT_DLOG5_STATE,
              dlogp5_regex,lambda match: match.group(2),str)
        p.add(CgStcEngStcParserDataParticleKey.CG_ENG_PORT_DLOG5_TX,
              dlogp5_regex,lambda match: long(match.group(3)),long)
        p.add(CgStcEngStcParserDataParticleKey.CG_ENG_PORT_DLOG5_RX,
              dlogp5_regex,lambda match: long(match.group(4)),long)
        p.add(CgStcEngStcParserDataParticleKey.CG_ENG_PORT_DLOG5_LOG,
              dlogp5_regex,lambda match: long(match.group(5)),long)
        p.add(CgStcEngStcParserDataParticleKey.CG_ENG_PORT_DLOG5_GOOD,
              dlogp5_regex,lambda match: long(match.group(6)),long)
        p.add(CgStcEngStcParserDataParticleKey.CG_ENG_PORT_DLOG5_BAD,
              dlogp5_regex,lambda match: long(match.group(7)),long)
        p.add(CgStcEngStcParserDataParticleKey.CG_ENG_PORT_DLOG5_BB,
              dlogp5_regex,lambda match: long(match.group(8)),long)
        p.add(CgStcEngStcParserDataParticleKey.CG_ENG_PORT_DLOG5_LD,
              dlogp5_regex,lambda match: long(match.group(9)),long)
        p.add(CgStcEngStcParserDataParticleKey.CG_ENG_PORT_DLOG5_LC,
              r'DLOGP5='+DLOG_LC_REGEX,lambda match: float(match.group(11)),float)
        p.add(CgStcEngStcParserDataParticleKey.CG_ENG_PORT_DLOG5_LU,
              dlogp5_regex,lambda match: float(match.group(12)),float)
        #6
        dlogp6_regex = r'DLOGP6='+DLOG_REGEX
        p.add(CgStcEngStcParserDataParticleKey.CG_ENG_PORT_DLOG6_NAME,
              dlogp6_regex,lambda match: match.group(1),str)
        p.add(CgStcEngStcParserDataParticleKey.CG_ENG_PORT_DLOG6_STATE,
              dlogp6_regex,lambda match: match.group(2),str)
        p.add(CgStcEngStcParserDataParticleKey.CG_ENG_PORT_DLOG6_TX,
              dlogp6_regex,lambda match: long(match.group(3)),long)
        p.add(CgStcEngStcParserDataParticleKey.CG_ENG_PORT_DLOG6_RX,
              dlogp6_regex,lambda match: long(match.group(4)),long)
        p.add(CgStcEngStcParserDataParticleKey.CG_ENG_PORT_DLOG6_LOG,
              dlogp6_regex,lambda match: long(match.group(5)),long)
        p.add(CgStcEngStcParserDataParticleKey.CG_ENG_PORT_DLOG6_GOOD,
              dlogp6_regex,lambda match: long(match.group(6)),long)
        p.add(CgStcEngStcParserDataParticleKey.CG_ENG_PORT_DLOG6_BAD,
              dlogp6_regex,lambda match: long(match.group(7)),long)
        p.add(CgStcEngStcParserDataParticleKey.CG_ENG_PORT_DLOG6_BB,
              dlogp6_regex,lambda match: long(match.group(8)),long)
        p.add(CgStcEngStcParserDataParticleKey.CG_ENG_PORT_DLOG6_LD,
              dlogp6_regex,lambda match: long(match.group(9)),long)
        p.add(CgStcEngStcParserDataParticleKey.CG_ENG_PORT_DLOG6_LC,
              r'DLOGP6='+DLOG_LC_REGEX,lambda match: float(match.group(11)),float)
        p.add(CgStcEngStcParserDataParticleKey.CG_ENG_PORT_DLOG6_LU,
              dlogp6_regex,lambda match: float(match.group(12)),float)
        #7
        dlogp7_regex = r'DLOGP7='+DLOG_REGEX
        p.add(CgStcEngStcParserDataParticleKey.CG_ENG_PORT_DLOG7_NAME,
              dlogp7_regex,lambda match: match.group(1),str)
        p.add(CgStcEngStcParserDataParticleKey.CG_ENG_PORT_DLOG7_STATE,
              dlogp7_regex,lambda match: match.group(2),str)
        p.add(CgStcEngStcParserDataParticleKey.CG_ENG_PORT_DLOG7_TX,
              dlogp7_regex,lambda match: long(match.group(3)),long)
        p.add(CgStcEngStcParserDataParticleKey.CG_ENG_PORT_DLOG7_RX,
              dlogp7_regex,lambda match: long(match.group(4)),long)
        p.add(CgStcEngStcParserDataParticleKey.CG_ENG_PORT_DLOG7_LOG,
              dlogp7_regex,lambda match: long(match.group(5)),long)
        p.add(CgStcEngStcParserDataParticleKey.CG_ENG_PORT_DLOG7_GOOD,
              dlogp7_regex,lambda match: long(match.group(6)),long)
        p.add(CgStcEngStcParserDataParticleKey.CG_ENG_PORT_DLOG7_BAD,
              dlogp7_regex,lambda match: long(match.group(7)),long)
        p.add(CgStcEngStcParserDataParticleKey.CG_ENG_PORT_DLOG7_BB,
              dlogp7_regex,lambda match: long(match.group(8)),long)
        p.add(CgStcEngStcParserDataParticleKey.CG_ENG_PORT_DLOG7_LD,
              dlogp7_regex,lambda match: long(match.group(9)),long)
        p.add(CgStcEngStcParserDataParticleKey.CG_ENG_PORT_DLOG7_LC,
              r'DLOGP7='+DLOG_LC_REGEX,lambda match: float(match.group(11)),float)
        p.add(CgStcEngStcParserDataParticleKey.CG_ENG_PORT_DLOG7_LU,
              dlogp7_regex,lambda match: float(match.group(12)),float)
        #8
        dlogp8_regex = r'DLOGP8='+DLOG_REGEX
        p.add(CgStcEngStcParserDataParticleKey.CG_ENG_PORT_DLOG8_NAME,
              dlogp8_regex,lambda match: match.group(1),str)
        p.add(CgStcEngStcParserDataParticleKey.CG_ENG_PORT_DLOG8_STATE,
              dlogp8_regex,lambda match: match.group(2),str)
        p.add(CgStcEngStcParserDataParticleKey.CG_ENG_PORT_DLOG8_TX,
              dlogp8_regex,lambda match: long(match.group(3)),long)
        p.add(CgStcEngStcParserDataParticleKey.CG_ENG_PORT_DLOG8_RX,
              dlogp8_regex,lambda match: long(match.group(4)),long)
        p.add(CgStcEngStcParserDataParticleKey.CG_ENG_PORT_DLOG8_LOG,
              dlogp8_regex,lambda match: long(match.group(5)),long)
        p.add(CgStcEngStcParserDataParticleKey.CG_ENG_PORT_DLOG8_GOOD,
              dlogp8_regex,lambda match: long(match.group(6)),long)
        p.add(CgStcEngStcParserDataParticleKey.CG_ENG_PORT_DLOG8_BAD,
              dlogp8_regex,lambda match: long(match.group(7)),long)
        p.add(CgStcEngStcParserDataParticleKey.CG_ENG_PORT_DLOG8_BB,
              dlogp8_regex,lambda match: long(match.group(8)),long)
        p.add(CgStcEngStcParserDataParticleKey.CG_ENG_PORT_DLOG8_LD,
              dlogp8_regex,lambda match: long(match.group(9)),long)
        p.add(CgStcEngStcParserDataParticleKey.CG_ENG_PORT_DLOG8_LC,
              r'DLOGP8='+DLOG_LC_REGEX,lambda match: float(match.group(11)),float)
        p.add(CgStcEngStcParserDataParticleKey.CG_ENG_PORT_DLOG8_LU,
              dlogp8_regex,lambda match: float(match.group(12)),float)

        DMGR_REGEX = r'DMGR.status=dmgrstatus: (\d{4}/\d{2}/\d{2}) (\d{2}:\d{2}:\d{2}\.\d+) '\
                            'act:(\d+) str:(\d+) hlt:(\d+) fld:(\d+) map:(.+)(\r\n?|\n)'

        p.add(CgStcEngStcParserDataParticleKey.CG_ENG_DMGRSTATUS_DATE,
              DMGR_REGEX,lambda match: match.group(1),str)
        p.add(CgStcEngStcParserDataParticleKey.CG_ENG_DMGRSTATUS_TIME,
              DMGR_REGEX,lambda match: match.group(2),str)
        p.add(CgStcEngStcParserDataParticleKey.CG_ENG_DMGRSTATUS_ACTIVE,
              DMGR_REGEX,lambda match: int(match.group(3)), int)
        p.add(CgStcEngStcParserDataParticleKey.CG_ENG_DMGRSTATUS_STARTED,
              DMGR_REGEX,lambda match: int(match.group(4)), int)
        p.add(CgStcEngStcParserDataParticleKey.CG_ENG_DMGRSTATUS_HALTED,
              DMGR_REGEX,lambda match: int(match.group(5)), int)
        p.add(CgStcEngStcParserDataParticleKey.CG_ENG_DMGRSTATUS_FAILED,
              DMGR_REGEX,lambda match: int(match.group(6)), int)
        p.add(CgStcEngStcParserDataParticleKey.CG_ENG_DMGRSTATUS_MAP,
              DMGR_REGEX,lambda match: match.group(7), str)

        p.add(CgStcEngStcParserDataParticleKey.CG_ENG_DMGRSTATUS_UPDATE,
              r'DMGR.last_update=(-?\d+\.\d+)(\r\n?|\n)',
              lambda match: float(match.group(1)),
              float)
        return p

    def gen_dclp_regex(self, port_number):
        """
        generate the regex to find the DCL port based on the port number
        """
        return r'DCL\.port\.%s=(-?\d) +(-?\d+\.\d+) +(-?\d+\.\d+) +(\d) +vsel: ' \
                '(-?\d+) clim: (-?\d+) prot: (-?\d+)(\r\n?|\n)' % port_number

    def gen_err_cnts(self, err_id_str):
        """
        generate the regex to find the status error counts based on an id string
        """
        return r'STATUS\.err_cnts=.*%s=(-?\d+).*(\r\n?|\n)' % err_id_str

    def gen_errmsg(self, err_id_str):
        """
        generate the error message regex to find the error message based on an id string
        """
        return r'STATUS\.last_err\.%s=(.+?)(\r\n?|\n)' % err_id_str

class CgStcEngStcParser(Parser):
    def __init__(self,
                 config,
                 state,
                 stream_handle,
                 state_callback,
                 publish_callback,
                 exception_callback,
                 *args, **kwargs):

        # no sieve function since we are not using the chunker here
        super(CgStcEngStcParser, self).__init__(config,
                                                stream_handle,
                                                state,
                                                None,
                                                state_callback,
                                                publish_callback,
                                                exception_callback,
                                                *args, **kwargs)
        # no setting state since there is no state here, 1 file = 1 particle

    def process_file(self):
        # get records expects to return a list
        record_list = []
        self._eng_str = self._stream_handle.read()
        # confirm we have actually read data, get_records may get called more than once for this
        # file but if we are already done reading it we will read no data
        if len(self._eng_str) > 0:
            # Read the first timestamp in from the stream_handle
            utime_grp = re.search(r'Platform.utime=(.+?)(\r\n?|\n)', self._eng_str)
            if utime_grp and utime_grp.group(1):
                self._timestamp = ntplib.system_to_ntp_time(float(utime_grp.group(1)))
                log.debug("extracting sample with timestamp %f", self._timestamp)
                sample = self._extract_sample(self._particle_class, None, self._eng_str, self._timestamp)
                if sample:
                    record_list.append(sample)
            else:
                raise SampleException("STC Engineering input file has no UTIME associated with it")
        return record_list

    def get_records(self, num_records):
        """
        Go ahead and execute the data parsing. This involves
        getting data from the file, then parsing it and publishing.
        @param num_records The number of records to gather
        @retval Return the list of particles requested, [] if none available
        """
        if num_records <= 0:
            return []
        # there is only one file producing one sample, process it
        record = self.process_file()
        # if a record was returned, publish it
        if record:
            self._publish_sample(record)
        # set the state to None since there is no state, and the file ingested flag to True
        # if no record was returned still set it to True because we have processed the whole file
        self._state_callback(None, True)
        return record

    def set_state(self, state):
        """
        Need to override this to pass since we have no state
        """
        pass

