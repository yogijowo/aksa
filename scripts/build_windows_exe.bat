@echo off
setlocal enabledelayedexpansion
echo ===============================================================
echo   AKSA - Windows Setup .exe Local Builder
echo ===============================================================

echo [1/4] Memeriksa dependensi Python, Node.js, dan Rust...
python --version >nul 2>&1
if %errorlevel% neq 0 (
    echo [ERROR] Python tidak ditemukan di PATH. Silakan install Python 3.12+.
    pause
    exit /b 1
)

node --version >nul 2>&1
if %errorlevel% neq 0 (
    echo [ERROR] Node.js tidak ditemukan di PATH. Silakan install Node.js 20+.
    pause
    exit /b 1
)

cargo --version >nul 2>&1
if %errorlevel% neq 0 (
    echo [ERROR] Rust / Cargo tidak ditemukan. Silakan install Rust via rustup.rs.
    pause
    exit /b 1
)

echo [2/4] Mempersiapkan lingkungan Python Engine Sidecar...
cd services\engine
if not exist ".venv" (
    python -m venv .venv
)
call .venv\Scripts\activate.bat
pip install --upgrade pip
pip install -e .
pip install pyinstaller
cd ..\..

echo [3/4] Mengompilasi Python Engine Sidecar menjadi .exe...
python scripts\build_sidecar.py --triple x86_64-pc-windows-msvc

echo [4/4] Membangun installer Windows desktop .exe (NSIS)...
cd apps\desktop
call npm install
call npm run build
call npx tauri build --bundles nsis
cd ..\..

echo ===============================================================
echo   Build Berhasil Selesai!
echo ===============================================================
for /r "apps\desktop\src-tauri\target\release\bundle\nsis" %%f in (*.exe) do (
    echo File Installer .exe siap: %%f
)
pause
