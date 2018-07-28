# Kettler Ant+ Support

This project makes a Kettler Racer 9 usable with any software requiring Ant+, for example Zwift or Sufferfest.

It reads power and cadence data from a Kettler indoor bike over USB (or bluetooth, though that's harder to get set up), and writes that to an Ant+ dongle.

Just run `kettler-ant-adapter.py`. It tries to use any USB device at `/dev/.*USB.*`.