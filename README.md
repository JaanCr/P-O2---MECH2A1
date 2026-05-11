# Air Carditioning -MECH2A1
Project P en O 2 van team **MECH2A1**. Opdracht: opwarmings- en afkoelingssysteem van een auto op kleine schaal.

## Features
* **Live temperaturen**: Lees de temperaturen in de gehele auto (+ buiten) per kant.
* **Dual-zone klimaatcontrole**: Aansturing voor de linkse- en rechtse zijde doormiddel van zelf in stellen doeltemperaturen en aanpasbare ventilatoren.
* **Automatisch verwarmen en koelen**: bij benadering van de doeltemperatuur (deadband) wordt de temperatuur automatisch geregeld om de doeltemperatuur goed te benaderen.
* **Temperatuursverloop**: bekijk het verloop van de temperatuur grafisch per zijde!
* **Dark/Light mode**: Ingebouwde thema schakelaar met mode naar keuze!

* ## Structuur / bestanden
* `main.py`: De CircuitPython backend. Regelt de hardware, Hysteresis-controller logica, en host de webserver & WebSockets. (Installeer zelf de nodige Adafruit bibliotheken!)
* `browsertests.html`: De hoofd-layout van de webpagina.
* `style-webpage.css`: Styling voor de user interface, inclusief CSS-variabelen voor de dark/light mode's.
* `webpage.js`: Frontend logica, WebSocket afhandeling en de berekening van de live grafieken.


<img width="1208" height="2128" alt="_C__Users_jaanc_OneDrive_Bureaublad_School_Tweede%20Bachelor_P O2_P O2_browsertests html" src="https://github.com/user-attachments/assets/08dea484-ff6e-40f8-95f2-ef2e0b2e39a7" />
