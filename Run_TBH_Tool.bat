@echo off
title TBH-Tool Launcher - PVandAI
cd /d "D:\Somethings\ToolTest"
if exist "dist\TBH-Tool\TBH-Tool.exe" (
    "dist\TBH-Tool\TBH-Tool.exe"
) else (
    "D:\Somethings\ToolTest\venv\Scripts\python.exe" main.py
)
pause
