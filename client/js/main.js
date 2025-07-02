const canvas = document.getElementById('gameCanvas');
const ctx = canvas.getContext('2d');
const connectionStatusEl = document.getElementById('connectionStatus');
const playerIdDisplayEl = document.getElementById('playerIdDisplay');
const leaderboardListEl = document.getElementById('leaderboardList');
const gameMessagesEl = document.createElement('div');
gameMessagesEl.id = 'gameMessages';
// ... (gameMessagesEl styling as before) ...
gameMessagesEl.style.position = 'absolute';
gameMessagesEl.style.top = '50%';
gameMessagesEl.style.left = '50%';
gameMessagesEl.style.transform = 'translate(-50%, -50%)';
gameMessagesEl.style.padding = '20px';
gameMessagesEl.style.backgroundColor = 'rgba(0, 0, 0, 0.7)';
gameMessagesEl.style.color = 'white';
gameMessagesEl.style.fontSize = '24px';
gameMessagesEl.style.textAlign = 'center';
gameMessagesEl.style.display = 'none';
document.body.appendChild(gameMessagesEl);


canvas.width = 800;
canvas.height = 600;

const SERVER_MAP_WIDTH = 2000;
const SERVER_MAP_HEIGHT = 2000;
const CLIENT_INTERPOLATION_FACTOR = 0.1; // Lower for smoother, higher for more responsive (0.05 to 0.2 typical)
const SERVER_TICK_RATE_HZ = 30; // Matches server's broadcast rate for dt calc
const CLIENT_UPDATE_INTERVAL = 1000 / SERVER_TICK_RATE_HZ; // Milliseconds

let socket;
let playerId = null;
let localPlayer = null; // Will store server state
let displayPlayer = null; // Will store interpolated state for rendering
let otherPlayers = {};
let displayOtherPlayers = {}; // For interpolating other players
let pellets = [];
let ejectedMasses = [];
let viruses = [];
let leaderboard = [];
let wasEaten = false;

let currentMouseWorldX = 0;
let currentMouseWorldY = 0;
let lastServerUpdateTime = 0;


const viewport = { x: 0, y: 0, width: canvas.width, height: canvas.height, zoom: 1.0 };

function worldToScreen(worldX, worldY) {
    return { x: (worldX - viewport.x) * viewport.zoom, y: (worldY - viewport.y) * viewport.zoom };
}
function screenToWorld(screenX, screenY) {
    return { x: (screenX / viewport.zoom) + viewport.x, y: (screenY / viewport.zoom) + viewport.y };
}

function updateViewport() {
    // Viewport should follow the *display* player (interpolated one)
    if (displayPlayer && displayPlayer.cells && displayPlayer.cells.length > 0) {
        const targetX = displayPlayer.view_x !== undefined ? displayPlayer.view_x : displayPlayer.cells[0].x;
        const targetY = displayPlayer.view_y !== undefined ? displayPlayer.view_y : displayPlayer.cells[0].y;
        viewport.x = targetX - viewport.width / (2 * viewport.zoom);
        viewport.y = targetY - viewport.height / (2 * viewport.zoom);
    } else if (!wasEaten) {
        viewport.x = (SERVER_MAP_WIDTH - viewport.width / viewport.zoom) / 2;
        viewport.y = (SERVER_MAP_HEIGHT - viewport.height / viewport.zoom) / 2;
    }
}

function interpolate(current, target, factor) {
    return current + (target - current) * factor;
}

function interpolateCell(currentCell, targetCell) {
    if (!currentCell) return { ...targetCell }; // If no current, jump to target
    return {
        ...targetCell, // Keep ID, mass, radius, etc. from target (server authoritative)
        x: interpolate(currentCell.x, targetCell.x, CLIENT_INTERPOLATION_FACTOR),
        y: interpolate(currentCell.y, targetCell.y, CLIENT_INTERPOLATION_FACTOR),
        // Mass and radius are not interpolated, they change instantly based on server.
    };
}

function interpolatePlayer(currentDisplayPlayer, serverPlayerState) {
    if (!currentDisplayPlayer || !currentDisplayPlayer.cells) { // First update or no cells
        return JSON.parse(JSON.stringify(serverPlayerState)); // Deep copy
    }
    if (!serverPlayerState || !serverPlayerState.cells) { // Server says player gone
        return null;
    }

    const newDisplayCells = [];
    const serverCellsById = new Map(serverPlayerState.cells.map(c => [c.id, c]));
    const currentDisplayCellsById = new Map(currentDisplayPlayer.cells.map(c => [c.id, c]));

    // Interpolate existing cells or add new ones
    serverPlayerState.cells.forEach(serverCell => {
        const currentDisplayCell = currentDisplayCellsById.get(serverCell.id);
        newDisplayCells.push(interpolateCell(currentDisplayCell, serverCell));
    });

    // Recalculate view_x, view_y based on interpolated cell positions for smooth camera
    let totalMass = 0;
    let weightedX = 0;
    let weightedY = 0;
    newDisplayCells.forEach(cell => {
        totalMass += cell.mass;
        weightedX += cell.x * cell.mass;
        weightedY += cell.y * cell.mass;
    });

    return {
        ...serverPlayerState, // id, name, total_mass from server
        cells: newDisplayCells,
        view_x: totalMass > 0 ? weightedX / totalMass : (newDisplayCells.length > 0 ? newDisplayCells[0].x : SERVER_MAP_WIDTH/2),
        view_y: totalMass > 0 ? weightedY / totalMass : (newDisplayCells.length > 0 ? newDisplayCells[0].y : SERVER_MAP_HEIGHT/2),
    };
}


function drawCell(cell, isLocalPlayerCell) { // Uses interpolated cell data
    if (!cell || typeof cell.x !== 'number') return;
    const screenPos = worldToScreen(cell.x, cell.y);
    const radius = cell.radius * viewport.zoom; // Radius comes from server, not interpolated
    ctx.beginPath();
    ctx.arc(screenPos.x, screenPos.y, radius, 0, Math.PI * 2);
    ctx.fillStyle = isLocalPlayerCell ? 'rgba(0, 100, 255, 0.8)' : 'rgba(255, 0, 0, 0.7)';
    ctx.fill();
    ctx.strokeStyle = isLocalPlayerCell ? 'darkblue' : 'darkred';
    ctx.lineWidth = Math.max(1, 2 * viewport.zoom);
    ctx.stroke();
    ctx.closePath();
    ctx.fillStyle = 'white'; ctx.textAlign = 'center';
    ctx.font = `bold ${Math.max(6, 10 * viewport.zoom)}px Arial`;
    ctx.fillText(Math.floor(cell.mass), screenPos.x, screenPos.y + (radius * 0.1));
}

function drawPlayerNameAndTotalMass(player) { // Uses interpolated player's view_x/y
    if (!player || !player.cells || player.cells.length === 0) return;
    // Use player's own view_x, view_y which are based on interpolated cells
    const screenPos = worldToScreen(player.view_x, player.view_y);
    let maxRadius = player.cells.reduce((maxR, cell) => Math.max(maxR, cell.radius * viewport.zoom), 0);

    ctx.fillStyle = 'black'; ctx.textAlign = 'center';
    ctx.font = `bold ${Math.max(10, 14 * viewport.zoom)}px Arial`;
    ctx.fillText(player.name || player.id.substring(0,4), screenPos.x, screenPos.y - maxRadius - (10 * viewport.zoom));
    ctx.font = `bold ${Math.max(8, 12 * viewport.zoom)}px Arial`;
    // Total mass from server is authoritative
    ctx.fillText(`Total: ${Math.floor(player.total_mass || 0)}`, screenPos.x, screenPos.y - maxRadius - (25 * viewport.zoom));
}

// ... (drawPellet, drawEjectedMass, drawVirus remain the same) ...
function drawPellet(pellet) {
    if (!pellet || typeof pellet.x !== 'number') return;
    const screenPos = worldToScreen(pellet.x, pellet.y);
    const radius = (pellet.radius || 2) * viewport.zoom;
    const pelletColors = ['#2ecc71', '#3498db', '#f1c40f', '#e74c3c', '#9b59b6', '#1abc9c', '#e67e22'];
    const colorIndex = parseInt(pellet.id.substring(0, 2), 16) % pelletColors.length;
    ctx.fillStyle = pelletColors[colorIndex];
    ctx.beginPath(); ctx.arc(screenPos.x, screenPos.y, radius, 0, Math.PI * 2); ctx.fill(); ctx.closePath();
}

function drawEjectedMass(em) {
    if (!em || typeof em.x !== 'number') return;
    const screenPos = worldToScreen(em.x, em.y);
    const radius = (em.radius || 3) * viewport.zoom;
    ctx.fillStyle = 'rgba(128, 128, 128, 0.9)';
    ctx.beginPath(); ctx.arc(screenPos.x, screenPos.y, radius, 0, Math.PI * 2); ctx.fill(); ctx.closePath();
}

function drawVirus(virus) {
    if (!virus || typeof virus.x !== 'number') return;
    const screenPos = worldToScreen(virus.x, virus.y);
    const radius = virus.radius * viewport.zoom;
    ctx.beginPath();
    ctx.arc(screenPos.x, screenPos.y, radius, 0, Math.PI * 2);
    ctx.fillStyle = 'rgba(50, 205, 50, 0.8)';
    ctx.fill();
    const spikes = 12;
    ctx.strokeStyle = 'rgba(34, 139, 34, 0.9)';
    ctx.lineWidth = Math.max(1, 2 * viewport.zoom);
    for (let i = 0; i < spikes; i++) {
        const angle = (i / spikes) * (Math.PI * 2);
        const outerRadius = radius * 1.2;
        ctx.beginPath();
        ctx.moveTo(screenPos.x + Math.cos(angle) * radius * 0.8, screenPos.y + Math.sin(angle) * radius * 0.8);
        ctx.lineTo(screenPos.x + Math.cos(angle) * outerRadius, screenPos.y + Math.sin(angle) * outerRadius);
        ctx.stroke();
    }
}

function updateLeaderboardDisplay() {
    if (!leaderboardListEl) return;
    leaderboardListEl.innerHTML = '';
    leaderboard.forEach(entry => {
        const li = document.createElement('li');
        li.textContent = `${entry.rank}. ${entry.name}: ${entry.total_mass}`;
        if (localPlayer && entry.name === localPlayer.name) {
            li.classList.add('localPlayer');
        }
        leaderboardListEl.appendChild(li);
    });
}


function gameLoop() {
    requestAnimationFrame(gameLoop);

    // Interpolate local player if server data exists
    if (localPlayer && displayPlayer) {
        displayPlayer = interpolatePlayer(displayPlayer, localPlayer);
    } else if (localPlayer && !displayPlayer) { // First time localPlayer data received
        displayPlayer = JSON.parse(JSON.stringify(localPlayer)); // Deep copy
    } else if (!localPlayer && displayPlayer) { // localPlayer removed from server
        displayPlayer = null;
    }

    // Interpolate other players (basic example, can be expanded)
    for (const id in otherPlayers) {
        if (displayOtherPlayers[id] && otherPlayers[id]) {
            displayOtherPlayers[id] = interpolatePlayer(displayOtherPlayers[id], otherPlayers[id]);
        } else if (otherPlayers[id] && !displayOtherPlayers[id]) {
            displayOtherPlayers[id] = JSON.parse(JSON.stringify(otherPlayers[id]));
        }
    }
    // Remove display players that no longer exist in server state
    for (const id in displayOtherPlayers) {
        if (!otherPlayers[id]) {
            delete displayOtherPlayers[id];
        }
    }


    if (!wasEaten) updateViewport();
    ctx.clearRect(0, 0, canvas.width, canvas.height);
    ctx.save();
    drawGrid();

    pellets.forEach(p => { if (isVisuallyInViewport(p, p.radius)) drawPellet(p); });
    ejectedMasses.forEach(em => { if (isVisuallyInViewport(em, em.radius)) drawEjectedMass(em); });
    viruses.forEach(v => { if (isVisuallyInViewport(v, v.radius)) drawVirus(v); });

    // Render the interpolated displayPlayer
    if (displayPlayer && displayPlayer.cells) {
        displayPlayer.cells.forEach(cell => drawCell(cell, true));
        drawPlayerNameAndTotalMass(displayPlayer); // Pass displayPlayer for consistent name/mass rendering
    }
    // Render interpolated other players
    for (const id in displayOtherPlayers) {
        const player = displayOtherPlayers[id];
        if (player && player.cells) {
            player.cells.forEach(cell => drawCell(cell, false));
            drawPlayerNameAndTotalMass(player);
        }
    }
    ctx.restore();
    gameMessagesEl.style.display = wasEaten ? 'block' : 'none';
    if (wasEaten) gameMessagesEl.innerHTML = "You were eaten!<br>Refresh to play again.";
}

function isVisuallyInViewport(obj, worldRadius) {
    if (!obj || typeof obj.x !== 'number' || typeof obj.y !== 'number') return false;
    const screenPos = worldToScreen(obj.x, obj.y);
    const screenRadius = (worldRadius || 2) * viewport.zoom;
    return screenPos.x + screenRadius > 0 && screenPos.x - screenRadius < canvas.width &&
           screenPos.y + screenRadius > 0 && screenPos.y - screenRadius < canvas.height;
}

function drawGrid() {
    ctx.strokeStyle = "#e0e0e0"; ctx.lineWidth = 1;
    const baseGridSize = 50;
    const worldViewLeft = viewport.x, worldViewTop = viewport.y;
    const worldViewRight = viewport.x + viewport.width / viewport.zoom, worldViewBottom = viewport.y + viewport.height / viewport.zoom;
    const startWorldX = Math.floor(worldViewLeft/baseGridSize)*baseGridSize, endWorldX = Math.ceil(worldViewRight/baseGridSize)*baseGridSize;
    const startWorldY = Math.floor(worldViewTop/baseGridSize)*baseGridSize, endWorldY = Math.ceil(worldViewBottom/baseGridSize)*baseGridSize;
    for (let cX=startWorldX; cX<endWorldX; cX+=baseGridSize) { const sX=worldToScreen(cX,0).x; ctx.beginPath();ctx.moveTo(sX,0);ctx.lineTo(sX,canvas.height);ctx.stroke(); }
    for (let cY=startWorldY; cY<endWorldY; cY+=baseGridSize) { const sY=worldToScreen(0,cY).y; ctx.beginPath();ctx.moveTo(0,sY);ctx.lineTo(canvas.width,sY);ctx.stroke(); }
    ctx.strokeStyle = "rgba(0,0,0,0.7)"; ctx.lineWidth = Math.max(1, 3*viewport.zoom);
    const tl=worldToScreen(0,0),tr=worldToScreen(SERVER_MAP_WIDTH,0),bl=worldToScreen(0,SERVER_MAP_HEIGHT),br=worldToScreen(SERVER_MAP_WIDTH,SERVER_MAP_HEIGHT);
    ctx.beginPath();ctx.moveTo(tl.x,tl.y);ctx.lineTo(tr.x,tr.y);ctx.lineTo(br.x,br.y);ctx.lineTo(bl.x,bl.y);ctx.closePath();ctx.stroke();
}

function connectToServer() {
    const protocol = window.location.protocol === "https:" ? "wss" : "ws";
    const serverHost = window.location.hostname, serverPort = 8000;
    socket = new WebSocket(`${protocol}://${serverHost}:${serverPort}/ws`);
    wasEaten = false; gameMessagesEl.style.display = 'none';

    socket.onopen = () => {
        connectionStatusEl.textContent='Connected!'; connectionStatusEl.style.color='green'; console.log('WS open.');
        wasEaten = false; gameMessagesEl.style.display = 'none';
        lastServerUpdateTime = performance.now();
    };
    socket.onmessage = (event) => {
        const message = JSON.parse(event.data);
        lastServerUpdateTime = performance.now();

        if (message.type === 'welcome') {
            playerId=message.playerId;
            localPlayer=message.initial_state;
            displayPlayer = JSON.parse(JSON.stringify(localPlayer)); // Initialize display player
            wasEaten=false; gameMessagesEl.style.display='none';
            playerIdDisplayEl.textContent=`ID: ${playerId.substring(0,6)}`;
        } else if (message.type === 'game_update') {
            const serverPlayers = message.players || [];
            let localPlayerFromServer = null;
            const currentServerOtherPlayerIds = new Set();

            serverPlayers.forEach(p => {
                if (p.id === playerId) {
                    localPlayerFromServer = p; // Update authoritative state
                } else {
                    otherPlayers[p.id] = p; // Update authoritative state for others
                    currentServerOtherPlayerIds.add(p.id);
                }
            });

            localPlayer = localPlayerFromServer; // Update main localPlayer state

            // If localPlayer was previously defined but is now null from server, they've been eaten.
            if (displayPlayer && !localPlayer && !wasEaten) { // Check displayPlayer to see if we *were* in game
                console.log("EATEN (localPlayer is null in game_update)!");
                wasEaten = true;
                displayPlayer = null; // Clear display player
            }

            // Update/Remove other players
            Object.keys(otherPlayers).forEach(id => {
                if(!currentServerOtherPlayerIds.has(id)) {
                    delete otherPlayers[id];
                    delete displayOtherPlayers[id]; // Remove from display list too
                }
            });

            pellets = message.pellets || [];
            ejectedMasses = message.ejected_masses || [];
            viruses = message.viruses || [];
            if (message.leaderboard) {
                leaderboard = message.leaderboard;
                updateLeaderboardDisplay();
            }
        } else if (message.type === 'player_joined') {
            if (message.player && message.player.id !== playerId) {
                otherPlayers[message.player.id] = message.player;
                displayOtherPlayers[message.player.id] = JSON.parse(JSON.stringify(message.player)); // Init display
            }
        } else if (message.type === 'player_left') {
            if (message.playerId !== playerId) {
                delete otherPlayers[message.playerId];
                delete displayOtherPlayers[message.playerId];
            } else if (message.playerId === playerId && !wasEaten) {
                console.log("EATEN (player_left)!");
                localPlayer = null; wasEaten = true; displayPlayer = null;
            }
        }
    };
    socket.onclose = (event) => {
        connectionStatusEl.textContent='Disconnected. Refresh.'; connectionStatusEl.style.color='red'; playerIdDisplayEl.textContent='';
        localPlayer=null; displayPlayer=null; otherPlayers={}; displayOtherPlayers={}; pellets=[]; ejectedMasses=[]; viruses=[]; leaderboard=[]; updateLeaderboardDisplay(); console.log('WS closed:',event.reason,`Code: ${event.code}`);
    };
    socket.onerror = (error) => {
        connectionStatusEl.textContent='Connection Error. Refresh.'; connectionStatusEl.style.color='red'; console.error('WS error:', error);
    };
}

canvas.addEventListener('mousemove', (event) => {
    const rect = canvas.getBoundingClientRect();
    const worldPos = screenToWorld(event.clientX - rect.left, event.clientY - rect.top);
    currentMouseWorldX = worldPos.x; currentMouseWorldY = worldPos.y;
    if (socket && socket.readyState === WebSocket.OPEN && localPlayer && !wasEaten) {
        socket.send(JSON.stringify({ type: "player_input", target_x: currentMouseWorldX, target_y: currentMouseWorldY }));
    }
});

window.addEventListener('keydown', (event) => {
    if (!socket || socket.readyState !== WebSocket.OPEN || !localPlayer || wasEaten) return;
    let actionPayload = null;
    if (event.code === 'Space') {
        event.preventDefault();
        actionPayload = { type: "player_action", action: "split", target_x: currentMouseWorldX, target_y: currentMouseWorldY };
    } else if (event.key === 'w' || event.key === 'W') {
        event.preventDefault();
        actionPayload = { type: "player_action", action: "eject", target_x: currentMouseWorldX, target_y: currentMouseWorldY };
    }
    if (actionPayload) socket.send(JSON.stringify(actionPayload));
});

connectToServer();
gameLoop();
