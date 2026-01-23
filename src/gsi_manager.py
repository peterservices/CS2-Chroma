# IMPORTS
import http.server
import json
import logging
import sys
import threading
import time
from typing import Any

from chroma_manager import ChromaControl
from chroma_models import ChromaEffect
from color_conversions import rgb_to_float
from effects import create_explosion_effect, create_wave_effect
from utils import (
    Configuration,
    GameState,
    Map,
    Player,
    Round,
    Weapon,
)

logger = logging.getLogger(__name__)

class GamestateRequestHandler(http.server.BaseHTTPRequestHandler):
    def do_POST(self) -> None:
        length = int(self.headers["Content-Length"])
        body: str = self.rfile.read(length).decode("utf-8")
        body: dict = json.loads(body)

        self.parse_payload(body)

        self.send_response(200)

    def log_request(self, code = "-", size = "-") -> None:
        if self.server.logging:
            return super().log_request(code, size)
        return None

    def parse_payload(self, payload: dict[str, Any]) -> None:
        gamestate_manager: GameState = self.server.gamestate_manager
        chroma_control: ChromaControl = self.server.chroma_control

        gamestate_manager.last_heartbeat = time.time()
        if "provider" in payload:
            _payload = payload["provider"]
            gamestate_manager.steam_id = _payload["steamid"]

        if "map" in payload:
            _payload = payload["map"]
            if gamestate_manager.map is None:
                gamestate_manager.map = Map()
            gamestate_manager.map.mode = _payload["mode"]
            gamestate_manager.map.name = _payload["name"]
            gamestate_manager.map.phase = _payload["phase"]
            gamestate_manager.map.round = _payload["round"]

            gamestate_manager.map.ct_team.score = _payload["team_ct"]["score"]
            gamestate_manager.map.ct_team.timeouts = _payload["team_ct"]["timeouts_remaining"]
            gamestate_manager.map.t_team.score = _payload["team_t"]["score"]
            gamestate_manager.map.t_team.timeouts = _payload["team_t"]["timeouts_remaining"]
        else:
            gamestate_manager.map = None

        if "round" in payload:
            _payload = payload["round"]
            if gamestate_manager.round is None:
                gamestate_manager.round = Round()
            gamestate_manager.round.phase = _payload["phase"]
            gamestate_manager.round.win_team = _payload.get("win_team")

            if "bomb" in _payload:
                if gamestate_manager.round.bomb != _payload["bomb"]:
                    match _payload["bomb"]:
                        case "planted":
                            gamestate_manager.round.bomb_plant_time = time.time()
                        case "exploded":
                            if self.server.config.effects.bomb_explosion_effect:
                                bomb_colors = create_explosion_effect((255, 81, 0))
                                bomb_effect = ChromaEffect(
                                    type="EXPLOSION",
                                    method="FILL_NO_ZERO",
                                    colors=bomb_colors,
                                    update_rate=0.1,
                                    last_update=time.time(),
                                    expires_after_updates=14,
                                    id="bomb",
                                )
                                chroma_control.state.add_effect(bomb_effect)
                gamestate_manager.round.bomb = _payload["bomb"]
            elif gamestate_manager.round.bomb is not None:
                gamestate_manager.round.bomb = None
                gamestate_manager.round.bomb_plant_time = None
        else:
            gamestate_manager.round = None

        if "player" in payload and (payload["player"]["steamid"] == gamestate_manager.steam_id or self.server.config.show_effects_for_others):
            if gamestate_manager.player is None:
                gamestate_manager.player = Player()
            _payload = payload["player"]

            player_changed = gamestate_manager.player.steam_id != _payload["steamid"]

            gamestate_manager.player.steam_id = _payload["steamid"]
            gamestate_manager.player.name = _payload["name"]
            gamestate_manager.player.team = _payload.get("team")

            if "state" in payload["player"]:
                _payload = payload["player"]["state"]

                if gamestate_manager.player.state.health != _payload["health"]:
                    if self.server.config.effects.death_effect:
                        if _payload["health"] == 0:
                            death_color = rgb_to_float((255, 0, 0))
                            death_effect = ChromaEffect(
                                type="STATIC",
                                method="FILL",
                                colors=[[death_color for _ in range(22)] for _ in range(6)],
                                id="death",
                            )
                            chroma_control.state.add_effect(death_effect)
                        elif _payload["health"] > gamestate_manager.player.state.health:
                            effect = chroma_control.state.find_effect_by_id("death")
                            if effect is not None:
                                chroma_control.state.remove_effect(effect)
                    gamestate_manager.player.state.health = _payload["health"]

                gamestate_manager.player.state.armor_health = _payload["armor"]
                gamestate_manager.player.state.has_helmet = _payload["helmet"]
                gamestate_manager.player.state.money = _payload["money"]

                if gamestate_manager.player.state.round_kills != _payload["round_kills"]:
                    if not player_changed and self.server.config.effects.kill_effect and _payload["round_kills"] > gamestate_manager.player.state.round_kills:
                        effect = chroma_control.state.find_effect_by_id("kill")
                        if effect:
                            chroma_control.state.remove_effect(effect)
                        if gamestate_manager.player.team == "CT":
                            kill_color = (93, 121, 174)
                        else:
                            kill_color = (222, 155, 53)

                        if _payload["round_kills"] % 5 != 0:
                            kill_color = rgb_to_float(kill_color)
                            kill_effect = ChromaEffect(
                                type="STATIC",
                                method="FILL",
                                colors=[[kill_color for _ in range(22)] for _ in range(6)],
                                decay_amount=20/255,
                                update_rate=0.1,
                                last_update=time.time(),
                                expires_after_updates=5,
                                id="kill",
                            )
                        else:
                            kill_colors = create_explosion_effect(kill_color)
                            kill_effect = ChromaEffect(
                                type="EXPLOSION",
                                method="FILL_NO_ZERO",
                                colors=kill_colors,
                                decay_amount=5/255,
                                update_rate=0.1,
                                last_update=time.time(),
                                expires_after_updates=14,
                                id="kill",
                            )
                        chroma_control.state.add_effect(kill_effect)
                    gamestate_manager.player.state.round_kills = _payload["round_kills"]

                gamestate_manager.player.state.round_headshot_kills = _payload["round_killhs"]
                gamestate_manager.player.state.equipment_value = _payload["equip_value"]

                if gamestate_manager.player.state.is_flashed != (_payload["flashed"] != 0):
                    if self.server.config.effects.flash_effect:
                        effect = chroma_control.state.find_effect_by_id("flash")
                        if _payload["flashed"] != 0:
                            if effect is not None:
                                chroma_control.state.remove_effect(effect)
                            flash_color = rgb_to_float((255, 255, 255))
                            flash_effect = ChromaEffect(
                                type="STATIC",
                                method="ADD",
                                colors=[[flash_color for _ in range(22)] for _ in range(6)],
                                id="flash",
                            )
                            chroma_control.state.add_effect(flash_effect)
                        else:
                            if effect is not None:
                                effect.last_update = time.time()
                                effect.update_rate = 0.1
                                effect.decay_amount = 15 / 255
                    gamestate_manager.player.state.is_flashed = _payload["flashed"] != 0

                if gamestate_manager.player.state.in_smoke != (_payload["smoked"] != 0):
                    if self.server.config.effects.smoke_effect:
                        effect = chroma_control.state.find_effect_by_id("smoke")
                        if _payload["smoked"] != 0:
                            if effect is not None:
                                chroma_control.state.remove_effect(effect)
                            smoke_color = rgb_to_float((100, 100, 100))
                            smoke_effect = ChromaEffect(
                                type="STATIC",
                                method="ADD",
                                colors=[[smoke_color for _ in range(22)] for _ in range(6)],
                                id="smoke",
                            )
                            chroma_control.state.add_effect(smoke_effect)
                        else:
                            if effect is not None:
                                effect.last_update = time.time()
                                effect.update_rate = 0.05
                                effect.decay_amount = 25 / 255
                    gamestate_manager.player.state.in_smoke = _payload["smoked"] != 0

                if gamestate_manager.player.state.is_burning != (_payload["burning"] == 255):
                    if self.server.config.effects.burning_effect:
                        effect = chroma_control.state.find_effect_by_id("fire")
                        if _payload["burning"] == 255:
                            if effect is not None:
                                chroma_control.state.remove_effect(effect)
                            burn_colors = create_wave_effect(colors=[(255, 81, 0), (255, 0, 0)], line_orientation="HORIZONTAL", mode="ALTERNATING")
                            burn_effect = ChromaEffect(
                                type="WAVE",
                                method="ADD",
                                direction="UP",
                                colors=burn_colors,
                                update_rate=0.2,
                                last_update=time.time(),
                                id="fire",
                            )
                            chroma_control.state.add_effect(burn_effect)
                        else:
                            if effect is not None:
                                effect.last_update = time.time()
                                effect.decay_amount = 128 / 255
                    gamestate_manager.player.state.is_burning = _payload["burning"] == 255
            else:
                chroma_control.state.remove_player_effects()

            # Weapons
            if "weapons" in payload["player"]:
                _payload: dict[str, dict[str, str | int]] = payload["player"]["weapons"]
                weapons_dict = gamestate_manager.player.state.weapons
                for k, v in _payload.items():
                    if k in weapons_dict and v["name"] == weapons_dict[k].name:
                        weapons_dict[k].ammo_reserve = v.get("ammo_reserve")
                        weapons_dict[k].active = v["state"] == "active"

                        if v.get("ammo_clip") is not None and v["ammo_clip"] != weapons_dict[k].ammo_clip:
                            if v["ammo_clip"] < weapons_dict[k].ammo_clip and weapons_dict[k].active and self.server.config.effects.shoot_effect:
                                effect = chroma_control.state.find_effect_by_id("shoot")
                                if effect is not None:
                                    effect.expires_after_updates = 1
                                    effect.last_update = time.time()
                                else:
                                    shoot_color = rgb_to_float((25, 25, 25))
                                    shoot_effect = ChromaEffect(
                                        type="STATIC",
                                        method="ADD",
                                        colors=[[shoot_color for _ in range(22)] for _ in range(6)],
                                        update_rate=0.15,
                                        expires_after_updates=1,
                                        last_update=time.time(),
                                        id="shoot"
                                    )
                                    chroma_control.state.add_effect(shoot_effect)
                            weapons_dict[k].ammo_clip = v["ammo_clip"]
                    else:
                        if k in weapons_dict:
                            del weapons_dict[k]
                        weapons_dict[k] = Weapon(name=v["name"], type=v.get("type"), ammo_clip=v.get("ammo_clip"), ammo_clip_max=v.get("ammo_clip_max"), ammo_reserve=v.get("ammo_reserve"), active=v["state"] == "active")
                removed_weapons: list[str] = []
                for k in weapons_dict:
                    if k not in _payload:
                        removed_weapons.append(k)
                for key in removed_weapons:
                    del weapons_dict[key]

            if "match_stats" in payload["player"]:
                _payload = payload["player"]["match_stats"]
                gamestate_manager.player.statistics.kills = _payload["kills"]
                gamestate_manager.player.statistics.assists = _payload["assists"]
                gamestate_manager.player.statistics.deaths = _payload["deaths"]
                gamestate_manager.player.statistics.mvps = _payload["mvps"]
                gamestate_manager.player.statistics.score = _payload["score"]
        else:
            gamestate_manager.player = None
            chroma_control.state.remove_player_effects()

class GamestateServer(http.server.HTTPServer):
    def __init__(self, address: tuple, RequestHandler: type, config: Configuration):
        self.gamestate_manager = GameState()
        self.chroma_control = ChromaControl()
        self.config = config
        self.logging = False

        super().__init__(address, RequestHandler)

        # Run the background monitor task
        thread = threading.Thread(target=self.background_monitor, daemon=True)
        thread.start()

    def background_monitor(self) -> None:
        """
        Complete various background tasks.

        - Checks to see if the game has pinged the server in the last 6 seconds.
        - Updates various indicator
        """
        while True:
            time.sleep(0.1) # If we don't wait, other threads may be severely slowed down
            # Detect game close
            if time.time() - self.gamestate_manager.last_heartbeat > 6: # Allow an extra second of missed heartbeats to be sure the game is actually closed
                if self.chroma_control.connected_event.is_set():
                    logger.info("Lost connection to game")
                    self.chroma_control.disconnect()
                    if self.config.close_after_game_close:
                        sys.exit()
            elif not self.chroma_control.connected_event.is_set():
                logger.info("Connected to game")
                self.chroma_control.connect()

            if self.chroma_control.connected_event.is_set():
                # Update defusal indicator
                if self.config.defusal_indicator:
                    effect = self.chroma_control.state.find_effect_by_id("defusal_indicator")
                    if self.gamestate_manager.round is not None and self.gamestate_manager.round.bomb_plant_time is not None and self.gamestate_manager.round.bomb == "planted":
                        if effect is None:
                            effect = ChromaEffect(
                                type="STATIC",
                                method="FILL_NO_ZERO",
                                colors=[[(0.0, 0.0, 0.0) for _ in range(22)] for _ in range(6)],
                                id="defusal_indicator"
                            )
                            self.chroma_control.state.add_effect(effect)

                        if time.time() - self.gamestate_manager.round.bomb_plant_time < 30:
                            colors = [(0.0, 1.0, 0.0) for _ in range(12)]
                        elif time.time() - self.gamestate_manager.round.bomb_plant_time < 35:
                            colors = [(0.0, 0.0, 1.0) for _ in range(12)]
                        else:
                            colors = [(1.0, 0.0, 0.0) for _ in range(12)]

                        effect.colors[0][3:15] = colors
                    elif effect is not None:
                        self.chroma_control.state.remove_effect(effect)

                # Update game result indicator
                if self.config.effects.game_result_effect:
                    effect = self.chroma_control.state.find_effect_by_id("result")
                    if self.gamestate_manager.map is not None and self.gamestate_manager.map.phase == "gameover":
                        if effect is None:
                            if self.gamestate_manager.player and ((self.gamestate_manager.player.team == "CT" and self.gamestate_manager.map.ct_team.score > self.gamestate_manager.map.t_team.score) or (self.gamestate_manager.player.team == "T" and self.gamestate_manager.map.ct_team.score < self.gamestate_manager.map.t_team.score)):
                                result_colors = create_wave_effect(colors=[(0, 255, 0), (105, 246, 104), (31, 201, 31)], line_orientation="VERTICAL", mode="CLUSTER")
                            elif self.gamestate_manager.player and self.gamestate_manager.map.ct_team.score != self.gamestate_manager.map.t_team.score:
                                result_colors = create_wave_effect(colors=[(255, 0, 0), (246, 105, 104), (201, 31, 31)], line_orientation="VERTICAL", mode="CLUSTER")
                            else:
                                result_colors = create_wave_effect(colors=[(150, 150, 150), (205, 205, 205), (90, 90, 90)], line_orientation="VERTICAL", mode="CLUSTER")

                            effect = ChromaEffect(
                                type="WAVE",
                                method="FILL",
                                direction="RIGHT",
                                colors=result_colors,
                                update_rate=0.2,
                                id="result"
                            )
                            self.chroma_control.state.add_effect(effect)
                    elif effect is not None:
                        self.chroma_control.state.remove_effect(effect)

                # Update movement key indicators
                if self.config.movement_key_indicators:
                    effect = self.chroma_control.state.find_effect_by_id("movement_key_indicator")
                    if self.gamestate_manager.map is not None and self.gamestate_manager.player is not None:
                        if effect is None:
                            key_colors = [[(0.0, 0.0, 0.0) for _ in range(22)] for _ in range(6)]
                            key_color = rgb_to_float((222, 155, 53))

                            # WASD
                            key_colors[2][3] = key_color
                            key_colors[3][2:5] = [key_color for _ in range(3)]

                            # SHIFT
                            key_colors[4][:2] = [key_color for _ in range(2)]

                            # CTRL
                            key_colors[5][1] = key_color

                            # SPACE
                            key_colors[5][4:11] = [key_color for _ in range(7)]

                            effect = ChromaEffect(
                                type="STATIC",
                                method="FILL_NO_ZERO",
                                direction="RIGHT",
                                colors=key_colors,
                                id="movement_key_indicator"
                            )
                            self.chroma_control.state.add_effect(effect)
                    elif effect is not None:
                        self.chroma_control.state.remove_effect(effect)

                # Update interaction key indicators
                if self.config.interaction_key_indicators:
                    effect = self.chroma_control.state.find_effect_by_id("interaction_key_indicator")
                    if self.gamestate_manager.map is not None and self.gamestate_manager.player is not None:
                        if effect is None:
                            key_colors = [[(0.0, 0.0, 0.0) for _ in range(22)] for _ in range(6)]
                            key_color = rgb_to_float((65, 58, 39))

                            # TAB, E, R, T, Y, U
                            key_colors[2][:2] = [key_color for _ in range(2)]
                            key_colors[2][4:9] = [key_color for _ in range(5)]

                            # G
                            key_colors[3][5:8] = [key_color for _ in range(3)]

                            # Z, C, V, B, M
                            key_colors[4][3] = key_color
                            key_colors[4][5:8] = [key_color for _ in range(3)]
                            key_colors[4][9] = key_color

                            effect = ChromaEffect(
                                type="STATIC",
                                method="FILL_NO_ZERO",
                                direction="RIGHT",
                                colors=key_colors,
                                id="interaction_key_indicator"
                            )
                            self.chroma_control.state.add_effect(effect)
                    elif effect is not None:
                        self.chroma_control.state.remove_effect(effect)

                # Update inventory key indicators depending on inventory content
                if self.config.inventory_key_indicators:
                    effect = self.chroma_control.state.find_effect_by_id("inventory_key_indicator")
                    if self.gamestate_manager.map is not None and self.gamestate_manager.player is not None:
                        colors = [[(0.0, 0.0, 0.0) for _ in range(22)] for _ in range(6)]
                        key_color = rgb_to_float((65, 58, 39))
                        if effect is None:
                            effect = ChromaEffect(
                                type="STATIC",
                                method="FILL_NO_ZERO",
                                colors=colors,
                                id="inventory_key_indicator"
                            )
                            self.chroma_control.state.add_effect(effect)

                        effect.colors = colors
                        for _, v in self.gamestate_manager.player.state.weapons.items():
                            match v.type:
                                case "Pistol":
                                    effect.colors[1][3] = key_color # 2
                                case "Knife":
                                    effect.colors[1][4] = key_color # 3
                                case "Grenade":
                                    effect.colors[1][5] = key_color # 4
                                case "StackableItem":
                                    effect.colors[4][4] = key_color # X
                                case "C4":
                                    effect.colors[1][6] = key_color # 5
                                case _:
                                    if v.name == "weapon_taser":
                                        effect.colors[1][4] = key_color # 3
                                    else:
                                        effect.colors[1][2] = key_color # 1
                    elif effect is not None:
                        self.chroma_control.state.remove_effect(effect)

# By @peterservices
