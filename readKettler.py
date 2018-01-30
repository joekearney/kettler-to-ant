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
            sp = serial.Serial(serial_name, timeout=1)
            return sp
        except fail,e:
            print e
            pass

    raise Exception, "No serial port found"

from ant_model import PowerModel

class Kettler():
    def __init__(self, sp):
        self.sp = sp
        self.GET_ID = "ID\r\n"
        self.GET_STATUS = "ST\r\n"

    def rpc(self, message):
        self.sp.write(message)
        self.sp.flush()
        response = self.sp.readline()
#        print "<< received: [" + response + "]"
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
            if destPower != realPower:
                print "Difference: destPower: %s  realPower: %s" % (destPower, realPower)
            return PowerModel(realPower, cadence)
        else:
            print "Received bad status string: [%s]" % statusLine
            return None

    def close(self):
        closeSafely(self.sp)


def closeSafely(thing):
    try:
        thing.close()
    except Exception as e:
        print "Failed to close [%s]: %s" % (str(thing), str(e))

import socket

class TcpWriter():
    def __init__(self, host, port, retries = 5):
        self.host = host
        self.port = port
        self.totalRetries = retries
        self.tcpSocket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)

    def __connect(self):
        self.tcpSocket.connect((self.host, self.port))

    def __doWrite(self, message):
        self.tcpSocket.send("%s\n" % message)

    def __resend(self, message, retryCount):
        if (retryCount <= self.totalRetries):
            try:
                print "Retries remaining: [%s]..." % retryCount
                self.__connect()
                self.__doWrite(message)
                return True
            except Exception as e:
                print "Failed to send with exception %s" % str(e)
                self.__resend(message, retryCount + 1)
        else:
            return False

    def write(self, model):
        message = "%s %s" % (str(model.power), str(model.cadence))
#        print "Sending message [%s]..." % message
        try:
            self.__doWrite(message)
        except Exception as e:
            print "Failed to send message [%s] due to [%s]" % (message, str(e))
            if not self.__resend(message, 0):
                print "Failed to send [%s] after [%s] retries" % (message, self.totalRetries)

from ant_model import PowerRunner
if __name__=="__main__":
    serialPort = findKettlerPath()
    print 'Kettler found at [%s @ %s]' % (serialPort.name, serialPort.port)

    kettler = Kettler(serialPort)

    kettlerId = kettler.getId()
    print "Connected to Kettler with ID: [%s]" % kettlerId

    try:
        writer = TcpWriter("192.168.1.195", 1234)

        while True:
            model = kettler.readModel()
            if model is not None:
                writer.write(model)

        closeSafely(writer.tcpSocket)
        closeSafely(kettler)
    except KeyboardInterrupt:
        closeSafely(writer.tcpSocket)
        closeSafely(kettler)
