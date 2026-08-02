#!/bin/bash
# Installatie voor marktplaats_barcode_scanner.py
# Draai dit vanuit dezelfde map als het script zelf

set -e

APP_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

echo "📦 GTK/PyGObject installeren..."
sudo apt update
sudo apt install -y python3-gi gir1.2-gtk-3.0 python3-pip

echo "📦 Python-packages installeren (alleen nodig als je Google Sheets gebruikt)..."
pip install --break-system-packages gspread google-auth

# Icoon (optioneel, zet zelf icon.png naast dit script)
if [ -f "$APP_DIR/icon.png" ]; then
    echo "🖼️  Icoon gevonden"
else
    echo "⚠️  Geen icon.png gevonden - snelkoppeling krijgt geen custom icoon"
fi

# Startscript aanmaken (X11 forceren voor betrouwbare WM_CLASS-matching)
cat > "$APP_DIR/start_scanner.sh" << EOF
#!/bin/bash
cd "\$(dirname "\$0")"
export GDK_BACKEND=x11
export XDG_SESSION_TYPE=x11
python3 marktplaats_barcode_scanner.py
EOF
chmod +x "$APP_DIR/start_scanner.sh"
echo "✅ start_scanner.sh aangemaakt"

# Desktop-snelkoppeling
cat > "$APP_DIR/MarktplaatsBarcodeScanner.desktop" << EOF
[Desktop Entry]
Version=1.0
Type=Application
Name=Marktplaats Barcode Scanner
Comment=Scan een artikelnummer en bekijk direct de productgegevens
Exec=$APP_DIR/start_scanner.sh
Icon=$APP_DIR/icon.png
Terminal=false
StartupNotify=true
StartupWMClass=marktplaats_barcode_scanner
Categories=Utility;Office;
EOF
chmod +x "$APP_DIR/MarktplaatsBarcodeScanner.desktop"

mkdir -p ~/.local/share/applications
cp "$APP_DIR/MarktplaatsBarcodeScanner.desktop" ~/.local/share/applications/
update-desktop-database ~/.local/share/applications 2>/dev/null || true
echo "✅ Snelkoppeling aangemaakt en toegevoegd aan het applicatiemenu"

echo ""
echo "✅ Klaar. Start de app op 2 manieren:"
echo "   1. cd $APP_DIR && ./start_scanner.sh"
echo "   2. Zoek 'Marktplaats Barcode Scanner' in het applicatiemenu"
echo ""
echo "📌 Open daarna '⚙️ Instellingen' en kies dezelfde opslagmethode"
echo "   (XML-pad of Google Sheets) als je in de andere Marktplaats-apps gebruikt."
