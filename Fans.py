# =========================================================
# VENTILATORS REGELING (CircuitPython)
# =========================================================

import time
import board
import pwmio

# =========================================================
# VENTILATOR KLASS
# =========================================================
class Fan:
    def __init__(self, pwm_pin, frequency=25000):
        self.pwm = pwmio.PWMOut(pwm_pin, frequency=frequency, duty_cycle=0)
        self.speed = 0.0  # 0.0 – 1.0

    def set_speed(self, speed):
        """Stel ventilatorsnelheid in (0.0 – 1.0)"""
        self.speed = max(0, min(1, speed))
        self.pwm.duty_cycle = int(self.speed * 65535)


# =========================================================
# INITIALISATIE VAN 2 VENTILATORS
# =========================================================
fan1 = Fan(board.GP16)
fan2 = Fan(board.GP17)

# =========================================================
# MAIN LOOP
# =========================================================
while True:
    # Hier kan je logica toevoegen om snelheid te bepalen
    # Voorbeeld: fan1 50%, fan2 80%
    fan1.set_speed(0.5)
    fan2.set_speed(0.8)

    print(f"Fan1 snelheid: {fan1.speed:.2f} | Fan2 snelheid: {fan2.speed:.2f}")

    time.sleep(1)