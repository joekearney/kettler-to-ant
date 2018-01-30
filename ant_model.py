#!/usr/bin/python

import os
import sys
import time

NetworkKeyAsString = os.getenv('ANT_PLUS_NETWORK_KEY', "00 00 00 00 00 00 00 00")
NetworkKey = [int(i, 16) for i in NetworkKeyAsString.split()]
if sum(NetworkKey) == 0:
    print "Environment variable ANT_PLUS_NETWORK_KEY must be set as space separated hex pairs"
    print "The standard Ant+ network key can be obtained from here: https://www.thisisant.com/developer/ant-plus/ant-plus-basics/network-keys"
    print "Example: '00 01 02 03 04 05 06 07'"
    exit(1)

from ant_support import ant
from ant_support import autoant_writer
import time
import math

from threading import Thread
from time import sleep

class PowerModel():
    def __init__(self, power = 0, cadence = 0):
        self.power = power
        self.cadence = cadence

    def __str__(self):
        return "power[" + str(self.power) + "] cadence[" + str(self.cadence) + "]"

from ant_writer import PowerBroadcaster

class PowerRunner():
    def __init__(self, Debug = False):
        self.ant = PowerBroadcaster("power.ants", NetworkKey, Debug)
        self.powerModel = PowerModel()
        self.running = False
        self.Debug = Debug
        self.died = False

    def __sendPower(self, power, cadence):
        print "Sending power model: " + str(self.powerModel)
        self.ant.broadcastPower(power, cadence)

    def __sendInLoop(self):
        print "Starting Ant+ writing loop..."
        try:
            while self.running:
                if self.Debug:
                    print "Sending data " + str(self.powerModel)
                self.__sendPower(self.powerModel.power, self.powerModel.cadence)
                sleep(0.25)
        except Exception as e:
            self.died = True
            print "Failed with exception [%s]: %s" % (str(thing), str(e))
        finally:
            self.ant.close()

    def updateModel(self, model):
        self.powerModel.power = min(model.power, 2048)
        self.powerModel.cadence = min(model.cadence, 255)

    def start(self):
        thread = Thread(target = self.__sendInLoop, args = [])
        thread.start()
        self.running = True

    def stop(self):
        self.running = False
