"""
Ask3lad War Thunder Test Drive GUI 2.5
---------------------------------------
A PyQt6 desktop application for customising Ask3lad's custom War Thunder
missions. These are community missions created and distributed by Ask3lad —
not official Gaijin test drives.

Players install the mission files into their War Thunder UserMissions folder,
then use this tool to configure vehicles, targets, and environment before
launching the mission in-game.

Ground mission edits:
  - UserMissions/Ask3lad/ask3lad_testdrive.blk       (mission definition)
  - content/pkg_local/gameData/units/tankModels/userVehicles/us_m2a4.blk
    (one-line include file — swapped to point at the chosen tank)

Naval mission edits:
  - UserMissions/Ask3lad/ask3lad_testdrive_naval.blk  (mission definition)
  - content/pkg_local/gameData/units/ships/userVehicles/us_pt6.blk
    (one-line include file — swapped to point at the chosen ship)

Both modes use the same include-line-swap pattern for the player vehicle file.
Vehicle, aircraft, helicopter, and ship data is loaded from JSON databases
in the Assets/ folder. The WT directory path is persisted in config.json
next to this script.
"""

import sys
import os
import json
import math
import re
import webbrowser
import urllib.request
import random
import traceback
import datetime

from PyQt6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QLineEdit, QListWidget, QListWidgetItem, QPushButton, QLabel,
    QFileDialog, QMessageBox, QTabWidget, QComboBox, QGroupBox, QDialog, QGridLayout, QButtonGroup,
    QInputDialog, QSlider, QSpinBox, QDoubleSpinBox, QDial, QCheckBox, QRadioButton
)
from PyQt6.QtCore import Qt, QThread, QTimer, pyqtSignal
from PyQt6.QtGui import QIcon, QPixmap, QAction, QColor, QPalette


# ── Crash Logger ─────────────────────────────────────────────────────────────
# When running as a PyInstaller exe, __file__ points to the temp extraction
# directory, not the exe's real location. Use sys.executable instead.
if getattr(sys, 'frozen', False):
    _APP_DIR = os.path.dirname(sys.executable)
else:
    _APP_DIR = os.path.dirname(os.path.abspath(__file__))
_LOGS_DIR  = os.path.join(_APP_DIR, "Logs")
_MAX_CRASHES = 10

def _collect_app_state():
    """Collect current app state from the running GUI window, if available."""
    try:
        app = QApplication.instance()
        if not app:
            return "  App not initialised\n"
        for widget in app.topLevelWidgets():
            if isinstance(widget, QMainWindow):
                w = widget
                break
        else:
            return "  Window not found\n"

        lines = []
        mode = getattr(w, "mode_tabs", None)
        mode_name = "Ground" if (mode and mode.currentIndex() == 0) else "Naval"
        lines.append(f"  Mode:                {mode_name}")

        # Ground state
        lines.append("")
        lines.append("  [Ground]")
        vid = getattr(w, "Current_Vehicle_ID", None)
        lines.append(f"  Selected Vehicle:    {vid or 'Not set'}")

        wo_mode = getattr(w, "weapon_override_mode", "none")
        if wo_mode != "none":
            donor = (getattr(w, "weapon_override_donor_id", "")
                     or getattr(w, "naval_weapon_override_donor_id", "")
                     or getattr(w, "aircraft_weapon_override_donor_id", ""))
            weapon_blk = (getattr(w, "weapon_override_current_weapon_blk", "")
                          or getattr(w, "naval_weapon_override_current_weapon_blk", "")
                          or getattr(w, "aircraft_weapon_override_current_weapon_blk", ""))
            weapon_name = weapon_blk.split("/")[-1].replace(".blk", "") if weapon_blk else "Not set"
            lines.append(f"  Weapon Override:     {wo_mode} / {donor or 'Not set'} / {weapon_name}")
            vel_active = getattr(w, "velocity_override_active", False)
            cal_active = getattr(w, "caliber_override_active", False)
            lines.append(f"  Velocity Override:   {'Enabled' if vel_active else 'Disabled'}")
            lines.append(f"  Caliber Override:    {'Enabled' if cal_active else 'Disabled'}")
            wt_dir = getattr(w, "_wt_dir", None)
            if wt_dir and (vel_active or cal_active):
                big_path = os.path.join(wt_dir, 'content', 'pkg_local',
                                        'gameData', 'weapons', 'ask3lad', 'Ask3ladBigWeaponSir.blk')
                lines.append(f"  BigWeaponSir.blk path: {big_path}")
                if os.path.exists(big_path):
                    try:
                        with open(big_path, encoding="utf-8") as _f:
                            lines.append("  BigWeaponSir.blk contents:")
                            for _line in _f.read().splitlines():
                                lines.append(f"    {_line}")
                    except Exception as _e:
                        lines.append(f"  (Could not read BigWeaponSir.blk: {_e})")
                else:
                    lines.append("  BigWeaponSir.blk: (not found)")
        else:
            lines.append(f"  Weapon Override:     None")

        lines.append(f"  Target 03:           {getattr(w, 'target03_id', None) or 'Not set'}")
        lines.append(f"  Target 04:           {getattr(w, 'target04_id', None) or 'Not set'}")
        lines.append(f"  Target 05:           {getattr(w, 'target05_id', None) or 'Not set'}")
        lines.append(f"  Moving Target:       {getattr(w, 'target06_id', None) or 'Not set'}")
        lines.append(f"  Naval Target:        {getattr(w, 'ship_target_id', None) or 'Not set'}")
        lines.append(f"  Air 01 (5km):        {getattr(w, 'air01_id', None) or 'Not set'}")
        lines.append(f"  Air 02 (2.5km):      {getattr(w, 'air02_id', None) or 'Not set'}")
        lines.append(f"  Helicopter (2km):    {getattr(w, 'heli_id', None) or 'Not set'}")

        # Naval state
        lines.append("")
        lines.append("  [Naval]")
        lines.append(f"  You (Naval):         {getattr(w, 'current_naval_vehicle_id', None) or 'Not set'}")
        lines.append(f"  Target 01:           {getattr(w, 'naval_target01_id', None) or 'Not set'}")
        lines.append(f"  Target 02:           {getattr(w, 'naval_target02_id', None) or 'Not set'}")
        lines.append(f"  Target 03:           {getattr(w, 'naval_target03_id', None) or 'Not set'}")
        lines.append(f"  Target 04:           {getattr(w, 'naval_target04_id', None) or 'Not set'}")
        lines.append(f"  Air 01:              {getattr(w, 'naval_air01_id', None) or 'Not set'}")
        lines.append(f"  Air 02:              {getattr(w, 'naval_air02_id', None) or 'Not set'}")

        return "\n".join(lines) + "\n"
    except Exception as e:
        return f"  (Could not collect state: {e})\n"


def _write_crash_log(exc_type, exc_value, exc_tb):
    """Write a timestamped crash report to Logs/crash_YYYY-MM-DD_HH-MM-SS.txt."""
    try:
        os.makedirs(_LOGS_DIR, exist_ok=True)

        # Prune old logs if over limit
        existing_logs = sorted(
            f for f in os.listdir(_LOGS_DIR) if f.startswith("crash_") and f.endswith(".txt")
        )
        while len(existing_logs) >= _MAX_CRASHES:
            os.remove(os.path.join(_LOGS_DIR, existing_logs.pop(0)))

        timestamp     = datetime.datetime.now()
        crash_log     = os.path.join(_LOGS_DIR, f"crash_{timestamp.strftime('%Y-%m-%d_%H-%M-%S')}.txt")
        tb_lines      = traceback.format_exception(exc_type, exc_value, exc_tb)
        tb_str        = "".join(tb_lines)
        state_str     = _collect_app_state()

        report = (
            f"{'=' * 60}\n"
            f"CRASH REPORT\n"
            f"Timestamp:  {timestamp.strftime('%Y-%m-%d %H:%M:%S')}\n"
            f"Version:    {APP_VERSION}\n"
            f"\n"
            f"--- Exception ---\n"
            f"Type:       {exc_type.__name__}\n"
            f"Message:    {exc_value}\n"
            f"\n"
            f"--- Traceback ---\n"
            f"{tb_str}\n"
            f"--- App State ---\n"
            f"{state_str}"
        )

        with open(crash_log, "w", encoding="utf-8") as f:
            f.write(report)

        return crash_log
    except Exception:
        return None  # Never let the crash logger itself crash


def _crash_handler(exc_type, exc_value, exc_tb):
    """Global unhandled exception hook — log then show a dialog."""
    crash_log = _write_crash_log(exc_type, exc_value, exc_tb)
    try:
        from PyQt6.QtWidgets import QMessageBox
        msg = QMessageBox()
        msg.setWindowTitle("Unexpected Error")
        msg.setIcon(QMessageBox.Icon.Critical)
        msg.setText(
            f"The application encountered an unexpected error and needs to close.\n\n"
            f"A crash report has been saved to:\n{crash_log or _LOGS_DIR}\n\n"
            f"Please send this file to Ask3lad so the issue can be fixed."
        )
        msg.exec()
    except Exception:
        pass
    sys.__excepthook__(exc_type, exc_value, exc_tb)


# ── Path helpers ──────────────────────────────────────────────────────────────
def _app_dir():
    """Return the directory containing the exe (frozen) or this script (dev)."""
    if getattr(sys, 'frozen', False):
        return os.path.dirname(sys.executable)
    return os.path.dirname(os.path.abspath(__file__))

# ── App Version ───────────────────────────────────────────────────────────────
APP_VERSION     = "2.51"
_APP_VERSION_URL = "https://raw.githubusercontent.com/ask3lad/wt-testdrive-db/main/app_version.json"

# ── War Thunder auto-detect paths ─────────────────────────────────────────────
_WT_SEARCH_PATHS = [
    r"C:/Program Files (x86)/Steam/steamapps/common/War Thunder",
    r"C:/Program Files/Steam/steamapps/common/War Thunder",
    r"C:/SteamLibrary/steamapps/common/War Thunder",
    r"C:/Steam/steamapps/common/War Thunder",
    r"C:/Games/War Thunder",
    r"C:/Program Files/War Thunder",
    r"D:/Steam/steamapps/common/War Thunder",
    r"D:/SteamLibrary/steamapps/common/War Thunder",
    r"D:/Games/War Thunder",
    r"D:/Program Files (x86)/Steam/steamapps/common/War Thunder",
    r"E:/Steam/steamapps/common/War Thunder",
    r"E:/SteamLibrary/steamapps/common/War Thunder",
    r"E:/Games/War Thunder",
    r"F:/Steam/steamapps/common/War Thunder",
    r"F:/SteamLibrary/steamapps/common/War Thunder",
    r"F:/Games/War Thunder",
]

# ── Database Auto-Update ──────────────────────────────────────────────────────
_DB_REPO_RAW    = "https://raw.githubusercontent.com/ask3lad/wt-testdrive-db/main"
_DB_VERSION_URL = f"{_DB_REPO_RAW}/db_version.json"
_DB_FILES = [
    "Tank2.0_DB.json",
    "Ships2.0_DB.json",
    "Plane2.0_DB.json",
    "Helicopter2.0_DB.json",
    "AmmoNames2.0_DB.json",
    "Weapons2.0_DB.json",
    "NavalWeapons2.0_DB.json",
    "AircraftWeapons2.0_DB.json",
    "db_version.json",
]

# ── Ammo pool alias map ───────────────────────────────────────────────────────
# Maps DB ammo-name prefixes that don't match the blk caliber name to the
# canonical pool key stored in ammo_limits.  Same logic as extract_ammo.py.
_AMMO_POOL_ALIASES = {
    "NATO":          ["120mm"],
    "USSR":          ["125mm"],
    "152mm":         ["127mm", "155mm"],
    "127mm":         ["152mm"],
    "12mm":          ["12"],
    "13mm":          ["13"],
    "14mm":          ["14"],
    "15mm":          ["20mm"],
    "50mm":          ["57mm"],
    "76mm":          ["77mm"],
    "100mm":         ["105mm"],
    "106mm":         ["105mm"],
    "125mm":         ["120mm"],
    "150mm":         ["136mm"],
    "begleitpanzer": ["127mm"],
}

def _ammo_pool_key(ammo_type, ammo_limits):
    """Return the canonical ammo_limits key for ammo_type, or None if not found."""
    prefix = ammo_type.split("_")[0]
    if prefix in ammo_limits:
        return prefix
    for fallback in _AMMO_POOL_ALIASES.get(prefix, []):
        if fallback in ammo_limits:
            return fallback
    return None

# ── Themed Presets ────────────────────────────────────────────────────────────
_GROUND_PRESETS = [
    {
        "name":        "WW1",
        "vehicle_id":  "germ_a7v",
        "ammo":        "",
        "environment": "Morning",
        "weather":     "rain",
        "target03_id": "fr_saint_chamond",
        "target04_id": "uk_mark_v",
        "target05_id": "ussr_garford_putilov",
        "air01_id":    "hp_12",
        "air02_id":    "fury_mk1",
        "heli_id":     "zeppelin",
    },
    {
        "name":        "WW2",
        "vehicle_id":  "germ_pzkpfw_vi_ausf_h1_tiger",
        "ammo":        "",
        "environment": "Morning",
        "weather":     "overcast",
        "target03_id": "us_m4a3e8_76w_sherman",
        "target04_id": "uk_a_22f_mk_7_churchill_1944",
        "target05_id": "ussr_t_34_1942",
        "air01_id":    "il_2m_1943",
        "air02_id":    "spitfire_mk1",
        "heli_id":     "sa_313b_france",
    },
    {
        "name":        "Gulf War",
        "vehicle_id":  "us_m1a1_abrams",
        "ammo":        "",
        "environment": "Noon",
        "weather":     "clear",
        "target03_id": "ussr_t_72a",
        "target04_id": "ussr_t_62m1",
        "target05_id": "ussr_bmp_2",
        "air01_id":    "a_10a_late",
        "air02_id":    "su_25",
        "heli_id":     "ah_64a",
    },
    {
        "name":        "Modern",
        "vehicle_id":  "ussr_t_90m_2020",
        "ammo":        "",
        "environment": "Day",
        "weather":     "clear",
        "target03_id": "us_m1a2_sep2_abrams",
        "target04_id": "germ_leopard_2a6",
        "target05_id": "uk_challenger_2_tes",
        "air01_id":    "f_16a_block_10",
        "air02_id":    "mig_29_9_13",
        "heli_id":     "ka_52",
    },
]
_NAVAL_PRESETS  = [
    {
        "name":           "Bombardment of Iwo Jima",
        "vehicle_id":     "jp_battleship_yamato",
        "ammo":           "",
        "environment":    "Dawn",
        "weather":        "clear",
        "target01_id":    "us_cruiser_atlanta_class_atlanta",
        "target02_id":    "us_battleship_iowa_class_iowa",
        "target03_id":    "us_aircraftcarrier_lexington",
        "target04_id":    "us_destroyer_fletcher",
        "air01_id":       "p-51d-30_usaaf_korea",
        "air02_id":       "b_24d",
        "cas_weapons":    "p-51d-30_mk78_mod2",
        "bomber_weapons": "b_24d_8x1000lbs",
        "shooter_ids": [
            "us_battleship_wyoming_class",
            "us_battleship_texas",
            "us_battleship_texas",
            "us_battleship_mississippi",
            "us_battleship_nevada",
            "us_battleship_tennessee",
            "us_aircraftcarrier_enterprise",
            "us_aircraftcarrier_lexington",
        ],
        "shooter_enabled": [True, True, True, True, True, True, True, True],
    },
]


class DbUpdateWorker(QThread):
    """
    Background thread that checks for and downloads database updates.

    Fetches db_version.json from the GitHub repo. If the remote version is
    higher than the locally stored version, downloads all DB files into the
    Assets/ folder and emits update_done with the new version number and date.
    Emits no_update if already on the latest version.
    All errors (no internet, timeout, bad response) are silently ignored so
    the app always starts normally even when offline.
    """

    update_done = pyqtSignal(float, str)  # (new version, date string)
    no_update   = pyqtSignal()          # already on the latest version

    def __init__(self, assets_folder, local_version):
        super().__init__()
        self.assets_folder = assets_folder
        self.local_version = local_version

    def run(self):
        try:
            with urllib.request.urlopen(_DB_VERSION_URL, timeout=5) as response:
                data = json.loads(response.read().decode("utf-8"))
            remote_version = float(data.get("version", 0))
            date = data.get("date", "Unknown")
            time = data.get("time", "")
            if time:
                date = f"{date}  {time}"
            if remote_version <= self.local_version:
                self.no_update.emit()
                return
            for filename in _DB_FILES:
                url  = f"{_DB_REPO_RAW}/{filename}"
                dest = os.path.join(self.assets_folder, filename)
                urllib.request.urlretrieve(url, dest)
            self.update_done.emit(remote_version, date)
        except Exception:
            pass  # Offline or any error — continue using local files


class AppUpdateWorker(QThread):
    """
    Background thread that checks for a new app version.

    Fetches app_version.json from GitHub. If the remote version string is
    different from the local APP_VERSION, emits update_available with the
    remote version string. Emits no_update if already on the latest version.
    All errors are silently ignored.
    """
    update_available = pyqtSignal(str)  # remote version string
    no_update        = pyqtSignal()

    def run(self):
        try:
            with urllib.request.urlopen(_APP_VERSION_URL, timeout=5) as response:
                data = json.loads(response.read().decode("utf-8"))
            remote = str(data.get("version", "")).strip()
            def _ver(v):
                try:
                    return tuple(int(x) for x in v.split("."))
                except Exception:
                    return (0,)
            if remote and _ver(remote) > _ver(APP_VERSION):
                self.update_available.emit(remote)
            elif remote:
                self.no_update.emit()
        except Exception:
            pass


# ── Shared Dialog ─────────────────────────────────────────────────────────────

class VehiclePickerDialog(QDialog):
    """
    A modal dialog for searching and selecting a vehicle from a list.

    Reused across ground targets, air targets, helicopter targets, naval ship
    targets, and naval air targets. Pass the appropriate data list and subfolder.

    Attributes:
        selected_id   (str | None): ID of the confirmed selection, or None.
        selected_name (str | None): Display name of the confirmed selection, or None.
    """

    def __init__(self, vehicle_data, parent=None, assets_folder=None, subfolder="Tank_Previews"):
        super().__init__(parent)
        self.setWindowTitle("Select Vehicle")
        self.setMinimumSize(300, 450)
        self.vehicle_data = vehicle_data
        self.selected_id = None
        self.selected_name = None
        self.assets_folder = assets_folder
        self.subfolder = subfolder

        layout = QVBoxLayout(self)

        preview_group = QGroupBox("Selected")
        preview_layout = QVBoxLayout(preview_group)
        preview_layout.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.preview = QLabel()
        self.preview.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.preview.setFixedSize(120, 120)
        preview_layout.addWidget(self.preview)
        self.preview_name = QLabel("-")
        self.preview_name.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.preview_name.setWordWrap(True)
        preview_layout.addWidget(self.preview_name)
        layout.addWidget(preview_group)

        self.search = QLineEdit()
        self.search.setPlaceholderText("Search vehicles...")
        self.search.textChanged.connect(self._filter)
        layout.addWidget(self.search)

        self.list = QListWidget()
        self.list.itemDoubleClicked.connect(self._confirm)
        self.list.currentItemChanged.connect(self._update_preview)
        layout.addWidget(self.list)

        btn = QPushButton("Select")
        btn.clicked.connect(self._confirm)
        layout.addWidget(btn)

        self._populate(self.vehicle_data)

    def _populate(self, data):
        self.list.clear()
        for v in data:
            if "name" in v:
                item = QListWidgetItem(v["name"])
                item.setData(Qt.ItemDataRole.UserRole, v["ID"])
                self.list.addItem(item)

    def _filter(self, text):
        term = text.lower()
        self._populate([v for v in self.vehicle_data if term in v.get("name", "").lower()])

    def _update_preview(self, current, previous):
        if not current or not self.assets_folder:
            self.preview.clear()
            self.preview_name.setText("-")
            return
        vehicle_id = current.data(Qt.ItemDataRole.UserRole)
        self.preview_name.setText(current.text())
        image_path = os.path.join(self.assets_folder, "Vehicle_Previews", self.subfolder, f"{vehicle_id}.png")
        if os.path.exists(image_path):
            pixmap = QPixmap(image_path).scaled(120, 120, Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation)
            self.preview.setPixmap(pixmap)
        else:
            self.preview.clear()

    def _confirm(self):
        item = self.list.currentItem()
        if item:
            self.selected_name = item.text()
            self.selected_id = item.data(Qt.ItemDataRole.UserRole)
            self.accept()


# ── Setup Wizard ──────────────────────────────────────────────────────────────

class SetupDialog(QDialog):
    """
    First-run / directory-not-found setup wizard.

    Guides the user through locating their War Thunder install folder.
    Runs auto-detect visibly on open, then lets the user browse manually
    if auto-detect fails. Stays open until a valid directory with mission
    files is confirmed, or the user explicitly skips.
    """

    _MISSION_FILES = (
        ("UserMissions", "Ask3lad", "ask3lad_testdrive.blk"),
        ("UserMissions", "Ask3lad", "ask3lad_testdrive_naval.blk"),
    )

    def __init__(self, parent, old_dir=None):
        super().__init__(parent)
        self.setWindowTitle("Setup — War Thunder Directory")
        self.setMinimumWidth(460)
        self.setWindowFlag(Qt.WindowType.WindowCloseButtonHint, False)
        self._old_dir = old_dir

        layout = QVBoxLayout(self)
        layout.setSpacing(12)
        layout.setContentsMargins(20, 20, 20, 20)

        self._status_label = QLabel()
        self._status_label.setWordWrap(True)
        layout.addWidget(self._status_label)

        self._info_label = QLabel()
        self._info_label.setWordWrap(True)
        self._info_label.hide()
        layout.addWidget(self._info_label)

        btn_row = QHBoxLayout()
        self._btn_primary   = QPushButton()
        self._btn_secondary = QPushButton()
        self._btn_discord   = QPushButton("Open Discord")
        self._btn_discord.clicked.connect(
            lambda: webbrowser.open("https://discord.com/invite/f3nsgypbh7")
        )
        btn_row.addWidget(self._btn_primary)
        btn_row.addWidget(self._btn_secondary)
        btn_row.addWidget(self._btn_discord)
        layout.addLayout(btn_row)

        self._btn_primary.hide()
        self._btn_secondary.hide()
        self._btn_discord.hide()

        QTimer.singleShot(50, self._run_auto_detect)

    # ── Helpers ───────────────────────────────────────────────────────────────

    def _reconnect(self, btn, fn):
        try:
            btn.clicked.disconnect()
        except (RuntimeError, TypeError):
            pass
        btn.clicked.connect(fn)

    def _try_path(self, wt_path):
        mission_paths = [os.path.join(wt_path, *parts) for parts in self._MISSION_FILES]
        missing = [p for p in mission_paths if not os.path.exists(p)]
        if not missing:
            self.accept()
            self.parent().locate_test_drive_file(wt_path)
        else:
            self._set_state_missing_files(wt_path)

    def _browse(self):
        path = QFileDialog.getExistingDirectory(self, "Select War Thunder Directory")
        if path:
            self._try_path(path)

    # ── Auto-detect ───────────────────────────────────────────────────────────

    def _run_auto_detect(self):
        if self._old_dir:
            self._status_label.setText(
                f"Previously saved folder not found:\n{self._old_dir}\n\nSearching for War Thunder..."
            )
        else:
            self._status_label.setText("Searching for War Thunder...")
        self._info_label.hide()
        self._btn_primary.hide()
        self._btn_secondary.hide()
        self._btn_discord.hide()

        for path in _WT_SEARCH_PATHS:
            if os.path.exists(path):
                self._set_state_found(path)
                return
        self._set_state_not_found()

    # ── States ────────────────────────────────────────────────────────────────

    def _set_state_found(self, path):
        self._status_label.setText(f"✓ Found at:\n{path}")
        self._info_label.hide()

        self._reconnect(self._btn_primary, lambda: self._try_path(path))
        self._btn_primary.setText("Use This")
        self._btn_primary.show()

        self._reconnect(self._btn_secondary, self._browse)
        self._btn_secondary.setText("Choose Different Folder")
        self._btn_secondary.show()

        self._btn_discord.hide()

    def _set_state_not_found(self):
        self._status_label.setText("✗ Could not find War Thunder automatically.")
        self._info_label.setText(
            "Steam:  Right-click War Thunder in your library\n"
            "        → Manage → Browse local files\n\n"
            "Gaijin Launcher:  Check your chosen install path"
        )
        self._info_label.show()

        self._reconnect(self._btn_primary, self._browse)
        self._btn_primary.setText("Browse Manually")
        self._btn_primary.show()

        self._reconnect(self._btn_secondary, self.reject)
        self._btn_secondary.setText("Skip for Now")
        self._btn_secondary.show()

        self._btn_discord.hide()

    def _set_state_missing_files(self, wt_path):
        self._status_label.setText("✗ Mission files not found in that folder.")
        self._info_label.setText(
            "Make sure you've installed the Ask3lad mission files first.\n"
            "Download them from Discord, install them, then try again."
        )
        self._info_label.show()

        self._reconnect(self._btn_primary, lambda: self._try_path(wt_path))
        self._btn_primary.setText("Try Again")
        self._btn_primary.show()

        self._reconnect(self._btn_secondary, self._browse)
        self._btn_secondary.setText("Choose Different Folder")
        self._btn_secondary.show()

        self._btn_discord.show()


# ── Main Window ───────────────────────────────────────────────────────────────

class WarThunderTestDriveGUI(QMainWindow):
    """
    Main application window for the Ask3lad War Thunder Mission GUI.

    Lets players configure Ask3lad's custom ground and naval War Thunder
    missions before launching them in-game. A top-level mode switcher
    separates Ground and Naval configuration. Each mode has its own tabs,
    state attributes, file paths, and apply logic. Shared utilities handle
    image loading, .blk file editing, and config persistence.
    """

    def __init__(self):
        super().__init__()
        self.setWindowTitle("Ask3lad War Thunder Test Drive GUI 2.5")
        self.setMinimumSize(700, 900)

        self.assets_folder = os.path.join(_app_dir(), "Assets")

        if not os.path.exists(self.assets_folder):
            msg = QMessageBox()
            msg.setWindowTitle("Assets Folder Not Found")
            msg.setIcon(QMessageBox.Icon.Critical)
            msg.setText("The Assets folder could not be found.")
            msg.setInformativeText(
                "The Assets folder must be placed in the same folder as the exe.\n\n"
                "Download it from the Discord and place it next to the exe, then restart the app."
            )
            msg.addButton("Open Discord", QMessageBox.ButtonRole.AcceptRole).clicked.connect(
                lambda: webbrowser.open("https://discord.com/invite/f3nsgypbh7")
            )
            msg.addButton("Close", QMessageBox.ButtonRole.RejectRole)
            msg.exec()
            sys.exit(1)

        icon_path = os.path.join(self.assets_folder, "Ask3lad.ico")
        if os.path.exists(icon_path):
            self.setWindowIcon(QIcon(icon_path))

        # ── Ground: file paths ────────────────────────────────────────────────
        self.test_drive_file = None
        self.test_drive_vehicle_file = None

        # ── Ground: current mission state ─────────────────────────────────────
        self.Selected_Vehicle_ID = None
        self.Current_Test_Vehicle = None
        self.Current_Vehicle_ID = None
        self.Current_Test_Vehicle_Weapons = None
        self.current_bullets    = ["", "", "", ""]
        self.current_counts     = [9999, 0, 0, 0]
        self.user_ammo_loadouts = {}
        self._all_ammo_options  = []
        self._ammo_names        = {}   # ammo_id -> friendly display name
        self._ammo_limits       = {}   # caliber_prefix -> max rounds for selected vehicle
        self._belt_sizes        = {}   # caliber_prefix -> rounds per belt (belt-fed only)
        self._belt_type_limit   = None # max simultaneous belt types (None = unlimited)
        self.current_environment = None
        self.current_weather = None
        self.current_target03_id = None
        self.current_target03_rotation = 0.0
        self.current_target04_id = None
        self.current_target04_rotation = 0.0
        self.current_target05_id = None
        self.current_target05_rotation = 0.0
        self.current_target06_id = None
        self.current_ship_target_id = None
        self.current_air01_id = None
        self.current_air02_id = None
        self.current_heli_id = None
        self.target03_id = None
        self.target03_rotation = 67.0
        self.target04_id = None
        self.target04_rotation = 67.0
        self.target05_id = None
        self.target05_rotation = 71.0
        self.target06_id = None
        self.ship_target_id = None
        self.air01_id = None
        self.air02_id = None
        self.heli_id = None
        self.current_horse_powers = 12000
        self.current_max_rpm = 15000
        self.current_mass = 50000
        self.power_shift_active = True
        self.rapid_fire_active = True
        self.rapid_fire_time = 0.2
        self.weapon_override_mode = "none"
        self.weapon_override_current_donor_id = ""
        self.weapon_override_current_weapon_blk = ""
        self.weapon_override_donor_id = ""
        self.naval_weapon_override_donor_id = ""
        self.naval_weapon_override_current_donor_id = ""
        self.naval_weapon_override_current_weapon_blk = ""
        self.aircraft_weapon_override_donor_id = ""
        self.aircraft_weapon_override_current_donor_id = ""
        self.aircraft_weapon_override_current_weapon_blk = ""
        self.velocity_override_active = False
        self.current_velocity_speed = 2000
        self.caliber_override_active = False
        self.current_caliber = 0.12
        self.naval_war_mode_active = False
        self.naval_war_mode_cas_count = 8
        self.naval_war_mode_bomber_count = 27
        self.naval_rapid_fire_active = True
        self.naval_rapid_fire_time = 0.1

        # ── Ground: databases ─────────────────────────────────────────────────
        self.tank_data = []
        self.plane_data = []
        self.heli_data = []

        # ── Naval: file paths ─────────────────────────────────────────────────
        self.naval_mission_file = None
        self.naval_vehicle_file = None

        # ── Naval: current mission state ──────────────────────────────────────
        self.naval_selected_vehicle_id = None
        self.naval_current_vehicle_id = None
        self.naval_current_weapons = None
        self.naval_current_environment = None
        self.naval_current_weather = None
        self.naval_current_target01_id = None
        self.naval_current_target02_id = None
        self.naval_current_target03_id = None
        self.naval_current_target04_id = None
        self.naval_current_air01_id = None
        self.naval_current_air02_id = None
        self.naval_current_air01_weapons = None
        self.naval_current_air02_weapons = None
        self.naval_target01_id = None
        self.naval_target02_id = None
        self.naval_target03_id = None
        self.naval_target04_id = None
        self.naval_air01_id = None
        self.naval_air02_id = None
        self.naval_shooter_current_ids      = [""] * 8
        self.naval_shooter_ids              = [""] * 8
        self.naval_shooter_current_disabled = [True] * 8

        # ── Naval: databases ──────────────────────────────────────────────────
        self.ship_data = []
        self.naval_plane_data = []

        # ── DB auto-update ────────────────────────────────────────────────────
        self._local_db_version = 0
        self._db_worker  = None
        self._app_worker = None
        self._check_db_no_update  = False
        self._check_app_no_update = False
        self._air_tab_clicks = 0
        self.naval_ammo_combos = []   # list of (caliber_str, QComboBox) — per-caliber ammo selection
        self._dark_mode = False
        self._custom_map = True

        # ── Saved: recently used, favourites & user presets ───────────────────
        self.ground_recently_used  = []
        self.ground_favourites     = []
        self.naval_recently_used   = []
        self.naval_favourites      = []
        self.user_ground_presets   = []
        self.user_naval_presets    = []

        self._build_menu()
        self._build_ui()
        self.check_config()
        _apply_theme(self._dark_mode)
        self._start_db_update_check()
        self._start_app_update_check()

    # ── Menu ──────────────────────────────────────────────────────────────────

    def _build_menu(self):
        """Build the top menu bar with File, community actions, and Help."""
        menubar = self.menuBar()

        file_menu = menubar.addMenu("File")
        locate_action = QAction("Locate War Thunder Directory", self)
        locate_action.triggered.connect(self.locate_test_drive_file)
        file_menu.addAction(locate_action)
        file_menu.addSeparator()
        update_action = QAction("Check for Updates", self)
        update_action.triggered.connect(self.check_for_updates)
        file_menu.addAction(update_action)
        file_menu.addSeparator()
        debug_action = QAction("[Debug] File Info", self)
        debug_action.triggered.connect(self.show_debug_info)
        file_menu.addAction(debug_action)
        open_vehicles_action = QAction("[Debug] Open Ground Vehicle Folder", self)
        open_vehicles_action.triggered.connect(self._debug_open_ground_vehicle_folder)
        file_menu.addAction(open_vehicles_action)
        open_missions_action = QAction("[Debug] Open UserMissions Folder", self)
        open_missions_action.triggered.connect(self._debug_open_usermissions_folder)
        file_menu.addAction(open_missions_action)
        open_wo_folder_action = QAction("[Debug] Open Weapon Override Folder", self)
        open_wo_folder_action.triggered.connect(self._debug_open_weapon_override_folder)
        file_menu.addAction(open_wo_folder_action)
        datamine_action = QAction("[Debug] War Thunder Datamine GitHub", self)
        datamine_action.triggered.connect(lambda: webbrowser.open("https://github.com/gszabi99/War-Thunder-Datamine"))
        file_menu.addAction(datamine_action)
        create_log_action = QAction("[Debug] Create Log", self)
        create_log_action.triggered.connect(self._debug_create_log)
        file_menu.addAction(create_log_action)
        file_menu.addSeparator()
        exit_action = QAction("Exit", self)
        exit_action.triggered.connect(self.close)
        file_menu.addAction(exit_action)

        for label, fn in [
            ("Become a YouTube Member", self.open_support),
            ("Boost the Discord",        self.open_discord),
            ("Grab our Decals",         self.show_decals),
        ]:
            action = QAction(label, self)
            action.triggered.connect(fn)
            menubar.addAction(action)

        help_menu = menubar.addMenu("Help")
        about_action = QAction("About", self)
        about_action.triggered.connect(self.show_about)
        help_menu.addAction(about_action)
        help_menu.addSeparator()
        how_to_action = QAction("How to Use", self)
        how_to_action.triggered.connect(self.show_how_to_use)
        help_menu.addAction(how_to_action)
        changelog_action = QAction("Changelog", self)
        changelog_action.triggered.connect(self.show_changelog)
        help_menu.addAction(changelog_action)
        db_changelog_action = QAction("Database Changelog", self)
        db_changelog_action.triggered.connect(self.show_db_changelog)
        help_menu.addAction(db_changelog_action)
        credits_action = QAction("Credits", self)
        credits_action.triggered.connect(self.show_credits)
        help_menu.addAction(credits_action)
        help_menu.addSeparator()
        bug_action = QAction("Report a Bug", self)
        bug_action.triggered.connect(self.open_discord)
        help_menu.addAction(bug_action)

        self._dark_mode_action = QAction("Dark Mode: OFF", self)
        self._dark_mode_action.setCheckable(True)
        self._dark_mode_action.triggered.connect(self._toggle_dark_mode)
        menubar.addAction(self._dark_mode_action)

        self._custom_map_action = QAction("Custom Map: ON", self)
        self._custom_map_action.setCheckable(True)
        self._custom_map_action.setChecked(True)
        self._custom_map_action.triggered.connect(self._toggle_custom_map)
        menubar.addAction(self._custom_map_action)

    # ── UI Construction ───────────────────────────────────────────────────────

    def _build_ui(self):
        """
        Build the main UI skeleton with a Ground / Naval mode switcher.

        Shows a setup prompt until the WT directory is confirmed.
        The mode tabs and Apply button are hidden until a valid directory
        is located and both mission files are verified.
        """
        central = QWidget()
        self.setCentralWidget(central)
        main_layout = QVBoxLayout(central)
        main_layout.setContentsMargins(8, 8, 8, 8)
        main_layout.setSpacing(6)

        self.setup_label = QLabel("Go to File > Locate War Thunder Directory to get started.")
        self.setup_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        main_layout.addWidget(self.setup_label)

        self.mode_tabs = QTabWidget()
        self.mode_tabs.hide()
        main_layout.addWidget(self.mode_tabs)

        ground_page = QWidget()
        ground_layout = QVBoxLayout(ground_page)
        ground_layout.setContentsMargins(0, 4, 0, 0)
        self.tab_widget = QTabWidget()
        ground_layout.addWidget(self.tab_widget)
        self.mode_tabs.addTab(ground_page, "Ground Test Drive")

        naval_page = QWidget()
        naval_layout = QVBoxLayout(naval_page)
        naval_layout.setContentsMargins(0, 4, 0, 0)
        self.naval_tab_widget = QTabWidget()
        naval_layout.addWidget(self.naval_tab_widget)
        self.mode_tabs.addTab(naval_page, "Naval Test Drive")

        self.mode_tabs.addTab(QWidget(), "Air Test Drive (Coming Soon™)")
        self.mode_tabs.setTabEnabled(2, False)
        self.mode_tabs.tabBar().installEventFilter(self)

        self._build_vehicle_tab()
        self._build_mission_tab()
        self._build_air_tab()
        self._build_ground_saved_tab()
        self._build_ground_experimental_combined_tab()
        self._build_naval_ship_tab()
        self._build_naval_targets_tab()
        self._build_naval_air_tab()
        self._build_naval_shooters_tab()
        self._build_naval_saved_tab()
        self._build_naval_experimental_tab()

        self.apply_button = QPushButton("Apply Changes")
        self.apply_button.clicked.connect(self._on_apply)
        self.apply_button.hide()
        main_layout.addWidget(self.apply_button)

    # ── Ground: Tab — Vehicle ─────────────────────────────────────────────────

    def _build_vehicle_tab(self):
        """
        Build the Vehicle tab for the ground mission.

        Left panel:  role filter combo, search bar, scrollable vehicle list.
        Right panel: country filter buttons, active vehicle preview (what is
                     currently written in the mission), selected vehicle preview
                     (what the user has chosen), and ammo selection combo.
        """
        tab = QWidget()
        layout = QHBoxLayout(tab)
        layout.setContentsMargins(8, 8, 8, 8)
        layout.setSpacing(8)

        left = QVBoxLayout()
        self.role_filter_combo = QComboBox()
        self.role_filter_combo.addItems(["All", "Heavy Tank", "Light Tank", "Medium Tank", "Tank Destroyer", "SPAA", "Special"])
        self.role_filter_combo.currentTextChanged.connect(self.filter_vehicles)
        left.addWidget(self.role_filter_combo)

        self.search_entry = QLineEdit()
        self.search_entry.setPlaceholderText("Search vehicles...")
        self.search_entry.textChanged.connect(self.filter_vehicles)
        left.addWidget(self.search_entry)

        self.list_widget = QListWidget()
        self.list_widget.currentItemChanged.connect(self.select_test_vehicle)
        left.addWidget(self.list_widget)
        layout.addLayout(left, 2)

        right = QVBoxLayout()
        right.setSpacing(6)

        self.country_group = QGroupBox("Country")
        country_grid = QGridLayout(self.country_group)
        country_grid.setSpacing(4)
        self.country_button_group = QButtonGroup(self)
        self.country_button_group.setExclusive(False)
        for i, country in enumerate(["USA", "USSR", "Germany", "Great Britain", "Japan", "China", "Italy", "France", "Sweden", "Israel"]):
            btn = QPushButton(country)
            btn.setCheckable(True)
            btn.setFixedHeight(24)
            btn.clicked.connect(self.filter_vehicles)
            self.country_button_group.addButton(btn)
            country_grid.addWidget(btn, i // 2, i % 2)
        right.addWidget(self.country_group)

        current_group = QGroupBox("In Mission")
        current_layout = QVBoxLayout(current_group)
        current_layout.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.current_image_label = QLabel()
        self.current_image_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.current_image_label.setFixedSize(120, 120)
        current_layout.addWidget(self.current_image_label)
        self.current_name_label = QLabel("Unknown")
        self.current_name_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.current_name_label.setWordWrap(True)
        current_layout.addWidget(self.current_name_label)
        right.addWidget(current_group)

        selected_group = QGroupBox("Your Selection")
        selected_layout = QVBoxLayout(selected_group)
        selected_layout.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.selected_image_label = QLabel()
        self.selected_image_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.selected_image_label.setFixedSize(120, 120)
        selected_layout.addWidget(self.selected_image_label)
        self.selected_name_label = QLabel("-")
        self.selected_name_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.selected_name_label.setWordWrap(True)
        selected_layout.addWidget(self.selected_name_label)
        right.addWidget(selected_group)

        self.ammo_group = QGroupBox("Ammo Loadout")
        ammo_group = self.ammo_group
        ammo_layout = QVBoxLayout(ammo_group)
        ammo_layout.setSpacing(4)

        self.ammo_slot_combos    = []
        self.ammo_slot_spinboxes = []
        for i in range(4):
            row = QHBoxLayout()
            row.addWidget(QLabel(f"Slot {i + 1}"))
            combo = QComboBox()
            combo.setFixedWidth(155)
            combo.setEnabled(False)
            row.addWidget(combo)
            spin = QSpinBox()
            spin.setMinimum(0)
            spin.setMaximum(9999)
            spin.setValue(0)
            spin.setFixedWidth(58)
            spin.setEnabled(False)
            row.addWidget(spin)
            ammo_layout.addLayout(row)
            self.ammo_slot_combos.append(combo)
            self.ammo_slot_spinboxes.append(spin)
            combo.currentTextChanged.connect(self._sync_ammo_slots)
            spin.valueChanged.connect(self._sync_ammo_slots)

        self.ammo_counter_label = QLabel("")
        self.ammo_counter_label.setAlignment(Qt.AlignmentFlag.AlignRight)
        ammo_layout.addWidget(self.ammo_counter_label)

        save_load_row = QHBoxLayout()
        self.ammo_save_btn = QPushButton("Save")
        self.ammo_save_btn.setEnabled(False)
        self.ammo_save_btn.clicked.connect(self._save_ammo_loadout)
        save_load_row.addWidget(self.ammo_save_btn)
        self.ammo_load_combo = QComboBox()
        self.ammo_load_combo.setEnabled(False)
        self.ammo_load_combo.setFixedWidth(130)
        save_load_row.addWidget(self.ammo_load_combo)
        self.ammo_load_btn = QPushButton("Load")
        self.ammo_load_btn.setEnabled(False)
        self.ammo_load_btn.clicked.connect(self._load_ammo_loadout)
        save_load_row.addWidget(self.ammo_load_btn)
        ammo_layout.addLayout(save_load_row)
        right.addWidget(ammo_group)

        self.ammo_wo_label = QLabel("⚠ Ammo Loadout is disabled when Weapon Override is enabled. Go to the Experimental tab to disable it.")
        self.ammo_wo_label.setStyleSheet("color: red;")
        self.ammo_wo_label.setWordWrap(True)
        self.ammo_wo_label.hide()
        right.addWidget(self.ammo_wo_label)

        right.addStretch()
        layout.addLayout(right, 1)
        self.tab_widget.addTab(tab, "Vehicle")

    # ── Ground: Tab — Ground Targets ──────────────────────────────────────────

    def _build_mission_tab(self):
        """
        Build the Ground Targets tab for the ground mission.

        Contains time-of-day and weather selectors, plus three static ground
        target slots: 300 m (Target_03), 600 m (Target_04), 800 m (Target_05).
        """
        tab = QWidget()
        layout = QVBoxLayout(tab)
        layout.setContentsMargins(8, 8, 8, 8)
        layout.setSpacing(10)

        time_row = QHBoxLayout()
        time_row.addWidget(QLabel("Time of Day"))
        self.time_combo = QComboBox()
        self.time_combo.addItems(["Day", "Morning", "Evening", "Night", "Dusk", "Dawn", "Noon"])
        time_row.addWidget(self.time_combo)
        layout.addLayout(time_row)

        weather_row = QHBoxLayout()
        weather_row.addWidget(QLabel("Weather"))
        self.weather_combo = QComboBox()
        self.weather_combo.addItems(["clear", "good", "cloudy", "cloudy_windy", "thin_clouds", "hazy", "overcast", "mist", "poor", "rain", "blind", "thunder"])
        weather_row.addWidget(self.weather_combo)
        layout.addLayout(weather_row)

        for group_label, img_attr, name_attr, slot, default_rot, spawn_deg in [
            ("Ground Target (300m)", "target03_image_label", "target03_name_label", 3, 67, 67),
            ("Ground Target (600m)", "target04_image_label", "target04_name_label", 4, 67, 67),
            ("Ground Target (800m)", "target05_image_label", "target05_name_label", 5, 71, 71),
        ]:
            group = QGroupBox(group_label)
            group_layout = QHBoxLayout(group)
            img = QLabel()
            img.setAlignment(Qt.AlignmentFlag.AlignCenter)
            img.setFixedSize(120, 120)
            setattr(self, img_attr, img)
            group_layout.addWidget(img)
            info = QVBoxLayout()
            lbl = QLabel("Not set")
            setattr(self, name_attr, lbl)
            info.addWidget(lbl)
            btn = QPushButton("Change...")
            btn.clicked.connect(lambda _, n=slot: self.pick_target(n))
            info.addWidget(btn)
            group_layout.addLayout(info)

            rot_layout = QVBoxLayout()
            rot_label = QLabel(f"{default_rot}°")
            rot_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
            dial_attr = f"target0{slot}_dial"
            label_attr = f"target0{slot}_rotation_label"
            setattr(self, label_attr, rot_label)
            rot_layout.addWidget(rot_label)
            dial = QDial()
            dial.setRange(0, 359)
            dial.setWrapping(True)
            dial.setSingleStep(1)
            dial.setPageStep(45)
            dial.setValue(default_rot)
            dial.setFixedSize(80, 80)
            dial.valueChanged.connect(lambda v, la=rot_label: la.setText(f"{v}°"))
            setattr(self, dial_attr, dial)
            rot_layout.addWidget(dial, alignment=Qt.AlignmentFlag.AlignCenter)
            note = QLabel(f"{spawn_deg}° = Facing Spawn")
            note.setStyleSheet("color: gray; font-size: 9px;")
            note.setAlignment(Qt.AlignmentFlag.AlignCenter)
            rot_layout.addWidget(note)
            default_btn = QPushButton("Return to Default")
            default_btn.setFixedWidth(110)
            default_btn.clicked.connect(lambda _, d=dial, v=default_rot: d.setValue(v))
            rot_layout.addWidget(default_btn, alignment=Qt.AlignmentFlag.AlignCenter)
            group_layout.addLayout(rot_layout)

            layout.addWidget(group)

        # Moving Target (Target_06)
        t6_group = QGroupBox("Moving Target")
        t6_layout = QHBoxLayout(t6_group)
        self.target06_image_label = QLabel()
        self.target06_image_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.target06_image_label.setFixedSize(120, 120)
        t6_layout.addWidget(self.target06_image_label)
        t6_info = QVBoxLayout()
        self.target06_name_label = QLabel("Not set")
        t6_info.addWidget(self.target06_name_label)
        t6_btn = QPushButton("Change...")
        t6_btn.clicked.connect(lambda: self._pick_moving_naval_target("target06"))
        t6_info.addWidget(t6_btn)
        t6_layout.addLayout(t6_info)
        layout.addWidget(t6_group)

        layout.addStretch()
        self.tab_widget.addTab(tab, "Ground Targets")

    # ── Ground: Tab — Air Targets ─────────────────────────────────────────────

    def _build_air_tab(self):
        """
        Build the Air Targets tab for the ground mission.

        Three slots: aircraft at 5 km (Target_Air_01), aircraft at 2.5 km
        (Target_Air_02), and helicopter formation at 2 km (Heli_Target).
        """
        tab = QWidget()
        layout = QVBoxLayout(tab)
        layout.setContentsMargins(8, 8, 8, 8)
        layout.setSpacing(12)

        for label, img_attr, name_attr, key in [
            ("Aircraft Target (5km)",      "air01_image_label", "air01_name_label", "air01"),
            ("Aircraft Target (2.5km)",    "air02_image_label", "air02_name_label", "air02"),
            ("Helicopter Formation (2km)", "heli_image_label",  "heli_name_label",  "heli"),
        ]:
            group = QGroupBox(label)
            group_layout = QHBoxLayout(group)
            img = QLabel()
            img.setAlignment(Qt.AlignmentFlag.AlignCenter)
            img.setFixedSize(120, 120)
            setattr(self, img_attr, img)
            group_layout.addWidget(img)
            info = QVBoxLayout()
            lbl = QLabel("Not set")
            setattr(self, name_attr, lbl)
            info.addWidget(lbl)
            btn = QPushButton("Change...")
            btn.clicked.connect(lambda _, k=key: self.pick_air_target(k))
            info.addWidget(btn)
            group_layout.addLayout(info)
            layout.addWidget(group)

        # Naval Target (Ship_Target)
        ship_group = QGroupBox("Naval Target")
        ship_layout = QHBoxLayout(ship_group)
        self.ship_target_image_label = QLabel()
        self.ship_target_image_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.ship_target_image_label.setFixedSize(120, 120)
        ship_layout.addWidget(self.ship_target_image_label)
        ship_info = QVBoxLayout()
        self.ship_target_name_label = QLabel("Not set")
        ship_info.addWidget(self.ship_target_name_label)
        ship_btn = QPushButton("Change...")
        ship_btn.clicked.connect(lambda: self._pick_moving_naval_target("ship_target"))
        ship_info.addWidget(ship_btn)
        ship_layout.addLayout(ship_info)
        layout.addWidget(ship_group)

        layout.addStretch()
        self.tab_widget.addTab(tab, "Air && Naval Target")

    # ── Ground: Tab — Saved ───────────────────────────────────────────────────

    def _build_ground_saved_tab(self):
        """Build the Saved tab for the ground mission (Recently Used, Favourites, Presets, Random)."""
        tab = QWidget()
        layout = QVBoxLayout(tab)
        layout.setContentsMargins(8, 8, 8, 8)
        layout.setSpacing(10)

        random_row = QHBoxLayout()
        random_btn = QPushButton("Random Vehicle")
        random_btn.clicked.connect(self._random_ground_vehicle)
        random_row.addWidget(random_btn)
        random_targets_btn = QPushButton("Random Targets")
        random_targets_btn.clicked.connect(self._random_ground_targets)
        random_row.addWidget(random_targets_btn)
        random_env_btn = QPushButton("Random Weather && Time")
        random_env_btn.clicked.connect(self._random_ground_time_weather)
        random_row.addWidget(random_env_btn)
        layout.addLayout(random_row)

        lists_row = QHBoxLayout()

        # Recently Used
        ru_group = QGroupBox("Recently Used")
        ru_layout = QVBoxLayout(ru_group)
        self.ground_ru_list = QListWidget()
        ru_layout.addWidget(self.ground_ru_list)
        ru_btns = QHBoxLayout()
        ru_select = QPushButton("Select")
        ru_select.clicked.connect(self._ground_ru_select)
        ru_fav = QPushButton("★ Add to Favourites")
        ru_fav.clicked.connect(self._ground_ru_add_fav)
        ru_btns.addWidget(ru_select)
        ru_btns.addWidget(ru_fav)
        ru_layout.addLayout(ru_btns)
        lists_row.addWidget(ru_group)

        # Favourites
        fav_group = QGroupBox("Favourites")
        fav_layout = QVBoxLayout(fav_group)
        self.ground_fav_list = QListWidget()
        fav_layout.addWidget(self.ground_fav_list)
        fav_btns = QHBoxLayout()
        fav_select = QPushButton("Select")
        fav_select.clicked.connect(self._ground_fav_select)
        fav_remove = QPushButton("Remove")
        fav_remove.clicked.connect(self._ground_fav_remove)
        fav_btns.addWidget(fav_select)
        fav_btns.addWidget(fav_remove)
        fav_layout.addLayout(fav_btns)
        lists_row.addWidget(fav_group)

        layout.addLayout(lists_row)

        # Themed Presets
        presets_group = QGroupBox("Themed Presets")
        presets_layout = QVBoxLayout(presets_group)
        if _GROUND_PRESETS:
            presets_row = QHBoxLayout()
            for preset in _GROUND_PRESETS:
                btn = QPushButton(preset["name"])
                btn.clicked.connect(lambda _, p=preset: self._ground_apply_preset(p))
                presets_row.addWidget(btn)
            presets_layout.addLayout(presets_row)
        else:
            presets_layout.addWidget(QLabel("No presets configured yet."))
        layout.addWidget(presets_group)

        # User Presets
        user_presets_group = QGroupBox("User Presets")
        user_presets_layout = QVBoxLayout(user_presets_group)
        self.ground_user_presets_list = QListWidget()
        self.ground_user_presets_list.setMaximumHeight(100)
        user_presets_layout.addWidget(self.ground_user_presets_list)
        up_btns = QHBoxLayout()
        up_load = QPushButton("Load")
        up_load.clicked.connect(self._ground_load_preset)
        up_rename = QPushButton("Rename")
        up_rename.clicked.connect(self._ground_rename_preset)
        up_delete = QPushButton("Delete")
        up_delete.clicked.connect(self._ground_delete_preset)
        up_save = QPushButton("Save Current as Preset")
        up_save.clicked.connect(self._ground_save_preset)
        up_import = QPushButton("Import")
        up_import.clicked.connect(lambda: self._import_presets("ground"))
        up_export = QPushButton("Export")
        up_export.clicked.connect(lambda: self._export_presets("ground"))
        up_btns.addWidget(up_load)
        up_btns.addWidget(up_rename)
        up_btns.addWidget(up_delete)
        up_btns.addWidget(up_import)
        up_btns.addWidget(up_export)
        up_btns.addStretch()
        up_btns.addWidget(up_save)
        user_presets_layout.addLayout(up_btns)
        layout.addWidget(user_presets_group)

        layout.addStretch()
        self.tab_widget.addTab(tab, "Garage")

    # ── Ground: Tab — Experimental ───────────────────────────────────────────

    def _build_ground_experimental_combined_tab(self):
        """Build the Experimental tab containing Performance Override and Weapon Override sub-tabs."""
        tab = QWidget()
        layout = QVBoxLayout(tab)
        layout.setContentsMargins(4, 4, 4, 4)
        layout.setSpacing(0)
        sub_tw = QTabWidget()
        layout.addWidget(sub_tw)
        self._build_ground_experimental_tab(sub_tw)
        self._build_ground_weapon_override_tab(sub_tw)
        self.tab_widget.addTab(tab, "Experimental")

    def _build_ground_experimental_tab(self, tw):
        """Build the Experimental tab for the ground mission."""
        tab = QWidget()
        layout = QVBoxLayout(tab)
        layout.setContentsMargins(8, 8, 8, 8)
        layout.setSpacing(10)

        power_group = QGroupBox("Engine Override")
        self.power_shift_group = power_group
        power_layout = QVBoxLayout(power_group)

        self.power_shift_checkbox = QCheckBox("Enable Engine Override")
        power_layout.addWidget(self.power_shift_checkbox)

        info = QLabel("Overrides the engine horsepower of your vehicle.\nHigher values = faster acceleration and top speed.")
        info.setWordWrap(True)
        power_layout.addWidget(info)

        self.engine_override_controls = QWidget()
        controls_layout = QVBoxLayout(self.engine_override_controls)
        controls_layout.setContentsMargins(0, 0, 0, 0)

        slider_row = QHBoxLayout()
        slider_row.addWidget(QLabel("100"))
        self.horse_powers_slider = QSlider(Qt.Orientation.Horizontal)
        self.horse_powers_slider.setMinimum(100)
        self.horse_powers_slider.setMaximum(50000)
        self.horse_powers_slider.setValue(self.current_horse_powers)
        self.horse_powers_slider.setTickInterval(5000)
        self.horse_powers_slider.setTickPosition(QSlider.TickPosition.TicksBelow)
        slider_row.addWidget(self.horse_powers_slider)
        slider_row.addWidget(QLabel("50000"))
        controls_layout.addLayout(slider_row)

        spinbox_row = QHBoxLayout()
        spinbox_row.addWidget(QLabel("Engine Power (HP):"))
        self.horse_powers_spinbox = QSpinBox()
        self.horse_powers_spinbox.setMinimum(100)
        self.horse_powers_spinbox.setMaximum(50000)
        self.horse_powers_spinbox.setValue(self.current_horse_powers)
        self.horse_powers_spinbox.setSingleStep(100)
        spinbox_row.addWidget(self.horse_powers_spinbox)
        spinbox_row.addStretch()
        controls_layout.addLayout(spinbox_row)

        rpm_slider_row = QHBoxLayout()
        rpm_slider_row.addWidget(QLabel("1000"))
        self.max_rpm_slider = QSlider(Qt.Orientation.Horizontal)
        self.max_rpm_slider.setMinimum(1000)
        self.max_rpm_slider.setMaximum(30000)
        self.max_rpm_slider.setValue(self.current_max_rpm)
        self.max_rpm_slider.setTickInterval(5000)
        self.max_rpm_slider.setTickPosition(QSlider.TickPosition.TicksBelow)
        rpm_slider_row.addWidget(self.max_rpm_slider)
        rpm_slider_row.addWidget(QLabel("30000"))
        controls_layout.addLayout(rpm_slider_row)

        rpm_row = QHBoxLayout()
        rpm_row.addWidget(QLabel("Max RPM:"))
        self.max_rpm_spinbox = QSpinBox()
        self.max_rpm_spinbox.setMinimum(1000)
        self.max_rpm_spinbox.setMaximum(30000)
        self.max_rpm_spinbox.setValue(self.current_max_rpm)
        self.max_rpm_spinbox.setSingleStep(500)
        rpm_row.addWidget(self.max_rpm_spinbox)
        rpm_row.addStretch()
        controls_layout.addLayout(rpm_row)

        mass_slider_row = QHBoxLayout()
        mass_slider_row.addWidget(QLabel("1t"))
        self.mass_slider = QSlider(Qt.Orientation.Horizontal)
        self.mass_slider.setMinimum(1)
        self.mass_slider.setMaximum(1000)
        self.mass_slider.setValue(self.current_mass // 1000)
        self.mass_slider.setTickInterval(100)
        self.mass_slider.setTickPosition(QSlider.TickPosition.TicksBelow)
        mass_slider_row.addWidget(self.mass_slider)
        mass_slider_row.addWidget(QLabel("1000t"))
        controls_layout.addLayout(mass_slider_row)

        mass_row = QHBoxLayout()
        mass_row.addWidget(QLabel("Mass (kg):"))
        self.mass_spinbox = QSpinBox()
        self.mass_spinbox.setMinimum(1000)
        self.mass_spinbox.setMaximum(1000000)
        self.mass_spinbox.setValue(self.current_mass)
        self.mass_spinbox.setSingleStep(1000)
        mass_row.addWidget(self.mass_spinbox)
        mass_row.addStretch()
        controls_layout.addLayout(mass_row)

        reset_row = QHBoxLayout()
        reset_btn = QPushButton("Reset to Defaults")
        reset_btn.clicked.connect(self._reset_engine_override_defaults)
        reset_row.addWidget(reset_btn)
        reset_row.addStretch()
        controls_layout.addLayout(reset_row)

        power_layout.addWidget(self.engine_override_controls)

        self.horse_powers_slider.valueChanged.connect(self.horse_powers_spinbox.setValue)
        self.horse_powers_spinbox.valueChanged.connect(self.horse_powers_slider.setValue)
        self.max_rpm_slider.valueChanged.connect(self.max_rpm_spinbox.setValue)
        self.max_rpm_spinbox.valueChanged.connect(self.max_rpm_slider.setValue)
        self.mass_slider.valueChanged.connect(lambda v: self.mass_spinbox.setValue(v * 1000))
        self.mass_spinbox.valueChanged.connect(lambda v: self.mass_slider.setValue(v // 1000))
        self.power_shift_checkbox.toggled.connect(self.engine_override_controls.setEnabled)
        self.engine_override_controls.setEnabled(False)

        layout.addWidget(power_group)

        rapid_group = QGroupBox("Rapid Fire - (automatically reload and repair)")
        rapid_layout = QVBoxLayout(rapid_group)

        self.rapid_fire_checkbox = QCheckBox("Enable Rapid Fire")
        rapid_layout.addWidget(self.rapid_fire_checkbox)

        rf_info = QLabel("Automatically reloads your ammo and repairs your vehicle on a periodic timer.\nLower interval = faster reload and repair. Default: 0.20s, Max: 10s")
        rf_info.setWordWrap(True)
        rapid_layout.addWidget(rf_info)

        self.rapid_fire_controls = QWidget()
        rf_controls_layout = QVBoxLayout(self.rapid_fire_controls)
        rf_controls_layout.setContentsMargins(0, 0, 0, 0)

        dial_row = QHBoxLayout()
        dial_row.addStretch()
        self.rapid_fire_dial = QDial()
        self.rapid_fire_dial.setMinimum(1)
        self.rapid_fire_dial.setMaximum(100)
        self.rapid_fire_dial.setValue(max(1, round(self.rapid_fire_time / 0.1)))
        self.rapid_fire_dial.setNotchesVisible(True)
        self.rapid_fire_dial.setFixedSize(80, 80)
        self.rapid_fire_dial.setWrapping(False)
        dial_row.addWidget(self.rapid_fire_dial)
        dial_row.addStretch()
        rf_controls_layout.addLayout(dial_row)

        spinbox_row = QHBoxLayout()
        spinbox_row.addWidget(QLabel("Rearm interval (s):"))
        self.rapid_fire_spinbox = QDoubleSpinBox()
        self.rapid_fire_spinbox.setMinimum(0.1)
        self.rapid_fire_spinbox.setMaximum(10.0)
        self.rapid_fire_spinbox.setSingleStep(0.1)
        self.rapid_fire_spinbox.setDecimals(2)
        self.rapid_fire_spinbox.setValue(self.rapid_fire_time)
        spinbox_row.addWidget(self.rapid_fire_spinbox)
        spinbox_row.addStretch()
        rf_controls_layout.addLayout(spinbox_row)

        rapid_layout.addWidget(self.rapid_fire_controls)

        self.rapid_fire_dial.valueChanged.connect(
            lambda v: self.rapid_fire_spinbox.setValue(round(v * 0.1, 2))
        )
        self.rapid_fire_spinbox.valueChanged.connect(
            lambda v: self.rapid_fire_dial.setValue(max(1, round(v / 0.1)))
        )
        self.rapid_fire_checkbox.toggled.connect(self.rapid_fire_controls.setEnabled)
        self.rapid_fire_controls.setEnabled(self.rapid_fire_active)

        layout.addWidget(rapid_group)
        layout.addStretch()
        tw.addTab(tab, "Performance Override")

    # ── Ground: Tab — Weapon Override [Experimental] ─────────────────────────

    def _build_ground_weapon_override_tab(self, tw):
        """Build the Weapon Override [Experimental] tab for the ground mission."""
        tab = QWidget()
        layout = QVBoxLayout(tab)
        layout.setContentsMargins(8, 8, 8, 8)
        layout.setSpacing(10)

        weapon_override_group = QGroupBox("Weapon Override")
        wo_layout = QVBoxLayout(weapon_override_group)

        self.wo_none_radio     = QRadioButton("None")
        self.wo_ground_radio   = QRadioButton("Ground Weapons")
        self.wo_naval_radio    = QRadioButton("Naval Weapons")
        self.wo_aircraft_radio = QRadioButton("Aircraft Weapons")
        self.wo_none_radio.setChecked(True)
        wo_btn_group = QButtonGroup(self)
        wo_btn_group.addButton(self.wo_none_radio)
        wo_btn_group.addButton(self.wo_ground_radio)
        wo_btn_group.addButton(self.wo_naval_radio)
        wo_btn_group.addButton(self.wo_aircraft_radio)
        wo_layout.addWidget(self.wo_none_radio)
        wo_layout.addWidget(self.wo_ground_radio)
        wo_layout.addWidget(self.wo_naval_radio)
        wo_layout.addWidget(self.wo_aircraft_radio)

        wo_info = QLabel("Replaces your vehicle's primary weapon with one from a donor vehicle.\nNote: Ammo Loadout will be locked while a weapon override is active.")
        wo_info.setWordWrap(True)
        wo_layout.addWidget(wo_info)

        # Ground weapon controls
        self.wo_ground_controls = QWidget()
        wo_g_layout = QVBoxLayout(self.wo_ground_controls)
        wo_g_layout.setContentsMargins(0, 4, 0, 0)
        wo_g_donor_row = QHBoxLayout()
        self.weapon_override_name_label = QLabel("Not set")
        wo_g_donor_row.addWidget(self.weapon_override_name_label, 1)
        wo_g_btn = QPushButton("Change...")
        wo_g_btn.clicked.connect(self._pick_weapon_override_donor)
        wo_g_donor_row.addWidget(wo_g_btn)
        wo_g_layout.addLayout(wo_g_donor_row)
        wo_g_weapon_row = QHBoxLayout()
        wo_g_weapon_row.addWidget(QLabel("Weapon:"))
        self.weapon_override_combo = QComboBox()
        wo_g_weapon_row.addWidget(self.weapon_override_combo, 1)
        wo_g_layout.addLayout(wo_g_weapon_row)
        wo_layout.addWidget(self.wo_ground_controls)
        self.wo_ground_controls.setVisible(False)

        # Naval weapon controls
        self.wo_naval_controls = QWidget()
        wo_n_layout = QVBoxLayout(self.wo_naval_controls)
        wo_n_layout.setContentsMargins(0, 4, 0, 0)
        wo_n_donor_row = QHBoxLayout()
        self.naval_weapon_override_name_label = QLabel("Not set")
        wo_n_donor_row.addWidget(self.naval_weapon_override_name_label, 1)
        wo_n_btn = QPushButton("Change...")
        wo_n_btn.clicked.connect(self._pick_naval_weapon_override_donor)
        wo_n_donor_row.addWidget(wo_n_btn)
        wo_n_layout.addLayout(wo_n_donor_row)
        wo_n_weapon_row = QHBoxLayout()
        wo_n_weapon_row.addWidget(QLabel("Weapon:"))
        self.naval_weapon_override_combo = QComboBox()
        wo_n_weapon_row.addWidget(self.naval_weapon_override_combo, 1)
        wo_n_layout.addLayout(wo_n_weapon_row)
        wo_layout.addWidget(self.wo_naval_controls)
        self.wo_naval_controls.setVisible(False)

        # Aircraft weapon controls
        self.wo_aircraft_controls = QWidget()
        wo_a_layout = QVBoxLayout(self.wo_aircraft_controls)
        wo_a_layout.setContentsMargins(0, 4, 0, 0)
        wo_a_donor_row = QHBoxLayout()
        self.aircraft_weapon_override_name_label = QLabel("Not set")
        wo_a_donor_row.addWidget(self.aircraft_weapon_override_name_label, 1)
        wo_a_btn = QPushButton("Change...")
        wo_a_btn.clicked.connect(self._pick_aircraft_weapon_override_donor)
        wo_a_donor_row.addWidget(wo_a_btn)
        wo_a_layout.addLayout(wo_a_donor_row)
        wo_a_weapon_row = QHBoxLayout()
        wo_a_weapon_row.addWidget(QLabel("Weapon:"))
        self.aircraft_weapon_override_combo = QComboBox()
        wo_a_weapon_row.addWidget(self.aircraft_weapon_override_combo, 1)
        wo_a_layout.addLayout(wo_a_weapon_row)
        wo_layout.addWidget(self.wo_aircraft_controls)
        self.wo_aircraft_controls.setVisible(False)

        self.wo_none_radio.toggled.connect(lambda checked: self._on_wo_mode_changed("none", checked))
        self.wo_ground_radio.toggled.connect(lambda checked: self._on_wo_mode_changed("ground", checked))
        self.wo_naval_radio.toggled.connect(lambda checked: self._on_wo_mode_changed("naval", checked))
        self.wo_aircraft_radio.toggled.connect(lambda checked: self._on_wo_mode_changed("aircraft", checked))

        layout.addWidget(weapon_override_group)

        # ── Velocity Override ──────────────────────────────────────────────────
        velocity_group = QGroupBox("Velocity Override")
        v_layout = QVBoxLayout(velocity_group)

        self.velocity_override_checkbox = QCheckBox("Enable Velocity Override")
        self.velocity_override_checkbox.setEnabled(False)
        v_layout.addWidget(self.velocity_override_checkbox)

        vo_info = QLabel("Overrides the projectile speed of the selected weapon.\nOnly available when a weapon override is active.")
        vo_info.setWordWrap(True)
        v_layout.addWidget(vo_info)

        self.velocity_controls = QWidget()
        v_controls_layout = QVBoxLayout(self.velocity_controls)
        v_controls_layout.setContentsMargins(0, 4, 0, 0)
        v_controls_layout.setSpacing(4)

        speed_row = QHBoxLayout()
        speed_row.addWidget(QLabel("Speed (m/s):"))
        self.velocity_spinbox = QSpinBox()
        self.velocity_spinbox.setRange(100, 5000)
        self.velocity_spinbox.setValue(2000)
        self.velocity_spinbox.setSingleStep(100)
        speed_row.addWidget(self.velocity_spinbox)
        v_controls_layout.addLayout(speed_row)

        self.velocity_slider = QSlider(Qt.Orientation.Horizontal)
        self.velocity_slider.setRange(100, 5000)
        self.velocity_slider.setValue(2000)
        self.velocity_slider.setSingleStep(100)
        self.velocity_slider.setTickPosition(QSlider.TickPosition.TicksBelow)
        self.velocity_slider.setTickInterval(500)
        v_controls_layout.addWidget(self.velocity_slider)

        v_labels_row = QHBoxLayout()
        v_labels_row.addWidget(QLabel("100 m/s"))
        v_labels_row.addStretch()
        v_labels_row.addWidget(QLabel("5000 m/s"))
        v_controls_layout.addLayout(v_labels_row)

        self.velocity_controls.setEnabled(False)
        v_layout.addWidget(self.velocity_controls)

        self.velocity_slider.valueChanged.connect(self.velocity_spinbox.setValue)
        self.velocity_spinbox.valueChanged.connect(self.velocity_slider.setValue)
        self.velocity_override_checkbox.toggled.connect(
            lambda checked: self.velocity_controls.setEnabled(checked)
        )

        # Caliber override
        self.caliber_override_checkbox = QCheckBox("Caliber Override")
        self.caliber_override_checkbox.setEnabled(False)
        v_layout.addWidget(self.caliber_override_checkbox)

        self.caliber_controls_widget = QWidget()
        c_controls_layout = QHBoxLayout(self.caliber_controls_widget)
        c_controls_layout.setContentsMargins(0, 0, 0, 0)
        c_controls_layout.addWidget(QLabel("Caliber (m):"))
        self.caliber_spinbox = QDoubleSpinBox()
        self.caliber_spinbox.setRange(0.01, 10.0)
        self.caliber_spinbox.setValue(0.12)
        self.caliber_spinbox.setSingleStep(0.01)
        self.caliber_spinbox.setDecimals(2)
        c_controls_layout.addWidget(self.caliber_spinbox)
        c_controls_layout.addStretch()
        caliber_hint = QLabel("0.12 = 120 mm  |  1.0 = 1 m  |  10.0 = 10 m")
        caliber_hint.setStyleSheet("color: gray;")
        c_controls_layout.addWidget(caliber_hint)
        self.caliber_controls_widget.setEnabled(False)
        v_layout.addWidget(self.caliber_controls_widget)

        self.caliber_override_checkbox.toggled.connect(
            lambda checked: self.caliber_controls_widget.setEnabled(checked)
        )

        layout.addWidget(velocity_group)
        layout.addStretch()
        tw.addTab(tab, "Weapon Override")

    def _reset_engine_override_defaults(self):
        """Reset Engine Override spinboxes to their default values."""
        self.horse_powers_spinbox.setValue(12000)
        self.max_rpm_spinbox.setValue(15000)
        self.mass_spinbox.setValue(50000)

    def _populate_weapon_override_combo(self, combo, vehicle_id, db_filename, select_blk=""):
        """Fill a weapon combo from the given DB for vehicle_id, optionally pre-selecting select_blk."""
        combo.blockSignals(True)
        combo.clear()
        db_path = os.path.join(self.assets_folder, db_filename)
        if os.path.exists(db_path):
            try:
                with open(db_path, encoding="utf-8") as f:
                    weapon_db = json.load(f)
                for w in weapon_db.get(vehicle_id, []):
                    combo.addItem(w["name"], w["blk"])
                if select_blk:
                    for i in range(combo.count()):
                        if (combo.itemData(i) or "").lower() == select_blk.lower():
                            combo.setCurrentIndex(i)
                            break
            except Exception:
                pass
        combo.blockSignals(False)

    def _on_wo_mode_changed(self, mode, checked):
        """Show the correct controls and strip override blocks immediately when None is selected."""
        if not checked:
            return
        self.wo_ground_controls.setVisible(mode == "ground")
        self.wo_naval_controls.setVisible(mode == "naval")
        self.wo_aircraft_controls.setVisible(mode == "aircraft")
        if hasattr(self, 'ammo_group'):
            self.ammo_group.setEnabled(mode == "none")
            if hasattr(self, 'ammo_wo_label'):
                self.ammo_wo_label.setVisible(mode != "none")
            if mode != "none":
                # Reset ammo back to stock so custom ammo doesn't persist
                # into a weapon override session where slots are locked
                self.current_bullets = ["", "", "", ""]
                self.current_counts  = [9999, 0, 0, 0]
                for combo in self.ammo_slot_combos:
                    combo.blockSignals(True)
                    combo.setCurrentIndex(0)
                    combo.blockSignals(False)
                for i, spin in enumerate(self.ammo_slot_spinboxes):
                    spin.setValue(9999 if i == 0 else 0)
        if hasattr(self, 'velocity_override_checkbox'):
            if mode == "none":
                self.velocity_override_checkbox.setChecked(False)
                self.velocity_override_checkbox.setEnabled(False)
                self.velocity_controls.setEnabled(False)
                self.caliber_override_checkbox.setChecked(False)
                self.caliber_override_checkbox.setEnabled(False)
                self.caliber_controls_widget.setEnabled(False)
            else:
                self.velocity_override_checkbox.setEnabled(True)
                self.caliber_override_checkbox.setEnabled(True)
        if mode == "none" and hasattr(self, 'test_drive_vehicle_file') and self.test_drive_vehicle_file:
            if not os.path.exists(self.test_drive_vehicle_file):
                return
            try:
                with open(self.test_drive_vehicle_file, 'r', encoding='utf-8') as f:
                    vf_lines = f.readlines()
                cleaned = []
                depth = 0
                in_block = False
                for line in vf_lines:
                    if not in_block:
                        if '"@override:weapon_presets"' in line or '"@override:commonWeapons"' in line:
                            in_block = True
                            depth = line.count('{') - line.count('}')
                            if depth <= 0:
                                in_block = False
                            continue
                        cleaned.append(line)
                    else:
                        depth += line.count('{') - line.count('}')
                        if depth <= 0:
                            in_block = False
                first_comment = next(
                    (i for i, l in enumerate(cleaned) if l.lstrip().startswith('//')),
                    len(cleaned)
                )
                content = [l for l in cleaned[1:first_comment] if l.strip()]
                if content:
                    cleaned = [cleaned[0]] + ['\n'] + content + ['\n'] + cleaned[first_comment:]
                else:
                    cleaned = [cleaned[0]] + ['\n'] + cleaned[first_comment:]
                with open(self.test_drive_vehicle_file, 'w', encoding='utf-8') as f:
                    f.writelines(cleaned)
                self.weapon_override_mode                          = "none"
                self.weapon_override_current_donor_id              = ""
                self.weapon_override_current_weapon_blk            = ""
                self.naval_weapon_override_current_donor_id        = ""
                self.naval_weapon_override_current_weapon_blk      = ""
                self.aircraft_weapon_override_current_donor_id     = ""
                self.aircraft_weapon_override_current_weapon_blk   = ""
            except Exception as e:
                QMessageBox.warning(self, "Weapon Override", f"Could not update vehicle file:\n{e}")

    def _pick_weapon_override_donor(self):
        """Open vehicle picker to select the ground donor vehicle for weapon override."""
        dialog = VehiclePickerDialog(self.tank_data, self, self.assets_folder, "Tank_Previews")
        if dialog.exec():
            self.weapon_override_donor_id = dialog.selected_id
            self.weapon_override_name_label.setText(dialog.selected_name)
            self._populate_weapon_override_combo(self.weapon_override_combo, dialog.selected_id, "Weapons2.0_DB.json")

    def _pick_naval_weapon_override_donor(self):
        """Open ship picker to select the naval donor for weapon override."""
        dialog = VehiclePickerDialog(self.ship_data, self, self.assets_folder, "Ship_Previews")
        if dialog.exec():
            self.naval_weapon_override_donor_id = dialog.selected_id
            self.naval_weapon_override_name_label.setText(dialog.selected_name)
            self._populate_weapon_override_combo(self.naval_weapon_override_combo, dialog.selected_id, "NavalWeapons2.0_DB.json")

    def _pick_aircraft_weapon_override_donor(self):
        """Open aircraft picker to select the donor aircraft for weapon override."""
        self.load_air_data()
        dialog = VehiclePickerDialog(self.plane_data + self.heli_data, self, self.assets_folder, "Aircraft_Previews")
        if dialog.exec():
            self.aircraft_weapon_override_donor_id = dialog.selected_id
            self.aircraft_weapon_override_name_label.setText(dialog.selected_name)
            self._populate_weapon_override_combo(self.aircraft_weapon_override_combo, dialog.selected_id, "AircraftWeapons2.0_DB.json")

    # ── Naval: Tab — Experimental ─────────────────────────────────────────────

    def _build_naval_experimental_tab(self):
        """Build the Experimental tab for the naval mission."""
        tab = QWidget()
        layout = QVBoxLayout(tab)
        layout.setContentsMargins(8, 8, 8, 8)
        layout.setSpacing(10)

        war_mode_group = QGroupBox("War Mode")
        war_mode_layout = QVBoxLayout(war_mode_group)
        self.naval_war_mode_checkbox = QCheckBox("Enable War Mode")
        war_mode_layout.addWidget(self.naval_war_mode_checkbox)
        war_mode_desc = QLabel("All units will focus fire onto you. Bombers will bomb you and CAS will attack you as well.")
        war_mode_desc.setWordWrap(True)
        war_mode_layout.addWidget(war_mode_desc)

        self.naval_war_mode_controls = QWidget()
        wm_controls_layout = QVBoxLayout(self.naval_war_mode_controls)
        wm_controls_layout.setContentsMargins(0, 4, 0, 0)

        # CAS count
        cas_label = QLabel("CAS Count (Air_Target_01):")
        wm_controls_layout.addWidget(cas_label)
        cas_slider_row = QHBoxLayout()
        cas_slider_row.addWidget(QLabel("1"))
        self.naval_cas_count_slider = QSlider(Qt.Orientation.Horizontal)
        self.naval_cas_count_slider.setMinimum(1)
        self.naval_cas_count_slider.setMaximum(128)
        self.naval_cas_count_slider.setValue(self.naval_war_mode_cas_count)
        self.naval_cas_count_slider.setTickInterval(16)
        self.naval_cas_count_slider.setTickPosition(QSlider.TickPosition.TicksBelow)
        cas_slider_row.addWidget(self.naval_cas_count_slider)
        cas_slider_row.addWidget(QLabel("128"))
        wm_controls_layout.addLayout(cas_slider_row)
        cas_spin_row = QHBoxLayout()
        self.naval_cas_count_spinbox = QSpinBox()
        self.naval_cas_count_spinbox.setMinimum(1)
        self.naval_cas_count_spinbox.setMaximum(128)
        self.naval_cas_count_spinbox.setValue(self.naval_war_mode_cas_count)
        cas_spin_row.addWidget(self.naval_cas_count_spinbox)
        cas_spin_row.addStretch()
        wm_controls_layout.addLayout(cas_spin_row)

        # Bomber count
        bomber_label = QLabel("Bomber Count (Air_Target_02):")
        wm_controls_layout.addWidget(bomber_label)
        bomber_slider_row = QHBoxLayout()
        bomber_slider_row.addWidget(QLabel("1"))
        self.naval_bomber_count_slider = QSlider(Qt.Orientation.Horizontal)
        self.naval_bomber_count_slider.setMinimum(1)
        self.naval_bomber_count_slider.setMaximum(128)
        self.naval_bomber_count_slider.setValue(self.naval_war_mode_bomber_count)
        self.naval_bomber_count_slider.setTickInterval(16)
        self.naval_bomber_count_slider.setTickPosition(QSlider.TickPosition.TicksBelow)
        bomber_slider_row.addWidget(self.naval_bomber_count_slider)
        bomber_slider_row.addWidget(QLabel("128"))
        wm_controls_layout.addLayout(bomber_slider_row)
        bomber_spin_row = QHBoxLayout()
        self.naval_bomber_count_spinbox = QSpinBox()
        self.naval_bomber_count_spinbox.setMinimum(1)
        self.naval_bomber_count_spinbox.setMaximum(128)
        self.naval_bomber_count_spinbox.setValue(self.naval_war_mode_bomber_count)
        bomber_spin_row.addWidget(self.naval_bomber_count_spinbox)
        bomber_spin_row.addStretch()
        wm_controls_layout.addLayout(bomber_spin_row)

        self.naval_cas_count_slider.valueChanged.connect(self.naval_cas_count_spinbox.setValue)
        self.naval_cas_count_spinbox.valueChanged.connect(self.naval_cas_count_slider.setValue)
        self.naval_bomber_count_slider.valueChanged.connect(self.naval_bomber_count_spinbox.setValue)
        self.naval_bomber_count_spinbox.valueChanged.connect(self.naval_bomber_count_slider.setValue)

        war_mode_layout.addWidget(self.naval_war_mode_controls)
        self.naval_war_mode_checkbox.toggled.connect(self.naval_war_mode_controls.setEnabled)
        self.naval_war_mode_controls.setEnabled(False)

        layout.addWidget(war_mode_group)

        rapid_group = QGroupBox("Rapid Fire - (automatically reload and repair)")
        rapid_layout = QVBoxLayout(rapid_group)

        self.naval_rapid_fire_checkbox = QCheckBox("Enable Rapid Fire")
        rapid_layout.addWidget(self.naval_rapid_fire_checkbox)

        rf_info = QLabel("Automatically reloads your ammo and repairs your vehicle on a periodic timer.\nLower interval = faster reload and repair. Default: 0.10s, Max: 10s")
        rf_info.setWordWrap(True)
        rapid_layout.addWidget(rf_info)

        self.naval_rapid_fire_controls = QWidget()
        rf_controls_layout = QVBoxLayout(self.naval_rapid_fire_controls)
        rf_controls_layout.setContentsMargins(0, 0, 0, 0)

        dial_row = QHBoxLayout()
        dial_row.addStretch()
        self.naval_rapid_fire_dial = QDial()
        self.naval_rapid_fire_dial.setMinimum(1)
        self.naval_rapid_fire_dial.setMaximum(100)
        self.naval_rapid_fire_dial.setValue(max(1, round(self.naval_rapid_fire_time / 0.1)))
        self.naval_rapid_fire_dial.setNotchesVisible(True)
        self.naval_rapid_fire_dial.setFixedSize(80, 80)
        self.naval_rapid_fire_dial.setWrapping(False)
        dial_row.addWidget(self.naval_rapid_fire_dial)
        dial_row.addStretch()
        rf_controls_layout.addLayout(dial_row)

        spinbox_row = QHBoxLayout()
        spinbox_row.addWidget(QLabel("Rearm interval (s):"))
        self.naval_rapid_fire_spinbox = QDoubleSpinBox()
        self.naval_rapid_fire_spinbox.setMinimum(0.1)
        self.naval_rapid_fire_spinbox.setMaximum(10.0)
        self.naval_rapid_fire_spinbox.setSingleStep(0.1)
        self.naval_rapid_fire_spinbox.setDecimals(2)
        self.naval_rapid_fire_spinbox.setValue(self.naval_rapid_fire_time)
        spinbox_row.addWidget(self.naval_rapid_fire_spinbox)
        spinbox_row.addStretch()
        rf_controls_layout.addLayout(spinbox_row)

        rapid_layout.addWidget(self.naval_rapid_fire_controls)

        self.naval_rapid_fire_dial.valueChanged.connect(
            lambda v: self.naval_rapid_fire_spinbox.setValue(round(v * 0.1, 2))
        )
        self.naval_rapid_fire_spinbox.valueChanged.connect(
            lambda v: self.naval_rapid_fire_dial.setValue(max(1, round(v / 0.1)))
        )
        self.naval_rapid_fire_checkbox.toggled.connect(self.naval_rapid_fire_controls.setEnabled)
        self.naval_rapid_fire_controls.setEnabled(self.naval_rapid_fire_active)

        layout.addWidget(rapid_group)

        layout.addStretch()
        self.naval_tab_widget.addTab(tab, "Experimental")

    # ── Naval: Tab — Bombarding Ships ────────────────────────────────────────

    def _build_naval_shooters_tab(self):
        """
        Build the Bombarding Ships tab for the naval mission.

        Lists all 8 background ships (Ship_01–08). Each row has a checkbox
        to enable/disable the ship (empty unit_class = disabled in-game),
        a 60×60 preview image, the current ship name, and a Change button
        to pick a different ship from the database.
        """
        tab = QWidget()
        layout = QVBoxLayout(tab)
        layout.setContentsMargins(8, 8, 8, 8)
        layout.setSpacing(6)

        self.naval_shooter_checkboxes   = []
        self.naval_shooter_image_labels = []
        self.naval_shooter_name_labels  = []

        ship_labels = [
            "Ship 1", "Ship 2", "Ship 3", "Ship 4",
            "Ship 5", "Ship 6", "Carrier 1", "Carrier 2",
        ]

        for i in range(8):
            group = QGroupBox(ship_labels[i])
            row = QHBoxLayout(group)
            row.setContentsMargins(6, 4, 6, 4)
            row.setSpacing(8)

            cb = QCheckBox("Enabled")
            cb.setChecked(True)
            self.naval_shooter_checkboxes.append(cb)
            row.addWidget(cb)

            img = QLabel()
            img.setFixedSize(60, 60)
            img.setAlignment(Qt.AlignmentFlag.AlignCenter)
            self.naval_shooter_image_labels.append(img)
            row.addWidget(img)

            name_lbl = QLabel("Not set")
            name_lbl.setWordWrap(True)
            self.naval_shooter_name_labels.append(name_lbl)
            row.addWidget(name_lbl, 1)

            btn = QPushButton("Change...")
            btn.clicked.connect(lambda _, n=i: self._pick_naval_shooter(n))
            row.addWidget(btn)

            layout.addWidget(group)

        layout.addStretch()
        self.naval_tab_widget.addTab(tab, "Bombarding Ships")

    def _pick_naval_shooter(self, index):
        """Open VehiclePickerDialog to change a shooter ship slot."""
        dialog = VehiclePickerDialog(self.ship_data, self, self.assets_folder, "Ship_Previews")
        if dialog.exec():
            self.naval_shooter_ids[index] = dialog.selected_id
            self.naval_shooter_name_labels[index].setText(dialog.selected_name)
            self.load_image(dialog.selected_id, self.naval_shooter_image_labels[index], "Ship_Previews", size=60)

    # ── Naval: Tab — Ship ─────────────────────────────────────────────────────

    def _build_naval_ship_tab(self):
        """
        Build the Ship tab for the naval mission.

        Left panel:  role filter combo (19 ship classes), search bar, ship list.
        Right panel: country filter buttons, active ship preview (what is
                     currently written in the mission), selected ship preview
                     (what the user has chosen), and ammo selection combo.
        Mirrors the ground Vehicle tab but uses ship data and Ship_Previews.
        """
        tab = QWidget()
        layout = QHBoxLayout(tab)
        layout.setContentsMargins(8, 8, 8, 8)
        layout.setSpacing(8)

        left = QVBoxLayout()
        self.naval_role_filter_combo = QComboBox()
        self.naval_role_filter_combo.addItems([
            "All",
            "Battleships", "Battlecruisers", "Heavy Cruisers", "Light Cruisers",
            "Destroyers", "Frigates", "Carrier",
            "Boats", "Torpedo Boat", "Heavy Boat", "Gunboat", "Heavy Gunboat",
            "Armored Boat", "Sub-Chasers", "Minelayer", "AA Ferry", "Ferry Barge", "Barges",
        ])
        self.naval_role_filter_combo.currentTextChanged.connect(self.filter_ships)
        left.addWidget(self.naval_role_filter_combo)

        self.naval_search_entry = QLineEdit()
        self.naval_search_entry.setPlaceholderText("Search ships...")
        self.naval_search_entry.textChanged.connect(self.filter_ships)
        left.addWidget(self.naval_search_entry)

        self.naval_list_widget = QListWidget()
        self.naval_list_widget.currentItemChanged.connect(self.select_naval_vehicle)
        left.addWidget(self.naval_list_widget)
        layout.addLayout(left, 2)

        right = QVBoxLayout()
        right.setSpacing(6)

        naval_country_group = QGroupBox("Country")
        naval_country_grid = QGridLayout(naval_country_group)
        naval_country_grid.setSpacing(4)
        self.naval_country_button_group = QButtonGroup(self)
        self.naval_country_button_group.setExclusive(False)
        for i, country in enumerate(["USA", "USSR", "Germany", "Great Britain", "Japan", "China", "Italy", "France", "Sweden", "Israel"]):
            btn = QPushButton(country)
            btn.setCheckable(True)
            btn.setFixedHeight(24)
            btn.clicked.connect(self.filter_ships)
            self.naval_country_button_group.addButton(btn)
            naval_country_grid.addWidget(btn, i // 2, i % 2)
        right.addWidget(naval_country_group)

        naval_current_group = QGroupBox("In Mission")
        naval_current_layout = QVBoxLayout(naval_current_group)
        naval_current_layout.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.naval_current_image_label = QLabel()
        self.naval_current_image_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.naval_current_image_label.setFixedSize(120, 120)
        naval_current_layout.addWidget(self.naval_current_image_label)
        self.naval_current_name_label = QLabel("Unknown")
        self.naval_current_name_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.naval_current_name_label.setWordWrap(True)
        naval_current_layout.addWidget(self.naval_current_name_label)
        right.addWidget(naval_current_group)

        naval_selected_group = QGroupBox("Your Selection")
        naval_selected_layout = QVBoxLayout(naval_selected_group)
        naval_selected_layout.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.naval_selected_image_label = QLabel()
        self.naval_selected_image_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.naval_selected_image_label.setFixedSize(120, 120)
        naval_selected_layout.addWidget(self.naval_selected_image_label)
        self.naval_selected_name_label = QLabel("-")
        self.naval_selected_name_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.naval_selected_name_label.setWordWrap(True)
        naval_selected_layout.addWidget(self.naval_selected_name_label)
        right.addWidget(naval_selected_group)

        naval_ammo_group = QGroupBox("Ammo Selection")
        naval_ammo_outer = QVBoxLayout(naval_ammo_group)
        self._naval_ammo_container = QWidget()
        self._naval_ammo_container_layout = QVBoxLayout(self._naval_ammo_container)
        self._naval_ammo_container_layout.setContentsMargins(0, 0, 0, 0)
        self._naval_ammo_container_layout.setSpacing(4)
        lbl = QLabel("Select a ship to see ammo options.")
        lbl.setEnabled(False)
        self._naval_ammo_container_layout.addWidget(lbl)
        naval_ammo_outer.addWidget(self._naval_ammo_container)
        right.addWidget(naval_ammo_group)

        right.addStretch()
        layout.addLayout(right, 1)
        self.naval_tab_widget.addTab(tab, "Vessel")

    # ── Naval: Tab — Naval Targets ────────────────────────────────────────────

    def _build_naval_targets_tab(self):
        """
        Build the Naval Targets tab for the naval mission.

        Contains time-of-day and weather selectors, plus three static ship
        target slots at 5 km (Target_01), 10 km (Target_02), 15 km (Target_03).
        All targets are picked from Ships2.0_DB.json.
        """
        tab = QWidget()
        layout = QVBoxLayout(tab)
        layout.setContentsMargins(8, 8, 8, 8)
        layout.setSpacing(10)

        time_row = QHBoxLayout()
        time_row.addWidget(QLabel("Time of Day"))
        self.naval_time_combo = QComboBox()
        self.naval_time_combo.addItems(["Day", "Morning", "Evening", "Night", "Dusk", "Dawn", "Noon"])
        time_row.addWidget(self.naval_time_combo)
        layout.addLayout(time_row)

        weather_row = QHBoxLayout()
        weather_row.addWidget(QLabel("Weather"))
        self.naval_weather_combo = QComboBox()
        self.naval_weather_combo.addItems(["clear", "good", "cloudy", "cloudy_windy", "thin_clouds", "hazy", "overcast", "mist", "poor", "rain", "blind", "thunder"])
        weather_row.addWidget(self.naval_weather_combo)
        layout.addLayout(weather_row)

        for group_label, img_attr, name_attr, slot in [
            ("Naval Target (5km)",  "naval_target01_image_label", "naval_target01_name_label", 1),
            ("Naval Target (10km)", "naval_target02_image_label", "naval_target02_name_label", 2),
            ("Naval Target (15km)", "naval_target03_image_label", "naval_target03_name_label", 3),
        ]:
            group = QGroupBox(group_label)
            group_layout = QHBoxLayout(group)
            img = QLabel()
            img.setAlignment(Qt.AlignmentFlag.AlignCenter)
            img.setFixedSize(120, 120)
            setattr(self, img_attr, img)
            group_layout.addWidget(img)
            info = QVBoxLayout()
            lbl = QLabel("Not set")
            setattr(self, name_attr, lbl)
            info.addWidget(lbl)
            btn = QPushButton("Change...")
            btn.clicked.connect(lambda _, n=slot: self.pick_naval_target(n))
            info.addWidget(btn)
            group_layout.addLayout(info)
            layout.addWidget(group)

        layout.addStretch()
        self.naval_tab_widget.addTab(tab, "Naval Targets")

    # ── Naval: Tab — Air & Moving Targets ─────────────────────────────────────

    def _build_naval_air_tab(self):
        """
        Build the Moving Targets tab for the naval mission.

        Three slots:
          - Moving Ship Target (Target_04)    — a ship that patrols a waypoint path
          - Aircraft (CAS Formation)  (Air_Target_01) — CAS aircraft with weapons preset combo
          - Aircraft (Bomber Formation)(Air_Target_02) — bomber with weapons preset combo
        """
        tab = QWidget()
        layout = QVBoxLayout(tab)
        layout.setContentsMargins(8, 8, 8, 8)
        layout.setSpacing(12)

        # Moving Ship Target
        ship_group = QGroupBox("Moving Ship Target")
        ship_layout = QHBoxLayout(ship_group)
        self.naval_target04_image_label = QLabel()
        self.naval_target04_image_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.naval_target04_image_label.setFixedSize(120, 120)
        ship_layout.addWidget(self.naval_target04_image_label)
        ship_info = QVBoxLayout()
        self.naval_target04_name_label = QLabel("Not set")
        ship_info.addWidget(self.naval_target04_name_label)
        ship_btn = QPushButton("Change...")
        ship_btn.clicked.connect(lambda: self.pick_naval_air_target("target04"))
        ship_info.addWidget(ship_btn)
        ship_layout.addLayout(ship_info)
        layout.addWidget(ship_group)

        # Aircraft (CAS Formation) — with weapons preset combo
        cas_group = QGroupBox("Aircraft (CAS Formation)")
        cas_layout = QHBoxLayout(cas_group)
        self.naval_air01_image_label = QLabel()
        self.naval_air01_image_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.naval_air01_image_label.setFixedSize(120, 120)
        cas_layout.addWidget(self.naval_air01_image_label)
        cas_info = QVBoxLayout()
        self.naval_air01_name_label = QLabel("Not set")
        cas_info.addWidget(self.naval_air01_name_label)
        cas_btn = QPushButton("Change...")
        cas_btn.clicked.connect(lambda: self.pick_naval_air_target("air01"))
        cas_info.addWidget(cas_btn)
        self.naval_cas_weapons_combo = QComboBox()
        self.naval_cas_weapons_combo.setEnabled(False)
        cas_info.addWidget(self.naval_cas_weapons_combo)
        cas_layout.addLayout(cas_info)
        layout.addWidget(cas_group)

        # Aircraft (Bomber Formation) — with weapons preset combo
        bomber_group = QGroupBox("Aircraft (Bomber Formation)")
        bomber_layout = QHBoxLayout(bomber_group)
        self.naval_air02_image_label = QLabel()
        self.naval_air02_image_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.naval_air02_image_label.setFixedSize(120, 120)
        bomber_layout.addWidget(self.naval_air02_image_label)
        bomber_info = QVBoxLayout()
        self.naval_air02_name_label = QLabel("Not set")
        bomber_info.addWidget(self.naval_air02_name_label)
        bomber_btn = QPushButton("Change...")
        bomber_btn.clicked.connect(lambda: self.pick_naval_air_target("air02"))
        bomber_info.addWidget(bomber_btn)
        self.naval_bomber_weapons_combo = QComboBox()
        self.naval_bomber_weapons_combo.setEnabled(False)
        bomber_info.addWidget(self.naval_bomber_weapons_combo)
        bomber_layout.addLayout(bomber_info)
        layout.addWidget(bomber_group)

        layout.addStretch()
        self.naval_tab_widget.addTab(tab, "Moving Targets")

    # ── Naval: Tab — Saved ────────────────────────────────────────────────────

    def _build_naval_saved_tab(self):
        """Build the Saved tab for the naval mission (Recently Used, Favourites, Presets, Random)."""
        tab = QWidget()
        layout = QVBoxLayout(tab)
        layout.setContentsMargins(8, 8, 8, 8)
        layout.setSpacing(10)

        random_row = QHBoxLayout()
        random_btn = QPushButton("Random Ship")
        random_btn.clicked.connect(self._random_naval_vehicle)
        random_row.addWidget(random_btn)
        random_targets_btn = QPushButton("Random Targets")
        random_targets_btn.clicked.connect(self._random_naval_targets)
        random_row.addWidget(random_targets_btn)
        random_env_btn = QPushButton("Random Weather && Time")
        random_env_btn.clicked.connect(self._random_naval_time_weather)
        random_row.addWidget(random_env_btn)
        layout.addLayout(random_row)

        lists_row = QHBoxLayout()

        # Recently Used
        ru_group = QGroupBox("Recently Used")
        ru_layout = QVBoxLayout(ru_group)
        self.naval_ru_list = QListWidget()
        ru_layout.addWidget(self.naval_ru_list)
        ru_btns = QHBoxLayout()
        ru_select = QPushButton("Select")
        ru_select.clicked.connect(self._naval_ru_select)
        ru_fav = QPushButton("★ Add to Favourites")
        ru_fav.clicked.connect(self._naval_ru_add_fav)
        ru_btns.addWidget(ru_select)
        ru_btns.addWidget(ru_fav)
        ru_layout.addLayout(ru_btns)
        lists_row.addWidget(ru_group)

        # Favourites
        fav_group = QGroupBox("Favourites")
        fav_layout = QVBoxLayout(fav_group)
        self.naval_fav_list = QListWidget()
        fav_layout.addWidget(self.naval_fav_list)
        fav_btns = QHBoxLayout()
        fav_select = QPushButton("Select")
        fav_select.clicked.connect(self._naval_fav_select)
        fav_remove = QPushButton("Remove")
        fav_remove.clicked.connect(self._naval_fav_remove)
        fav_btns.addWidget(fav_select)
        fav_btns.addWidget(fav_remove)
        fav_layout.addLayout(fav_btns)
        lists_row.addWidget(fav_group)

        layout.addLayout(lists_row)

        # Themed Presets
        presets_group = QGroupBox("Themed Presets")
        presets_layout = QVBoxLayout(presets_group)
        if _NAVAL_PRESETS:
            presets_row = QHBoxLayout()
            for preset in _NAVAL_PRESETS:
                btn = QPushButton(preset["name"])
                btn.clicked.connect(lambda _, p=preset: self._naval_apply_preset(p))
                presets_row.addWidget(btn)
            presets_layout.addLayout(presets_row)
        else:
            presets_layout.addWidget(QLabel("No presets configured yet."))
        layout.addWidget(presets_group)

        # User Presets
        naval_user_presets_group = QGroupBox("User Presets")
        naval_user_presets_layout = QVBoxLayout(naval_user_presets_group)
        self.naval_user_presets_list = QListWidget()
        self.naval_user_presets_list.setMaximumHeight(100)
        naval_user_presets_layout.addWidget(self.naval_user_presets_list)
        nup_btns = QHBoxLayout()
        nup_load = QPushButton("Load")
        nup_load.clicked.connect(self._naval_load_preset)
        nup_rename = QPushButton("Rename")
        nup_rename.clicked.connect(self._naval_rename_preset)
        nup_delete = QPushButton("Delete")
        nup_delete.clicked.connect(self._naval_delete_preset)
        nup_save = QPushButton("Save Current as Preset")
        nup_save.clicked.connect(self._naval_save_preset)
        nup_import = QPushButton("Import")
        nup_import.clicked.connect(lambda: self._import_presets("naval"))
        nup_export = QPushButton("Export")
        nup_export.clicked.connect(lambda: self._export_presets("naval"))
        nup_btns.addWidget(nup_load)
        nup_btns.addWidget(nup_rename)
        nup_btns.addWidget(nup_delete)
        nup_btns.addWidget(nup_import)
        nup_btns.addWidget(nup_export)
        nup_btns.addStretch()
        nup_btns.addWidget(nup_save)
        naval_user_presets_layout.addLayout(nup_btns)
        layout.addWidget(naval_user_presets_group)

        layout.addStretch()
        self.naval_tab_widget.addTab(tab, "Dock")

    # ── Shared: Config ────────────────────────────────────────────────────────

    def check_config(self):
        """
        Load config.json on startup and auto-initialise if a saved WT directory exists.

        config.json sits next to this script and stores:
            { "WT_DIR": "<path to War Thunder installation>", "db_version": <int> }

        After loading, if no WT directory was successfully set up a startup prompt
        is shown once the window is visible (via QTimer.singleShot).
        """
        config_path = os.path.join(_app_dir(), "config.json")
        old_dir = None  # set if a dir was saved but no longer exists on disk

        if os.path.exists(config_path):
            try:
                with open(config_path, 'r', encoding='utf-8') as f:
                    config = json.load(f)
                if isinstance(config, dict):
                    self._local_db_version    = float(config.get("db_version", 0))
                    self._stored_app_version  = config.get("app_version", "")
                    self.ground_recently_used = [v for v in config.get("ground_recently_used", []) if v]
                    self.ground_favourites    = [v for v in config.get("ground_favourites", []) if v]
                    self.naval_recently_used  = [v for v in config.get("naval_recently_used", []) if v]
                    self.naval_favourites     = [v for v in config.get("naval_favourites", []) if v]
                    self.user_ground_presets  = config.get("user_ground_presets", [])
                    self.user_naval_presets   = config.get("user_naval_presets", [])
                    self.user_ammo_loadouts   = config.get("user_ammo_loadouts", {})
                    self._dark_mode           = bool(config.get("dark_mode", False))
                    self._dark_mode_action.setChecked(self._dark_mode)
                    self._dark_mode_action.setText("Dark Mode: ON" if self._dark_mode else "Dark Mode: OFF")
                    wt_dir = config.get("WT_DIR")
                    if wt_dir and os.path.exists(wt_dir):
                        self.locate_test_drive_file(wt_dir)
                    elif wt_dir:
                        old_dir = wt_dir  # saved but folder is gone
            except Exception:
                pass

        # If setup didn't succeed, try known install paths before prompting
        if self.test_drive_file is None:
            for path in _WT_SEARCH_PATHS:
                if os.path.exists(path):
                    self.locate_test_drive_file(path)
                    if self.test_drive_file is not None:
                        break

        # If db_version wasn't stored in config, read it from the local DB file.
        if self._local_db_version == 0:
            db_ver_path = os.path.join(self.assets_folder, "db_version.json")
            if os.path.exists(db_ver_path):
                try:
                    with open(db_ver_path, encoding="utf-8") as f:
                        self._local_db_version = float(json.load(f).get("version", 0))
                except Exception:
                    pass

        # Write all config fields so the file is always complete on startup.
        self.update_config(db_version=self._local_db_version, app_version=APP_VERSION)
        self._save_saved_lists()

        # Upgrade detection.
        stored = getattr(self, "_stored_app_version", "")
        if stored and stored != APP_VERSION:
            QTimer.singleShot(200, self._show_updated_message)

        # If still not found, show the startup prompt
        if self.test_drive_file is None:
            QTimer.singleShot(0, lambda: self._show_startup_prompt(old_dir))

    def update_config(self, wt_path=None, db_version=None, app_version=None):
        """
        Persist settings to config.json.

        Args:
            wt_path     (str | None): War Thunder directory path to save.
            db_version  (int | None): Local DB version number to save.
            app_version (str | None): App version string to save.
        """
        config_path = os.path.join(_app_dir(), "config.json")
        config = {}
        if os.path.exists(config_path):
            try:
                with open(config_path, 'r', encoding='utf-8') as f:
                    config = json.load(f)
            except Exception:
                config = {}
        if wt_path:
            config["WT_DIR"] = wt_path
        if db_version is not None:
            config["db_version"] = db_version
        if app_version is not None:
            config["app_version"] = app_version
        try:
            with open(config_path, 'w', encoding='utf-8') as f:
                json.dump(config, f, indent=4)
        except Exception as e:
            QMessageBox.critical(self, "Error", f"Could not save config: {str(e)}")

    def _save_saved_lists(self):
        """Persist recently used and favourites lists to config.json."""
        config_path = os.path.join(_app_dir(), "config.json")
        config = {}
        if os.path.exists(config_path):
            try:
                with open(config_path, 'r', encoding='utf-8') as f:
                    config = json.load(f)
            except Exception:
                config = {}
        config["ground_recently_used"] = self.ground_recently_used
        config["ground_favourites"]    = self.ground_favourites
        config["naval_recently_used"]  = self.naval_recently_used
        config["naval_favourites"]     = self.naval_favourites
        config["user_ground_presets"]  = self.user_ground_presets
        config["user_naval_presets"]   = self.user_naval_presets
        config["user_ammo_loadouts"]   = self.user_ammo_loadouts
        config["dark_mode"]            = self._dark_mode
        try:
            with open(config_path, 'w', encoding='utf-8') as f:
                json.dump(config, f, indent=4)
        except Exception:
            pass

    # ── Shared: WT Directory Setup ────────────────────────────────────────────

    def _show_startup_prompt(self, old_dir=None):
        """
        Show the setup wizard to guide the user to their WT directory.

        Called via QTimer.singleShot so the main window is visible first.
        old_dir: previously saved path that no longer exists on disk, or None.
        """
        SetupDialog(self, old_dir=old_dir).exec()

    def locate_test_drive_file(self, wt_path=None):
        """
        Resolve the WT directory and validate all four required mission files.

        On success, reads the current state of both missions, saves the path
        to config, and reveals the mode tabs and Apply button.

        Required files:
          Ground: UserMissions/Ask3lad/ask3lad_testdrive.blk
                  content/pkg_local/gameData/units/tankModels/userVehicles/us_m2a4.blk
          Naval:  UserMissions/Ask3lad/ask3lad_testdrive_naval.blk
                  content/pkg_local/gameData/units/ships/userVehicles/us_pt6.blk

        Args:
            wt_path (str | None): Pre-validated WT directory path (e.g. from config).
                                  If None, opens a directory picker dialog.
        """
        if not isinstance(wt_path, str) or not wt_path:
            wt_path = QFileDialog.getExistingDirectory(self, "Select War Thunder Directory")

        if not wt_path:
            return

        candidates = {
            "ground_mission": os.path.join(wt_path, "UserMissions", "Ask3lad", "ask3lad_testdrive.blk"),
            "ground_vehicle": os.path.join(wt_path, "content", "pkg_local", "gameData", "units", "tankModels", "userVehicles", "us_m2a4.blk"),
            "naval_mission":  os.path.join(wt_path, "UserMissions", "Ask3lad", "ask3lad_testdrive_naval.blk"),
            "naval_vehicle":  os.path.join(wt_path, "content", "pkg_local", "gameData", "units", "ships", "userVehicles", "us_pt6.blk"),
        }

        # Auto-create vehicle override files if missing, and reset mission player block to match
        _override_info = {
            "ground_vehicle": {
                "mission_key": "ground_mission",
                "unit_path":   "tankModels",
                "default_id":  "us_m2a4",
                "comment_id":  "Tank",
            },
            "naval_vehicle": {
                "mission_key": "naval_mission",
                "unit_path":   "ships",
                "default_id":  "us_pt6",
                "comment_id":  "Ship",
            },
        }
        for key, info in _override_info.items():
            path = candidates[key]
            if not os.path.exists(path):
                vid = info["default_id"]
                default_content = (
                    f'include "#/develop/gameBase/gameData/units/{info["unit_path"]}/{vid}.blk"\n'
                    f'\n'
                    f'//Change \'{vid}\' from line to any {info["comment_id"]} ID\n'
                    f'//For more information watch the video or join the Discord.\n'
                    f'//If you like these Test Drives and want to help out, feel free to become a YouTube Member\n'
                    f'//https://www.youtube.com/@Ask3lad/join\n'
                )
                try:
                    os.makedirs(os.path.dirname(path), exist_ok=True)
                    with open(path, "w", encoding="utf-8") as f:
                        f.write(default_content)
                    print(f"[Auto-created] {path}")
                except Exception as e:
                    QMessageBox.critical(self, "Error", f"Could not create {os.path.basename(path)}:\n{e}")
                    return

                # Reset the mission file's player block to match the default vehicle
                mission_path = candidates[info["mission_key"]]
                if os.path.exists(mission_path):
                    try:
                        with open(mission_path, "r", encoding="utf-8") as f:
                            mc = f.read()
                        default_weapons = f"{vid}_default"
                        if key == "ground_vehicle":
                            mc = self.update_vehicle_in_content(mc, "You", vid, default_weapons, new_bullets0="")
                        else:
                            mc = self._update_field_in_block(mc, "You_Naval", "weapons:t=", default_weapons)
                            for bullet in ("bullets0:t=", "bullets1:t=", "bullets2:t=", "bullets3:t="):
                                mc = self._update_field_in_block(mc, "You_Naval", bullet, "")
                        with open(mission_path, "w", encoding="utf-8") as f:
                            f.write(mc)
                        print(f"[Reset weapons] {os.path.basename(mission_path)} -> {default_weapons}, bullets cleared")
                    except Exception as e:
                        print(f"[Warn] Could not reset mission weapons: {e}")

        # Check mission files — these must be installed by the user
        missing = [(k, p) for k, p in candidates.items()
                   if k not in _override_info and not os.path.exists(p)]
        if missing:
            QMessageBox.critical(
                self, "Missing Files",
                "Mission files were not found in that War Thunder directory.\n\n"
                "Make sure you dragged the UserMissions folder into your War Thunder directory."
            )
            return

        # All files present — assign paths and proceed
        self._wt_dir                 = wt_path
        self.test_drive_file         = candidates["ground_mission"]
        self.test_drive_vehicle_file = candidates["ground_vehicle"]
        self.naval_mission_file      = candidates["naval_mission"]
        self.naval_vehicle_file      = candidates["naval_vehicle"]

        # Detect custom map state from the ground level blk
        _level_blk = os.path.join(wt_path, "content", "pkg_local", "levels", "Ask3lad_Testdrive.blk")
        if os.path.exists(_level_blk):
            try:
                with open(_level_blk, "r", encoding="utf-8") as _f:
                    _lc = _f.read()
                self._custom_map = r'customLevelMap:t="levels\Ask3lad_Testdrive_map.png"' in _lc
                self._custom_map_action.setChecked(self._custom_map)
                self._custom_map_action.setText("Custom Map: ON" if self._custom_map else "Custom Map: OFF")
            except Exception:
                pass

        self.find_current_test_vehicle()
        self.find_current_naval_vehicle()
        self.update_config(wt_path)
        self.setup_label.hide()
        self.show_main_ui()
        self.show_naval_ui()
        self.mode_tabs.show()
        self.apply_button.show()

    # ── Ground: UI Initialisation ─────────────────────────────────────────────

    def show_main_ui(self):
        """
        Populate the ground tabs with the current mission state.

        Loads Tank2.0_DB.json, sets the time-of-day and weather combos to
        reflect what is currently in the mission file, and populates all
        target and air target slots with their current values.
        """
        tank_db_path = os.path.join(self.assets_folder, "Tank2.0_DB.json")
        if not os.path.exists(tank_db_path):
            QMessageBox.critical(self, "Error", "Tank2.0_DB.json not found in the Assets folder.")
            return

        ammo_names_path = os.path.join(self.assets_folder, "AmmoNames2.0_DB.json")
        if os.path.exists(ammo_names_path):
            with open(ammo_names_path, encoding="utf-8") as f:
                self._ammo_names = json.load(f)

        self.load_tank_data(tank_db_path)

        current_name = next(
            (t["name"] for t in self.tank_data if t["ID"] == self.Current_Vehicle_ID),
            self.Current_Vehicle_ID or "Unknown"
        )
        self.current_name_label.setText(current_name)
        self.load_image(self.Current_Vehicle_ID, self.current_image_label)

        if self.current_environment:
            idx = self.time_combo.findText(self.current_environment, Qt.MatchFlag.MatchFixedString)
            if idx >= 0:
                self.time_combo.setCurrentIndex(idx)
        if self.current_weather:
            idx = self.weather_combo.findText(self.current_weather, Qt.MatchFlag.MatchFixedString)
            if idx >= 0:
                self.weather_combo.setCurrentIndex(idx)

        self.populate_target_combos()
        self.load_air_data()
        self.populate_air_targets()
        self._refresh_ground_saved_ui()
        self.horse_powers_spinbox.setValue(self.current_horse_powers)
        self.max_rpm_spinbox.setValue(self.current_max_rpm)
        self.mass_spinbox.setValue(self.current_mass)
        self.power_shift_checkbox.setChecked(self.power_shift_active)
        self.engine_override_controls.setEnabled(self.power_shift_active)
        self.rapid_fire_spinbox.setValue(self.rapid_fire_time)
        self.rapid_fire_dial.setValue(max(1, round(self.rapid_fire_time / 0.1)))
        self.rapid_fire_checkbox.setChecked(self.rapid_fire_active)
        self.rapid_fire_controls.setEnabled(self.rapid_fire_active)
        self.wo_none_radio.setChecked(self.weapon_override_mode == "none")
        self.wo_ground_radio.setChecked(self.weapon_override_mode == "ground")
        self.wo_naval_radio.setChecked(self.weapon_override_mode == "naval")
        self.wo_aircraft_radio.setChecked(self.weapon_override_mode == "aircraft")
        self.wo_ground_controls.setVisible(self.weapon_override_mode == "ground")
        self.wo_naval_controls.setVisible(self.weapon_override_mode == "naval")
        self.wo_aircraft_controls.setVisible(self.weapon_override_mode == "aircraft")
        self.ammo_group.setEnabled(self.weapon_override_mode == "none")
        self.ammo_wo_label.setVisible(self.weapon_override_mode != "none")
        if self.aircraft_weapon_override_current_donor_id:
            donor_name = next((p["name"] for p in self.plane_data + self.heli_data if p["ID"] == self.aircraft_weapon_override_current_donor_id), self.aircraft_weapon_override_current_donor_id)
            self.aircraft_weapon_override_name_label.setText(donor_name)
            self._populate_weapon_override_combo(self.aircraft_weapon_override_combo, self.aircraft_weapon_override_current_donor_id, "AircraftWeapons2.0_DB.json", self.aircraft_weapon_override_current_weapon_blk)
        if self.weapon_override_current_donor_id:
            donor_name = next((t["name"] for t in self.tank_data if t["ID"] == self.weapon_override_current_donor_id), self.weapon_override_current_donor_id)
            self.weapon_override_name_label.setText(donor_name)
            self._populate_weapon_override_combo(self.weapon_override_combo, self.weapon_override_current_donor_id, "Weapons2.0_DB.json", self.weapon_override_current_weapon_blk)
        if self.naval_weapon_override_current_donor_id:
            donor_name = next((s["name"] for s in self.ship_data if s["ID"] == self.naval_weapon_override_current_donor_id), self.naval_weapon_override_current_donor_id)
            self.naval_weapon_override_name_label.setText(donor_name)
            self._populate_weapon_override_combo(self.naval_weapon_override_combo, self.naval_weapon_override_current_donor_id, "NavalWeapons2.0_DB.json", self.naval_weapon_override_current_weapon_blk)

    # ── Naval: UI Initialisation ──────────────────────────────────────────────

    def show_naval_ui(self):
        """
        Populate the naval tabs with the current mission state.

        Loads Ships2.0_DB.json, sets the time-of-day and weather combos to
        reflect what is currently in the mission file, and populates all
        ship target and air/moving target slots with their current values.
        """
        ship_db_path = os.path.join(self.assets_folder, "Ships2.0_DB.json")
        if not os.path.exists(ship_db_path):
            QMessageBox.critical(self, "Error", "Ships2.0_DB.json not found in the Assets folder.")
            return

        self.load_ship_data(ship_db_path)

        # Refresh the ground-tab Naval Target name now that ship_data is loaded
        # (populate_target_combos runs before this in show_main_ui, so ship_data was empty then)
        self.ship_target_name_label.setText(
            next((s["name"] for s in self.ship_data if s["ID"] == self.ship_target_id),
                 self.ship_target_id or "Not set")
        )
        if self.ship_target_id:
            self.load_image(self.ship_target_id, self.ship_target_image_label, "Ship_Previews")

        current_name = next(
            (s["name"] for s in self.ship_data if s["ID"] == self.naval_current_vehicle_id),
            self.naval_current_vehicle_id or "Unknown"
        )
        self.naval_current_name_label.setText(current_name)
        self.load_image(self.naval_current_vehicle_id, self.naval_current_image_label, "Ship_Previews")

        if self.naval_current_environment:
            idx = self.naval_time_combo.findText(self.naval_current_environment, Qt.MatchFlag.MatchFixedString)
            if idx >= 0:
                self.naval_time_combo.setCurrentIndex(idx)
        if self.naval_current_weather:
            idx = self.naval_weather_combo.findText(self.naval_current_weather, Qt.MatchFlag.MatchFixedString)
            if idx >= 0:
                self.naval_weather_combo.setCurrentIndex(idx)

        self.populate_naval_target_combos()
        self.load_naval_plane_data()
        self.populate_naval_air_targets()
        self._refresh_naval_saved_ui()
        self.naval_war_mode_checkbox.setChecked(self.naval_war_mode_active)
        self.naval_war_mode_controls.setEnabled(self.naval_war_mode_active)
        self.naval_cas_count_spinbox.setValue(self.naval_war_mode_cas_count)
        self.naval_bomber_count_spinbox.setValue(self.naval_war_mode_bomber_count)
        self.naval_rapid_fire_spinbox.setValue(self.naval_rapid_fire_time)
        self.naval_rapid_fire_dial.setValue(max(1, round(self.naval_rapid_fire_time / 0.1)))
        self.naval_rapid_fire_checkbox.setChecked(self.naval_rapid_fire_active)
        self.naval_rapid_fire_controls.setEnabled(self.naval_rapid_fire_active)
        for i in range(8):
            uid = self.naval_shooter_current_ids[i]
            self.naval_shooter_ids[i] = uid
            self.naval_shooter_checkboxes[i].setChecked(not self.naval_shooter_current_disabled[i])
            name = next((s["name"] for s in self.ship_data if s["ID"] == uid), uid or "Not set")
            self.naval_shooter_name_labels[i].setText(name)
            self.load_image(uid or None, self.naval_shooter_image_labels[i], "Ship_Previews", size=60)

    # ── Ground: .blk Reading ──────────────────────────────────────────────────

    def find_current_test_vehicle(self):
        """
        Read the ground mission .blk and us_m2a4.blk to populate current ground state.

        The current vehicle ID is read from the include line in us_m2a4.blk.
        Environment, weather, and all six target slot unit_class values are
        read from the mission file and stored for change-detection on apply.
        """
        if not self.test_drive_file or not os.path.exists(self.test_drive_file):
            QMessageBox.critical(self, "Error", "Ground test drive file not found.")
            return

        self.current_environment = None
        self.current_weather = None
        self.current_target03_id       = None
        self.current_target03_rotation = 0.0
        self.current_target04_id       = None
        self.current_target04_rotation = 0.0
        self.current_target05_id       = None
        self.current_target05_rotation = 0.0
        self.current_target06_id       = None
        self.current_ship_target_id    = None
        self.current_air01_id          = None
        self.current_air02_id          = None
        self.current_heli_id           = None

        try:
            with open(self.test_drive_file, 'r', encoding='utf-8') as f:
                content = f.read()

            for line in content.splitlines()[:30]:
                stripped = line.strip()
                if stripped.startswith('environment:t='):
                    self.current_environment = stripped.split('"')[1]
                elif stripped.startswith('weather:t='):
                    self.current_weather = stripped.split('"')[1]

            tank_models_start = content.find("tankModels")
            if tank_models_start == -1:
                QMessageBox.critical(self, "Error", "tankModels section not found in ground mission file.")
                return

            you_start = content.find('name:t="You"', tank_models_start)
            if you_start == -1:
                QMessageBox.critical(self, "Error", "Player vehicle block not found in ground mission file.")
                return

            block_start = content.rfind("{", 0, you_start)
            block_end = content.find("}", you_start)
            if block_start == -1 or block_end == -1:
                return

            self.Current_Test_Vehicle = content[block_start:block_end + 1]

            if self.test_drive_vehicle_file and os.path.exists(self.test_drive_vehicle_file):
                with open(self.test_drive_vehicle_file, 'r', encoding='utf-8') as vf:
                    vf_lines = vf.readlines()
                first_line = vf_lines[0].strip() if vf_lines else ""
                if first_line.startswith('include "#/develop/gameBase/gameData/units/tankModels/'):
                    self.Current_Vehicle_ID = first_line.split('/')[-1].replace('.blk"', '')
                self.power_shift_active = any('horsePowers' in l for l in vf_lines)
                for line in vf_lines:
                    if 'horsePowers' in line:
                        try:
                            self.current_horse_powers = int(float(line.split(':r=')[1].rstrip('}\n').strip()))
                        except Exception:
                            pass
                    elif '@override:maxRPM' in line:
                        try:
                            self.current_max_rpm = int(float(line.split(':r=')[1].rstrip('}\n').strip()))
                        except Exception:
                            pass
                    elif '@override:Mass' in line:
                        try:
                            self.current_mass = int(float(line.split(':r=')[1].rstrip('}\n').strip()))
                        except Exception:
                            pass

                # Weapon override
                self.weapon_override_current_donor_id = ""
                self.weapon_override_current_weapon_blk = ""
                self.naval_weapon_override_current_donor_id = ""
                self.naval_weapon_override_current_weapon_blk = ""
                self.aircraft_weapon_override_current_donor_id = ""
                self.aircraft_weapon_override_current_weapon_blk = ""
                _has_override = any('"@override:weapon_presets"' in l for l in vf_lines)
                _weapon_blk = ""
                _donor_blk = ""
                for line in vf_lines:
                    if '"@override:blk"' in line and ('tankmodels' in line.lower() or 'flightmodels' in line.lower() or ('units' in line.lower() and 'ships' in line.lower())):
                        for part in line.split('"'):
                            pl = part.lower()
                            if pl.startswith('gamedata') and ('tankmodels' in pl or 'flightmodels' in pl or 'ships' in pl):
                                _donor_blk = part.split('/')[-1].replace('.blk', '')
                                break
                    elif '"@override:blk"' in line and ('models_weapons' in line.lower() or 'bombguns' in line.lower() or 'rocketguns' in line.lower()):
                        for part in line.split('"'):
                            pl = part.lower()
                            if pl.startswith('gamedata') and ('models_weapons' in pl or 'bombguns' in pl or 'rocketguns' in pl):
                                _weapon_blk = part
                                break
                if _has_override and 'navalmodels' in _weapon_blk.lower():
                    self.weapon_override_mode = "naval"
                    self.naval_weapon_override_current_donor_id   = _donor_blk
                    self.naval_weapon_override_current_weapon_blk = _weapon_blk
                    self.naval_weapon_override_donor_id = _donor_blk
                elif _has_override and ('bombguns' in _weapon_blk.lower() or 'rocketguns' in _weapon_blk.lower()):
                    self.weapon_override_mode = "aircraft"
                    self.aircraft_weapon_override_current_donor_id   = _donor_blk
                    self.aircraft_weapon_override_current_weapon_blk = _weapon_blk
                    self.aircraft_weapon_override_donor_id = _donor_blk
                elif _has_override:
                    self.weapon_override_mode = "ground"
                    self.weapon_override_current_donor_id   = _donor_blk
                    self.weapon_override_current_weapon_blk = _weapon_blk
                    self.weapon_override_donor_id = _donor_blk
                else:
                    self.weapon_override_mode = "none"

            weapons_start = self.Current_Test_Vehicle.find("weapons:t=")
            if weapons_start != -1:
                weapons_end = self.Current_Test_Vehicle.find("\n", weapons_start)
                self.Current_Test_Vehicle_Weapons = self.Current_Test_Vehicle[weapons_start:weapons_end].strip()

            self.current_bullets = []
            self.current_counts  = []
            for b_slot in ("bullets0:t=", "bullets1:t=", "bullets2:t=", "bullets3:t="):
                s = self.Current_Test_Vehicle.find(b_slot)
                if s == -1:
                    self.current_bullets.append("")
                    continue
                try:
                    e = self.Current_Test_Vehicle.find("\n", s)
                    self.current_bullets.append(self.Current_Test_Vehicle[s:e].strip().split('"')[1])
                except Exception:
                    self.current_bullets.append("")
            for c_slot in ("bulletsCount0:i=", "bulletsCount1:i=", "bulletsCount2:i=", "bulletsCount3:i="):
                s = self.Current_Test_Vehicle.find(c_slot)
                if s == -1:
                    self.current_counts.append(0)
                    continue
                try:
                    e = self.Current_Test_Vehicle.find("\n", s)
                    raw = self.Current_Test_Vehicle[s:e].split("=")[1].strip().rstrip("}")
                    self.current_counts.append(int(raw))
                except Exception:
                    self.current_counts.append(0)

            # Read Rapid Fire state from the triggers block
            rf_pos = content.find('"Experimental Rapid Fire"')
            if rf_pos != -1:
                rf_end = content.find("mission_objectives{", rf_pos)
                if rf_end == -1:
                    rf_end = len(content)
                en_pos = content.find("is_enabled:b=", rf_pos, rf_end)
                if en_pos != -1:
                    en_line_end = content.find("\n", en_pos)
                    self.rapid_fire_active = content[en_pos:en_line_end].strip().endswith("yes")
                periodic_pos = content.find("periodicEvent{", rf_pos, rf_end)
                if periodic_pos != -1:
                    t_pos = content.find("time:r=", periodic_pos, rf_end)
                    if t_pos != -1:
                        t_end = content.find("\n", t_pos)
                        try:
                            self.rapid_fire_time = float(content[t_pos:t_end].split("=")[1].strip())
                        except (ValueError, IndexError):
                            pass

            s = tank_models_start
            self.current_target03_id       = self._read_field_in_block(content, "Target_03", "unit_class:t=", s)
            self.current_target03_rotation = self._read_tm_rotation(content, "Target_03")
            self.current_target04_id       = self._read_field_in_block(content, "Target_04", "unit_class:t=", s)
            self.current_target04_rotation = self._read_tm_rotation(content, "Target_04")
            self.current_target05_id       = self._read_field_in_block(content, "Target_05", "unit_class:t=", s)
            self.current_target05_rotation = self._read_tm_rotation(content, "Target_05")
            self.current_target06_id    = self._read_field_in_block(content, "Target_06",    "unit_class:t=", s)
            self.current_ship_target_id = self._read_field_in_block(content, "Ship_Target",  "unit_class:t=")
            self.current_air01_id       = self._read_field_in_block(content, "Target_Air_01","unit_class:t=", s)
            self.current_air02_id       = self._read_field_in_block(content, "Target_Air_02","unit_class:t=", s)
            self.current_heli_id        = self._read_field_in_block(content, "Heli_Target",  "unit_class:t=", s)

        except Exception as e:
            QMessageBox.critical(self, "Error", f"Error reading ground mission file: {str(e)}")

    # ── Naval: .blk Reading ───────────────────────────────────────────────────

    def find_current_naval_vehicle(self):
        """
        Read the naval mission .blk and us_pt6.blk to populate current naval state.

        The current ship ID is read from the include line in us_pt6.blk.
        The You_Naval unit_class in the mission file always stays fixed as
        userVehicles/us_pt6 — the actual ship is determined by that include line.
        Environment, weather, all target slot unit_class values, and the
        weapons presets for Air_Target_01/02 are stored for change-detection
        on apply.
        """
        if not self.naval_mission_file or not os.path.exists(self.naval_mission_file):
            QMessageBox.critical(self, "Error", "Naval mission file not found.")
            return

        self.naval_current_environment   = None
        self.naval_current_weather       = None
        self.naval_current_vehicle_id    = None
        self.naval_current_weapons       = None
        self.naval_current_target01_id   = None
        self.naval_current_target02_id   = None
        self.naval_current_target03_id   = None
        self.naval_current_target04_id   = None
        self.naval_current_air01_id      = None
        self.naval_current_air02_id      = None
        self.naval_current_air01_weapons = None
        self.naval_current_air02_weapons = None

        try:
            with open(self.naval_mission_file, 'r', encoding='utf-8') as f:
                content = f.read()

            for line in content.splitlines()[:30]:
                stripped = line.strip()
                if stripped.startswith('environment:t='):
                    self.naval_current_environment = stripped.split('"')[1]
                elif stripped.startswith('weather:t='):
                    self.naval_current_weather = stripped.split('"')[1]

            units_start = content.find("units{")
            if units_start == -1:
                QMessageBox.critical(self, "Error", "units section not found in naval mission file.")
                return

            if self.naval_vehicle_file and os.path.exists(self.naval_vehicle_file):
                with open(self.naval_vehicle_file, 'r', encoding='utf-8') as vf:
                    first_line = vf.readline().strip()
                if first_line.startswith('include "#/develop/gameBase/gameData/units/ships/'):
                    self.naval_current_vehicle_id = first_line.split('/')[-1].replace('.blk"', '')

            you_start = content.find('name:t="You_Naval"', units_start)
            if you_start != -1:
                block_end = content.find("}", you_start)
                block = content[you_start:block_end]
                w_start = block.find("weapons:t=")
                if w_start != -1:
                    w_end = block.find("\n", w_start)
                    self.naval_current_weapons = block[w_start:w_end].strip()

            s = units_start
            self.naval_current_target01_id   = self._read_field_in_block(content, "Target_01",    "unit_class:t=", s)
            self.naval_current_target02_id   = self._read_field_in_block(content, "Target_02",    "unit_class:t=", s)
            self.naval_current_target03_id   = self._read_field_in_block(content, "Target_03",    "unit_class:t=", s)
            self.naval_current_target04_id   = self._read_field_in_block(content, "Target_04",    "unit_class:t=", s)
            self.naval_current_air01_id      = self._read_field_in_block(content, "Air_Target_01","unit_class:t=", s)
            self.naval_current_air02_id      = self._read_field_in_block(content, "Air_Target_02","unit_class:t=", s)
            self.naval_current_air01_weapons = self._read_field_in_block(content, "Air_Target_01","weapons:t=",    s)
            self.naval_current_air02_weapons = self._read_field_in_block(content, "Air_Target_02","weapons:t=",    s)

            # Read War Mode state — active when "Shoot You" is enabled
            shoot_you_pos = content.find('"Shoot You"')
            if shoot_you_pos != -1:
                en_pos = content.find("is_enabled:b=", shoot_you_pos)
                if en_pos != -1:
                    en_end = content.find("\n", en_pos)
                    self.naval_war_mode_active = content[en_pos:en_end].strip().endswith("yes")

            # Read Air_Target_01 and Air_Target_02 counts
            for arm_name, attr in (("Air_Target_01", "naval_war_mode_cas_count"),
                                   ("Air_Target_02", "naval_war_mode_bomber_count")):
                arm_pos = content.find(f'name:t="{arm_name}"')
                if arm_pos != -1:
                    props_pos = content.find("props{", arm_pos)
                    if props_pos != -1:
                        props_end = content.find("}", props_pos)
                        count_pos = content.find("count:i=", props_pos, props_end)
                        if count_pos != -1:
                            count_end = content.find("\n", count_pos)
                            try:
                                setattr(self, attr, int(content[count_pos:count_end].split("=")[1].strip()))
                            except (ValueError, IndexError):
                                pass

            # Read shooter ship unit_class and disabled state (Ship_01 through Ship_08)
            disable_pos = content.find('"Disable Ship"')
            sleep_targets = set()
            if disable_pos != -1:
                put_sleep_pos = content.find("unitPutToSleep{", disable_pos)
                if put_sleep_pos != -1:
                    put_sleep_end = content.find("}", put_sleep_pos)
                    for line in content[put_sleep_pos:put_sleep_end].splitlines():
                        stripped = line.strip()
                        if stripped.startswith('target:t="'):
                            sleep_targets.add(stripped.split('"')[1])
            for i in range(8):
                ship_name = f"Ship_0{i + 1}"
                uid = self._read_field_in_block(content, ship_name, "unit_class:t=") or ""
                self.naval_shooter_current_ids[i]      = uid
                self.naval_shooter_current_disabled[i] = ship_name in sleep_targets

            # Read Rapid Fire state
            rf_pos = content.find('"Experimental Rapid Fire"')
            if rf_pos != -1:
                rf_end = content.find("mission_objectives{", rf_pos)
                if rf_end == -1:
                    rf_end = len(content)
                en_pos = content.find("is_enabled:b=", rf_pos, rf_end)
                if en_pos != -1:
                    en_end = content.find("\n", en_pos)
                    self.naval_rapid_fire_active = content[en_pos:en_end].strip().endswith("yes")
                periodic_pos = content.find("periodicEvent{", rf_pos, rf_end)
                if periodic_pos != -1:
                    t_pos = content.find("time:r=", periodic_pos, rf_end)
                    if t_pos != -1:
                        t_end = content.find("\n", t_pos)
                        try:
                            self.naval_rapid_fire_time = float(content[t_pos:t_end].split("=")[1].strip())
                        except (ValueError, IndexError):
                            pass

        except Exception as e:
            QMessageBox.critical(self, "Error", f"Error reading naval mission file: {str(e)}")

    # ── Shared: .blk Helpers ──────────────────────────────────────────────────

    def _read_field_in_block(self, content, block_name, field_key, search_start=0):
        """
        Extract a field value from a named block in .blk file content.

        Args:
            content      (str): Full text of the .blk file.
            block_name   (str): The name:t= value to search for.
            field_key    (str): Field prefix, e.g. 'unit_class:t=' or 'weapons:t='.
            search_start (int): Character offset to begin searching from.

        Returns:
            str | None: The quoted value after field_key, or None if not found.
        """
        name_pos = content.find(f'name:t="{block_name}"', search_start)
        if name_pos == -1:
            return None
        block_end = content.find("}", name_pos)
        if block_end == -1:
            return None
        block = content[name_pos:block_end]
        f_start = block.find(field_key)
        if f_start == -1:
            return None
        f_end = block.find("\n", f_start)
        try:
            return block[f_start:f_end].strip().split('"')[1]
        except IndexError:
            return None

    def _update_field_in_block(self, content, block_name, field_key, new_value):
        """
        Replace a field value in a named block within .blk file content.

        Args:
            content    (str): Full .blk file text.
            block_name (str): The name:t= value of the block to update.
            field_key  (str): Field prefix, e.g. 'unit_class:t=' or 'weapons:t='.
            new_value  (str): New value (wrapped in double quotes by this method).

        Returns:
            str: Updated file content.
        """
        name_pos = content.find(f'name:t="{block_name}"')
        if name_pos == -1:
            return content
        block_end = content.find("}", name_pos)
        if block_end == -1:
            return content
        block = content[name_pos:block_end]
        f_start = block.find(field_key)
        if f_start == -1:
            return content
        f_end = block.find("\n", f_start)
        new_block = block.replace(block[f_start:f_end], f'{field_key}"{new_value}"')
        return content[:name_pos] + new_block + content[block_end:]

    def _read_tm_rotation(self, content, block_name):
        """Read the Y-axis rotation angle (degrees) from the tm:m line of a named block."""
        name_pos = content.find(f'name:t="{block_name}"')
        if name_pos == -1:
            return 0.0
        block_end = content.find('}', name_pos)
        block = content[name_pos:block_end]
        tm_start = block.find('tm:m=')
        if tm_start == -1:
            return 0.0
        tm_end = block.find('\n', tm_start)
        tm_line = block[tm_start:tm_end]
        nums = [float(x) for x in re.findall(r'-?\d+\.?\d*(?:[eE][+-]?\d+)?', tm_line)]
        if len(nums) < 9:
            return 0.0
        # r00 = nums[0] = cos θ,  r20 = nums[6] = sin θ
        angle = math.degrees(math.atan2(nums[6], nums[0]))
        return angle % 360

    def _update_tm_rotation(self, content, block_name, angle_degrees):
        """Rewrite the tm:m line of a named block with a new Y-axis rotation, keeping position."""
        name_pos = content.find(f'name:t="{block_name}"')
        if name_pos == -1:
            return content
        block_end = content.find('}', name_pos)
        block = content[name_pos:block_end]
        tm_start = block.find('tm:m=')
        if tm_start == -1:
            return content
        tm_end = block.find('\n', tm_start)
        tm_line = block[tm_start:tm_end]
        nums = [float(x) for x in re.findall(r'-?\d+\.?\d*(?:[eE][+-]?\d+)?', tm_line)]
        if len(nums) < 12:
            return content
        px, py, pz = nums[9], nums[10], nums[11]
        a = math.radians(angle_degrees)
        c, s = math.cos(a), math.sin(a)
        new_line = (f'tm:m=[[{c:.6f}, 0, {-s:.6f}] [0, 1, 0] [{s:.6f}, 0, {c:.6f}]'
                    f' [{px}, {py}, {pz}]]')
        abs_start = name_pos + tm_start
        abs_end   = name_pos + tm_end
        return content[:abs_start] + new_line + content[abs_end:]

    # ── Ground: Data Loading ──────────────────────────────────────────────────

    def load_tank_data(self, tank_db_path):
        """Load Tank2.0_DB.json and populate the ground vehicle list widget."""
        try:
            with open(tank_db_path, 'r', encoding='utf-8') as f:
                self.tank_data = json.load(f)
            self.list_widget.clear()
            for tank in self.tank_data:
                if "name" in tank:
                    self.list_widget.addItem(QListWidgetItem(tank["name"]))
        except json.JSONDecodeError:
            QMessageBox.critical(self, "Error", "Failed to parse Tank2.0_DB.json.")
        except Exception as e:
            QMessageBox.critical(self, "Error", f"Error loading tank data: {str(e)}")

    def populate_target_combos(self):
        """Initialise the ground target labels and images from current mission state."""
        self.target03_id       = self.current_target03_id
        self.target03_rotation = self.current_target03_rotation
        self.target04_id       = self.current_target04_id
        self.target04_rotation = self.current_target04_rotation
        self.target05_id       = self.current_target05_id
        self.target05_rotation = self.current_target05_rotation
        self.target06_id       = self.current_target06_id
        self.ship_target_id    = self.current_ship_target_id
        for slot, attr in [(3, "03"), (4, "04"), (5, "05")]:
            rot = getattr(self, f"target{attr}_rotation")
            dial = getattr(self, f"target0{slot}_dial")
            label = getattr(self, f"target0{slot}_rotation_label")
            dial.blockSignals(True)
            dial.setValue(int(round(rot)))
            dial.blockSignals(False)
            label.setText(f"{int(round(rot))}°")

        self.target03_name_label.setText(next((t["name"] for t in self.tank_data if t["ID"] == self.target03_id), self.target03_id or "Not set"))
        self.target04_name_label.setText(next((t["name"] for t in self.tank_data if t["ID"] == self.target04_id), self.target04_id or "Not set"))
        self.target05_name_label.setText(next((t["name"] for t in self.tank_data if t["ID"] == self.target05_id), self.target05_id or "Not set"))
        self.target06_name_label.setText(next((t["name"] for t in self.tank_data if t["ID"] == self.target06_id), self.target06_id or "Not set"))
        self.ship_target_name_label.setText(next((s["name"] for s in self.ship_data if s["ID"] == self.ship_target_id), self.ship_target_id or "Not set"))

        self.load_image(self.target03_id, self.target03_image_label)
        self.load_image(self.target04_id, self.target04_image_label)
        self.load_image(self.target05_id, self.target05_image_label)
        self.load_image(self.target06_id, self.target06_image_label)
        self.load_image(self.ship_target_id, self.ship_target_image_label, "Ship_Previews")

    def pick_target(self, target_num):
        """
        Open VehiclePickerDialog for a ground target slot and apply the selection.

        Args:
            target_num (int): 3 (300 m), 4 (600 m), or 5 (800 m).
        """
        dialog = VehiclePickerDialog(self.tank_data, self, self.assets_folder, "Tank_Previews")
        if dialog.exec():
            slot_map = {
                3: ("target03_id", "target03_name_label", "target03_image_label"),
                4: ("target04_id", "target04_name_label", "target04_image_label"),
                5: ("target05_id", "target05_name_label", "target05_image_label"),
            }
            if target_num in slot_map:
                id_attr, name_attr, img_attr = slot_map[target_num]
                setattr(self, id_attr, dialog.selected_id)
                getattr(self, name_attr).setText(dialog.selected_name)
                self.load_image(dialog.selected_id, getattr(self, img_attr))

    def _pick_moving_naval_target(self, key):
        """Open picker for Moving Target (tank_data) or Naval Target (ship_data)."""
        if key == "target06":
            dialog = VehiclePickerDialog(self.tank_data, self, self.assets_folder, "Tank_Previews")
            if dialog.exec():
                self.target06_id = dialog.selected_id
                self.target06_name_label.setText(dialog.selected_name)
                self.load_image(dialog.selected_id, self.target06_image_label)
        elif key == "ship_target":
            dialog = VehiclePickerDialog(self.ship_data, self, self.assets_folder, "Ship_Previews")
            if dialog.exec():
                self.ship_target_id = dialog.selected_id
                self.ship_target_name_label.setText(dialog.selected_name)
                self.load_image(dialog.selected_id, self.ship_target_image_label, "Ship_Previews")

    def load_air_data(self):
        """Load Plane2.0_DB.json and Helicopter2.0_DB.json for the ground air tab."""
        for attr, filename in [("plane_data", "Plane2.0_DB.json"), ("heli_data", "Helicopter2.0_DB.json")]:
            path = os.path.join(self.assets_folder, filename)
            if not os.path.exists(path):
                QMessageBox.critical(self, "Error", f"{filename} not found in the Assets folder.")
                setattr(self, attr, [])
                continue
            try:
                with open(path, 'r', encoding='utf-8') as f:
                    setattr(self, attr, json.load(f))
            except json.JSONDecodeError:
                QMessageBox.critical(self, "Error", f"Failed to parse {filename}.")
                setattr(self, attr, [])
            except Exception as e:
                QMessageBox.critical(self, "Error", f"Error loading {filename}: {str(e)}")
                setattr(self, attr, [])

    def populate_air_targets(self):
        """Initialise the three ground air target labels and images from current mission state."""
        self.air01_id = self.current_air01_id
        self.air02_id = self.current_air02_id
        self.heli_id  = self.current_heli_id

        self.air01_name_label.setText(next((t["name"] for t in self.plane_data if t["ID"] == self.air01_id), self.air01_id or "Not set"))
        self.air02_name_label.setText(next((t["name"] for t in self.plane_data if t["ID"] == self.air02_id), self.air02_id or "Not set"))
        self.heli_name_label.setText( next((t["name"] for t in self.heli_data  if t["ID"] == self.heli_id),  self.heli_id  or "Not set"))

        self.load_image(self.air01_id, self.air01_image_label, "Aircraft_Previews")
        self.load_image(self.air02_id, self.air02_image_label, "Aircraft_Previews")
        self.load_image(self.heli_id,  self.heli_image_label,  "Aircraft_Previews")

    def pick_air_target(self, key):
        """
        Open VehiclePickerDialog for a ground air/heli slot and apply the selection.

        Args:
            key (str): 'air01', 'air02' (plane_data), or 'heli' (heli_data).
        """
        data = self.plane_data if key in ("air01", "air02") else self.heli_data
        dialog = VehiclePickerDialog(data, self, self.assets_folder, "Aircraft_Previews")
        if dialog.exec():
            slot_map = {
                "air01": ("air01_id", "air01_name_label", "air01_image_label"),
                "air02": ("air02_id", "air02_name_label", "air02_image_label"),
                "heli":  ("heli_id",  "heli_name_label",  "heli_image_label"),
            }
            if key in slot_map:
                id_attr, name_attr, img_attr = slot_map[key]
                setattr(self, id_attr, dialog.selected_id)
                getattr(self, name_attr).setText(dialog.selected_name)
                self.load_image(dialog.selected_id, getattr(self, img_attr), "Aircraft_Previews")

    # ── Ground: Vehicle List Interaction ──────────────────────────────────────

    def filter_vehicles(self):
        """Re-populate the ground vehicle list applying role, search, and country filters."""
        search_term = self.search_entry.text().lower()
        role_filter = self.role_filter_combo.currentText()
        selected_countries = {btn.text() for btn in self.country_button_group.buttons() if btn.isChecked()}
        _short = {"USA": "US", "USSR": "USSR", "Germany": "GER", "Great Britain": "UK",
                  "Japan": "JPN", "China": "CHN", "Italy": "ITA", "France": "FRA",
                  "Sweden": "SWE", "Israel": "ISR"}
        if selected_countries:
            short_names = ", ".join(_short.get(c, c) for c in sorted(selected_countries))
            self.country_group.setTitle(f"Only Showing: {short_names}")
        else:
            self.country_group.setTitle("Country")
        self.list_widget.clear()
        for tank in self.tank_data:
            if "name" not in tank:
                continue
            if search_term and search_term not in tank["name"].lower():
                continue
            if role_filter != "All" and tank.get("role") != role_filter:
                continue
            if selected_countries and tank.get("country") not in selected_countries:
                continue
            self.list_widget.addItem(QListWidgetItem(tank["name"]))

    def select_test_vehicle(self, current, previous):
        """Handle ground vehicle list selection — update display, image, and ammo combo."""
        if not current:
            return
        for tank in self.tank_data:
            if tank["name"] == current.text():
                self.Selected_Vehicle_ID = tank["ID"]
                self.selected_name_label.setText(current.text())
                self.load_image(self.Selected_Vehicle_ID, self.selected_image_label)
                self.populate_ammo_combo(tank)
                break

    def _ammo_label(self, ammo_id):
        """Return the friendly display name for an ammo ID, falling back to the raw ID."""
        return self._ammo_names.get(ammo_id, ammo_id)

    def populate_ammo_combo(self, tank):
        """Populate the 4-slot ammo loadout UI for the given vehicle entry."""
        # Build full option list: ammo[] union with any extra IDs from DB loadout bullets
        base_ammo = tank.get("ammo", [])
        all_ammo  = list(base_ammo)
        for lo in tank.get("ammo_loadouts", []):
            for b in lo.get("bullets", []):
                if b and b not in all_ammo:
                    all_ammo.append(b)

        self._all_ammo_options = all_ammo
        self._ammo_limits      = tank.get("ammo_limits", {})
        self._belt_sizes       = tank.get("belt_size", {})
        self._belt_type_limit  = tank.get("belt_type_limit", None)
        has_ammo = bool(all_ammo)

        for i, (combo, spin) in enumerate(zip(self.ammo_slot_combos, self.ammo_slot_spinboxes)):
            combo.blockSignals(True)
            combo.clear()
            if not has_ammo:
                combo.addItem("No ammo data")
                combo.setEnabled(False)
                spin.setValue(0)
                spin.setEnabled(False)
            else:
                combo.addItem("-- None --")
                for ammo in all_ammo:
                    combo.addItem(self._ammo_label(ammo), ammo)
                combo.setEnabled(True)
                b = self.current_bullets[i] if i < len(self.current_bullets) else ""
                if b:
                    idx = combo.findData(b)
                    combo.setCurrentIndex(idx if idx >= 0 else 0)
                else:
                    combo.setCurrentIndex(0)
                is_none = combo.currentText() == "-- None --"
                spin.setEnabled(not is_none)
                spin.setValue(0 if is_none else (self.current_counts[i] if i < len(self.current_counts) else 0))
            combo.blockSignals(False)

        self.ammo_save_btn.setEnabled(has_ammo)
        if has_ammo:
            self._sync_ammo_slots()
        self._refresh_ammo_load_combo(tank)

    def _sync_ammo_slots(self, *_):
        """
        Keep slot combos mutually exclusive and enforce ammo_limits pool caps.

        For each slot:
          - Rebuilds combo options (each ammo type in at most one slot).
          - Determines the caliber pool for the selected ammo type via
            _ammo_pool_key(), looks up its limit in self._ammo_limits, sums
            the counts already assigned to other slots in the same pool, and
            sets this slot's spinbox max = limit - other_pool_usage.
          - Defaults to the full remaining pool (instead of 9999) when a slot
            is first activated.
        Vehicles with no ammo_limits fall back to uncapped (9999) behaviour.
        """
        if not self._all_ammo_options:
            return

        # Snapshot selections and counts before any changes
        selections = []
        for combo in self.ammo_slot_combos:
            t = combo.currentData() or combo.currentText()
            selections.append("" if t in ("-- None --", "No ammo data", "", "Stock") else t)
        counts = [spin.value() for spin in self.ammo_slot_spinboxes]

        primary_pool = next(iter(self._belt_sizes)) if self._belt_sizes else (next(iter(self._ammo_limits)) if self._ammo_limits else None)
        stock_mixed  = (self.ammo_slot_combos[0].currentText() == "Stock" and any(selections[1:]))

        for i, (combo, spin) in enumerate(zip(self.ammo_slot_combos, self.ammo_slot_spinboxes)):
            current        = selections[i]
            used_by_others = {s for j, s in enumerate(selections) if j != i and s}
            available      = [a for a in self._all_ammo_options if a not in used_by_others]

            # Belt type limit: when limit reached on non-slot-0, restrict to non-belt ammo only
            belt_limit_reached = False
            if self._belt_type_limit is not None and i != 0:
                others_belt_active = sum(
                    1 for j, s in enumerate(selections)
                    if j != i and s and _ammo_pool_key(s, self._ammo_limits) in self._belt_sizes
                )
                if stock_mixed:
                    others_belt_active += 1  # Stock counts as 1 active belt type
                belt_limit_reached = others_belt_active >= self._belt_type_limit

            if belt_limit_reached:
                # Filter available to non-belt ammo only (missiles still allowed)
                available = [a for a in available
                             if _ammo_pool_key(a, self._ammo_limits) not in self._belt_sizes]

            combo.blockSignals(True)
            combo.clear()
            combo.addItem("Stock" if i == 0 else "-- None --")
            for ammo in available:
                combo.addItem(self._ammo_label(ammo), ammo)

            if current and current in available:
                idx = combo.findData(current)
                combo.setCurrentIndex(idx if idx >= 0 else 0)
            else:
                combo.setCurrentIndex(0)
                if current:
                    spin.blockSignals(True)
                    spin.setValue(0)
                    spin.blockSignals(False)

            if belt_limit_reached and not available and not selections[i]:
                # Belt limit reached and no non-belt ammo available — lock slot
                combo.setEnabled(False)
                spin.blockSignals(True)
                spin.setValue(0)
                spin.setEnabled(False)
                spin.blockSignals(False)
                combo.blockSignals(False)
                continue
            else:
                combo.setEnabled(True)

            is_stock    = (i == 0 and combo.currentText() == "Stock")
            other_have  = any(s for j, s in enumerate(selections) if j != i and s)
            stock_alone = is_stock and not other_have
            is_none     = combo.currentText() == "-- None --" or stock_alone

            spin.setEnabled(not is_none)

            if is_none:
                spin.blockSignals(True)
                spin.setValue(9999 if i == 0 else 0)
                spin.setMaximum(9999)
                spin.blockSignals(False)
            else:
                if is_stock:
                    # Stock mixed with other ammo: use primary belt pool
                    pool_key = primary_pool
                else:
                    sel_ammo = combo.currentData() or combo.currentText()
                    pool_key = _ammo_pool_key(sel_ammo, self._ammo_limits)

                if pool_key is not None:
                    limit = self._ammo_limits[pool_key]
                    belt_sz = self._belt_sizes.get(pool_key)
                    if belt_sz:
                        limit = -(-limit // belt_sz)  # ceiling division: rounds → belts
                    other_usage = sum(
                        counts[j] for j, s in enumerate(selections)
                        if j != i and s and _ammo_pool_key(s, self._ammo_limits) == pool_key
                    )
                    # Include Stock slot when mixed and sharing the primary pool
                    if i != 0 and stock_mixed and pool_key == primary_pool:
                        other_usage += counts[0]
                    remaining = max(0, limit - other_usage)
                else:
                    remaining = 9999

                spin.blockSignals(True)
                spin.setMaximum(remaining)
                if spin.value() > remaining:
                    spin.setValue(remaining)
                elif spin.value() == 0:
                    spin.setValue(remaining)
                counts[i] = spin.value()  # keep snapshot in sync for later slots
                spin.blockSignals(False)

            combo.blockSignals(False)

        # If every slot is empty, set count0 to 9999 (no-ammo fallback)
        if not any(selections):
            self.ammo_slot_spinboxes[0].blockSignals(True)
            self.ammo_slot_spinboxes[0].setValue(9999)
            self.ammo_slot_spinboxes[0].blockSignals(False)

        self._update_ammo_counter()

    def _update_ammo_counter(self):
        """
        Refresh the ammo counter label below the 4 slots.
        Shows used / max for each caliber pool in self._ammo_limits.
          Simple vehicle:  "125mm: 35 / 40"
          Complex vehicle: "100mm: 20 / 38  |  30mm: 250 / 500"
        Hidden when no ammo_limits are defined for the vehicle.
        """
        if not self._ammo_limits:
            self.ammo_counter_label.setText("")
            return

        # Sum counts per canonical pool key
        primary_pool = next(iter(self._belt_sizes)) if self._belt_sizes else (next(iter(self._ammo_limits)) if self._ammo_limits else None)
        pool_used = {k: 0 for k in self._ammo_limits}
        for combo, spin in zip(self.ammo_slot_combos, self.ammo_slot_spinboxes):
            t = combo.currentData() or combo.currentText()
            if t in ("-- None --", "No ammo data", ""):
                continue
            if t == "Stock" and spin.isEnabled():
                # Stock mixed — counts against primary pool
                if primary_pool:
                    pool_used[primary_pool] += spin.value()
                continue
            key = _ammo_pool_key(t, self._ammo_limits)
            if key is not None:
                pool_used[key] += spin.value()

        parts = []
        for k, v in self._ammo_limits.items():
            used = pool_used[k]
            belt_sz = self._belt_sizes.get(k)
            # Use friendly display name if pool ammo are all TOW variants
            pool_ammo = [a for a in self._all_ammo_options if _ammo_pool_key(a, self._ammo_limits) == k]
            if not pool_ammo:
                continue  # no selectable ammo for this pool — fixed weapon, hide from counter
            if all("tow" in a.lower() for a in pool_ammo):
                label = "TOW"
            else:
                label = k
            if belt_sz:
                max_belts = -(-v // belt_sz)  # ceiling division
                parts.append(f"{label}: {used} / {max_belts} belts")
            else:
                parts.append(f"{label}: {used} / {v}")
        self.ammo_counter_label.setText("  |  ".join(parts))

    def _refresh_ammo_load_combo(self, tank=None):
        """Repopulate the load combo with DB presets and user-saved loadouts."""
        self.ammo_load_combo.blockSignals(True)
        self.ammo_load_combo.clear()
        has_items = False
        if tank:
            for lo in tank.get("ammo_loadouts", []):
                self.ammo_load_combo.addItem(f"[Preset] {lo['name']}", lo)
                has_items = True
        vid = self.Selected_Vehicle_ID
        if vid and vid in self.user_ammo_loadouts:
            for lo in self.user_ammo_loadouts[vid]:
                self.ammo_load_combo.addItem(lo["name"], lo)
                has_items = True
        self.ammo_load_combo.setEnabled(has_items)
        self.ammo_load_btn.setEnabled(has_items)
        self.ammo_load_combo.blockSignals(False)

    def _save_ammo_loadout(self):
        """Prompt for a name and save the current 4-slot configuration."""
        name, ok = QInputDialog.getText(self, "Save Loadout", "Loadout name:")
        if not ok or not name.strip():
            return
        name = name.strip()
        bullets, counts = [], []
        for combo, spin in zip(self.ammo_slot_combos, self.ammo_slot_spinboxes):
            t = combo.currentData() or combo.currentText()
            if t in ("-- None --", "No ammo data", "", "Stock"):
                bullets.append("")
                counts.append(0)
            else:
                bullets.append(t)
                counts.append(spin.value())
        vid = self.Selected_Vehicle_ID
        if not vid:
            return
        if vid not in self.user_ammo_loadouts:
            self.user_ammo_loadouts[vid] = []
        for i, lo in enumerate(self.user_ammo_loadouts[vid]):
            if lo["name"] == name:
                self.user_ammo_loadouts[vid][i] = {"name": name, "bullets": bullets, "counts": counts}
                self._save_saved_lists()
                tank = next((t for t in self.tank_data if t["ID"] == vid), None)
                self._refresh_ammo_load_combo(tank)
                return
        self.user_ammo_loadouts[vid].append({"name": name, "bullets": bullets, "counts": counts})
        self._save_saved_lists()
        tank = next((t for t in self.tank_data if t["ID"] == vid), None)
        self._refresh_ammo_load_combo(tank)

    def _load_ammo_loadout(self):
        """Populate the 4 slot rows from the selected loadout in the load combo."""
        lo = self.ammo_load_combo.currentData()
        if not lo:
            return
        bullets = lo.get("bullets", [])
        counts  = lo.get("counts",  [9999, 0, 0, 0])
        for i, (combo, spin) in enumerate(zip(self.ammo_slot_combos, self.ammo_slot_spinboxes)):
            b = bullets[i] if i < len(bullets) else ""
            c = counts[i]  if i < len(counts)  else 0
            combo.blockSignals(True)
            if b:
                idx = combo.findData(b)
                combo.setCurrentIndex(idx if idx >= 0 else 0)
            else:
                combo.setCurrentIndex(0)
            spin.setValue(c)
            spin.setEnabled(combo.currentText() != "-- None --")
            combo.blockSignals(False)
        self._sync_ammo_slots()

    # ── Naval: Data Loading ───────────────────────────────────────────────────

    def load_ship_data(self, ship_db_path):
        """Load Ships2.0_DB.json and populate the naval ship list widget."""
        try:
            with open(ship_db_path, 'r', encoding='utf-8') as f:
                self.ship_data = json.load(f)
            self.naval_list_widget.clear()
            for ship in self.ship_data:
                if "name" in ship:
                    self.naval_list_widget.addItem(QListWidgetItem(ship["name"]))
        except json.JSONDecodeError:
            QMessageBox.critical(self, "Error", "Failed to parse Ships2.0_DB.json.")
        except Exception as e:
            QMessageBox.critical(self, "Error", f"Error loading ship data: {str(e)}")

    def populate_naval_target_combos(self):
        """Initialise the three naval target labels and images from current mission state."""
        self.naval_target01_id = self.naval_current_target01_id
        self.naval_target02_id = self.naval_current_target02_id
        self.naval_target03_id = self.naval_current_target03_id

        self.naval_target01_name_label.setText(next((s["name"] for s in self.ship_data if s["ID"] == self.naval_target01_id), self.naval_target01_id or "Not set"))
        self.naval_target02_name_label.setText(next((s["name"] for s in self.ship_data if s["ID"] == self.naval_target02_id), self.naval_target02_id or "Not set"))
        self.naval_target03_name_label.setText(next((s["name"] for s in self.ship_data if s["ID"] == self.naval_target03_id), self.naval_target03_id or "Not set"))

        self.load_image(self.naval_target01_id, self.naval_target01_image_label, "Ship_Previews")
        self.load_image(self.naval_target02_id, self.naval_target02_image_label, "Ship_Previews")
        self.load_image(self.naval_target03_id, self.naval_target03_image_label, "Ship_Previews")

    def pick_naval_target(self, target_num):
        """
        Open VehiclePickerDialog for a naval ship target slot and apply the selection.

        Args:
            target_num (int): 1, 2, or 3 (corresponding to Target_01/02/03).
        """
        dialog = VehiclePickerDialog(self.ship_data, self, self.assets_folder, "Ship_Previews")
        if dialog.exec():
            slot_map = {
                1: ("naval_target01_id", "naval_target01_name_label", "naval_target01_image_label"),
                2: ("naval_target02_id", "naval_target02_name_label", "naval_target02_image_label"),
                3: ("naval_target03_id", "naval_target03_name_label", "naval_target03_image_label"),
            }
            if target_num in slot_map:
                id_attr, name_attr, img_attr = slot_map[target_num]
                setattr(self, id_attr, dialog.selected_id)
                getattr(self, name_attr).setText(dialog.selected_name)
                self.load_image(dialog.selected_id, getattr(self, img_attr), "Ship_Previews")

    def load_naval_plane_data(self):
        """Load Plane2.0_DB.json for the naval air target slots."""
        path = os.path.join(self.assets_folder, "Plane2.0_DB.json")
        if os.path.exists(path):
            try:
                with open(path, 'r', encoding='utf-8') as f:
                    self.naval_plane_data = json.load(f)
            except Exception:
                self.naval_plane_data = []

    def populate_naval_air_targets(self):
        """
        Initialise the Moving Targets tab labels, images, and weapon combos.

        Target_04 is a ship (uses ship_data + Ship_Previews).
        Air_Target_01/02 are aircraft (uses naval_plane_data + Aircraft_Previews).
        Weapons combos for CAS and Bomber are populated from the plane DB entries.
        """
        self.naval_target04_id = self.naval_current_target04_id
        self.naval_air01_id    = self.naval_current_air01_id
        self.naval_air02_id    = self.naval_current_air02_id

        self.naval_target04_name_label.setText(next((s["name"] for s in self.ship_data        if s["ID"] == self.naval_target04_id), self.naval_target04_id or "Not set"))
        self.naval_air01_name_label.setText(   next((p["name"] for p in self.naval_plane_data if p["ID"] == self.naval_air01_id),    self.naval_air01_id    or "Not set"))
        self.naval_air02_name_label.setText(   next((p["name"] for p in self.naval_plane_data if p["ID"] == self.naval_air02_id),    self.naval_air02_id    or "Not set"))

        self.load_image(self.naval_target04_id, self.naval_target04_image_label, "Ship_Previews")
        self.load_image(self.naval_air01_id,    self.naval_air01_image_label,    "Aircraft_Previews")
        self.load_image(self.naval_air02_id,    self.naval_air02_image_label,    "Aircraft_Previews")
        self._populate_weapons_combo(self.naval_air01_id, self.naval_cas_weapons_combo)
        self._populate_weapons_combo(self.naval_air02_id, self.naval_bomber_weapons_combo)

    def _populate_weapons_combo(self, plane_id, combo):
        """Populate a weapons preset combo from the plane's weapons_default list."""
        combo.clear()
        plane = next((p for p in self.naval_plane_data if p["ID"] == plane_id), None)
        if not plane:
            combo.setEnabled(False)
            return
        wd = plane.get("weapons_default", [])
        if isinstance(wd, list) and wd:
            combo.addItems(wd)
            combo.setEnabled(True)
        else:
            combo.addItem("No presets available")
            combo.setEnabled(False)

    def pick_naval_air_target(self, key):
        """
        Open VehiclePickerDialog for a naval air/moving slot and apply the selection.

        Args:
            key (str): 'target04' (ship picker) or 'air01'/'air02' (plane picker).
        """
        if key == "target04":
            dialog = VehiclePickerDialog(self.ship_data, self, self.assets_folder, "Ship_Previews")
        else:
            dialog = VehiclePickerDialog(self.naval_plane_data, self, self.assets_folder, "Aircraft_Previews")

        if dialog.exec():
            if key == "target04":
                self.naval_target04_id = dialog.selected_id
                self.naval_target04_name_label.setText(dialog.selected_name)
                self.load_image(self.naval_target04_id, self.naval_target04_image_label, "Ship_Previews")
            elif key == "air01":
                self.naval_air01_id = dialog.selected_id
                self.naval_air01_name_label.setText(dialog.selected_name)
                self.load_image(self.naval_air01_id, self.naval_air01_image_label, "Aircraft_Previews")
                self._populate_weapons_combo(self.naval_air01_id, self.naval_cas_weapons_combo)
            elif key == "air02":
                self.naval_air02_id = dialog.selected_id
                self.naval_air02_name_label.setText(dialog.selected_name)
                self.load_image(self.naval_air02_id, self.naval_air02_image_label, "Aircraft_Previews")
                self._populate_weapons_combo(self.naval_air02_id, self.naval_bomber_weapons_combo)

    # ── Naval: Ship List Interaction ──────────────────────────────────────────

    def filter_ships(self):
        """Re-populate the naval ship list applying role, search, and country filters."""
        search_term = self.naval_search_entry.text().lower()
        role_filter = self.naval_role_filter_combo.currentText()
        selected_countries = {btn.text() for btn in self.naval_country_button_group.buttons() if btn.isChecked()}
        self.naval_list_widget.clear()
        for ship in self.ship_data:
            if "name" not in ship:
                continue
            if search_term and search_term not in ship["name"].lower():
                continue
            if role_filter != "All":
                role = ship.get("role", [])
                if isinstance(role, str):
                    role = [role]
                if role_filter not in role:
                    continue
            if selected_countries and ship.get("country") not in selected_countries:
                continue
            self.naval_list_widget.addItem(QListWidgetItem(ship["name"]))

    def select_naval_vehicle(self, current, _):
        """Handle naval ship list selection — update display, image, and ammo combo."""
        if not current:
            return
        for ship in self.ship_data:
            if ship["name"] == current.text():
                self.naval_selected_vehicle_id = ship["ID"]
                self.naval_selected_name_label.setText(current.text())
                self.load_image(self.naval_selected_vehicle_id, self.naval_selected_image_label, "Ship_Previews")
                self.populate_naval_ammo_combo(ship)
                break

    def populate_naval_ammo_combo(self, ship):
        """
        Rebuild the naval ammo section with one combo per caliber (up to 4).

        Groups ammo IDs by caliber prefix (e.g. "203mm"), orders largest first
        so the main battery is always at the top, and maps bullets0-3 in that
        same order when writing to the mission blk.
        """
        # Clear existing rows
        while self._naval_ammo_container_layout.count():
            item = self._naval_ammo_container_layout.takeAt(0)
            if item.widget():
                item.widget().setParent(None)
        self.naval_ammo_combos = []

        ammo_list = ship.get("ammo", [])
        ammo_limits = ship.get("ammo_limits", {})

        # No usable ammo data
        if not ammo_list or ammo_list == ["N/A"] or not ammo_limits:
            lbl = QLabel("No ammo data")
            lbl.setEnabled(False)
            self._naval_ammo_container_layout.addWidget(lbl)
            return

        # Group ammo IDs by caliber prefix (first token before "_")
        ammo_by_cal = {}
        for ammo_id in ammo_list:
            if not ammo_id or ammo_id == "N/A":
                continue
            cal = ammo_id.split("_")[0]
            ammo_by_cal.setdefault(cal, []).append(ammo_id)

        # Sort calibers numerically descending (main battery first), cap at 4
        def _cal_num(c):
            try:
                return int("".join(ch for ch in c if ch.isdigit()))
            except ValueError:
                return 0

        calibers = sorted(ammo_by_cal, key=_cal_num, reverse=True)[:4]

        for cal in calibers:
            row = QWidget()
            row_layout = QHBoxLayout(row)
            row_layout.setContentsMargins(0, 0, 0, 0)
            row_layout.addWidget(QLabel(f"{cal}:"))
            combo = QComboBox()
            for ammo_id in ammo_by_cal[cal]:
                display = self._ammo_names.get(ammo_id, ammo_id)
                combo.addItem(display, userData=ammo_id)
            row_layout.addWidget(combo, 1)
            self._naval_ammo_container_layout.addWidget(row)
            self.naval_ammo_combos.append((cal, combo))

    # ── Saved: Ground ─────────────────────────────────────────────────────────

    def _refresh_ground_saved_ui(self):
        """Rebuild the ground Recently Used and Favourites list widgets from current lists."""
        self.ground_ru_list.clear()
        for vid in self.ground_recently_used:
            name = next((t["name"] for t in self.tank_data if t["ID"] == vid), vid)
            item = QListWidgetItem(name)
            item.setData(Qt.ItemDataRole.UserRole, vid)
            self.ground_ru_list.addItem(item)

        self.ground_fav_list.clear()
        for vid in self.ground_favourites:
            name = next((t["name"] for t in self.tank_data if t["ID"] == vid), vid)
            item = QListWidgetItem(name)
            item.setData(Qt.ItemDataRole.UserRole, vid)
            self.ground_fav_list.addItem(item)

        self._refresh_ground_presets_ui()

    def _refresh_ground_presets_ui(self):
        """Rebuild the ground User Presets list widget."""
        self.ground_user_presets_list.clear()
        for i, preset in enumerate(self.user_ground_presets):
            item = QListWidgetItem(preset["name"])
            item.setData(Qt.ItemDataRole.UserRole, i)
            self.ground_user_presets_list.addItem(item)

    def _ground_add_recently_used(self, vehicle_id):
        """Add vehicle_id to front of recently used (max 12) and persist."""
        if vehicle_id in self.ground_recently_used:
            self.ground_recently_used.remove(vehicle_id)
        self.ground_recently_used.insert(0, vehicle_id)
        self.ground_recently_used = self.ground_recently_used[:12]
        self._save_saved_lists()
        self._refresh_ground_saved_ui()

    def _select_ground_saved(self, vehicle_id):
        """Load a vehicle by ID into the Vehicle tab's selected slot."""
        tank = next((t for t in self.tank_data if t["ID"] == vehicle_id), None)
        if not tank:
            return
        self.Selected_Vehicle_ID = vehicle_id
        self.selected_name_label.setText(tank["name"])
        self.load_image(vehicle_id, self.selected_image_label)
        self.populate_ammo_combo(tank)
        self.tab_widget.setCurrentIndex(0)

    def _ground_ru_select(self):
        item = self.ground_ru_list.currentItem()
        if item:
            self._select_ground_saved(item.data(Qt.ItemDataRole.UserRole))

    def _ground_ru_add_fav(self):
        item = self.ground_ru_list.currentItem()
        if not item:
            return
        vid = item.data(Qt.ItemDataRole.UserRole)
        if vid not in self.ground_favourites:
            self.ground_favourites.append(vid)
            self._save_saved_lists()
            self._refresh_ground_saved_ui()

    def _ground_fav_select(self):
        item = self.ground_fav_list.currentItem()
        if item:
            self._select_ground_saved(item.data(Qt.ItemDataRole.UserRole))

    def _ground_fav_remove(self):
        item = self.ground_fav_list.currentItem()
        if not item:
            return
        vid = item.data(Qt.ItemDataRole.UserRole)
        if vid in self.ground_favourites:
            self.ground_favourites.remove(vid)
            self._save_saved_lists()
            self._refresh_ground_saved_ui()

    def _random_ground_vehicle(self):
        """Select a random vehicle from the loaded tank database."""
        if not self.tank_data:
            return
        tank = random.choice(self.tank_data)
        self._select_ground_saved(tank["ID"])

    def _random_ground_targets(self):
        """Randomise all ground target slots (tanks, aircraft, helicopter)."""
        def pick(data, id_attr, name_attr, img_attr, subfolder="Tank_Previews"):
            pool = [x for x in data if x.get("role") != "Special"]
            if not pool:
                return
            v = random.choice(pool)
            setattr(self, id_attr, v["ID"])
            getattr(self, name_attr).setText(v["name"])
            self.load_image(v["ID"], getattr(self, img_attr), subfolder)

        pick(self.tank_data,  "target03_id",    "target03_name_label",    "target03_image_label")
        pick(self.tank_data,  "target04_id",    "target04_name_label",    "target04_image_label")
        pick(self.tank_data,  "target05_id",    "target05_name_label",    "target05_image_label")
        pick(self.tank_data,  "target06_id",    "target06_name_label",    "target06_image_label")
        pick(self.ship_data,  "ship_target_id", "ship_target_name_label", "ship_target_image_label", "Ship_Previews")
        pick(self.plane_data, "air01_id",       "air01_name_label",       "air01_image_label",       "Aircraft_Previews")
        pick(self.plane_data, "air02_id",       "air02_name_label",       "air02_image_label",       "Aircraft_Previews")
        pick(self.heli_data,  "heli_id",        "heli_name_label",        "heli_image_label",        "Aircraft_Previews")

    def _random_ground_time_weather(self):
        """Randomise the time of day and weather selectors for the ground mission."""
        self.time_combo.setCurrentIndex(random.randrange(self.time_combo.count()))
        self.weather_combo.setCurrentIndex(random.randrange(self.weather_combo.count()))

    # ── Ground: User Presets ──────────────────────────────────────────────────

    def _ground_save_preset(self):
        """Prompt for a name and save the current ground configuration as a user preset."""
        dlg = QInputDialog(self)
        dlg.setWindowTitle("Save Preset")
        dlg.setLabelText("Preset name:")
        dlg.resize(500, dlg.sizeHint().height())
        ok = dlg.exec()
        name = dlg.textValue().strip()
        if not ok or not name:
            return
        existing_names = [p["name"] for p in self.user_ground_presets]
        if name in existing_names:
            reply = QMessageBox.question(
                self, "Duplicate Name",
                f"A preset named '{name}' already exists. Overwrite it?",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
            )
            if reply != QMessageBox.StandardButton.Yes:
                return
            self.user_ground_presets = [p for p in self.user_ground_presets if p["name"] != name]
        wo_mode = ("ground"   if self.wo_ground_radio.isChecked()   else
                   "naval"    if self.wo_naval_radio.isChecked()    else
                   "aircraft" if self.wo_aircraft_radio.isChecked() else "none")
        preset = {
            "name":        name,
            "vehicle_id":  self.Selected_Vehicle_ID or self.Current_Vehicle_ID,
            "ammo_bullets": [
                "" if (c.currentData() or c.currentText()) in ("-- None --", "No ammo data", "Stock")
                else (c.currentData() or c.currentText())
                for c in self.ammo_slot_combos
            ],
            "ammo_counts": [s.value() for s in self.ammo_slot_spinboxes],
            "environment": self.time_combo.currentText(),
            "weather":     self.weather_combo.currentText(),
            "target03_id":       self.target03_id,
            "target03_rotation": self.target03_dial.value(),
            "target04_id":       self.target04_id,
            "target04_rotation": self.target04_dial.value(),
            "target05_id":       self.target05_id,
            "target05_rotation": self.target05_dial.value(),
            "target06_id":       self.target06_id,
            "ship_target_id":    self.ship_target_id,
            "air01_id":          self.air01_id,
            "air02_id":          self.air02_id,
            "heli_id":           self.heli_id,
            "engine_enabled": self.power_shift_checkbox.isChecked(),
            "engine_hp":      self.horse_powers_spinbox.value(),
            "engine_rpm":     self.max_rpm_spinbox.value(),
            "engine_mass":    self.mass_spinbox.value(),
            "rapid_fire_enabled": self.rapid_fire_checkbox.isChecked(),
            "rapid_fire_time":    self.rapid_fire_spinbox.value(),
            "weapon_override_mode":   wo_mode,
            "weapon_override_donor":  self.weapon_override_donor_id or self.weapon_override_current_donor_id,
            "weapon_override_weapon": self.weapon_override_combo.currentData() or self.weapon_override_current_weapon_blk,
            "naval_wo_donor":         self.naval_weapon_override_donor_id or self.naval_weapon_override_current_donor_id,
            "naval_wo_weapon":        self.naval_weapon_override_combo.currentData() or self.naval_weapon_override_current_weapon_blk,
            "aircraft_wo_donor":      self.aircraft_weapon_override_donor_id or self.aircraft_weapon_override_current_donor_id,
            "aircraft_wo_weapon":     self.aircraft_weapon_override_combo.currentData() or self.aircraft_weapon_override_current_weapon_blk,
            "velocity_enabled": self.velocity_override_checkbox.isChecked(),
            "velocity_speed":   self.velocity_spinbox.value(),
            "caliber_enabled":  self.caliber_override_checkbox.isChecked(),
            "caliber_value":    self.caliber_spinbox.value(),
        }
        self.user_ground_presets.append(preset)
        self._save_saved_lists()
        self._refresh_ground_presets_ui()

    def _ground_apply_preset(self, preset):
        """Apply a ground preset dict to all UI slots."""
        vid = preset.get("vehicle_id")
        if vid:
            if not any(t["ID"] == vid for t in self.tank_data):
                QMessageBox.warning(
                    self, "Vehicle Not Found",
                    f"The vehicle '{vid}' saved in this preset no longer exists in the database.\n"
                    "It may have been removed in a database update. All other preset settings will still be applied."
                )
            self._select_ground_saved(vid)
            ammo_bullets = preset.get("ammo_bullets", [])
            ammo_counts  = preset.get("ammo_counts",  [9999, 0, 0, 0])
            # Backward-compat: old presets stored a single "ammo" string
            if not ammo_bullets:
                old_ammo = preset.get("ammo", "")
                ammo_bullets = [old_ammo, "", "", ""]
                ammo_counts  = [9999, 0, 0, 0]
            if ammo_bullets:
                for i, (combo, spin) in enumerate(zip(self.ammo_slot_combos, self.ammo_slot_spinboxes)):
                    b = ammo_bullets[i] if i < len(ammo_bullets) else ""
                    c = ammo_counts[i]  if i < len(ammo_counts)  else 0
                    combo.blockSignals(True)
                    if b:
                        idx = combo.findData(b)
                        combo.setCurrentIndex(idx if idx >= 0 else 0)
                    else:
                        combo.setCurrentIndex(0)
                    spin.setValue(c)
                    spin.setEnabled(combo.currentText() != "-- None --")
                    combo.blockSignals(False)

        for key, val in [("environment", self.time_combo), ("weather", self.weather_combo)]:
            v = preset.get(key)
            if v:
                idx = val.findText(v, Qt.MatchFlag.MatchFixedString)
                if idx >= 0:
                    val.setCurrentIndex(idx)

        for id_attr, name_attr, img_attr, preset_key, rot_attr, data, subfolder in [
            ("target03_id",    "target03_name_label",    "target03_image_label",    "target03_id",    "target03_dial", self.tank_data,  "Tank_Previews"),
            ("target04_id",    "target04_name_label",    "target04_image_label",    "target04_id",    "target04_dial", self.tank_data,  "Tank_Previews"),
            ("target05_id",    "target05_name_label",    "target05_image_label",    "target05_id",    "target05_dial", self.tank_data,  "Tank_Previews"),
            ("target06_id",    "target06_name_label",    "target06_image_label",    "target06_id",    None,            self.tank_data,  "Tank_Previews"),
            ("ship_target_id", "ship_target_name_label", "ship_target_image_label", "ship_target_id", None,            self.ship_data,  "Ship_Previews"),
            ("air01_id",       "air01_name_label",       "air01_image_label",       "air01_id",       None,            self.plane_data, "Aircraft_Previews"),
            ("air02_id",       "air02_name_label",       "air02_image_label",       "air02_id",       None,            self.plane_data, "Aircraft_Previews"),
            ("heli_id",        "heli_name_label",        "heli_image_label",        "heli_id",        None,            self.heli_data,  "Aircraft_Previews"),
        ]:
            tid = preset.get(preset_key)
            if tid:
                setattr(self, id_attr, tid)
                getattr(self, name_attr).setText(next((t["name"] for t in data if t["ID"] == tid), tid))
                self.load_image(tid, getattr(self, img_attr), subfolder)
            if rot_attr:
                rot = preset.get(f"{id_attr[:-3]}_rotation")
                if rot is not None:
                    getattr(self, rot_attr).setValue(int(rot))

        # Engine override
        if preset.get("engine_enabled") is not None:
            self.power_shift_checkbox.setChecked(preset["engine_enabled"])
            self.engine_override_controls.setEnabled(preset["engine_enabled"])
        if preset.get("engine_hp") is not None:
            self.horse_powers_spinbox.setValue(preset["engine_hp"])
        if preset.get("engine_rpm") is not None:
            self.max_rpm_spinbox.setValue(preset["engine_rpm"])
        if preset.get("engine_mass") is not None:
            self.mass_spinbox.setValue(preset["engine_mass"])

        # Rapid fire
        if preset.get("rapid_fire_enabled") is not None:
            self.rapid_fire_checkbox.setChecked(preset["rapid_fire_enabled"])
            self.rapid_fire_controls.setEnabled(preset["rapid_fire_enabled"])
        if preset.get("rapid_fire_time") is not None:
            self.rapid_fire_spinbox.setValue(preset["rapid_fire_time"])

        # Weapon override
        wo_mode   = preset.get("weapon_override_mode", "none")
        wo_donor  = preset.get("weapon_override_donor", "")
        wo_weapon = preset.get("weapon_override_weapon", "")
        nw_donor  = preset.get("naval_wo_donor", "")
        nw_weapon = preset.get("naval_wo_weapon", "")
        aw_donor  = preset.get("aircraft_wo_donor", "")
        aw_weapon = preset.get("aircraft_wo_weapon", "")
        if wo_mode == "ground":
            self.wo_ground_radio.setChecked(True)
            if wo_donor:
                self.weapon_override_donor_id = wo_donor
                donor_name = next((t["name"] for t in self.tank_data if t["ID"] == wo_donor), wo_donor)
                self.weapon_override_name_label.setText(donor_name)
                self._populate_weapon_override_combo(self.weapon_override_combo, wo_donor, "Weapons2.0_DB.json", wo_weapon)
        elif wo_mode == "naval":
            self.wo_naval_radio.setChecked(True)
            if nw_donor:
                self.naval_weapon_override_donor_id = nw_donor
                donor_name = next((s["name"] for s in self.ship_data if s["ID"] == nw_donor), nw_donor)
                self.naval_weapon_override_name_label.setText(donor_name)
                self._populate_weapon_override_combo(self.naval_weapon_override_combo, nw_donor, "NavalWeapons2.0_DB.json", nw_weapon)
        elif wo_mode == "aircraft":
            self.wo_aircraft_radio.setChecked(True)
            if aw_donor:
                self.aircraft_weapon_override_donor_id = aw_donor
                self.load_air_data()
                donor_name = next((p["name"] for p in self.plane_data + self.heli_data if p["ID"] == aw_donor), aw_donor)
                self.aircraft_weapon_override_name_label.setText(donor_name)
                self._populate_weapon_override_combo(self.aircraft_weapon_override_combo, aw_donor, "AircraftWeapons2.0_DB.json", aw_weapon)
        else:
            self.wo_none_radio.setChecked(True)

        # Velocity / caliber override
        if preset.get("velocity_enabled") is not None:
            self.velocity_override_checkbox.setChecked(preset["velocity_enabled"])
            self.velocity_controls.setEnabled(preset["velocity_enabled"])
        if preset.get("velocity_speed") is not None:
            self.velocity_spinbox.setValue(preset["velocity_speed"])
            self.velocity_slider.setValue(preset["velocity_speed"])
        if preset.get("caliber_enabled") is not None:
            self.caliber_override_checkbox.setChecked(preset["caliber_enabled"])
            self.caliber_controls_widget.setEnabled(preset["caliber_enabled"])
        if preset.get("caliber_value") is not None:
            self.caliber_spinbox.setValue(preset["caliber_value"])

    def _ground_load_preset(self):
        """Load the selected user preset into all ground UI slots."""
        item = self.ground_user_presets_list.currentItem()
        if not item:
            return
        self._ground_apply_preset(self.user_ground_presets[item.data(Qt.ItemDataRole.UserRole)])

    def _ground_rename_preset(self):
        """Prompt for a new name and rename the selected user preset."""
        item = self.ground_user_presets_list.currentItem()
        if not item:
            return
        idx = item.data(Qt.ItemDataRole.UserRole)
        dlg = QInputDialog(self)
        dlg.setWindowTitle("Rename Preset")
        dlg.setLabelText("New name:")
        dlg.setTextValue(self.user_ground_presets[idx]["name"])
        dlg.resize(500, dlg.sizeHint().height())
        if not dlg.exec() or not dlg.textValue().strip():
            return
        self.user_ground_presets[idx]["name"] = dlg.textValue().strip()
        self._save_saved_lists()
        self._refresh_ground_presets_ui()

    def _ground_delete_preset(self):
        """Delete the selected user preset after confirmation."""
        item = self.ground_user_presets_list.currentItem()
        if not item:
            return
        idx = item.data(Qt.ItemDataRole.UserRole)
        if QMessageBox.question(self, "Delete Preset", f"Delete '{self.user_ground_presets[idx]['name']}'?",
                                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No) == QMessageBox.StandardButton.Yes:
            del self.user_ground_presets[idx]
            self._save_saved_lists()
            self._refresh_ground_presets_ui()

    # ── Presets: Import / Export ──────────────────────────────────────────────

    def _export_presets(self, mode):
        """Export ground or naval user presets to a JSON file."""
        presets = self.user_ground_presets if mode == "ground" else self.user_naval_presets
        if not presets:
            QMessageBox.information(self, "Export Presets", "No presets to export.")
            return
        path, _ = QFileDialog.getSaveFileName(
            self, "Export Presets", f"{mode}_presets.json", "JSON Files (*.json)"
        )
        if not path:
            return
        try:
            with open(path, "w", encoding="utf-8") as f:
                json.dump({"mode": mode, "presets": presets}, f, indent=4)
            QMessageBox.information(self, "Export Presets",
                f"Exported {len(presets)} preset(s) to:\n{path}")
        except Exception as e:
            QMessageBox.critical(self, "Export Failed", str(e))

    def _import_presets(self, mode):
        """Import ground or naval user presets from a JSON file."""
        path, _ = QFileDialog.getOpenFileName(
            self, "Import Presets", "", "JSON Files (*.json)"
        )
        if not path:
            return
        try:
            with open(path, "r", encoding="utf-8") as f:
                data = json.load(f)
        except Exception as e:
            QMessageBox.critical(self, "Import Failed", f"Could not read file:\n{e}")
            return

        incoming = data.get("presets", [])
        if not isinstance(incoming, list) or not incoming:
            QMessageBox.warning(self, "Import Presets", "No presets found in this file.")
            return

        file_mode = data.get("mode", "")
        if file_mode and file_mode != mode:
            reply = QMessageBox.question(
                self, "Mode Mismatch",
                f"This file contains {file_mode} presets but you are importing into {mode}.\n"
                "Import anyway?",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
            )
            if reply != QMessageBox.StandardButton.Yes:
                return

        current = self.user_ground_presets if mode == "ground" else self.user_naval_presets
        existing_names = {p["name"] for p in current}
        duplicates = [p["name"] for p in incoming if p["name"] in existing_names]

        overwrite = False
        if duplicates:
            msg = QMessageBox(self)
            msg.setWindowTitle("Duplicate Presets")
            msg.setText(f"{len(duplicates)} preset(s) already exist with the same name:")
            msg.setInformativeText("\n".join(f"  • {n}" for n in duplicates))
            overwrite_btn = msg.addButton("Overwrite", QMessageBox.ButtonRole.AcceptRole)
            msg.addButton("Skip Duplicates", QMessageBox.ButtonRole.NoRole)
            msg.addButton("Cancel", QMessageBox.ButtonRole.RejectRole)
            msg.exec()
            clicked = msg.clickedButton()
            if clicked is None or clicked.text() == "Cancel":
                return
            overwrite = (clicked == overwrite_btn)

        added = 0
        for preset in incoming:
            name = preset.get("name", "").strip()
            if not name:
                continue
            if name in existing_names:
                if overwrite:
                    current[:] = [p for p in current if p["name"] != name]
                else:
                    continue
            current.append(preset)
            existing_names.add(name)
            added += 1

        self._save_saved_lists()
        if mode == "ground":
            self._refresh_ground_presets_ui()
        else:
            self._refresh_naval_presets_ui()

        QMessageBox.information(self, "Import Presets", f"Imported {added} preset(s).")

    # ── Saved: Naval ──────────────────────────────────────────────────────────

    def _refresh_naval_saved_ui(self):
        """Rebuild the naval Recently Used and Favourites list widgets from current lists."""
        self.naval_ru_list.clear()
        for vid in self.naval_recently_used:
            name = next((s["name"] for s in self.ship_data if s["ID"] == vid), vid)
            item = QListWidgetItem(name)
            item.setData(Qt.ItemDataRole.UserRole, vid)
            self.naval_ru_list.addItem(item)

        self.naval_fav_list.clear()
        for vid in self.naval_favourites:
            name = next((s["name"] for s in self.ship_data if s["ID"] == vid), vid)
            item = QListWidgetItem(name)
            item.setData(Qt.ItemDataRole.UserRole, vid)
            self.naval_fav_list.addItem(item)

        self._refresh_naval_presets_ui()

    def _refresh_naval_presets_ui(self):
        """Rebuild the naval User Presets list widget."""
        self.naval_user_presets_list.clear()
        for i, preset in enumerate(self.user_naval_presets):
            item = QListWidgetItem(preset["name"])
            item.setData(Qt.ItemDataRole.UserRole, i)
            self.naval_user_presets_list.addItem(item)

    def _naval_add_recently_used(self, vehicle_id):
        """Add ship_id to front of recently used (max 12) and persist."""
        if vehicle_id in self.naval_recently_used:
            self.naval_recently_used.remove(vehicle_id)
        self.naval_recently_used.insert(0, vehicle_id)
        self.naval_recently_used = self.naval_recently_used[:12]
        self._save_saved_lists()
        self._refresh_naval_saved_ui()

    def _select_naval_saved(self, vehicle_id):
        """Load a ship by ID into the Vessel tab's selected slot."""
        ship = next((s for s in self.ship_data if s["ID"] == vehicle_id), None)
        if not ship:
            return
        self.naval_selected_vehicle_id = vehicle_id
        self.naval_selected_name_label.setText(ship["name"])
        self.load_image(vehicle_id, self.naval_selected_image_label, "Ship_Previews")
        self.populate_naval_ammo_combo(ship)
        self.naval_tab_widget.setCurrentIndex(0)

    def _naval_ru_select(self):
        item = self.naval_ru_list.currentItem()
        if item:
            self._select_naval_saved(item.data(Qt.ItemDataRole.UserRole))

    def _naval_ru_add_fav(self):
        item = self.naval_ru_list.currentItem()
        if not item:
            return
        vid = item.data(Qt.ItemDataRole.UserRole)
        if vid not in self.naval_favourites:
            self.naval_favourites.append(vid)
            self._save_saved_lists()
            self._refresh_naval_saved_ui()

    def _naval_fav_select(self):
        item = self.naval_fav_list.currentItem()
        if item:
            self._select_naval_saved(item.data(Qt.ItemDataRole.UserRole))

    def _naval_fav_remove(self):
        item = self.naval_fav_list.currentItem()
        if not item:
            return
        vid = item.data(Qt.ItemDataRole.UserRole)
        if vid in self.naval_favourites:
            self.naval_favourites.remove(vid)
            self._save_saved_lists()
            self._refresh_naval_saved_ui()

    def _random_naval_vehicle(self):
        """Select a random ship from the loaded ship database."""
        if not self.ship_data:
            return
        ship = random.choice(self.ship_data)
        self._select_naval_saved(ship["ID"])

    def _random_naval_targets(self):
        """Randomise all naval target slots (ships and aircraft)."""
        def pick(data, id_attr, name_attr, img_attr, subfolder="Ship_Previews"):
            pool = [x for x in data if x.get("role") != "Special"]
            if not pool:
                return
            v = random.choice(pool)
            setattr(self, id_attr, v["ID"])
            getattr(self, name_attr).setText(v["name"])
            self.load_image(v["ID"], getattr(self, img_attr), subfolder)

        pick(self.ship_data,        "naval_target01_id", "naval_target01_name_label", "naval_target01_image_label")
        pick(self.ship_data,        "naval_target02_id", "naval_target02_name_label", "naval_target02_image_label")
        pick(self.ship_data,        "naval_target03_id", "naval_target03_name_label", "naval_target03_image_label")
        pick(self.ship_data,        "naval_target04_id", "naval_target04_name_label", "naval_target04_image_label")
        pick(self.naval_plane_data, "naval_air01_id",    "naval_air01_name_label",    "naval_air01_image_label",    "Aircraft_Previews")
        pick(self.naval_plane_data, "naval_air02_id",    "naval_air02_name_label",    "naval_air02_image_label",    "Aircraft_Previews")
        self._populate_weapons_combo(self.naval_air01_id, self.naval_cas_weapons_combo)
        self._populate_weapons_combo(self.naval_air02_id, self.naval_bomber_weapons_combo)

    def _random_naval_time_weather(self):
        """Randomise the time of day and weather selectors for the naval mission."""
        self.naval_time_combo.setCurrentIndex(random.randrange(self.naval_time_combo.count()))
        self.naval_weather_combo.setCurrentIndex(random.randrange(self.naval_weather_combo.count()))

    # ── Naval: User Presets ───────────────────────────────────────────────────

    def _naval_save_preset(self):
        """Prompt for a name and save the current naval configuration as a user preset."""
        dlg = QInputDialog(self)
        dlg.setWindowTitle("Save Preset")
        dlg.setLabelText("Preset name:")
        dlg.resize(500, dlg.sizeHint().height())
        ok = dlg.exec()
        name = dlg.textValue().strip()
        if not ok or not name:
            return
        existing_names = [p["name"] for p in self.user_naval_presets]
        if name in existing_names:
            reply = QMessageBox.question(
                self, "Duplicate Name",
                f"A preset named '{name}' already exists. Overwrite it?",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
            )
            if reply != QMessageBox.StandardButton.Yes:
                return
            self.user_naval_presets = [p for p in self.user_naval_presets if p["name"] != name]
        shooter_ids      = [self.naval_shooter_ids[i] or self.naval_shooter_current_ids[i] for i in range(8)]
        shooter_enabled  = [self.naval_shooter_checkboxes[i].isChecked() for i in range(8)]
        preset = {
            "name":           name,
            "vehicle_id":     self.naval_selected_vehicle_id or self.naval_current_vehicle_id,
            "ammo":           [combo.currentText() for _, combo in self.naval_ammo_combos] if self.naval_ammo_combos else [],
            "environment":    self.naval_time_combo.currentText(),
            "weather":        self.naval_weather_combo.currentText(),
            "target01_id":    self.naval_target01_id,
            "target02_id":    self.naval_target02_id,
            "target03_id":    self.naval_target03_id,
            "target04_id":    self.naval_target04_id,
            "air01_id":       self.naval_air01_id,
            "air02_id":       self.naval_air02_id,
            "cas_weapons":    self.naval_cas_weapons_combo.currentText()    if self.naval_cas_weapons_combo.isEnabled()    else "",
            "bomber_weapons": self.naval_bomber_weapons_combo.currentText() if self.naval_bomber_weapons_combo.isEnabled() else "",
            "shooter_ids":     shooter_ids,
            "shooter_enabled": shooter_enabled,
        }
        self.user_naval_presets.append(preset)
        self._save_saved_lists()
        self._refresh_naval_presets_ui()

    def _naval_apply_preset(self, preset):
        """Apply a naval preset dict to all UI slots."""
        vid = preset.get("vehicle_id")
        if vid:
            if not any(s["ID"] == vid for s in self.ship_data):
                QMessageBox.warning(
                    self, "Ship Not Found",
                    f"The ship '{vid}' saved in this preset no longer exists in the database.\n"
                    "It may have been removed in a database update. All other preset settings will still be applied."
                )
            self._select_naval_saved(vid)
            ammo = preset.get("ammo", [])
            if isinstance(ammo, str):
                ammo = [ammo] if ammo else []   # backward compat with old string format
            for i, ammo_id in enumerate(ammo[:len(self.naval_ammo_combos)]):
                _, combo = self.naval_ammo_combos[i]
                # Find by userData (raw ammo ID) first; fall back to display text
                idx = combo.findData(ammo_id)
                if idx < 0:
                    idx = combo.findText(ammo_id, Qt.MatchFlag.MatchFixedString)
                if idx >= 0:
                    combo.setCurrentIndex(idx)

        for key, val in [("environment", self.naval_time_combo), ("weather", self.naval_weather_combo)]:
            v = preset.get(key)
            if v:
                idx = val.findText(v, Qt.MatchFlag.MatchFixedString)
                if idx >= 0:
                    val.setCurrentIndex(idx)

        for id_attr, name_attr, img_attr, preset_key, data, subfolder in [
            ("naval_target01_id", "naval_target01_name_label", "naval_target01_image_label", "target01_id", self.ship_data,        "Ship_Previews"),
            ("naval_target02_id", "naval_target02_name_label", "naval_target02_image_label", "target02_id", self.ship_data,        "Ship_Previews"),
            ("naval_target03_id", "naval_target03_name_label", "naval_target03_image_label", "target03_id", self.ship_data,        "Ship_Previews"),
            ("naval_target04_id", "naval_target04_name_label", "naval_target04_image_label", "target04_id", self.ship_data,        "Ship_Previews"),
            ("naval_air01_id",    "naval_air01_name_label",    "naval_air01_image_label",    "air01_id",    self.naval_plane_data, "Aircraft_Previews"),
            ("naval_air02_id",    "naval_air02_name_label",    "naval_air02_image_label",    "air02_id",    self.naval_plane_data, "Aircraft_Previews"),
        ]:
            tid = preset.get(preset_key)
            if tid:
                setattr(self, id_attr, tid)
                getattr(self, name_attr).setText(next((t["name"] for t in data if t["ID"] == tid), tid))
                self.load_image(tid, getattr(self, img_attr), subfolder)

        self._populate_weapons_combo(self.naval_air01_id, self.naval_cas_weapons_combo)
        self._populate_weapons_combo(self.naval_air02_id, self.naval_bomber_weapons_combo)
        for combo, key in [(self.naval_cas_weapons_combo, "cas_weapons"), (self.naval_bomber_weapons_combo, "bomber_weapons")]:
            v = preset.get(key, "")
            if v and combo.isEnabled():
                idx = combo.findText(v, Qt.MatchFlag.MatchFixedString)
                if idx >= 0:
                    combo.setCurrentIndex(idx)

        shooter_ids     = preset.get("shooter_ids", [])
        shooter_enabled = preset.get("shooter_enabled", [bool(uid) for uid in shooter_ids])  # backward compat
        for i in range(min(8, max(len(shooter_ids), len(shooter_enabled)))):
            uid     = shooter_ids[i]     if i < len(shooter_ids)     else self.naval_shooter_current_ids[i]
            enabled = shooter_enabled[i] if i < len(shooter_enabled) else bool(uid)
            self.naval_shooter_ids[i] = uid
            self.naval_shooter_checkboxes[i].setChecked(enabled)
            name = next((s["name"] for s in self.ship_data if s["ID"] == uid), uid or "Not set")
            self.naval_shooter_name_labels[i].setText(name)
            self.load_image(uid or None, self.naval_shooter_image_labels[i], "Ship_Previews", size=60)

    def _naval_load_preset(self):
        """Load the selected user preset into all naval UI slots."""
        item = self.naval_user_presets_list.currentItem()
        if not item:
            return
        self._naval_apply_preset(self.user_naval_presets[item.data(Qt.ItemDataRole.UserRole)])

    def _naval_rename_preset(self):
        """Prompt for a new name and rename the selected naval user preset."""
        item = self.naval_user_presets_list.currentItem()
        if not item:
            return
        idx = item.data(Qt.ItemDataRole.UserRole)
        dlg = QInputDialog(self)
        dlg.setWindowTitle("Rename Preset")
        dlg.setLabelText("New name:")
        dlg.setTextValue(self.user_naval_presets[idx]["name"])
        dlg.resize(500, dlg.sizeHint().height())
        if not dlg.exec() or not dlg.textValue().strip():
            return
        self.user_naval_presets[idx]["name"] = dlg.textValue().strip()
        self._save_saved_lists()
        self._refresh_naval_presets_ui()

    def _naval_delete_preset(self):
        """Delete the selected naval user preset after confirmation."""
        item = self.naval_user_presets_list.currentItem()
        if not item:
            return
        idx = item.data(Qt.ItemDataRole.UserRole)
        if QMessageBox.question(self, "Delete Preset", f"Delete '{self.user_naval_presets[idx]['name']}'?",
                                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No) == QMessageBox.StandardButton.Yes:
            del self.user_naval_presets[idx]
            self._save_saved_lists()
            self._refresh_naval_presets_ui()

    # ── Shared: Image Loading ─────────────────────────────────────────────────

    def load_image(self, vehicle_id, label, subfolder="Tank_Previews", size=120):
        """
        Load and display a vehicle preview image scaled to size×size px.

        Falls back to default.png in the same subfolder if the specific
        image is not found. Clears the label if neither exists.

        Args:
            vehicle_id (str | None): Vehicle ID used as the filename (without .png).
            label      (QLabel):     Label widget to display the image on.
            subfolder  (str):        Subfolder inside Vehicle_Previews/.
            size       (int):        Square size in pixels to scale the image to.
        """
        if not vehicle_id:
            label.clear()
            return
        image_path = os.path.join(self.assets_folder, "Vehicle_Previews", subfolder, f"{vehicle_id}.png")
        if not os.path.exists(image_path):
            image_path = os.path.join(self.assets_folder, "Vehicle_Previews", subfolder, "default.png")
        if os.path.exists(image_path):
            pixmap = QPixmap(image_path).scaled(size, size, Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation)
            label.setPixmap(pixmap)
        else:
            label.clear()

    # ── Shared: Apply Router ──────────────────────────────────────────────────

    def _on_apply(self):
        """Route the Apply button to ground or naval apply based on the active mode tab."""
        if not self.test_drive_file:
            msg = QMessageBox(self)
            msg.setWindowTitle("War Thunder Directory Not Set")
            msg.setIcon(QMessageBox.Icon.Warning)
            msg.setText("No War Thunder directory has been set yet.")
            msg.setInformativeText(
                "To find your War Thunder folder:\n\n"
                "• Steam:  open Steam → right-click War Thunder → Manage → Browse local files\n"
                "  (usually C:\\Program Files (x86)\\Steam\\steamapps\\common\\War Thunder)\n\n"
                "• Gaijin Launcher:  check the install path you chose during setup\n"
                "  (usually C:\\Program Files\\War Thunder)\n\n"
                "Click 'Locate Now' then select that folder."
            )
            locate_btn = msg.addButton("Locate Now", QMessageBox.ButtonRole.AcceptRole)
            msg.addButton("Cancel", QMessageBox.ButtonRole.RejectRole)
            msg.exec()
            if msg.clickedButton() == locate_btn:
                self.locate_test_drive_file()
            return
        if self.mode_tabs.currentIndex() == 0:
            self.apply_changes()
        else:
            self.apply_naval_changes()

    # ── Ground: Apply Changes ─────────────────────────────────────────────────

    def _has_changes(self):
        """Return True if any ground setting differs from what is in the mission files."""
        if self.Selected_Vehicle_ID and self.Selected_Vehicle_ID != self.Current_Vehicle_ID:
            return True
        if self.time_combo.currentText() != (self.current_environment or ""):
            return True
        if self.weather_combo.currentText() != (self.current_weather or ""):
            return True
        if self.target03_id != self.current_target03_id:
            return True
        if abs(self.target03_dial.value() - self.current_target03_rotation) > 0.5:
            return True
        if self.target04_id != self.current_target04_id:
            return True
        if abs(self.target04_dial.value() - self.current_target04_rotation) > 0.5:
            return True
        if self.target05_id != self.current_target05_id:
            return True
        if abs(self.target05_dial.value() - self.current_target05_rotation) > 0.5:
            return True
        if self.target06_id != self.current_target06_id:
            return True
        if self.ship_target_id != self.current_ship_target_id:
            return True
        if self.air01_id != self.current_air01_id:
            return True
        if self.air02_id != self.current_air02_id:
            return True
        if self.heli_id != self.current_heli_id:
            return True
        if self.power_shift_checkbox.isChecked() != self.power_shift_active:
            return True
        if self.power_shift_checkbox.isChecked() and (
            self.horse_powers_spinbox.value() != self.current_horse_powers
            or self.max_rpm_spinbox.value() != self.current_max_rpm
            or self.mass_spinbox.value() != self.current_mass
        ):
            return True
        if self.rapid_fire_checkbox.isChecked() != self.rapid_fire_active:
            return True
        if abs(self.rapid_fire_spinbox.value() - self.rapid_fire_time) > 0.001:
            return True
        current_mode = ("ground"   if self.wo_ground_radio.isChecked()   else
                        "naval"    if self.wo_naval_radio.isChecked()    else
                        "aircraft" if self.wo_aircraft_radio.isChecked() else "none")
        if current_mode != self.weapon_override_mode:
            return True
        if current_mode == "ground" and (
            self.weapon_override_donor_id != self.weapon_override_current_donor_id
            or (self.weapon_override_combo.currentData() or "") != self.weapon_override_current_weapon_blk
        ):
            return True
        if current_mode == "naval" and (
            self.naval_weapon_override_donor_id != self.naval_weapon_override_current_donor_id
            or (self.naval_weapon_override_combo.currentData() or "") != self.naval_weapon_override_current_weapon_blk
        ):
            return True
        if current_mode == "aircraft" and (
            self.aircraft_weapon_override_donor_id != self.aircraft_weapon_override_current_donor_id
            or (self.aircraft_weapon_override_combo.currentData() or "") != self.aircraft_weapon_override_current_weapon_blk
        ):
            return True
        if hasattr(self, 'velocity_override_checkbox') and current_mode != "none":
            if self.velocity_override_checkbox.isChecked() != self.velocity_override_active:
                return True
            if self.velocity_override_checkbox.isChecked() and self.velocity_spinbox.value() != self.current_velocity_speed:
                return True
            if self.caliber_override_checkbox.isChecked() != self.caliber_override_active:
                return True
            if self.caliber_override_checkbox.isChecked() and abs(self.caliber_spinbox.value() - self.current_caliber) > 0.001:
                return True
        for i, (combo, spin) in enumerate(zip(self.ammo_slot_combos, self.ammo_slot_spinboxes)):
            t = combo.currentData() or combo.currentText()
            b = "" if t in ("-- None --", "No ammo data", "Stock") else t
            if b != (self.current_bullets[i] if i < len(self.current_bullets) else ""):
                return True
            if combo.isEnabled() and b:
                if spin.value() != (self.current_counts[i] if i < len(self.current_counts) else 0):
                    return True
        return False

    def apply_changes(self):
        """
        Write all pending ground changes to the mission and vehicle .blk files.

        Write order:
          1. us_m2a4.blk  — include line updated to chosen vehicle
          2. You block    — weapons:t= and bullets0:t= updated
          3. AI_Shooting_01-04 — unit_class and weapons updated to match player
          4. Target_03/04/05   — unit_class updated
          5. Target_Air_01/02  — unit_class updated
          6. Heli_Target       — unit_class updated
          7. environment:t= and weather:t= updated in mission header
        """
        if not self.test_drive_file or not os.path.exists(self.test_drive_file):
            QMessageBox.critical(self, "Error", "Ground test drive file not found.")
            return

        if not self._has_changes():
            QMessageBox.information(self, "No Changes", "Nothing has been changed.")
            return

        try:
            with open(self.test_drive_file, 'r', encoding='utf-8') as f:
                content = f.read()

            if self.Selected_Vehicle_ID:
                weapons_default = next(
                    (t.get("weapons_default") for t in self.tank_data if t["ID"] == self.Selected_Vehicle_ID), None
                )
                if not weapons_default:
                    QMessageBox.critical(self, "Error", f"No weapons_default found for: {self.Selected_Vehicle_ID}")
                    return

                with open(self.test_drive_vehicle_file, 'r', encoding='utf-8') as f:
                    vf_content = f.readlines()
                if vf_content and vf_content[0].startswith('include "#/develop/gameBase/gameData/units/tankModels/'):
                    vf_content[0] = f'include "#/develop/gameBase/gameData/units/tankModels/{self.Selected_Vehicle_ID}.blk"\n'
                    with open(self.test_drive_vehicle_file, 'w', encoding='utf-8') as f:
                        f.writelines(vf_content)
                else:
                    QMessageBox.critical(self, "Error", "Ground vehicle file does not have the expected format.")
                    return

                slot_bullets, slot_counts = [], []
                for combo, spin in zip(self.ammo_slot_combos, self.ammo_slot_spinboxes):
                    t = combo.currentData() or combo.currentText()
                    if t == "Stock":
                        slot_bullets.append("")
                        slot_counts.append(spin.value())  # 9999 alone, pool-limited when mixed
                    elif t in ("-- None --", "No ammo data", ""):
                        slot_bullets.append("")
                        slot_counts.append(0)
                    else:
                        slot_bullets.append(t)
                        slot_counts.append(spin.value())
                # If no ammo selected at all, write 9999 for count0 (no-ammo fallback)
                if not any(slot_bullets):
                    slot_counts[0] = 9999
                selected_loadout = {"bullets": slot_bullets, "counts": slot_counts}

                content = self.update_vehicle_in_content(content, "You", self.Selected_Vehicle_ID, weapons_default, None, selected_loadout)
                for i in range(1, 5):
                    content = self.update_vehicle_in_content(content, f"AI_Shooting_0{i}", self.Selected_Vehicle_ID, weapons_default)

            for block_name, id_attr in [
                ("Target_03",     "target03_id"),    ("Target_04",     "target04_id"),    ("Target_05",  "target05_id"),
                ("Target_06",     "target06_id"),
                ("Target_Air_01", "air01_id"),        ("Target_Air_02", "air02_id"),        ("Heli_Target","heli_id"),
            ]:
                vid = getattr(self, id_attr)
                if vid:
                    content = self._update_field_in_block(content, block_name, "unit_class:t=", vid)
                    content = self._update_field_in_block(content, block_name, "weapons:t=", f"{vid}_default")
            if self.ship_target_id:
                content = self._update_field_in_block(content, "Ship_Target", "unit_class:t=", self.ship_target_id)
                content = self._update_field_in_block(content, "Ship_Target", "weapons:t=", f"{self.ship_target_id}_default")

            content = self._update_tm_rotation(content, "Target_03", self.target03_dial.value())
            content = self._update_tm_rotation(content, "Target_04", self.target04_dial.value())
            content = self._update_tm_rotation(content, "Target_05", self.target05_dial.value())

            content = self.update_top_level_value(content, "environment:t=", self.time_combo.currentText())
            content = self.update_top_level_value(content, "weather:t=", self.weather_combo.currentText())

            # Update Rapid Fire trigger block
            rf_pos = content.find('"Experimental Rapid Fire"')
            if rf_pos != -1:
                rf_end = content.find("mission_objectives{", rf_pos)
                if rf_end == -1:
                    rf_end = len(content)
                en_pos = content.find("is_enabled:b=", rf_pos, rf_end)
                if en_pos != -1:
                    en_line_end = content.find("\n", en_pos)
                    enabled_str = "yes" if self.rapid_fire_checkbox.isChecked() else "no"
                    content = content[:en_pos] + f"is_enabled:b={enabled_str}" + content[en_line_end:]
                    # Recompute rf_end after length change
                    rf_end = content.find("mission_objectives{", rf_pos)
                    if rf_end == -1:
                        rf_end = len(content)
                periodic_pos = content.find("periodicEvent{", rf_pos, rf_end)
                if periodic_pos != -1:
                    t_pos = content.find("time:r=", periodic_pos, rf_end)
                    if t_pos != -1:
                        t_end = content.find("\n", t_pos)
                        content = content[:t_pos] + f"time:r={self.rapid_fire_spinbox.value()}" + content[t_end:]

            with open(self.test_drive_file, 'w', encoding='utf-8') as f:
                f.write(content)

            # Write or remove power shift overrides in vehicle file
            ps_checked = self.power_shift_checkbox.isChecked()
            new_hp      = self.horse_powers_spinbox.value()
            new_max_rpm = self.max_rpm_spinbox.value()
            new_mass    = self.mass_spinbox.value()
            ps_changed = (
                ps_checked != self.power_shift_active
                or (ps_checked and (
                    new_hp != self.current_horse_powers
                    or new_max_rpm != self.current_max_rpm
                    or new_mass != self.current_mass
                ))
            )
            if ps_changed:
                with open(self.test_drive_vehicle_file, 'r', encoding='utf-8') as f:
                    vf_lines = f.readlines()
                _ps_keys = ('@override:Mass', '@override:horsePowers', '@override:maxRPM', '@override:minRPM')
                cleaned = [l for l in vf_lines if not any(k in l for k in _ps_keys)]
                # Strip accumulated blank lines before the comment block to prevent stacking
                first_comment = next(
                    (i for i, l in enumerate(cleaned) if l.lstrip().startswith('//')),
                    len(cleaned)
                )
                content = [l for l in cleaned[1:first_comment] if l.strip()]
                if ps_checked:
                    ps_lines = [
                        f'"@override:VehiclePhys" {{ "@override:Mass" {{ "@override:Empty":r={new_mass}}}}}\n',
                        f'"@override:VehiclePhys" {{ "@override:engine" {{ "@override:horsePowers":r={new_hp}}}}}\n',
                        f'"@override:VehiclePhys" {{ "@override:engine" {{ "@override:maxRPM":r={new_max_rpm}}}}}\n',
                        '"@override:VehiclePhys" { "@override:engine" { "@override:minRPM":r=3000}}\n',
                    ]
                    cleaned = [cleaned[0]] + content + cleaned[first_comment:]
                    cleaned = cleaned[:1] + ['\n'] + ps_lines + ['\n'] + cleaned[1:]
                else:
                    if content:
                        cleaned = [cleaned[0]] + ['\n'] + content + ['\n'] + cleaned[first_comment:]
                    else:
                        cleaned = [cleaned[0]] + ['\n'] + cleaned[first_comment:]
                with open(self.test_drive_vehicle_file, 'w', encoding='utf-8') as f:
                    f.writelines(cleaned)
                self.current_horse_powers = new_hp if ps_checked else self.current_horse_powers
                self.current_max_rpm      = new_max_rpm if ps_checked else self.current_max_rpm
                self.current_mass         = new_mass if ps_checked else self.current_mass
                self.power_shift_active   = ps_checked

            # Weapon override
            new_mode  = ("ground"   if self.wo_ground_radio.isChecked()   else
                         "naval"    if self.wo_naval_radio.isChecked()    else
                         "aircraft" if self.wo_aircraft_radio.isChecked() else "none")
            wo_donor  = self.weapon_override_donor_id or self.weapon_override_current_donor_id
            wo_weapon = self.weapon_override_combo.currentData() or self.weapon_override_current_weapon_blk
            nw_donor  = self.naval_weapon_override_donor_id or self.naval_weapon_override_current_donor_id
            nw_weapon = self.naval_weapon_override_combo.currentData() or self.naval_weapon_override_current_weapon_blk
            aw_donor  = self.aircraft_weapon_override_donor_id or self.aircraft_weapon_override_current_donor_id
            aw_weapon = self.aircraft_weapon_override_combo.currentData() or self.aircraft_weapon_override_current_weapon_blk
            active_donor  = wo_donor if new_mode == "ground" else nw_donor if new_mode == "naval" else aw_donor if new_mode == "aircraft" else ""
            active_weapon = wo_weapon if new_mode == "ground" else nw_weapon if new_mode == "naval" else aw_weapon if new_mode == "aircraft" else ""
            donor_path = (f"gameData/units/tankmodels/{active_donor}.blk" if new_mode == "ground"
                          else f"gameData/units/ships/{active_donor}.blk" if new_mode == "naval"
                          else f"gamedata/flightmodels/{active_donor}.blk" if new_mode == "aircraft" else "")
            velocity_enabled = (
                hasattr(self, 'velocity_override_checkbox') and
                self.velocity_override_checkbox.isChecked() and
                new_mode != "none"
            )
            caliber_enabled = (
                hasattr(self, 'caliber_override_checkbox') and
                self.caliber_override_checkbox.isChecked() and
                new_mode != "none"
            )
            new_velocity_speed = self.velocity_spinbox.value() if hasattr(self, 'velocity_spinbox') else 2000
            new_caliber = self.caliber_spinbox.value() if hasattr(self, 'caliber_spinbox') else 0.12
            wo_changed = new_mode != self.weapon_override_mode or (
                new_mode == "ground"   and (wo_donor != self.weapon_override_current_donor_id or wo_weapon != self.weapon_override_current_weapon_blk)
            ) or (
                new_mode == "naval"    and (nw_donor != self.naval_weapon_override_current_donor_id or nw_weapon != self.naval_weapon_override_current_weapon_blk)
            ) or (
                new_mode == "aircraft" and (aw_donor != self.aircraft_weapon_override_current_donor_id or aw_weapon != self.aircraft_weapon_override_current_weapon_blk)
            ) or (
                new_mode != "none" and (
                    velocity_enabled != self.velocity_override_active or
                    (velocity_enabled and new_velocity_speed != self.current_velocity_speed) or
                    caliber_enabled != self.caliber_override_active or
                    (caliber_enabled and abs(new_caliber - self.current_caliber) > 0.001)
                )
            )
            if wo_changed:
                with open(self.test_drive_vehicle_file, 'r', encoding='utf-8') as f:
                    vf_lines = f.readlines()
                cleaned = []
                depth = 0
                in_block = False
                for line in vf_lines:
                    if not in_block:
                        if '"@override:weapon_presets"' in line or '"@override:commonWeapons"' in line:
                            in_block = True
                            depth = line.count('{') - line.count('}')
                            if depth <= 0:
                                in_block = False
                            continue
                        cleaned.append(line)
                    else:
                        depth += line.count('{') - line.count('}')
                        if depth <= 0:
                            in_block = False
                first_comment = next(
                    (i for i, l in enumerate(cleaned) if l.lstrip().startswith('//')),
                    len(cleaned)
                )
                cleaned = [cleaned[0]] + [l for l in cleaned[1:first_comment] if l.strip()] + ['\n'] + cleaned[first_comment:]
                if new_mode != "none" and active_donor and active_weapon:
                    # Velocity/caliber override: update Ask3ladBigWeaponSir.blk and redirect commonWeapons to it
                    if velocity_enabled or caliber_enabled:
                        include_path = active_weapon.replace('\\', '/')
                        if include_path.lower().startswith('gamedata/'):
                            include_path = 'gamedata/' + include_path[9:]
                        elif include_path.startswith('gameData/'):
                            include_path = 'gamedata/' + include_path[9:]
                        vo_blk_path = os.path.join(
                            self._wt_dir, 'content', 'pkg_local',
                            'gameData', 'weapons', 'ask3lad', 'Ask3ladBigWeaponSir.blk'
                        )
                        s = new_velocity_speed
                        c = new_caliber
                        vo_content = f'include "#/develop/gameBase/{include_path}"\n'
                        if velocity_enabled:
                            vo_content += (
                                f'\n'
                                f'//Regular Ammo Override\n'
                                f'"@override:bullet" {{ "@override:speed":r={s}}}\n'
                                f'\n'
                                f'//Rocket Override (SturmTiger)\n'
                                f'"@override:bullet" {{ "@override:rocket" {{ "@override:startSpeed":r={s}}}}}\n'
                                f'"@override:bullet" {{ "@override:rocket" {{ "@override:maxSpeed":r={s}}}}}\n'
                                f'"@override:bullet" {{ "@override:rocket" {{ "@override:endSpeed":r={s}}}}}\n'
                                f'\n'
                                f'//Rocket Override (RBT-5)\n'
                                f'"@override:rocket" {{ "@override:startSpeed":r={s}}}\n'
                                f'"@override:rocket" {{ "@override:maxSpeed":r={s}}}\n'
                                f'"@override:rocket" {{ "@override:endSpeed":r={s}}}\n'
                            )
                        if caliber_enabled:
                            vo_content += (
                                f'\n'
                                f'//Caliber Override\n'
                                f'"@override:bullet" {{ "@override:caliber":r={c}}}\n'
                            )
                        with open(vo_blk_path, 'w', encoding='utf-8') as f:
                            f.write(vo_content)
                        effective_weapon = 'gameData/weapons/ask3lad/Ask3ladBigWeaponSir.blk'
                        self.velocity_override_active = velocity_enabled
                        self.current_velocity_speed = s
                        self.caliber_override_active = caliber_enabled
                        self.current_caliber = c
                    else:
                        effective_weapon = active_weapon
                        self.velocity_override_active = False
                        self.caliber_override_active = False
                    wo_lines = [
                        f'"@override:weapon_presets" {{ "@override:preset[1]" {{ "@override:name":t = "{self.Current_Vehicle_ID}_default"}}}}\n',
                        f'"@override:weapon_presets" {{ "@override:preset[1]" {{ "@override:blk":t = "{donor_path}"}}}}\n',
                        '\n',
                        f'"@override:commonWeapons" {{ "@override:Weapon[1]" {{ "@override:trigger":t = "gunner0"}}}}\n',
                        f'"@override:commonWeapons" {{ "@override:Weapon[1]" {{ "@override:blk":t = "{effective_weapon}"}}}}\n',
                        '\n',
                    ]
                    cleaned = cleaned[:1] + ['\n'] + wo_lines + cleaned[1:]
                with open(self.test_drive_vehicle_file, 'w', encoding='utf-8') as f:
                    f.writelines(cleaned)
                if new_mode == "ground":
                    self.weapon_override_current_donor_id   = active_donor
                    self.weapon_override_current_weapon_blk = active_weapon
                elif new_mode == "naval":
                    self.naval_weapon_override_current_donor_id   = active_donor
                    self.naval_weapon_override_current_weapon_blk = active_weapon
                elif new_mode == "aircraft":
                    self.aircraft_weapon_override_current_donor_id   = active_donor
                    self.aircraft_weapon_override_current_weapon_blk = active_weapon
                else:
                    self.weapon_override_current_donor_id             = ""
                    self.weapon_override_current_weapon_blk           = ""
                    self.naval_weapon_override_current_donor_id       = ""
                    self.naval_weapon_override_current_weapon_blk     = ""
                    self.aircraft_weapon_override_current_donor_id    = ""
                    self.aircraft_weapon_override_current_weapon_blk  = ""
                    self.velocity_override_active = False
                    self.caliber_override_active = False
                self.weapon_override_mode = new_mode

            if self.Selected_Vehicle_ID:
                self.Current_Vehicle_ID = self.Selected_Vehicle_ID
                self.current_name_label.setText(next((t["name"] for t in self.tank_data if t["ID"] == self.Current_Vehicle_ID), self.Current_Vehicle_ID))
                self.load_image(self.Current_Vehicle_ID, self.current_image_label)
                self._ground_add_recently_used(self.Current_Vehicle_ID)
                # Update @override:name if weapon override is active
                if self.weapon_override_mode != "none" and os.path.exists(self.test_drive_vehicle_file):
                    try:
                        with open(self.test_drive_vehicle_file, 'r', encoding='utf-8') as f:
                            vf_content = f.read()
                        if '"@override:name"' in vf_content:
                            old_start = vf_content.find('"@override:name":t = "')
                            if old_start != -1:
                                val_start = old_start + len('"@override:name":t = "')
                                val_end = vf_content.find('"', val_start)
                                vf_content = vf_content[:val_start] + f"{self.Current_Vehicle_ID}_default" + vf_content[val_end:]
                            with open(self.test_drive_vehicle_file, 'w', encoding='utf-8') as f:
                                f.write(vf_content)
                    except Exception:
                        pass

            self.current_environment = self.time_combo.currentText()
            self.current_weather     = self.weather_combo.currentText()
            self.current_target03_id       = self.target03_id
            self.current_target03_rotation = float(self.target03_dial.value())
            self.current_target04_id       = self.target04_id
            self.current_target04_rotation = float(self.target04_dial.value())
            self.current_target05_id       = self.target05_id
            self.current_target05_rotation = float(self.target05_dial.value())
            self.current_target06_id       = self.target06_id
            self.current_ship_target_id    = self.ship_target_id
            self.current_air01_id       = self.air01_id
            self.current_air02_id       = self.air02_id
            self.current_heli_id        = self.heli_id
            if self.Selected_Vehicle_ID:
                self.current_bullets = slot_bullets
                self.current_counts  = slot_counts

            self.rapid_fire_active = self.rapid_fire_checkbox.isChecked()
            self.rapid_fire_time   = self.rapid_fire_spinbox.value()

            QMessageBox.information(self, "Success", "Ground changes applied successfully.")

        except Exception as e:
            QMessageBox.critical(self, "Error", f"Error updating ground files: {str(e)}")

    # ── Naval: Apply Changes ──────────────────────────────────────────────────

    def _has_naval_changes(self):
        """Return True if any naval setting differs from what is in the mission files."""
        if self.naval_selected_vehicle_id and self.naval_selected_vehicle_id != self.naval_current_vehicle_id:
            return True
        if self.naval_time_combo.currentText() != (self.naval_current_environment or ""):
            return True
        if self.naval_weather_combo.currentText() != (self.naval_current_weather or ""):
            return True
        if self.naval_target01_id != self.naval_current_target01_id:
            return True
        if self.naval_target02_id != self.naval_current_target02_id:
            return True
        if self.naval_target03_id != self.naval_current_target03_id:
            return True
        if self.naval_target04_id != self.naval_current_target04_id:
            return True
        if self.naval_air01_id != self.naval_current_air01_id:
            return True
        if self.naval_air02_id != self.naval_current_air02_id:
            return True
        if self.naval_cas_weapons_combo.isEnabled() and self.naval_cas_weapons_combo.currentText() != (self.naval_current_air01_weapons or ""):
            return True
        if self.naval_bomber_weapons_combo.isEnabled() and self.naval_bomber_weapons_combo.currentText() != (self.naval_current_air02_weapons or ""):
            return True
        if self.naval_war_mode_checkbox.isChecked() != self.naval_war_mode_active:
            return True
        if self.naval_war_mode_checkbox.isChecked() and (
            self.naval_cas_count_spinbox.value() != self.naval_war_mode_cas_count
            or self.naval_bomber_count_spinbox.value() != self.naval_war_mode_bomber_count
        ):
            return True
        if self.naval_rapid_fire_checkbox.isChecked() != self.naval_rapid_fire_active:
            return True
        if abs(self.naval_rapid_fire_spinbox.value() - self.naval_rapid_fire_time) > 0.001:
            return True
        for i in range(8):
            if self.naval_shooter_checkboxes[i].isChecked() == self.naval_shooter_current_disabled[i]:
                return True
            new_id = self.naval_shooter_ids[i] or self.naval_shooter_current_ids[i]
            if new_id != self.naval_shooter_current_ids[i]:
                return True
        return False

    def apply_naval_changes(self):
        """
        Write all pending naval changes to the mission and vehicle .blk files.

        Write order:
          1. us_pt6.blk    — include line updated to chosen ship
          2. You_Naval block — weapons:t= updated; bullets0 set to selected ammo
                               or cleared; bullets1-3 always cleared to prevent
                               stale ammo from a previous ship causing a crash
          3. Target_01/02/03 — unit_class updated (static ship targets)
          4. Target_04       — unit_class updated (moving ship target)
          5. Air_Target_01   — unit_class and weapons:t= updated (CAS)
          6. Air_Target_02   — unit_class and weapons:t= updated (Bomber)
          7. environment:t= and weather:t= updated in mission header

        Ship_01–08 (the AI shooter ships in the background) are never modified.
        """
        if not self.naval_mission_file or not os.path.exists(self.naval_mission_file):
            QMessageBox.critical(self, "Error", "Naval mission file not found.")
            return

        if not self._has_naval_changes():
            QMessageBox.information(self, "No Changes", "Nothing has been changed.")
            return

        try:
            with open(self.naval_mission_file, 'r', encoding='utf-8') as f:
                content = f.read()

            if self.naval_selected_vehicle_id:
                weapons_default = next(
                    (s.get("weapons_default") for s in self.ship_data if s["ID"] == self.naval_selected_vehicle_id), None
                )
                if not weapons_default:
                    QMessageBox.critical(self, "Error", f"No weapons_default found for: {self.naval_selected_vehicle_id}")
                    return

                with open(self.naval_vehicle_file, 'r', encoding='utf-8') as f:
                    vf_content = f.readlines()
                if vf_content and vf_content[0].startswith('include "#/develop/gameBase/gameData/units/ships/'):
                    vf_content[0] = f'include "#/develop/gameBase/gameData/units/ships/{self.naval_selected_vehicle_id}.blk"\n'
                    with open(self.naval_vehicle_file, 'w', encoding='utf-8') as f:
                        f.writelines(vf_content)
                else:
                    QMessageBox.critical(self, "Error", "Naval vehicle file does not have the expected format.")
                    return

                # Build per-caliber ammo selections (bullets0 = largest cal, etc.)
                # Ships with no ammo data have empty naval_ammo_combos — slots stay "".
                ammo_slots = ["", "", "", ""]
                for i, (_, combo) in enumerate(self.naval_ammo_combos[:4]):
                    # Use itemData (the raw ammo ID); fall back to text if not set
                    data = combo.currentData()
                    ammo_slots[i] = data if data is not None else combo.currentText()

                you_start = content.find('name:t="You_Naval"')
                if you_start != -1:
                    block_end = content.find("}", you_start)
                    block = content[you_start:block_end]

                    w_start = block.find("weapons:t=")
                    if w_start != -1:
                        w_end = block.find("\n", w_start)
                        block = block.replace(block[w_start:w_end], f'weapons:t="{weapons_default}"')

                    # Write one ammo type per slot; clear unused slots.
                    # bulletsCount0-3 all stay 9999 — naval ammo is always unlimited.
                    for bullet_key, ammo_val in zip(
                        ("bullets0:t=", "bullets1:t=", "bullets2:t=", "bullets3:t="),
                        ammo_slots,
                    ):
                        b_start = block.find(bullet_key)
                        if b_start != -1:
                            b_end = block.find("\n", b_start)
                            block = block.replace(block[b_start:b_end], f'{bullet_key}"{ammo_val}"')
                    for count_key in ("bulletsCount0:i=", "bulletsCount1:i=", "bulletsCount2:i=", "bulletsCount3:i="):
                        bc_start = block.find(count_key)
                        if bc_start != -1:
                            bc_end = block.find("\n", bc_start)
                            block = block.replace(block[bc_start:bc_end], f"{count_key}9999")

                    content = content[:you_start] + block + content[block_end:]

            for block_name, id_attr in [
                ("Target_01", "naval_target01_id"), ("Target_02", "naval_target02_id"),
                ("Target_03", "naval_target03_id"), ("Target_04", "naval_target04_id"),
            ]:
                vid = getattr(self, id_attr)
                if vid:
                    content = self._update_field_in_block(content, block_name, "unit_class:t=", vid)
                    content = self._update_field_in_block(content, block_name, "weapons:t=", f"{vid}_default")
                    for bullet in ("bullets0:t=", "bullets1:t=", "bullets2:t=", "bullets3:t="):
                        content = self._update_field_in_block(content, block_name, bullet, "")

            if self.naval_air01_id:
                content = self._update_field_in_block(content, "Air_Target_01", "unit_class:t=", self.naval_air01_id)
                if self.naval_cas_weapons_combo.isEnabled():
                    selected_cas_weapons = self.naval_cas_weapons_combo.currentText()
                    if selected_cas_weapons:
                        content = self._update_field_in_block(content, "Air_Target_01", "weapons:t=", selected_cas_weapons)
            if self.naval_air02_id:
                content = self._update_field_in_block(content, "Air_Target_02", "unit_class:t=", self.naval_air02_id)
                if self.naval_bomber_weapons_combo.isEnabled():
                    selected_weapons = self.naval_bomber_weapons_combo.currentText()
                    if selected_weapons:
                        content = self._update_field_in_block(content, "Air_Target_02", "weapons:t=", selected_weapons)

            content = self.update_top_level_value(content, "environment:t=", self.naval_time_combo.currentText())
            content = self.update_top_level_value(content, "weather:t=", self.naval_weather_combo.currentText())

            # War Mode — flip Shoot Target / Shoot You
            war_on = self.naval_war_mode_checkbox.isChecked()
            for block_name, enabled in (
                ('"Shoot Target"', not war_on),
                ('"Shoot You"',    war_on),
            ):
                pos = content.find(block_name)
                if pos != -1:
                    en_pos = content.find("is_enabled:b=", pos)
                    if en_pos != -1:
                        en_end = content.find("\n", en_pos)
                        content = content[:en_pos] + ("is_enabled:b=yes" if enabled else "is_enabled:b=no") + content[en_end:]

            # War Mode — update Air_Target counts
            cas_count    = self.naval_cas_count_spinbox.value()    if war_on else 8
            bomber_count = self.naval_bomber_count_spinbox.value() if war_on else 27
            for arm_name, new_count in (("Air_Target_01", cas_count), ("Air_Target_02", bomber_count)):
                arm_pos = content.find(f'name:t="{arm_name}"')
                if arm_pos != -1:
                    props_pos = content.find("props{", arm_pos)
                    if props_pos != -1:
                        props_end = content.find("}", props_pos)
                        count_pos = content.find("count:i=", props_pos, props_end)
                        if count_pos != -1:
                            count_end = content.find("\n", count_pos)
                            content = content[:count_pos] + f"count:i={new_count}" + content[count_end:]

            # Shooter ships — update unit_class and weapons if changed via picker
            for i in range(8):
                new_id = self.naval_shooter_ids[i] or self.naval_shooter_current_ids[i]
                if new_id != self.naval_shooter_current_ids[i]:
                    ship_name = f"Ship_0{i + 1}"
                    content = self._update_field_in_block(content, ship_name, "unit_class:t=", new_id)
                    content = self._update_field_in_block(content, ship_name, "weapons:t=", f"{new_id}_default")

            # Rewrite unitPutToSleep targets in "Disable Ship" trigger
            disable_pos = content.find('"Disable Ship"')
            if disable_pos != -1:
                put_sleep_pos = content.find("unitPutToSleep{", disable_pos)
                if put_sleep_pos != -1:
                    put_sleep_end = content.find("}", put_sleep_pos)
                    disabled_ships = [f"Ship_0{i + 1}" for i in range(8) if not self.naval_shooter_checkboxes[i].isChecked()]
                    if disabled_ships:
                        targets_str = "\n".join(f'        target:t="{s}"' for s in disabled_ships)
                        new_sleep_block = f"unitPutToSleep{{\n{targets_str}\n      }}"
                    else:
                        new_sleep_block = "unitPutToSleep{}"
                    content = content[:put_sleep_pos] + new_sleep_block + content[put_sleep_end + 1:]

            # Update Rapid Fire trigger block
            rf_pos = content.find('"Experimental Rapid Fire"')
            if rf_pos != -1:
                rf_end = content.find("mission_objectives{", rf_pos)
                if rf_end == -1:
                    rf_end = len(content)
                en_pos = content.find("is_enabled:b=", rf_pos, rf_end)
                if en_pos != -1:
                    en_line_end = content.find("\n", en_pos)
                    enabled_str = "yes" if self.naval_rapid_fire_checkbox.isChecked() else "no"
                    content = content[:en_pos] + f"is_enabled:b={enabled_str}" + content[en_line_end:]
                    rf_end = content.find("mission_objectives{", rf_pos)
                    if rf_end == -1:
                        rf_end = len(content)
                periodic_pos = content.find("periodicEvent{", rf_pos, rf_end)
                if periodic_pos != -1:
                    t_pos = content.find("time:r=", periodic_pos, rf_end)
                    if t_pos != -1:
                        t_end = content.find("\n", t_pos)
                        content = content[:t_pos] + f"time:r={self.naval_rapid_fire_spinbox.value()}" + content[t_end:]

            with open(self.naval_mission_file, 'w', encoding='utf-8') as f:
                f.write(content)

            if self.naval_selected_vehicle_id:
                self.naval_current_vehicle_id = self.naval_selected_vehicle_id
                self.naval_current_name_label.setText(next((s["name"] for s in self.ship_data if s["ID"] == self.naval_current_vehicle_id), self.naval_current_vehicle_id))
                self.load_image(self.naval_current_vehicle_id, self.naval_current_image_label, "Ship_Previews")
                self._naval_add_recently_used(self.naval_current_vehicle_id)

            self.naval_current_environment  = self.naval_time_combo.currentText()
            self.naval_current_weather      = self.naval_weather_combo.currentText()
            self.naval_current_target01_id  = self.naval_target01_id
            self.naval_current_target02_id  = self.naval_target02_id
            self.naval_current_target03_id  = self.naval_target03_id
            self.naval_current_target04_id  = self.naval_target04_id
            self.naval_current_air01_id      = self.naval_air01_id
            self.naval_current_air02_id      = self.naval_air02_id
            self.naval_current_air01_weapons = self.naval_cas_weapons_combo.currentText()   if self.naval_cas_weapons_combo.isEnabled()   else self.naval_current_air01_weapons
            self.naval_current_air02_weapons = self.naval_bomber_weapons_combo.currentText() if self.naval_bomber_weapons_combo.isEnabled() else self.naval_current_air02_weapons
            self.naval_war_mode_active        = self.naval_war_mode_checkbox.isChecked()
            self.naval_war_mode_cas_count     = cas_count
            self.naval_war_mode_bomber_count  = bomber_count
            self.naval_rapid_fire_active      = self.naval_rapid_fire_checkbox.isChecked()
            self.naval_rapid_fire_time        = self.naval_rapid_fire_spinbox.value()
            for i in range(8):
                self.naval_shooter_current_ids[i]      = self.naval_shooter_ids[i] or self.naval_shooter_current_ids[i]
                self.naval_shooter_current_disabled[i] = not self.naval_shooter_checkboxes[i].isChecked()

            QMessageBox.information(self, "Success", "Naval changes applied successfully.")

        except Exception as e:
            QMessageBox.critical(self, "Error", f"Error updating naval files: {str(e)}")

    # ── Shared: .blk Writing Helpers ──────────────────────────────────────────

    def update_vehicle_in_content(self, content, vehicle_name, new_vehicle_id, new_weapons, new_bullets0=None, loadout=None):
        """
        Replace unit_class, weapons, and optionally bullets/counts in a named vehicle block.

        Used by ground apply for the 'You' player block and 'AI_Shooting_01-04'.
        - AI_Shooting blocks: unit_class + weapons updated.
        - You block: weapons + bullets updated (unit_class stays as userVehicles/us_m2a4).
          If loadout is provided, all 4 bullet slots and counts are written from it.
          Otherwise only bullets0 is updated from new_bullets0.

        Naval apply handles You_Naval inline rather than calling this method.
        """
        vehicle_start = content.find(f'name:t="{vehicle_name}"')
        if vehicle_start == -1:
            return content
        block_end = content.find("}", vehicle_start)
        if block_end == -1:
            return content
        vehicle_block = content[vehicle_start:block_end]

        if vehicle_name.startswith("AI_Shooting_"):
            uc_start = vehicle_block.find("unit_class:t=")
            if uc_start != -1:
                uc_end = vehicle_block.find("\n", uc_start)
                vehicle_block = vehicle_block.replace(vehicle_block[uc_start:uc_end], f'unit_class:t="{new_vehicle_id}"')

        w_start = vehicle_block.find("weapons:t=")
        if w_start != -1:
            w_end = vehicle_block.find("\n", w_start)
            vehicle_block = vehicle_block.replace(vehicle_block[w_start:w_end], f'weapons:t="{new_weapons}"')

        if vehicle_name == "You":
            if loadout:
                bullets = loadout.get("bullets", [])
                counts  = loadout.get("counts", [9999, 0, 0, 0])
                for i in range(4):
                    b_key = f"bullets{i}:t="
                    c_key = f"bulletsCount{i}:i="
                    b_val = bullets[i] if i < len(bullets) else ""
                    c_val = counts[i]  if i < len(counts)  else 0
                    for key, new_line in ((b_key, f'{b_key}"{b_val}"'), (c_key, f'{c_key}{c_val}')):
                        s = vehicle_block.find(key)
                        if s != -1:
                            e = vehicle_block.find("\n", s)
                            vehicle_block = vehicle_block.replace(vehicle_block[s:e], new_line)
            elif new_bullets0 is not None:
                b_start = vehicle_block.find("bullets0:t=")
                if b_start != -1:
                    b_end = vehicle_block.find("\n", b_start)
                    vehicle_block = vehicle_block.replace(vehicle_block[b_start:b_end], f'bullets0:t="{new_bullets0}"')
                for i in range(1, 4):
                    for key, reset in ((f"bullets{i}:t=", f'bullets{i}:t=""'), (f"bulletsCount{i}:i=", f"bulletsCount{i}:i=0")):
                        s = vehicle_block.find(key)
                        if s != -1:
                            e = vehicle_block.find("\n", s)
                            vehicle_block = vehicle_block.replace(vehicle_block[s:e], reset)

        return content[:vehicle_start] + vehicle_block + content[block_end:]

    def update_top_level_value(self, content, key, value):
        """
        Replace a top-level key:t= value within the first 30 lines of a .blk file.

        Used for environment:t= and weather:t= which appear near the top of both
        the ground and naval mission files. Searches only the first 30 lines to
        avoid accidentally matching identically named keys inside unit blocks.
        """
        lines = content.splitlines(keepends=True)
        for i, line in enumerate(lines[:30]):
            if line.strip().startswith(key):
                indent = line[:len(line) - len(line.lstrip())]
                lines[i] = f'{indent}{key}"{value}"\n'
                break
        return ''.join(lines)

    # ── Shared: DB Auto-Update ────────────────────────────────────────────────

    def _start_app_update_check(self):
        """Start the background app version check silently on startup."""
        self._app_worker = AppUpdateWorker()
        self._app_worker.update_available.connect(self._on_app_update_available)
        self._app_worker.start()

    def _on_app_update_available(self, remote_version):
        """Show a prompt when a newer app version is detected."""
        msg = QMessageBox(self)
        msg.setWindowTitle("Update Available")
        msg.setIcon(QMessageBox.Icon.Information)
        msg.setText(f"Version {remote_version} of the Test Drive GUI is available.")
        msg.setInformativeText("Head to the Discord to download the latest version.")
        discord_btn = msg.addButton("Open Discord", QMessageBox.ButtonRole.AcceptRole)
        msg.addButton("Later", QMessageBox.ButtonRole.RejectRole)
        msg.exec()
        if msg.clickedButton() == discord_btn:
            self.open_discord()

    def _start_db_update_check(self):
        """Start the background DB update worker silently on startup."""
        self._db_worker = DbUpdateWorker(self.assets_folder, self._local_db_version)
        self._db_worker.update_done.connect(self._on_db_updated)
        self._db_worker.start()

    def check_for_updates(self):
        """Manually trigger a DB and app update check from the File menu."""
        if self._db_worker and self._db_worker.isRunning():
            return
        self._check_db_no_update   = False
        self._check_app_no_update  = False
        self._db_worker = DbUpdateWorker(self.assets_folder, self._local_db_version)
        self._db_worker.update_done.connect(self._on_db_updated)
        self._db_worker.no_update.connect(self._on_manual_db_no_update)
        self._db_worker.start()
        self._app_worker = AppUpdateWorker()
        self._app_worker.update_available.connect(self._on_app_update_available)
        self._app_worker.no_update.connect(self._on_manual_app_no_update)
        self._app_worker.start()

    def _on_db_updated(self, new_version, date):
        """Called on the main thread when updated DB files have been downloaded."""
        self._local_db_version = new_version
        self.update_config(db_version=new_version)
        QMessageBox.information(
            self,
            "Database Updated",
            f"The vehicle database has been updated to version {new_version}.\n"
            f"Last updated: {date}\n\n"
            "Restart the app to load the latest data."
        )

    def _on_manual_db_no_update(self):
        """Called when a manual update check finds the DB is already up to date."""
        self._check_db_no_update = True
        if self._check_db_no_update and self._check_app_no_update:
            QMessageBox.information(self, "Up to Date", "Database and app are both up to date.")

    def _on_manual_app_no_update(self):
        """Called when a manual update check finds the app is already up to date."""
        self._check_app_no_update = True
        if self._check_db_no_update and self._check_app_no_update:
            QMessageBox.information(self, "Up to Date", "Database and app are both up to date.")

    # ── Theme ─────────────────────────────────────────────────────────────────

    def _toggle_dark_mode(self, checked):
        """Toggle dark/light mode and persist the preference."""
        self._dark_mode = checked
        self._dark_mode_action.setText("Dark Mode: ON" if checked else "Dark Mode: OFF")
        _apply_theme(self._dark_mode)
        self._save_saved_lists()

    def _toggle_custom_map(self, checked):
        """Toggle the custom minimap lines in both level .blk files."""
        self._custom_map = checked
        self._custom_map_action.setText("Custom Map: ON" if checked else "Custom Map: OFF")

        map_line1 = r'customLevelMap:t="levels\Ask3lad_Testdrive_map.png"'
        map_line2 = r'customLevelTankMap:t="levels\Ask3lad_Testdrive_map.png"'

        if not hasattr(self, '_wt_dir'):
            return

        level_paths = [
            os.path.join(self._wt_dir, "content", "pkg_local", "levels", "Ask3lad_Testdrive.blk"),
            os.path.join(self._wt_dir, "content", "pkg_local", "levels", "Ask3lad_Testdrive_Naval.blk"),
        ]

        for path in level_paths:
            if not os.path.exists(path):
                continue
            try:
                with open(path, "r", encoding="utf-8") as f:
                    content = f.read()
                if checked:
                    if map_line1 not in content:
                        content = content.replace(
                            "weatherPreset:t=",
                            f"{map_line1}\n{map_line2}\nweatherPreset:t=",
                            1
                        )
                else:
                    content = content.replace(map_line1 + "\n", "")
                    content = content.replace(map_line2 + "\n", "")
                with open(path, "w", encoding="utf-8") as f:
                    f.write(content)
            except Exception as e:
                QMessageBox.warning(self, "Custom Map", f"Could not update {os.path.basename(path)}:\n{e}")

        # Also swap the level in the ground mission blk
        if hasattr(self, 'test_drive_file') and os.path.exists(self.test_drive_file):
            try:
                with open(self.test_drive_file, "r", encoding="utf-8") as f:
                    content = f.read()
                if checked:
                    content = content.replace(
                        'level:t="levels/hangar_field.bin"',
                        'level:t="levels/Ask3lad_Testdrive.bin"'
                    )
                else:
                    content = content.replace(
                        'level:t="levels/Ask3lad_Testdrive.bin"',
                        'level:t="levels/hangar_field.bin"'
                    )
                with open(self.test_drive_file, "w", encoding="utf-8") as f:
                    f.write(content)
            except Exception as e:
                QMessageBox.warning(self, "Custom Map", f"Could not update {os.path.basename(self.test_drive_file)}:\n{e}")

        # Also swap the level in the naval mission blk
        if hasattr(self, 'naval_mission_file') and os.path.exists(self.naval_mission_file):
            try:
                with open(self.naval_mission_file, "r", encoding="utf-8") as f:
                    content = f.read()
                if checked:
                    content = content.replace(
                        'level:t="levels/iwo_jima.bin"',
                        'level:t="levels/Ask3lad_Testdrive_Naval.bin"'
                    )
                else:
                    content = content.replace(
                        'level:t="levels/Ask3lad_Testdrive_Naval.bin"',
                        'level:t="levels/iwo_jima.bin"'
                    )
                with open(self.naval_mission_file, "w", encoding="utf-8") as f:
                    f.write(content)
            except Exception as e:
                QMessageBox.warning(self, "Custom Map", f"Could not update {os.path.basename(self.naval_mission_file)}:\n{e}")

    # ── First-run / Upgrade Messages ──────────────────────────────────────────

    def _show_updated_message(self):
        """Show an upgrade notice when the app version has changed since last run."""
        stored = getattr(self, "_stored_app_version", "")

        # Read notes from Assets/app_version.json if available
        notes = []
        app_ver_path = os.path.join(self.assets_folder, "app_version.json")
        if os.path.exists(app_ver_path):
            try:
                with open(app_ver_path, encoding="utf-8") as f:
                    notes = json.load(f).get("notes", [])
            except Exception:
                pass

        body = f"The Test Drive GUI has been updated from {stored} to {APP_VERSION}."
        if notes:
            body += "\n\nWhat's new:\n" + "\n".join(f"  \u2022 {n}" for n in notes)
        body += "\n\nCheck the Discord for more details."

        msg = QMessageBox(self)
        msg.setWindowTitle(f"Updated to {APP_VERSION}")
        msg.setIcon(QMessageBox.Icon.Information)
        msg.setText(body)
        discord_btn = msg.addButton("Open Discord", QMessageBox.ButtonRole.AcceptRole)
        msg.addButton("OK", QMessageBox.ButtonRole.RejectRole)
        msg.exec()
        if msg.clickedButton() == discord_btn:
            self.open_discord()

    # ── Help Dialogs & Links ──────────────────────────────────────────────────

    def show_debug_info(self):
        """Show a debug info dialog with current file paths and their status."""
        def status(path):
            if not path:
                return "✗  Not set"
            return "✓  Found" if os.path.exists(path) else "✗  Not found"

        files = [
            ("Ground mission",  self.test_drive_file),
            ("Ground vehicle",  self.test_drive_vehicle_file),
            ("Naval mission",   self.naval_mission_file),
            ("Naval vehicle",   self.naval_vehicle_file),
        ]

        try:
            db_ver_path = os.path.join(self.assets_folder, "db_version.json")
            with open(db_ver_path, "r", encoding="utf-8") as f:
                db_ver = json.load(f)
            db_stamp = f"v{db_ver.get('version','?')}  {db_ver.get('date','?')}  {db_ver.get('time','')}".strip()
        except Exception:
            db_stamp = "Unknown"

        wt_dir = os.path.dirname(os.path.dirname(self.test_drive_file)) if self.test_drive_file else None

        lines = ["File Status\n" + "─" * 44]
        for i, (label, path) in enumerate(files):
            entry = f"{label}:\n\n  {status(path)}\n  {path or '(none)'}"
            lines.append(("\n" + entry) if i > 0 else entry)
        lines.append("\n" + "─" * 44)
        lines.append(f"App version:  v{APP_VERSION}")
        lines.append(f"DB version:   {db_stamp}")
        lines.append(f"WT directory: {wt_dir or '(not set)'}")

        QMessageBox.information(self, "Debug Info", "\n".join(lines))

    def _debug_create_log(self):
        """Write a manual debug snapshot to Logs/debug_YYYY-MM-DD_HH-MM-SS.txt and open the folder."""
        try:
            os.makedirs(_LOGS_DIR, exist_ok=True)
            timestamp  = datetime.datetime.now()
            log_path   = os.path.join(_LOGS_DIR, f"debug_{timestamp.strftime('%Y-%m-%d_%H-%M-%S')}.txt")

            def _val(v): return v or "(not set)"
            def _exists(p): return ("✓ Found" if os.path.exists(p) else "✗ Not found") if p else "✗ Not set"

            def _extract_you_block(mission_path, you_name="You"):
                """Extract unit_class and weapons from the named You block in a mission file."""
                if not mission_path or not os.path.exists(mission_path):
                    return "  (file not set or not found)"
                try:
                    with open(mission_path, encoding="utf-8") as f:
                        lines = f.readlines()
                    you_idx = next((i for i, l in enumerate(lines) if f'name:t="{you_name}"' in l), None)
                    if you_idx is None:
                        return f'  (name:t="{you_name}" block not found)'
                    unit_class = weapons = "(not found)"
                    for l in lines[you_idx:you_idx + 15]:
                        if "unit_class" in l:
                            unit_class = l.strip()
                        elif "weapons" in l:
                            weapons = l.strip()
                    return f"  {unit_class}\n  {weapons}"
                except Exception as e:
                    return f"  (Could not read: {e})"

            # DB version
            try:
                with open(os.path.join(self.assets_folder, "db_version.json"), encoding="utf-8") as f:
                    db_ver = json.load(f)
                db_stamp = f"v{db_ver.get('version','?')}  {db_ver.get('date','?')}  {db_ver.get('time','')}".strip()
            except Exception:
                db_stamp = "Unknown"

            # Ammo slots
            ammo_slots = ""
            for i in range(4):
                ammo_slots += f"    Slot {i+1}: {self.current_bullets[i] or '(empty)'}  x{self.current_counts[i]}\n"

            # Naval shooters
            shooter_lines = ""
            ship_labels = ["Ship 1","Ship 2","Ship 3","Ship 4","Ship 5","Ship 6","Carrier 1","Carrier 2"]
            for i in range(8):
                enabled = not self.naval_shooter_current_disabled[i]
                shooter_lines += f"    {ship_labels[i]}: {'Enabled' if enabled else 'Disabled'}  {_val(self.naval_shooter_current_ids[i])}\n"

            # Weapon override blk contents
            big_weapon_blk_path = ""
            big_weapon_blk = ""
            if getattr(self, '_wt_dir', None):
                big_weapon_blk_path = os.path.join(
                    self._wt_dir, 'content', 'pkg_local',
                    'gameData', 'weapons', 'ask3lad', 'Ask3ladBigWeaponSir.blk'
                )
                if os.path.exists(big_weapon_blk_path):
                    try:
                        with open(big_weapon_blk_path, encoding="utf-8") as f:
                            big_weapon_blk = f.read()
                    except Exception as e:
                        big_weapon_blk = f"(Could not read: {e})"
                else:
                    big_weapon_blk = "(not found)"
            else:
                big_weapon_blk = "(WT directory not set)"

            # Ground vehicle blk contents
            ground_blk = ""
            if self.test_drive_vehicle_file and os.path.exists(self.test_drive_vehicle_file):
                try:
                    with open(self.test_drive_vehicle_file, encoding="utf-8") as f:
                        ground_blk = f.read()
                except Exception as e:
                    ground_blk = f"(Could not read: {e})"
            else:
                ground_blk = "(not set or not found)"

            # Naval vehicle blk contents
            naval_blk = ""
            if self.naval_vehicle_file and os.path.exists(self.naval_vehicle_file):
                try:
                    with open(self.naval_vehicle_file, encoding="utf-8") as f:
                        naval_blk = f.read()
                except Exception as e:
                    naval_blk = f"(Could not read: {e})"
            else:
                naval_blk = "(not set or not found)"

            wt_dir = os.path.dirname(os.path.dirname(self.test_drive_file)) if self.test_drive_file else "(not set)"
            mode   = "Ground" if (hasattr(self, "mode_tabs") and self.mode_tabs.currentIndex() == 0) else "Naval"

            report = (
                f"{'=' * 60}\n"
                f"DEBUG LOG\n"
                f"Timestamp:    {timestamp.strftime('%Y-%m-%d %H:%M:%S')}\n"
                f"App version:  v{APP_VERSION}\n"
                f"DB version:   {db_stamp}\n"
                f"Active mode:  {mode}\n"
                f"\n"
                f"--- File Paths ---\n"
                f"WT directory:         {wt_dir}\n"
                f"Ground mission:       {_val(self.test_drive_file)}  [{_exists(self.test_drive_file)}]\n"
                f"Ground vehicle file:  {_val(self.test_drive_vehicle_file)}  [{_exists(self.test_drive_vehicle_file)}]\n"
                f"Naval mission:        {_val(self.naval_mission_file)}  [{_exists(self.naval_mission_file)}]\n"
                f"Naval vehicle file:   {_val(self.naval_vehicle_file)}  [{_exists(self.naval_vehicle_file)}]\n"
                f"Weapon override blk:  {_val(big_weapon_blk_path)}  [{_exists(big_weapon_blk_path)}]\n"
                f"\n"
                f"--- Ground State ---\n"
                f"Vehicle (in mission): {_val(self.Current_Vehicle_ID)}\n"
                f"Vehicle (selected):   {_val(self.Selected_Vehicle_ID)}\n"
                f"Environment:          {_val(self.current_environment)}\n"
                f"Weather:              {_val(self.current_weather)}\n"
                f"Ammo loadout:\n{ammo_slots}"
                f"Target 300m:          {_val(self.current_target03_id)}\n"
                f"Target 600m:          {_val(self.current_target04_id)}\n"
                f"Target 800m:          {_val(self.current_target05_id)}\n"
                f"Moving target:        {_val(self.current_target06_id)}\n"
                f"Naval target:         {_val(self.current_ship_target_id)}\n"
                f"Air 5km:              {_val(self.current_air01_id)}\n"
                f"Air 2.5km:            {_val(self.current_air02_id)}\n"
                f"Helicopter 2km:       {_val(self.current_heli_id)}\n"
                f"Engine override:      {'Enabled' if self.power_shift_active else 'Disabled'}\n"
                f"  Horsepower:         {self.current_horse_powers} HP\n"
                f"  Max RPM:            {self.current_max_rpm}\n"
                f"  Mass:               {self.current_mass} kg\n"
                f"Rapid fire:           {'Enabled' if self.rapid_fire_active else 'Disabled'}  interval={self.rapid_fire_time}s\n"
                f"Weapon override:      {self.weapon_override_mode}\n"
                f"  Donor (ground):     {_val(self.weapon_override_current_donor_id)}\n"
                f"  Weapon (ground):    {_val(self.weapon_override_current_weapon_blk)}\n"
                f"  Donor (naval):      {_val(self.naval_weapon_override_current_donor_id)}\n"
                f"  Weapon (naval):     {_val(self.naval_weapon_override_current_weapon_blk)}\n"
                f"  Donor (aircraft):   {_val(self.aircraft_weapon_override_current_donor_id)}\n"
                f"  Weapon (aircraft):  {_val(self.aircraft_weapon_override_current_weapon_blk)}\n"
                f"\n"
                f"--- Naval State ---\n"
                f"Ship (in mission):    {_val(self.naval_current_vehicle_id)}\n"
                f"Ship (selected):      {_val(self.naval_selected_vehicle_id)}\n"
                f"Environment:          {_val(self.naval_current_environment)}\n"
                f"Weather:              {_val(self.naval_current_weather)}\n"
                f"Target 5km:           {_val(self.naval_current_target01_id)}\n"
                f"Target 10km:          {_val(self.naval_current_target02_id)}\n"
                f"Target 15km:          {_val(self.naval_current_target03_id)}\n"
                f"Moving target:        {_val(self.naval_current_target04_id)}\n"
                f"CAS aircraft:         {_val(self.naval_current_air01_id)}\n"
                f"CAS weapons:          {_val(self.naval_current_air01_weapons)}\n"
                f"Bomber aircraft:      {_val(self.naval_current_air02_id)}\n"
                f"Bomber weapons:       {_val(self.naval_current_air02_weapons)}\n"
                f"War mode:             {'Enabled' if self.naval_war_mode_active else 'Disabled'}\n"
                f"  CAS count:          {self.naval_war_mode_cas_count}\n"
                f"  Bomber count:       {self.naval_war_mode_bomber_count}\n"
                f"Rapid fire:           {'Enabled' if self.naval_rapid_fire_active else 'Disabled'}  interval={self.naval_rapid_fire_time}s\n"
                f"Bombarding Ships:\n{shooter_lines}"
                f"\n"
                f"--- Ground Mission: You Block ---\n"
                f"{_extract_you_block(self.test_drive_file)}\n"
                f"\n"
                f"--- Naval Mission: You Block ---\n"
                f"{_extract_you_block(self.naval_mission_file, 'You_Naval')}\n"
                f"\n"
                f"--- Ground Vehicle File ---\n"
                f"{ground_blk}\n"
                f"--- Naval Vehicle File ---\n"
                f"{naval_blk}\n"
                f"--- Weapon Override File (Ask3ladBigWeaponSir.blk) ---\n"
                f"{big_weapon_blk}\n"
            )

            with open(log_path, "w", encoding="utf-8") as f:
                f.write(report)

            os.startfile(_LOGS_DIR)
            QMessageBox.information(self, "Debug Log Created", f"Log saved to:\n{log_path}")

        except Exception as e:
            QMessageBox.warning(self, "Debug Log", f"Could not create log:\n{e}")

    def _debug_open_ground_vehicle_folder(self):
        """Open the folder containing the ground vehicle .blk file in Explorer."""
        path = self.test_drive_vehicle_file
        if path and os.path.exists(path):
            os.startfile(os.path.dirname(path))
        else:
            QMessageBox.warning(self, "Debug", "Ground vehicle file not set or not found.")

    def _debug_open_weapon_override_folder(self):
        """Open the Ask3ladBigWeaponSir.blk folder in Explorer."""
        if not getattr(self, '_wt_dir', None):
            QMessageBox.warning(self, "Debug", "War Thunder directory not set.")
            return
        path = os.path.join(self._wt_dir, 'content', 'pkg_local', 'gameData', 'weapons', 'ask3lad')
        if os.path.exists(path):
            os.startfile(path)
        else:
            QMessageBox.warning(self, "Debug", f"Weapon override folder not found:\n{path}")

    def _debug_open_usermissions_folder(self):
        """Open the UserMissions/Ask3lad folder in Explorer."""
        path = self.test_drive_file
        if path and os.path.exists(path):
            os.startfile(os.path.dirname(path))
        else:
            QMessageBox.warning(self, "Debug", "UserMissions folder not set or not found.")

    def show_about(self):
        """Show the About / Credits dialog."""
        dialog = QDialog(self)
        dialog.setWindowTitle("About")
        dialog.setMinimumWidth(340)
        dialog.setMaximumWidth(340)

        layout = QVBoxLayout(dialog)
        layout.setSpacing(8)
        layout.setContentsMargins(20, 20, 20, 20)

        title = QLabel("Ask3lad War Thunder Test Drive GUI")
        title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        font = title.font()
        font.setBold(True)
        font.setPointSize(11)
        title.setFont(font)
        layout.addWidget(title)

        version = QLabel("Version 2.4")
        version.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(version)

        layout.addSpacing(6)

        desc = QLabel(
            "A custom mission configuration tool for the\n"
            "Ask3lad War Thunder Test Drive.\n\n"
            "Swap vehicles, select ammo, set targets,\n"
            "choose weapons loadouts, and change the environment\n"
            "for both ground and naval user missions."
        )
        desc.setAlignment(Qt.AlignmentFlag.AlignCenter)
        desc.setWordWrap(True)
        layout.addWidget(desc)

        layout.addSpacing(6)

        made_by = QLabel("Created by <b>Ask3lad</b>")
        made_by.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(made_by)

        layout.addSpacing(10)

        close_btn = QPushButton("Close")
        close_btn.clicked.connect(dialog.accept)
        layout.addWidget(close_btn)

        dialog.exec()

    def show_how_to_use(self):
        """Show the How to Use guide dialog."""
        dialog = QDialog(self)
        dialog.setWindowTitle("How to Use")
        dialog.setMinimumWidth(380)
        dialog.setMaximumWidth(380)

        layout = QVBoxLayout(dialog)
        layout.setSpacing(8)
        layout.setContentsMargins(20, 20, 20, 20)

        title = QLabel("How to Use")
        title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        font = title.font()
        font.setBold(True)
        font.setPointSize(11)
        title.setFont(font)
        layout.addWidget(title)

        layout.addSpacing(6)

        steps = QLabel(
            "1.  Go to File → Locate War Thunder Directory\n"
            "    and select your War Thunder installation folder.\n\n"
            "2.  Select the Ground or Naval tab at the top\n"
            "    depending on which mission you want to configure.\n\n"
            "3.  Browse the vehicle list and click a vehicle\n"
            "    to select it. Use the search bar, role filter,\n"
            "    and country buttons to narrow the list down.\n\n"
            "4.  Select your ammo from the Ammo Selection combo\n"
            "    if available.\n\n"
            "5.  Switch to the other tabs to change targets,\n"
            "    weapons loadouts, time of day, and weather.\n\n"
            "6.  Click Apply Changes when ready.\n\n"
            "7.  Launch the mission in War Thunder."
        )
        steps.setWordWrap(True)
        layout.addWidget(steps)

        layout.addSpacing(6)
        close_btn = QPushButton("Close")
        close_btn.clicked.connect(dialog.accept)
        layout.addWidget(close_btn)

        dialog.exec()

    def show_credits(self):
        """Show the Credits dialog."""
        dialog = QDialog(self)
        dialog.setWindowTitle("Credits")
        dialog.setMinimumWidth(340)
        dialog.setMaximumWidth(340)

        layout = QVBoxLayout(dialog)
        layout.setSpacing(8)
        layout.setContentsMargins(20, 20, 20, 20)

        title = QLabel("Credits")
        title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        font = title.font()
        font.setBold(True)
        font.setPointSize(11)
        title.setFont(font)
        layout.addWidget(title)

        layout.addSpacing(6)

        body = QLabel(
            "  Developer\n"
            "  • Ask3lad\n\n"
            "  Special Thanks\n"
            "  • Avarik\n"
            "  • TheUnsocialEngineer\n"
            "  • Gszabi99\n"
            "  • One Tap Eoka\n"
            "  • IForgotMyName\n"
            "  • Lensterboi\n"
            "  • TheGreenlandicGamer\n"
            "  • Lionstripes\n"
            "  • Hurin170\n"
            "  • DeeVEK\n"
            "  • Pyrenees General\n"
            "  • Bebbsy40\n"
            "  • Kmanb\n"
            "  • Axen\n"
            "  • Timber0\n"
        )
        body.setWordWrap(True)
        layout.addWidget(body)

        layout.addSpacing(6)
        close_btn = QPushButton("Close")
        close_btn.clicked.connect(dialog.accept)
        layout.addWidget(close_btn)

        dialog.exec()

    def show_decals(self):
        """Show the Grab our Decals dialog."""
        dialog = QDialog(self)
        dialog.setWindowTitle("Grab our Decals")
        dialog.setMinimumWidth(320)
        dialog.setMaximumWidth(320)

        layout = QVBoxLayout(dialog)
        layout.setSpacing(8)
        layout.setContentsMargins(20, 20, 20, 20)

        title = QLabel("Grab our Decals")
        title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        font = title.font()
        font.setBold(True)
        font.setPointSize(11)
        title.setFont(font)
        layout.addWidget(title)

        layout.addSpacing(6)

        supporters = [
            ("Ask3lad",              "https://store.gaijin.net/catalog.php?category=WarThunder&partner=Ask3lad&partner_val=lpzjtauw"),
            ("Lionstripes",          "https://store.gaijin.net/catalog.php?category=WarThunder&partner=Lionstripe&partner_val=42alaxss"),
            ("TheGreenlandicGamer",  "https://store.gaijin.net/catalog.php?category=WarThunder&partner=TheGreenlandicGamer&partner_val=rt16bh24"),
        ]

        for name, url in supporters:
            btn = QPushButton(name)
            btn.clicked.connect(lambda _, u=url: webbrowser.open(u))
            layout.addWidget(btn)

        layout.addSpacing(6)
        close_btn = QPushButton("Close")
        close_btn.clicked.connect(dialog.accept)
        layout.addWidget(close_btn)

        dialog.exec()

    def show_changelog(self):
        """Show the Changelog dialog."""
        dialog = QDialog(self)
        dialog.setWindowTitle("Changelog")
        dialog.setMinimumWidth(360)
        dialog.setMaximumWidth(360)

        layout = QVBoxLayout(dialog)
        layout.setSpacing(8)
        layout.setContentsMargins(20, 20, 20, 20)

        title = QLabel("Changelog")
        title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        font = title.font()
        font.setBold(True)
        font.setPointSize(11)
        title.setFont(font)
        layout.addWidget(title)

        layout.addSpacing(6)

        log = QLabel(
            "Version 2.51\n"
            "―――――――――――――――――――――――――――――\n"
            "  General\n"
            "  • Full UI redesign with tabbed layout\n"
            "  • Automatic database updates from GitHub\n"
            "  • Added Setup Wizard for first-time setup\n"
            "  • Added Ground and Naval mode switcher\n"
            "  • Added Active and Selected Previews\n"
            "  • Added ammo selection for vehicles and ships\n"
            "  • Added time of day and weather selectors\n"
            "  • Added target and vehicle selection\n"
            "  • Added role filter for vehicles and ships\n"
            "  • Added country filter buttons\n"
            "  • Added Themed Presets (Ground and Naval)\n"
            "  • Added Save / Load / Rename / Delete User Presets\n"
            "  • Added Recently Used Vehicles\n"
            "  • Added Favourites List\n"
            "  • Added Random Time & Weather button\n"
            "  • Added Air Test Drive tab (Coming Soon)\n"
            "  • Added File → Check for Updates (database and app)\n"
            "  • Added How to Use, Changelog, and Report a Bug\n"
            "  • Added app version check on startup\n"
            "  • Added Import / Export for user presets\n"
            "  • Added Custom Map toggle button\n"
            "  • Added crash log system (Logs/ folder)\n"
            "  • Added [Debug] Open Weapon Override Folder\n"
            "  • Added [Debug] War Thunder Datamine GitHub\n"
            "  • Improved search bar for vehicles and ships\n\n"
            "  Ground\n"
            "  • Added 3 ground target slots (300m/600m/800m)\n"
            "  • Added 2 aircraft target slots (5km/2.5km)\n"
            "  • Added helicopter target slot (2km)\n"
            "  • Added Themed Presets (WW1 to Modern)\n"
            "  • Added Experimental tab with Engine Override\n"
            "  • Added Multi-slot Ammo Loadout support\n"
            "  • Added auto-respawn for ground targets\n"
            "  • Added rotation dials for all 3 ground targets\n"
            "  • Added Weapon Override — change projectile\n"
            "  • Added Velocity Override — change projectile speed\n"
            "  • Added Caliber Override — change projectile diameter\n\n"
            "  Naval\n"
            "  • Added full Naval Test Drive support\n"
            "  • Added 3 static target slots (5km/10km/15km)\n"
            "  • Added moving ship target slot\n"
            "  • Added aircraft target slots (10km/25km)\n"
            "  • Added Themed Preset (Bombardment of Iwo Jima)\n"
            "  • Added in-game display names for naval ammunition\n"
            "  • Added Naval Ammo Selection (per-caliber)\n"
            "  • Added Bombarding Ships tab\n"
            "  • Added Experimental tab with War Mode\n"
            "  • Added Rapid Fire to Naval Experimental tab\n"
        )
        log.setWordWrap(True)
        layout.addWidget(log)

        layout.addSpacing(6)
        close_btn = QPushButton("Close")
        close_btn.clicked.connect(dialog.accept)
        layout.addWidget(close_btn)

        dialog.exec()

    def show_db_changelog(self):
        """Show the Database Changelog dialog."""
        try:
            db_ver_path = os.path.join(self.assets_folder, "db_version.json")
            with open(db_ver_path, "r", encoding="utf-8") as f:
                db_ver = json.load(f)
            db_stamp = f"v{db_ver.get('version', '?')} — {db_ver.get('date', '?')}"
            t = db_ver.get("time", "")
            if t:
                db_stamp += f"  {t}"
            db_notes = db_ver.get("notes", [])
        except Exception:
            db_stamp = "unknown"
            db_notes = []

        dialog = QDialog(self)
        dialog.setWindowTitle("Database Changelog")
        dialog.setMinimumWidth(360)
        dialog.setMaximumWidth(360)

        layout = QVBoxLayout(dialog)
        layout.setSpacing(8)
        layout.setContentsMargins(20, 20, 20, 20)

        title = QLabel("Database Changelog")
        title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        font = title.font()
        font.setBold(True)
        font.setPointSize(11)
        title.setFont(font)
        layout.addWidget(title)

        layout.addSpacing(6)

        notes_text = "".join(f"  • {note}\n" for note in db_notes) if db_notes else "  No notes available.\n"
        log = QLabel(
            f"  {db_stamp}\n"
            "―――――――――――――――――――――――――――――\n"
            + notes_text
        )
        log.setWordWrap(True)
        layout.addWidget(log)

        layout.addSpacing(6)
        close_btn = QPushButton("Close")
        close_btn.clicked.connect(dialog.accept)
        layout.addWidget(close_btn)

        dialog.exec()

    def eventFilter(self, source, event):
        if source is self.mode_tabs.tabBar() and event.type() == event.Type.MouseButtonPress:
            index = self.mode_tabs.tabBar().tabAt(event.pos())
            if index == 2:
                self._air_tab_clicks += 1
                if self._air_tab_clicks >= 10:
                    self._air_tab_clicks = 0
                    webbrowser.open("https://youtu.be/dQw4w9WgXcQ?si=29SOy2SgUusiLr0D")
        return super().eventFilter(source, event)

    def open_discord(self):
        """Open the Ask3lad Discord invite in the default browser."""
        webbrowser.open("https://discord.com/invite/f3nsgypbh7")

    def open_support(self):
        """Open the YouTube channel membership page in the default browser."""
        webbrowser.open("https://www.youtube.com/@Ask3lad/join")


# ── Palettes ──────────────────────────────────────────────────────────────────

def _light_palette():
    p = QPalette()
    p.setColor(QPalette.ColorRole.Window,          QColor(240, 240, 240))
    p.setColor(QPalette.ColorRole.WindowText,      QColor(0,   0,   0))
    p.setColor(QPalette.ColorRole.Base,            QColor(255, 255, 255))
    p.setColor(QPalette.ColorRole.AlternateBase,   QColor(233, 233, 233))
    p.setColor(QPalette.ColorRole.Text,            QColor(0,   0,   0))
    p.setColor(QPalette.ColorRole.Button,          QColor(240, 240, 240))
    p.setColor(QPalette.ColorRole.ButtonText,      QColor(0,   0,   0))
    p.setColor(QPalette.ColorRole.Highlight,       QColor(0,   120, 215))
    p.setColor(QPalette.ColorRole.HighlightedText, QColor(255, 255, 255))
    p.setColor(QPalette.ColorRole.ToolTipBase,     QColor(255, 255, 220))
    p.setColor(QPalette.ColorRole.ToolTipText,     QColor(0,   0,   0))
    return p

def _dark_palette():
    p = QPalette()
    p.setColor(QPalette.ColorRole.Window,          QColor(45,  45,  45))
    p.setColor(QPalette.ColorRole.WindowText,      QColor(220, 220, 220))
    p.setColor(QPalette.ColorRole.Base,            QColor(30,  30,  30))
    p.setColor(QPalette.ColorRole.AlternateBase,   QColor(40,  40,  40))
    p.setColor(QPalette.ColorRole.Text,            QColor(220, 220, 220))
    p.setColor(QPalette.ColorRole.Button,          QColor(55,  55,  55))
    p.setColor(QPalette.ColorRole.ButtonText,      QColor(220, 220, 220))
    p.setColor(QPalette.ColorRole.Highlight,       QColor(0,   120, 215))
    p.setColor(QPalette.ColorRole.HighlightedText, QColor(255, 255, 255))
    p.setColor(QPalette.ColorRole.ToolTipBase,     QColor(50,  50,  50))
    p.setColor(QPalette.ColorRole.ToolTipText,     QColor(220, 220, 220))
    return p

def _apply_theme(dark):
    QApplication.instance().setPalette(_dark_palette() if dark else _light_palette())
    if dark:
        QApplication.instance().setStyleSheet("""
            QLineEdit { color: #dcdcdc; }
            QLineEdit::placeholder { color: #888888; }
            QCheckBox { spacing: 8px; }
            QCheckBox::indicator {
                width: 18px; height: 18px;
                border: 2px solid #aaaaaa;
                border-radius: 3px;
                background: #2d2d2d;
            }
            QCheckBox::indicator:checked {
                background: #0078d7;
                border-color: #0078d7;
            }
            QCheckBox::indicator:unchecked:hover { border-color: #cccccc; }
        """)
    else:
        QApplication.instance().setStyleSheet("""
            QLineEdit { color: black; }
            QLineEdit::placeholder { color: #888888; }
            QCheckBox { spacing: 8px; }
            QCheckBox::indicator {
                width: 18px; height: 18px;
                border: 2px solid #555555;
                border-radius: 3px;
                background: #ffffff;
            }
            QCheckBox::indicator:checked {
                background: #0078d7;
                border-color: #0078d7;
            }
            QCheckBox::indicator:unchecked:hover { border-color: #222222; }
        """)

# ── Entry Point ───────────────────────────────────────────────────────────────

if __name__ == "__main__":
    sys.excepthook = _crash_handler
    app = QApplication(sys.argv)
    app.setStyle("Fusion")
    app.setPalette(_light_palette())
    app.setStyleSheet("QLineEdit { color: black; } QLineEdit::placeholder { color: #888888; }")

    window = WarThunderTestDriveGUI()
    window.show()
    sys.exit(app.exec())
