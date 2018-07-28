import os
import re

from serial import Serial, PARITY_NONE

from components.ant import PowerModel


def find_kettler_bluetooth(debug):
    "returns a Kettler instance for the first Kettler serial port found that replies to ID and ST"

    print "Looking for serial ports for a Kettler device..."

    candidates = [f for f in os.listdir("/dev/") if
                  re.match(r'cu\.KETTLER[0-9A-Z]+-SerialPort', f)]

    print "Found %s candidates" % len(candidates)

    for c in candidates:
        print "Trying: [%s]..." % c
        try:
            serial_name = "/dev/" + c
            serial_port = Serial(serial_name, timeout=1)
            kettler = Kettler(serial_port, debug)
            kettler_id = kettler.getId()
            if len(kettler_id) > 0:
                print "Connected to Kettler [%s] at [%s]" % (kettler_id, serial_name)
                return kettler
        except Exception as e:
            print e
            pass

    raise Exception("No serial port found")


def find_kettler_usb(debug):
    "returns a Kettler instance for the first Kettler serial port found that replies to ID and ST"

    print "Looking for serial ports for a Kettler device..."

    candidates = [f for f in os.listdir("/dev/") if
                  re.match(r'.*USB.*', f)]

    print "Found %s candidates" % len(candidates)

    for c in candidates:
        print "Trying: [%s]..." % c
        try:
            serial_name = "/dev/" + c
            serial_port = Serial(serial_name,
                                 baudrate=57600,
                                 parity=PARITY_NONE,
                                 timeout=1)
            kettler = Kettler(serial_port, debug)
            kettler_id = kettler.getId()
            if len(kettler_id) > 0:
                print "Connected to Kettler [%s] at [%s]" % (kettler_id, serial_name)
                return kettler
        except Exception as e:
            print "Failed to connect to [%s]"
            print e
            pass

    raise Exception("No serial port found")


def close_safely(thing):
    try:
        thing.close()
    except Exception as e:
        print "Failed to close [%s]: %s" % (str(thing), str(e))


class Kettler():
    def __init__(self, serial_port, debug=False):
        self.serial_port = serial_port
        self.debug = debug
        self.GET_ID = "ID\r\n"
        self.GET_STATUS = "ST\r\n"

    def rpc(self, message):
        self.serial_port.write(message)
        self.serial_port.flush()
        response = self.serial_port.readline().rstrip()  # rstrip trims trailing whitespace
        return response

    def getId(self):
        return self.rpc(self.GET_ID)

    def readModel(self):
        statusLine = self.rpc(self.GET_STATUS)
        # heartRate cadence speed distanceInFunnyUnits destPower energy timeElapsed realPower
        # 000 052 095 000 030 0001 00:12 030

        segments = statusLine.split()
        if len(segments) == 8:
            cadence = int(segments[1])
            destPower = int(segments[4])
            realPower = int(segments[7])
            if self.debug and destPower != realPower:
                print "Difference: destPower: %s  realPower: %s" % (destPower, realPower)
            return PowerModel(realPower, cadence)
        else:
            print "Received bad status string from Kettler: [%s]" % statusLine
            return None

    def close(self):
        close_safely(self.serial_port)
