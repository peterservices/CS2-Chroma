# Counter-Strike 2 Razer Chroma Integration

[![Build](https://github.com/peterservices/CS2-Chroma/actions/workflows/build.yml/badge.svg)](https://github.com/peterservices/CS2-Chroma/actions/workflows/build.yml)
[![Ruff](https://github.com/peterservices/CS2-Chroma/actions/workflows/ruff.yml/badge.svg)](https://github.com/peterservices/CS2-Chroma/actions/workflows/ruff.yml)

A configurable Razer Chroma integration that brings the heat of the game to your keyboard with color effects.

> [!NOTE]
> This script is only compatible with Windows.
>
> Windows may warn you about start.bat and/or cs2_chroma.exe because they are not signed, but they are perfectly safe. (Upload to VirusTotal if you want to check)

### **Quickstart Guide**

* Install [Razer Synapse 4 BETA](https://www.razer.com/synapse-4) (Non-BETA will not work)
* Download and unzip the [latest release](https://github.com/peterservices/CS2-Chroma/releases/latest) (recommended) or [development build](https://github.com/peterservices/CS2-Chroma/actions/workflows/build.yml).
* Add `"C:\\PATH\\TO\\PROJECT\\start.bat" %command%` to Counter-Strike 2's launch options (Replace the path with your own)
* Launch the game. If you want to view the configuration first, run start.bat separately and edit the generated `config.json` file.

### **Features**

* Colored feedback for in-game actions and events
  * Firing weapons
  * Killing enemies
  * Standing in smoke
  * Burning in fire
  * Flash-banged
  * Dying
  * Bomb exploding
  * Winning/losing/tying the game
* Active key indicators
  * Movement keys
  * Inventory slots
  * Other interaction controls (disabled by default)
* Helpful indicators
  * Bomb defuse indicator (disabled by default)
* Pause system media when alive (disabled by default)

All features are toggle-able via a JSON file generated when you first run the script.

> [!IMPORTANT]
> CS2-Chroma is not affiliated or endorsed in any way by Razer, Valve, or any of their subsidaries
