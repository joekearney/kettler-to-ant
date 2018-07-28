#!/usr/bin/python

import os

import serial
import re
import socket
from ant_model import PowerModel


def find_kettler(debug):
    "returns a Kettler instance for the first Kettler serial port found that replies to ID and ST"

    print "Looking for serial ports for a Kettler device..."

    candidates = [f for f in os.listdir("/dev/") if
                  re.match(r'cu\.KETTLER[0-9A-Z]+-SerialPort', f)]

    print "Found %s candidates" % len(candidates)

    for c in candidates:
        print "Trying: [%s]..." % c
        try:
            serial_name = "/dev/" + c
            serial_port = serial.Serial(serial_name, timeout=1)
            kettler = Kettler(serial_port, debug)
            kettler_id = kettler.getId()
            if len(kettler_id) > 0:
                print "Connected to Kettler [%s] at [%s]" % (kettler_id, serial_name)
                return kettler
        except Exception as e:
            print e
            pass

    raise Exception("No serial port found")


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


def close_safely(thing):
    try:
        thing.close()
    except Exception as e:
        print "Failed to close [%s]: %s" % (str(thing), str(e))


class TcpWriter():
    def __init__(self, host, port, debug, retries=5):
        self.host = host
        self.port = port
        self.debug = debug
        self.totalRetries = retries
        self.tcpSocket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)

    def debugPrint(self, message):
        if self.debug:
            print message

    def __connect(self):
        self.tcpSocket.connect((self.host, self.port))

    def __doWrite(self, message):
        self.tcpSocket.send("%s\n" % message)

    def __resend(self, message, retry_count):
        if retry_count <= self.totalRetries:
            try:
                self.debugPrint("Retries remaining: [%s]..." % retry_count)
                self.__connect()
                self.__doWrite(message)
                return True
            except Exception as e:
                self.debugPrint("Failed to send with exception %s" % str(e))
                self.__resend(message, retry_count + 1)
        else:
            return False

    def write(self, model):
        message = "%s %s" % (str(model.power), str(model.cadence))
        try:
            self.__doWrite(message)
        except Exception as e:
            self.debugPrint("Failed to send message [%s] due to [%s]" % (message, str(e)))
            if not self.__resend(message, 0):
                message = "Failed to send [%s] after [%s] retries" % (message, self.totalRetries)
                print message
                raise Exception(message)


TCP_TARGET_HOST = "192.168.1.195"
TCP_TARGET_PORT = 1234
DEBUG = False

if __name__ == "__main__":
    kettler = find_kettler(DEBUG)
    print 'Kettler found at [%s]' % kettler.serial_port

    kettlerId = kettler.getId()
    if len(kettlerId) > 0:
        print "Connected to Kettler with ID: [%s]" % kettlerId
    else:
        raise Exception("Kettler didn't reply with an ID")

    try:
        writer = TcpWriter(TCP_TARGET_HOST, TCP_TARGET_PORT, DEBUG)
        print "Connected to Ant+ adapter at [%s:%s]" % (TCP_TARGET_HOST, TCP_TARGET_PORT)

        print "Streaming data from Kettler at [%s] to Ant+ adapter at [%s:%s]..." \
              % (kettlerId, TCP_TARGET_HOST, TCP_TARGET_PORT)

        while True:
            model = kettler.readModel()
            if model is not None:
                writer.write(model)

        closeSafely(writer.tcpSocket)
        closeSafely(kettler)
    except KeyboardInterrupt:
        print "Closing connection to Kettler [%s]" % kettlerId
        close_safely(writer.tcpSocket)
        close_safely(kettler)
