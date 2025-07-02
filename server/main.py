import uvicorn
from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from typing import Dict
import asyncio
import uuid
import json
import time
import math # For distance calculation

from .config import (
    GAME_LOOP_DELAY, PLAYER_DEFAULT_NAME_PREFIX, SERVER_TICK_RATE,
    LEADERBOARD_UPDATE_INTERVAL, LEADERBOARD_SIZE, PLAYER_AREA_OF_INTEREST_RADIUS
)
from . import game # game.py now contains get_player_specific_view_state

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
    while True:
        current_time_perf = time.perf_counter()
        dt = current_time_perf - last_update_time
        last_update_time = current_time_perf
        game.update_game_state(dt)
        await asyncio.sleep(GAME_LOOP_DELAY)

async def broadcast_loop():
    global last_leaderboard_update_time
    while True:
        current_time_epoch = time.time()

        leaderboard_payload_segment = {}
        if current_time_epoch - last_leaderboard_update_time > LEADERBOARD_UPDATE_INTERVAL:
            leaderboard_data = game.get_leaderboard(LEADERBOARD_SIZE)
            if leaderboard_data:
                 leaderboard_payload_segment = {"leaderboard": leaderboard_data}
            last_leaderboard_update_time = current_time_epoch

        for client_id, websocket in list(manager.active_connections.items()):
            # Use the helper function from game.py
            view_state_for_player = game.get_player_specific_view_state(
                client_id,
                PLAYER_AREA_OF_INTEREST_RADIUS # Pass the radius
                                               # game.py has access to game.game_data internally
            )

            # If player was not found or inactive by the helper, it returns dict with empty lists
            player_specific_snapshot = {
                "type": "game_update",
                "players": view_state_for_player["players"],
                "pellets": view_state_for_player["pellets"],
                "ejected_masses": view_state_for_player["ejected_masses"],
                "viruses": view_state_for_player["viruses"],
            }

            if leaderboard_payload_segment: # Add leaderboard if updated
                player_specific_snapshot.update(leaderboard_payload_segment)

            await manager.send_personal_message(player_specific_snapshot, client_id)

        await asyncio.sleep(SERVER_TICK_RATE)


@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    player_id = str(uuid.uuid4())
    player_name = f"{PLAYER_DEFAULT_NAME_PREFIX}_{player_id[:4]}"

    await manager.connect(websocket, player_id)
    player_obj = game.add_player(player_id, name=player_name)
    initial_player_state = player_obj.get_state()

    await manager.send_personal_message({"type": "welcome", "playerId": player_id, "initial_state": initial_player_state}, player_id)
    await manager.broadcast({"type": "player_joined", "player": initial_player_state})

    try:
        while True:
            data = await websocket.receive_text()
            try:
                message = json.loads(data)
                msg_type = message.get("type")
                target_x = message.get("target_x")
                target_y = message.get("target_y")

                player_for_action = game.game_data["players"].get(player_id)

                if player_for_action and player_for_action.is_active:
                    if isinstance(target_x, (int, float)) and isinstance(target_y, (int, float)):
                        action = message.get("action") if msg_type == "player_action" else None
                        game.handle_player_input(player_id, float(target_x), float(target_y), action=action)
                    elif msg_type == "player_action":
                        action = message.get("action")
                        game.handle_player_input(player_id, player_for_action.target_x, player_for_action.target_y, action=action)
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
    last_leaderboard_update_time = time.time()
    asyncio.create_task(game_engine_loop())
    asyncio.create_task(broadcast_loop())
    print("Server started. Game engine and broadcast loops are running.")

if __name__ == "__main__":
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)
