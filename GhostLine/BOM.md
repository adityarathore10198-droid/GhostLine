# GhostLine: Complete Bill of Materials (BOM)

> **Contest Criteria**: Detail the hardware, software, and tools used (20 Points).

---

## 1. Primary Compute & Edge AI Hardware

| Component | Description / Specification | Quantity | Purpose in GhostLine | Source / Link |
| :--- | :--- | :---: | :--- | :--- |
| **Arduino UNO Q (ABX00162 / ABX00173)** | Qualcomm Dragonwing QRB2210 Quad-Core Cortex-A53 @ 2.0GHz + STM32U585 Cortex-M33 MCU, 2GB/4GB RAM, 16GB/32GB eMMC | 1 | Dual-brain controller: Linux MPU runs AI computer vision and ghost telemetry; STM32 MCU runs real-time hardware signals. | [Arduino Store](https://store.arduino.cc) |
| **USB Top-Down Camera** | 1080p / 720p USB 2.0 / USB 3.0 UVC Camera with 90°+ Wide Angle Field of View (e.g., Logitech C270 or IMX219 via CSI) | 1 | Mounts overhead to capture top-down perspective of the racetrack for sensor-free car tracking. | Amazon / Electronics Supplier |
| **USB-C Multiport Hub with Power Delivery (PD)** | USB-C hub with 1x USB-C PD input (60W+ pass-through), 2x USB-A ports, HDMI output | 1 | Supplies stable 5V 3A power to the UNO Q while connecting the USB camera and external peripherals. | [Arduino / Anker / UGREEN](https://store.arduino.cc) |
| **5V 3A USB-C Power Supply** | 15W+ (5V 3A) regulated USB-C AC wall adapter | 1 | Powers the Arduino UNO Q and connected USB accessories without brownouts during vision processing. | Standard USB-C Charger |

---

## 2. Race Physical Hardware & Embedded Signals

| Component | Description / Specification | Quantity | Purpose in GhostLine | Source / Link |
| :--- | :--- | :---: | :--- | :--- |
| **RC Race Cars** | 1:24 or 1:28 Scale Micro RC Cars (e.g., WLtoys 284131, Mini-Z, or mini toy racers) | 2 | Competitors on the track (Car 1 = Cyan, Car 2 = Orange). | Hobby Shop / Amazon |
| **High-Contrast Decals** | Neon Cyan (#00f3ff) and Neon Orange (#ff5500) circular vinyl stickers (15mm diameter) | 2 | Mounted to car roofs to provide sub-pixel centroid detection under varying lighting. | Stationery / Vinyl sheet |
| **5mm Red Diffused LED** | Forward Voltage ~1.9V - 2.1V, 20mA max | 1 | Physical race countdown light (Pins D2 on UNO Q). | Standard Component |
| **5mm Yellow Diffused LED**| Forward Voltage ~2.0V - 2.2V, 20mA max | 1 | Sector hazard / yellow caution flag (Pin D3 on UNO Q). | Standard Component |
| **5mm Green Diffused LED** | Forward Voltage ~2.8V - 3.2V, 20mA max | 1 | Race start green flag indicator (Pin D4 on UNO Q). | Standard Component |
| **Current Limiting Resistors**| 220Ω to 330Ω, 1/4W, 5% tolerance | 3 | Limits current from STM32 3.3V GPIO pins to LEDs. | Standard Resistor Kit |
| **5V Active/Piezo Buzzer** | 3.3V-compatible miniature piezo buzzer / sounder | 1 | Generates countdown beeps, lap chime, and finish fanfare (Pin D5). | Standard Component |
| **Solderless Breadboard** | 400-tie point half-size breadboard | 1 | Rapid prototyping of the starting lights and buzzer circuit. | Standard Breadboard |
| **Jumper Wires** | Male-to-Male and Male-to-Female jumper wires | 10 | Connects UNO Q classic headers to breadboard. | Standard Kit |

---

## 3. Racetrack & Mechanical Setup

| Item | Specification | Notes |
| :--- | :--- | :--- |
| **Overhead Camera Mount** | Desk clamp boom arm, gooseneck, or tripod | Suspends camera 1.2m – 1.8m above the racing surface looking straight down. |
| **Track Surface** | 1.5m x 1.0m smooth tabletop, EVA foam tiles, or poster board | White or dark grey matte surface provides the best vision contrast. |
| **Track Barriers** | Cardboard strips, 3D-printed curbs, or painter's tape | Defines track boundaries and turns. |

---

## 4. Software Stack & Tooling

| Software / Tool | Version | License | Role in System |
| :--- | :--- | :--- | :--- |
| **Arduino App Lab** | Latest (v0.5.0+) | Official Arduino | Unified IDE hosting MPU Python code, STM32 Zephyr sketch, and WebUI. |
| **Arduino RouterBridge** | v0.2.2 | Open Source (MPL-2.0) | High-speed MessagePack RPC bridge between STM32 MCU and Qualcomm MPU. |
| **Zephyr RTOS Core** | `arduino:zephyr` | Apache 2.0 | Microcontroller RTOS running deterministic timing and matrix animations. |
| **OpenCV (cv2) / NumPy** | Python 3 | Apache 2.0 / BSD | Video frame processing, HSV color thresholding, and contour analysis. |
| **Arduino WebUI Brick** | `arduino:web_ui` | Official Brick | Hosts WebSocket server on port 7000 and serves frontend arcade HUD. |
| **HTML5 Canvas / Web Audio** | Standard W3C | Open Web | Renders 60 FPS augmented overlay and generates arcade sound synthesizer. |
