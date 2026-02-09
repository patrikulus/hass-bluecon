# HASS-BlueCon

[![hacs_badge](https://img.shields.io/badge/HACS-Custom-41BDF5.svg?style=for-the-badge)](https://github.com/hacs/integration)

<div align="center">
  <img src="images/logo.svg" width="400" alt="Fermax Blue Integration Logo">
</div>

## 📑 Description

Custom Home Assistant integration for **Fermax Blue** intercoms.
Allows you to open your door directly from Home Assistant using the official Fermax API.

> **Note**: This integration replaces the previous library implementation with a direct API client based on reverse-engineered protocol details.

## ✨ Features

- **Open Door**: Unlock your building door via Home Assistant.
- **Multiple Doors**: Supports devices with multiple access points.
- **Token Management**: Handles authentication and automatic token refreshing.
- **Config Flow**: Easy setup via Home Assistant UI.

## 🚀 Installation

### Option 1: HACS (Recommended)
1. Open HACS in Home Assistant.
2. Go to "Integrations" > "Explore & Download Repositories".
3. Search for "Fermax Blue" or add this repository URL as a custom repository.
4. Click "Download".
5. Restart Home Assistant.

### Option 2: Manual
1. Copy the `custom_components/bluecon` folder to your HA `config/custom_components/` directory.
2. Restart Home Assistant.

## ⚙️ Configuration

1. Go to **Settings** > **Devices & Services**.
2. Click **Add Integration**.
3. Search for **Fermax Blue**.
4. Enter your Fermax Blue **Username** and **Password**.

## 📚 Documentation

- [Manual Testing Guide](docs/MANUAL_TESTS.md)
- [Porting Notes](docs/porting_notes.md)

## ⚠️ Disclaimer

This integration is not affiliated with Fermax. Use at your own risk.
Tested on Fermax VEO-XS WIFI 4,3" DUOX PLUS (REF: 9449).

## ☕ Support

If you find this useful, please consider starring the repository.

## ⌨️ Contributions

- [AfonsoFGarcia](https://github.com/AfonsoFGarcia) - Original Author
- [patrikulus](https://github.com/patrikulus) - Author of this fork
- [cvc90](https://github.com/cvc90) - Spanish translations
- [marcosav](https://github.com/marcosav) - Author of the [script](https://github.com/marcosav/fermax-blue-intercom) which was used for this fork
- [viseniv](https://github.com/viseniv) - Without him I probably wouldn't find the script above :)

## 📑 License
MIT License | [Read more here](LICENSE)
