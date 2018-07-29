#!/usr/bin/python

import os
import sys
import traceback
import threading
from threading import Thread

from components.ant_writer import *
from components import kettler_serial
from components.ant import PowerModel

MAX_TIME_BETWEEN_UPDATES = 5000
TRANSMIT_INTERVAL_MILLIS = 250
MAX_CONSECUTIVE_BAD_LINES = 100
MAX_CONSECUTIVE_EMPTY_LINES = 5
DEBUG = False

ANT_PLUS_NETWORK_KEY_STRING = os.getenv('ANT_PLUS_NETWORK_KEY', "00 00 00 00 00 00 00 00")
ANT_PLUS_NETWORK_KEY = [int(i, 16) for i in ANT_PLUS_NETWORK_KEY_STRING.split()]
if sum(ANT_PLUS_NETWORK_KEY) == 0:
    print "Environment variable ANT_PLUS_NETWORK_KEY must be set as space separated hex pairs"
    print "The standard Ant+ network key can be obtained from here: " \
          "https://www.thisisant.com/developer/ant-plus/ant-plus-basics/network-keys"
    print "Example: '00 01 02 03 04 05 06 07'"
    exit(1)
elif DEBUG:
    print "Found Ant+ network key: %s" % ANT_PLUS_NETWORK_KEY_STRING


def quit_on_problem(reason, antWriter):
    print "WATCHDOG QUIT TRIGGERED because ANT+ writer thread %s. Letting it close, then exiting..." % reason
    antWriter.stop()
    sleep(1)
    printStackTraces()
    print "Watchdog is done"


def currentTimeMillis():
    return int(round(time.time() * 1000))


def printStackTraces():
    print >> sys.stderr, "\n*** STACKTRACE - START ***\n"
    code = []
    threadList = threading.enumerate()
    for threadId, stack in sys._current_frames().items():
        thread = filter(lambda x: x.ident == threadId, threadList)[0]
        code.append("\n# Thread: id[%s] name[%s] daemon[%s]" % (threadId, thread.name, thread.daemon))
        for filename, lineno, name, line in traceback.extract_stack(stack):
            code.append('  File: "%s", line %d, in %s' % (filename,
                                                          lineno, name))
            if line:
                code.append("    %s" % (line.strip()))

    for line in code:
        print >> sys.stderr, line
    print >> sys.stderr, "\n*** STACKTRACE - END ***\n"


def runWatchdog(antWriter):
    watchdogRunning = True
    while watchdogRunning:
        sleep(1)

        if antWriter.died:
            watchdogRunning = False
            quit_on_problem("died", antWriter)

        if not antWriter.running:
            watchdogRunning = False
            antWriter.stop()

        millisSinceLastUpdate = (currentTimeMillis() - antWriter.lastUpdate)
        if millisSinceLastUpdate > MAX_TIME_BETWEEN_UPDATES:
            watchdogRunning = False
            quit_on_problem("made no progress for %sms" % millisSinceLastUpdate, antWriter)


def readFromKettler(antWriter, kettler, debug):
    while True:
        model = kettler.readModel()
        if model is not None:
            antWriter.updateModel(model)


def detectInterrupt(antWriter):
    try:
        while True:
            sys.stdin.readline()
    except KeyboardInterrupt:
        print "Detected Ctrl-C, quitting"
        antWriter.stop()


def readFromStdin(antWriter, debug):
    try:
        badLinesReceived = 0
        emptyLinesReceived = 0

        while antWriter.running:
            line = sys.stdin.readline()
            segments = line.split()

            if len(segments) == 2:
                receivedPower = int(segments[0])
                receivedCadence = int(segments[1])
                badLinesReceived = 0
                emptyLinesReceived = 0
                model = PowerModel(receivedPower, receivedCadence)
                antWriter.updateModel(model)
            elif len(line) == 0:
                emptyLinesReceived += 1
                if debug:
                    print "Received empty line, ignoring"
            else:
                badLinesReceived += 1
                print "[%s] Received bad line with [%s] characters: %s" % (badLinesReceived, len(line), line)

            if badLinesReceived >= MAX_CONSECUTIVE_BAD_LINES or emptyLinesReceived >= MAX_CONSECUTIVE_EMPTY_LINES:
                print "Received [%s] bad and [%s] empty consecutive lines, and interpreting that as a QUIT" % (
                    badLinesReceived, emptyLinesReceived)
                sys.stdin.close()
                break

    except KeyboardInterrupt:
        antWriter.stop()
    except Exception as e:
        print "Failed with exception: %s" % str(e)
        antWriter.stop()
    finally:
        antWriter.stop()


def runMain(antWriter, kettler):
    print "Creating worker threads"

    # this thread reads from the in-memory power model and writes to Ant+
    antWriteThread = Thread(target=antWriter.start, args=[])
    antWriteThread.setDaemon(True)
    antWriteThread.setName("ant-write")

    # this thread watches that progress continues to be made
    watchdogThread = Thread(target=runWatchdog, args=(antWriter,))
    watchdogThread.setDaemon(True)
    watchdogThread.setName("watchdog")

    # this thread reads input from the Kettler and pushes it into the power model
    inputThread = Thread(target=readFromKettler, args=(antWriter, kettler, DEBUG,))
    inputThread.setDaemon(True)
    inputThread.setName("kettler-to-model")

    # this thread checks for Ctrl-C and shuts down
    interruptThread = Thread(target=detectInterrupt, args=(antWriter,))
    interruptThread.setDaemon(True)
    interruptThread.setName("interrupt-detector")

    interruptThread.start()
    antWriteThread.start()
    antWriter.awaitRunning()
    watchdogThread.start()
    inputThread.start()

    watchdogThread.join()


if __name__ == "__main__":
    antWriter = None
    try:
        print "Creating Ant writer..."
        antWriter = PowerWriter(transmitIntervalMillis=TRANSMIT_INTERVAL_MILLIS,
                                networkKey=ANT_PLUS_NETWORK_KEY,
                                debug=DEBUG)

        print "Creating Kettler interface..."
        kettler = kettler_serial.find_kettler_usb(DEBUG)
        print "Found Kettler at [%s]" % kettler.getId()

        runMain(antWriter, kettler)
    except KeyboardInterrupt:
        if antWriter:
            antWriter.stop()
    except Exception as e:
        print "Failed with exception: %s" % str(e)
        if antWriter:
            antWriter.stop()
        raise e
    finally:
        if antWriter:
            antWriter.stop()

    if DEBUG:
        print "Finished main"
        printStackTraces()
