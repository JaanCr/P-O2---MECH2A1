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

# passwoord en naam van het netwerk
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
    #def __init__(self, pin_rpwm, pin_lpwm, Kp=1.0, Ki=0.05, Kd=0.2):
    def __init__(self, pin_rpwm, pin_lpwm, deadband = 0.5):
        self.rpwm = pwmio.PWMOut(pin_rpwm, frequency=20000, duty_cycle=0)
        self.lpwm = pwmio.PWMOut(pin_lpwm, frequency=20000, duty_cycle=0)

        #self.Kp = Kp    #verwijder als Hysteris
        #self.Ki = Ki    #
        #self.Kd = Kd    #

        self.deadband = deadband
        self.target = 20.0
        self.enabled = False # System starts as OFF

        #self.integral = 0       #verwijder als Hysteris
        self.last_error = 0
        
        self.current_state = 0
        self.last_switch_time = time.monotonic()
        self.switch_delay = 4.0  
        self.is_switching = False  
        self.last_update = time.monotonic()

    #def reset_pid(self):        # verwijder als Hysteris + verwijder in stopall logic
    #    self.integral = 0
    #    self.last_error = 0

    def set_target(self, t):
        self.target = float(t)

    def set_output(self, direction, power):
        #power = max(0, min(1, power))       # verwijder als Hysteris
        duty = int(power * 65535)

        if direction == 0:
            self.rpwm.duty_cycle = 0
            self.lpwm.duty_cycle = 0
        elif direction == 1:   # koelen
            self.rpwm.duty_cycle = duty
            self.lpwm.duty_cycle = 0
        elif direction == -1:  # verwarmen
            self.rpwm.duty_cycle = 0
            self.lpwm.duty_cycle = duty

    def update(self, current_temp):
        if current_temp is None or not self.enabled:
            self.set_output(0, 0)
            self.current_state = 0
            return

        now = time.monotonic()

        if self.is_switching:
            self.set_output(0, 0)
            if now - self.last_switch_time >= self.switch_delay:
                print("switching klaar")
                self.is_switching = False
            return

        # --- Hysteresis Logic ---
        # Cooling Logic
        if current_temp > (self.target + self.deadband):
            print("cooling")
            if self.current_state == -1: 
                self._start_switch_pause()
            else:
                self.set_output(1, 1.0) 
                self.current_state = 1
                
        # Heating Logic
        elif current_temp < (self.target - self.deadband):
            print("heating")
            if self.current_state == 1: 
                self._start_switch_pause()
            else:
                self.set_output(-1, 1.0) 
                self.current_state = -1
                
        # --- OFF als in deadband ---
        # Heating deadband
        elif abs(self.target - current_temp) < (self.deadband * 3 / 4) and self.current_state == -1:
            print("deadband")
            self.set_output(0, 0)
            self.current_state = 0

        # Cooling deadband
        elif abs(self.target - current_temp) < (self.deadband / 4) and self.current_state == 1:
            print("deadband")
            self.set_output(0, 0)
            self.current_state = 0

    def _start_switch_pause(self):
        print("switching")
        self.set_output(0, 0)
        self.current_state = 0
        self.is_switching = True
        self.last_switch_time = time.monotonic()

    #def update(self, current_temp):
    #    if current_temp is None or current_temp < -20 or current_temp > 50 or not self.enabled:
    #        self.set_output(0, 0)
    #        return 0

    #    now = time.monotonic()
    #    dt = now - self.last_update
    #    self.last_update = now

    #    if dt <= 0: return 0

        # Ompolingsveiligheid
    #    if self.is_switching:
    #        self.set_output(0, 0)
    #        if now - self.last_switch_time >= self.switch_delay:
    #            self.is_switching = False
    #            self.reset_pid()
    #            print("Peltier herstart na polariteitswissel.")
    #        else:
    #            return 0 

    #    error = self.target - current_temp
    #    if abs(error) < 0.1: error = 0
    #    self.integral += error * dt
    #    self.integral = max(-50, min(50, self.integral))
    #    derivative = (error - self.last_error) / dt

    #    output = self.Kp * error + self.Ki * self.integral + self.Kd * derivative
    #    self.last_error = error

    #    if abs(output) < 0.05:
    #        self.set_output(0, 0)
    #        return 0

    #    desired_direction = 1 if output > 0 else -1

    #    if desired_direction != self.current_state and self.current_state != 0:
    #        print(f"Polariteitswissel! Pauze van {self.switch_delay}s.")
    #        self.set_output(0, 0)
    #        self.last_switch_time = now
    #        self.is_switching = True
    #        self.current_state = 0
    #        return 0

    #    if output > 0:
    #        self.current_state = 1
    #        self.set_output(1, min(1, output))
    #    else:
    #        self.current_state = -1
    #        self.set_output(-1, min(1, -output))

    #    return output

# =========================================================
# GLOBALE VARIABELEN & INITIALISATIE
# =========================================================
ow_bus = OneWireBus(board.GP21)
mijn_sensoren = []

sensor_data = {
    "temperatureLinks": "--",
    "temperatureLinksBoven": "--",
    "temperatureLinksOnder": "--",
    "temperatureRechts": "--",
    "temperatureRechtsBoven": "--",
    "temperatureRechtsOnder": "--",
    "temperatureBuiten": "--",
    "temperatureGem": "--",
    "statusLinksBoven": False,
    "statusLinksOnder": False,
    "statusRechtsBoven": False,
    "statusRechtsOnder": False,
    "statusBuiten": False,
    "fanStatusLinks": False,
    "fanStatusRechts": False,
    "peltierEnabledLinks": False,
    "peltierEnabledRechts": False,
    "queue_pos": 0 
}

ruwe_temps = {"Links": None, "Rechts": None}

all_clients = []

fan1 = Fan(board.GP13) # Links
fan2 = Fan(board.GP18) # Rechts

last_Speed_Fan_Links = 0.5   
last_Speed_Fan_Rechts = 0.5  

peltiers = [
    PeltierHBridge(board.GP14, board.GP15),  # Links
    PeltierHBridge(board.GP16, board.GP17)   # Rechts
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

        for key in ["statusLinksBoven", "statusLinksOnder", "statusRechtsBoven", "statusRechtsOnder", "statusBuiten"]:
                sensor_data[key] = False

        temps = {"LinksBoven": None, "LinksOnder": None, "RechtsBoven": None, "RechtsOnder": None}

        for s in mijn_sensoren:
            naam = s["naam"]
            try:
                temp = s["object"].temperature
                status_key = "status" + naam
                if status_key in sensor_data: sensor_data[status_key] = True
                if naam in temps: temps[naam] = temp
                elif naam == "Buiten": sensor_data["temperatureBuiten"] = f"{temp:.1f}"
            except Exception:
                if naam == "Buiten": sensor_data["temperatureBuiten"] = "FOUT"

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

        # LinksBoven
        linksBoven = temps["LinksBoven"]
        if linksBoven is not None:
            sensor_data["temperatureLinksBoven"] = f"{linksBoven:.1f}"
        else:
            sensor_data["temperatureLinksBoven"] = "--"
        
        # LinksOnder
        linksOnder = temps["LinksOnder"]
        if linksOnder is not None:
            sensor_data["temperatureLinksOnder"] = f"{linksOnder:.1f}"
        else:
            sensor_data["temperatureLinksOnder"] = "--"

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

        # RechtsBoven
        rechtsBoven = temps["RechtsBoven"]
        if rechtsBoven is not None:
            sensor_data["temperatureRechtsBoven"] = f"{rechtsBoven:.1f}"
        else:
            sensor_data["temperatureRechtsBoven"] = "--"

        # RechtsOnder
        rechtsOnder = temps["RechtsOnder"]
        if rechtsOnder is not None:
            sensor_data["temperatureRechtsOnder"] = f"{rechtsOnder:.1f}"
        else:
            sensor_data["temperatureRechtsOnder"] = "--"

        # Gemiddelde
        if aantal_binnen > 0:
            sensor_data["temperatureGem"] = f"{som_binnen / aantal_binnen:.1f}"
        else:
            sensor_data["temperatureGem"] = "--"

        await asyncio.sleep(2)

async def handle_websocket():
    global all_clients
    while True:
        still_connected = []

        for index, ws in enumerate(all_clients):
            try:
                data = ws.receive(fail_silently=True)
                if data and index == 0:
                    process_incoming_command(data)

                sensor_data["queue_pos"] = index 

                sensor_data["fanStatusLinks"] = fan1.speed > 0
                sensor_data["fanStatusRechts"] = fan2.speed > 0
                sensor_data["peltierEnabledLinks"] = peltiers[0].enabled
                sensor_data["peltierEnabledRechts"] = peltiers[1].enabled
                sensor_data["queue_pos"] = index 
                
                ws.send_message(json.dumps(sensor_data))
                
                still_connected.append(ws)

            except Exception:
                print(f"Klant op positie {index} is verbroken.")
                continue
        
        all_clients = still_connected
        await asyncio.sleep(0.1)

def process_incoming_command(data):
    global last_Speed_Fan_Links, last_Speed_Fan_Rechts
    if "=" in data:
        cmd, val = data.split("=")
        try:
            val_float = float(val)
            if cmd == "TEMP_LINKS":
                peltiers[0].enabled = True
                peltiers[0].set_target(val_float)
            elif cmd == "TEMP_RECHTS":   
                peltiers[1].enabled = True                             
                peltiers[1].set_target(val_float)
            elif cmd == "TEMP_GEM":
                peltiers[0].enabled = peltiers[1].enabled = True
                peltiers[0].set_target(val_float)
                peltiers[1].set_target(val_float)
            elif cmd == "FAN_LINKS":
                fan1.set_speed(val_float / 100.0)
                if val_float > 0: last_Speed_Fan_Links = val_float / 100.0
            elif cmd == "FAN_RECHTS":
                fan2.set_speed(val_float / 100.0)
                if val_float > 0: last_Speed_Fan_Rechts = val_float / 100.0
        except ValueError:
            pass
    else:
        if data == "FanOnOffLinks":
            fan1.set_speed(0.0 if fan1.speed > 0 else last_Speed_Fan_Links)
        elif data == "FanOnOffRechts":
            fan2.set_speed(0.0 if fan2.speed > 0 else last_Speed_Fan_Rechts)
        elif data == "TurnOnOff":
            ns = 0.0 if (fan1.speed > 0 or fan2.speed > 0) else 1.0
            fan1.set_speed(ns); fan2.set_speed(ns)
        elif data == "STOP_ALL":
            fan1.set_speed(0); fan2.set_speed(0)
            for p in peltiers:
                p.set_output(0, 0); p.enabled = False; p.set_target(20.0)

async def regel_hardware_taak():
    while True:
        if ruwe_temps["Links"] is not None: peltiers[0].update(ruwe_temps["Links"])
        if ruwe_temps["Rechts"] is not None: peltiers[1].update(ruwe_temps["Rechts"])
        await asyncio.sleep(1)

async def poll_server():
    while True:
        server.poll()
        await asyncio.sleep(0.05)

# =========================================================
# NETWERK SETUP & ROUTES
# =========================================================
print(f"Opstart WiFi AP: {AP_SSID}...")
wifi.radio.start_ap(AP_SSID, AP_PASSWORD)
ap_ip = str(wifi.radio.ipv4_address_ap)
pool = socketpool.SocketPool(wifi.radio)
server = Server(pool, "/",  debug=True)

@server.route("/", GET)
def serve_html(request: Request): return FileResponse(request, "browsertests.html")
@server.route("/style-webpage.css", GET)
def serve_css(request: Request): return FileResponse(request, "style-webpage.css")
@server.route("/webpage.js", GET)
def serve_js(request: Request): return FileResponse(request, "webpage.js")

@server.route("/connect-websocket", GET)
def connect_websocket(request: Request):
    global all_clients
    ws = Websocket(request)
    all_clients.append(ws) 
    print(f"Nieuwe connectie! Wachtrij lengte: {len(all_clients)}")
    return ws

async def main():
    global mijn_sensoren
    try:
        mijn_sensoren = initialiseer_sensoren()
        server.start(ap_ip)
        print(f"Server draait op http://{ap_ip}"+":5000")
        await asyncio.gather(poll_server(), handle_websocket(), lees_sensoren_taak(), regel_hardware_taak())
    except Exception as e:
        print(f"Kritieke fout: {e}")
        time.sleep(5)

asyncio.run(main())