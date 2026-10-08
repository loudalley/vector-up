@echo off
rem Builds the portable single-file Vector-Up by Koenekt: 64-bit and 32-bit.
rem Output: dist\VectorUp-<ver>-win64.exe and ...-win32.exe
rem Needs PyInstaller in both interpreters:  py -3.14 -m pip install pyinstaller
rem                                          py -3.14-32 -m pip install pyinstaller
setlocal
cd /d "%~dp0"
for /f %%v in ('py -3.14 -c "from techtool import VERSION; print(VERSION)"') do set VER=%%v

call :build 3.14 win64 || exit /b 1
call :build 3.14-32 win32 || exit /b 1
echo.
echo Built:
dir /b dist\VectorUp-%VER%-*.exe
exit /b 0

:build
echo === %2 ===
py -%1 -m PyInstaller --noconfirm --clean --onefile --windowed ^
  --name VectorUp-%VER%-%2 --icon "%~dp0app_icon.ico" ^
  --add-data "%~dp0app_icon.ico;." ^
  --distpath dist --workpath build\pyi-%2 --specpath build\pyi-%2 ^
  "%~dp0techtool_main.py" > build-%VER%-%2.log 2>&1
if errorlevel 1 (echo FAILED, see build-%VER%-%2.log & exit /b 1)
exit /b 0
