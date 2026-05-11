if (localStorage.getItem("theme") === "dark") {
    document.body.classList.add("dark-mode");
    updateThemeButton()
}

class PolynomialGraph {
    constructor(canvasId, targetColor) {
        this.canvas = document.getElementById(canvasId);
        this.ctx = this.canvas.getContext('2d');
        this.targetColor = targetColor;
        
        this.dataBuffer = []; // Gemeten punten (t, y)
        this.curves = [];     // Reeds getekende 2de-graadsfuncties
        this.t = 0;           // Tijd bijhouden
        this.targetTemp = 20;
        this.minDisplaySeconds = 200; // Aantal seconden die ten alle tijden zichtbaar moet zijn op de grafieken (aanpassen naargelang testen)
    }

    setTarget(temp) {
        this.targetTemp = parseFloat(temp);
        this.draw();
    }

    addData(tempStr) {
        if (tempStr === "--" || tempStr === "FOUT") return;
        let y = parseFloat(tempStr);
        this.dataBuffer.push({ t: this.t, y: y });

        // Na 10 seconden (5 metingen) nieuwe parabool tekenen
        if (this.dataBuffer.length >= 5) {
            this.calculatePolynomial();
            this.dataBuffer = [this.dataBuffer[this.dataBuffer.length - 1]]; // Laatste punt behouden als startpunt voor de volgende parabool
        }

        this.t += 2; 
        this.draw();
    }
    // Berekenen van de tweedegraadsfunctie / parabool
    calculatePolynomial() {
    const n = this.dataBuffer.length;
    let sumX=0, sumX2=0, sumX3=0, sumX4=0;
    let sumY=0, sumXY=0, sumX2Y=0;

    for (let i = 0; i < n; i++) {
        let x = i - 2; // -2,-1,0,1,2
        let y = this.dataBuffer[i].y;
        sumX  += x;
        sumX2 += x*x;
        sumX3 += x*x*x;
        sumX4 += x*x*x*x;
        sumY  += y;
        sumXY += x*y;
        sumX2Y+= x*x*y;
    }

    // berekening parameters a, b, c voor de parabool y = ax^2 + bx + c
    let a = (n * sumX2Y - sumX2 * sumY) / (n * sumX4 - sumX2 * sumX2);
    let b = sumXY / sumX2;
    let c = (sumY - a * sumX2) / n;

    this.curves.push({
        a, b, c,
        t_center: this.dataBuffer[2].t
    });
}

    
    getColorForTemp(temp) {
        let diff = temp - this.targetTemp;
        if (diff > 0.5) return "#3498db";  // Te warm ==> Koelen ==> Blauw
        if (diff < -0.5) return "#e74c3c"; // Te koud ==> Verwarmen ==> Rood
        return "#2ecc71";                  // Deadband ==> GOede benadering ==> Groen
    }

    // Tekenen van de grafieken en constante lijnen
    draw() {
        let rect = this.canvas.getBoundingClientRect();
        if (rect.width === 0) return; 
        this.canvas.width = rect.width * 2;
        this.canvas.height = rect.height * 2;
        
        let w = this.canvas.width;
        let h = this.canvas.height;
        this.ctx.clearRect(0, 0, w, h);

        let textColor = getComputedStyle(document.body).getPropertyValue('--text-color').trim() || '#333';

        let minY = this.targetTemp - 2;
        let maxY = this.targetTemp + 2;
        
        let allY = [];
        for(let c of this.curves) {
            for(let x=-2; x<=2; x+=0.5) allY.push(c.a*x*x + c.b*x + c.c);
        }
        for(let pt of this.dataBuffer) allY.push(pt.y);
        
        if (allY.length > 0) {
            minY = Math.min(minY, Math.min(...allY) - 1);
            maxY = Math.max(maxY, Math.max(...allY) + 1);
        }
        let rangeY = maxY - minY || 10;
        let rangeX = Math.max(this.minDisplaySeconds, this.t); 

        // Verhoogde padding om cut-off te voorkomen en ruimte te maken voor as-labels
        let padX = 100, padY = 50; 
        let plotW = w - padX * 2, plotH = h - padY * 2;

        let getX = (time) => padX + (time / rangeX) * plotW;
        let getY = (val) => padY + plotH - ((val - minY) / rangeY) * plotH;

        this.ctx.fillStyle = textColor;
        this.ctx.font = "20px sans-serif";

        // --- ACHTERGROND GRID & Y-AS LABELS ---
        this.ctx.textAlign = "right";
        this.ctx.textBaseline = "middle";
        let ySteps = 4; // 4 gelijke stappen op de Y-as
        for (let i = 0; i <= ySteps; i++) {
            let val = minY + (rangeY * (i / ySteps));
            let yPos = getY(val);
            
            // Horizontale gridlijn
            this.ctx.beginPath();
            this.ctx.strokeStyle = "rgba(150, 150, 150, 0.2)";
            this.ctx.lineWidth = 1.5;
            this.ctx.moveTo(padX, yPos);
            this.ctx.lineTo(padX + plotW, yPos);
            this.ctx.stroke();

            // Label (bv: 22.0°C)
            this.ctx.fillText(val.toFixed(1) + "°C", padX - 15, yPos);
        }

        // --- ACHTERGROND GRID & X-AS LABELS ---
        this.ctx.textAlign = "center";
        this.ctx.textBaseline = "top";
        let xTickInterval = 50; // Label elke 50 seconden
        for (let xVal = 0; xVal <= rangeX; xVal += xTickInterval) {
            let xPos = getX(xVal);
            
            // Verticale gridlijn
            this.ctx.beginPath();
            this.ctx.strokeStyle = "rgba(150, 150, 150, 0.2)";
            this.ctx.lineWidth = 1.5;
            this.ctx.moveTo(xPos, padY);
            this.ctx.lineTo(xPos, padY + plotH);
            this.ctx.stroke();

            // Label (bv: 100s)
            this.ctx.fillText(xVal + "s", xPos, padY + plotH + 15);
        }

        // Assen buitenlijnen tekenen (L-vorm)
        this.ctx.strokeStyle = textColor;
        this.ctx.lineWidth = 2;
        this.ctx.beginPath();
        this.ctx.moveTo(padX, padY);
        this.ctx.lineTo(padX, padY + plotH);
        this.ctx.lineTo(padX + plotW, padY + plotH);
        this.ctx.stroke();

        // --- DOELTEMPERATUUR & DEADBAND ---
        this.ctx.beginPath();
        this.ctx.strokeStyle = this.targetColor;
        this.ctx.lineWidth = 3;
        this.ctx.setLineDash([15, 15]);
        this.ctx.moveTo(padX, getY(this.targetTemp));
        this.ctx.lineTo(padX + plotW, getY(this.targetTemp));
        this.ctx.stroke();

        this.ctx.beginPath();
        this.ctx.lineWidth = 1; 
        this.ctx.setLineDash([5, 5]); 
        this.ctx.moveTo(padX, getY(this.targetTemp + 0.5));
        this.ctx.lineTo(padX + plotW, getY(this.targetTemp + 0.5));
        this.ctx.moveTo(padX, getY(this.targetTemp - 0.5));
        this.ctx.lineTo(padX + plotW, getY(this.targetTemp - 0.5));
        this.ctx.stroke();
        this.ctx.setLineDash([]); 

        this.ctx.fillStyle = this.targetColor;
        this.ctx.font = "24px sans-serif";
        this.ctx.textAlign = "left";
        this.ctx.textBaseline = "bottom";
        this.ctx.fillText("Doel: " + this.targetTemp + "°C", padX + 10, getY(this.targetTemp) - 10);

        // --- DYNAMISCH GEKLEURDE GRAFIEKLIJNEN ---
        this.ctx.lineWidth = 4;
        let prevPt = null;
        let prevPy = null;

        const drawSegment = (t1, y1, t2, y2) => {
            this.ctx.beginPath();
            this.ctx.strokeStyle = this.getColorForTemp((y1 + y2) / 2);
            this.ctx.moveTo(getX(t1), getY(y1));
            this.ctx.lineTo(getX(t2), getY(y2));
            this.ctx.stroke();
        };
        
    
        for (let i = 0; i < this.curves.length; i++) {
            let c = this.curves[i];
            for (let x = -2; x <= 2; x += 0.2) {
                let py = c.a * x * x + c.b * x + c.c;
                let pt = c.t_center + (x * 2); 
                
                if (prevPt !== null) { drawSegment(prevPt, prevPy, pt, py); }
                prevPt = pt;
                prevPy = py;
            }
        }
        
        for (let pt of this.dataBuffer) {
            if (prevPt !== null) { drawSegment(prevPt, prevPy, pt.t, pt.y); }
            prevPt = pt.t;
            prevPy = pt.y;
        }
        
        for (let pt of this.dataBuffer) {
            this.ctx.fillStyle = this.getColorForTemp(pt.y);
            this.ctx.beginPath();
            this.ctx.arc(getX(pt.t), getY(pt.y), 6, 0, Math.PI * 2);
            this.ctx.fill();
        }
    }
}

let graphLinks, graphRechts;
let socket;

function connect_socket() {
    disconnect_socket();

    if (!graphLinks) {
        // Doeltemperaturen in oranje tekenen (verschillend van de 3 die op de grafiek worden gebruikt)
        graphLinks = new PolynomialGraph("graphLinks", "#f39c12");
        graphRechts = new PolynomialGraph("graphRechts", "#f39c12");
        
        graphLinks.setTarget(document.getElementById("doelLinks").textContent);
        graphRechts.setTarget(document.getElementById("doelRechts").textContent);
    }

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
        setTimeout(() => { connect_socket(); }, 2500);
    });
    
    socket.addEventListener("message", (event) => {
        const data = JSON.parse(event.data); 
        
        const overlay = document.getElementById("waiting-room");
        const queueMessage = document.getElementById("queue-status-text");

        if (data.queue_pos === 0) {
            overlay.style.display = "none";
        } else {
            overlay.style.display = "flex";
            let x = data.queue_pos;
            if (x === 1) {
                queueMessage.innerHTML = "Een andere persoon heeft de controle op dit moment, u staat <strong>1ste</strong> in de wachtrij.";
            } else {
                queueMessage.innerHTML = "Een andere persoon heeft de controle op dit moment, u staat <strong>" + x + "de</strong> in de wachtrij."
            } 
        }
        
        const updateDot = (id, isOnline) => {
            const statusSens = document.getElementById(id);
            if (!statusSens) return;
            if (isOnline) {
                statusSens.classList.add("online");
                statusSens.classList.remove("offline");
            } else {
                statusSens.classList.add("offline");
                statusSens.classList.remove("online");
            }
        };

        // UI Updates
        let inputL = document.getElementById('inputTempLinks');
        if (data.peltierEnabledLinks) {
            inputL.classList.add('input-enabled'); inputL.classList.remove('input-disabled');
        } else {
            inputL.classList.add('input-disabled'); inputL.classList.remove('input-enabled');
        }

        let inputR = document.getElementById('inputTempRechts');
        if (data.peltierEnabledRechts) {
            inputR.classList.add('input-enabled'); inputR.classList.remove('input-disabled');
        } else {
            inputR.classList.add('input-disabled'); inputR.classList.remove('input-enabled');
        }

        updateDot("statusLinksBoven", data.statusLinksBoven);
        updateDot("statusRechtsBoven", data.statusRechtsBoven);
        updateDot("statusBuiten", data.statusBuiten);
        updateDot("statusLinksOnder", data.statusLinksOnder);
        updateDot("statusRechtsOnder", data.statusRechtsOnder);

        if (data.fanStatusLinks !== undefined) updateFanButton("fanBtnLinks", data.fanStatusLinks);
        if (data.fanStatusRechts !== undefined) updateFanButton("fanBtnRechts", data.fanStatusRechts);

        document.getElementById("tempLinks").textContent = data.temperatureLinks;
        document.getElementById("tempRechts").textContent = data.temperatureRechts;
        document.getElementById("tempBuiten").textContent = data.temperatureBuiten;
        document.getElementById("tempGem").textContent = data.temperatureGem;

        if (graphLinks && data.temperatureLinks) graphLinks.addData(data.temperatureLinks);
        if (graphRechts && data.temperatureRechts) graphRechts.addData(data.temperatureRechts);
    });

    socket.addEventListener("error", (event) => {
        o.textContent = "Status: Disconnected";
        o.className = "disconnected";
    });
}


function disconnect_socket() { if (socket != undefined) { socket.close(); socket = undefined; } }

function sendCommand(command) {
    if(socket != undefined && socket.readyState === WebSocket.OPEN) { socket.send(command); } 
    else { alert("Disconnected"); }
}

function handleMasterStop() {
    if(socket != undefined && socket.readyState === WebSocket.OPEN) {
        sendCommand('STOP_ALL'); resetAll(); alert("Systeem is gestopt!");
    } else { alert("Disconnected"); } 
}

function resetAll() {
    const rw = "20";
    document.getElementById("doelGem").textContent = rw;
    document.getElementById("doelLinks").textContent = rw;
    document.getElementById("doelRechts").textContent = rw;
    document.getElementById("inputTempLinks").value = rw;
    document.getElementById("inputTempRechts").value = rw;
    document.getElementById("inputTempGem").value = rw;
    document.getElementById("fanSliderLinks").value = 50; 
    document.getElementById("fanSliderRechts").value = 50;
    document.getElementById("fanValLinks").textContent = "50";
    document.getElementById("fanValRechts").textContent = "50";
    if (graphLinks) graphLinks.setTarget(rw);
    if (graphRechts) graphRechts.setTarget(rw);
}

function setTargetTemp(kant) {
    if(socket != undefined && socket.readyState === WebSocket.OPEN) {
        let val = document.getElementById("inputTemp" + kant).value;
        socket.send("TEMP_" + kant.toUpperCase() + "=" + val);
        document.getElementById("doel" + kant).textContent = val;
        if (kant === "Links") graphLinks.setTarget(val);
        if (kant === "Rechts") graphRechts.setTarget(val);
    } else { alert("Disconnected"); }
}

function setGlobalTargetTemp() {
    if(socket != undefined && socket.readyState === WebSocket.OPEN) {
        let val = document.getElementById("inputTempGem").value;
        socket.send("TEMP_GEM=" + val);
        document.getElementById("doelGem").textContent = val;
        document.getElementById("doelLinks").textContent = val;
        document.getElementById("doelRechts").textContent = val;
        graphLinks.setTarget(val);
        graphRechts.setTarget(val);
    } else { alert("Disconnected"); }
}

function toggleDarkMode() {
    document.body.classList.toggle("dark-mode");
    const isDark = document.body.classList.contains("dark-mode");
    localStorage.setItem("theme", isDark ? "dark" : "light");
    updateThemeButton()
}

function updateThemeButton() {
    const btn = document.getElementById("theme-btn");
    if (!btn) return;
    const isDark = document.body.classList.contains("dark-mode");
    btn.textContent = isDark ? "☀️ Light Mode" : "🌙 Dark Mode";
}

const updateFanButton = (btnId, isRunning) => {
    const btn = document.getElementById(btnId);
    if (!btn) return;
    btn.classList.toggle("active-fan", isRunning);
    btn.textContent = isRunning ? "Toggle Fan (ON)" : "Toggle Fan (OFF)";
};

function updateFanLabel(kant, waarde) { document.getElementById("fanVal" + kant).textContent = waarde; }

function sendFanSpeed(kant, waarde) {
    if(socket != undefined && socket.readyState === WebSocket.OPEN) {
        socket.send("FAN_" + kant.toUpperCase() + "=" + waarde);
    } else { alert("Disconnected"); }
}