# Sigma Studio - Windows Start Script
$ErrorActionPreference = "Stop"
$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Definition
Set-Location -Path (Split-Path -Parent $ScriptDir)

python sigma_launcher.py
