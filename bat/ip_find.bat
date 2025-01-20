@setlocal enabledelayedexpansion
@echo off
type ip\ip_list.txt |  findstr /r "^[0-9]*\.[0-9]*\.[0-9]*\.[0-9]*$"  >> log\run.log  2>&1