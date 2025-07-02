import uvicorn
from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from typing import Dict
import asyncio
import uuid
import json
import time

from .config import GAME_LOOP_DELAY, PLAYER_DEFAULT_NAME_PREFIX, SERVER_TICK_RATE, LEADERBOARD_UPDATE_INTERVAL, LEADERBOARD_SIZE
from . import game

app = FastAPI()

class ConnectionManager:
    def __init__(self):
        self.active_connections: Dict[str, WebSocket] = {}

    async def connect(self, websocket: WebSocket, client_id: str):
        await websocket.accept()
        self.active_connections[client_id] = websocket
        print(f"Client {client_id} connected. Total clients: {len(self.active_connections)}")

    def disconnect(self, client_id: str):
        if client_id in self.active_connections:
            del self.active_connections[client_id]
            print(f"Client {client_id} disconnected. Total clients: {len(self.active_connections)}")

    async def send_personal_message(self, message: dict, client_id: str):
        if client_id in self.active_connections:
            try:
                await self.active_connections[client_id].send_text(json.dumps(message))
            except Exception as e:
                print(f"Error sending personal message to {client_id}: {e}")

    async def broadcast(self, message: dict):
        client_ids = list(self.active_connections.keys())
        for client_id in client_ids:
            if client_id in self.active_connections:
                try:
                    await self.active_connections[client_id].send_text(json.dumps(message))
                except Exception as e:
                    print(f"Error broadcasting to {client_id}: {e}")

manager = ConnectionManager()
last_update_time = time.perf_counter()
last_leaderboard_update_time = 0

async def game_engine_loop():
    global last_update_time
    # print("Game engine loop started.") # Less verbose
    while True:
        current_time = time.perf_counter()
        dt = current_time - last_update_time
        last_update_time = current_time
        game.update_game_state(dt)
        await asyncio.sleep(GAME_LOOP_DELAY)

async def broadcast_loop():
    global last_leaderboard_update_time
    # print("Broadcast loop started.") # Less verbose
    while True:
        current_time = time.time()
        players_list = [p.get_state() for p_id, p in game.game_data["players"].items() if p.is_active and p.cells]
        pellets_list = [p.get_state() for p_id, p in game.game_data["pellets"].items()]
        ejected_mass_list = [em.get_state() for em_id, em in game.game_data["ejected_masses"].items() if em.is_active]
        viruses_list = [v.get_state() for v_id, v in game.game_data["viruses"].items() if v.is_active]

        leaderboard_data = []
        if current_time - last_leaderboard_update_time > LEADERBOARD_UPDATE_INTERVAL:
            leaderboard_data = game.get_leaderboard(LEADERBOARD_SIZE)
            last_leaderboard_update_time = current_time

        current_snapshot = {
            "type": "game_update",
            "players": players_list,
            "pellets": pellets_list,
            "ejected_masses": ejected_mass_list,
            "viruses": viruses_list,
        }
        # Only include leaderboard if it was updated this cycle to save bandwidth
        if leaderboard_data:
            current_snapshot["leaderboard"] = leaderboard_data

        if manager.active_connections:
            await manager.broadcast(current_snapshot)
        await asyncio.sleep(SERVER_TICK_RATE)


@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    player_id = str(uuid.uuid4())
    player_name = f"{PLAYER_DEFAULT_NAME_PREFIX}_{player_id[:4]}"

    await manager.connect(websocket, player_id)
    player_obj = game.add_player(player_id, name=player_name)
    initial_player_state = player_obj.get_state()

    await manager.send_personal_message({"type": "welcome", "playerId": player_id, "initial_state": initial_player_state}, player_id)
    await manager.broadcast({"type": "player_joined", "player": initial_player_state}) # Inform others

    try:
        while True:
            data = await websocket.receive_text()
            try:
                message = json.loads(data)
                msg_type = message.get("type")
                target_x = message.get("target_x")
                target_y = message.get("target_y")

                if isinstance(target_x, (int, float)) and isinstance(target_y, (int, float)):
                    action = message.get("action") if msg_type == "player_action" else None
                    game.handle_player_input(player_id, float(target_x), float(target_y), action=action)
                elif msg_type == "player_action":
                    action = message.get("action")
                    player = game.game_data["players"].get(player_id)
                    if player and player.is_active: # Ensure player exists and is active
                         game.handle_player_input(player_id, player.target_x, player.target_y, action=action)
                # else:
                    # print(f"Invalid or incomplete message from {player_id}: {message}") # Can be too noisy

            except json.JSONDecodeError:
                print(f"Received non-JSON message from {player_id}: {data}")
            except Exception as e:
                print(f"Error processing message from {player_id}: {e} - Data: {data}")

    except WebSocketDisconnect:
        print(f"Player {player_id} disconnected.")
    except Exception as e:
        print(f"Error with client {player_id}: {e}")
    finally:
        manager.disconnect(player_id)
        game.remove_player(player_id)
        await manager.broadcast({"type": "player_left", "playerId": player_id})
        print(f"Player {player_id} resources cleaned up.")

@app.on_event("startup")
async def on_startup():
    global last_update_time, last_leaderboard_update_time
    game.initialize_game()
    last_update_time = time.perf_counter()
    last_leaderboard_update_time = time.time() # Initialize leaderboard timer
    asyncio.create_task(game_engine_loop())
    asyncio.create_task(broadcast_loop())
    print("Server started. Game engine and broadcast loops are running.")

if __name__ == "__main__":
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)
