# Kettler Ant+ Support

This project has scripts to do a few things:

* script `readKettler.py` that reads data from a Kettler Racer 9 over a serial port, writing out the power and cadence values over TCP
* script `send_to_ant.py` that reads power and cadence from stdin, and writes that to an Ant+ dongle.

This allows power/cadence data from a Kettler Racer 9 (or just from stdin!) to be presented as an Ant+ device. Then it can be received by any normal head, such as a Garmin or another Ant+ dongle for Zwift.
