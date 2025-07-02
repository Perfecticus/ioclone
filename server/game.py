import uuid
import math
import random
import time
from .config import (
    MAP_WIDTH, MAP_HEIGHT, PLAYER_START_MASS, PELLET_MASS, MAX_PELLETS,
    PLAYER_BASE_SPEED, GAME_LOOP_DELAY, PELLET_RADIUS, PLAYER_DEFAULT_NAME_PREFIX,
    PLAYER_EAT_MASS_FACTOR, PLAYER_MIN_MASS_TO_SPLIT, PLAYER_MAX_CELLS,
    CELL_SPLIT_PROPULSION, CELL_MERGE_TIME,
    MASS_EJECT_AMOUNT, MASS_EJECT_COST, MASS_EJECT_SPEED, MASS_EJECT_MIN_MASS,
    EJECTED_MASS_RADIUS, EJECTED_MASS_LIFESPAN, EJECTED_MASS_FRICTION,
    VIRUS_MASS, VIRUS_RADIUS_BASE_FACTOR, MAX_VIRUSES, VIRUS_SPLIT_PLAYER_MASS_FACTOR,
    VIRUS_MAX_MASS_BEFORE_SPLIT, VIRUS_FEED_MASS_GAIN,
    VIRUS_CELL_SPLIT_COUNT_MIN, VIRUS_CELL_SPLIT_COUNT_MAX, VIRUS_SPLIT_PROPULSION_FACTOR,
    PLAYER_AREA_OF_INTEREST_RADIUS # Import for the new helper
)

class Player:
    def __init__(self, id: str, name: str, x: float, y: float, initial_mass: float = PLAYER_START_MASS):
        self.id = id; self.name = name if name else f"{PLAYER_DEFAULT_NAME_PREFIX}_{id[:4]}"
        self.cells = [self._create_initial_cell(x, y, initial_mass)]
        self.target_x = x; self.target_y = y
        self.is_active = True

    def _create_cell_base(self, x: float, y: float, mass: float, target_x: float = None, target_y: float = None) -> dict:
        current_time = time.time()
        cell_id = str(uuid.uuid4())
        radius = Player.get_cell_radius(mass)
        return {
            'id': cell_id, 'x': x, 'y': y, 'mass': mass, 'radius': radius,
            'target_x': target_x if target_x is not None else x,
            'target_y': target_y if target_y is not None else y,
            'creation_time': current_time,
            'can_merge_after_timestamp': current_time
        }

    def _create_cell(self, x: float, y: float, mass: float, target_x: float = None, target_y: float = None) -> dict:
        cell = self._create_cell_base(x, y, mass, target_x, target_y)
        cell['can_merge_after_timestamp'] = time.time() + CELL_MERGE_TIME
        return cell

    def _create_initial_cell(self, x: float, y: float, mass: float) -> dict:
        cell = self._create_cell_base(x, y, mass)
        return cell

    def _update_cell_radius(self, cell: dict):
        cell['radius'] = Player.get_cell_radius(cell['mass'])

    @property
    def total_mass(self): return sum(c['mass'] for c in self.cells) if self.cells else 0

    @property
    def view_x(self):
        if not self.cells: return MAP_WIDTH / 2
        return sum(c['x'] * c['mass'] for c in self.cells) / self.total_mass if self.total_mass > 0 else (self.cells[0]['x'] if self.cells else MAP_WIDTH / 2)

    @property
    def view_y(self):
        if not self.cells: return MAP_HEIGHT / 2
        return sum(c['y'] * c['mass'] for c in self.cells) / self.total_mass if self.total_mass > 0 else (self.cells[0]['y'] if self.cells else MAP_HEIGHT / 2)

    def get_state(self): # This is the full state for the player, used for self or when others see them.
        return { "id": self.id, "name": self.name,
            "cells": [{"id": c['id'], "x": c['x'], "y": c['y'], "mass": c['mass'], "radius": c['radius']} for c in self.cells],
            "total_mass": self.total_mass, "view_x": self.view_x, "view_y": self.view_y }

    def update_target(self, target_x: float, target_y: float):
        if target_x is not None: self.target_x = target_x
        if target_y is not None: self.target_y = target_y
        for cell in self.cells:
            if target_x is not None: cell['target_x'] = target_x
            if target_y is not None: cell['target_y'] = target_y

    def move_cells(self, dt: float):
        for cell in self.cells:
            speed_reduction = max(1, (cell['mass'] / PLAYER_START_MASS)**0.4)
            speed = PLAYER_BASE_SPEED / speed_reduction
            angle = math.atan2(cell['target_y'] - cell['y'], cell['target_x'] - cell['x'])
            dist_to_target = math.hypot(cell['target_x'] - cell['x'], cell['target_y'] - cell['y'])
            if dist_to_target > 1:
                move_dist = min(speed * dt, dist_to_target)
                cell['x'] += math.cos(angle) * move_dist
                cell['y'] += math.sin(angle) * move_dist
            cell['x'] = max(cell['radius'], min(cell['x'], MAP_WIDTH - cell['radius']))
            cell['y'] = max(cell['radius'], min(cell['y'], MAP_HEIGHT - cell['radius']))

    def split(self):
        if len(self.cells) >= PLAYER_MAX_CELLS or not self.cells: return False
        cell_to_split = max(self.cells, key=lambda c: c['mass'])
        if cell_to_split['mass'] < PLAYER_MIN_MASS_TO_SPLIT: return False
        original_mass = cell_to_split['mass']
        new_mass = original_mass / 2
        cell_to_split['mass'] = new_mass
        self._update_cell_radius(cell_to_split)
        angle = math.atan2(self.target_y - cell_to_split['y'], self.target_x - cell_to_split['x'])
        new_cell = self._create_cell(cell_to_split['x'], cell_to_split['y'], new_mass)
        propulsion = CELL_SPLIT_PROPULSION
        new_cell['x'] += math.cos(angle) * (propulsion/2); new_cell['y'] += math.sin(angle) * (propulsion/2)
        new_cell['target_x'] = cell_to_split['x'] + math.cos(angle) * propulsion
        new_cell['target_y'] = cell_to_split['y'] + math.sin(angle) * propulsion
        cell_to_split['target_x'] = cell_to_split['x'] - math.cos(angle) * (propulsion/2)
        cell_to_split['target_y'] = cell_to_split['y'] - math.sin(angle) * (propulsion/2)
        self.cells.append(new_cell)
        return True

    def burst_cell(self, cell_id_to_burst: str):
        cell_idx = -1; burst_cell_obj = None
        for i, c in enumerate(self.cells):
            if c['id'] == cell_id_to_burst: burst_cell_obj = c; cell_idx = i; break
        if cell_idx == -1 or burst_cell_obj is None: return False
        self.cells.pop(cell_idx)
        original_mass = burst_cell_obj['mass']
        num_pieces = random.randint(VIRUS_CELL_SPLIT_COUNT_MIN, VIRUS_CELL_SPLIT_COUNT_MAX)
        if num_pieces == 0: return True
        mass_per_piece = original_mass / num_pieces
        if mass_per_piece < 1: mass_per_piece = 1
        if len(self.cells) + num_pieces > PLAYER_MAX_CELLS:
            num_pieces = PLAYER_MAX_CELLS - len(self.cells)
            if num_pieces <= 0:
                if self.cells: self.cells[0]['mass'] += original_mass; self._update_cell_radius(self.cells[0])
                return True
            mass_per_piece = original_mass / num_pieces
        base_angle = random.uniform(0, 2 * math.pi)
        angle_increment = (2 * math.pi) / num_pieces
        for i in range(num_pieces):
            angle = base_angle + i * angle_increment
            new_c = self._create_cell(burst_cell_obj['x'], burst_cell_obj['y'], mass_per_piece)
            propulsion = CELL_SPLIT_PROPULSION * 0.75
            new_c['x'] += math.cos(angle) * (new_c['radius'] + 1)
            new_c['y'] += math.sin(angle) * (new_c['radius'] + 1)
            new_c['target_x'] = burst_cell_obj['x'] + math.cos(angle) * propulsion
            new_c['target_y'] = burst_cell_obj['y'] + math.sin(angle) * propulsion
            self.cells.append(new_c)
        if not self.cells: self.is_active = False
        return True

    def eject_mass(self):
        if not self.cells: return False
        cell_to_eject_from = max(self.cells, key=lambda c: c['mass'])
        if cell_to_eject_from['mass'] < MASS_EJECT_MIN_MASS or \
           cell_to_eject_from['mass'] - MASS_EJECT_COST < 1: return False
        cell_to_eject_from['mass'] -= MASS_EJECT_COST
        self._update_cell_radius(cell_to_eject_from)
        angle = math.atan2(self.target_y - cell_to_eject_from['y'], self.target_x - cell_to_eject_from['x'])
        sx = cell_to_eject_from['x'] + math.cos(angle) * (cell_to_eject_from['radius'] + EJECTED_MASS_RADIUS + 2)
        sy = cell_to_eject_from['y'] + math.sin(angle) * (cell_to_eject_from['radius'] + EJECTED_MASS_RADIUS + 2)
        em = EjectedMass(x=sx, y=sy, angle=angle, ejected_by_player_id=self.id)
        game_data["ejected_masses"][em.id] = em
        return True

    @staticmethod
    def get_cell_radius(mass: float) -> float: return math.sqrt(max(1, mass) / math.pi) * 10

class Pellet:
    def __init__(self, id: str, x: float, y: float, mass: float = PELLET_MASS):
        self.id=id; self.x=x; self.y=y; self.mass=mass; self.radius=PELLET_RADIUS
    def get_state(self): return {"id":self.id,"x":self.x,"y":self.y,"mass":self.mass,"radius":self.radius}

class EjectedMass:
    def __init__(self, x: float, y: float, angle: float, ejected_by_player_id: str):
        self.id = str(uuid.uuid4()); self.x = x; self.y = y; self.mass = MASS_EJECT_AMOUNT; self.radius = EJECTED_MASS_RADIUS
        self.creation_time = time.time(); self.vx = math.cos(angle)*MASS_EJECT_SPEED; self.vy = math.sin(angle)*MASS_EJECT_SPEED
        self.is_active = True; self.ejected_by_player_id = ejected_by_player_id
    def update(self, dt: float):
        self.x+=self.vx*dt; self.y+=self.vy*dt; self.vx*=EJECTED_MASS_FRICTION; self.vy*=EJECTED_MASS_FRICTION
        if time.time()>self.creation_time+EJECTED_MASS_LIFESPAN or self.x<0 or self.x>MAP_WIDTH or self.y<0 or self.y>MAP_HEIGHT: self.is_active=False
    def get_state(self): return {"id":self.id,"x":self.x,"y":self.y,"mass":self.mass,"radius":self.radius}

class Virus:
    def __init__(self, x: float, y: float, mass: float = VIRUS_MASS):
        self.id = str(uuid.uuid4()); self.x = x; self.y = y; self.mass = mass
        self.radius = Virus.get_virus_radius(self.mass)
        self.is_active = True
    def get_state(self): return {"id":self.id,"x":self.x,"y":self.y,"mass":self.mass,"radius":self.radius}
    def update_radius(self): self.radius = Virus.get_virus_radius(self.mass)
    @staticmethod
    def get_virus_radius(mass: float) -> float:
        return math.sqrt(max(1, mass) / math.pi) * VIRUS_RADIUS_BASE_FACTOR

game_data = {"players": {}, "pellets": {}, "ejected_masses": {}, "viruses": {}}

def get_random_position(radius=0): return (random.uniform(radius,MAP_WIDTH-radius),random.uniform(radius,MAP_HEIGHT-radius))

def initialize_game():
    game_data["players"].clear(); game_data["pellets"].clear(); game_data["ejected_masses"].clear(); game_data["viruses"].clear()
    for _ in range(MAX_PELLETS // 2): spawn_pellet()
    for _ in range(MAX_VIRUSES // 2): spawn_virus()
    print(f"Game initialized. Pellets: {len(game_data['pellets'])}, Viruses: {len(game_data['viruses'])}")

def spawn_pellet():
    if len(game_data["pellets"]) < MAX_PELLETS: pid=str(uuid.uuid4()); x,y=get_random_position(PELLET_RADIUS); game_data["pellets"][pid]=Pellet(id=pid,x=x,y=y); return game_data["pellets"][pid]
    return None

def spawn_virus(x=None, y=None):
    if len(game_data["viruses"]) < MAX_VIRUSES:
        vid = str(uuid.uuid4())
        if x is None or y is None : x, y = get_random_position(Virus.get_virus_radius(VIRUS_MASS))
        game_data["viruses"][vid] = Virus(x=x, y=y)
        return game_data["viruses"][vid]
    return None

def add_player(player_id: str, name: str):
    sx,sy=get_random_position(Player.get_cell_radius(PLAYER_START_MASS))
    p=Player(id=player_id,name=name,x=sx,y=sy,initial_mass=PLAYER_START_MASS)
    game_data["players"][player_id]=p
    return p

def remove_player(player_id: str):
    if player_id in game_data["players"]: game_data["players"][player_id].is_active = False

def handle_player_input(player_id: str, target_x: float, target_y: float, action: str = None):
    player=game_data["players"].get(player_id)
    if player and player.is_active: player.update_target(target_x,target_y);_=[player.split()if action=="split"else player.eject_mass()if action=="eject"else None]

def update_game_state(dt: float):
    current_time = time.time()
    active_players = [p for p in game_data["players"].values() if p.is_active]
    for p in active_players: p.move_cells(dt)

    # Update and remove inactive EjectedMass
    active_ejected_masses = {}
    for em_id, em_obj in game_data["ejected_masses"].items(): # Iterate directly, will rebuild
        em_obj.update(dt)
        if em_obj.is_active:
            active_ejected_masses[em_id] = em_obj
    game_data["ejected_masses"] = active_ejected_masses

    consumed_pellets=set(); consumed_ejected_mass=set(); consumed_viruses=set()
    player_cells_to_burst = []

    for player in active_players:
        for cell_idx, cell in enumerate(list(player.cells)):
            if not cell: continue
            for p_id,pellet in list(game_data["pellets"].items()):
                if p_id in consumed_pellets:continue
                if math.hypot(cell['x']-pellet.x,cell['y']-pellet.y)**2 < cell['radius']**2:
                    cell['mass']+=pellet.mass; player._update_cell_radius(cell); consumed_pellets.add(p_id)
            for em_id,em in list(game_data["ejected_masses"].items()):
                if em_id in consumed_ejected_mass:continue
                if math.hypot(cell['x']-em.x,cell['y']-em.y)**2 < cell['radius']**2:
                    cell['mass']+=em.mass; player._update_cell_radius(cell); consumed_ejected_mass.add(em_id)
            for v_id,virus in list(game_data["viruses"].items()):
                if v_id in consumed_viruses:continue
                dist_sq = math.hypot(cell['x']-virus.x,cell['y']-virus.y)**2
                if dist_sq < (cell['radius'] + virus.radius)**2 * 0.8:
                    if cell['mass'] > virus.mass * VIRUS_SPLIT_PLAYER_MASS_FACTOR:
                        player_cells_to_burst.append((player.id, cell['id']))
                        consumed_viruses.add(v_id); spawn_virus()
                        break
            if cell['id'] in [c_id for p_id_burst,c_id in player_cells_to_burst if p_id_burst == player.id]: continue

    for p_id,c_id in player_cells_to_burst: p=game_data.get(p_id); _=[p.burst_cell(c_id) if p and p.is_active else None]
    for p_id in consumed_pellets: _=[del game_data["pellets"][p_id],spawn_pellet()] if p_id in game_data["pellets"] else None
    for em_id in consumed_ejected_mass: _=[del game_data["ejected_masses"][em_id]] if em_id in game_data["ejected_masses"] else None
    for v_id in consumed_viruses: _=[del game_data["viruses"][v_id]] if v_id in game_data["viruses"] else None

    fed_viruses_to_split = {}
    for em_id, em in list(game_data["ejected_masses"].items()):
        if em_id in consumed_ejected_mass: continue
        for v_id, virus in list(game_data["viruses"].items()):
            if math.hypot(em.x - virus.x, em.y - virus.y) < virus.radius:
                virus.mass += VIRUS_FEED_MASS_GAIN; virus.update_radius()
                consumed_ejected_mass.add(em_id)
                if virus.mass > VIRUS_MAX_MASS_BEFORE_SPLIT:
                    fed_viruses_to_split[v_id] = math.atan2(em.y - virus.y, em.x - virus.x)
                break
    for em_id in consumed_ejected_mass:
        if em_id in game_data["ejected_masses"]: del game_data["ejected_masses"][em_id]

    for v_id, angle in fed_viruses_to_split.items():
        virus = game_data["viruses"].get(v_id)
        if virus:
            virus.mass = VIRUS_MASS; virus.update_radius()
            propel_dist = virus.radius * VIRUS_SPLIT_PROPULSION_FACTOR
            nx = virus.x + math.cos(angle) * propel_dist
            ny = virus.y + math.sin(angle) * propel_dist
            spawn_virus(nx, ny)

    cells_to_remove_map={pid:[]for pid in[pid for pid,p in game_data["players"].items()if p.is_active]}
    player_ids_active = [pid for pid,p in game_data["players"].items() if p.is_active]
    for i in range(len(player_ids_active)):
        p1=game_data[player_ids_active[i]]
        for j in range(i+1,len(player_ids_active)):
            p2=game_data[player_ids_active[j]]
            for c1 in list(p1.cells):
                for c2 in list(p2.cells):
                    if c2['id']in cells_to_remove_map.get(p2.id,[]):continue
                    dist_sq=math.hypot(c1['x']-c2['x'],c1['y']-c2['y'])**2
                    if c1['mass']>c2['mass']*PLAYER_EAT_MASS_FACTOR and dist_sq<c1['radius']**2-(c2['radius']**2/2):
                        c1['mass']+=c2['mass']; p1._update_cell_radius(c1); cells_to_remove_map.setdefault(p2.id,[]).append(c2['id'])
                    elif c2['mass']>c1['mass']*PLAYER_EAT_MASS_FACTOR and dist_sq<c2['radius']**2-(c1['radius']**2/2):
                        c2['mass']+=c1['mass']; p2._update_cell_radius(c2); cells_to_remove_map.setdefault(p1.id,[]).append(c1['id']);break

    for p in active_players:
        merged_indices_this_tick = set()
        player_cells_copy = list(p.cells)
        for i_idx in range(len(player_cells_copy)):
            if i_idx in merged_indices_this_tick: continue
            cell_i = player_cells_copy[i_idx]
            if not cell_i or cell_i['id'] in cells_to_remove_map.get(p.id, []): continue
            if current_time < cell_i['can_merge_after_timestamp']: continue
            for j_idx in range(i_idx + 1, len(player_cells_copy)):
                if j_idx in merged_indices_this_tick: continue
                cell_j = player_cells_copy[j_idx]
                if not cell_j or cell_j['id'] in cells_to_remove_map.get(p.id, []): continue
                if current_time < cell_j['can_merge_after_timestamp']: continue
                distance_sq = math.hypot(cell_i['x'] - cell_j['x'], cell_i['y'] - cell_j['y'])**2
                if distance_sq < (cell_i['radius'] + cell_j['radius'])**2 * 0.25:
                    larger_cell, smaller_cell, smaller_idx = (cell_i, cell_j, j_idx) if cell_i['mass'] >= cell_j['mass'] else (cell_j, cell_i, i_idx)
                    larger_cell['mass'] += smaller_cell['mass']
                    p._update_cell_radius(larger_cell)
                    cells_to_remove_map.setdefault(p.id, []).append(smaller_cell['id'])
                    merged_indices_this_tick.add(smaller_idx)
                    larger_cell['can_merge_after_timestamp'] = current_time + CELL_MERGE_TIME
                    if smaller_cell == cell_i: break

    for pid,c_ids in cells_to_remove_map.items():
        p=game_data.get(pid)
        if p:
            p.cells = [c for c in p.cells if c['id'] not in c_ids]
            if not p.cells: p.is_active = False

    final_remove_pids = []
    for pid, p_obj in list(game_data["players"].items()):
        if not p_obj.is_active or not p_obj.cells:
            final_remove_pids.append(pid)
    for pid in final_remove_pids:
        if pid in game_data["players"]: del game_data["players"][pid]

    if len(game_data["pellets"])<MAX_PELLETS*0.75 and random.random()<0.05:spawn_pellet()

    return {"type":"game_update",
            "players":[p.get_state()for p in game_data["players"].values()if p.is_active and p.cells],
            "pellets":[p.get_state()for p in game_data["pellets"].values()],
            "ejected_masses":[em.get_state()for em in game_data["ejected_masses"].values()if em.is_active],
            "viruses": [v.get_state() for v in game_data["viruses"].values() if v.is_active]}

def get_leaderboard(size: int):
    active_players = [p for p in game_data["players"].values() if p.is_active and p.cells]
    sorted_players = sorted(active_players, key=lambda p: p.total_mass, reverse=True)
    leaderboard = []
    for i, player in enumerate(sorted_players[:size]):
        leaderboard.append({ "rank": i + 1, "name": player.name, "total_mass": round(player.total_mass) })
    return leaderboard

if __name__ == '__main__':
    initialize_game()
    p_id = "test_player_virus"
    add_player(p_id, "VirusVictim", initial_mass=VIRUS_MASS * 2)
    player = game_data[p_id]

    if not game_data["viruses"]: spawn_virus(player.view_x + player.cells[0]['radius'] + Virus.get_virus_radius(VIRUS_MASS) + 10, player.view_y)
    virus_key = list(game_data["viruses"].keys())[0]
    virus = game_data["viruses"][virus_key]

    player.update_target(virus.x, virus.y)
    print(f"Player {player.name} (Mass: {player.total_mass}) targeting Virus {virus.id} (Mass: {virus.mass}) at ({virus.x:.0f},{virus.y:.0f})")
    print(f"Player cell at ({player.cells[0]['x']:.0f},{player.cells[0]['y']:.0f}) with radius {player.cells[0]['radius']:.1f}")

    for i in range(120):
        state = update_game_state(GAME_LOOP_DELAY)
        p_state = next((p_s for p_s in state["players"] if p_s["id"] == p_id), None)
        v_state = next((v_s for v_s in state["viruses"] if v_s["id"] == virus_key), None)

        if i % 30 == 0:
            if p_state: print(f"Tick {i}: Player cells: {len(p_state['cells'])}, Total Mass: {p_state['total_mass']:.0f}")
            else: print(f"Tick {i}: Player GONE"); break
            if v_state: print(f"  Virus Mass: {v_state['mass']:.0f}, Radius: {v_state['radius']:.1f}")
            else: print(f"  Virus {virus_key} GONE (consumed/split)")

        if p_state and len(p_state['cells']) > 1: print(f"Player burst by virus at tick {i}!"); break
        if not v_state and p_state and len(p_state['cells'])==1 : print(f"Virus consumed by player at tick {i}"); break
        if not v_state and not p_state: print("Both player and virus gone?"); break

    if game_data["viruses"]:
        virus_key_feed = list(game_data["viruses"].keys())[0]
        virus_to_feed = game_data["viruses"][virus_key_feed]
        print(f"\nFeeding virus {virus_to_feed.id} at ({virus_to_feed.x:.0f}, {virus_to_feed.y:.0f}), initial mass: {virus_to_feed.mass}")

        feeder_id = "feeder_bot"
        add_player(feeder_id, "Feeder", initial_mass=MASS_EJECT_MIN_MASS*3)
        feeder = game_data[feeder_id]
        feeder.update_target(virus_to_feed.x, virus_to_feed.y)

        initial_virus_count = len(game_data["viruses"])
        for _ in range(10):
            feeder.eject_mass()
            if feeder.total_mass < MASS_EJECT_MIN_MASS : break

        for i in range(180):
            state = update_game_state(GAME_LOOP_DELAY)
            v_state_feed = next((v for v in state["viruses"] if v["id"] == virus_key_feed), None)
            if i % 30 == 0:
                if v_state_feed : print(f"Tick {i+120}: Fed Virus Mass: {v_state_feed['mass']:.0f}, Radius: {v_state_feed['radius']:.1f}, Total Viruses: {len(state['viruses'])}")
                else: print(f"Tick {i+120}: Original fed virus gone. Total Viruses: {len(state['viruses'])}"); break
            if len(state["viruses"]) > initial_virus_count: print(f"Virus split detected at tick {i+120}!"); break
            if not v_state_feed : break

    print("Test complete.")

[end of server/game.py]
