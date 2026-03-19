import time
import board
import pwmio
from digitalio import DigitalInOut, Direction
from adafruit_onewire.bus import OneWireBus
import adafruit_ds18x20
import wifi
import socketpool
import asyncio
import json
from adafruit_httpserver import Server, Request, Response, Websocket, GET, FileResponse

# =========================================================
# CONFIGURATIE sensoren
# =========================================================

SENSOR_MAP = {
    "286C8CBC000000C9": "RechtsBoven",
    "28697054000000F0": "RechtsOnder",
    "28DCB6BF0000007F": "LinksBoven",
    "287F395300000085": "LinksOnder",
    "28E0DCBF00000043": "Buiten"
}


#passwoord en naam van het netwerk
AP_SSID = "Air Carditioning"
AP_PASSWORD = "2026MECH2A1"
NUM_SENSORS = 5

# =========================================================
# KLASSEN (Fan & Peltier)
# =========================================================
class Fan:
    def __init__(self, pwm_pin, frequency=25000):
        self.pwm = pwmio.PWMOut(pwm_pin, frequency=frequency, duty_cycle=0)
        self.speed = 0.0  # 0.0 – 1.0

    def set_speed(self, speed):
        self.speed = max(0, min(1, float(speed)))
        self.pwm.duty_cycle = int(self.speed * 65535)

class PeltierHBridge:
    def __init__(self, pin_in1, pin_in2, pin_pwm, Kp=1.0, Ki=0.05, Kd=0.2):
        self.in1 = DigitalInOut(pin_in1)
        self.in1.direction = Direction.OUTPUT
        self.in2 = DigitalInOut(pin_in2)
        self.in2.direction = Direction.OUTPUT
        self.pwm = pwmio.PWMOut(pin_pwm, frequency=20000, duty_cycle=0)

        self.Kp = Kp
        self.Ki = Ki
        self.Kd = Kd

        self.integral = 0
        self.last_error = 0
        self.target = 20.0
        self.last_direction = 0
        self.last_switch_time = time.monotonic()
        self.switch_delay = 10.0   
        self.last_update = time.monotonic()

    def reset_pid(self):
        self.integral = 0
        self.last_error = 0

    def set_target(self, t):
        self.target = float(t)

    def set_output(self, direction, power):
        power = max(0, min(1, power))
        duty = int(power * 65535)

        if direction == 0:
            self.in1.value = False
            self.in2.value = False
            self.pwm.duty_cycle = 0
            self.last_direction = 0
        elif direction == 1:  # koelen
            self.in1.value = True
            self.in2.value = False
            self.pwm.duty_cycle = duty
        elif direction == -1:  # verwarmen
            self.in1.value = False
            self.in2.value = True
            self.pwm.duty_cycle = duty

    def update(self, current_temp):
        if current_temp is None or current_temp < -20 or current_temp > 50:
            self.set_output(0, 0)
            return 0
        
        now = time.monotonic()
        dt = now - self.last_update
        self.last_update = now
       
        if dt <= 0: return 0

        error = self.target - current_temp
        if abs(error) < 0.1: error = 0
        self.integral += error * dt
        self.integral = max(-50, min(50, self.integral))
        derivative = (error - self.last_error) / dt

        output = self.Kp * error + self.Ki * self.integral + self.Kd * derivative
        self.last_error = error
        
        if abs(output) < 0.05:
            self.set_output(0, 0)
            return 0

        desired_direction = 1 if output > 0 else -1

        if (desired_direction != self.last_direction and now - self.last_switch_time < self.switch_delay):
            self.set_output(0, 0)
            return 0
        
        if output > 0:
            if self.last_direction != 1:
                self.last_switch_time = now
                self.last_direction = 1
                self.reset_pid()
            self.set_output(1, min(1, output))
        else:
            if self.last_direction != -1:
                self.last_switch_time = now
                self.last_direction = -1
                self.reset_pid()
            self.set_output(-1, min(1, -output))

        return output

# =========================================================
# GLOBALE VARIABELEN & INITIALISATIE HARDWARE
# =========================================================
ow_bus = OneWireBus(board.GP22)
mijn_sensoren = []

# Variabelen voor de website (JSON payload)
sensor_data = {
    "temperatureLinks": "--",
    "temperatureRechts": "--",
    "temperatureBuiten": "--",
    "temperatureGem": "--"
}

# Ruwe float data voor de PID-regelaar
ruwe_temps = {"Links": None, "Rechts": None}

websocket = None

# Fans definiëren
fan1 = Fan(board.GP16) # Links
fan2 = Fan(board.GP17) # Rechts

# Peltiers (Aanname: Peltier 0 = Links, Peltier 1 = Rechts)
peltiers = [
    PeltierHBridge(board.GP10, board.GP11, board.GP12), # Links
    PeltierHBridge(board.GP13, board.GP14, board.GP15)  # Rechts
]

def initialiseer_sensoren():
    gevonden_devices = ow_bus.scan()
    sensor_lijst = []
    print(f"Systeem heeft {len(gevonden_devices)} sensoren gevonden.")
    
    for device in gevonden_devices:
        sensor_obj = adafruit_ds18x20.DS18X20(ow_bus, device)
        id_hex = "".join([f"{b:02X}" for b in device.rom])
        naam = SENSOR_MAP.get(id_hex, f"Onbekend_{id_hex[-4:]}")
        sensor_lijst.append({"object": sensor_obj, "naam": naam})
    return sensor_lijst

# =========================================================
# ASYNC TAKEN
# =========================================================
async def lees_sensoren_taak():
    global sensor_data, ruwe_temps
    while True:
        som_binnen = 0.0
        aantal_binnen = 0

        temps = {"LinksBoven": None, "LinksOnder": None, "RechtsBoven": None, "RechtsOnder": None}

        for s in mijn_sensoren:
            naam = s["naam"]
            try:
                temp = s["object"].temperature
                if naam in temps:
                    temps[naam] = temp
                elif naam == "Buiten":
                    sensor_data["temperatureBuiten"] = f"{temp:.1f}"
            except Exception:
                if naam == "Buiten":
                    sensor_data["temperatureBuiten"] = "FOUT"

        # Gemiddelde Links
        links_waarden = [v for v in [temps["LinksBoven"], temps["LinksOnder"]] if v is not None]
        if links_waarden:
            gem_links = sum(links_waarden) / len(links_waarden)
            sensor_data["temperatureLinks"] = f"{gem_links:.1f}"
            ruwe_temps["Links"] = gem_links
            som_binnen += gem_links
            aantal_binnen += 1
        else:
            sensor_data["temperatureLinks"] = "FOUT"
            ruwe_temps["Links"] = None

        # Gemiddelde Rechts
        rechts_waarden = [v for v in [temps["RechtsBoven"], temps["RechtsOnder"]] if v is not None]
        if rechts_waarden:
            gem_rechts = sum(rechts_waarden) / len(rechts_waarden)
            sensor_data["temperatureRechts"] = f"{gem_rechts:.1f}"
            ruwe_temps["Rechts"] = gem_rechts
            som_binnen += gem_rechts
            aantal_binnen += 1
        else:
            sensor_data["temperatureRechts"] = "FOUT"
            ruwe_temps["Rechts"] = None

        if aantal_binnen > 0:
            sensor_data["temperatureGem"] = f"{som_binnen / aantal_binnen:.1f}"
        else:
            sensor_data["temperatureGem"] = "--"

        await asyncio.sleep(2)

 
async def regel_hardware_taak():   #regeling van de teperatuur obv gemeten temp en huidige temp
    while True:
        if ruwe_temps["Links"] is not None:
            peltiers[0].update(ruwe_temps["Links"])
        
        if ruwe_temps["Rechts"] is not None:
            peltiers[1].update(ruwe_temps["Rechts"])
            
        await asyncio.sleep(1)

async def poll_server():
    while True:
        server.poll()
        await asyncio.sleep(0.05)

async def handle_websocket():
    global websocket
    while True:
        if websocket is not None:
            try:
                data = websocket.receive(fail_silently=True)
                if data:
                    print(f"Websocket Inkomend: {data}")
                    
                    if "=" in data:
                        cmd, val = data.split("=")
                        try:
                            val_float = float(val)
                            if cmd == "TEMP_LINKS":
                                peltiers[0].set_target(val_float)
                                print(f"Doel Links -> {val_float}")
                            elif cmd == "TEMP_RECHTS":
                                peltiers[1].set_target(val_float)
                                print(f"Doel Rechts -> {val_float}")

                            # Fans regelen op basis van slider input    
                            elif cmd == "FAN_LINKS":
                                fan1.set_speed(val_float / 100.0) #set speed verwacht waarde tussen 0-1, slider geeft 0-100
                            elif cmd == "FAN_RECHTS":
                                fan2.set_speed(val_float / 100.0)
    
                        except ValueError:
                            pass
                    else:
                        # Toggles voor de Fans
                        if data == "FanOnOffLinks":
                            nieuwe_snelheid = 0.0 if fan1.speed > 0 else 1.0
                            fan1.set_speed(nieuwe_snelheid)
                        elif data == "FanOnOffRechts":
                            nieuwe_snelheid = 0.0 if fan2.speed > 0 else 1.0
                            fan2.set_speed(nieuwe_snelheid)
                        elif data == "TurnOnOff":
                            # Beide ventilatoren tesamen uit zetten
                            nieuwe_snelheid = 0.0 if (fan1.speed > 0 or fan2.speed > 0) else 1.0
                            fan1.set_speed(nieuwe_snelheid)
                            fan2.set_speed(nieuwe_snelheid)
                        

                
                # Huidige temperaturen verzenden als JSON naar websocket
                json_string = json.dumps(sensor_data)
                websocket.send_message(json_string, fail_silently=True)
                
            except Exception as e:
                print("WebSocket fout:", e)
                websocket = None 
        await asyncio.sleep(0.5)

# =========================================================
# NETWERK SETUP & SERVER ROUTES
# =========================================================
print(f"Opstart WiFi AP: {AP_SSID}...")
wifi.radio.start_ap(AP_SSID, AP_PASSWORD)
ap_ip = str(wifi.radio.ipv4_address_ap)

pool = socketpool.SocketPool(wifi.radio)
server = Server(pool, debug=True)

# HTML bestand
@server.route("/", GET)
def serve_html(request: Request):
    return FileResponse(request, "browsertests.html", "text/html")

# CSS bestand
@server.route("/style-webpage.css", GET)
def serve_css(request: Request):
    return FileResponse(request, "style-webpage.css", "text/css")

# JS bestand
@server.route("/webpage.js", GET)
def serve_js(request: Request):
    return FileResponse(request, "webpage.js", "application/javascript")

# JavaScript gebruiken voor de connectie
@server.route("/connect-websocket", GET)
def connect_websocket(request: Request):
    global websocket
    if websocket is not None: 
        websocket.close()
    websocket = Websocket(request)
    return websocket

# =========================================================
# MAIN RUNNER
# =========================================================
async def main():
    global mijn_sensoren
    mijn_sensoren = initialiseer_sensoren()
    
    server.start(ap_ip)
    print(f"Server draait op http://{ap_ip}")
    
    await asyncio.gather(
        poll_server(),
        handle_websocket(),
        lees_sensoren_taak(),
        regel_hardware_taak()
    )

asyncio.run(main())