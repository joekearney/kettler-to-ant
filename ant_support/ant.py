#!/usr/bin/python

import sys,time,os

import serial
import struct
import math,time
import sys
import traceback
import time

ANT_Version = 0x3e
ANT_Capabilities = 0x54
ANT_Channel_Status = 0x52
ANT_Channel_ID = 0x51


ANT_Request_Message = 0x4d
ANT_Unassign_Channel = 0x41
ANT_Assign_Channel = 0x42
ANT_Reset_System = 0x4a
ANT_Broadcast_Data = 0x4e
ANT_Acknowledged_Data = 0x4f
ANT_Extended_Acknowledged_Data = 0x5e
ANT_Extended_Burst_Data = 0x5f
ANT_Burst_Data = 0x50
ANT_Set_Network = 0x46
ANT_Set_Channel_ID = 0x51
ANT_Set_Channel_Period = 0x43
ANT_Set_Channel_Freq = 0x45
ANT_Open_Channel = 0x4b
ANT_Open_Scan_Channel = 0x5b
ANT_Close_Channel = 0x4c
ANT_Set_Channel_Search_Timeout = 0x44
ANT_Set_LP_Search_Timeout = 0x63
ANT_Set_Proximity_Search = 0x71
ANT_Init_Test_Mode = 0x53
ANT_Set_Test_Mode = 0x48
ANT_Enable_Ext_Msgs = 0x66
ANT_Lib_Config = 0x6E
ANTRCT_Set_RSSI_Threshold = 0xC4

ant_ids={}
for ant_message in [x for x in dir() if x.startswith('ANT')]:
    ant_ids[eval(ant_message)]=ant_message

class AntException(Exception): pass
class AntNoDataException(AntException): pass
class AntWrongResponseException(AntException): pass
class AntRxSearchTimeoutException(AntException): pass
class AntResponseTimeoutException(AntException): pass
class AntBurstFailedError(AntException): pass
class AntBurstSequenceError(AntException): pass
class AntTransferRxFailedException(AntException): pass
class AntChecksumException(AntException): pass

interesting_fields={'crank_torque':'%(power)5.1f w %(cadence)d RPM',
                    'quarq_strain':'%(hb1)6d Nm/32',
                    'calibration_pass':'                                            %(calibration_data)4.2f Nm/32',
                    'calibration_fail':'                                            %(calibration_data)4.2f Nm/32',
                    'calibration_request':'                                          ((( request )))',
                    'calibration_request_az':'                                          ((( autozero %(autozero_status)d)))',
                    'battery_voltage':'%(voltage)4.2f V',
                    'standard_power':'%(instant_power)04x %(instant_power)5.1fw %(power)5.1fw %(instant_cadence)d RPM %(event_count_accum)3d',
                    'burst_message':'%(seq)d %(data0)02x %(data1)02x %(data2)02x %(data3)02x %(data4)02x %(data5)02x %(data6)02x %(data7)02x',
                    'response_no_error':'0x%02x(message_id)' }


def print_interesting(m):
    format=interesting_fields[m.name]
    #print format,m
    print format%m
    sys.stdout.flush()

def load_ant_messages():
    import ant_messages
    try:
        import quarq_messages
    except ImportError:
        quarq_messages=None

    import ant_sport_messages

    messages = ant_sport_messages.messages
    if quarq_messages:
        messages += quarq_messages.messages #msgs in here with the same name as ant_sport_messages will overwrite the msg in ant_sport_messages
    messages += ant_messages.messages

    #offending messages that match some more important messages
    #move to the back of the bus!!!
    offending_messages = ['heart_rate','speed','cadence','speed_cadence']
    for m in offending_messages:
        messages.messages_keys.remove(m)
        messages.messages_keys.append(m)

    return messages


class Ant:
    def __init__(self, quiet=False, silent=False):
        self.quiet=quiet
        self.silent=silent
        self.messages = load_ant_messages()

        self.t0 = time.time()

        class NoPortException(Exception): pass

        class NoPort:
            def read(self, n): raise NoPortException
            def write(self, n): raise NoPortException

        self.sp=None # NoPort()

        self.ant_pad='\0\0\0'

        self.rssi_log = {}
        self.rssi_logging = False

    def serial_init(self, port=None):
        if None==port:
            port = guess_ant_serial_port()
        self.sp=port
        self.sp.setTimeout(120) # Sometimes the initial message takes a long time to come in.
        try:
            "RESET and TEST together make up the SBW pair for AT3 module"
            self.sp.setDTR(1) # RESET
            try:
                self.sp.setRTS(0) # TEST
            except IOError: # sometimes setRTS fails, but setDTR still
                            # necessary for resetting.
                pass

            time.sleep(0.1)
            self.sp.setDTR(0)
            self.sp.setRTS(1)

        except IOError: pass

        self.baudrate_probe()
        self.sp.flushInput()

    def network_init(self, port=None):
        self.sp=port

    def auto_init(self):
        if None != self.sp:
            return

        port=try_connecting()
        if port:
            self.network_init(port)
        else:
            self.serial_init(port)

    def baudrate_probe(self):
        timeout=1.5
        # try some baudrate madness
        baudrates=[57600, 19200, 38400, 115200]
        baudrates.remove(self.sp.baudrate)
        baudrates=[self.sp.baudrate]+baudrates
        for baudrate in baudrates:
            if not self.quiet: print "trying",baudrate
            self.sp.setBaudrate(baudrate)
            if self.reset_system_and_probe(timeout):
                return
        raise "Where's Ant?"

    def flush(self):
        self.sp.flushInput()
        self.sp.flushOutput()

    def assemble_message(self,id,data):
        message=[0xa4, # sync
                len(data),
                id] + data
        checksum=reduce(lambda x,y: x^y, message)
        message.append(checksum)

        return message

    def send_message(self,id,data):
        "data is a list of values (as ints)"
        message=self.assemble_message(id,data)

        message=''.join([chr(c) for c in message])
        self.sp.write(message+self.ant_pad)
        self.sp.flush()

        # this sleep is to work around bugs in cp210x driver...
        time.sleep(len(message)*10.0/self.sp.getBaudrate())

        if not self.quiet:
            self.print_message(message)

    def print_message(self, message):
        print "sending message %s [ %s ]"%(ant_ids[ord(message[2])],' '.join(["%02x"%ord(c) for c in message]))

    def get_byte(self):
        while 1:
            b=self.sp.read(1)
            if b=='':
                raise AntNoDataException
            else:
                break

        return ord(b)

    def receive_message(self,source=None,dispose=None,wait=30.0,syncprint=''):
        #wait 0.0 is forever?
        timeout=self.sp.getTimeout()
        self.sp.setTimeout(wait)

        try:
            #print "sp bytes waiting = ", self.sp.inWaiting()
            if (None==source): source=self.get_byte
            if (None==dispose): dispose=self.interpret_message
            x=source()
            while x != 0xa4:
                if x:
                    print syncprint,"lost sync 0x%02x"%x
                x=source()

            datalen=source()
            id=source()
            data=[source() for c in range(datalen)]
            checksum=source()

            if self.assemble_message(id, data)[-1] != checksum:
                print id,data
                raise AntChecksumException

        finally:
            if not wait:
                self.sp.setTimeout(timeout)


        #print ["%x"%x for x in [id]+data]
        m = dispose(id,data)
        if self.rssi_logging:
            self.log_rssi(m)
        return m


    def flush_msg_queue(self):
        while self.sp.inWaiting() > 0:
            m = self.receive_message()

    def get_msg_queue(self):
        from copy import deepcopy
        msgs = []
        while self.sp.inWaiting() > 0:
            msgs.append( deepcopy(self.receive_message()) )
        msgs.append( self.receive_message() )
        return msgs

    def enable_rssi_logging(self, onoff):
        if onoff:
            self.rssi_logging = True
        else:
            self.rssi_logging = False

    def log_rssi(self, message):
        if message.has_key('device_number'):
            #check if device number is already in dict, if not, create it
            if not self.rssi_log.has_key(message['device_number']):
                self.rssi_log[message['device_number']] = []

            if message.has_key('rssi'):
                self.rssi_log[message['device_number']].append(message['rssi'])
            elif message.has_key('power_dbm'):
                self.rssi_log[message['device_number']].append(message['power_dbm'])

    def wait_for_burst(self, timeout=None, channel=1, first_message=None):
        """Waits for ANT burst message.
        Returns the entire message as a list"""

        retdata=[]
        nextseq=0

        while 1:
            if None==first_message:
                m=self.wait_for_response( [[ 'burst_message',
                                             {'channel':channel} ],
                                           [ 'event_transfer_rx_failed',
                                             {'channel':channel} ]],
                                          timeout)
            else:
                m=first_message
                first_message=None

            #print m

            if m.name=='event_transfer_rx_failed':
                raise AntTransferRxFailedException

            #print "sequence",m['seq']
            if (m['seq']&3) != nextseq:
                print m['seq'], nextseq, m['chan_seq']#, m['data']
                raise AntBurstSequenceError

            nextseq={0:1,
                     1:2,
                     2:3,
                     3:1}[m['seq']&3]

            retdata.append(m['burst_data'])
            if m['seq']&4: break

        return reduce(lambda a,b:a+b,retdata)

    def wait_for_response(self, responses, timeout):
        """Waits for certain ANT response(s).
        Each response is a [message_name, { key: val ... } ] list.
        Returns Message class for a response.
        timeout is in seconds, None for forever timeout
        """

        #print "looking for",(",".join([repr(r) for r in responses]))

        def check_response(response,message):

            name, data = response

            if not message: return False
            if name and message.name != name: return False

            for k in data.keys():
                if not message.has_key(k): return False
                if message[k]!=data[k]: return False
            return True

        #print "Timeout =", timeout
        t0=time.time()
        last_unwanted=''
        while (timeout==None) or (time.time()-t0 < timeout):
            #print "time %4.2f %s\r" % (time.time()-t0, timeout)
            #print '>',
            m = self.receive_message(wait=timeout)
            print m
            if not m: continue #raise

            #if not self.quiet:
            #    print m

            if True in [check_response(r,m) for r in responses]:
                #print "Wanted message",m.name
                #print '
                return m

            if m.name==last_unwanted:
                #print ".",
                sys.stdout.flush()
            else:
                if not self.silent:
                    print "unwanted message",m,"out of",(",".join([repr(r) for r in responses]))
                last_unwanted=m.name

        #print "Timeout!"
        raise AntResponseTimeoutException

    def get_msgs(self):
        while 1:
            yield self.receive_message()

    def wait_for_msg(self,name):
        for m in self.get_msgs():
            if m and m.name==name:
                return m

    def wait_for_broadcast_msg(self, chan, timeout=None):

        self.flush_msg_queue()
        t0=time.time()
        while None==timeout or time.time()<t0+timeout:
            m=self.receive_message()
            if m and m.last_message.startswith('\x4e'): return m

        raise AntResponseTimeoutException

    def wait_for_lost_connection(self, timeout=5.0, timelost = 1.0):
        self.flush_msg_queue()
        t0=time.time()
        t_last=time.time()

        while 1:
           if time.time()-t0 > timeout:
               return False #raise AntWrongResponseException
           if time.time()-t_last > timelost:
               return True

           m = self.receive_message()
           #print "%20s   %5.1f  %5.1f" % (m.name, time.time()-t0, time.time()-t_last)
           if not m.name == 'event_rx_fail':
               t_last=time.time()

    def send_broadcast_data(self, chan, data):
        self.send_message(ANT_Broadcast_Data,[chan]+data)

    def send_extended_burst_data(self, chan,
                                 device_id, device_type,
                                 transmission_type,
                                 data):
        self.send_message(ANT_Extended_Burst_Data,
                          [chan,
                           device_id&0xff,
                           (device_id>>8)&0xff,
                           device_type,
                           transmission_type]+data)
        return

    def send_extended_acknowledged_data(self, chan,
                                        device_id, device_type,
                                        transmission_type,
                                        data):
        self.send_message(ANT_Extended_Acknowledged_Data,
                          [chan,
                           device_id&0xff,
                           (device_id>>8)&0xff,
                           device_type,
                           transmission_type]+data)
        return

    def send_acknowledged_data(self, chan, data):
        #print "\nAck waiting",
        #sys.stdout.flush()
        count=0
        while 1:
            try:
                count=count+1
                self.send_message(ANT_Acknowledged_Data,[chan]+data)
                if not self.silent:
                    print "... (%d)"%count,
                    sys.stdout.flush()
                while 1:
                    m=self.wait_for_response([[ 'event_rx_fail', {'channel':chan}],
                                          [ 'event_transfer_tx_completed', {'channel':chan}],
                                          [ 'event_transfer_tx_failed', {'channel':chan}],
                                          [ 'event_rx_search_timeout', {'channel':chan}],
                                          [ 'transfer_in_progress', {'channel':chan}]],
                                         timeout=10)

                    if not self.silent:
                        print m

                    if m.name!='event_rx_fail': break

                if m.name=='transfer_in_progress':
                    # file('/tmp/stop_test',"w").write("1")
                    raise "transfer in progress"
                elif m.name=='event_transfer_tx_completed':
                    if not self.silent:
                        print "+",
                        sys.stdout.flush()
                    return m

                elif m.name=='event_transfer_tx_failed':
                    if not self.silent:
                        print "X",
                        #self.__init__()
                        sys.stdout.flush()

                elif m.name=='event_rx_fail':
                    if not self.silent:
                        print "rx_fail",
                        sys.stdout.flush()
                    pass

                elif m.name=='event_rx_search_timeout' and m['channel']==chan:
                    print "Rx Search Timeout",
                    sys.stdout.flush()
                    pass

            except AntResponseTimeoutException:
                print "Response timeout.",
                sys.stdout.flush()
                pass
            except AntWrongResponseException:
                print "Wrong response.",
                sys.stdout.flush()
                pass
            except AntBurstFailedError:
                print "Burst fail.",
                sys.stdout.flush()
                pass
            except AntNoDataException:
                print "No data.",
                sys.stdout.flush()
                pass

    def send_burst_data(self, chan, indata, progress_func=None, broadcast_messages=[]):
        class TransferTxFailedException(Exception): pass
        class TransferSequenceException(Exception): pass
        class TransferInProgressException(Exception): pass

        def interpret_response(m):
            if m.name=='event_transfer_tx_failed':
                raise TransferTxFailedException
            elif m.name=='transfer_seq_number_error':
                raise TransferSequenceException
            elif m.name=='transfer_in_progress':
                raise TransferInProgressException

            elif m.name in broadcast_messages:
                return False
            elif m.name=='event_transfer_tx_completed':
                return True

        self.flush()
        count=0
        while 1:
            try:
                data=indata[:]
                sequence=0;
                if not self.quiet: print "starting ",count
                while len(data):
                    if progress_func:
                        progress_func(len(data),len(indata))
                    padding=[0xff]*8
                    thispack=(data+padding)[:8]
                    data=data[8:]

                    if len(data)==0:
                        sequence |= 4

                    thispack = thispack + [chr(0xff)]*(8-len(thispack))

                    #print "remain",len(data)

                    #print "thispack",thispack
                    #print "seq",sequence,
                    #print "count",count
                    try:
                        while not self.sp.getCTS():
                            time.sleep(0.001)
                    except IOError:
                        pass
                    t0=time.time()
                    self.send_message(ANT_Burst_Data,[chan + (sequence<<5)]+thispack)

                    #print "s",sequence,
                    sys.stdout.flush()
                    sequence={0:1,
                              1:2,
                              2:3,
                              3:1}[sequence&3]

                    if self.sp.inWaiting():
                        def get_byte_and_print():
                            x=self.get_byte()
                            #print "%02x %d"%(x,self.sp.inWaiting())
                            #sys.stdout.flush()
                            return x
                        #print
                        m=self.receive_message(source=get_byte_and_print)

                        if not self.quiet:
                            print "got message during burst:",
                            print m
                        if interpret_response(m):
                            if progress_func:
                                progress_func(len(data),len(indata))
                            return m

                while 1: # loop waiting for appropriate message
                    while 1: # loop waiting for our-channel message
                        m=self.receive_message()
                        if m['channel']==0:
                            break

                    if not self.silent: print m

                    if interpret_response(m):
                        if progress_func:
                            progress_func(len(data),len(indata))
                        return m

            except (TransferTxFailedException, TransferSequenceException, TransferInProgressException):
                count+=1
                self.flush_msg_queue()
                pass

            #print self.wait_for_response([['flash_crc',{'channel':0}]],None)
        print "done"

    def get_ant_rev(self):
        self.send_message(ANT_Request_Message,[0,ANT_Version])

        resp = self.wait_for_response([['ant_version',{}],
                                       ['ant_version_long',{}],
                                       ['ant_version_11',{}],
                                       ['invalid_message',{'message_id':77}]], 10)

        if resp.name.startswith('ant_version'):
            datakeys=filter(lambda x:x.startswith('data'),resp.keys())
            datakeys.sort(lambda x,y: cmp(int(x[4:]),int(y[4:])))
            string=''.join([chr(resp[k]) for k in datakeys])
            resp['string']=string

        return resp

        #raise "Not supported on the nRF24AP1, fool"
        #return self.request_message(ANT_Version)

    def get_channel_status(self,channel):
        self.send_message(ANT_Request_Message,[channel,ANT_Channel_Status])
        return self.wait_for_response([['channel_status',{'channel':channel}]],10)


    def get_capabilities(self):
        self.send_message(ANT_Request_Message,[0,ANT_Capabilities])
        return self.wait_for_response([['capabilities',{}],
                                       ['capabilities_extended',{}]],10)

    def get_channel_id(self,channel):
        self.send_message(ANT_Request_Message,[channel,ANT_Channel_ID])
        return self.wait_for_response([['channel_id',{'channel':channel}]],3)

    def get_device_id(self,channel):
        return self.get_channel_id(channel)['device_number']

    def wait_no_error(self,channel,message_id):
        m = self.wait_for_response([[None, {'channel':channel,
                                            'message_id':message_id}]], 5)
        #print m
        if m.name=='response_no_error':
            return m
        raise AntWrongResponseException, m.name+' for message type '+ant_ids[message_id]

    def assign_channel(self,channel,type,network,extended=None):
        if None==extended:
            self.send_message(ANT_Assign_Channel,[channel,type,network])
        else:
            self.send_message(ANT_Assign_Channel,[channel,type,network,extended])
        self.wait_no_error(channel,ANT_Assign_Channel)

    def unassign_channel(self,channel):
        self.send_message(ANT_Unassign_Channel,[channel])
        self.wait_no_error(channel,ANT_Unassign_Channel)

    def reset_system_and_probe(self, timeout=10.0):
        self.send_message(ANT_Reset_System,[0])
        return self.probe(timeout=timeout)

    def set_network_key(self, network, key):
        self.send_message(ANT_Set_Network, [network] +key)
        self.wait_no_error(network,ANT_Set_Network)

    def set_channel_id(self, channel, device, device_type_id, man_id):
        self.send_message(ANT_Set_Channel_ID, [channel,
                           device&0xff,
                           (device>>8)&0xff,
                           device_type_id,
                           man_id])
        self.wait_no_error(channel,ANT_Set_Channel_ID)

    def set_channel_period(self, channel, period):
        self.send_message(ANT_Set_Channel_Period, [channel,
                           period&0xff,
                           (period>>8)&0xff])
        self.wait_no_error(channel,ANT_Set_Channel_Period)

    def set_channel_freq(self, channel, freq):
        self.send_message(ANT_Set_Channel_Freq, [channel,
                         freq])
        self.wait_no_error(channel,ANT_Set_Channel_Freq)

    def set_channel_search_timeout(self, channel, search_timeout):
        self.send_message(ANT_Set_Channel_Search_Timeout, [channel,
                               search_timeout])
        self.wait_no_error(channel,ANT_Set_Channel_Search_Timeout)

    def set_low_priority_search_timeout(self, channel, search_timeout):
        self.send_message(ANT_Set_LP_Search_Timeout, [channel,
                                                              search_timeout])
        self.wait_no_error(channel,ANT_Set_LP_Search_Timeout)

    def set_proximity_search(self, channel, level):
        self.send_message(ANT_Set_Proximity_Search, [channel,
                                                     level])
        self.wait_no_error(channel,ANT_Set_Proximity_Search)


    def open_channel(self,channel):
        self.send_message(ANT_Open_Channel, [channel]);
        self.wait_no_error(channel,ANT_Open_Channel)

    def open_rx_scan_channel(self,filler=0):
        self.send_message(ANT_Open_Scan_Channel, [filler]);
        self.wait_no_error(filler, ANT_Open_Scan_Channel);

    def enable_extended_messages(self,enable):
        self.send_message(ANT_Enable_Ext_Msgs, [0, enable]);
        self.wait_no_error(0, ANT_Enable_Ext_Msgs);

    def config_extended_messages(self,rssi=False,rx_timestamp=False,chan_id=False):
        dat = 0
        if rx_timestamp: dat += 0x20
        if rssi: dat += 0x40
        if chan_id: dat += 0x80
        self.send_message(ANT_Lib_Config, [0, dat]);
        self.wait_no_error(0, ANT_Lib_Config);

    def close_channel(self,channel):
        self.send_message(ANT_Close_Channel, [channel]);
        self.wait_no_error(channel,ANT_Close_Channel)
        self.wait_for_response([['event_channel_closed', {'channel':channel}]],
                               5)

    def cw_test_mode(self, freq, power=3):
        self.send_message(ANT_Init_Test_Mode, [0])
        self.wait_no_error(0,ANT_Init_Test_Mode)

        self.send_message(ANT_Set_Test_Mode, [0, power, freq])
        self.wait_no_error(0,ANT_Set_Test_Mode)

    def inner_probe(self):
        timeout=self.sp.getTimeout()
        self.sp.setTimeout(0.1)
        try:
            capabilities=self.get_capabilities()
        except AntNoDataException:
            self.sp.setTimeout(timeout)
            return False
        except AntChecksumException:
            self.sp.setTimeout(timeout)
            return False

        self.sp.setTimeout(timeout)
        return True

    def probe(self, timeout=10):
        t0=time.time()
        while time.time() < t0+timeout:
            if self.inner_probe():
                self.send_message(ANT_Reset_System,[0])
                return True

    def interpret_message(self,id,msgdata):

        #print ''.join(['[%02X]'%x for x in [id]+msgdata])

        m=self.messages.new_message(''.join([chr(x) for x in [id]+msgdata]))

        if m:
            t = time.time()
            m['t'] = t
            m['dt'] = t - self.t0

        if False==m and self.quiet==False:
            print "unknown message 0x%x [%s]"%(id,', '.join(["0x%x"%z for z in msgdata]))
        return m

import os

def guess_ant_baudrate(serial_name):
    br={'COM4':115200,
        '/dev/ttyANT':115200,
        '/dev/ttyANT0':115200,
        '/dev/ttyANT2':115200,
        '/dev/ttyANTRCT':115200,
        '/dev/tty.SLAB_USBtoUART':57600,
        '/dev/ttyANTDEV':57600,
        '/dev/ttyANT_Beacon':115200,
        '/dev/cu.ANTUSBStick.slabvcp':115200}

    return br[serial_name]

def open_serial(serial_name):
    br=guess_ant_baudrate(serial_name)
    #print "trying ",serial_name,br
    return serial.Serial(serial_name, baudrate=br, rtscts=1)

def guess_ant_serial_port():
    "returns serial.Serial instance"
    fail=serial.serialutil.SerialException

    if os.name == 'nt':
        return open_serial('COM4')

    for serial_name in ['/dev/ttyANT0','/dev/ttyANT2','/dev/ttyANTDEV',
                        '/dev/ttyANTRCT', '/dev/tty.SLAB_USBtoUART',
                        '/dev/cu.ANTUSBStick.slabvcp']:
        try:
            sp = open_serial(serial_name)
            print 'ANT on %s' % serial_name
            return sp
        except fail,e:
            #traceback.print_exc()
            print e
            pass

    #import ap2
    #try:
    #    return ap2.FakeSerial()
    #except ValueError:
    #    pass


    raise Exception, "No serial port found"

import socket

class SocketProxy:
    def __init__(self,sock):
        self.sock=sock
        #self.read=sock.recv
        self.write=sock.sendall
        self.portstr="socket"

        #self.logfd=file('/tmp/socket_rx_log','w')
        self.retbuf=''

    def read(self,ct):
        result=self.sock.recv(ct)
        #print >> self.logfd, time.time(),
        #print >> self.logfd, "rx "," ".join(["%02x"%ord(r) for r in result])
        #print "rx "," ".join(["%02x"%ord(r) for r in result]),ct
        return result

    def flushInput(self):
        self.sock.settimeout(0.001)
        try:
            self.sock.recv(4096)
        except socket.timeout:
            pass
        self.sock.settimeout(None)

    def flushOutput(self): pass
    def flush(self): pass
    #def setTimeout(self, timeout): pass
    def setDTR(self, val): pass
    def setRTS(self, val): pass
    def inWaiting(self):
        self.flushInput()
        return 0

    def getCTS(self): return True

    def getBaudrate(self):
        return 54321

    def close(self):
        self.sock.shutdown(socket.SHUT_WR)
        self.sock.close()
        del self.sock
        time.sleep(1)

    def getTimeout(self): return 30
    def setTimeout(self, t): pass

def try_connecting():
    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    for hostname in ['localhost']: #,'192.168.1.47']:
        try:
            s.connect((hostname, 57783))
            return SocketProxy(s)
        except socket.error:
            pass
    return None

def quicktest():
    a=Ant()
    a.auto_init()
    print a.get_capabilities()

if __name__=="__main__":
    quicktest()
