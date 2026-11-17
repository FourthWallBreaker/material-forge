@echo off
rem Thin wrapper so the whole project can call Blender without hardcoding the
rem Steam path. Override with: set BLENDER_EXE=C:\path\to\blender.exe
if not defined BLENDER_EXE set "BLENDER_EXE=D:\Program Files (x86)\Steam\steamapps\common\Blender\blender.exe"
"%BLENDER_EXE%" %*
