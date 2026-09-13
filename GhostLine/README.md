# GhostLine: AI-Powered RC Racing System

Smart multiplayer RC racing arcade system powered by edge AI computer vision tracking, real-time telemetry, ghost lap comparison, and instant physical race signals on the **Arduino UNO Q & App Lab**.

![GhostLine Architecture](assets/docs_assets/banner.png)

## Quick Start in Arduino App Lab

1. Open **Arduino App Lab**.
2. Connect your **Arduino UNO Q** board.
3. Open this folder: `GhostLine`.
4. Click **Run** on the top toolbar.
5. The Arcade HUD will launch automatically at `http://localhost:7000` (or `http://<board-ip>:7000`).

## Project Structure

```
GhostLine/
├── app.yaml               # App Lab manifest (WebUI brick, ports 5001, 7000)
├── python/                # Linux MPU Python Application (Qualcomm Dragonwing)
│   ├── main.py            # Central orchestrator & simulation loop
│   ├── tracker.py         # Multi-car vision tracking & speed estimation
│   ├── ghost_engine.py    # Fastest-lap recorder & real-time delta comparator
│   └── race_manager.py    # Race states, rules, timing tower, and debouncing
├── sketch/                # STM32 Microcontroller Firmware (Zephyr RTOS)
│   ├── sketch.ino         # Bridge RPC, 8x13 LED matrix, starting lights, buzzer
│   └── sketch.yaml        # Pinned Zephyr libraries & RouterBridge dependencies
├── assets/                # Cyberpunk Arcade HUD Dashboard
│   ├── index.html         # Live track canvas, timing tower, delta meter
│   ├── style.css          # High-contrast racing telemetry styling
│   ├── app.js             # 60 FPS Canvas rendering, Web Audio synthesizer
│   └── libs/              # App Lab WebUI and Socket.io client libraries
├── BOM.md                 # Complete Bill of Materials (20 Points)
├── SCHEMATICS.md          # Circuit diagrams and pinout tables (15 Points)
└── HACKSTER_SUBMISSION.md # Full 30-Point Hackster Project Documentation
```

## Documentation

- Full Contest Submission Guide: [HACKSTER_SUBMISSION.md](HACKSTER_SUBMISSION.md)
- Complete Bill of Materials: [BOM.md](BOM.md)
- Hardware Schematics & Wiring: [SCHEMATICS.md](SCHEMATICS.md)
