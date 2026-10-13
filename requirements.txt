#!/bin/bash
set -e
cd "$(dirname "$0")"
python3 -m pip install --upgrade pip
python3 -m pip install -r requirements.txt pyinstaller pillow
python3 build.py
echo "فایل آماده است: dist/Didban.dmg"
