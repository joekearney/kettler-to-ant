#!/usr/bin/python
""" Rather than maintain a growing number of confusing scripts, I'm
making a domain-specific language to describe ANT messages.

Format is channel_type message_name datafield[,datafield[, ...]] [text description]

channel_type is one of [power, heartrate, speed, cadence, speed_cadence, quarq, *]

datafield has the format:
  datatype:name

where datatypes are
  uint8:  unsigned 8-bit integer
  uint16_le: unsigned 16-bit integer, little-endian
  sint16_le: signed 16-bit integer, little-endian
  uint16_be: unsigned 16-bit integer, big-endian
  uint16_le_diff: unsigned 16-bit integer accumulator, little-endian
  uint16_be_diff: unsigned 16-bit integer accumulator, big-endian
  uint32_be: unsigned 32-bit integer, big-endian

and names have the following magic values:
  (integer constant): used to decide message type. hexadecimal ok.
  None: skip these bytes, don't attempt to assign meaning

or just:
  name
(datatype defaults to uint8 in this case)

"""

import struct
import sys


class AntTypeException(Exception):
    def __init__(self, type):
        print type, "is unknown"


class AccumValue:
    def __init__(self, parent):
        self.name = parent.name + "_accum"
        self.value = 0
        self.prev_value = 0


class Value:
    def __init__(self, name, type, pos):
        self.name = name
        self.pos = pos
        if type.startswith('uint8'):
            self.width = 1
            self.width_format = 'B'  # byte
            self.endian = ''
        elif type.startswith('sint8'):
            self.width = 1
            self.width_format = 'b'  # byte
            self.endian = ''
        elif type.startswith('uint16'):
            self.width = 2
            self.width_format = 'H'  # short
            if 'be' in type:
                self.endian = '>'
            else:
                self.endian = '<'

        elif type.startswith('sint16'):
            self.width = 2
            self.width_format = 'h'  # short
            if 'be' in type:
                self.endian = '>'
            else:
                self.endian = '<'

        elif type.startswith('uint32'):
            self.width = 4
            self.width_format = 'I'  # int
            if 'be' in type:
                self.endian = '>'
            else:
                self.endian = '<'

        else:
            raise AntTypeException(type)

        # is the name actually an integer?  use it for matching
        try:
            self.match_value = int(name)
        except ValueError:
            try:
                self.match_value = int(name, 16)
            except ValueError:
                self.match_value = None

                if self.name == 'None':
                    self.width_format = 'x' * self.width

                elif 'diff' in type:  # "diff" means the value is a cumulative value
                    self.diff = True
                    self.value = 0
                    self.prev_value = 0
                    self.accum_value = AccumValue(self)
                else:
                    self.diff = False
                    self.value = 0  # None

    def update(self, value):

        if None != self.match_value: return

        if self.diff:
            self.accum_value.prev_value = self.prev_value
            self.accum_value.value = value
            self.value = value - self.prev_value & (256 ** self.width - 1)
            self.prev_value = value
        else:
            self.value = value

    def depends(self):
        return [self.name]


import sys


class CalculatedValue:
    def __init__(self, name, equation, parent, typename=None):
        self.name = name
        self.eq = equation
        self.parent = parent
        self.value = None
        self.typename = typename

    def update(self):
        if sys.version_info[1] < 4:  # python 2.3 and earlier need real dict
            d = {}
            for k in self.parent.keys():
                d[k] = self.parent[k]
        else:
            d = self.parent

        self.value = eval(self.eq, {'struct': struct}, d)

    def depends(self):
        class Sniff(object):
            def __init__(self):
                self.requested = []

            def __getitem__(self, request):
                self.requested.append(request)
                return 1

        s = Sniff()
        self.value = eval(self.eq, {'struct': struct}, s)

        return reduce(lambda x, y: x + y, [self.parent.byname[x].depends() for x in s.requested], [])


import time


class AntMessageType:
    def __init__(self, name, value_desc, desc=''):
        self.name = name
        self.values = []
        self.calculations = []
        self.desc = desc
        self.last_message = None
        self.time = 0
        self.extravalues = {}
        self.touched = []

        pos = 0
        for v in value_desc.split(','):
            if ':' in v:
                type, v = v.split(':')
            else:
                type = 'uint8'

            value = Value(v, type, pos)
            self.values.append(value)
            pos += value.width

        self.byname = {}
        self.keynames = {}
        for v in self.values:
            self.keynames = v.name
            self.byname[v.name] = v
            if v.match_value is None and v.name != "None" and v.diff:
                self.byname[v.name + "_accum"] = v.accum_value

        endiantest = ''.join([s.endian for s in self.values])

        if endiantest == '': endiantest = '<'

        if [e for e in endiantest if e != endiantest[0]]:
            raise AntTypeException('endianness')

        self.struct_format = endiantest[0] + ''.join([s.width_format for s in self.values])
        # print self.struct_format

    def __len__(self):
        return sum([s.width for s in self.values])

    def __getitem__(self, query):
        if self.byname.has_key(query):
            return self.byname[query].value
        if query.endswith("_prev"):
            actual_query = query[:-len("_prev")]
            return self.byname[actual_query + '_accum'].prev_value
        return self.extravalues[query]

    def __setitem__(self, key, value):
        if self.byname.has_key(key):
            raise KeyError
        self.extravalues[key] = value

    def keys(self):
        return ([v.name for v in self.values if 'value' in dir(v)] +
                [v.accum_value.name for v in self.values
                 if 'accum_value' in dir(v)] +
                [c.name for c in self.calculations] +
                self.extravalues.keys())  # ignores don't care and fixed values

    def has_key(self, key):
        return key in self.keys()

    def test(self, message):  # message is list-formatted Ant message

        # print "trying",self.name

        if len(message) != len(self):
            return False

        message_values = list(struct.unpack(self.struct_format, message))
        test_values = [s.match_value for s in self.values if s.name != "None"]

        if len(message_values) != len(test_values):
            raise Exception("Unknown message")

        while (test_values):
            m = message_values.pop(0)
            t = test_values.pop(0)

            # print m,t

            if not (None == t or m == t):
                return False

        return True

    def calc_update(self):
        try:
            [c.update() for c in self.calculations]
        except ZeroDivisionError:
            pass

    def update(self, message):
        self.isrepeat = (message == self.last_message)
        if self.isrepeat: return True

        self.last_message = message
        self.time = time.time()
        values = list(struct.unpack(self.struct_format, message))
        [s.update(values.pop(0)) for s in self.values if s.name != 'None']

        self.calc_update()
        return True

    def add_calculation(self, name, calculation, typename):
        self.calculations.append(CalculatedValue(name, calculation, self, typename))
        self.byname[name] = self.calculations[-1]

    def __repr__(self):
        return '\'%s\': { %s }' % (
            self.name, ', '.join(["'%s':%s" % (k, self[k]) for k in self.keys() if not k[0] == "_"]))

    def pprint(self, offset=''):
        glue = '\n' + offset + '   '
        return '\'%s\':\n%s { %s }' % (self.name, offset, glue.join(["'%s':%s" % (k, self[k]) for k in self.keys()]))


# lpf=file("last_power","w")
last_power = (None, None)


def set_last_power(c):
    global last_power
    raw, power = struct.unpack("<Hh", c)
    power = power * (0.01)
    last_power = power, raw
    # print >>lpf, last_power


class MessageSet:
    def __init__(self, messages='', calculations=''):
        self._read_message_types(messages)
        self._read_calculations(calculations)

    def _read_message_types(self, text):
        self.messages = {}
        self.messages_keys = []  # to preserve order
        for m in text.split('\n'):
            if not m.strip() or m.startswith('#'):  # Allow comments, blank lines
                continue
            x = m.split()
            desc = ' '.join(x[3:])
            blah, name, values = x[:3]

            self.messages[name] = AntMessageType(name, values, desc)
            self.messages_keys.append(name)

    def _read_calculations(self, text):
        for m in text.split('\n'):
            if not m.strip() or m.startswith('#'):  # Allow comments, blank lines
                continue
            x = m.split()
            name = x[0]
            typename = x[1]
            calc = ' '.join(x[2:])

            eq = calc.rstrip().rstrip(";")
            calcname, val = eq.split('=')
            self[name].add_calculation(calcname, val, typename)

    def __add__(self, other):
        ms = MessageSet()

        for mk in self.messages_keys:
            ms.messages[mk] = self.messages[mk]

        for mk in other.messages_keys:
            ms.messages[mk] = other.messages[mk]

        ms.messages_keys = self.messages_keys + other.messages_keys

        return ms

    def keys(self):
        return self.messages_keys

    def has_key(self, key):
        return self.messages.has_key(key)

    def __getitem__(self, query):
        return self.messages[query]

    def check_rssi_message(self, message):
        # RSSI message, transform to regular message
        m_c = map(ord, message)
        # print "m_c:",map(lambda x:"%02X"%x,m_c)
        # ANTRCT RSSI Broadcast Data, Ack Data,Burst Data
        if len(m_c) == 18 and m_c[0] in [0xc1, 0xc2, 0xc3]:
            # print 'ANTRCT RSSI Broadcast Data, Ack Data,Burst Data'
            replacement_message = [m_c[0] - (0xc1 - 0x4e), m_c[1]] + m_c[10:]
            mess = self._new_message(''.join(map(chr, replacement_message)))
            mess['channel_number'] = m_c[1]
            mess['device_number'] = m_c[2] + (m_c[3] << 8)
            mess['device_type_id'] = m_c[4]
            mess['transmission_type'] = m_c[5]
            mess['power_raw'] = m_c[6] + (m_c[7] << 8)
            mess['power_dbm'] = (m_c[8] + (m_c[9] << 8))
            if m_c[9] & 0x80:
                mess['power_dbm'] -= 0x10000
            mess['power_dbm'] /= 100.0
            # return mess
        # Don't know, ANTRCT RSSI Power
        elif m_c[0] in [0xc1, 0xc2, 0xc3]:
            # print 'ANTRCT RSSI Power'
            raise Exception("WTF?")
        # ANTRCT RSSI Tx Transfer Complete Event
        elif len(m_c) == 8 and m_c[0] == 0x40 and m_c[2] == 0x1 and m_c[3] == 0x10:
            # print 'ANTRCT RSSI Tx Transfer Complete Event'
            replacement_message = m_c[0:4]
            replacement_message[3] = 0x05  ##This is a little hackey, makes the
            # message match the generic 'event_transfer_tx_completed' message
            mess = self._new_message(''.join(map(chr, replacement_message)))
            mess['power_raw'] = m_c[4] + (m_c[5] << 8)
            mess['power_dbm'] = (m_c[6] + (m_c[7] << 8))
            if m_c[7] & 0x80:
                mess['power_dbm'] -= 0x10000
            mess['power_dbm'] /= 100.0
            # return mess
        # Extended Ant Messages, RSSI, no timestamp, no channel id
        elif (len(m_c) in [14, 15]) and m_c[10] == 0x40:
            # print 'Extended Ant Messages, RSSI, no timestamp, no channel id'
            # this is the new style of rssi messages (extended, rssi only)
            # print "m_c:",m_c
            replacement_message = m_c[0:10]  # 0x10 --> 0x05
            mess = self._new_message(''.join(map(chr, replacement_message)))
            mess['msg_type'] = m_c[11]
            if m_c[12] & 0x80:
                mess['rssi'] = m_c[12] - 0x100
            else:
                mess['rssi'] = m_c[12]
            if m_c[13] & 0x80:
                mess['rssi_thresh'] = m_c[13] - 0x100
            else:
                mess['rssi_thresh'] = m_c[13]
            # return mess
        # Extended Ant Messages, RSSI, Channel ID, no timestamp
        elif (len(m_c) in [18]) and m_c[10] == 0xC0:
            # print 'Extended Ant Messages, RSSI, Channel ID, no timestamp'
            # this is the new style of rssi messages (extended, rssi only)
            # print "m_c:",m_c
            replacement_message = m_c[0:10]
            mess = self._new_message(''.join(map(chr, replacement_message)))
            mess['device_number'] = m_c[12] * 256 + m_c[11]
            mess['device_type'] = m_c[13]
            mess['transmission_type'] = m_c[14]
            mess['msg_type'] = m_c[15]
            if m_c[16] & 0x80:
                mess['rssi'] = m_c[16] - 0x100
            else:
                mess['rssi'] = m_c[16]
            if m_c[17] & 0x80:
                mess['rssi_thresh'] = m_c[17] - 0x100
            else:
                mess['rssi_thresh'] = m_c[17]
            # return mess
        # Extended Ant Messages, RSSI, Channel ID, Timestamp
        elif (len(m_c) in [20]) and m_c[10] == 0xE0:
            # print 'Extended Ant Messages, RSSI, Channel ID, Timestamp'
            # this is the new style of rssi messages (extended, rssi only)
            # print "m_c:",m_c
            replacement_message = m_c[0:10]
            mess = self._new_message(''.join(map(chr, replacement_message)))
            mess['device_number'] = m_c[12] * 256 + m_c[11]
            mess['device_type'] = m_c[13]
            mess['transmission_type'] = m_c[14]
            mess['msg_type'] = m_c[15]
            if m_c[16] & 0x80:
                mess['rssi'] = m_c[16] - 0x100
            else:
                mess['rssi'] = m_c[16]
            if m_c[17] & 0x80:
                mess['rssi_thresh'] = m_c[17] - 0x100
            else:
                mess['rssi_thresh'] = m_c[17]
            mess['rx_timestamp'] = m_c[19] * 256 + m_c[18]
            # return mess
        # Flag extended
        elif m_c[0] in [0x4e, 0x4f, 0x50] and len(m_c) > 10 and m_c[10] in [0x80, 0xe0]:
            "Flagged extended message"
            replacement_message = m_c[0:10]
            mess = self._new_message(''.join(map(chr, replacement_message)))
            mess['device_number'] = m_c[11] + (m_c[12] << 8)
            mess['device_type_id'] = m_c[13]
            mess['transmission_type'] = m_c[14]
            return mess
        else:
            mess = self._new_message(message)
            # return

        # print mess
        return mess

    def new_message(self, message):
        return self.check_rssi_message(message)

    def _new_message(self, message):
        """Interprets new message data.  Returns False if no match is found"""
        for m in self.messages_keys:
            if self[m].test(message):
                self[m].update(message)
                return self[m]
        return False


import pprint

if __name__ == '__main__':
    print "implement me"
