name: Build Didban (exe + dmg)

on:
  workflow_dispatch:
  push:
    tags: ["v*"]

jobs:
  build:
    strategy:
      fail-fast: false
      matrix:
        include:
          - os: windows-latest
            file: dist/Didban.exe
            label: Didban-Windows
          - os: macos-14          # Apple Silicon (M1/M2/M3)
            file: dist/Didban.dmg
            label: Didban-macOS-AppleSilicon
          - os: macos-13          # Intel
            file: dist/Didban.dmg
            label: Didban-macOS-Intel
    runs-on: ${{ matrix.os }}
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with:
          python-version: "3.11"
      - name: Fetch Vazirmatn font
        shell: bash
        continue-on-error: true
        run: |
          for w in Regular Bold Black; do
            curl -fsSL -o "didban/assets/Vazirmatn-$w.ttf" \
              "https://raw.githubusercontent.com/rastikerdar/vazirmatn/master/fonts/ttf/Vazirmatn-$w.ttf" || true
          done
      - name: Install
        run: python -m pip install -r requirements.txt pyinstaller pillow
      - name: Build
        run: python build.py
      - uses: actions/upload-artifact@v4
        with:
          name: ${{ matrix.label }}
          path: ${{ matrix.file }}

  release:
    if: startsWith(github.ref, 'refs/tags/')
    needs: build
    runs-on: ubuntu-latest
    permissions:
      contents: write
    steps:
      - uses: actions/download-artifact@v4
        with:
          path: out
      - name: Rename
        run: |
          mv out/Didban-Windows/Didban.exe out/Didban-Windows.exe
          mv out/Didban-macOS-AppleSilicon/Didban.dmg out/Didban-macOS-AppleSilicon.dmg
          mv out/Didban-macOS-Intel/Didban.dmg out/Didban-macOS-Intel.dmg
      - uses: softprops/action-gh-release@v2
        with:
          files: out/*.*
