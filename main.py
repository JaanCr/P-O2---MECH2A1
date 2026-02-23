import machine
import time
import onewire
import ds18x20

#code voor sensoren info op te halen

datapin = machine.Pin(22)
datasensor = ds18x20.DS18X20(onewire.OneWire(datapin))