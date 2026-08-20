@echo off
title HM_v3 - JARVIS AI 3.0 Trading Terminal
cd /d "%~dp0"
echo ======================================================================
echo           Starting HM_v3 JARVIS AI 3.0 Live Trading Terminal
echo ======================================================================
python HM_start.py %*
pause
