#!/usr/bin/env bash
# Start the Hydrogel Diagram Maker (macOS / Linux): ./start_app.sh
cd "$(dirname "$0")"
python3 -m pip install -q -r requirements.txt
python3 -m streamlit run app.py
