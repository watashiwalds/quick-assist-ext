@echo off
rem Bấm đúp để chạy QuickAssist trên máy và dùng thử (xem scripts\chay-thu.ps1)
chcp 65001 >nul
powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0scripts\chay-thu.ps1"
