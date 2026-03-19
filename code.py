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
    "286C8CBC000000C9": "Links",
    # Overige sensoren moeten nog getest worden
}


#passwoord en naam van het netwerk
AP_SSID = "Air Carditioning"
AP_PASSWORD = "2026MECH2A1"
NUM_SENSORS = 5


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
        
        for s in mijn_sensoren:
            naam = s["naam"]
            try:
                temp = s["object"].temperature
                # Formatteer naar 1 decimaal voor de website
                temp_str = f"{temp:.1f}"
                
                if naam == "Links":
                    sensor_data["temperatureLinks"] = temp_str
                    ruwe_temps["Links"] = temp
                    som_binnen += temp
                    aantal_binnen += 1
                elif naam == "Rechts":
                    sensor_data["temperatureRechts"] = temp_str
                    ruwe_temps["Rechts"] = temp
                    som_binnen += temp
                    aantal_binnen += 1
                elif naam == "Buiten":
                    sensor_data["temperatureBuiten"] = temp_str
            except Exception:
                if naam in ["Links", "Rechts", "Buiten"]:
                    sensor_data[f"temperature{naam}"] = "FOUT"
                    if naam in ruwe_temps:
                        ruwe_temps[naam] = None

        if aantal_binnen > 0:
            gemiddelde = som_binnen / aantal_binnen
            sensor_data["temperatureGem"] = f"{gemiddelde:.1f}"
        else:
            sensor_data["temperatureGem"] = "--"
            
        await asyncio.sleep(2)

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
    )

asyncio.run(main())