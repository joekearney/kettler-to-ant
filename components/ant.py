class PowerModel():
    def __init__(self, power=0, cadence=0):
        self.power = power
        self.cadence = cadence

    def __str__(self):
        return "power[" + str(self.power) + "] cadence[" + str(self.cadence) + "]"
