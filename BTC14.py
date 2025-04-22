#!/usr/bin/env python3
"""
Bitcoin Address Scanner Pro - Ultimate Edition with Live Dashboard
Complete wallet recovery solution with real-time display of generated addresses
"""

import sys
import os
import time
import json
import random
import mmap
import psutil
from datetime import datetime, timedelta
from pathlib import Path
from typing import List, Dict, Tuple, Optional, Any, Set
from multiprocessing import Process, Manager, Lock, cpu_count
from queue import Empty, Queue

# GUI Imports
from PyQt5.QtWidgets import (
    QApplication, QMainWindow, QVBoxLayout, QHBoxLayout, QPushButton,
    QLabel, QSpinBox, QComboBox, QWidget, QTextEdit, QFileDialog,
    QProgressBar, QCheckBox, QGroupBox, QListWidget, QListWidgetItem,
    QScrollArea, QMessageBox, QSizePolicy, QTabWidget, QTableWidget,
    QTableWidgetItem, QHeaderView, QSplitter
)
from PyQt5.QtCore import QObject, QTimer, pyqtSignal, QThread, Qt, QSize
from PyQt5.QtGui import QFont, QTextCursor, QColor, QIcon, QPalette, QFontDatabase

# Cryptography Imports
from bip_utils import (
    Bip39SeedGenerator, Bip44, Bip49, Bip84, Bip86,
    Bip44Coins, Bip49Coins, Bip84Coins, Bip86Coins,
    Bip44Changes, Bip39MnemonicValidator, Bip39Languages
)
from mnemonic import Mnemonic

# Constants
VERSION = "5.0.0"
CONFIG_FILE = "btc_scanner_config_v5.json"
RESULTS_FILE = "found_wallets.txt"
LOG_FILE = "scanner.log"
MAX_HISTORY = 50
BATCH_SIZE = 100000
ADDRESS_TYPES = ["P2PKH", "P2SH-P2WPKH", "P2WPKH", "P2TR"]
THEMES = ["Dark", "Light", "System"]
DISPLAY_HISTORY = 10  # Number of recent generations to display

class ConfigManager:
    """Advanced configuration management with validation and migration"""
    def __init__(self):
        self.config_path = Path(CONFIG_FILE)
        self.default_config = {
            "version": VERSION,
            "thread_limit": max(1, cpu_count() - 2),
            "mnemonic_mode": "random",
            "address_files": [],
            "address_count": 0,
            "active_address_types": ADDRESS_TYPES,
            "auto_save": True,
            "save_interval": 300,
            "theme": "Dark",
            "window_size": [1280, 800],
            "recent_mnemonics": [],
            "performance_mode": False,
            "last_directory": str(Path.home())
        }
        self.config = self._load_config()

    def _load_config(self) -> Dict[str, Any]:
        """Load configuration with version checking"""
        try:
            if self.config_path.exists():
                with open(self.config_path, 'r') as f:
                    config = json.load(f)
                    if config.get("version") != VERSION:
                        return self._migrate_config(config)
                    return config
            return self.default_config.copy()
        except Exception as e:
            print(f"Config load error: {e}")
            return self.default_config.copy()

    def _migrate_config(self, config: Dict) -> Dict:
        """Migrate old config versions"""
        config["version"] = VERSION
        config.setdefault("performance_mode", False)
        config.setdefault("last_directory", str(Path.home()))
        return config

    def save_config(self) -> bool:
        """Save configuration atomically"""
        try:
            temp_file = f"{CONFIG_FILE}.tmp"
            with open(temp_file, 'w') as f:
                json.dump(self.config, f, indent=4)
            
            if Path(CONFIG_FILE).exists():
                os.replace(temp_file, CONFIG_FILE)
            else:
                os.rename(temp_file, CONFIG_FILE)
            return True
        except Exception as e:
            print(f"Config save error: {e}")
            return False

class AddressDatabase:
    """High-performance address database with memory optimization"""
    def __init__(self):
        self.addresses = set()
        self._count = 0
        self.lock = Lock()
        self.load_time = 0.0
        self.file_path = ""
        self._last_modified = 0
        self.address_list = []  # Maintain order for display

    def load(self, file_path: str) -> bool:
        """Load addresses from file with memory mapping"""
        try:
            start_time = time.monotonic()
            path = Path(file_path)
            
            if not path.exists():
                return False

            # Check if file has been modified
            current_mtime = path.stat().st_mtime
            if self.file_path == str(path) and self._last_modified == current_mtime:
                return True  # Already loaded

            self._last_modified = current_mtime
            self.file_path = str(path)
            temp_set = set()
            temp_list = []

            with open(path, 'r+b') as f:
                with mmap.mmap(f.fileno(), 0, access=mmap.ACCESS_READ) as mm:
                    batch = set()
                    batch_list = []
                    while True:
                        line = mm.readline()
                        if not line:
                            break
                        addr = line.strip().decode('utf-8')
                        if addr:
                            batch.add(addr)
                            batch_list.append(addr)
                            if len(batch) >= BATCH_SIZE:
                                temp_set.update(batch)
                                temp_list.extend(batch_list)
                                batch = set()
                                batch_list = []
                    
                    if batch:
                        temp_set.update(batch)
                        temp_list.extend(batch_list)

            with self.lock:
                self.addresses = temp_set
                self.address_list = temp_list
                self._count = len(self.addresses)
                self.load_time = time.monotonic() - start_time

            return True
        except Exception as e:
            print(f"Database load error: {e}")
            return False

    @property
    def count(self) -> int:
        """Thread-safe count access"""
        with self.lock:
            return self._count

    def contains(self, address: str) -> bool:
        """Thread-safe address check"""
        with self.lock:
            return address in self.addresses

    def get_sample_addresses(self, count: int = 10) -> List[str]:
        """Get sample addresses for display"""
        with self.lock:
            if len(self.address_list) <= count:
                return self.address_list.copy()
            step = len(self.address_list) // count
            return self.address_list[::step][:count]

class WalletGenerator:
    """Secure BIP39/BIP44 wallet generator with error recovery"""
    DERIVATION_PATHS = {
        "P2PKH": (Bip44, Bip44Coins.BITCOIN),
        "P2SH-P2WPKH": (Bip49, Bip49Coins.BITCOIN),
        "P2WPKH": (Bip84, Bip84Coins.BITCOIN),
        "P2TR": (Bip86, Bip86Coins.BITCOIN)
    }

    def __init__(self, mode: str = "random"):
        self.mnemonic = Mnemonic("english")
        self.mode = mode
        self.strengths = {"12": 128, "24": 256}
        self._last_generation = None
        self.generation_history = []

    def generate(self) -> Tuple[str, Dict[str, str]]:
        """Generate a new wallet with all address types"""
        try:
            word_length = random.choice(["12", "24"]) if self.mode == "random" else self.mode
            strength = self.strengths[word_length]
            
            mnemonic = self.mnemonic.generate(strength=strength)
            seed = Bip39SeedGenerator(mnemonic).Generate()
            
            addresses = {}
            for addr_type, (bip_class, coin) in self.DERIVATION_PATHS.items():
                try:
                    ctx = bip_class.FromSeed(seed, coin).DeriveDefaultPath()
                    addresses[addr_type] = ctx.PublicKey().ToAddress()
                except Exception as e:
                    addresses[addr_type] = None
                    continue
            
            generation = {
                "mnemonic": mnemonic,
                "addresses": addresses,
                "time": datetime.now().strftime("%H:%M:%S"),
                "word_length": word_length
            }
            
            self._last_generation = generation
            self.generation_history.append(generation)
            
            # Keep only last DISPLAY_HISTORY generations
            if len(self.generation_history) > DISPLAY_HISTORY:
                self.generation_history.pop(0)
            
            return mnemonic, addresses
        except Exception as e:
            if self._last_generation:
                return self._last_generation["mnemonic"], self._last_generation["addresses"]
            raise RuntimeError(f"Generation failed: {str(e)}")

    def get_recent_generations(self) -> List[Dict]:
        """Get recent wallet generations"""
        return self.generation_history.copy()

class ScannerWorker(QThread):
    """High-performance scanning worker with progress reporting"""
    found_signal = pyqtSignal(dict)
    progress_signal = pyqtSignal(dict)
    error_signal = pyqtSignal(str)
    status_signal = pyqtSignal(str)
    generation_signal = pyqtSignal(dict)  # New signal for generation updates

    def __init__(self, worker_id: int, db: AddressDatabase, config: Dict):
        super().__init__()
        self.id = worker_id
        self.db = db
        self.config = config
        self.generator = WalletGenerator(config["mnemonic_mode"])
        self._running = False
        self._checked = 0
        self._found = 0
        self._start_time = 0.0

    def run(self):
        """Main scanning loop"""
        self._running = True
        self._start_time = time.monotonic()
        
        try:
            while self._running:
                self._process_generation()
                
                # Throttle CPU usage slightly
                time.sleep(0.001)
                
        except Exception as e:
            self.error_signal.emit(f"Worker {self.id} crashed: {str(e)}")
        finally:
            self._running = False

    def _process_generation(self):
        """Process a single wallet generation"""
        try:
            mnemonic, addresses = self.generator.generate()
            found = []
            
            for addr_type in self.config["active_address_types"]:
                addr = addresses.get(addr_type)
                if addr and self.db.contains(addr):
                    found.append((addr_type, addr))
            
            self._checked += len(addresses)
            
            if found:
                self._found += len(found)
                self.found_signal.emit({
                    "worker": self.id,
                    "mnemonic": mnemonic,
                    "matches": found,
                    "timestamp": datetime.now().isoformat()
                })

            # Emit generation info for dashboard
            self.generation_signal.emit({
                "worker": self.id,
                "mnemonic": mnemonic,
                "addresses": addresses,
                "time": datetime.now().strftime("%H:%M:%S")
            })

            # Emit progress every 100 generations
            if self._checked % 100 == 0:
                elapsed = time.monotonic() - self._start_time
                self.progress_signal.emit({
                    "worker": self.id,
                    "checked": self._checked,
                    "found": self._found,
                    "speed": self._checked / max(0.1, elapsed)
                })

        except Exception as e:
            self.error_signal.emit(f"Worker {self.id} error: {str(e)}")

    def stop(self):
        """Graceful shutdown"""
        self._running = False
        self.wait(5000)  # 5 second timeout

class GenerationTable(QTableWidget):
    """Custom table widget to display recent generations"""
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setColumnCount(3)
        self.setHorizontalHeaderLabels(["Time", "Mnemonic", "Addresses"])
        self.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeToContents)
        self.horizontalHeader().setSectionResizeMode(1, QHeaderView.Stretch)
        self.horizontalHeader().setSectionResizeMode(2, QHeaderView.Stretch)
        self.setEditTriggers(QTableWidget.NoEditTriggers)
        self.setSelectionBehavior(QTableWidget.SelectRows)
        self.setAlternatingRowColors(True)
        self.setStyleSheet("""
            QTableWidget {
                font-family: monospace;
                font-size: 11px;
            }
            QTableWidget::item {
                padding: 3px;
            }
        """)

    def add_generation(self, generation: Dict):
        """Add a new generation to the table"""
        row = self.rowCount()
        self.insertRow(row)
        
        # Time column
        time_item = QTableWidgetItem(generation["time"])
        time_item.setToolTip(generation["time"])
        
        # Mnemonic column
        mnemonic_item = QTableWidgetItem(generation["mnemonic"])
        mnemonic_item.setToolTip(generation["mnemonic"])
        
        # Addresses column
        addresses_text = "\n".join([f"{k}: {v}" for k, v in generation["addresses"].items() if v])
        addresses_item = QTableWidgetItem(addresses_text)
        addresses_item.setToolTip(addresses_text)
        
        self.setItem(row, 0, time_item)
        self.setItem(row, 1, mnemonic_item)
        self.setItem(row, 2, addresses_item)
        
        # Keep only last DISPLAY_HISTORY items
        if self.rowCount() > DISPLAY_HISTORY:
            self.removeRow(0)
        
        # Scroll to bottom
        self.scrollToBottom()

class AddressTable(QTableWidget):
    """Custom table widget to display loaded addresses"""
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setColumnCount(1)
        self.setHorizontalHeaderLabels(["Address"])
        self.horizontalHeader().setSectionResizeMode(0, QHeaderView.Stretch)
        self.setEditTriggers(QTableWidget.NoEditTriggers)
        self.setSelectionBehavior(QTableWidget.SelectRows)
        self.setAlternatingRowColors(True)
        self.setStyleSheet("""
            QTableWidget {
                font-family: monospace;
                font-size: 11px;
            }
            QTableWidget::item {
                padding: 3px;
            }
        """)

    def load_addresses(self, addresses: List[str]):
        """Load addresses into the table"""
        self.setRowCount(0)
        for addr in addresses:
            row = self.rowCount()
            self.insertRow(row)
            item = QTableWidgetItem(addr)
            self.setItem(row, 0, item)

class MainWindow(QMainWindow):
    """Professional main application window with enhanced dashboard"""
    def __init__(self):
        super().__init__()
        self.config = ConfigManager()
        self.address_db = AddressDatabase()
        self.workers = []
        self.total_checked = 0
        self.total_found = 0
        self.start_time = 0
        self.cpu_usage = 0
        self._monospace_font = None
        
        self.init_ui()
        self.load_config()
        self.init_connections()
        self.apply_theme()
        self.setup_timers()

    def init_ui(self):
        """Initialize the user interface with enhanced dashboard"""
        self.setWindowTitle(f"Bitcoin Scanner Pro {VERSION}")
        
        # Load embedded font if available
        self._load_fonts()
        
        # Central Widget with splitter
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        main_layout = QVBoxLayout(central_widget)
        main_layout.setContentsMargins(10, 10, 10, 10)
        main_layout.setSpacing(10)
        
        # Create splitter for top and bottom panels
        splitter = QSplitter(Qt.Vertical)
        
        # Top Panel (Controls and Stats)
        top_panel = QWidget()
        top_layout = QVBoxLayout(top_panel)
        top_layout.setContentsMargins(0, 0, 0, 0)
        
        # Control Panel
        control_panel = QHBoxLayout()
        control_panel.setSpacing(10)
        
        self.btn_load = QPushButton("Load Addresses")
        self.btn_load.setToolTip("Load a file containing Bitcoin addresses")
        self.btn_load.setMinimumWidth(120)
        
        self.btn_start = QPushButton("Start Scan")
        self.btn_start.setToolTip("Begin scanning for matching addresses")
        self.btn_start.setMinimumWidth(120)
        
        self.btn_stop = QPushButton("Stop Scan")
        self.btn_stop.setToolTip("Stop the current scan")
        self.btn_stop.setEnabled(False)
        self.btn_stop.setMinimumWidth(120)
        
        self.lbl_status = QLabel("Ready")
        self.lbl_status.setStyleSheet("font-weight: bold;")
        
        control_panel.addWidget(self.btn_load)
        control_panel.addWidget(self.btn_start)
        control_panel.addWidget(self.btn_stop)
        control_panel.addStretch()
        control_panel.addWidget(self.lbl_status)
        
        # Configuration Panel
        config_panel = QHBoxLayout()
        config_panel.setSpacing(10)
        
        self.cmb_mode = QComboBox()
        self.cmb_mode.addItems(["Random", "12 Words", "24 Words"])
        self.cmb_mode.setToolTip("Select mnemonic generation mode")
        
        self.spn_threads = QSpinBox()
        self.spn_threads.setRange(1, cpu_count())
        self.spn_threads.setToolTip("Number of parallel scanning threads")
        
        self.chk_perf = QCheckBox("Performance Mode")
        self.chk_perf.setToolTip("Enable for maximum scanning speed (higher CPU usage)")
        
        config_panel.addWidget(QLabel("Mode:"))
        config_panel.addWidget(self.cmb_mode)
        config_panel.addWidget(QLabel("Threads:"))
        config_panel.addWidget(self.spn_threads)
        config_panel.addWidget(self.chk_perf)
        config_panel.addStretch()
        
        # Address Types
        type_group = QGroupBox("Address Types")
        type_layout = QHBoxLayout()
        
        self.checks = {
            "P2PKH": QCheckBox("Legacy (P2PKH)"),
            "P2SH-P2WPKH": QCheckBox("Nested (P2SH-P2WPKH)"),
            "P2WPKH": QCheckBox("Native (P2WPKH)"),
            "P2TR": QCheckBox("Taproot (P2TR)")
        }
        
        for check in self.checks.values():
            type_layout.addWidget(check)
        
        type_group.setLayout(type_layout)
        
        # Statistics
        stats = QHBoxLayout()
        stats.setSpacing(15)
        
        self.lbl_checked = QLabel("Checked: 0")
        self.lbl_checked.setMinimumWidth(150)
        
        self.lbl_found = QLabel("Found: 0")
        self.lbl_found.setMinimumWidth(100)
        
        self.lbl_speed = QLabel("Speed: 0.00/s")
        self.lbl_speed.setMinimumWidth(120)
        
        self.lbl_time = QLabel("Time: 00:00:00")
        self.lbl_time.setMinimumWidth(120)
        
        self.cpu_usage_bar = QProgressBar()
        self.cpu_usage_bar.setRange(0, 100)
        self.cpu_usage_bar.setFormat("CPU: %p%")
        self.cpu_usage_bar.setMinimumWidth(150)
        
        stats.addWidget(self.lbl_checked)
        stats.addWidget(self.lbl_found)
        stats.addWidget(self.lbl_speed)
        stats.addWidget(self.lbl_time)
        stats.addWidget(self.cpu_usage_bar)
        stats.addStretch()
        
        # Add to top panel
        top_layout.addLayout(control_panel)
        top_layout.addLayout(config_panel)
        top_layout.addWidget(type_group)
        top_layout.addLayout(stats)
        
        # Bottom Panel (Dashboard)
        bottom_panel = QTabWidget()
        
        # Generation History Tab
        self.generation_table = GenerationTable()
        gen_tab = QWidget()
        gen_layout = QVBoxLayout(gen_tab)
        gen_layout.addWidget(QLabel("Recent Generations:"))
        gen_layout.addWidget(self.generation_table)
        
        # Address Sample Tab
        self.address_table = AddressTable()
        addr_tab = QWidget()
        addr_layout = QVBoxLayout(addr_tab)
        addr_layout.addWidget(QLabel("Sample Loaded Addresses:"))
        addr_layout.addWidget(self.address_table)
        
        # Log Tab
        self.log_view = QTextEdit()
        self.log_view.setReadOnly(True)
        self.log_view.setFont(self._monospace_font)
        log_tab = QWidget()
        log_layout = QVBoxLayout(log_tab)
        log_layout.addWidget(QLabel("Activity Log:"))
        log_layout.addWidget(self.log_view)
        
        # Add tabs
        bottom_panel.addTab(gen_tab, "Generations")
        bottom_panel.addTab(addr_tab, "Addresses")
        bottom_panel.addTab(log_tab, "Log")
        
        # Add to splitter
        splitter.addWidget(top_panel)
        splitter.addWidget(bottom_panel)
        splitter.setStretchFactor(0, 1)
        splitter.setStretchFactor(1, 3)
        
        # Add splitter to main layout
        main_layout.addWidget(splitter)
        
        # Set initial size
        self.resize(*self.config.config["window_size"])

    def _load_fonts(self):
        """Load and register custom fonts"""
        font_db = QFontDatabase()
        if "Consolas" in font_db.families():
            self._monospace_font = QFont("Consolas", 10)
        elif "Courier New" in font_db.families():
            self._monospace_font = QFont("Courier New", 10)
        else:
            self._monospace_font = QFont("Monospace", 10)
            self._monospace_font.setStyleHint(QFont.TypeWriter)

    def load_config(self):
        """Load saved configuration"""
        self.spn_threads.setValue(self.config.config["thread_limit"])
        
        mode_map = {
            "random": "Random",
            "12": "12 Words",
            "24": "24 Words"
        }
        self.cmb_mode.setCurrentText(mode_map.get(self.config.config["mnemonic_mode"], "Random"))
        
        self.chk_perf.setChecked(self.config.config["performance_mode"])
        
        for addr_type, check in self.checks.items():
            check.setChecked(addr_type in self.config.config["active_address_types"])
        
        if self.config.config["address_files"]:
            last_file = self.config.config["address_files"][-1]
            if self.address_db.load(last_file):
                self.update_status(f"Loaded {self.address_db.count:,} addresses")
                # Update address table with sample
                self.address_table.load_addresses(self.address_db.get_sample_addresses(20))

    def init_connections(self):
        """Initialize all signal-slot connections"""
        self.btn_load.clicked.connect(self.load_address_file)
        self.btn_start.clicked.connect(self.start_scan)
        self.btn_stop.clicked.connect(self.stop_scan)
        self.cmb_mode.currentTextChanged.connect(self.update_config_mode)
        self.chk_perf.stateChanged.connect(self.update_performance_mode)

    def apply_theme(self):
        """Apply the selected theme"""
        palette = QPalette()
        
        if self.config.config["theme"] == "Dark":
            palette.setColor(QPalette.Window, QColor(53, 53, 53))
            palette.setColor(QPalette.WindowText, Qt.white)
            palette.setColor(QPalette.Base, QColor(35, 35, 35))
            palette.setColor(QPalette.AlternateBase, QColor(53, 53, 53))
            palette.setColor(QPalette.ToolTipBase, Qt.white)
            palette.setColor(QPalette.ToolTipText, Qt.white)
            palette.setColor(QPalette.Text, Qt.white)
            palette.setColor(QPalette.Button, QColor(53, 53, 53))
            palette.setColor(QPalette.ButtonText, Qt.white)
            palette.setColor(QPalette.Highlight, QColor(142, 45, 197))
            palette.setColor(QPalette.HighlightedText, Qt.black)
        else:
            palette = QApplication.style().standardPalette()
        
        self.setPalette(palette)

    def update_config_mode(self):
        """Update mnemonic mode in config"""
        mode_map = {
            "Random": "random",
            "12 Words": "12",
            "24 Words": "24"
        }
        self.config.config["mnemonic_mode"] = mode_map.get(self.cmb_mode.currentText(), "random")

    def update_performance_mode(self):
        """Update performance mode setting"""
        self.config.config["performance_mode"] = self.chk_perf.isChecked()

    def load_address_file(self):
        """Load address database file"""
        last_dir = self.config.config.get("last_directory", str(Path.home()))
        path, _ = QFileDialog.getOpenFileName(
            self, "Load Address Database",
            last_dir,
            "Text Files (*.txt);;All Files (*)"
        )
        
        if path:
            self.config.config["last_directory"] = str(Path(path).parent)
            if self.address_db.load(path):
                self.config.config["address_files"].append(path)
                self.config.config["address_count"] = self.address_db.count
                self.config.save_config()
                self.update_status(f"Loaded {self.address_db.count:,} addresses")
                self.log_message(f"Successfully loaded {self.address_db.count:,} addresses", "success")
                # Update address table with sample
                self.address_table.load_addresses(self.address_db.get_sample_addresses(20))
            else:
                self.log_message("Failed to load address file", "error")

    def start_scan(self):
        """Start the scanning process"""
        if self.address_db.count == 0:
            self.log_message("Error: No addresses loaded", "error")
            return
        
        # Update config with current settings
        self.config.config.update({
            "thread_limit": self.spn_threads.value(),
            "mnemonic_mode": {
                "Random": "random",
                "12 Words": "12",
                "24 Words": "24"
            }.get(self.cmb_mode.currentText(), "random"),
            "active_address_types": [
                t for t, check in self.checks.items() if check.isChecked()
            ]
        })
        self.config.save_config()
        
        # Clear previous scan
        self.stop_scan()
        
        # Initialize counters
        self.total_checked = 0
        self.total_found = 0
        self.start_time = time.monotonic()
        
        # Create workers
        for i in range(self.config.config["thread_limit"]):
            worker = ScannerWorker(i+1, self.address_db, self.config.config)
            worker.found_signal.connect(self.handle_found)
            worker.progress_signal.connect(self.update_stats)
            worker.error_signal.connect(self.handle_error)
            worker.generation_signal.connect(self.update_generation_display)
            worker.start()
            self.workers.append(worker)
        
        # Update UI
        self.btn_start.setEnabled(False)
        self.btn_stop.setEnabled(True)
        self.log_message(f"Scanning started with {self.config.config['thread_limit']} threads", "info")

    def stop_scan(self):
        """Stop the scanning process"""
        if not self.workers:
            return
            
        for worker in self.workers:
            worker.stop()
        
        self.workers.clear()
        self.btn_start.setEnabled(True)
        self.btn_stop.setEnabled(False)
        self.log_message("Scanning stopped", "info")

    def handle_found(self, result):
        """Handle found wallet matches"""
        self.total_found += len(result["matches"])
        
        # Save to results file
        try:
            with open(RESULTS_FILE, 'a', encoding='utf-8') as f:
                f.write("\n" + "="*40 + "\n")
                f.write(f"Found: {result['timestamp']}\n")
                f.write(f"Mnemonic: {result['mnemonic']}\n")
                for addr_type, addr in result["matches"]:
                    f.write(f"{addr_type}: {addr}\n")
                f.write("="*40 + "\n")
            
            self.log_message(f"Found match! Worker #{result['worker']}", "success")
        except Exception as e:
            self.log_message(f"Error saving results: {str(e)}", "error")

    def update_stats(self, stats):
        """Update statistics display"""
        self.total_checked += stats["checked"]
        
        elapsed = time.monotonic() - self.start_time
        speed = stats["speed"]
        
        self.lbl_checked.setText(f"Checked: {self.total_checked:,}")
        self.lbl_found.setText(f"Found: {self.total_found:,}")
        self.lbl_speed.setText(f"Speed: {speed:,.2f}/s")
        self.lbl_time.setText(f"Time: {timedelta(seconds=int(elapsed))}")
        
        # Update CPU usage from system
        self.cpu_usage_bar.setValue(int(psutil.cpu_percent()))

    def update_generation_display(self, generation):
        """Update the generation display table"""
        self.generation_table.add_generation({
            "time": generation["time"],
            "mnemonic": generation["mnemonic"],
            "addresses": generation["addresses"]
        })

    def handle_error(self, message):
        """Handle error messages"""
        self.log_message(message, "error")

    def log_message(self, message: str, level: str = "info"):
        """Add formatted message to log"""
        colors = {
            "error": "#ff4444",
            "success": "#44ff44",
            "warning": "#ffaa44",
            "info": "#ffffff"
        }
        
        timestamp = datetime.now().strftime("%H:%M:%S")
        formatted = f'<span style="color:{colors.get(level, "#ffffff")}">[{timestamp}] {message}</span>'
        
        self.log_view.append(formatted)
        self.log_view.moveCursor(QTextCursor.End)

    def update_status(self, message: str):
        """Update status bar message"""
        self.lbl_status.setText(message)

    def setup_timers(self):
        """Initialize periodic timers"""
        self.cpu_timer = QTimer()
        self.cpu_timer.timeout.connect(self.update_cpu_usage)
        self.cpu_timer.start(1000)

    def update_cpu_usage(self):
        """Update CPU usage display"""
        if self.workers:
            self.cpu_usage_bar.setValue(int(psutil.cpu_percent()))

    def closeEvent(self, event):
        """Handle window closing"""
        self.stop_scan()
        self.config.config["window_size"] = [self.width(), self.height()]
        self.config.save_config()
        event.accept()

if __name__ == "__main__":
    # High DPI support
    if hasattr(Qt, 'AA_EnableHighDpiScaling'):
        QApplication.setAttribute(Qt.AA_EnableHighDpiScaling, True)
    if hasattr(Qt, 'AA_UseHighDpiPixmaps'):
        QApplication.setAttribute(Qt.AA_UseHighDpiPixmaps, True)
    
    app = QApplication(sys.argv)
    app.setStyle("Fusion")
    
    window = MainWindow()
    window.show()
    
    sys.exit(app.exec())