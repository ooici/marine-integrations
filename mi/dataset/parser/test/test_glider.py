#!/usr/bin/env python

"""
@package mi.dataset.parser.test.test_glider Base dataset parser test code
@file mi/dataset/parser/test/test_glider.py
@author Chris Wingard & Stuart Pearce
@brief Test code for a Glider data parser.
"""

from StringIO import StringIO
import gevent
import os
import numpy as np
import ntplib
import unittest

from mi.core.log import get_logger
log = get_logger()

from nose.plugins.attrib import attr

from mi.core.exceptions import SampleException
from mi.dataset.test.test_parser import ParserUnitTestCase
from mi.dataset.dataset_driver import DataSetDriverConfigKeys
from mi.dataset.parser.glider import GliderParser, GliderEngineeringParser, StateKey
from mi.dataset.parser.glider import CtdgvDataParticle, CtdgvParticleKey
from mi.dataset.parser.glider import DostaTelemeteredDataParticle, DostaTelemeteredParticleKey
from mi.dataset.parser.glider import DostaRecoveredDataParticle, DostaRecoveredParticleKey
from mi.dataset.parser.glider import FlordDataParticle, FlordParticleKey
from mi.dataset.parser.glider import FlortRecoveredDataParticle, FlortRecoveredParticleKey
from mi.dataset.parser.glider import FlortTelemeteredDataParticle, FlortTelemeteredParticleKey
from mi.dataset.parser.glider import ParadRecoveredDataParticle, ParadRecoveredParticleKey
from mi.dataset.parser.glider import ParadTelemeteredDataParticle, ParadTelemeteredParticleKey
from mi.dataset.parser.glider import EngineeringTelemeteredParticleKey
from mi.dataset.parser.glider import EngineeringScienceTelemeteredParticleKey
from mi.dataset.parser.glider import EngineeringScienceTelemeteredDataParticle
from mi.dataset.parser.glider import EngineeringTelemeteredDataParticle
from mi.dataset.parser.glider import EngineeringMetadataDataParticle
from mi.dataset.parser.glider import EngineeringMetadataParticleKey
from mi.dataset.parser.glider import DataParticleType, GliderParticle
from mi.dataset.parser.test.glider_test_results import positions, glider_test_data


HEADER = """dbd_label: DBD_ASC(dinkum_binary_data_ascii)file
encoding_ver: 2
num_ascii_tags: 14
all_sensors: 0
filename: unit_363-2013-245-6-6
the8x3_filename: 01790006
filename_extension: sbd
filename_label: unit_363-2013-245-6-6-sbd(01790006)
mission_name: TRANS58.MI
fileopen_time: Thu_Sep__5_02:46:15_2013
sensors_per_cycle: 29
num_label_lines: 3
num_segments: 1
segment_filename_0: unit_363-2013-245-6-6
c_battpos c_wpt_lat c_wpt_lon m_battpos m_coulomb_amphr_total m_coulomb_current m_depth m_de_oil_vol m_gps_lat m_gps_lon m_heading m_lat m_lon m_pitch m_present_secs_into_mission m_present_time m_speed m_water_vx m_water_vy x_low_power_status sci_flbb_bb_units sci_flbb_chlor_units sci_m_present_secs_into_mission sci_m_present_time sci_oxy4_oxygen sci_oxy4_saturation sci_water_cond sci_water_pressure sci_water_temp
in lat lon in amp-hrs amp m cc lat lon rad lat lon rad sec timestamp m/s m/s m/s nodim nodim ug/l sec timestamp um % s/m bar degc
4 8 8 4 4 4 4 4 8 8 4 8 8 4 4 8 4 4 4 4 4 4 4 8 4 4 4 4 4 """

# header from sample data in ctdgv driver test
HEADER2 = """dbd_label: DBD_ASC(dinkum_binary_data_ascii)file
encoding_ver: 2
num_ascii_tags: 14
all_sensors: 0
filename: unit_363-2013-245-6-6
the8x3_filename: 01790006
filename_extension: sbd
filename_label: unit_363-2013-245-6-6-sbd(01790006)
mission_name: TRANS58.MI
fileopen_time: Thu_Sep__5_02:46:15_2013
sensors_per_cycle: 29
num_label_lines: 3
num_segments: 1
segment_filename_0: unit_363-2013-245-6-6
c_battpos c_wpt_lat c_wpt_lon m_battpos m_coulomb_amphr_total m_coulomb_current m_depth m_de_oil_vol m_gps_lat m_gps_lon m_heading m_lat m_lon m_pitch m_present_secs_into_mission m_present_time m_speed m_water_vx m_water_vy x_low_power_status sci_flbb_bb_units sci_flbb_chlor_units sci_m_present_secs_into_mission sci_m_present_time sci_oxy4_oxygen sci_oxy4_saturation sci_water_cond sci_water_pressure sci_water_temp
in lat lon in amp-hrs amp m cc lat lon rad lat lon rad sec timestamp m/s m/s m/s nodim nodim ug/l sec timestamp um % s/m bar degc
4 8 8 4 4 4 4 4 8 8 4 8 8 4 4 8 4 4 4 4 4 4 4 8 4 4 4 4 4  """

HEADER3 = """dbd_label: DBD_ASC(dinkum_binary_data_ascii)file
encoding_ver: 2
num_ascii_tags: 14
all_sensors: 0
filename: unit_247-2012-051-0-0-sf
the8x3_filename: 01840000
filename_extension: dbd
filename_label: unit_247-2012-051-0-0-dbd(01840000)
mission_name: ENDUR1.MI
fileopen_time: Tue_Feb_21_18:39:39_2012
sensors_per_cycle: 346
num_label_lines: 3
num_segments: 1
segment_filename_0: unit_247-2012-051-0-0
c_air_pump c_ballast_pumped c_battpos c_battroll c_bsipar_on c_de_oil_vol c_dvl_on c_flbbcd_on c_heading c_oxy3835_wphase_on c_pitch c_profile_on c_wpt_lat c_wpt_lon m_1meg_persistor m_aground_water_depth m_air_fill m_air_pump m_altimeter_status m_altimeter_voltage m_altitude m_altitude_rate m_appear_to_be_at_surface m_argos_is_xmitting m_argos_on m_argos_sent_data m_argos_timestamp m_at_risk_depth m_avbot_enable m_avbot_power m_avg_climb_rate m_avg_depth_rate m_avg_dive_rate m_avg_downward_inflection_time m_avg_speed m_avg_system_clock_lags_gps m_avg_upward_inflection_time m_avg_yo_time m_ballast_pumped m_ballast_pumped_energy m_ballast_pumped_vel m_battery m_battery_inst m_battpos m_battpos_vel m_battroll m_battroll_vel m_bpump_fault_bit m_certainly_at_surface m_chars_tossed_by_abend m_chars_tossed_with_cd_off m_chars_tossed_with_power_off m_climb_tot_time m_console_cd m_console_on m_cop_tickle m_coulomb_amphr m_coulomb_amphr_raw m_coulomb_amphr_total m_coulomb_current m_coulomb_current_raw m_cycle_number m_depth m_depth_rate m_depth_rate_avg_final m_depth_rate_running_avg m_depth_rate_running_avg_n m_depth_rate_subsampled m_depth_rejected m_depth_state m_depth_subsampled m_device_drivers_called_abnormally m_device_error m_device_oddity m_device_warning m_de_oil_vol m_de_oil_vol_pot_voltage m_de_pump_fault_count m_digifin_cmd_done m_digifin_cmd_error m_digifin_leakdetect_reading m_digifin_motorstep_counter m_digifin_resp_data m_digifin_status m_disk_free m_disk_usage m_dist_to_wpt m_dive_depth m_dive_tot_time m_dr_fix_time m_dr_postfix_time m_dr_surf_x_lmc m_dr_surf_y_lmc m_dr_time m_dr_x_actual_err m_dr_x_ini_err m_dr_x_postfix_drift m_dr_x_ta_postfix_drift m_dr_y_actual_err m_dr_y_ini_err m_dr_y_postfix_drift m_dr_y_ta_postfix_drift m_est_time_to_surface m_fin m_final_water_vx m_final_water_vy m_fin_vel m_fluid_pumped m_fluid_pumped_aft_hall_voltage m_fluid_pumped_fwd_hall_voltage m_fluid_pumped_vel m_free_heap m_gps_dist_from_dr m_gps_fix_x_lmc m_gps_fix_y_lmc m_gps_full_status m_gps_heading m_gps_ignored_lat m_gps_ignored_lon m_gps_invalid_lat m_gps_invalid_lon m_gps_lat m_gps_lon m_gps_mag_var m_gps_num_satellites m_gps_on m_gps_postfix_x_lmc m_gps_postfix_y_lmc m_gps_speed m_gps_status m_gps_toofar_lat m_gps_toofar_lon m_gps_uncertainty m_gps_utc_day m_gps_utc_hour m_gps_utc_minute m_gps_utc_month m_gps_utc_second m_gps_utc_year m_gps_x_lmc m_gps_y_lmc m_hdg_derror m_hdg_error m_hdg_ierror m_hdg_rate m_heading m_initial_water_vx m_initial_water_vy m_iridium_attempt_num m_iridium_call_num m_iridium_connected m_iridium_console_on m_iridium_dialed_num m_iridium_on m_iridium_redials m_iridium_signal_strength m_iridium_status m_iridium_waiting_redial_delay m_iridium_waiting_registration m_is_ballast_pump_moving m_is_battpos_moving m_is_battroll_moving m_is_de_pump_moving m_is_fin_moving m_is_fpitch_pump_moving m_is_speed_estimated m_is_thermal_valve_moving m_last_yo_time m_lat m_leak m_leakdetect_voltage m_leakdetect_voltage_forward m_leak_forward m_lithium_battery_relative_charge m_lithium_battery_status m_lithium_battery_time_to_charge m_lithium_battery_time_to_discharge m_lon m_min_free_heap m_min_spare_heap m_mission_avg_speed_climbing m_mission_avg_speed_diving m_mission_start_time m_num_half_yos_in_segment m_pitch m_pitch_energy m_pitch_error m_present_secs_into_mission m_present_time m_pressure m_pressure_raw_voltage_sample0 m_pressure_raw_voltage_sample19 m_pressure_voltage m_raw_altitude m_raw_altitude_rejected m_roll m_science_clothesline_lag m_science_on m_science_ready_for_consci m_science_sent_some_data m_science_sync_time m_science_unreadiness_for_consci m_spare_heap m_speed m_stable_comms m_strobe_ctrl m_surface_est_cmd m_surface_est_ctd m_surface_est_fw m_surface_est_gps m_surface_est_irid m_surface_est_total m_system_clock_lags_gps m_tcm3_is_calibrated m_tcm3_magbearth m_tcm3_poll_time m_tcm3_recv_start_time m_tcm3_recv_stop_time m_tcm3_stddeverr m_tcm3_xcoverage m_tcm3_ycoverage m_tcm3_zcoverage m_thermal_acc_pres m_thermal_acc_pres_voltage m_thermal_acc_vol m_thermal_enuf_acc_vol m_thermal_pump m_thermal_updown m_thermal_valve m_time_til_wpt m_tot_ballast_pumped_energy m_tot_horz_dist m_tot_num_inflections m_tot_on_time m_vacuum m_vehicle_temp m_veh_overheat m_veh_temp m_vmg_to_wpt m_vx_lmc m_vy_lmc m_water_cond m_water_delta_vx m_water_delta_vy m_water_depth m_water_pressure m_water_temp m_water_vx m_water_vy m_why_started m_x_lmc m_y_lmc x_last_wpt_lat x_last_wpt_lon x_system_clock_adjusted sci_bsipar_is_installed sci_bsipar_par sci_bsipar_sensor_volts sci_bsipar_supply_volts sci_bsipar_temp sci_bsipar_timestamp sci_ctd41cp_is_installed sci_ctd41cp_timestamp sci_dvl_bd_range_to_bottom sci_dvl_bd_time_since_last_good_vel sci_dvl_bd_u_dist sci_dvl_bd_v_dist sci_dvl_bd_w_dist sci_dvl_be_u_vel sci_dvl_be_v_vel sci_dvl_be_vel_good sci_dvl_be_w_vel sci_dvl_bi_err_vel sci_dvl_bi_vel_good sci_dvl_bi_x_vel sci_dvl_bi_y_vel sci_dvl_bi_z_vel sci_dvl_bs_longitudinal_vel sci_dvl_bs_normal_vel sci_dvl_bs_transverse_vel sci_dvl_bs_vel_good sci_dvl_ensemble_offset sci_dvl_error sci_dvl_is_installed sci_dvl_sa_heading sci_dvl_sa_pitch sci_dvl_sa_roll sci_dvl_ts_bit sci_dvl_ts_depth sci_dvl_ts_sal sci_dvl_ts_sound_speed sci_dvl_ts_temp sci_dvl_ts_timestamp sci_dvl_wd_range_to_water_mass_center sci_dvl_wd_time_since_last_good_vel sci_dvl_wd_u_dist sci_dvl_wd_v_dist sci_dvl_wd_w_dist sci_dvl_we_u_vel sci_dvl_we_v_vel sci_dvl_we_vel_good sci_dvl_we_w_vel sci_dvl_wi_err_vel sci_dvl_wi_vel_good sci_dvl_wi_x_vel sci_dvl_wi_y_vel sci_dvl_wi_z_vel sci_dvl_ws_longitudinal_vel sci_dvl_ws_normal_vel sci_dvl_ws_transverse_vel sci_dvl_ws_vel_good sci_flbbcd_bb_ref sci_flbbcd_bb_sig sci_flbbcd_bb_units sci_flbbcd_cdom_ref sci_flbbcd_cdom_sig sci_flbbcd_cdom_units sci_flbbcd_chlor_ref sci_flbbcd_chlor_sig sci_flbbcd_chlor_units sci_flbbcd_is_installed sci_flbbcd_therm sci_flbbcd_timestamp sci_m_disk_free sci_m_disk_usage sci_m_free_heap sci_m_min_free_heap sci_m_min_spare_heap sci_m_present_secs_into_mission sci_m_present_time sci_m_science_on sci_m_spare_heap sci_oxy3835_is_installed sci_oxy3835_oxygen sci_oxy3835_saturation sci_oxy3835_temp sci_oxy3835_timestamp sci_reqd_heartbeat sci_software_ver sci_wants_comms sci_wants_surface sci_water_cond sci_water_pressure sci_water_temp sci_x_disk_files_removed sci_x_sent_data_files
enum cc in rad sec cc sec sec rad sec rad sec lat lon bool m bool bool enum volts m m/s bool bool bool bool timestamp m bool bool m/s m/s m/s sec m/s sec sec sec cc joules cc/sec volts volts in in/sec rad rad/sec bool bool nodim nodim nodim s bool bool bool amp-hrs nodim amp-hrs amp nodim nodim m m/s m/s m/s enum m/s bool enum m nodim nodim nodim nodim cc volts nodim nodim nodim nodim nodim nodim nodim Mbytes Mbytes m m s sec sec m m sec m m m m m m m m sec rad m/s m/s rad/sec cc volts volts cc/sec bytes m m m enum rad lat lon lat lon lat lon rad nodim bool m m m/s enum lat lat nodim byte byte byte byte nodim byte m m rad/sec rad rad-sec rad/sec rad m/s m/s nodim nodim bool enum nodim bool nodim nodim enum bool bool bool bool bool bool bool bool bool bool sec lat bool volts volts bool % nodim mins mins lon bytes bytes m/s m/s timestamp nodim rad joules rad sec timestamp bar volts volts volts m bool rad s bool bool nodim timestamp enum bytes m/s bool bool nodim nodim nodim nodim nodim nodim sec bool uT ms ms ms uT % % % bar volts cc bool enum enum enum s kjoules km nodim days inHg degC bool c m/s m/s m/s S/m m/s m/s m bar degC m/s m/s enum m m lat lon sec bool ue/m^2sec volts volts degc timestamp bool timestamp m sec m m m mm/s mm/s bool mm/s mm/s bool mm/s mm/s mm/s mm/s mm/s mm/s bool nodim nodim bool deg deg deg nodim m ppt m/s degc timestamp m sec m m m mm/s mm/s bool mm/s mm/s bool mm/s mm/s mm/s mm/s mm/s mm/s bool nodim nodim nodim nodim nodim ppb nodim nodim ug/l bool nodim timestamp mbytes mbytes bytes bytes bytes sec timestamp bool bytes bool nodim nodim nodim timestamp secs nodim bool enum s/m bar degc nodim nodim
1 4 4 4 4 4 4 4 4 4 4 4 8 8 1 4 1 1 1 4 4 4 1 1 1 1 8 4 1 1 4 4 4 4 4 4 4 4 4 4 4 4 4 4 4 4 4 1 1 4 4 4 4 1 1 1 4 4 4 4 4 4 4 4 4 4 1 4 1 1 4 4 4 4 4 4 4 4 4 4 4 4 4 4 4 4 4 4 4 4 4 4 4 4 4 4 4 4 4 4 4 4 4 4 4 4 4 4 4 4 4 4 4 4 4 1 4 8 8 8 8 8 8 4 4 1 4 4 4 1 8 8 4 1 1 1 1 4 1 4 4 4 4 4 4 4 4 4 4 4 1 1 4 1 4 4 1 1 1 1 1 1 1 1 1 1 1 4 8 1 4 4 1 4 4 4 4 8 4 4 4 4 8 4 4 4 4 4 8 4 4 4 4 4 1 4 4 1 1 4 8 1 4 4 1 1 4 4 4 4 4 4 4 1 4 4 4 4 4 4 4 4 4 4 4 1 1 1 1 4 4 4 4 4 4 4 1 4 4 4 4 4 4 4 4 4 4 4 4 1 4 4 8 8 4 1 4 4 4 4 8 1 8 4 4 4 4 4 4 4 1 4 4 1 4 4 4 4 4 4 1 4 4 1 4 4 4 4 4 4 4 4 8 4 4 4 4 4 4 4 1 4 4 1 4 4 4 4 4 4 1 4 4 4 4 4 4 4 4 4 1 4 8 4 4 4 4 4 4 8 1 4 1 4 4 4 8 4 4 1 1 4 4 4 4 4 """

HEADER4 = """dbd_label: DBD_ASC(dinkum_binary_data_ascii)file
encoding_ver: 2
num_ascii_tags: 14
all_sensors: 0
filename: unit_247-2012-051-0-0-sf
the8x3_filename: 01840000
filename_extension: dbd
filename_label: unit_247-2012-051-0-0-dbd(01840000)
mission_name: ENDUR1.MI
fileopen_time: Tue_Feb_21_18:39:39_2012
sensors_per_cycle: 347
num_label_lines: 3
num_segments: 1
segment_filename_0: unit_247-2012-051-0-0
c_air_pump c_ballast_pumped c_battpos c_battroll c_bsipar_on c_de_oil_vol c_dvl_on c_flbbcd_on c_heading c_oxy3835_wphase_on c_pitch c_profile_on c_wpt_lat c_wpt_lon m_1meg_persistor m_aground_water_depth m_air_fill m_air_pump m_altimeter_status m_altimeter_voltage m_altitude m_altitude_rate m_appear_to_be_at_surface m_argos_is_xmitting m_argos_on m_argos_sent_data m_argos_timestamp m_at_risk_depth m_avbot_enable m_avbot_power m_avg_climb_rate m_avg_depth_rate m_avg_dive_rate m_avg_downward_inflection_time m_avg_speed m_avg_system_clock_lags_gps m_avg_upward_inflection_time m_avg_yo_time m_ballast_pumped m_ballast_pumped_energy m_ballast_pumped_vel m_battery m_battery_inst m_battpos m_battpos_vel m_battroll m_battroll_vel m_bpump_fault_bit m_certainly_at_surface m_chars_tossed_by_abend m_chars_tossed_with_cd_off m_chars_tossed_with_power_off m_climb_tot_time m_console_cd m_console_on m_cop_tickle m_coulomb_amphr m_coulomb_amphr_raw m_coulomb_amphr_total m_coulomb_current m_coulomb_current_raw m_cycle_number m_depth m_depth_rate m_depth_rate_avg_final m_depth_rate_running_avg m_depth_rate_running_avg_n m_depth_rate_subsampled m_depth_rejected m_depth_state m_depth_subsampled m_device_drivers_called_abnormally m_device_error m_device_oddity m_device_warning m_de_oil_vol m_de_oil_vol_pot_voltage m_de_pump_fault_count m_digifin_cmd_done m_digifin_cmd_error m_digifin_leakdetect_reading m_digifin_motorstep_counter m_digifin_resp_data m_digifin_status m_disk_free m_disk_usage m_dist_to_wpt m_dive_depth m_dive_tot_time m_dr_fix_time m_dr_postfix_time m_dr_surf_x_lmc m_dr_surf_y_lmc m_dr_time m_dr_x_actual_err m_dr_x_ini_err m_dr_x_postfix_drift m_dr_x_ta_postfix_drift m_dr_y_actual_err m_dr_y_ini_err m_dr_y_postfix_drift m_dr_y_ta_postfix_drift m_est_time_to_surface m_fin m_final_water_vx m_final_water_vy m_fin_vel m_fluid_pumped m_fluid_pumped_aft_hall_voltage m_fluid_pumped_fwd_hall_voltage m_fluid_pumped_vel m_free_heap m_gps_dist_from_dr m_gps_fix_x_lmc m_gps_fix_y_lmc m_gps_full_status m_gps_heading m_gps_ignored_lat m_gps_ignored_lon m_gps_invalid_lat m_gps_invalid_lon m_gps_lat m_gps_lon m_gps_mag_var m_gps_num_satellites m_gps_on m_gps_postfix_x_lmc m_gps_postfix_y_lmc m_gps_speed m_gps_status m_gps_toofar_lat m_gps_toofar_lon m_gps_uncertainty m_gps_utc_day m_gps_utc_hour m_gps_utc_minute m_gps_utc_month m_gps_utc_second m_gps_utc_year m_gps_x_lmc m_gps_y_lmc m_hdg_derror m_hdg_error m_hdg_ierror m_hdg_rate m_heading m_initial_water_vx m_initial_water_vy m_iridium_attempt_num m_iridium_call_num m_iridium_connected m_iridium_console_on m_iridium_dialed_num m_iridium_on m_iridium_redials m_iridium_signal_strength m_iridium_status m_iridium_waiting_redial_delay m_iridium_waiting_registration m_is_ballast_pump_moving m_is_battpos_moving m_is_battroll_moving m_is_de_pump_moving m_is_fin_moving m_is_fpitch_pump_moving m_is_speed_estimated m_is_thermal_valve_moving m_last_yo_time m_lat m_leak m_leakdetect_voltage m_leakdetect_voltage_forward m_leak_forward m_lithium_battery_relative_charge m_lithium_battery_status m_lithium_battery_time_to_charge m_lithium_battery_time_to_discharge m_lon m_min_free_heap m_min_spare_heap m_mission_avg_speed_climbing m_mission_avg_speed_diving m_mission_start_time m_num_half_yos_in_segment m_pitch m_pitch_energy m_pitch_error m_present_secs_into_mission m_present_time m_pressure m_pressure_raw_voltage_sample0 m_pressure_raw_voltage_sample19 m_pressure_voltage m_raw_altitude m_raw_altitude_rejected m_roll m_science_clothesline_lag m_science_on m_science_ready_for_consci m_science_sent_some_data m_science_sync_time m_science_unreadiness_for_consci m_spare_heap m_speed m_stable_comms m_strobe_ctrl m_surface_est_cmd m_surface_est_ctd m_surface_est_fw m_surface_est_gps m_surface_est_irid m_surface_est_total m_system_clock_lags_gps m_tcm3_is_calibrated m_tcm3_magbearth m_tcm3_poll_time m_tcm3_recv_start_time m_tcm3_recv_stop_time m_tcm3_stddeverr m_tcm3_xcoverage m_tcm3_ycoverage m_tcm3_zcoverage m_thermal_acc_pres m_thermal_acc_pres_voltage m_thermal_acc_vol m_thermal_enuf_acc_vol m_thermal_pump m_thermal_updown m_thermal_valve m_time_til_wpt m_tot_ballast_pumped_energy m_tot_horz_dist m_tot_num_inflections m_tot_on_time m_vacuum m_vehicle_temp m_veh_overheat m_veh_temp m_vmg_to_wpt m_vx_lmc m_vy_lmc m_water_cond m_water_delta_vx m_water_delta_vy m_water_depth m_water_pressure m_water_temp m_water_vx m_water_vy m_why_started m_x_lmc m_y_lmc x_last_wpt_lat x_last_wpt_lon x_system_clock_adjusted sci_bsipar_is_installed sci_bsipar_par sci_bsipar_sensor_volts sci_bsipar_supply_volts sci_bsipar_temp sci_bsipar_timestamp sci_ctd41cp_is_installed sci_ctd41cp_timestamp sci_dvl_bd_range_to_bottom sci_dvl_bd_time_since_last_good_vel sci_dvl_bd_u_dist sci_dvl_bd_v_dist sci_dvl_bd_w_dist sci_dvl_be_u_vel sci_dvl_be_v_vel sci_dvl_be_vel_good sci_dvl_be_w_vel sci_dvl_bi_err_vel sci_dvl_bi_vel_good sci_dvl_bi_x_vel sci_dvl_bi_y_vel sci_dvl_bi_z_vel sci_dvl_bs_longitudinal_vel sci_dvl_bs_normal_vel sci_dvl_bs_transverse_vel sci_dvl_bs_vel_good sci_dvl_ensemble_offset sci_dvl_error sci_dvl_is_installed sci_dvl_sa_heading sci_dvl_sa_pitch sci_dvl_sa_roll sci_dvl_ts_bit sci_dvl_ts_depth sci_dvl_ts_sal sci_dvl_ts_sound_speed sci_dvl_ts_temp sci_dvl_ts_timestamp sci_dvl_wd_range_to_water_mass_center sci_dvl_wd_time_since_last_good_vel sci_dvl_wd_u_dist sci_dvl_wd_v_dist sci_dvl_wd_w_dist sci_dvl_we_u_vel sci_dvl_we_v_vel sci_dvl_we_vel_good sci_dvl_we_w_vel sci_dvl_wi_err_vel sci_dvl_wi_vel_good sci_dvl_wi_x_vel sci_dvl_wi_y_vel sci_dvl_wi_z_vel sci_dvl_ws_longitudinal_vel sci_dvl_ws_normal_vel sci_dvl_ws_transverse_vel sci_dvl_ws_vel_good sci_flbbcd_bb_ref sci_flbbcd_bb_sig sci_flbbcd_bb_units sci_flbbcd_cdom_ref sci_flbbcd_cdom_sig sci_flbbcd_cdom_units sci_flbbcd_chlor_ref sci_flbbcd_chlor_sig sci_flbbcd_chlor_units sci_flbbcd_is_installed sci_flbbcd_therm sci_flbbcd_timestamp sci_m_disk_free sci_m_disk_usage sci_m_free_heap sci_m_min_free_heap sci_m_min_spare_heap sci_m_present_secs_into_mission sci_m_present_time sci_m_science_on sci_m_spare_heap sci_oxy3835_is_installed sci_oxy3835_oxygen sci_oxy3835_saturation sci_oxy3835_temp sci_oxy3835_timestamp sci_reqd_heartbeat sci_software_ver sci_wants_comms sci_wants_surface sci_water_cond sci_water_pressure sci_water_temp sci_x_disk_files_removed sci_x_sent_data_files x_low_power_status
enum cc in rad sec cc sec sec rad sec rad sec lat lon bool m bool bool enum volts m m/s bool bool bool bool timestamp m bool bool m/s m/s m/s sec m/s sec sec sec cc joules cc/sec volts volts in in/sec rad rad/sec bool bool nodim nodim nodim s bool bool bool amp-hrs nodim amp-hrs amp nodim nodim m m/s m/s m/s enum m/s bool enum m nodim nodim nodim nodim cc volts nodim nodim nodim nodim nodim nodim nodim Mbytes Mbytes m m s sec sec m m sec m m m m m m m m sec rad m/s m/s rad/sec cc volts volts cc/sec bytes m m m enum rad lat lon lat lon lat lon rad nodim bool m m m/s enum lat lat nodim byte byte byte byte nodim byte m m rad/sec rad rad-sec rad/sec rad m/s m/s nodim nodim bool enum nodim bool nodim nodim enum bool bool bool bool bool bool bool bool bool bool sec lat bool volts volts bool % nodim mins mins lon bytes bytes m/s m/s timestamp nodim rad joules rad sec timestamp bar volts volts volts m bool rad s bool bool nodim timestamp enum bytes m/s bool bool nodim nodim nodim nodim nodim nodim sec bool uT ms ms ms uT % % % bar volts cc bool enum enum enum s kjoules km nodim days inHg degC bool c m/s m/s m/s S/m m/s m/s m bar degC m/s m/s enum m m lat lon sec bool ue/m^2sec volts volts degc timestamp bool timestamp m sec m m m mm/s mm/s bool mm/s mm/s bool mm/s mm/s mm/s mm/s mm/s mm/s bool nodim nodim bool deg deg deg nodim m ppt m/s degc timestamp m sec m m m mm/s mm/s bool mm/s mm/s bool mm/s mm/s mm/s mm/s mm/s mm/s bool nodim nodim nodim nodim nodim ppb nodim nodim ug/l bool nodim timestamp mbytes mbytes bytes bytes bytes sec timestamp bool bytes bool nodim nodim nodim timestamp secs nodim bool enum s/m bar degc nodim nodim volts
1 4 4 4 4 4 4 4 4 4 4 4 8 8 1 4 1 1 1 4 4 4 1 1 1 1 8 4 1 1 4 4 4 4 4 4 4 4 4 4 4 4 4 4 4 4 4 1 1 4 4 4 4 1 1 1 4 4 4 4 4 4 4 4 4 4 1 4 1 1 4 4 4 4 4 4 4 4 4 4 4 4 4 4 4 4 4 4 4 4 4 4 4 4 4 4 4 4 4 4 4 4 4 4 4 4 4 4 4 4 4 4 4 4 4 1 4 8 8 8 8 8 8 4 4 1 4 4 4 1 8 8 4 1 1 1 1 4 1 4 4 4 4 4 4 4 4 4 4 4 1 1 4 1 4 4 1 1 1 1 1 1 1 1 1 1 1 4 8 1 4 4 1 4 4 4 4 8 4 4 4 4 8 4 4 4 4 4 8 4 4 4 4 4 1 4 4 1 1 4 8 1 4 4 1 1 4 4 4 4 4 4 4 1 4 4 4 4 4 4 4 4 4 4 4 1 1 1 1 4 4 4 4 4 4 4 1 4 4 4 4 4 4 4 4 4 4 4 4 1 4 4 8 8 4 1 4 4 4 4 8 1 8 4 4 4 4 4 4 4 1 4 4 1 4 4 4 4 4 4 1 4 4 1 4 4 4 4 4 4 4 4 8 4 4 4 4 4 4 4 1 4 4 1 4 4 4 4 4 4 1 4 4 4 4 4 4 4 4 4 1 4 8 4 4 4 4 4 4 8 1 4 1 4 4 4 8 4 4 1 1 4 4 4 4 4 4 """


ENGSCI_RECORD = """
1 260 0.7 0 -1 260 -1 -1 4.96727 -1 0.4528 -1 4330 -12600 0 -1 1 1 2 2.44548 12.9695 -0.219681 1 0 1 0 1329843706.03265 1196.2 0 0 -0.183911 0.00699798 0.166781 155.923 0.379813 0.55692 124.082 4971.02 0 0 0 10.6873 10.7871 0.703717 0.141578 0 0 0 1 59 1 1 -1 0 1 1 40.9937 -9944 303.803 0.485094 -1634 0 0.258982 0 0.00472497 0 0 0.00136254 0 0 0.258982 8 6 21 6 259.77 1.43611 0 0 0 1022 6 0 4194300 1781.12 219.812 48926.2 -1 -1 -1 -1 0 0 -1 0 0 0 0 0 0 0 0 43.0556 0 -0.0616963 -0.144984 0 0 0 0 0 304128 0.916352 0 0 0 1.7942 4328.2816 -12523.8141 4328.2925 -12523.8189 4328.2683 -12523.7965 -0.279253 11 0 0 0 0.308667 0 4328.6173 -12513.3557 0.9 21 18 3 2 35 12 40389 -1904.23 0.0197767 0.11338 0.120462 -0.0173492 5.05447 -0.0616291 -0.145094 0 518 1 0 3323 0 0 5 99 0 0 0 0 0 0 0 0 0 0 4756.23 4328.26830007145 0 2.46526 2.45955 0 57.8052 0 0 0 -12523.7965000589 289792 270336 0.430413 0.350943 1329849569 0 0.518363 102687000 -0.0426476 0 1329849569.26294 0.0258982 0 0 0.137179 16.967 1 -0.10821 32.0756 0 0 1371 1329849561.95532 1 284672 0.348396 1 0 1 0 0 7.58463e-23 1 2 1 0 -1 0 0 0 -1 -1 -1 -1 0 0 0 0 0 3 2 -172433 0.74206 605.857 3115 5.06637 10.0444 0 0 13.1124 -0.283741 0.300996 -0.0683846 3 -0.0218157 0.0107268 -1 49.141 10 -0.0616963 -0.144984 16 40389 -1904.23 4330 -12600 -12 NaN NaN NaN NaN NaN NaN NaN NaN NaN NaN NaN NaN NaN NaN NaN NaN NaN NaN NaN NaN NaN NaN NaN NaN NaN NaN NaN NaN NaN NaN NaN NaN NaN NaN NaN NaN NaN NaN NaN NaN NaN NaN NaN NaN NaN NaN NaN NaN NaN NaN NaN NaN NaN NaN NaN NaN NaN NaN NaN NaN NaN NaN NaN NaN NaN NaN NaN NaN 1000.1 1000.1 NaN NaN NaN 1000.1 1000.1 NaN NaN NaN NaN NaN NaN NaN NaN NaN NaN NaN NaN NaN NaN NaN NaN 1000.1
1 260 0.7 0 -1 260 -1 -1 4.96727 -1 0.4528 -1 4330 -12600 0 -1 1 1 2 2.44548 12.9695 -0.219681 1 0 1 0 1329843706.03265 1196.2 0 0 -0.183911 0.00699798 0.166781 155.923 0.379813 0.55692 124.082 4971.02 0 0 0 10.6806 10.6208 0.695632 0.141578 0 0 0 1 59 1 1 -1 0 1 1 40.9972 -9947 303.806 0.0955938 -322 1 0.148777 0 0.00472497 0 0 0.00136254 0 0 0.258982 3 6 21 6 259.742 1.43605 0 0 0 1023 3 0 4194310 1781.12 219.812 48926.2 -1 -1 -1 -1 0 0 -1 0 0 0 0 0 0 0 0 43.0556 0.0127162 -0.0616963 -0.144984 0 0 0 0 0 324608 0.916352 0 0 7 1.7942 4328.2816 -12523.8141 4328.2925 -12523.8189 4328.2683 -12523.7965 -0.279253 11 1 0 0 0.308667 0 4328.6173 -12513.3557 0.9 21 18 3 2 35 12 40389 -1904.23 0.0197767 0.11338 0.120462 -0.0173492 5.05447 -0.0616291 -0.145094 0 518 0 0 3323 0 0 5 99 0 0 0 0 0 0 0 0 0 0 4756.23 4328.26830007145 0 2.46386 2.45876 0 57.8047 0 0 0 -12523.7965000589 289792 270336 0.430413 0.350943 1329849569 0 0.518363 115832000 -0.0426476 49.646 1329849618.79962 0.0148777 0 0 0.137057 16.967 1 -0.10821 32.0756 1 0 59 1329849561.95532 1 283648 0.348396 0 0 1 0 0 6.63787e-23 0.875173 1.87517 1 0 -1 0 0 0 -1 -1 -1 -1 0 0 0 0 0 3 2 -172433 0.74206 605.857 3115 5.06637 7.84544 0 0 13.1954 -0.283741 0 0 3 -0.0218157 0.0107268 -1 49.141 10 -0.0616963 -0.144984 16 0 0 4330 -12600 -12 NaN NaN NaN NaN NaN NaN NaN NaN NaN NaN NaN NaN NaN NaN NaN NaN NaN NaN NaN NaN NaN NaN NaN NaN NaN NaN NaN NaN NaN NaN NaN NaN NaN NaN NaN NaN NaN NaN NaN NaN NaN NaN NaN NaN NaN NaN NaN NaN NaN NaN NaN NaN NaN NaN NaN NaN NaN NaN NaN NaN NaN NaN NaN NaN NaN NaN NaN NaN 1000.2 1000.2 NaN NaN NaN 1000.2 1000.2 NaN NaN NaN NaN NaN NaN NaN NaN NaN NaN NaN NaN NaN NaN NaN NaN 1000.1 """

FLORT_RECORD = """
NaN NaN NaN NaN NaN NaN NaN NaN NaN NaN NaN NaN NaN NaN NaN NaN NaN NaN NaN NaN NaN NaN NaN NaN NaN NaN NaN NaN NaN NaN NaN NaN NaN NaN NaN NaN NaN NaN NaN NaN NaN NaN NaN NaN NaN NaN NaN NaN NaN NaN NaN NaN NaN NaN NaN NaN NaN NaN NaN NaN NaN NaN NaN NaN NaN NaN NaN NaN NaN NaN NaN NaN NaN NaN NaN NaN NaN NaN NaN NaN NaN NaN NaN NaN NaN NaN NaN NaN NaN NaN NaN NaN NaN NaN NaN NaN NaN NaN NaN NaN NaN NaN NaN NaN NaN NaN NaN NaN NaN NaN NaN NaN NaN NaN NaN NaN NaN NaN NaN NaN NaN NaN NaN NaN NaN NaN NaN NaN NaN NaN NaN NaN NaN NaN NaN NaN NaN NaN NaN NaN NaN NaN NaN NaN NaN NaN NaN NaN NaN NaN NaN NaN NaN NaN NaN NaN NaN NaN NaN NaN NaN NaN NaN NaN NaN NaN NaN NaN NaN NaN NaN NaN NaN NaN NaN NaN NaN NaN NaN NaN NaN NaN NaN NaN NaN NaN NaN 153.928 1329849722.92795 NaN NaN NaN NaN NaN NaN NaN NaN NaN NaN NaN NaN NaN NaN NaN NaN NaN NaN NaN NaN NaN NaN NaN NaN NaN NaN NaN NaN NaN NaN NaN NaN NaN NaN NaN NaN NaN NaN NaN NaN NaN NaN NaN NaN NaN NaN NaN NaN NaN NaN NaN NaN NaN NaN NaN NaN NaN NaN NaN NaN NaN NaN NaN NaN NaN NaN NaN 664.424 0.401911 10.572 10.25 NaN NaN NaN NaN NaN NaN NaN NaN NaN NaN NaN NaN NaN NaN NaN NaN NaN NaN NaN NaN NaN NaN NaN NaN NaN NaN NaN NaN NaN NaN NaN NaN NaN NaN NaN NaN NaN NaN NaN NaN NaN NaN NaN NaN NaN NaN NaN NaN NaN NaN NaN 700 139 0.000281336 460 72 2.0352 695 114 0.8349 NaN 560 NaN NaN NaN NaN NaN NaN 153.928 1329849722.92795 NaN NaN NaN 266.42 93.49 9.48 NaN NaN NaN NaN NaN NaN NaN NaN NaN NaN
NaN NaN NaN NaN NaN NaN NaN NaN NaN NaN NaN NaN NaN NaN NaN NaN NaN NaN NaN NaN NaN NaN NaN NaN NaN NaN NaN NaN NaN NaN NaN NaN NaN NaN NaN NaN NaN NaN NaN NaN NaN NaN NaN NaN NaN NaN NaN NaN NaN NaN NaN NaN NaN NaN NaN NaN NaN NaN NaN NaN NaN NaN NaN NaN NaN NaN NaN NaN NaN NaN NaN NaN NaN NaN NaN NaN NaN NaN NaN NaN NaN NaN NaN NaN NaN NaN NaN NaN NaN NaN NaN NaN NaN NaN NaN NaN NaN NaN NaN NaN NaN NaN NaN NaN NaN NaN NaN NaN NaN NaN NaN NaN NaN NaN NaN NaN NaN NaN NaN NaN NaN NaN NaN NaN NaN NaN NaN NaN NaN NaN NaN NaN NaN NaN NaN NaN NaN NaN NaN NaN NaN NaN NaN NaN NaN NaN NaN NaN NaN NaN NaN NaN NaN NaN NaN NaN NaN NaN NaN NaN NaN NaN NaN NaN NaN NaN NaN NaN NaN NaN NaN NaN NaN NaN NaN NaN NaN NaN NaN NaN NaN NaN NaN NaN NaN NaN NaN 154.944 1329849723.94394 NaN NaN NaN NaN NaN NaN NaN NaN NaN NaN NaN NaN NaN NaN NaN NaN NaN NaN NaN NaN NaN NaN NaN NaN NaN NaN NaN NaN NaN NaN NaN NaN NaN NaN NaN NaN NaN NaN NaN NaN NaN NaN NaN NaN NaN NaN NaN NaN NaN NaN NaN NaN NaN NaN NaN NaN NaN NaN NaN NaN NaN NaN NaN NaN NaN NaN NaN 645.569 0.390792 10.572 10.25 NaN NaN NaN NaN NaN NaN NaN NaN NaN NaN NaN NaN NaN NaN NaN NaN NaN NaN NaN NaN NaN 892 NaN NaN NaN NaN NaN NaN NaN NaN NaN NaN NaN NaN NaN NaN NaN NaN NaN NaN NaN NaN NaN NaN NaN NaN NaN NaN NaN NaN NaN 700 133 0.000262988 460 73 2.12 695 115 0.847 NaN 559 NaN NaN NaN NaN NaN NaN 154.944 1329849723.94394 NaN NaN NaN NaN NaN NaN NaN NaN NaN NaN NaN NaN NaN NaN NaN NaN """

EMPTY_RECORD = """
NaN NaN NaN NaN NaN NaN NaN NaN NaN NaN NaN NaN NaN NaN NaN NaN NaN NaN NaN NaN NaN NaN NaN NaN NaN NaN NaN NaN """

ZERO_GPS_VALUE = """
NaN 0 NaN NaN NaN NaN NaN NaN NaN NaN NaN NaN NaN NaN NaN NaN NaN NaN NaN NaN NaN NaN NaN NaN NaN NaN NaN NaN NaN """

INT_GPS_VALUE = """
NaN 2012 NaN NaN NaN NaN NaN NaN NaN NaN NaN NaN NaN NaN NaN NaN NaN NaN NaN NaN NaN NaN NaN NaN NaN NaN NaN NaN NaN """

CHUNKER_TEST = """
0.273273 NaN NaN 0.335 149.608 0.114297 33.9352 -64.3506 NaN NaN NaN 5011.38113678061 -14433.5809717525 NaN 121546 1378349641.79871 NaN NaN NaN 0 NaN NaN NaN NaN NaN NaN NaN 11.00
3 NaN NaN NaN NaN NaN NaN NaN NaN NaN 1.23569 NaN NaN -0.0820305 121379 1378349475.09927 0.236869 NaN NaN NaN NaN NaN NaN NaN NaN NaN NaN NaN 1
"""

CTDGV_RECORD = """
NaN NaN NaN NaN NaN NaN NaN NaN NaN NaN NaN NaN NaN NaN 121147 1378349241.82962 NaN NaN NaN NaN NaN NaN 121147 1378349241.82962 NaN NaN 4.03096 0.021 15.3683
NaN NaN NaN NaN NaN NaN NaN NaN NaN NaN NaN NaN NaN NaN 121207 1378349302.10907 NaN NaN NaN NaN NaN NaN 121207 1378349302.10907 NaN NaN 4.03113 0.093 15.3703 """

DOSTA_RECORD = """
NaN NaN NaN NaN NaN NaN NaN NaN NaN NaN NaN NaN NaN NaN 121144 1378349238.77789 NaN NaN NaN NaN NaN NaN 121144 1378349238.77789 242.217 96.009 NaN NaN NaN
NaN NaN NaN NaN NaN NaN NaN NaN NaN NaN NaN NaN NaN NaN 121204 1378349299.09106 NaN NaN NaN NaN NaN NaN 121204 1378349299.09106 242.141 95.988 NaN NaN NaN """

FLORD_RECORD = """
NaN NaN NaN NaN NaN NaN NaN NaN NaN NaN NaN NaN NaN NaN 121140 1378349234.75079 NaN NaN NaN NaN 0.000298102 1.519 121140 1378349234.75079 NaN NaN NaN NaN NaN
NaN NaN NaN NaN NaN NaN NaN NaN NaN NaN NaN NaN NaN NaN 121321 1378349415.84534 NaN NaN NaN NaN 0.000327355 1.708 121321 1378349415.84534 NaN NaN NaN NaN NaN """

ENG_RECORD = """
0.273273 NaN NaN 0.335 149.608 0.114297 33.9352 -64.3506 NaN NaN NaN 5011.38113678061 -14433.5809717525 NaN 121546 1378349641.79871 NaN NaN NaN 0 NaN NaN NaN NaN NaN NaN NaN NaN NaN
NaN NaN NaN NaN NaN NaN NaN NaN NaN NaN 1.23569 NaN NaN -0.0820305 121379 1378349475.09927 0.236869 NaN NaN NaN NaN NaN NaN NaN NaN NaN NaN NaN NaN """

@attr('UNIT', group='mi')
class GliderParserUnitTestCase(ParserUnitTestCase):
    """
    Glider Parser unit test base class and common tests.
    """
    config = {}

    def state_callback(self, state, file_ingested):
        """ Call back method to watch what comes in via the state callback """
        self.state_callback_values.append(state)
        self.file_ingested = file_ingested

    def pub_callback(self, particle):
        """ Call back method to watch what comes in via the publish callback """
        self.publish_callback_values.append(particle)

    def error_callback(self, error):
        """ Call back method to watch what comes in via the state callback """
        self.error_callback_values.append(error)

    def setUp(self):
        ParserUnitTestCase.setUp(self)

    def set_data(self, *args):
        """
        Accept strings of data in args[] joined together and then a file handle
        to the concatenated string is returned.
        """
        io = StringIO()
        for count, data in enumerate(args):
            io.write(data)

        #log.debug("Test data file: %s", io.getvalue())
        io.seek(0)
        self.test_data = io

    def set_data_file(self, filename):
        """
        Set test to read from a file.
        """
        self.test_data = open(filename, "r")

    def reset_parser(self, state = {}):
        self.state_callback_values = []
        self.publish_callback_values = []
        self.error_callback_values = []
        self.parser = GliderParser(self.config, state, self.test_data,
                                   self.state_callback, self.pub_callback, self.error_callback)

    def reset_eng_parser(self, state = {}):
        self.state_callback_values = []
        self.publish_callback_values = []
        self.error_callback_values = []
        self.parser = GliderEngineeringParser(self.config, state, self.test_data,
                                   self.state_callback, self.pub_callback, self.error_callback)

    def get_published_value(self):
        return self.publish_callback_values.pop(0)

    def get_state_value(self):
        return self.state_callback_values.pop(0)

    def assert_state(self, expected_position):
        """
        Verify the state
        """
        state = self.parser._read_state
        log.debug("Current state: %s", state)

        position = state.get(StateKey.POSITION)
        self.assertEqual(position, expected_position)

    def assert_no_more_data(self):
        """
        Verify we don't find any other records in the data file.
        """
        records = self.parser.get_records(1)
        self.assertEqual(len(records), 0)

    def assert_generate_particle(self, particle_type, values_dict = None, expected_position = None):
        """
        Verify that we can generate a particle of the correct type and that
        the state is set properly.
        @param particle_type type of particle we are producing
        @param values_dict key value pairs to test in the particle.
        @param expected_position upon publication of the particle, what should the state position indicate.
        """
        # ensure the callback queues are empty before we start
        self.assertEqual(len(self.publish_callback_values), 0)
        self.assertEqual(len(self.state_callback_values), 0)

        records = self.parser.get_records(1)

        self.assertIsNotNone(records)
        self.assertIsInstance(records, list)
        self.assertEqual(len(records), 1)

        self.assertEqual(len(self.publish_callback_values), 1)
        self.assertEqual(len(self.state_callback_values), 1)

        particles = self.get_published_value()
        self.assertEqual(len(particles), 1)

        # Verify the data
        if values_dict:
            self.assert_particle_values(particles[0], values_dict)

        # Verify the parser state
        state = self.get_state_value()
        log.debug("Published state: %s", state)

        if expected_position:
            position = state.get(StateKey.POSITION)
            self.assertEqual(position, expected_position)

    def assert_particle_values(self, particle, expected_values):
        """
        Verify the data in expected values is the data in the particle
        """
        data_dict = particle.generate_dict()
        log.debug("Data in particle: %s", data_dict)
        log.debug("Expected Data: %s", expected_values)

        for key in expected_values.keys():
            for value in data_dict['values']:
                if value['value_id'] == key:
                    self.assertEqual(value['value'], expected_values[key])

    def assert_type(self, records, particle_type):
        for particle in records:
            str_of_type = particle.type()
            self.assertEqual(particle_type, str_of_type)

    def assert_timestamp(self, ntp_timestamp, unix_timestamp):
        ntp_stamp = ntplib.system_to_ntp_time(unix_timestamp)
        assertion = np.allclose(ntp_timestamp, ntp_stamp)
        self.assertTrue(assertion)

    def test_init(self):
        """
        Verify we can initialize
        """
        self.set_data(HEADER)
        self.reset_parser()
        self.assert_state(1003)

        self.set_data(HEADER2)
        self.reset_parser()
        self.assert_state(1004)

    def test_exception(self):
        with self.assertRaises(SampleException):
            self.set_data("Foo")
            self.reset_parser()

    def test_chunker(self):
        """
        Verify the chunker is returning values we expect.
        """
        self.set_data(HEADER, CHUNKER_TEST)
        self.reset_parser()

        records = CHUNKER_TEST.strip("\n").split("\n")
        log.debug("Expected Records: %s", records)
        self.assertEqual(len(records), 2)

        # Load all data into the chunker
        self.parser.get_block(1024)

        self.assertEqual(CHUNKER_TEST.strip("\n"), self.parser._chunker.buffer.strip("\n"))

        (timestamp, data_record, start, end) = self.parser._chunker.get_next_data_with_index()
        log.debug("Data Record: %s", data_record)
        self.assertEqual(records[0]+"\n", data_record)

        (timestamp, data_record, start, end) = self.parser._chunker.get_next_data_with_index()
        self.assertEqual(records[1]+"\n", data_record)


@attr('UNIT', group='mi')
class CTDGVGliderTest(GliderParserUnitTestCase):
    """
    Test cases for ctdgv glider data
    """
    config = {
        DataSetDriverConfigKeys.PARTICLE_MODULE: 'mi.dataset.parser.glider',
        DataSetDriverConfigKeys.PARTICLE_CLASS: 'CtdgvDataParticle',
    }

    def test_ctdgv_particle(self):
        """
        Verify we publish particles as expected.  Ensure particle is published and
        that state is returned.
        """
        self.set_data(HEADER, CTDGV_RECORD)
        self.reset_parser()

        record_1 = {CtdgvParticleKey.SCI_WATER_TEMP: 15.3683, CtdgvParticleKey.SCI_WATER_COND: 4.03096,
                    CtdgvParticleKey.SCI_WATER_PRESSURE: 0.021}
        record_2 = {CtdgvParticleKey.SCI_WATER_TEMP: 15.3703, CtdgvParticleKey.SCI_WATER_COND: 4.03113,
                    CtdgvParticleKey.SCI_WATER_PRESSURE: 0.093}

        self.assert_generate_particle(CtdgvDataParticle, record_1, 1162)
        self.assert_generate_particle(CtdgvDataParticle, record_2, 1321)
        self.assert_no_more_data()

        # Reset with the parser, but with a state this time
        self.set_data(HEADER, CTDGV_RECORD)
        self.reset_parser({StateKey.POSITION: 1162})
        self.assert_generate_particle(CtdgvDataParticle, record_2, 1321)
        self.assert_no_more_data()

    def test_gps(self):
        self.set_data(HEADER, ZERO_GPS_VALUE)
        self.reset_parser()
        records = self.parser.get_records(1)
        self.assertEqual(len(records), 0)

        self.set_data(HEADER, INT_GPS_VALUE)
        self.reset_parser()
        records = self.parser.get_records(1)
        self.assertEqual(len(records), 0)

@attr('UNIT', group='mi')
class DOSTATelemeteredGliderTest(GliderParserUnitTestCase):
    """
    Test cases for dosta glider data
    """
    config = {
        DataSetDriverConfigKeys.PARTICLE_MODULE: 'mi.dataset.parser.glider',
        DataSetDriverConfigKeys.PARTICLE_CLASS: 'DostaTelemeteredDataParticle',
    }

    def test_dosta_telemetered_particle(self):
        """
        Verify we publish particles as expected.  Ensure particle is published and
        that state is returned.
        """
        self.set_data(HEADER, DOSTA_RECORD)
        self.reset_parser()

        record_1 = {DostaTelemeteredParticleKey.SCI_OXY4_OXYGEN: 242.217, DostaTelemeteredParticleKey.SCI_OXY4_SATURATION: 96.009}
        record_2 = {DostaTelemeteredParticleKey.SCI_OXY4_OXYGEN: 242.141, DostaTelemeteredParticleKey.SCI_OXY4_SATURATION: 95.988}

        self.assert_generate_particle(DostaTelemeteredDataParticle, record_1, 1159)
        self.assert_generate_particle(DostaTelemeteredDataParticle, record_2, 1315)
        self.assert_no_more_data()

        # Reset with the parser, but with a state this time
        self.set_data(HEADER, DOSTA_RECORD)
        self.reset_parser({StateKey.POSITION: 1159})
        self.assert_generate_particle(DostaTelemeteredDataParticle, record_2, 1315)
        self.assert_no_more_data()

@attr('UNIT', group='mi')
class FLORTTelemeteredGliderTest(GliderParserUnitTestCase):
    """
    Test cases for dosta glider data
    """
    config = {
        DataSetDriverConfigKeys.PARTICLE_MODULE: 'mi.dataset.parser.glider',
        DataSetDriverConfigKeys.PARTICLE_CLASS: 'FlortTelemeteredDataParticle',
    }

    def test_flort_telemetered_particle(self):
        """
        Verify we publish particles as expected.  Ensure particle is published and
        that state is returned.
        """
        self.set_data(HEADER3, FLORT_RECORD)
        self.reset_parser()

        record_1 = {FlortTelemeteredParticleKey.SCI_FLBBCD_BB_UNITS: 0.000281336,
                    FlortTelemeteredParticleKey.SCI_FLBBCD_CDOM_UNITS: 2.0352,
                    FlortTelemeteredParticleKey.SCI_FLBBCD_CHLOR_UNITS: 0.8349}
        record_2 = {FlortTelemeteredParticleKey.SCI_FLBBCD_BB_UNITS: 0.000262988,
                    FlortTelemeteredParticleKey.SCI_FLBBCD_CDOM_UNITS: 2.12,
                    FlortTelemeteredParticleKey.SCI_FLBBCD_CHLOR_UNITS: 0.847}

        self.assert_generate_particle(FlortTelemeteredDataParticle, record_1, 10534)
        self.assert_generate_particle(FlortTelemeteredDataParticle, record_2, 11977)
        self.assert_no_more_data()

        # Reset with the parser, but with a state this time
        self.set_data(HEADER3, FLORT_RECORD)
        self.reset_parser({StateKey.POSITION: 10534})
        self.assert_generate_particle(FlortTelemeteredDataParticle, record_2, 11977)
        self.assert_no_more_data()

@attr('UNIT', group='mi')
class PARADTelemeteredGliderTest(GliderParserUnitTestCase):
    """
    Test cases for dosta glider data
    """
    config = {
        DataSetDriverConfigKeys.PARTICLE_MODULE: 'mi.dataset.parser.glider',
        DataSetDriverConfigKeys.PARTICLE_CLASS: 'ParadTelemeteredDataParticle',
    }

    def test_parad_telemetered_particle(self):
        """
        Verify we publish particles as expected.  Ensure particle is published and
        that state is returned.
        """
        # reused the FLORT record data for this Parad test
        self.set_data(HEADER3, FLORT_RECORD)
        self.reset_parser()

        record_1 = {ParadTelemeteredParticleKey.SCI_BSIPAR_PAR: 664.424}
        record_2 = {ParadTelemeteredParticleKey.SCI_BSIPAR_PAR: 645.569}

        # (10553 = file size up to start of last row) 10553 - 19 bytes (for 19 lines of Carriage returns above) = 10534
        self.assert_generate_particle(ParadTelemeteredDataParticle, record_1, 10534)
        # (11997 = file size in bytes) 11997 - 20 bytes (for 20 lines of Carriage returns above) = 11977
        self.assert_generate_particle(ParadTelemeteredDataParticle, record_2, 11977)
        self.assert_no_more_data()

        # Reset with the parser, but with a state this time
        self.set_data(HEADER3, FLORT_RECORD)
        self.reset_parser({StateKey.POSITION: 10534})
        self.assert_generate_particle(ParadTelemeteredDataParticle, record_2, 11977)
        self.assert_no_more_data()

@attr('UNIT', group='mi')
class FLORDGliderTest(GliderParserUnitTestCase):
    """
    Test cases for flord glider data
    """
    config = {
        DataSetDriverConfigKeys.PARTICLE_MODULE: 'mi.dataset.parser.glider',
        DataSetDriverConfigKeys.PARTICLE_CLASS: 'FlordDataParticle',
    }

    def test_flord_particle(self):
        """
        Verify we publish particles as expected.  Ensure particle is published and
        that state is returned.
        """
        # reused the FLORT record data for this Flord test
        self.set_data(HEADER3, FLORT_RECORD)
        self.reset_parser()

        record_1 = {FlordParticleKey.SCI_FLBBCD_BB_UNITS: 0.000281336, FlordParticleKey.SCI_FLBBCD_CHLOR_UNITS: 0.8349}
        record_2 = {FlordParticleKey.SCI_FLBBCD_BB_UNITS: 0.000262988, FlordParticleKey.SCI_FLBBCD_CHLOR_UNITS: 0.847}

        # (10553 = file size up to start of last row) 10553 - 19 bytes (for 19 lines of Carriage returns above) = 10534
        self.assert_generate_particle(ParadTelemeteredDataParticle, record_1, 10534)
        # (11997 = file size in bytes) 11997 - 20 bytes (for 20 lines of Carriage returns above) = 11977
        self.assert_generate_particle(ParadTelemeteredDataParticle, record_2, 11977)
        self.assert_no_more_data()

        # Reset with the parser, but with a state this time
        self.set_data(HEADER3, FLORT_RECORD)
        self.reset_parser({StateKey.POSITION: 10534})
        self.assert_generate_particle(FlordDataParticle, record_2, 11977)
        self.assert_no_more_data()

@attr('UNIT', group='mi')
class ENGGliderTest(GliderParserUnitTestCase):
    """
    Test cases for eng glider data
    """
    config = {
        DataSetDriverConfigKeys.PARTICLE_MODULE: 'mi.dataset.parser.glider',
        DataSetDriverConfigKeys.PARTICLE_CLASS: ['EngineeringMetadataDataParticle',
                                                 'EngineeringTelemeteredDataParticle',
                                                 'EngineeringScienceTelemeteredDataParticle']
    }

    def test_eng_particle(self):
        """
        Verify we publish particles as expected.  Ensure particle is published and
        that state is returned.
        """
        self.set_data(HEADER4, ENGSCI_RECORD)
        self.reset_eng_parser()

        meta_record = {EngineeringMetadataParticleKey.GLIDER_ENG_FILENAME: 'unit_247-2012-051-0-0-dbd(01840000)',
                       EngineeringMetadataParticleKey.GLIDER_MISSION_NAME: 'ENDUR1.MI',
                       EngineeringMetadataParticleKey.GLIDER_ENG_FILEOPEN_TIME: 'Tue_Feb_21_18:39:39_2012'}

        record_1 = {EngineeringTelemeteredParticleKey.M_BATTPOS: 0.703717,
                    EngineeringTelemeteredParticleKey.M_HEADING: 5.05447}
        record_2 = {EngineeringTelemeteredParticleKey.M_BATTPOS: 0.695632,
                    EngineeringTelemeteredParticleKey.M_HEADING: 5.05447}

        record_sci_1 = {EngineeringScienceTelemeteredParticleKey.SCI_M_DISK_FREE: 1000.1,
                    EngineeringScienceTelemeteredParticleKey.SCI_M_DISK_USAGE: 1000.1}
        record_sci_2 = {EngineeringScienceTelemeteredParticleKey.SCI_M_DISK_FREE: 1000.2,
                    EngineeringScienceTelemeteredParticleKey.SCI_M_DISK_USAGE: 1000.2}

        self.assert_generate_particle(EngineeringMetadataDataParticle, meta_record, 9110)
        # 1 sample line generates 2 particles
        self.assert_generate_particle(EngineeringTelemeteredDataParticle, record_1, 10795)
        self.assert_generate_particle(EngineeringScienceTelemeteredDataParticle, record_sci_1, 10795)
        # total file size in bytes
        self.assert_generate_particle(EngineeringTelemeteredDataParticle, record_2, 12479)
        self.assert_generate_particle(EngineeringScienceTelemeteredDataParticle, record_sci_2, 12479)
        self.assert_no_more_data()

        # Reset with the parser, but with a state this time
        self.set_data(HEADER4, ENGSCI_RECORD)
        self.reset_eng_parser({StateKey.POSITION: 10795, StateKey.SENT_METADATA: True})
        self.assert_generate_particle(EngineeringTelemeteredDataParticle, record_2, 12479)
        self.assert_generate_particle(EngineeringScienceTelemeteredDataParticle, record_sci_2, 12479)
        self.assert_no_more_data()
