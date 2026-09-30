@echo off
rem e-Fatura programi kurulumu. Cift tiklayin; Windows izin isterse "Evet" deyin.
cd /d "%~dp0"
powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0kurulum.ps1"
