#!/usr/bin/python

import os

import serial
import re

def findKettlerPath():
    "returns serial.Serial instance for the first Kettler serial port found"
    fail=serial.serialutil.SerialException

    print "Looking for serial ports for a Kettler device..."

    candidates = [f for f in os.listdir("/dev/") if re.match(r'cu\.KETTLER[0-9A-Z]+-SerialPort', f)]

    print "Found candidates: " + str(candidates)

    for c in candidates:
        try:
            serial_name = "/dev/" + c
            serialPort = serial.Serial(serial_name, timeout=1)
            return serialPort
        except fail,e:
            print e
            pass

    raise Exception, "No serial port found"

from ant_model import PowerModel

class Kettler():
    def __init__(self, serialPort, debug = False):
        self.serialPort = serialPort
        self.debug = debug
        self.GET_ID = "ID\r\n"
        self.GET_STATUS = "ST\r\n"

    def rpc(self, message):
        self.serialPort.write(message)
        self.serialPort.flush()
        response = self.serialPort.readline().rstrip() # rstrip trims trailing whitespace
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
        closeSafely(self.serialPort)


def closeSafely(thing):
    try:
        thing.close()
    except Exception as e:
        print "Failed to close [%s]: %s" % (str(thing), str(e))

import socket

class TcpWriter():
    def __init__(self, host, port, debug, retries = 5):
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

    def __resend(self, message, retryCount):
        if (retryCount <= self.totalRetries):
            try:
                self.debugPrint("Retries remaining: [%s]..." % retryCount)
                self.__connect()
                self.__doWrite(message)
                return True
            except Exception as e:
                self.debugPrint("Failed to send with exception %s" % str(e))
                self.__resend(message, retryCount + 1)
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

if __name__=="__main__":
    serialPort = findKettlerPath()
    print 'Kettler found at [%s @ %s]' % (serialPort.name, serialPort.port)

    kettler = Kettler(serialPort, DEBUG)

    kettlerId = kettler.getId()
    print "Connected to Kettler with ID: [%s]" % kettlerId

    try:
        writer = TcpWriter(TCP_TARGET_HOST, TCP_TARGET_PORT, DEBUG)
        print "Connected to Ant+ adapter at [%s:%s]" % (TCP_TARGET_HOST, TCP_TARGET_PORT)

        print "Streaming data from Kettler at [%s] to Ant+ adapter at [%s:%s]..." % (kettlerId, TCP_TARGET_HOST, TCP_TARGET_PORT)

        while True:
            model = kettler.readModel()
            if model is not None:
                writer.write(model)

        closeSafely(writer.tcpSocket)
        closeSafely(kettler)
    except KeyboardInterrupt:
        print "Closing connection to Kettler [%s]" % kettlerId
        closeSafely(writer.tcpSocket)
        closeSafely(kettler)
