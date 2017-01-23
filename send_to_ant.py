#!/usr/bin/python

import os
import sys
import time

import time
import math

from ant_model import *

if __name__=="__main__":
    def closeSafely(runners):
        for r in runners:
            try:
                r.ant.close()
            except Exception as e:
                print str(e)

    runners = []
    heart = False

    debug = True

    channelNumber = 0

    powerModel = PowerModel()
    p = PowerRunner(channelNumber, powerModel, debug)

    try:
        p.debug = debug
        p.start()

        if len(runners) > 1:
            print "Only one device is supported. Pick either h or p"
            exit(1)

        while True:
            line = sys.stdin.readline()
            segments = line.split()

            if powerModel:
                powerModel.power = int(segments[0])
                powerModel.cadence = int(segments[1])
                if debug:
                    print "Updated power model: " + str(powerModel)

            if heart:
                h.sendHeart(int(segments[0]), time.time())

    except KeyboardInterrupt:
        p.stop()
    finally:
        p.stop()
