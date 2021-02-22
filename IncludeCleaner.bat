cd /d "%~dp0"
if "%*" == "" (.\Python27_64\python.exe IncludeCleaner.py %*) else (.\Python27_32\python.exe IncludeCleaner.py %*)
@echo off
pause