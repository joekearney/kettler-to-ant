#!/usr/bin/python

messages="""
power calibration_request    None,channel,0x01,0xAA,None,None,None,None,None,None
power srm_zero_response      None,channel,0x01,0x10,0x01,None,None,None,uint16_be:offset
power calibration_pass       None,channel,0x01,0xAC,uint8:autozero_status,None,None,None,uint16_le:calibration_data
power calibration_fail       None,channel,0x01,0xAF,uint8:autozero_status,None,None,None,uint16_le:calibration_data
power torque_support         None,channel,0x01,0x12,uint8:sensor_configuration,sint16_le:raw_torque,sint16_le:offset_torque,None
power standard_power         0x4e,channel,0x10,uint8_diff:event_count,uint8:pedal_balance,uint8:instant_cadence,uint16_le_diff:sum_power,uint16_le:instant_power
power wheel_torque           0x4e,channel,0x11,uint8_diff:event_count,uint8:wheel_rev,uint8:instant_cadence,uint16_le_diff:wheel_period,uint16_le_diff:torque
power crank_torque           0x4e,channel,0x12,uint8_diff:event_count,uint8:crank_rev,uint8:instant_cadence,uint16_le_diff:crank_period,uint16_le_diff:torque
power crank_SRM              0x4e,channel,0x20,uint8_diff:event_count,uint16_be:slope,uint16_be_diff:crank_period,uint16_be_diff:torque
* manufacturer               0x4e,channel,0x50,None,None,hw_rev,uint16_le:manufacturer_id,uint16_le:model_number_id
* product                    0x4e,channel,0x51,None,None,sw_rev,uint16_le:serial_number_qpod,uint16_le:serial_number_spider
* battery_voltage            0x4e,channel,0x52,None,None,operating_time_lsb,operating_time_1sb,operating_time_msb,voltage_lsb,descriptive_bits
heartrate heart_rate         0x4e,channel,None,None,None,None,uint16_le_diff:measurement_time,uint8_diff:beats,uint8:instant_heart_rate Ant heart rate monitor
speed speed                  0x4e,channel,None,None,None,None,uint16_le_diff:measurement_time,uint16_le_diff:wheel_revs
cadence cadence              0x4e,channel,None,None,None,None,uint16_le_diff:measurement_time,uint16_le_diff:crank_revs
speed_cadence speed_cadence  0x4e,channel,uint16_le_diff:cadence_measurement_time,uint16_le_diff:crank_revs,uint16_le_diff:speed_measurement_time,uint16_le_diff:wheel_revs
"""

message_calculations="""
crank_torque    float  nm_torque=torque/(32.0*event_count)
crank_torque    float  cadence=2048.0*60*event_count/crank_period
crank_torque    float  power=3.14159*nm_torque*cadence/30

crank_SRM       float  offset=0.0 #This is wrong, should get this from the srm_zero_response msg
crank_SRM       float  elapsed_time=(crank_period/2000.0)
crank_SRM       float  torque_frequency=torque/elapsed_time-offset
crank_SRM       float  nm_torque=10.0*torque_frequency/slope
crank_SRM       float  cadence=2000.0*60*event_count/crank_period
crank_SRM       float  power=3.14159*nm_torque*cadence/30


wheel_torque    float  nm_torque=torque/(32.0*event_count)
wheel_torque    float  wheel_rpm=2048.0*60*event_count/wheel_period
wheel_torque    float  power=3.14159*nm_torque*wheel_rpm/30

battery_voltage float voltage=(descriptive_bits&0x0F)+voltage_lsb/256.0
battery_voltage list  batt_state=['Undefined','New','Good','Ok','Low','Critical','Disallowed0x06','Disallowed0x07'][descriptive_bits>>4&0x07]
battery_voltage int32 operating_time=(operating_time_lsb|(operating_time_1sb<<8)|(operating_time_msb<<16))*[10,2][(descriptive_bits>>7)&0x01]

calibration_pass string autozero_message={0x00:"Autozero_off",0x01:"Autozero_on",0xff:"Autozero_not_supported"}[autozero_status]

manufacturer string radio={0:"AP1",1:"AP2_bug",2:"AP2_fixed",3:"AT3"}[7&(hw_rev>>2)]
manufacturer bool adxl=bool(hw_rev&2)
manufacturer bool rev4=bool(hw_rev&1)

torque_support  bool auto_zero_supported=bool(sensor_configuration&1)
torque_support  bool auto_zero_status=bool(sensor_configuration&2)

product uint32 serial_number=(serial_number_qpod)|(serial_number_spider<<16)

speed           float   rpm=1024*60*(wheel_revs)/measurement_time
cadence         float   rpm=1024*60*(crank_revs)/measurement_time
speed_cadence   float   wheel_rpm=1024*60.0*(wheel_revs)/speed_measurement_time
speed_cadence   float   crank_rpm=1024*60.0*(crank_revs)/cadence_measurement_time

speed           float   timediff=measurement_time/1024.0
cadence         float   timediff=measurement_time/1024.0
speed_cadence   float   timediff=speed_measurement_time/1024.0
crank_torque    float   timediff=crank_period/2048.0
wheel_torque    float   timediff=wheel_period/2048.0
heart_rate      float   timediff=measurement_time/1024.0
"""

import message_set
messages=message_set.MessageSet(messages, message_calculations)
