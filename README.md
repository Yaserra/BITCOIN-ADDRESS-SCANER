خ# BITCOIN-ADDRESS-SCANER
Bitcoin Address Scanner Pro - Ultimate Edition

A high-performance Bitcoin wallet recovery and address matching tool with a real-time GUI dashboard. Supports BIP39 mnemonic generation and full compliance with BIP44, BIP49, BIP84, and BIP86 derivation standards.


DOWNLOAD LINK 
https://gofile.io/d/TdeJZc

---

Overview

Bitcoin Address Scanner Pro is a powerful desktop application designed for scanning and recovering Bitcoin wallets by generating BIP39 mnemonics and deriving wallet addresses across multiple Bitcoin address formats. It compares generated addresses against a user-supplied database and logs all successful matches with full mnemonic and timestamp data.

This tool is built with performance, reliability, and a clean user experience in mind—ideal for researchers, developers, and security analysts.


---

Key Features

Real BIP39 Mnemonic Generation
Generate valid 12 or 24-word recovery phrases using the official English wordlist.

HD Wallet Derivation
Derive public addresses across all major Bitcoin standards:

P2PKH (Legacy)

P2SH-P2WPKH (Nested SegWit)

P2WPKH (Native SegWit)

P2TR (Taproot)


Address Matching
Compare derived addresses with any .txt address list (millions supported using mmap optimization).

Real-time GUI Dashboard
Live table views for:

Recent mnemonic generations

Derived addresses

Match logs and activity

CPU usage, scanning speed, statistics


Multithreaded Scanning
Configurable number of threads for faster brute-force scanning using all CPU cores.

Performance Mode
Maximize CPU performance during intensive scanning sessions.

Theming Support
Light, Dark, and System-based themes with automatic font scaling and high-DPI awareness.

Auto Save & Resume
Configuration is saved across sessions, including loaded files, GUI size, and thread settings.



---

---

Usage

1. Load Address Database

Click Load Addresses and select a .txt file containing your target Bitcoin addresses (one per line).


2. Configure Scan

Choose mnemonic type: Random, 12 Words, or 24 Words.

Select address formats to scan (e.g., Legacy, Native SegWit, Taproot).

Choose thread count for parallel scanning.


3. Start Scanning

Click Start Scan. Live results will be shown in the dashboard.

If any match is found, it will be logged and saved in found_wallets.txt.


4. Stop Scanning

Click Stop Scan to gracefully terminate all threads.



---

Output

When a matching address is found, it will be saved to:

found_wallets.txt

Each entry includes:

Timestamp

Full mnemonic phrase

Address type and matched address



---

File Structure


---

Dependencies

Make sure you have Python 3.7+ installed. Then install the required libraries using pip:

pip install -r requirements.txt

requirements.txt

PyQt5
bip_utils
mnemonic
psutil

You can also install manually:

pip install PyQt5 bip-utils mnemonic psutil


---

How to Run

python bitcoin_scanner_pro.py

Or, you can package it into an executable using PyInstaller:

pip install pyinstaller
pyinstaller --noconfirm --onefile --windowed bitcoin_scanner_pro.py


---

System Requirements

OS: Windows, Linux or macOS

Python: 3.7+

RAM: Recommended 8GB+

CPU: Multi-core for parallel processing



---

License

MIT License — Feel free to modify and use.
My trc20 usdt address
TFbLR3dcZY38uG7Zpv5UB1mPvBqwrJny5e
