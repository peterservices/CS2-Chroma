# IMPORTS
import logging
import shutil
import winreg
from pathlib import Path

from gsi_manager import GamestateRequestHandler, GamestateServer
from utils import Configuration

logging.basicConfig(level=logging.INFO, format="[CHROMA] [%(levelname)s] %(message)s")

logger = logging.getLogger(__name__)

def setup() -> None:
    # Attempt to load the config from the disk
    config_file = Path("config.json")
    if not config_file.exists():
        config = Configuration()
        to_write = config.model_dump_json(indent=5)
        with config_file.open("x") as file:
            file.write(to_write)
    else:
        with config_file.open() as file:
            config = Configuration.model_validate_json(file.read())

        # Write the config back to the file in case any values are not present on the disk
        to_write = config.model_dump_json(indent=5)
        with config_file.open("w") as file:
            file.write(to_write)

    # Get Steam path from registry
    try:
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, r"Software\Valve\Steam") as key:
            steam_path, value_type = winreg.QueryValueEx(key, "SteamPath")
    except OSError as e:
        raise OSError("Steam could not be found in the Windows registry.") from e

    if value_type != 1:
        raise TypeError(f"Key `SteamPath` is of an unexpected type: {value_type}, expected 1.")
    if not Path(steam_path).exists():
        raise FileNotFoundError(f"Expected Steam directory located at {steam_path}, but directory does not exist.")

    # Parse game location file to find CS2's path
    library_folders = Path(steam_path).joinpath("steamapps", "libraryfolders.vdf")

    cs2_installed_path: Path
    with Path(library_folders).open() as file:
        path: str | None = None
        while True:
            line = file.readline()
            if line == "":
                # We have reached the end of the file
                raise KeyError("Could not find CS2 game folder installed in Steam.")
            if "\"path\"" in line:
                path = line.replace("\"path\"", "")
                path = path.replace("\"", "")
                path = path.strip()
                if not Path(path).exists():
                    path = None
            if "\"730\"" in line:
                if path is None:
                    raise FileNotFoundError("The CS2 game folder is located within a directory that does not exist.")
                break
        cs2_installed_path = Path(path)

    cs2_config_path = cs2_installed_path.joinpath("steamapps", "common", "Counter-Strike Global Offensive", "game", "csgo", "cfg")
    if not cs2_config_path.exists():
        raise KeyError("Could not find CS2 game folder installed in Steam.")

    # Check if a game state integration file already exists in the CS2 game directory
    copy_config = False
    cs2_config_file = cs2_config_path.joinpath("gamestate_integration_razerchroma.cfg")
    if not Path("gamestate_integration_razerchroma.cfg").exists():
        raise FileNotFoundError("gamestate_integration_razerchroma.cfg was not found in cs2_chroma's directory.")
    if cs2_config_file.exists():
        # Compare the file contents to check for changes
        with cs2_config_file.open() as file:
            existing_file = file.read()
        with Path("gamestate_integration_razerchroma.cfg").open() as file:
            if existing_file != file.read():
                copy_config = True
    else:
        copy_config = True

    # Copy the new or updated config into the CS2 config folder
    if copy_config:
        if cs2_config_file.exists():
            cs2_config_file.unlink()
        try:
            shutil.copyfile("gamestate_integration_razerchroma.cfg", cs2_config_file)
        except PermissionError as e:
            raise PermissionError("User does not have permission to copy to CS2 game folder. Try running as administrator.") from e
        logger.info("Copied gamestate integration config into the CS2 game folder. You may need to restart the game for changes to be applied.")

    gamestate_integration_server = GamestateServer(("127.0.0.1", 3003), GamestateRequestHandler, config)
    try:
        gamestate_integration_server.serve_forever()
    except KeyboardInterrupt:
        if gamestate_integration_server.chroma_control.chroma_connected_event.is_set():
            gamestate_integration_server.chroma_control.chroma_disconnect()
    except SystemExit:
        pass # Exception raised when shutting down when game is closed

if __name__ == "__main__":
    setup()

# By @peterservices
