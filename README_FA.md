"""ساخت فایل اجرایی: ویندوز → dist/Didban.exe   ·   مک → dist/Didban.dmg
اجرا:  python build.py
"""
import platform
import shutil
import subprocess
import sys

import PyInstaller.__main__ as pi

win = platform.system() == "Windows"
mac = platform.system() == "Darwin"
args = [
    "main.py", "--name", "Didban", "--noconfirm", "--clean", "--windowed",
    "--add-data", "didban/assets:didban/assets",
    "--collect-all", "ccxt",
    "--collect-submodules", "pyqtgraph",
    "--collect-submodules", "keyring",
    "--exclude-module", "tkinter", "--exclude-module", "matplotlib",
    "--icon", "didban/assets/icon.ico" if win else "didban/assets/icon.png",
]
if win:
    args.append("--onefile")
if mac:
    args += ["--osx-bundle-identifier", "app.didban.agent"]
pi.run(args)

if mac:
    dmg = "dist/Didban.dmg"
    shutil.rmtree("dist/dmg", ignore_errors=True)
    shutil.copytree("dist/Didban.app", "dist/dmg/Didban.app", symlinks=True)
    subprocess.run(["ln", "-s", "/Applications", "dist/dmg/Applications"], check=True)
    subprocess.run(["hdiutil", "create", "-volname", "Didban", "-srcfolder", "dist/dmg", "-ov", "-format", "UDZO", dmg], check=True)
    print("✔", dmg)
elif win:
    print("✔ dist/Didban.exe")
sys.exit(0)
