@echo off
rem Install dependencies (cmd entry point): delegates to setup.ps1.
rem Usage: setup.cmd [--dev] [--index <URL>] [--proxy <URL>]
rem NOTE: keep this file ASCII-only. cmd.exe reads it in the console code page,
rem so non-ASCII comments get mangled and can be executed as commands.
chcp 65001 >nul 2>&1
rem Prefer PowerShell 7 (pwsh) when present; fall back to Windows PowerShell.
where pwsh >nul 2>&1 && (pwsh -NoProfile -File "%~dp0setup.ps1" %*) || (powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0setup.ps1" %*)
