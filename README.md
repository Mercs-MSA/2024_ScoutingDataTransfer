<img src="icons/mercs.png" height=180 style="display: block; margin-left: auto; margin-right: auto;"></img>

# 6369 Scouting Data Transfer

## 2025 Season

Transfer scouting form data from our data collection app to CSV files.

Collects data with a serial QR/Barcode Scanner.

## Features

- QR Code Import
- Auto/manual CSV export
- Internal SQLite Database
- Data preview
- Live data editor
- Robot picture import from PNG, JPEG, BMP, HEIC
- Robot report export powered by HTML Jinja2 Templates
- Easy configuration for import format
- Deploy [Collection App](https://github.com/Mercs-MSA/2024_ScoutingDataCollection) to tablets over ADB

## Requirements

### System Requirements

ADB must be installed to the current PATH

#### Fedora

ADB is provided with the `android-tools` package

### Python Requirements

This app requires Python 3.11 or newer

Install modules with `pip install -r requirements.txt`

### Note about Python 3.13

If using Py 3.13, `cargo`, the Rust package manager is required for building the `minify-html` dependency.

**It will take a while to install the `minify-html` dependency as it will build from source**

You may also need the `--ignore-requires-python` pip argument to successfully install the `pyqtdarktheme` fork.
