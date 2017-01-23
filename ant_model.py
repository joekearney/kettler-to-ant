#!/usr/bin/python

import os
import sys
import time

NetworkKeyAsString = os.getenv('ANT_PLUS_NETWORK_KEY', "00 00 00 00 00 00 00 00")
NetworkKey = [int(i, 16) for i in NetworkKeyAsString.split()]
if sum(NetworkKey) == 0:
    print "Environment variable ANT_PLUS_NETWORK_KEY must be set as space separated hex pairs"
    print "Example: '00 01 02 03 04 05 06 07'"
    exit(1)

from ant_support import ant
from ant_support import autoant_writer
import time
import math

from threading import Thread
from time import sleep

class PowerModel():
    def __init__(self):
        self.power=0
        self.cadence=0

    def __str__(self):
        return "power[" + str(self.power) + "] cadence[" + str(self.cadence) + "]"

from ant_writer import AntBroadcaster

class PowerRunner():
    def __init__(self, channelNumber, powerModel, Debug):
        self.ant = AntBroadcaster("power.ants", NetworkKey, Debug)
        self.powerModel = powerModel
        self.running = False
        self.Debug = Debug

    def sendPower(self, power, cadence):
        print "Sending power model: " + str(self.powerModel)
        self.ant.broadcastPower(power, cadence)

    def sendInLoop(self):
        print "Starting Ant+ writing loop..."
        try:
            while self.running:
                if self.Debug:
                    print "Sending data " + str(self.powerModel)
                self.sendPower(self.powerModel.power, self.powerModel.cadence)
                sleep(0.25)
        finally:
            self.ant.close()

    def start(self):
        thread = Thread(target = self.sendInLoop, args = [])
        thread.start()
        self.running = True

    def stop(self):
        self.running = False
