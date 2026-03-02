import time
import board
from adafruit_onewire.bus import OneWireBus
import adafruit_ds18x20
import wifi
import socketpool
import asyncio
from adafruit_httpserver import Server, Request, Response, Websocket, GET


####################################################
#Temperatuur lezen
####################################################
#Sensoren mappen op basis van postie in de auto.
SENSOR_MAP = {
    "286C8CBC000000C9" : "LinksBoven"
}

# 1. Initialiseer de OneWire bus op pin GP22
ow_bus = OneWireBus(board.GP22)

# 2. Scan de bus en maak een lijst van sensor-objecten met hun namen
def initialiseer_sensoren():
    gevonden_devices = ow_bus.scan()
    sensor_lijst = []
    
    print(f"Systeem heeft {len(gevonden_devices)} sensoren gevonden op de bus.")
    
    for device in gevonden_devices:
        # Maak het DS18X20 object aan
        sensor_obj = adafruit_ds18x20.DS18X20(ow_bus, device)
        
        # Haal het unieke Hex-ID op
        id_hex = "".join([f"{b:02X}" for b in device.rom])
        
        # Zoek de naam op in onze SENSOR_MAP
        # Als het ID niet in de lijst staat, gebruiken we "Onbekend" + ID
        naam = SENSOR_MAP.get(id_hex, f"Onbekend ({id_hex})")
        
        sensor_lijst.append({
            "object": sensor_obj,
            "naam": naam,
            "id": id_hex
        })
    return sensor_lijst

# Start de initialisatie
mijn_sensoren = initialiseer_sensoren()

print("-" * 40)
print(f"{'LOCATIE':<15} | {'TEMPERATUUR':<12}")
print("-" * 40)

# 3. Main loop voor het uitlezen
while True:
    for s in mijn_sensoren:
        try:
            # Lees de temperatuur uit
            temp = s["object"].temperature
            print(f"{s['naam']:<15} | {temp:>10.2f}°C")
        except Exception as e:
            # Als een specifieke sensor faalt, printen we een foutmelding ipv te crashen
            print(f"{s['naam']:<15} | FOUT: {e}")

    print("-" * 40)
    
    # Wacht 5 seconden voor de volgende meting
    time.sleep(5)


################################################
# WiFi access point opstarten
################################################

AP_SSID = "Air Carditioning"
AP_PASSWORD = "2026MECH2A1"

print(f"Opstart WiFi Access Point: {AP_SSID}...")
try:
    wifi.radio.start_ap(AP_SSID, AP_PASSWORD)
    
    # When creating a network, the IP address uses a slightly different command:
    ap_ip = str(wifi.radio.ipv4_address_ap) 
    
    print("Access Point aangemaakt!")
    print(f"IP Address: {ap_ip}")
except Exception as e:
    print("Access Point niet kunnen opstarten:", e)
    raise

# 2. Setup van de HTTP Server en WebSocket pool
pool = socketpool.SocketPool(wifi.radio)
server = Server(pool, debug=True)
websocket = None

# 3. HTML Template 
HTML_TEMPLATE = """
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Pico 2 W AP WebSocket</title>
    <style>
        body { font-family: sans-serif; text-align: center; margin-top: 50px; background-color: #f4f4f9; }
        button { padding: 10px 20px; font-size: 16px; cursor: pointer; border-radius: 5px; border: 1px solid #ccc; background-color: #007bff; color: white; }
        button:active { background-color: #0056b3; }
        #msg { color: #d9534f; font-weight: bold; font-size: 1.2em; }
    </style>
</head>
<body>
    <h2>Test voor netwerk van de Carditioning</h2>
    <button onclick="sendMessage()">Stuur testdata naar vs code</button>
    <p><strong>Berichten van pico:</strong></p>
    <p id="msg">Wachten op data...</p>

    <script>
        // Connect to the WebSocket route dynamically
        let ws = new WebSocket('ws://' + location.host + '/ws');
        
        ws.onopen = () => console.log('WebSocket connection opened');
        ws.onclose = () => console.log('WebSocket connection closed');
        
        ws.onmessage = (event) => {
            document.getElementById('msg').innerText = event.data;
            document.getElementById('msg').style.color = '#5cb85c';
        };

        function sendMessage() {
            if (ws.readyState === WebSocket.OPEN) {
                ws.send("Button Clicked on Laptop!");
            } else {
                alert("WebSocket is not connected.");
            }
        }
    </script>
</body>
</html>
"""

@server.route("/", GET)
def serve_client(request: Request):
    """Serve the HTML interface."""
    return Response(request, HTML_TEMPLATE, content_type="text/html")

@server.route("/ws", GET)
def connect_websocket(request: Request):
    """Upgrade the HTTP request to a WebSocket."""
    global websocket
    if websocket is not None:
        websocket.close()
    websocket = Websocket(request)
    print("Laptop connected via WebSocket!")
    return websocket

# 4. Asynchronous Task Handlers
async def poll_server():
    """Continuously poll the HTTP server."""
    while True:
        server.poll()
        await asyncio.sleep(0)

async def handle_websocket():
    """Handle incoming and outgoing WS messages."""
    global websocket
    counter = 0
    while True:
        if websocket is not None:
            try:
                # Checken of er berichten van de laptop worden verzonden
                if (data := websocket.receive(fail_silently=True)) is not None:
                    print(f"Received from laptop: {data}")
                
                # Counter doorsturen naar laptop
                websocket.send_message(f"Pico Uptime Count: {counter}", fail_silently=True)
                counter += 1
            except Exception as e:
                print("WebSocket disconnected:", e)
                websocket = None 
                
        await asyncio.sleep(1)

async def main():
    """Main execution loop."""
    server.start(ap_ip)
    print(f"Server is opgestart en aan het werk!")
    print(f"1. Maak verbinding met Wi-Fi netwerk: '{AP_SSID}'.")
    print(f"2. Passwoord van dit netwerk is: '{AP_PASSWORD}'.")
    print(f"3. Open http://{ap_ip}:5000 in uw browser!")
    
    await asyncio.gather(
        asyncio.create_task(poll_server()),
        asyncio.create_task(handle_websocket())
    )

# Websocket opstarten 
asyncio.run(main())





