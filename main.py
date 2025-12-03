# IMPORTS
import logging
import os
import shutil
import winreg

from gsi_manager import GamestateRequestHandler, GamestateServer
from utils import Configuration

logging.getLogger("http").setLevel("WARNING")

def setup():
    # Attempt to load the config from a file
    if not os.path.exists("config.json"):
        config = Configuration()
        to_write = config.model_dump_json(indent=5)
        with open("config.json", "x") as file:
            file.write(to_write)
    else:
        with open("config.json") as file:
            config = Configuration.model_validate_json(file.read())

        # Write the config back to the file in case any values are not present on the disk
        to_write = config.model_dump_json(indent=5)
        with open("config.json", "w") as file:
            file.write(to_write)

    # Check if a game state integration file already exists in the CS2 game directory
    try:
        key = winreg.OpenKey(winreg.HKEY_CURRENT_USER, r"Software\Valve\Steam")
        steam_path, value_type = winreg.QueryValueEx(key, "SteamPath")
        key.Close()
    except OSError as e:
        raise OSError("Steam could not be found in the Windows registry.", e)

    if value_type != 1:
        raise TypeError(f"Key `SteamPath` is of an unexpected type: {value_type}, expected 1.")
    if not os.path.exists(steam_path):
        raise FileNotFoundError(f"Expected Steam directory located at {steam_path}, but directory does not exist.")

    library_folders = os.path.join(steam_path, r"steamapps\libraryfolders.vdf")

    installed_path: str
    with open(library_folders) as file:
        path: str | None = None
        while True:
            line = file.readline()
            if line == "":
                raise KeyError("Could not find CS2 game folder installed in Steam.")
            if "\"path\"" in line:
                path = line.replace("\"path\"", "")
                path = path.replace("\"", "")
                path = path.strip()
                if not os.path.exists(path):
                    path = None
            if "\"730\"" in line:
                if path is None:
                    raise FileNotFoundError("The CS2 game folder is located within a directory that does not exist.")
                break
        installed_path = path

    config_path = os.path.normpath(os.path.join(installed_path, r"steamapps\common\Counter-Strike Global Offensive\game\csgo\cfg"))
    if not os.path.exists(config_path):
        raise KeyError("Could not find CS2 game folder installed in Steam.")

    copy_config = False
    config_file = os.path.join(config_path, "gamestate_integration_chroma.cfg")
    if os.path.exists(config_file):
        with open(config_file) as file:
            existing_title = file.readline()
        with open("gamestate_integration_razerchroma.cfg") as file:
            if existing_title != file.readline():
                copy_config = True
    else:
        copy_config = True

    if copy_config:
        if os.path.exists(config_file):
            os.remove(config_file)
        try:
            shutil.copyfile("gamestate_integration_razerchroma.cfg", config_file)
        except PermissionError as e:
            raise PermissionError("User does not have permission to copy to CS2 game folder. Try running as administrator.", e)
        print("Copied gamestate integration config into the CS2 game folder. You may have to restart the game for changes to be applied.")

    gamestate_integration_server = GamestateServer(("127.0.0.1", 3003), GamestateRequestHandler, config)

    try:
        gamestate_integration_server.serve_forever()
    except KeyboardInterrupt:
        if gamestate_integration_server.chroma_control.connected_event.is_set():
            gamestate_integration_server.chroma_control.disconnect()
    except SystemExit:
        pass # Exception caused by shutting down when game is closed

if __name__ == "__main__":
    setup()

# By @peterservices
