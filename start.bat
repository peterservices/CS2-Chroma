@echo off
cd /D "%~dp0" & :: Enter the project directory

:: Execute the command(s) passed (Should be the game executable along with any arguments)
IF NOT "%~1" == "" (
    echo Launching game executable...
    start "" %*
)

:: Check if installed version is python code or an executable
IF EXIST "cs2_chroma.exe" (
    start "" cs2_chroma.exe
) ELSE (
    where uv >nul 2>nul & :: Check if uv is installed
    IF %ERRORLEVEL% NEQ 0 (
        echo Please install `uv` to continue automatic CS2 Chroma launch. https://docs.astral.sh/uv/
        pause
        exit /b
    )

    uv python install 3.13
    uv sync --python 3.13

    uv run src/main.py
)
