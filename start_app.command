#!/usr/bin/env bash
# Double-click this file to start the Hydrogel Diagram Maker (macOS).
# (Linux: run ./start_app.command in a terminal.)
cd "$(dirname "$0")" || exit 1

if ! command -v python3 >/dev/null 2>&1 || \
   ! python3 -c 'import sys; sys.exit(sys.version_info < (3, 10))' 2>/dev/null; then
    echo
    echo "Python 3.10 or newer is needed but was not found."
    echo "Download it from https://www.python.org/downloads/ ,"
    echo "install it, then double-click this file again."
    echo
    read -r -p "Press Enter to close."
    exit 1
fi

echo "Getting everything ready. The first time this takes a few minutes..."
# Everything is installed into a private .venv folder next to this file.
if [ ! -x .venv/bin/python ] && ! python3 -m venv .venv; then
    echo
    echo "Could not create the .venv folder - see the message above."
    read -r -p "Press Enter to close."
    exit 1
fi
if ! .venv/bin/python -m pip install --quiet --disable-pip-version-check -r requirements.txt; then
    echo
    echo "Something went wrong while installing - see the message above."
    read -r -p "Press Enter to close."
    exit 1
fi
echo
echo "Starting. Your web browser will open in a moment."
echo "KEEP THIS WINDOW OPEN while you use the app. Close it when you are done."
echo
.venv/bin/python -m streamlit run app.py
