#!/usr/bin/python

import time

from time import sleep

from components.ant import PowerModel

from ant_broadcaster import PowerBroadcaster, ANT_DEVICE_TYPE_POWER, AntBroadcaster, FakeAntBroadcaster


def checkRange(min, value, max):
    if value < 0:
        return 0
    elif value > max:
        return max
    else:
        return value


def currentTimeMillis():
    return int(round(time.time() * 1000))


class PowerWriter():
    def __init__(self, transmit_interval_millis, network_key, debug=False, fallback_to_fake=False):
        broadcaster = self.create_broadcaster(network_key, debug, fallback_to_fake)

        self.ant = PowerBroadcaster(broadcaster, debug)
        self.debug = debug
        self.transmitIntervalSecs = transmit_interval_millis / 1000.0
        self.powerModel = PowerModel()
        self.running = False
        self.died = False
        self.__markProgress()
        if self.debug:
            print "Set up PowerWriter with transmitIntervalSecs[%s] deviceId[%s]" % (
                self.transmitIntervalSecs, self.ant.deviceId)

    def create_broadcaster(self, network_key, debug, fallback_to_fake):
        try:
            return AntBroadcaster(network_key, debug, device_type=ANT_DEVICE_TYPE_POWER)
        except Exception as e:
            print "Failed to create real Ant Broadcaster"
            print e
            if fallback_to_fake:
                return FakeAntBroadcaster()
            else:
                raise e


    def __markProgress(self):
        self.lastUpdate = currentTimeMillis()

    def __sendPower(self, power, cadence):
        self.ant.broadcastPower(power, cadence)

    def __sendInLoop(self):
        print "Starting Ant+ writing loop..."
        try:
            while self.running:
                self.__sendPower(self.powerModel.power, self.powerModel.cadence)
                self.__markProgress()
                sleep(self.transmitIntervalSecs)
        except Exception as e:
            self.died = True
            print "Failed with exception: %s" % str(e)
        finally:
            if self.debug:
                print "Closing send loop"
            self.ant.close()

    def updateModel(self, model):
        self.powerModel.power = checkRange(0, model.power, 2048)
        self.powerModel.cadence = checkRange(0, model.cadence, 255)

    def start(self):
        self.running = True
        self.__sendInLoop()

    def awaitRunning(self):
        while not self.running and not self.died:
            sleep(0.1)
        if self.died:
            raise RuntimeError("Runner already died")

    def stop(self):
        self.running = False
