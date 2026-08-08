#!/usr/bin/env python3
"""
Marktplaats Barcode Scanner

Koppel een USB-barcodescanner aan de productdatabase (dezelfde XML of
Google Sheets als marktplaats_productmanager.py en
marktplaats_automater_gtk.py gebruiken). Scan het artikelnummer, en de
omschrijving + details verschijnen direct in beeld.

Een USB-barcodescanner gedraagt zich als een toetsenbord: hij "typt" de
gescande code gevolgd door Enter. Dit venster hoeft dus alleen focus op
een tekstveld te houden - er is geen speciale scanner-driver nodig.
"""

import gi
gi.require_version('Gtk', '3.0')
from gi.repository import Gtk, Gdk, GLib, GdkPixbuf, Pango
import os
import sys
import json
import subprocess
import datetime

# ============================================
# KOLOMSTRUCTUUR (gedeeld met de andere apps)
# ============================================
COLUMNS = [
    "artikelnummer", "titel", "categorie", "omschrijving", "online",
    "lengte", "breedte", "hoogte", "gewicht", "conditie", "staat_details",
    "waarde_min", "waarde_max", "vraagprijs", "aanmaakdatum", "aanmaaktijd",
    "tijdsperiode", "opslaglocatie", "sublocatie", "rij", "folder_locatie",
    "verkocht", "verkoopprijs", "verkoopdatum", "algemene_voorwaarden",
    "url_1", "url_2", "url_3", "url_4", "url_5",
    "leverwijze", "klant_naam", "klant_telefoon", "klant_email",
    "ophaal_afspraak", "track_trace", "verwerkt_door", "toegewezen_aan",
]

TEXTVIEW_CSS = b"""
textview {
    border: 1px solid alpha(@borders, 0.6);
    border-radius: 4px;
}
textview text {
    background-color: #3a3a3a;
    color: #e8e8e8;
    padding: 8px;
}
"""


def apply_css():
    provider = Gtk.CssProvider()
    provider.load_from_data(TEXTVIEW_CSS)
    screen = Gdk.Screen.get_default()
    Gtk.StyleContext.add_provider_for_screen(
        screen, provider, Gtk.STYLE_PROVIDER_PRIORITY_APPLICATION
    )


def config_dir():
    return os.path.dirname(os.path.abspath(__file__))


def config_path():
    return os.path.join(config_dir(), "scanner_config.json")


# ============================================
# CONFIGURATIE
# ============================================
class ConfigManager:
    DEFAULTS = {
        "storage": {
            "backend": "xml",  # "xml" of "sheets"
            "xml_path": os.path.join(config_dir(), "producten.xml"),
        },
        "sheets": {
            "sheet_url": "",
            "credentials_file": os.path.join(config_dir(), "credentials.json"),
        },
    }

    def __init__(self):
        self.path = config_path()
        self.data = self._load()

    def _load(self):
        if os.path.exists(self.path):
            try:
                with open(self.path, "r", encoding="utf-8") as f:
                    loaded = json.load(f)
                merged = json.loads(json.dumps(self.DEFAULTS))
                merged.update(loaded)
                return merged
            except Exception:
                pass
        return json.loads(json.dumps(self.DEFAULTS))

    def save(self):
        with open(self.path, "w", encoding="utf-8") as f:
            json.dump(self.data, f, indent=2, ensure_ascii=False)

    def get(self, key, default=None):
        return self.data.get(key, default)

    def set(self, key, value):
        self.data[key] = value
        self.save()


# ============================================
# OPSLAG (alleen lezen + markeren-als-verkocht)
# ============================================
def load_all_products_xml(xml_path):
    import xml.etree.ElementTree as ET
    if not os.path.exists(xml_path):
        raise FileNotFoundError(f"XML-bestand niet gevonden: {xml_path}")
    tree = ET.parse(xml_path)
    root = tree.getroot()
    products = []
    for prod_el in root.findall("product"):
        product = {}
        for col in COLUMNS:
            el = prod_el.find(col)
            product[col] = el.text if el is not None and el.text else ""
        products.append(product)
    return products


def save_all_products_xml(xml_path, products):
    import xml.etree.ElementTree as ET
    root = ET.Element("producten")
    for product in products:
        prod_el = ET.SubElement(root, "product")
        for col in COLUMNS:
            el = ET.SubElement(prod_el, col)
            el.text = str(product.get(col, ""))
    tree = ET.ElementTree(root)
    tree.write(xml_path, encoding="utf-8", xml_declaration=True)


def get_sheets_worksheet(sheet_url, credentials_file):
    import gspread
    from google.oauth2.service_account import Credentials
    scopes = [
        "https://www.googleapis.com/auth/spreadsheets",
        "https://www.googleapis.com/auth/drive",
    ]
    creds = Credentials.from_service_account_file(credentials_file, scopes=scopes)
    client = gspread.authorize(creds)
    sheet = client.open_by_url(sheet_url)
    return sheet.get_worksheet(0)


def load_all_products_sheets(sheet_url, credentials_file):
    ws = get_sheets_worksheet(sheet_url, credentials_file)
    all_values = ws.get_all_values()
    products = []
    for row in all_values[1:]:
        if not row or not row[0]:
            continue
        product = {}
        for i, col in enumerate(COLUMNS):
            product[col] = row[i] if i < len(row) else ""
        products.append(product)
    return products


def find_product(config, artikelnummer):
    """Zoekt één product op artikelnummer. Retourneert (product_dict, None)
    of (None, foutmelding)."""
    backend = config.get("storage", {}).get("backend", "xml")
    artikelnummer = artikelnummer.strip()
    try:
        if backend == "xml":
            xml_path = config.get("storage", {}).get("xml_path", "")
            products = load_all_products_xml(xml_path)
        else:
            sheets_cfg = config.get("sheets", {})
            products = load_all_products_sheets(
                sheets_cfg.get("sheet_url", ""), sheets_cfg.get("credentials_file", "")
            )
    except Exception as e:
        return None, f"Kon opslag niet lezen: {e}"

    for p in products:
        if p.get("artikelnummer", "").strip() == artikelnummer:
            return p, None
    return None, f"Geen product gevonden met artikelnummer '{artikelnummer}'"


def mark_product_sold(config, artikelnummer, verkoopprijs):
    """Markeert een product als verkocht in de actieve opslag."""
    backend = config.get("storage", {}).get("backend", "xml")
    vandaag = datetime.date.today().isoformat()

    if backend == "xml":
        xml_path = config.get("storage", {}).get("xml_path", "")
        products = load_all_products_xml(xml_path)
        gevonden = False
        for p in products:
            if p.get("artikelnummer", "").strip() == artikelnummer:
                p["verkocht"] = "ja"
                p["verkoopprijs"] = verkoopprijs
                p["verkoopdatum"] = vandaag
                gevonden = True
                break
        if not gevonden:
            raise ValueError("Product niet gevonden in XML")
        save_all_products_xml(xml_path, products)
    else:
        sheets_cfg = config.get("sheets", {})
        ws = get_sheets_worksheet(sheets_cfg.get("sheet_url", ""), sheets_cfg.get("credentials_file", ""))
        all_values = ws.get_all_values()
        row_num = None
        for idx, row in enumerate(all_values, start=1):
            if row and row[0] == artikelnummer:
                row_num = idx
                break
        if row_num is None:
            raise ValueError("Product niet gevonden in Google Sheets")
        ws.update_cell(row_num, COLUMNS.index("verkocht") + 1, "ja")
        ws.update_cell(row_num, COLUMNS.index("verkoopprijs") + 1, verkoopprijs)
        ws.update_cell(row_num, COLUMNS.index("verkoopdatum") + 1, vandaag)

    return vandaag


def get_omschrijving_tekst(product):
    """Geeft de omschrijving.txt uit de productmap terug indien aanwezig,
    anders de losse omschrijving-kolom."""
    folder = product.get("folder_locatie", "").strip()
    if folder:
        txt_path = os.path.join(folder, "omschrijving.txt")
        if os.path.exists(txt_path):
            try:
                with open(txt_path, "r", encoding="utf-8") as f:
                    inhoud = f.read().strip()
                if inhoud:
                    return inhoud
            except Exception:
                pass
    return product.get("omschrijving", "")


# ============================================
# INSTELLINGEN-DIALOOG
# ============================================
class SettingsDialog(Gtk.Dialog):
    def __init__(self, parent, config):
        super().__init__(title="Instellingen", transient_for=parent, flags=0)
        self.config = config
        self.set_default_size(500, 320)
        self.add_buttons(Gtk.STOCK_CANCEL, Gtk.ResponseType.CANCEL, Gtk.STOCK_SAVE, Gtk.ResponseType.OK)
        
        box = self.get_content_area()
        box.set_spacing(10)
        box.set_border_width(15)
        
        box.pack_start(self._section_label("Opslagmethode"), False, False, 0)
        self.backend_combo = Gtk.ComboBoxText()
        self.backend_combo.append("xml", "Lokaal XML-bestand")
        self.backend_combo.append("sheets", "Google Sheets")
        self.backend_combo.set_active_id(config.get("storage", {}).get("backend", "xml"))
        self.backend_combo.connect("changed", self._on_backend_changed)
        box.pack_start(self.backend_combo, False, False, 0)
        
        hint = Gtk.Label()
        hint.set_markup("<small><i>⚠️ Moet overeenkomen met de opslagmethode in de andere Marktplaats-apps.</i></small>")
        hint.set_xalign(0)
        hint.set_line_wrap(True)
        box.pack_start(hint, False, False, 0)
        
        self.xml_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=3)
        box.pack_start(self.xml_box, False, False, 0)
        self.xml_box.pack_start(Gtk.Label(label="XML-bestandspad:", xalign=0), False, False, 0)
        xml_row = Gtk.Box(spacing=5)
        self.xml_path_entry = Gtk.Entry()
        self.xml_path_entry.set_text(config.get("storage", {}).get("xml_path", ""))
        xml_row.pack_start(self.xml_path_entry, True, True, 0)
        browse_xml_btn = Gtk.Button(label="Bladeren")
        browse_xml_btn.connect("clicked", self._browse_xml)
        xml_row.pack_start(browse_xml_btn, False, False, 0)
        self.xml_box.pack_start(xml_row, False, False, 0)
        
        self.sheets_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=3)
        box.pack_start(self.sheets_box, False, False, 0)
        self.sheets_box.pack_start(Gtk.Label(label="Google Sheets URL:", xalign=0), False, False, 0)
        self.sheet_url_entry = Gtk.Entry()
        self.sheet_url_entry.set_text(config.get("sheets", {}).get("sheet_url", ""))
        self.sheets_box.pack_start(self.sheet_url_entry, False, False, 0)
        
        self.sheets_box.pack_start(Gtk.Label(label="credentials.json pad:", xalign=0), False, False, 0)
        creds_row = Gtk.Box(spacing=5)
        self.creds_entry = Gtk.Entry()
        self.creds_entry.set_text(config.get("sheets", {}).get("credentials_file", ""))
        creds_row.pack_start(self.creds_entry, True, True, 0)
        browse_creds_btn = Gtk.Button(label="Bladeren")
        browse_creds_btn.connect("clicked", self._browse_creds)
        creds_row.pack_start(browse_creds_btn, False, False, 0)
        self.sheets_box.pack_start(creds_row, False, False, 0)
        
        self._on_backend_changed(self.backend_combo)
        self.show_all()
    
    def _section_label(self, text):
        label = Gtk.Label()
        label.set_markup(f"<b>{text}</b>")
        label.set_xalign(0)
        return label
    
    def _on_backend_changed(self, widget):
        is_xml = self.backend_combo.get_active_id() == "xml"
        self.xml_box.set_visible(is_xml)
        self.sheets_box.set_visible(not is_xml)
    
    def _browse_xml(self, widget):
        dialog = Gtk.FileChooserDialog(
            title="Selecteer producten.xml", transient_for=self, action=Gtk.FileChooserAction.OPEN
        )
        dialog.add_buttons(Gtk.STOCK_CANCEL, Gtk.ResponseType.CANCEL, Gtk.STOCK_OPEN, Gtk.ResponseType.OK)
        response = dialog.run()
        if response == Gtk.ResponseType.OK:
            self.xml_path_entry.set_text(dialog.get_filename())
        dialog.destroy()
    
    def _browse_creds(self, widget):
        dialog = Gtk.FileChooserDialog(
            title="Selecteer credentials.json", transient_for=self, action=Gtk.FileChooserAction.OPEN
        )
        dialog.add_buttons(Gtk.STOCK_CANCEL, Gtk.ResponseType.CANCEL, Gtk.STOCK_OPEN, Gtk.ResponseType.OK)
        response = dialog.run()
        if response == Gtk.ResponseType.OK:
            self.creds_entry.set_text(dialog.get_filename())
        dialog.destroy()
    
    def apply_to_config(self):
        self.config.set("storage", {
            "backend": self.backend_combo.get_active_id(),
            "xml_path": self.xml_path_entry.get_text().strip(),
        })
        self.config.set("sheets", {
            "sheet_url": self.sheet_url_entry.get_text().strip(),
            "credentials_file": self.creds_entry.get_text().strip(),
        })


# ============================================
# HOOFDVENSTER
# ============================================
class MainWindow(Gtk.Window):
    def __init__(self):
        super().__init__(title="Marktplaats Barcode Scanner")
        self.set_default_size(750, 650)
        self.set_position(Gtk.WindowPosition.CENTER)
        self.set_border_width(15)
        
        icon_path = os.path.join(config_dir(), "icon.png")
        if os.path.exists(icon_path):
            try:
                self.set_icon_from_file(icon_path)
            except Exception:
                pass
        
        self.config = ConfigManager()
        self.huidig_product = None
        self.geschiedenis = []  # laatst gescande artikelnummers, nieuwste eerst
        
        vbox = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=12)
        self.add(vbox)
        
        # Bovenbalk: instellingen
        top_row = Gtk.Box(spacing=5)
        settings_btn = Gtk.Button(label="⚙️ Instellingen")
        settings_btn.connect("clicked", self._open_settings)
        top_row.pack_end(settings_btn, False, False, 0)
        self.backend_label = Gtk.Label()
        self._update_backend_label()
        top_row.pack_start(self.backend_label, False, False, 0)
        vbox.pack_start(top_row, False, False, 0)
        
        # Scanveld
        scan_label = Gtk.Label()
        scan_label.set_markup("<b>Scan een barcode (artikelnummer)</b>")
        scan_label.set_xalign(0)
        vbox.pack_start(scan_label, False, False, 0)
        
        self.scan_entry = Gtk.Entry()
        self.scan_entry.set_placeholder_text("Klik hier en scan de barcode...")
        self.scan_entry.override_font(Pango.FontDescription("Monospace 20"))
        self.scan_entry.connect("activate", self._on_scan)
        vbox.pack_start(self.scan_entry, False, False, 0)
        
        self.status_label = Gtk.Label()
        self.status_label.set_xalign(0)
        self.status_label.set_line_wrap(True)
        vbox.pack_start(self.status_label, False, False, 0)
        
        # Resultaat
        result_scroll = Gtk.ScrolledWindow()
        result_scroll.set_policy(Gtk.PolicyType.NEVER, Gtk.PolicyType.AUTOMATIC)
        result_scroll.set_vexpand(True)
        vbox.pack_start(result_scroll, True, True, 0)
        
        self.result_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=10)
        self.result_box.set_border_width(5)
        result_scroll.add(self.result_box)
        
        self._toon_lege_state()
        
        # Geschiedenis
        hist_label = Gtk.Label()
        hist_label.set_markup("<b>Recent gescand</b>")
        hist_label.set_xalign(0)
        vbox.pack_start(hist_label, False, False, 0)
        
        self.hist_store = Gtk.ListStore(str, str, str)  # artikelnummer, titel, tijd
        self.hist_view = Gtk.TreeView(model=self.hist_store)
        for i, label in enumerate(["Artikelnummer", "Titel", "Tijd"]):
            renderer = Gtk.CellRendererText()
            column = Gtk.TreeViewColumn(label, renderer, text=i)
            self.hist_view.append_column(column)
        self.hist_view.connect("row-activated", self._on_hist_row_activated)
        
        hist_scroll = Gtk.ScrolledWindow()
        hist_scroll.set_size_request(-1, 140)
        hist_scroll.add(self.hist_view)
        vbox.pack_start(hist_scroll, False, False, 0)
        
        self.connect("show", lambda w: self.scan_entry.grab_focus())
    
    def _update_backend_label(self):
        backend = self.config.get("storage", {}).get("backend", "xml")
        naam = "Lokaal XML" if backend == "xml" else "Google Sheets"
        self.backend_label.set_markup(f"<small>Actieve opslag: <b>{naam}</b></small>")
    
    def _open_settings(self, widget):
        dialog = SettingsDialog(self, self.config)
        response = dialog.run()
        if response == Gtk.ResponseType.OK:
            dialog.apply_to_config()
            self._update_backend_label()
        dialog.destroy()
    
    def _toon_lege_state(self):
        for child in self.result_box.get_children():
            self.result_box.remove(child)
        placeholder = Gtk.Label()
        placeholder.set_markup("<span foreground='gray'><i>Nog geen product gescand.</i></span>")
        self.result_box.pack_start(placeholder, False, False, 20)
        self.result_box.show_all()
    
    def _on_scan(self, widget):
        code = self.scan_entry.get_text().strip()
        self.scan_entry.set_text("")
        self.scan_entry.grab_focus()
        
        if not code:
            return
        
        self.status_label.set_markup(f"<span foreground='blue'>🔄 Zoeken naar '{code}'...</span>")
        while Gtk.events_pending():
            Gtk.main_iteration()
        
        product, fout = find_product(self.config, code)
        
        if fout:
            self.status_label.set_markup(f"<span foreground='red'>❌ {fout}</span>")
            return
        
        self.status_label.set_text("")
        self.huidig_product = product
        self._toon_product(product)
        self._voeg_toe_aan_geschiedenis(product)
    
    def _voeg_toe_aan_geschiedenis(self, product):
        tijd = datetime.datetime.now().strftime("%H:%M:%S")
        self.hist_store.prepend([product.get("artikelnummer", ""), product.get("titel", ""), tijd])
        # geschiedenis niet onbeperkt laten groeien
        while len(self.hist_store) > 50:
            laatste_iter = self.hist_store[len(self.hist_store) - 1].iter
            self.hist_store.remove(laatste_iter)
    
    def _on_hist_row_activated(self, tree_view, path, column):
        artikelnummer = self.hist_store[path][0]
        product, fout = find_product(self.config, artikelnummer)
        if fout:
            self.status_label.set_markup(f"<span foreground='red'>❌ {fout}</span>")
            return
        self.status_label.set_text("")
        self.huidig_product = product
        self._toon_product(product)
    
    def _toon_product(self, product):
        for child in self.result_box.get_children():
            self.result_box.remove(child)
        
        titel_label = Gtk.Label()
        verkocht = product.get("verkocht", "").strip().lower() == "ja"
        online = product.get("online", "").strip().lower() == "ja"
        if verkocht:
            status_tekst, status_kleur = "💰 VERKOCHT", "orange"
        elif online:
            status_tekst, status_kleur = "🌐 ONLINE", "#4a9eff"
        else:
            status_tekst, status_kleur = "⚪ OFFLINE (nog niet geplaatst)", "gray"
        titel_label.set_markup(
            f"<span size='x-large' weight='bold'>{GLib.markup_escape_text(product.get('titel', ''))}</span>\n"
            f"<span foreground='{status_kleur}'>{status_tekst}</span>"
        )
        titel_label.set_xalign(0)
        titel_label.set_line_wrap(True)
        self.result_box.pack_start(titel_label, False, False, 0)
        
        if verkocht and product.get("leverwijze", "").strip().lower() == "ophalen":
            verificatie = Gtk.Label()
            klant = GLib.markup_escape_text(product.get("klant_naam", "") or "(geen naam ingevuld)")
            prijs = GLib.markup_escape_text(product.get("verkoopprijs", "") or "?")
            verificatie.set_markup(
                f"<span background='#2d4a2d' foreground='#a0e0a0' size='large'>"
                f"  ✅ OPHALEN - controleer: <b>{klant}</b> - €{prijs}  "
                f"</span>"
            )
            verificatie.set_xalign(0)
            verificatie.set_margin_top(6)
            verificatie.set_margin_bottom(6)
            self.result_box.pack_start(verificatie, False, False, 0)
        
        # Kerngegevens
        grid = Gtk.Grid()
        grid.set_column_spacing(15)
        grid.set_row_spacing(4)
        self.result_box.pack_start(grid, False, False, 0)
        
        velden = [
            ("Artikelnummer", product.get("artikelnummer", "")),
            ("Categorie", product.get("categorie", "")),
            ("Tijdsperiode", product.get("tijdsperiode", "")),
            ("Conditie", product.get("conditie", "")),
            ("Staat details", product.get("staat_details", "")),
            ("Afmetingen (LxBxH)", self._afmetingen_tekst(product)),
            ("Gewicht", f"{product.get('gewicht', '')} kg" if product.get("gewicht") else ""),
            ("Geschatte waarde", self._waarde_tekst(product)),
            ("Vraagprijs", f"€{product.get('vraagprijs', '')}" if product.get("vraagprijs") else ""),
            ("Aanmaakdatum", product.get("aanmaakdatum", "")),
            ("Opslaglocatie", " / ".join(x for x in [
                product.get("opslaglocatie", ""), product.get("sublocatie", ""), product.get("rij", "")
            ] if x)),
            ("Verwerkt door", product.get("verwerkt_door", "")),
            ("Toegewezen aan", product.get("toegewezen_aan", "")),
        ]
        if online:
            for i in range(1, 6):
                url = product.get(f"url_{i}", "")
                if url:
                    velden.append((f"Advertentie-URL {i}", url))
        if verkocht:
            velden.append(("Verkoopprijs", f"€{product.get('verkoopprijs', '')}"))
            velden.append(("Verkoopdatum", product.get("verkoopdatum", "")))
            leverwijze = product.get("leverwijze", "").strip().lower()
            velden.append(("Leverwijze", "📦 Ophalen" if leverwijze == "ophalen" else "🚚 Verzenden" if leverwijze == "verzenden" else ""))
            velden.append(("Marktplaatsnaam koper", product.get("klant_naam", "")))
            if leverwijze == "ophalen":
                velden.append(("Telefoonnummer", product.get("klant_telefoon", "")))
                velden.append(("E-mail", product.get("klant_email", "")))
                velden.append(("Afspraak", product.get("ophaal_afspraak", "")))
            elif leverwijze == "verzenden":
                velden.append(("Track & Trace", product.get("track_trace", "")))
        
        for i, (label_tekst, waarde) in enumerate(velden):
            if not waarde:
                continue
            l = Gtk.Label(label=f"{label_tekst}:")
            l.set_xalign(1)
            l.get_style_context().add_class("dim-label")
            grid.attach(l, 0, i, 1, 1)
            w = Gtk.Label(label=waarde)
            w.set_xalign(0)
            w.set_line_wrap(True)
            w.set_selectable(True)
            grid.attach(w, 1, i, 1, 1)
        
        # Omschrijving
        omschrijving_label = Gtk.Label()
        omschrijving_label.set_markup("<b>Omschrijving</b>")
        omschrijving_label.set_xalign(0)
        omschrijving_label.set_margin_top(10)
        self.result_box.pack_start(omschrijving_label, False, False, 0)
        
        omschrijving_view = Gtk.TextView()
        omschrijving_view.set_editable(False)
        omschrijving_view.set_wrap_mode(Gtk.WrapMode.WORD)
        omschrijving_view.get_buffer().set_text(get_omschrijving_tekst(product))
        omschrijving_scroll = Gtk.ScrolledWindow()
        omschrijving_scroll.set_size_request(-1, 180)
        omschrijving_scroll.add(omschrijving_view)
        self.result_box.pack_start(omschrijving_scroll, False, False, 0)
        
        # Acties
        actie_row = Gtk.Box(spacing=5)
        actie_row.set_margin_top(10)
        self.result_box.pack_start(actie_row, False, False, 0)
        
        folder = product.get("folder_locatie", "").strip()
        if folder and os.path.isdir(folder):
            open_map_btn = Gtk.Button(label="📁 Open productmap")
            open_map_btn.connect("clicked", lambda w: self._open_folder(folder))
            actie_row.pack_start(open_map_btn, False, False, 0)
        
        if not verkocht:
            verkocht_btn = Gtk.Button(label="💰 Markeer als verkocht")
            verkocht_btn.connect("clicked", lambda w: self._markeer_verkocht(product))
            actie_row.pack_start(verkocht_btn, False, False, 0)
        
        self.result_box.show_all()
    
    def _afmetingen_tekst(self, product):
        l, b, h = product.get("lengte", ""), product.get("breedte", ""), product.get("hoogte", "")
        if not (l or b or h):
            return ""
        return " x ".join(f"{x}cm" for x in (l, b, h) if x)
    
    def _waarde_tekst(self, product):
        vmin, vmax = product.get("waarde_min", ""), product.get("waarde_max", "")
        if not (vmin or vmax):
            return ""
        if vmin and vmax:
            return f"{vmin} ~{vmax}"
        return vmin or vmax
    
    def _open_folder(self, folder):
        try:
            subprocess.Popen(["xdg-open", folder])
        except Exception as e:
            self.status_label.set_markup(f"<span foreground='red'>❌ Kon map niet openen: {e}</span>")
    
    def _markeer_verkocht(self, product):
        dialog = Gtk.Dialog(title="Markeer als verkocht", transient_for=self, flags=0)
        dialog.add_buttons(Gtk.STOCK_CANCEL, Gtk.ResponseType.CANCEL, Gtk.STOCK_OK, Gtk.ResponseType.OK)
        box = dialog.get_content_area()
        box.set_spacing(8)
        box.set_border_width(10)
        box.pack_start(Gtk.Label(label=f"Verkoopprijs voor {product.get('artikelnummer', '')}:"), False, False, 0)
        prijs_entry = Gtk.Entry()
        prijs_entry.set_placeholder_text("bijv. 45.00")
        box.pack_start(prijs_entry, False, False, 0)
        dialog.show_all()
        response = dialog.run()
        prijs = prijs_entry.get_text().strip()
        dialog.destroy()
        
        if response == Gtk.ResponseType.OK and prijs:
            try:
                mark_product_sold(self.config, product.get("artikelnummer", ""), prijs)
                self.status_label.set_markup("<span foreground='green'>✅ Gemarkeerd als verkocht</span>")
                # Herlaad het product zodat de weergave klopt
                bijgewerkt, _ = find_product(self.config, product.get("artikelnummer", ""))
                if bijgewerkt:
                    self.huidig_product = bijgewerkt
                    self._toon_product(bijgewerkt)
            except Exception as e:
                self.status_label.set_markup(f"<span foreground='red'>❌ Kon niet opslaan: {e}</span>")
        
        self.scan_entry.grab_focus()


def main():
    GLib.set_prgname("marktplaats_barcode_scanner")
    apply_css()
    win = MainWindow()
    win.connect("destroy", Gtk.main_quit)
    win.show_all()
    Gtk.main()


if __name__ == "__main__":
    main()
