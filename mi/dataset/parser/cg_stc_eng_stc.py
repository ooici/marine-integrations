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
from mi.core.exceptions import SampleException, DatasetParserException
from mi.dataset.dataset_parser import Parser
from mi.core.instrument.protocol_param_dict import ProtocolParameterDict

class DataParticleType(BaseEnum):
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
    CG_ENG_PORT_DLOG7_LU = 'cg_eng_port_dlog7_lu'
    CG_ENG_PORT_DLOG8_NAME = 'cg_eng_port_dlog8_name'
    CG_ENG_PORT_DLOG8_STATE = 'cg_eng_port_dlog8_state'
    CG_ENG_PORT_DLOG8_TX = 'cg_eng_port_dlog8_tx'
    CG_ENG_PORT_DLOG8_RX = 'cg_eng_port_dlog8_rx'
    CG_ENG_PORT_DLOG8_LOG = 'cg_eng_port_dlog8_log'
    CG_ENG_PORT_DLOG8_GOOD = 'cg_eng_port_dlog8_good'
    CG_ENG_PORT_DLOG8_BAD = 'cg_eng_port_dlog8_bad'
    CG_ENG_PORT_DLOG8_BB = 'cg_eng_port_dlog8_bb'
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

    _data_particle_type = DataParticleType.SAMPLE

    def _build_parsed_values(self):
        """
        Take something in the data format and turn it into
        a particle with the appropriate tag.
        @throws SampleException If there is a problem with sample creation
        """
        result = []
        # Instanciate the param_dict 
        params = self._build_param_dict()
        
        # Go through the param_dict dictionary for every definition
        params.update(self.raw_data)
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
        p = ProtocolParameterDict()
        p.add(CgStcEngStcParserDataParticleKey.CG_ENG_GPS_DATE,
              r'GPS.date=(.+)\r\n',
              lambda match: int(match.group(1)),
              int)
        p.add(CgStcEngStcParserDataParticleKey.CG_ENG_GPS_TIME,
              r'GPS.time=(.+)\r\n',
              lambda match: int(match.group(1)),
              int)
        p.add(CgStcEngStcParserDataParticleKey.CG_ENG_GPS_LATSTR,
              r'GPS.lat_str=(.+)\r\n',
              lambda match: match.group(1),
              str)
        p.add(CgStcEngStcParserDataParticleKey.CG_ENG_GPS_LONSTR,
              r'GPS.lon_str=(.+)\r\n',
              lambda match: match.group(1),
              str)
        p.add(CgStcEngStcParserDataParticleKey.CG_ENG_GPS_LAT,
              r'GPS.lat=(-?\d+\.\d+)\r\n',
              lambda match: float(match.group(1)),
              float)
        p.add(CgStcEngStcParserDataParticleKey.CG_ENG_GPS_LON,
              r'GPS.lon=(-?\d+\.\d+)\r\n',
              lambda match: float(match.group(1)),
              float)
        p.add(CgStcEngStcParserDataParticleKey.CG_ENG_GPS_SPD,
              r'GPS.spd=(\d+\.\d+)\r\n',
              lambda match: float(match.group(1)),
              float)
        return p

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
            utime_grp = re.search(r'Platform.utime=(.+)\r\n', self._eng_str)
            if utime_grp:
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

