@echo off
rem Package the source test release (cmd entry point): delegates to package.ps1.
rem Usage: package.cmd [output-dir]
rem NOTE: keep this file ASCII-only. cmd.exe reads it in the console code page,
rem so non-ASCII comments get mangled and can be executed as commands.
chcp 65001 >nul 2>&1
rem Prefer PowerShell 7 (pwsh) when present; fall back to Windows PowerShell.
where pwsh >nul 2>&1 && (pwsh -NoProfile -File "%~dp0package.ps1" %*) || (powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0package.ps1" %*)
