if (localStorage.getItem("theme") === "dark") {
    document.body.classList.add("dark-mode");
    updateThemeButton()
}

let socket;

function connect_socket() {
    disconnect_socket();

    socket = new WebSocket("ws://" + window.location.host + "/connect-websocket");
    const o = document.getElementById("status");

    socket.addEventListener("open", (event) => {
       o.textContent = "Status: Connected";
       o.className = "connected"; 
    });

    socket.addEventListener("close", (event) => {
        o.textContent = "Status: Disconnected";
        o.className = "disconnected";
        socket = undefined;
        setTimeout(() => {
            connect_socket(); 
        }, 2500);
    });
    
    socket.addEventListener("message", (event) => {
        const data = JSON.parse(event.data); 
        document.getElementById("tempLinks").textContent = data.temperatureLinks;
        document.getElementById("tempRechts").textContent = data.temperatureRechts;
        document.getElementById("tempBuiten").textContent = data.temperatureBuiten;
        document.getElementById("tempGem").textContent = data.temperatureGem;
    });

    socket.addEventListener("error", (event) => {
        o.textContent = "Status: Disconnected";
        o.className = "disconnected";
    });
}

function disconnect_socket() {
    if (socket != undefined) {
        socket.close();
        socket = undefined;
    }
}

function sendCommand(command) {
    if(socket != undefined && socket.readyState === WebSocket.OPEN) {
        socket.send(command);
    } else {
        alert("Disconnected");
    }
}

// Nieuwe functie voor het instellen van de doeltemperatuur via de input velden
function setTargetTemp(kant) {
    if(socket != undefined && socket.readyState === WebSocket.OPEN) {
        let inputElement = document.getElementById("inputTemp" + kant);
        let waarde = inputElement.value;
        
        // Stuur commando, bijvoorbeeld "TEMP_LINKS=21.5"
        let commando = "TEMP_" + kant.toUpperCase() + "=" + waarde;
        socket.send(commando);

        // Update de tekst in de UI
        document.getElementById("doel" + kant).textContent = waarde;
    } else {
        alert("Disconnected");
    }
}

function toggleDarkMode() {
    document.body.classList.toggle("dark-mode");
    const isDark = document.body.classList.contains("dark-mode");
    localStorage.setItem("theme", isDark ? "dark" : "light");
    updateThemeButton()
}

function updateThemeButton() {
    const btn = document.getElementById("theme-btn");
    if (!btn) return; // safety check
    const isDark = document.body.classList.contains("dark-mode");
    btn.textContent = isDark ? "☀️ Light Mode" : "🌙 Dark Mode";
}

function updateFanLabel(kant, waarde) {
    document.getElementById("fanVal" + kant).textContent = waarde;
}

// Sends the final value to the Pico
function sendFanSpeed(kant, waarde) {
    if(socket != undefined && socket.readyState === WebSocket.OPEN) {
        // Sends: "FAN_LINKS=75"
        let commando = "FAN_" + kant.toUpperCase() + "=" + waarde;
        socket.send(commando);
        console.log("Sent fan speed:", commando);
    } else {
        alert("Disconnected");
    }
}