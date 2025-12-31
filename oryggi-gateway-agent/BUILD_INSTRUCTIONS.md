# OryggiAI Gateway Agent - Native Windows Build Instructions

## Overview

This document explains how to build the **Native Windows Gateway Agent** - a zero-configuration solution that:

- **No Docker required** - Runs natively on Windows
- **No SQL password needed** - Uses Windows Authentication
- **Auto-discovers databases** - Shows dropdown of available databases
- **One-click setup** - Just run the installer and connect

## Prerequisites

1. **Python 3.9+** installed on build machine
2. **pip** package manager
3. **Inno Setup 6.x** (for creating installer) - https://jrsoftware.org/isinfo.php

## Build Steps

### Step 1: Install Dependencies

```powershell
cd oryggi-gateway-agent
pip install -r requirements.txt
```

### Step 2: Build Executable with PyInstaller

```powershell
python build_exe.py
```

This creates: `dist/OryggiAI-Gateway.exe`

### Step 3: Create Installer (Optional)

1. Open `installer.iss` in Inno Setup Compiler
2. Click **Build > Compile**
3. Output: `Output/OryggiAI-Gateway-Setup.exe`

## Files Created

| File | Purpose |
|------|---------|
| `gateway_agent/gui_v2.py` | Enhanced GUI with database auto-discovery |
| `gateway_agent/service.py` | Windows Service support |
| `build_exe.py` | PyInstaller build script |
| `installer.iss` | Inno Setup installer script |

## How It Works

### For End Users

1. User goes to OryggiAI dashboard
2. Adds their database (with Gateway mode)
3. Generates a gateway token
4. Downloads "Native Windows" installer
5. Runs the installer - it auto-discovers their databases
6. Selects database from dropdown
7. Clicks "Connect" - done!

### Technical Flow

```
┌─────────────────────────────────────────────────────────────┐
│  User's Windows PC                                          │
│  ┌─────────────────────────────────────────────────────┐   │
│  │  OryggiAI-Gateway.exe                               │   │
│  │  - Runs natively (no Docker)                        │   │
│  │  - Uses Windows Authentication                      │   │
│  │  - Connects to localhost SQL Server                 │   │
│  └─────────────────────┬───────────────────────────────┘   │
│                        │                                    │
│                        ▼ WebSocket (outbound)               │
└────────────────────────┼────────────────────────────────────┘
                         │
                         ▼
┌─────────────────────────────────────────────────────────────┐
│  OryggiAI Cloud (103.197.77.163:9000)                      │
│  - Receives queries                                         │
│  - Returns results to chat UI                               │
└─────────────────────────────────────────────────────────────┘
```

### Why Windows Authentication Works

When the `.exe` runs natively on Windows:
1. It inherits the logged-in user's Windows credentials
2. SQL Server accepts `Trusted_Connection=yes` connections
3. No SQL Server authentication mode changes needed
4. No TCP/IP or firewall configuration needed
5. Connection happens via local named pipes or localhost

This is why Docker fails but native works - Docker runs in an isolated container with its own user context.

## Configuration Storage

The agent stores configuration in:
```
C:\ProgramData\OryggiAI\gateway-config.json
```

This file contains:
- Gateway token
- WebSocket URL
- Selected database
- Windows Auth flag

## Troubleshooting

### "No databases found"
- Ensure SQL Server is running
- Ensure your Windows user has access to SQL Server

### "Connection failed"
- Check SQL Server is running on localhost
- Verify ODBC Driver 17 or 18 is installed

### Agent won't start with Windows
- Check Windows Services for "OryggiAI Gateway Agent"
- Run as Administrator if needed

## Version History

- **v2.0.0** - Native Windows support, zero-config, Windows Authentication
- **v1.0.0** - Docker-based (requires SQL Server configuration)
