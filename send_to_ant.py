#!/usr/bin/python

import os
import sys
import time

import time
import math

from ant_model import *

if __name__=="__main__":
    def min(a, b):
        if a < b:
            return a
        else:
            return b

    def startWatchdog(runner):
        while True:
            if runner.died:
                print "Runner died. Letting it close, then exiting..."
                sleep(3)
                print "Exiting now"
                exit(1)

    debug = True

    channelNumber = 0

    p = PowerRunner()

    #startWatchdog(p)

    try:
        p.debug = debug
        p.start()

        while True:
            line = sys.stdin.readline()
            segments = line.split()

            receivedPower = int(segments[0])
            receivedCadence = int(segments[1])
            model = PowerModel(receivedPower, receivedCadence)
            p.updateModel(model)

    except KeyboardInterrupt:
        #traceback.print_stack()
        p.stop()
    finally:
        p.stop()
