#!/usr/bin/python

import sys

from ant_support import ant
from ant_support import autoant_writer
import time
import math

antclass=autoant_writer.AutoAntWriter

class AntBroadcaster(antclass):
    def __init__(self, filename, NetworkKey, Debug):
        antclass.__init__(self, quiet=1, silent = not Debug)
        try:
            self.open_ants(filename)
            print "Saving autoant script as \"%s\""%filename
        except AttributeError:
            pass

        self.auto_init()

        self.throbber="-\|/"
        self.dropping=False

        try:
            self.close_channel(0)
        except ant.AntWrongResponseException:
            pass

        self.assign_channel(channel=0,
                            type=0x10,
                            network=1)
        self.set_network_key(network=1, key=NetworkKey)

        deviceId=12345
        print "Broadcasting device ID [12345]"

        self.set_channel_id(channel=0,
                            device=deviceId,
                            device_type_id=11,
                            man_id=5)
        self.set_channel_freq(0, 57)


        self.set_channel_period(0, 8182)

        self.set_channel_search_timeout(0, 40)
        self.open_channel(0)

        self.event_counter=0
        self.event_counter2=0

        self.t0=time.time();
        self.last_time_ticks=-1

        self.power_accum=0

    def close(self):
        self.stopped=True
        self.close_channel(0)

    def broadcastPower(self, power=0, cadence=0):

        self.power_accum+=power

        balance = 50

        self.standard_data=[0x10,
                            (self.event_counter+128)&0xff,
                            0x80|balance,
                            int(cadence), #0xff, # instant cadence
                            int(self.power_accum)&0xff,
                            (int(self.power_accum)>>8)&0xff,
                            int(power)&0xff,
                            (int(power)>>8)&0xff]

        self.event_counter=(self.event_counter+1)%0xff

        print "sending standard data: " + str(self.standard_data)
        self.send_broadcast_data(0,self.standard_data)
        self.wait_tx()

    def wait_tx(self):
        self.sp.setTimeout(0.05)

        while 1:
            try:
                resp=self.receive_message()
                if not resp:
                    continue
                #print resp.name

                if resp.name=='calibration_request':
                    print "Ignoring request for calibration"
                if resp.name=='event_tx':
                    return

            except ant.AntNoDataException:
                pass
