// ============================================================================
// GhostLine: AI-Powered RC Racing - STM32 MCU Firmware
// Hardware: Arduino UNO Q (STM32U585 running Zephyr RTOS)
// Description: Real-time race timing controller, physical race light sequencing,
//              8x13 LED matrix animation engine, and Bridge RPC interface.
// ============================================================================

#include <Arduino.h>
#include <Arduino_RouterBridge.h>

// Onboard 8x13 LED matrix low-level driver
extern "C" void matrixBegin();
extern "C" void matrixWrite(const uint32_t* buf);

// ----------------------------------------------------------------------------
// Pin Definitions (3.3V Logic)
// ----------------------------------------------------------------------------
const int PIN_RED_LIGHT    = 2;    // Race Start Light - Red
const int PIN_YELLOW_LIGHT = 3;    // Sector Hazard / Caution Light - Yellow
const int PIN_GREEN_LIGHT  = 4;    // Track Clear / Race On - Green
const int PIN_BUZZER       = 5;    // Active/Piezo Buzzer for acoustic cues

// Note: On Arduino UNO Q, LED_BUILTIN is inverted: LOW = ON, HIGH = OFF
#define SET_BUILTIN_LED(state) digitalWrite(LED_BUILTIN, (state) ? LOW : HIGH)

// ----------------------------------------------------------------------------
// Race States
// ----------------------------------------------------------------------------
enum RaceState {
    STATE_IDLE,
    STATE_COUNTDOWN,
    STATE_RACING,
    STATE_HAZARD,
    STATE_FINISH
};

volatile RaceState currentRaceState = STATE_IDLE;

// Countdown sequence control
int countdownStep = 0;           // 3, 2, 1, 0 (GO)
unsigned long lastCountdownTick = 0;
bool countdownActive = false;

// LED Matrix animation variables
unsigned long lastMatrixUpdate = 0;
int animFrame = 0;
String scrollMessage = "GHOSTLINE";
int scrollOffset = 13;
bool scrollActive = false;

// ----------------------------------------------------------------------------
// 4x6 Pixel Font for 8x13 LED Matrix (0-9, A-Z, Space, Period)
// ----------------------------------------------------------------------------
static const byte font_digits[10][6] = {
    {0b0110, 0b1001, 0b1001, 0b1001, 0b1001, 0b0110}, // 0
    {0b0010, 0b0110, 0b0010, 0b0010, 0b0010, 0b0111}, // 1
    {0b0110, 0b1001, 0b0001, 0b0010, 0b0100, 0b1111}, // 2
    {0b1110, 0b0001, 0b0110, 0b0001, 0b0001, 0b1110}, // 3
    {0b0010, 0b0110, 0b1010, 0b1111, 0b0010, 0b0010}, // 4
    {0b1111, 0b1000, 0b1110, 0b0001, 0b0001, 0b1110}, // 5
    {0b0110, 0b1000, 0b1110, 0b1001, 0b1001, 0b0110}, // 6
    {0b1111, 0b0001, 0b0010, 0b0100, 0b0100, 0b0100}, // 7
    {0b0110, 0b1001, 0b0110, 0b1001, 0b1001, 0b0110}, // 8
    {0b0110, 0b1001, 0b1001, 0b0111, 0b0001, 0b0110}  // 9
};

// ----------------------------------------------------------------------------
// LED Matrix Helper Functions
// ----------------------------------------------------------------------------
void clearMatrix(uint32_t* frame) {
    frame[0] = 0;
    frame[1] = 0;
    frame[2] = 0;
    frame[3] = 0;
}

void setPixel(uint32_t* frame, int row, int col, bool on) {
    if (row < 0 || row >= 8 || col < 0 || col >= 13) return;
    int bitPos = row * 13 + col;
    if (on) {
        frame[bitPos / 32] |= (1UL << (bitPos % 32));
    } else {
        frame[bitPos / 32] &= ~(1UL << (bitPos % 32));
    }
}

void drawDigit(uint32_t* frame, int digit, int startCol, int startRow) {
    if (digit < 0 || digit > 9) return;
    for (int r = 0; r < 6; r++) {
        byte rowByte = font_digits[digit][r];
        for (int c = 0; c < 4; c++) {
            if (rowByte & (1 << (3 - c))) {
                setPixel(frame, startRow + r, startCol + c, true);
            }
        }
    }
}

// Draw Checkered Flag pattern for victory/finish
void drawCheckeredFlag(uint32_t* frame, int phase) {
    clearMatrix(frame);
    for (int r = 0; r < 8; r++) {
        for (int c = 0; c < 13; c++) {
            bool on = (((r / 2) + (c / 2) + phase) % 2 == 0);
            setPixel(frame, r, c, on);
        }
    }
}

// Draw traffic light countdown on matrix
void drawCountdownMatrix(uint32_t* frame, int step) {
    clearMatrix(frame);
    if (step == 3) {
        // Red lights: 3 columns on left
        drawDigit(frame, 3, 5, 1);
        for (int r = 1; r < 7; r++) {
            setPixel(frame, r, 0, true);
            setPixel(frame, r, 1, true);
        }
    } else if (step == 2) {
        drawDigit(frame, 2, 5, 1);
        for (int r = 1; r < 7; r++) {
            setPixel(frame, r, 0, true);
            setPixel(frame, r, 1, true);
            setPixel(frame, r, 11, true);
            setPixel(frame, r, 12, true);
        }
    } else if (step == 1) {
        drawDigit(frame, 1, 5, 1);
        for (int r = 0; r < 8; r++) {
            setPixel(frame, r, 0, true);
            setPixel(frame, r, 1, true);
            setPixel(frame, r, 11, true);
            setPixel(frame, r, 12, true);
        }
    } else if (step == 0) {
        // "GO" pattern - all perimeter lit
        for (int c = 0; c < 13; c++) {
            setPixel(frame, 0, c, true);
            setPixel(frame, 7, c, true);
        }
        for (int r = 0; r < 8; r++) {
            setPixel(frame, r, 0, true);
            setPixel(frame, r, 12, true);
        }
        // Center G and O
        // G
        setPixel(frame, 2, 3, true); setPixel(frame, 2, 4, true); setPixel(frame, 2, 5, true);
        setPixel(frame, 3, 3, true);
        setPixel(frame, 4, 3, true); setPixel(frame, 4, 5, true);
        setPixel(frame, 5, 3, true); setPixel(frame, 5, 4, true); setPixel(frame, 5, 5, true);
        // O
        setPixel(frame, 2, 7, true); setPixel(frame, 2, 8, true); setPixel(frame, 2, 9, true);
        setPixel(frame, 3, 7, true); setPixel(frame, 3, 9, true);
        setPixel(frame, 4, 7, true); setPixel(frame, 4, 9, true);
        setPixel(frame, 5, 7, true); setPixel(frame, 5, 8, true); setPixel(frame, 5, 9, true);
    }
}

// ----------------------------------------------------------------------------
// Audio / Buzzer Signals
// ----------------------------------------------------------------------------
void beepTone(int durationMs, int pulseMs) {
    unsigned long start = millis();
    while (millis() - start < (unsigned long)durationMs) {
        digitalWrite(PIN_BUZZER, HIGH);
        delayMicroseconds(pulseMs);
        digitalWrite(PIN_BUZZER, LOW);
        delayMicroseconds(pulseMs);
    }
}

void playCountdownBeep(bool highPitch) {
    if (highPitch) {
        beepTone(350, 400); // 1250 Hz high GO tone
    } else {
        beepTone(180, 800); // 625 Hz low warning tone
    }
}

void playVictoryMelody() {
    beepTone(100, 500);
    delay(50);
    beepTone(100, 400);
    delay(50);
    beepTone(250, 300);
}

// ----------------------------------------------------------------------------
// Bridge RPC Exposed Functions (Callable from Python MPU)
// ----------------------------------------------------------------------------

// Set high-level race state
void setRaceState(String state) {
    state.trim();
    state.toUpperCase();

    if (state == "IDLE") {
        currentRaceState = STATE_IDLE;
        countdownActive = false;
        digitalWrite(PIN_RED_LIGHT, LOW);
        digitalWrite(PIN_YELLOW_LIGHT, LOW);
        digitalWrite(PIN_GREEN_LIGHT, LOW);
        SET_BUILTIN_LED(false);

        uint32_t frame[4];
        clearMatrix(frame);
        matrixWrite(frame);
    } 
    else if (state == "COUNTDOWN") {
        currentRaceState = STATE_COUNTDOWN;
        countdownStep = 3;
        countdownActive = true;
        lastCountdownTick = millis();

        digitalWrite(PIN_RED_LIGHT, HIGH);
        digitalWrite(PIN_YELLOW_LIGHT, LOW);
        digitalWrite(PIN_GREEN_LIGHT, LOW);

        uint32_t frame[4];
        drawCountdownMatrix(frame, 3);
        matrixWrite(frame);
        playCountdownBeep(false);
    } 
    else if (state == "RACING") {
        currentRaceState = STATE_RACING;
        countdownActive = false;
        digitalWrite(PIN_RED_LIGHT, LOW);
        digitalWrite(PIN_YELLOW_LIGHT, LOW);
        digitalWrite(PIN_GREEN_LIGHT, HIGH);
        SET_BUILTIN_LED(true);
    } 
    else if (state == "HAZARD") {
        currentRaceState = STATE_HAZARD;
        digitalWrite(PIN_RED_LIGHT, LOW);
        digitalWrite(PIN_YELLOW_LIGHT, HIGH);
        digitalWrite(PIN_GREEN_LIGHT, LOW);
    } 
    else if (state == "FINISH") {
        currentRaceState = STATE_FINISH;
        countdownActive = false;
        digitalWrite(PIN_RED_LIGHT, LOW);
        digitalWrite(PIN_YELLOW_LIGHT, LOW);
        digitalWrite(PIN_GREEN_LIGHT, LOW);
        playVictoryMelody();
    }
}

// Trigger start sequence explicitly
void triggerCountdown() {
    setRaceState("COUNTDOWN");
}

// Display lap time on LED matrix (e.g., "4.82")
void displayLapTime(String lapStr) {
    scrollMessage = "LAP " + lapStr + "S";
    scrollOffset = 13;
    scrollActive = true;
}

// Play sound cues on demand
void playBuzzerCue(String cueType) {
    if (cueType == "lap") {
        beepTone(100, 600);
    } else if (cueType == "finish") {
        playVictoryMelody();
    } else if (cueType == "hazard") {
        beepTone(200, 1000);
    }
}

// Diagnostic status call
String getHardwareStatus() {
    String status = "{\"state\":";
    status += String((int)currentRaceState);
    status += ",\"uptime\":";
    status += String(millis());
    status += "}";
    return status;
}

// ----------------------------------------------------------------------------
// Setup & Main Loop
// ----------------------------------------------------------------------------
void setup() {
    // Configure race signal output pins
    pinMode(PIN_RED_LIGHT, OUTPUT);
    pinMode(PIN_YELLOW_LIGHT, OUTPUT);
    pinMode(PIN_GREEN_LIGHT, OUTPUT);
    pinMode(PIN_BUZZER, OUTPUT);
    pinMode(LED_BUILTIN, OUTPUT);

    digitalWrite(PIN_RED_LIGHT, LOW);
    digitalWrite(PIN_YELLOW_LIGHT, LOW);
    digitalWrite(PIN_GREEN_LIGHT, LOW);
    digitalWrite(PIN_BUZZER, LOW);
    SET_BUILTIN_LED(false);

    // Initialize 8x13 LED matrix
    matrixBegin();
    uint32_t initFrame[4];
    clearMatrix(initFrame);
    matrixWrite(initFrame);

    // Initialize RouterBridge
    Bridge.begin();

    // Register RPC endpoints for Linux MPU
    Bridge.provide("set_race_state", setRaceState);
    Bridge.provide("trigger_countdown", triggerCountdown);
    Bridge.provide("display_lap_time", displayLapTime);
    Bridge.provide("play_buzzer_cue", playBuzzerCue);
    Bridge.provide("get_hardware_status", getHardwareStatus);

    // Initial boot animation: quick flash of green and matrix
    digitalWrite(PIN_GREEN_LIGHT, HIGH);
    delay(100);
    digitalWrite(PIN_GREEN_LIGHT, LOW);
}

void loop() {
    unsigned long now = millis();

    // 1. Handle Automatic Countdown Tick
    if (countdownActive) {
        if (now - lastCountdownTick >= 1000) {
            lastCountdownTick = now;
            countdownStep--;

            if (countdownStep > 0) {
                // Steps 2 and 1: Red lights still on
                digitalWrite(PIN_RED_LIGHT, HIGH);
                digitalWrite(PIN_GREEN_LIGHT, LOW);
                uint32_t frame[4];
                drawCountdownMatrix(frame, countdownStep);
                matrixWrite(frame);
                playCountdownBeep(false);
            } else if (countdownStep == 0) {
                // GO! Green lights on, high pitch beep
                digitalWrite(PIN_RED_LIGHT, LOW);
                digitalWrite(PIN_GREEN_LIGHT, HIGH);
                uint32_t frame[4];
                drawCountdownMatrix(frame, 0);
                matrixWrite(frame);
                playCountdownBeep(true);

                // Notify Python MPU that the race has officially started!
                Bridge.notify("on_race_green_flag", (int)now);
                currentRaceState = STATE_RACING;
            } else {
                // End of GO animation
                countdownActive = false;
            }
        }
    }

    // 2. State-Specific Matrix Animations
    if (currentRaceState == STATE_FINISH) {
        // Alternate checkered flag every 180ms
        if (now - lastMatrixUpdate >= 180) {
            lastMatrixUpdate = now;
            animFrame = (animFrame + 1) % 2;
            uint32_t frame[4];
            drawCheckeredFlag(frame, animFrame);
            matrixWrite(frame);
        }
    } 
    else if (currentRaceState == STATE_HAZARD) {
        // Flash yellow hazard lights every 250ms
        if (now - lastMatrixUpdate >= 250) {
            lastMatrixUpdate = now;
            animFrame = (animFrame + 1) % 2;
            digitalWrite(PIN_YELLOW_LIGHT, animFrame ? HIGH : LOW);
            
            uint32_t frame[4];
            clearMatrix(frame);
            if (animFrame) {
                // Exclamation mark in center
                for (int r = 1; r <= 4; r++) setPixel(frame, r, 6, true);
                setPixel(frame, 6, 6, true);
            }
            matrixWrite(frame);
        }
    }
    else if (currentRaceState == STATE_RACING && !countdownActive) {
        // Idle heartbeat or subtle racing scanline
        if (now - lastMatrixUpdate >= 80) {
            lastMatrixUpdate = now;
            animFrame = (animFrame + 1) % 13;
            uint32_t frame[4];
            clearMatrix(frame);
            for (int r = 0; r < 8; r++) {
                setPixel(frame, r, animFrame, true);
            }
            matrixWrite(frame);
        }
    }

    delay(5);
}
