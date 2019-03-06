#!/usr/bin/python

from ant_support import ant

ANT_NETWORK = 1

ANT_DEVICE_TYPE_POWER = 11
ANT_DEVICE_TYPE_FITNESS_EQUIPMENT = 0x11
ANT_FITNESS_EQUIPMENT_TYPE_STATIONARY_BIKE = 21

ANT_POWER_PROFILE_POwER_PAGE = 0x10
ANT_FITNESS_EQUIPMENT_PROFILE_GENERAL_DATA_PAGE = 0x10
ANT_FITNESS_EQUIPMENT_PROFILE_GENERAL_SETTINGS_PAGE = 0x17
ANT_FITNESS_EQUIPMENT_PROFILE_STATIONARY_BIKE_DATA_PAGE = 0x15
ANT_FITNESS_EQUIPMENT_PROFILE_TRAINER_DATA_PAGE = 0x19
ANT_FITNESS_EQUIPMENT_PROFILE_TARGET_POWER_PAGE = 0x31  # head unit -> device


class FakeAntBroadcaster():
    def __init__(self):
        self.deviceId = 1

    def close(self):
        print "Closing broadcaster"

    def wait_tx(self):
        pass

    def send_broadcast_data(self, chan, data):
        print "Sending chan[%s] data[%s]" % (chan, ' '.join(str(x) for x in data))


class AntBroadcaster(ant.Ant):
    def __init__(self, network_key, debug, device_type):
        ant.Ant.__init__(self, quiet=not debug, silent=False)

        self.auto_init()

        try:
            self.close_channel(0)
        except ant.AntWrongResponseException:
            pass

        self.assign_channel(channel=0,
                            type=ANT_POWER_PROFILE_POwER_PAGE,
                            network=ANT_NETWORK)
        self.set_network_key(network=ANT_NETWORK, key=network_key)

        self.deviceId = 12329 + device_type
        print "Initialised broadcaster for deviceId[%s] of type[%s]" % (self.deviceId, device_type)

        self.set_channel_id(channel=0,
                            device=self.deviceId,
                            device_type_id=device_type,
                            man_id=5)
        self.set_channel_freq(0, 57)
        self.set_channel_period(0, 8182)
        self.set_channel_search_timeout(0, 40)
        self.open_channel(0)

    def close(self):
        self.stopped = True
        self.close_channel(0)

    def wait_tx(self):
        self.sp.setTimeout(0.05)

        while 1:
            try:
                resp = self.receive_message(wait=2.0)
                if not resp:
                    continue

                if resp.name == 'calibration_request':
                    print "Ignoring request for calibration"
                if resp.name == 'event_tx':
                    return

            except ant.AntNoDataException:
                pass


class PowerBroadcaster():
    def __init__(self, ant_broadcaster, Debug):
        self.ant_broadcaster = ant_broadcaster
        self.deviceId = ant_broadcaster.deviceId
        self.Debug = Debug
        self.power_accum = 0
        self.event_counter = 0
        self.lastPowerUpdate = -1
        self.lastCadenceUpdate = -1

    def broadcastPower(self, power=0, cadence=0):
        self.power_accum += power
        balance = 50

        data = [
            ANT_POWER_PROFILE_POwER_PAGE,
            (self.event_counter + 128) & 0xff,
            0x80 | balance,
            int(cadence),  # 0xff, # instant cadence
            int(self.power_accum) & 0xff,
            (int(self.power_accum) >> 8) & 0xff,
            int(power) & 0xff,
            (int(power) >> 8) & 0xff
        ]

        self.event_counter = (self.event_counter + 1) % 0xff

        if self.Debug or (power != self.lastPowerUpdate) or (cadence != self.lastCadenceUpdate):
            print "Sending data for device[%s]: %40s for power[%s] cadence[%s]" % (
                self.deviceId, str(data), power, cadence)
        self.ant_broadcaster.send_broadcast_data(0, data)
        self.lastPowerUpdate = power
        self.lastCadenceUpdate = cadence
        self.ant_broadcaster.wait_tx()

    def close(self):
        self.ant_broadcaster.close()


class FitnessEquipmentBroadcaster(AntBroadcaster):
    def __init__(self, filename, NetworkKey, Debug):
        AntBroadcaster.__init__(self, NetworkKey, Debug, deviceType=ANT_DEVICE_TYPE_FITNESS_EQUIPMENT)

    def broadcastGeneralDataPage(self, elapsedTimeSeconds, distanceMetres, speedMetresPerSec, heartRate):
        # general data page for a FitnessEquipment. This doesn't need an event counter

        # speed in units of 0.001m/s, rollover at 65534
        speedInFunnyUnits = speedMetresPerSec * 1000
        speedLsb = speedInFunnyUnits & 0xff
        speedMsb = (speedInFunnyUnits >> 8) & 0xff

        capabilitiesBitField = (
                2 << 4 |  # HR data source is 5kHz HRM
                1 << 2 |  # distance transmission is enabled
                1  # speed is virtual, not real
        )

        data = [
            ANT_FITNESS_EQUIPMENT_PROFILE_GENERAL_DATA_PAGE,
            ANT_FITNESS_EQUIPMENT_TYPE_STATIONARY_BIKE,
            (elapsedTimeSeconds % 64) * 4,  # time in units of 0.25s, rollover at 64s
            distanceMetres % 256,  # distance in metres, rollover at 256m
            speedLsb,
            speedMsb,
            capabilitiesBitField
        ]

        self.send_broadcast_data(0, data)
        self.wait_tx()

    def broadcastPower(self, power=0, cadence=0):
        self.power_accum += power
        balance = 50

        data = [
            ANT_POWER_PROFILE_POwER_PAGE,
            (self.event_counter + 128) & 0xff,
            0x80 | balance,
            int(cadence),  # 0xff, # instant cadence
            int(self.power_accum) & 0xff,
            (int(self.power_accum) >> 8) & 0xff,
            int(power) & 0xff,
            (int(power) >> 8) & 0xff
        ]

        self.event_counter = (self.event_counter + 1) % 0xff

        print "sending standard data: " + str(data)
        self.send_broadcast_data(0, data)
        self.wait_tx()
