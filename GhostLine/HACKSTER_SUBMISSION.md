# GhostLine: AI-Powered RC Racing & Smart Arcade System

> **A Next-Generation Edge AI Racing System for the Arduino UNO Q and App Lab Competition**  
> **Category**: Gaming - Smart Multiplayer Arcade Cabinet  
> **Author**: Aditya Rathore  

---

## 🏎️ Executive Summary

**GhostLine** is a smart multiplayer RC racing arcade platform that transforms any physical tabletop or floor racetrack into a connected, augmented reality motorsport experience. Using a single overhead USB camera and edge AI, GhostLine tracks physical radio-controlled (RC) cars in real time **without requiring any physical sensors, transponders, or RFID tags on the vehicles**.

By leveraging the **dual-brain architecture of the Arduino UNO Q**:
- The **Qualcomm Dragonwing QRB2210 Linux MPU** runs real-time vehicle detection via the `arduino:video_object_detection` brick using custom Edge Impulse vehicle detection models, streams live video at port 4912, executes the **GhostLine** fastest-lap trajectory algorithm, and hosts a live WebSocket arcade dashboard with full **Driver & Car Registration and customizable target laps**.
- The **STM32U585 Microcontroller** (running Zephyr RTOS) executes deterministic, microsecond-accurate race signal sequencing, manages external starting lights/buzzers, and animates the onboard **8×13 LED matrix** (countdown digits, live lap times, and checkered victory flags).

---

## 💡 The Inspiration & The Problem

Have you ever watched an F1 broadcast and been amazed by the real-time sector deltas, or played *Gran Turismo* / *Mario Kart* and chased a translucent **"Ghost Car"** to shave tenths of a second off your lap time?

In real-world hobbyist RC racing, having this level of telemetry has historically been impossible or extremely expensive:
1. **Sensor Clutter & Weight**: Conventional timing systems require infrared transponders, magnetic loops buried under the carpet, or RFID tags that add weight to micro RC cars and demand external batteries.
2. **Zero In-Race Feedback**: Solo practice is lonely and unengaging; drivers have no way of knowing whether they are gaining or losing time mid-lap compared to their personal best.
3. **No Centralized Arcade Experience**: Casual racers want an arcade-style experience—countdown lights, buzzer beeps, live leaderboards, and checkered flags—without thousands of dollars of commercial equipment.

**GhostLine solves this completely.** With just one Arduino UNO Q and a standard webcam, any room becomes an intelligent racing arena.

---

## 🧠 Why the Arduino UNO Q? (Dual-Brain Architecture)

The Arduino UNO Q is uniquely suited for GhostLine because it solves the fundamental trade-off between **high-level AI compute** and **hard real-time embedded control**.

```
+--------------------------------------------------------------------------------+
|                                ARDUINO UNO Q                                   |
|                                                                                |
|  +-----------------------------------+    +----------------------------------+ |
|  |       QUALCOMM DRAGONWING         |    |            STM32U585             | |
|  |     Cortex-A53 @ 2.0 GHz (Linux)  |    |     Cortex-M33 (Zephyr RTOS)     | |
|  +-----------------------------------+    +----------------------------------+ |
|  | • 60 FPS Computer Vision Engine   |    | • Jitter-free Signal Timing      | |
|  | • Sub-pixel Vehicle Centroids     |    | • 8x13 Matrix Animations         | |
|  | • GhostLine Recording & Deltas    |    | • Traffic Light PWM Signals      | |
|  | • App Lab WebUI WebSocket Server  |    | • Piezo Acoustic Sound Engine    | |
|  +-----------------+-----------------+    +-----------------+----------------+ |
|                    |                                        |                  |
|                    +======== Arduino RouterBridge ==========+                  |
|                               (115200 Baud RPC)                                |
+--------------------------------------------------------------------------------+
```

### Responsibility Breakdown:
1. **Linux MPU (Qualcomm Dragonwing)**:
   - Processes 720p/1080p camera frames.
   - Extracts sub-pixel vehicle coordinates and estimates scale speed in km/h.
   - Computes virtual finish-line crossings with vector intersection math.
   - Interpolates the **GhostLine** trajectory $(x, y, t)$ to evaluate if the driver is ahead ($-0.35s$ green) or behind ($+0.42s$ red).
   - Serves the Cyberpunk Arcade HUD via App Lab's `arduino:web_ui` brick at port 7000.

2. **Microcontroller MCU (STM32U585)**:
   - Provides guaranteed, non-blocking hardware timing for the 3-2-1-GO starting lights.
   - Drives external race gantry LEDs (Pins D2-D4) and audio buzzer (Pin D5).
   - Directly manipulates the onboard 104-pixel (8×13) LED matrix with bitmapped frame buffers.

3. **Arduino RouterBridge**:
   - High-speed MessagePack RPC allows the Linux Python engine to trigger physical race alerts (`Bridge.call("trigger_countdown")`) and receive instant hardware green-flag notifications (`Bridge.notify("on_race_green_flag")`).

---

## ⚙️ How GhostLine Works (Technical Pipeline)

### 1. Sensor-Free Vehicle Tracking
The system uses a top-down camera overlooking the track. Each vehicle is equipped with a distinct neon color marker (Neon Cyan for Car 1, Neon Orange for Car 2). The Python vision engine performs:
- Color space conversion (`BGR -> HSV`).
- Morphological noise filtering.
- Contour moment analysis to calculate normalized centroids $(x, y) \in [0.0, 1.0]$.
- Moving-average trail buffer to visualize racing line breadcrumbs.

### 2. Virtual Finish Line & Debounce
Instead of physical sensors, the user defines a virtual start/finish line segment $AB$ on the dashboard. Using counter-clockwise (CCW) orientation math, the tracker evaluates whether the vector connecting a car's previous position to its current position intersects $AB$:
$$\text{Intersects}(P_{prev}, P_{curr}, A, B) = \text{True}$$
A configurable debounce threshold (default 2.0 seconds) ensures multiple detections during a single crossing are safely ignored.

### 3. The GhostLine Engine
When a driver sets a new personal best lap:
1. The exact trajectory $[(x_0, y_0, t_0), (x_1, y_1, t_1), \dots]$ is saved to disk as the active **Ghost Record**.
2. On subsequent laps, at any elapsed time $t$, the engine performs binary-search interpolation along the ghost trajectory to find the ghost's target location $(x_{ghost}, y_{ghost})$.
3. It compares the car's current position to the nearest point on the ghost line, computing an instantaneous delta:
   - $\Delta t < 0$ (Faster than ghost): Displayed in neon green.
   - $\Delta t > 0$ (Slower than ghost): Displayed in warning red.
4. The live HUD displays both the **Ghost Hologram** and a dynamic center-weighted delta meter.

### 4. Interactive Arcade Telemetry HUD
Built on HTML5 Canvas and WebSockets, the browser dashboard provides:
- **Live Augmented Track View**: Overlays virtual finish lines, ghost breadcrumbs, and live speed tags.
- **F1-Style Timing Tower**: Real-time positions (P1, P2), lap count, last lap, best lap, and gap to leader.
- **Race Director Controls**: Buttons to Start Race, Reset, Toggle Sector Hazard (Yellow Flag), and switch modes (Time Attack vs. 2-Player GP).
- **Web Audio Sound Effects**: Synthesized arcade tones for countdown beeps and victory fanfares.

---

## 🛠️ Step-by-Step Reproduction Guide

### Step 1: Hardware Assembly & Circuit
1. Mount the Arduino UNO Q onto your workspace.
2. Build the race light circuit on a solderless breadboard according to [`SCHEMATICS.md`](file:///c:/Users/Asus/Downloads/GhostLine%20Project/GhostLine/SCHEMATICS.md):
   - **Pin D2** $\to$ 220Ω $\to$ Red LED Anode $\to$ GND
   - **Pin D3** $\to$ 220Ω $\to$ Yellow LED Anode $\to$ GND
   - **Pin D4** $\to$ 220Ω $\to$ Green LED Anode $\to$ GND
   - **Pin D5** $\to$ Buzzer $(+)$ $\to$ GND
3. Connect the powered USB-C hub to the UNO Q's USB-C port, and plug your USB camera into the hub.

### Step 2: Track Preparation
1. Lay out an oval or circuit on a tabletop using tape or miniature foam barriers.
2. Mount the USB camera overhead (1.2m to 1.8m above the track) facing straight down.
3. Affix the neon cyan sticker to Car 1 and neon orange sticker to Car 2.

### Step 3: Open in Arduino App Lab
1. Launch **Arduino App Lab** on your computer.
2. Connect the Arduino UNO Q via USB-C or local network (`http://arduino-uno-q.local:7000`).
3. Open the `GhostLine` folder.
4. Click **Run** on the App Lab toolbar:
   - App Lab will automatically compile `sketch/sketch.ino` for the STM32 MCU.
   - It will start the Python application on the Qualcomm MPU.
   - The WebUI dashboard will open automatically in your browser.

### Step 4: Calibrate & Race!
1. Click **"Calibrate Line"** on the dashboard to align the virtual finish line across your straightaway.
2. Hit **"START RACE"**:
   - The STM32 MCU triggers the physical Red LED and displays "3", "2", "1" on the 8x13 LED matrix with synchronized beeps.
   - On "GO!", the Green LED lights up and the race timer starts!
3. Drive your RC car:
   - Complete Lap 1 to establish your baseline GhostLine.
   - On Lap 2, watch the Ghost Hologram and live delta meter to beat your best time!

---

## 🌍 Sustainability & Environmental Impact

1. **Elimination of Electronic Waste**: Traditional race timing demands batteries, RFID transponders, and cables for every car. GhostLine's sensor-free computer vision architecture eliminates transponder e-waste entirely.
2. **Energy-Efficient Edge Processing**: All AI vision and telemetry calculations occur locally on the low-power Qualcomm Cortex-A53 MPU (consuming less than 5W), requiring zero cloud server bandwidth or remote datacenters.
3. **Reusability**: The system works with *any* existing RC cars or miniature robotic vehicles without modifications.

---

## 🔮 Scalability & Future Roadmap

- **Autonomous Vehicle Guidance**: The same vision and ghost-path tracking algorithm can be adapted for industrial automated guided vehicles (AGVs) in smart warehouses.
- **Edge Impulse Custom Models**: Training a lightweight YOLOv8 Nano model on Edge Impulse to classify vehicle types, orientation angles, and drift dynamics.
- **Floor Projection Mapping**: Connecting an ultra-short-throw projector to the UNO Q's HDMI port to project the ghost line directly onto the physical racetrack floor!

---

## 📋 Bill of Materials & Schematics

- For the complete parts list, see [BOM.md](file:///c:/Users/Asus/Downloads/GhostLine%20Project/GhostLine/BOM.md).
- For circuit schematics and pinouts, see [SCHEMATICS.md](file:///c:/Users/Asus/Downloads/GhostLine%20Project/GhostLine/SCHEMATICS.md).
