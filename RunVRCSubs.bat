@echo off
call UpdateScripts.bat
echo "Installing requirements (be sure to have python installed and in PATH)"
pip install -r VRCSubs/Requirements.txt
py VRCSubs/vrcsubs.py
pause