#!/bin/bash
cd "$(dirname "$0")"
export GDK_BACKEND=x11
export XDG_SESSION_TYPE=x11
python3 marktplaats_barcode_scanner.py
