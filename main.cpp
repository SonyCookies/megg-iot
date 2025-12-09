#include <Arduino.h>
#include <Servo.h>
#include <HX711.h>
#include <EEPROM.h>

// ==================== DEVELOPMENT FLAGS ====================
// Set to true to allow 'START' command even if HX711 is not calibrated (for demonstration/testing)
#define ALLOW_UNCALIBRATED_START true

// ==================== FUNCTION DECLARATIONS ====================
void handleSerialCommands();
void startSystem();
void stopSystem();
void homeServo();
void runContinuousSorting();
void sendStatus();
int classifyEgg(); // Returns index (0=BAD, 1=SMALL, 2=MEDIUM, 3=LARGE)
void calibrateUno();
void calibrateHX711(float known_weight = 23.0f);
void calibrateNema23();
void calibrateLoaderServo();
void calibrateMG996R();
unsigned long calculateStepDelay(int currentStep, int totalSteps); // Trapezoidal profile helper

// ==================== PIN DEFINITIONS ====================
#define LOADER_SERVO_PIN 6
#define MG996R_PIN 5
#define HX711_DT_PIN A0
#define HX711_SCK_PIN A1
#define NEMA23_STEP_PIN 3
#define NEMA23_DIR_PIN 4
#define NEMA23_ENABLE_PIN 2

// ==================== EEPROM ADDRESSES ====================
#define HX711_OFFSET_ADDR 0
#define HX711_SCALE_ADDR sizeof(long)

// ==================== HARDWARE OBJECTS ====================
Servo loader;
Servo mg996r;
HX711 hx711;

// ==================== SYSTEM VARIABLES ====================
bool systemActive = false;
bool calibrationMode = false;
bool stopRequested = false; // Graceful stop flag: finish current cycle before stopping
bool plainMode = false;

// Servo positions
const int LOADER_HOME_POS = 160; // Loader MG996R Home position (Egg Holder Up/Safe)
const int LOADER_LOAD_POS = 100;   // Loader MG996R Load position (Egg Holder Down/Release)
const int MG996R_HOME_POS = 90; // MG996R Neutral/Home position (Only used on HOME/STOP)
// MG996R Position Index: 0=BAD, 1=SMALL, 2=MEDIUM, 3=LARGE
const int MG996R_POSITIONS[4] = {15, 70, 125, 170};

// Load cell calibration (defaults updated to latest accurate values)
float hx711_scale = 1840.353881f;
long hx711_offset = 119011;
bool hx711_calibrated = false;

// Egg Sorting Weight Ranges (g) - **THESE ARE SET BY SET_RANGES COMMAND**
float smallMin = 35.0f;
float smallMax = 42.0f;
float mediumMin = 43.0f;
float mediumMax = 50.0f;
float largeMin = 51.0f;
float largeMax = 58.0f;

// Stepper control
int nema23_position = 0;
const int NEMA23_STEPS = 1600; // Steps for one index movement

// Stepper non-blocking control
unsigned long lastStepTime = 0; // Tracks the last time the step pin was toggled (micros)
const unsigned long STEP_PULSE_DELAY_US = 800; // Base time for HIGH or LOW state of the pulse (800us HIGH + 800us LOW)
int stepsRemainingInMove = 0; // Counter for the current move
int currentStepInMove = 0; // Tracks current step number (for trapezoidal profile)

// Trapezoidal speed profile parameters
const unsigned long MIN_STEP_DELAY_US = 400;  // Maximum speed (fastest)
const unsigned long MAX_STEP_DELAY_US = 1200; // Minimum speed (slowest, at start/end)
const int ACCEL_STEPS = 200;  // Number of steps to accelerate over
const int DECEL_STEPS = 200;  // Number of steps to decelerate over

// Weight storage
float currentEggWeight = 0.0f;
// New variable for quality check (TRUE if quality is confirmed GOOD)
bool eggQualityIsGood = false;
int weightClassificationIndex = 0; // Stores the size index (0-3)

// --- NON-BLOCKING STATE MACHINE ---
// REMOVED MG996R_RETURN_INIT and MG996R_WAIT_HOME to prevent homing in every cycle
enum SortingStep {
    STEP_IDLE,
    STEP_LOAD_EGG_DOWN,
    STEP_LOAD_EGG_UP,
    STEP_MOVE_TO_SCALE_INIT,
    STEP_STEPPER_MOVING,
    STEP_WEIGH_WAIT,
    STEP_WEIGH_READ,
    STEP_WAIT_FOR_QUALITY, // NEW STEP: Wait for signal from frontend after image capture
    STEP_SORT_ACTUATE,    // 1. Move MG996R to target position
    STEP_EGG_DROP_WAIT    // 2. Wait for TIME_SORT_ACTUATE (Egg drop time). MG996R stays put.
};
SortingStep currentSortingStep = STEP_IDLE;
unsigned long stepStartTime = 0;

// Timing constants (in ms)
const unsigned long TIME_SERVO_ACTUATE = 1500; // Time for SG90 to move fully
const unsigned long TIME_SETTLE_VIBRATION = 500; // Wait after stepper stops
const unsigned long TIME_SORT_ACTUATE = 2000;   // Time for egg to drop into bin
// const unsigned long TIME_MG996R_RETURN = 500; // No longer needed as it doesn't return in cycle

// ==================== SERIAL HANDLER VARIABLES ====================
char inputBuffer[80];
byte inputIndex = 0;

// ==================== SETUP ====================
void setup() {
    Serial.begin(115200);
    Serial.println(F("MEGG Hardware Control System Starting..."));

    loader.attach(LOADER_SERVO_PIN);
    mg996r.attach(MG996R_PIN);
    hx711.begin(HX711_DT_PIN, HX711_SCK_PIN);
    hx711.set_gain(128); // Match working sketch default gain

    EEPROM.get(HX711_OFFSET_ADDR, hx711_offset);
    EEPROM.get(HX711_SCALE_ADDR, hx711_scale);

    if (isnan(hx711_scale) || fabs(hx711_scale) < 0.0001f) {
        hx711_scale = 1840.353881f;
        hx711_offset = 119011;
        Serial.println(F("Using default HX711 scale 1840.353881, offset 119011"));
    }

    hx711.set_offset(hx711_offset);
    hx711.set_scale(hx711_scale);
    hx711_calibrated = (fabs(hx711_scale) > 0.0001f);

    // Stepper pins
    pinMode(NEMA23_STEP_PIN, OUTPUT);
    pinMode(NEMA23_DIR_PIN, OUTPUT);
    pinMode(NEMA23_ENABLE_PIN, OUTPUT);
    digitalWrite(NEMA23_ENABLE_PIN, HIGH); // disable by default

    loader.write(LOADER_HOME_POS);
    mg996r.write(MG996R_HOME_POS);
    delay(1000);

    Serial.println(F("System Ready!"));
    Serial.println(F("Commands: START [ranges], STOP, HOME, STATUS, SET_RANGES <s_min> <s_max> <m_min> <m_max> <l_min> <l_max>"));
    Serial.println(F("Calibration: CALIBRATE_UNO, CALIBRATE_HX711 [weight], CALIBRATE_NEMA23, CALIBRATE_LOADER, CALIBRATE_MG996R"));
}

// ==================== MAIN LOOP ====================
void loop() {
    // CRITICAL: Always handle serial commands first for responsiveness (especially STOP)
    handleSerialCommands();

    // Non-blocking sorting flow
    if (systemActive) {
        runContinuousSorting();
    }
}

// ==================== SERIAL COMMANDS ====================
void handleSerialCommands() {
    while (Serial.available()) {
        char inChar = (char)Serial.read();
        if (inChar == '\n' || inChar == '\r') {
            inputBuffer[inputIndex] = '\0';
            if (inputIndex > 0) {
                char cmdBuf[80];
                strncpy(cmdBuf, inputBuffer, sizeof(cmdBuf));
                cmdBuf[sizeof(cmdBuf) - 1] = '\0';
                inputIndex = 0;

                char *p = cmdBuf;
                while (*p == ' ') p++;

                Serial.print(F("CMD: "));
                Serial.println(p);

                if (strncmp(p, "CALIBRATE_HX711", 15) == 0) {
                    char *arg = p + 15;
                    while (*arg == ' ') arg++;
                    if (*arg != '\0') calibrateHX711(atof(arg));
                    else calibrateHX711();
                }

                // Handle START command
                else if (strcmp(p, "START") == 0 || strncmp(p, "START ", 6) == 0) {
                  float s_min, s_max, m_min, m_max, l_min, l_max;

                  if (sscanf(p + 5, "%f %f %f %f %f %f",
                                              &s_min, &s_max,
                                              &m_min, &m_max,
                                              &l_min, &l_max) == 6) {

                        smallMin = s_min;
                        smallMax = s_max;
                        mediumMin = m_min;
                        mediumMax = m_max;
                        largeMin = l_min;
                        largeMax = l_max;
                        Serial.println(F("CONFIG_UPDATED: Egg size ranges set successfully."));

                    } else if (strlen(p) > 5 && strncmp(p+5, " ", 1) != 0) {
                        Serial.println(F("ERROR: START with ranges requires 6 float arguments. Using current ranges."));
                    }

                    plainMode = false;
                    startSystem();

                }

                else if (strncmp(p, "START_PLAIN", 11) == 0) {
                    float s_min, s_max, m_min, m_max, l_min, l_max;

                    if (sscanf(p + 11, "%f %f %f %f %f %f",
                                            &s_min, &s_max,
                                            &m_min, &m_max,
                                            &l_min, &l_max) == 6) {

                        smallMin = s_min;
                        smallMax = s_max;
                        mediumMin = m_min;
                        mediumMax = m_max;
                        largeMin = l_min;
                        largeMax = l_max;
                        Serial.println(F("CONFIG_UPDATED: Egg size ranges set successfully."));

                    } else if (strlen(p) > 11 && strncmp(p+11, " ", 1) != 0) {
                        Serial.println(F("ERROR: START_PLAIN with ranges requires 6 float arguments. Using current ranges."));
                    }

                    plainMode = true;
                    startSystem();

                }

                else if (strcmp(p, "STOP") == 0) {
                    // Graceful stop: mark request and let the current cycle finish
                    if (systemActive) {
                        stopRequested = true;
                        Serial.println(F("STOP_REQUESTED: Will stop after current cycle."));
                    } else {
                        Serial.println(F("SYSTEM_WARNING: System already stopped."));
                    }
                }

                else if (strcmp(p, "HOME") == 0) homeServo();
                else if (strcmp(p, "STATUS") == 0) sendStatus();
                
                // NEW: Handle QUALITY command from frontend
                else if (strncmp(p, "QUALITY", 7) == 0) {
                    if (currentSortingStep != STEP_WAIT_FOR_QUALITY) {
                        Serial.println(F("ERROR: QUALITY command ignored. Not in STEP_WAIT_FOR_QUALITY."));
                        continue;
                    }
                    char *quality_arg = p + 7;
                    while (*quality_arg == ' ') quality_arg++;

                    if (strncmp(quality_arg, "GOOD", 4) == 0) {
                        eggQualityIsGood = true;
                        Serial.println(F("QUALITY_RECEIVED: GOOD. Proceeding to sort."));
                        currentSortingStep = STEP_SORT_ACTUATE;
                    } else if (strncmp(quality_arg, "BAD", 3) == 0) {
                        eggQualityIsGood = false;
                        Serial.println(F("QUALITY_RECEIVED: BAD (Cracked). Routing to BAD bin."));
                        currentSortingStep = STEP_SORT_ACTUATE;
                    } else {
                        Serial.println(F("ERROR: QUALITY command requires GOOD or BAD argument."));
                    }
                }

                // Command to set configuration ranges for sorting
                else if (strncmp(p, "SET_RANGES", 10) == 0) {
                    float s_min, s_max, m_min, m_max, l_min, l_max;
                    if (sscanf(p + 10, "%f %f %f %f %f %f",
                                            &s_min, &s_max,
                                            &m_min, &m_max,
                                            &l_min, &l_max) == 6) {
                        smallMin = s_min;
                        smallMax = s_max;
                        mediumMin = m_min;
                        mediumMax = m_max;
                        largeMin = l_min;
                        largeMax = l_max;
                        Serial.println(F("CONFIG_UPDATED: Egg size ranges set successfully."));
                    } else {
                        Serial.println(F("ERROR: SET_RANGES usage: SET_RANGES <s_min> <s_max> <m_min> <m_max> <l_min> <l_max>"));
                    }
                }

                else if (strcmp(p, "CALIBRATE_UNO") == 0) calibrateUno();
                else if (strcmp(p, "CALIBRATE_NEMA23") == 0) calibrateNema23();
                else if (strcmp(p, "CALIBRATE_SG90") == 0) calibrateLoaderServo();
                else if (strcmp(p, "CALIBRATE_LOADER") == 0) calibrateLoaderServo();
                else if (strcmp(p, "CALIBRATE_MG996R") == 0) calibrateMG996R();

                else if (strcmp(p, "RUN") == 0) startSystem();

                // FIX 1: Ignore known CMD: markers to clean up logs
                else if (strncmp(p, "CMD:", 4) == 0) { /* ignore marker from backend/echo */ }

                else Serial.println(F("ERROR: Unknown command"));
            }
        } else if (inputIndex < sizeof(inputBuffer) - 1) {
            inputBuffer[inputIndex++] = inChar;
        }
    }
}

// ==================== SYSTEM CONTROL ====================
void startSystem() {
    if (systemActive) {
        Serial.println(F("SYSTEM_WARNING: System already active."));
        return;
    }

    // FIX 3: Check calibration and apply development bypass flag
    if (!hx711_calibrated) {
        if (!ALLOW_UNCALIBRATED_START) {
            Serial.println(F("SYSTEM_ERROR: Load cell not calibrated. Cannot start sorting."));
            return;
        } else {
            Serial.println(F("SYSTEM_WARNING: Starting uncalibrated (ALLOW_UNCALIBRATED_START=true). Using test weight injection."));
        }
    }

    systemActive = true;
    digitalWrite(NEMA23_ENABLE_PIN, LOW); // Enable Stepper Motor
    currentSortingStep = STEP_LOAD_EGG_DOWN; // Start the first step
    stepStartTime = millis();
    Serial.println(F("SYSTEM_STARTED"));
}

void stopSystem() {
    if (!systemActive) {
        Serial.println(F("SYSTEM_WARNING: System already stopped."));
        return;
    }
    // If the stepper is mid-move, defer stopping until move completes
    if (stepsRemainingInMove > 0) {
        Serial.println(F("STOP_DEFERRED: Completing current stepper move before stopping."));
        stopRequested = true; // ensure graceful stop after cycle
        return;
    }
    // Halt motor activity immediately
    digitalWrite(NEMA23_ENABLE_PIN, HIGH); // Disable Stepper Motor

    // Reset non-blocking stepper variables
    stepsRemainingInMove = 0;
    currentStepInMove = 0;

    homeServo(); // **MG996R returns to home here on STOP**

    systemActive = false;
    currentSortingStep = STEP_IDLE; // Reset sorting flow

    Serial.println(F("SYSTEM_STOPPED"));
    Serial.println(F("STOP_ACK"));
}

// ==================== SERVO CONTROL ====================
void homeServo() {
    loader.write(LOADER_HOME_POS);
    mg996r.write(MG996R_HOME_POS);
    Serial.println(F("SERVOS_HOMED"));
}

// ==================== EGG SORTING LOGIC (UPDATED) ====================
/**
 * @brief Classifies the egg based on the measured currentEggWeight and returns the MG996R position.
 * The logic is updated to classify weights outside the defined max/min bounds into the largest/smallest categories.
 * NOTE: This function now returns the classification INDEX (0-3), NOT the servo position.
 */
int classifyEgg() {
    const char* sizeLabel = "BAD (GAP)";
    int targetPositionIndex = 0; // Default to 0 (BAD position)

    if (currentEggWeight < 0) {
        sizeLabel = "BAD (INVALID)";
        targetPositionIndex = 0; 
        Serial.println(F("SORT: Weight invalid. Discarding egg (BAD bin)."));
    }
    // 1. Check for LARGE or OVER-MAX (New logic: anything >= largeMin is LARGE)
    else if (currentEggWeight >= largeMin) {
        targetPositionIndex = 3;
        if (currentEggWeight > largeMax) {
            sizeLabel = "LARGE (OVER_MAX)";
        } else {
            sizeLabel = "LARGE";
        }
    }
    // 2. Check for MEDIUM
    else if (currentEggWeight >= mediumMin && currentEggWeight <= mediumMax) {
        targetPositionIndex = 2;
        sizeLabel = "MEDIUM";
    }
    // 3. Check for SMALL (New logic: anything < mediumMin but > 0)
    else if (currentEggWeight >= smallMin) { 
        // This covers [smallMin, smallMax] AND the gap (smallMax, mediumMin). 
        // We keep the gap as BAD/GAP (default index 0) and only match the intended small range.
        if (currentEggWeight <= smallMax) {
             targetPositionIndex = 1;
             sizeLabel = "SMALL";
        } else {
             // This is the gap: smallMax < W < mediumMin
             sizeLabel = "BAD (GAP)";
             targetPositionIndex = 0; 
        }
    }
    // 4. Check for UNDER-MIN (New logic: classify as SMALL)
    else if (currentEggWeight > 0 && currentEggWeight < smallMin) {
        targetPositionIndex = 1;
        sizeLabel = "SMALL (UNDER_MIN)";
    }
    // 5. Default/Gaps: The only other case is the gap between Medium and Large (mediumMax < W < largeMin)
    else {
        sizeLabel = "BAD (GAP)";
        targetPositionIndex = 0;
    }

    Serial.print(F("SORT: Egg ("));
    Serial.print(currentEggWeight, 2);
    Serial.print(F("g) classified as "));
    Serial.println(sizeLabel);

    // Final check for the gap between Medium and Large (50.0 < W < 51.0 in default config)
    // The previous logic covers all cases correctly:
    // Case 1 handles W >= 51.0 (LARGE/OVER_MAX)
    // Case 2 handles W in [43.0, 50.0] (MEDIUM)
    // Case 3 handles W in [35.0, 42.0] (SMALL) and also the gap [42.0, 43.0] as BAD (GAP)
    // Case 4 handles W in (0, 35.0) (SMALL/UNDER_MIN)
    // The final else {} handles the remaining gap (50.0 < W < 51.0 in default config) as BAD (GAP)

    return targetPositionIndex; // RETURN INDEX (0-3)
}

// ==================== SYSTEM FLOW (NON-BLOCKING) ====================
/**
 * @brief Executes the full MEGG system flow using a non-blocking state machine.
 */
void runContinuousSorting() {
    unsigned long currentTime = millis();
    unsigned long currentMicroseconds = micros();

    switch (currentSortingStep) {

        case STEP_LOAD_EGG_DOWN:
            // 1. SG90: Move down (release egg)
            loader.write(LOADER_LOAD_POS);
            Serial.println(F("STEP: Load egg down."));
            stepStartTime = currentTime;
            currentSortingStep = STEP_LOAD_EGG_UP;
            break;

        case STEP_LOAD_EGG_UP:
            // 2. Wait for move time, then move up (home)
            if (currentTime - stepStartTime >= TIME_SERVO_ACTUATE) {
                loader.write(LOADER_HOME_POS);
                Serial.println(F("STEP: Load egg up (home). EGG_LOADED."));
                // Move directly to NEMA23 move initialization
                currentSortingStep = STEP_MOVE_TO_SCALE_INIT;
            }
            break;

        case STEP_MOVE_TO_SCALE_INIT:
            // Initialize NEMA23 non-blocking move
            Serial.println(F("STEP: NEMA23 starting non-blocking forward move..."));
            digitalWrite(NEMA23_DIR_PIN, HIGH); // Set direction FORWARD
            digitalWrite(NEMA23_ENABLE_PIN, LOW); // Enable motor

            stepsRemainingInMove = NEMA23_STEPS;
            currentStepInMove = 0; // Reset step counter for trapezoidal profile
            lastStepTime = currentMicroseconds;
            currentSortingStep = STEP_STEPPER_MOVING;
            // No break: Fall through to start moving immediately in the same loop cycle

        case STEP_STEPPER_MOVING: {
            // Execute non-blocking steps using micros() timing with trapezoidal speed profile
            if (stepsRemainingInMove > 0) {
                // Calculate dynamic delay based on trapezoidal profile
                unsigned long currentDelay = calculateStepDelay(currentStepInMove, NEMA23_STEPS);
                
                // Check if it's time for the next pulse state (HIGH or LOW)
                if (currentMicroseconds - lastStepTime >= currentDelay) {

                    if (digitalRead(NEMA23_STEP_PIN) == LOW) {
                        // Start HIGH pulse
                        digitalWrite(NEMA23_STEP_PIN, HIGH);
                        lastStepTime = currentMicroseconds;
                    } else {
                        // End LOW pulse (a full step is complete)
                        digitalWrite(NEMA23_STEP_PIN, LOW);
                        lastStepTime = currentMicroseconds;
                        stepsRemainingInMove--;
                        currentStepInMove++; // Increment step counter for profile calculation
                    }
                }
                // IMPORTANT: Exit the switch (and runContinuousSorting) immediately to return control
                // to loop() for handleSerialCommands()
                return;
            } else {
                // Move finished
                digitalWrite(NEMA23_ENABLE_PIN, HIGH); // Disable motor
                Serial.println(F("STEP: NEMA23 finished forward move (Non-Blocking)."));
                stepStartTime = currentTime; // Start timing for settling
                currentSortingStep = STEP_WEIGH_WAIT;
            }
            break;
        }

        case STEP_WEIGH_WAIT:
            // 4. Wait for vibration/settling after NEMA23 stops
            if (currentTime - stepStartTime >= TIME_SETTLE_VIBRATION) {
                currentSortingStep = STEP_WEIGH_READ;
            }
            break;

        case STEP_WEIGH_READ:
            if (hx711.is_ready() && hx711_calibrated) {
                currentEggWeight = hx711.get_units(10);
                Serial.print(F("HX711: Weight measured: "));
                Serial.print(currentEggWeight, 2);
                Serial.println(F(" g"));
            } else {
                // Test Weight Injection (Used if uncalibrated or HX711 not ready)
                static float testWeight = 47.0f; 
                testWeight += 25.0f; // Cycle through test weights (will be > largeMax quickly)
                if (testWeight > 350.0f) testWeight = 47.0f; // Reset to a medium test weight
                
                currentEggWeight = testWeight;
                Serial.print(F("HX711: Test Weight ("));
                Serial.print(currentEggWeight, 2);
                Serial.println(F(" g, WARNING: Uncalibrated/Failed)"));
            }

            weightClassificationIndex = classifyEgg();
            if (plainMode) {
                eggQualityIsGood = true;
                currentSortingStep = STEP_SORT_ACTUATE;
            } else {
                eggQualityIsGood = false;
                Serial.println(F("SORT_READY: Wait for quality check from frontend."));
                stepStartTime = currentTime;
                currentSortingStep = STEP_WAIT_FOR_QUALITY;
            }
            break;

        case STEP_WAIT_FOR_QUALITY:
            // Wait for 'QUALITY GOOD' or 'QUALITY BAD' command via Serial.
            // Transition happens in handleSerialCommands(). This step is non-blocking.
            // If STOP was requested, allow a short window for UI to send QUALITY; otherwise auto-route BAD.
            if (stopRequested) {
                const unsigned long QUALITY_WAIT_TIMEOUT_ON_STOP = 3000; // ms
                if (currentTime - stepStartTime >= QUALITY_WAIT_TIMEOUT_ON_STOP) {
                    eggQualityIsGood = false; // Route to BAD bin by default if no UI input
                    Serial.println(F("STOP_REQUESTED: No QUALITY within timeout. Auto-routing to BAD and finishing cycle."));
                    currentSortingStep = STEP_SORT_ACTUATE;
                }
            }
            break;


        case STEP_SORT_ACTUATE: {
            // 5a. MG996R: Sort the egg based on weight AND quality
            int finalBinIndex = weightClassificationIndex; // Start with the size determined by weight
            const char* finalBinLabel = "ERROR";

            // If quality is bad (e.g., cracked), override the bin to BAD (index 0)
            if (!eggQualityIsGood || finalBinIndex == 0) {
                finalBinIndex = 0; // BAD bin index
                finalBinLabel = "BAD (CRACKED/GAP)";
            } else {
                // If quality is good, use the size classification
                if (finalBinIndex == 1) finalBinLabel = "SMALL";
                else if (finalBinIndex == 2) finalBinLabel = "MEDIUM";
                else if (finalBinIndex == 3) finalBinLabel = "LARGE";
            }

            int targetPos = MG996R_POSITIONS[finalBinIndex];
            mg996r.write(targetPos);

            Serial.print(F("FINAL_SORT: Egg directed to "));
            Serial.print(finalBinLabel);
            Serial.print(F(" bin at "));
            Serial.print(targetPos);
            Serial.println(F(" degrees."));

            stepStartTime = currentTime;
            currentSortingStep = STEP_EGG_DROP_WAIT;
            break;
        }

        case STEP_EGG_DROP_WAIT:
            // 5b. Wait for the egg to drop (Non-blocking delay)
            if (currentTime - stepStartTime >= TIME_SORT_ACTUATE) {
                Serial.println(F("SYSTEM_FLOW_END: Egg dropped. MG996R remains in position."));

                // If a graceful stop was requested, perform stop now (at cycle boundary)
                if (stopRequested) {
                    stopRequested = false;
                    stopSystem();
                } else {
                    // Otherwise, restart immediately at step 1 for continuous operation
                    currentSortingStep = STEP_LOAD_EGG_DOWN;
                    Serial.println(F("SYSTEM_FLOW_RESTART"));
                }
            }
            break;

        case STEP_IDLE:
        default:
            break;
    }
}

// ==================== CALIBRATIONS (Unchanged) ====================
void calibrateUno() {
    Serial.println(F("CALIBRATION_START:UNO"));
    calibrationMode = true;
    for (int i = 2; i <= 13; i++) {
        pinMode(i, OUTPUT);
        digitalWrite(i, HIGH);
        delay(50);
        digitalWrite(i, LOW);
    }
    calibrationMode = false;
    Serial.println(F("CALIBRATION_COMPLETE:UNO"));
}

void calibrateHX711(float known_weight) {
    calibrationMode = true;
    if (!hx711.is_ready()) {
        Serial.println(F("{\"hx711\":\"error\",\"message\":\"HX711 not ready\"}"));
        calibrationMode = false;
        return;
    }

    Serial.println(F("{\"hx711\":\"step1\",\"message\":\"Remove all weight from load cell.\"}"));
    delay(3000);
    
    // Tare and wait for stabilization
    hx711.tare(); // Reset zero point
    delay(2000); // Wait for stabilization after tare
    
    // Take multiple zero readings and check stability
    long zero_readings[3];
    for (int i = 0; i < 3; i++) {
        zero_readings[i] = hx711.read_average(30); // More samples for accuracy
        delay(500);
    }
    
    // Check if zero readings are stable (within 100 raw units)
    long zero_variance = abs(zero_readings[1] - zero_readings[0]) + abs(zero_readings[2] - zero_readings[1]);
    if (zero_variance > 100) {
        Serial.println(F("{\"hx711\":\"warning\",\"message\":\"Zero reading unstable. Retrying...\"}"));
        delay(2000);
        hx711.tare();
        delay(2000);
        // Retake zero readings
        for (int i = 0; i < 3; i++) {
            zero_readings[i] = hx711.read_average(30);
            delay(500);
        }
    }
    
    long zero_offset = (zero_readings[0] + zero_readings[1] + zero_readings[2]) / 3; // Average of stable readings

    Serial.println(F("{\"hx711\":\"step2\",\"message\":\"Place known weight on load cell.\"}"));
    delay(8000); // Longer wait for mechanical settling (8 seconds instead of 5)
    
    // Take multiple readings and check stability
    long weight_readings[3];
    for (int i = 0; i < 3; i++) {
        weight_readings[i] = hx711.read_average(30); // More samples for accuracy
        delay(500);
    }
    
    // Check if weight readings are stable
    long weight_variance = abs(weight_readings[1] - weight_readings[0]) + abs(weight_readings[2] - weight_readings[1]);
    if (weight_variance > 100) {
        Serial.println(F("{\"hx711\":\"warning\",\"message\":\"Weight reading unstable. Waiting longer...\"}"));
        delay(3000); // Wait longer if unstable
        for (int i = 0; i < 3; i++) {
            weight_readings[i] = hx711.read_average(30);
            delay(500);
        }
    }
    
    // Use average of stable readings
    long reading = (weight_readings[0] + weight_readings[1] + weight_readings[2]) / 3;
    long diff = reading - zero_offset;
    if (diff == 0) diff = 1;
    float new_scale = ((float)diff) / known_weight;

    EEPROM.put(HX711_OFFSET_ADDR, zero_offset);
    EEPROM.put(HX711_SCALE_ADDR, new_scale);

    hx711_offset = zero_offset;
    hx711_scale = new_scale;
    hx711.set_offset(hx711_offset);
    hx711.set_scale(hx711_scale);
    hx711_calibrated = true;

    // Verify calibration by reading back the weight
    delay(1000);
    float verified_weight = hx711.get_units(30);
    float error = abs(verified_weight - known_weight);
    
    Serial.print(F("{\"hx711\":\"done\",\"offset\":"));
    Serial.print(hx711_offset);
    Serial.print(F(",\"scale\":"));
    Serial.print(hx711_scale, 6);
    Serial.print(F(",\"verified_weight\":"));
    Serial.print(verified_weight, 2);
    Serial.print(F(",\"error\":"));
    Serial.print(error, 2);
    if (error > 1.0f) {
        Serial.print(F(",\"warning\":\"Calibration error > 1g. Consider recalibrating.\"}"));
    } else {
        Serial.print(F(",\"message\":\"Calibration complete and verified\"}"));
    }
    Serial.println();
    
    calibrationMode = false;
}

void calibrateNema23() {
    Serial.println(F("CALIBRATION_START:NEMA23"));
    calibrationMode = true;

    digitalWrite(NEMA23_ENABLE_PIN, LOW);

    Serial.println(F("Moving forward 1600 steps (blocking)..."));
    digitalWrite(NEMA23_DIR_PIN, HIGH);
    for (int i = 0; i < 1600; i++) {
        digitalWrite(NEMA23_STEP_PIN, HIGH);
        delayMicroseconds(800);
        digitalWrite(NEMA23_STEP_PIN, LOW);
        delayMicroseconds(800);
    }

    delay(500);

    Serial.println(F("Moving backward 1600 steps (blocking)..."));
    digitalWrite(NEMA23_DIR_PIN, LOW);
    for (int i = 0; i < 1600; i++) {
        digitalWrite(NEMA23_STEP_PIN, HIGH);
        delayMicroseconds(800);
        digitalWrite(NEMA23_STEP_PIN, LOW);
        delayMicroseconds(800);
    }

    digitalWrite(NEMA23_ENABLE_PIN, HIGH);
    calibrationMode = false;
    Serial.println(F("CALIBRATION_COMPLETE:NEMA23"));
}

/**
 * @brief Calibrates the SG90 servo by sweeping 0 -> 100 -> 0 and returning to 100.
 */
void calibrateLoaderServo() {
    Serial.println(F("CALIBRATION_START:LOADER"));
    calibrationMode = true;

    // 1. Move from current position down to 0 degrees (Min)
    Serial.println(F("LOADER: Sweeping to 0 degrees..."));
    for (int pos = loader.read(); pos >= 100; pos -= 1) {
        loader.write(pos);
        delay(5);
    }
    Serial.println(F("LOADER: Reached 0 degrees (Min)."));
    delay(1000);

    // 2. Move from 0 up to 100 degrees (Test Peak)
    Serial.println(F("LOADER: Sweeping to 100 degrees..."));
    for (int pos = loader.read(); pos <= 160; pos += 1) {
        loader.write(pos);
        delay(5);
    }
    Serial.println(F("LOADER: Reached 100 degrees (Test Peak)."));
    delay(1000);

    // 3. Move from 100 back down to 0 degrees (Min)
    Serial.println(F("LOADER: Sweeping back to 0 degrees..."));
    for (int pos = loader.read(); pos >= 100; pos -= 1) {
        loader.write(pos);
        delay(5);
    }
    Serial.println(F("LOADER: Reached 0 degrees (Min)."));
    delay(1000);

    // 4. Return to home position (100 degrees)
    Serial.println(F("LOADER: Returning to 100 degrees (Home)."));
    for (int pos = loader.read(); pos <= 160; pos += 1) {
        loader.write(pos);
        delay(5);
    }

    calibrationMode = false;
    Serial.println(F("CALIBRATION_COMPLETE:LOADER"));
}

void calibrateMG996R() {
    Serial.println(F("CALIBRATION_START:MG996R"));
    calibrationMode = true;
    const char *labels[4] = {"BAD", "SMALL", "MEDIUM", "LARGE"};
    for (int i = 0; i < 4; i++) {
        mg996r.write(MG996R_POSITIONS[i]);
        delay(1000);
        Serial.print(F("Position ")); Serial.print(labels[i]);
        Serial.print(F(": ")); Serial.print(MG996R_POSITIONS[i]);
        Serial.println(F("°"));
    }
    // MG996R returns to home (90 degrees) after calibration is complete
    mg996r.write(MG996R_HOME_POS);
    delay(1000);
    calibrationMode = false;
    Serial.println(F("CALIBRATION_COMPLETE:MG996R"));
}

// ==================== TRAPEZOIDAL SPEED PROFILE ====================
/**
 * @brief Calculates the step delay for trapezoidal speed profile.
 * @param currentStep The current step number in the move (0-indexed)
 * @param totalSteps The total number of steps in the move
 * @return The delay in microseconds for the current step
 * 
 * Profile phases:
 * 1. Acceleration: Steps 0 to ACCEL_STEPS - gradually decrease delay (speed up)
 * 2. Constant: Steps ACCEL_STEPS to (totalSteps - DECEL_STEPS) - maintain max speed
 * 3. Deceleration: Steps (totalSteps - DECEL_STEPS) to totalSteps - gradually increase delay (slow down)
 */
unsigned long calculateStepDelay(int currentStep, int totalSteps) {
    // Phase 1: Acceleration (beginning of move)
    if (currentStep < ACCEL_STEPS) {
        // Linear interpolation from MAX_STEP_DELAY_US to MIN_STEP_DELAY_US
        float ratio = (float)currentStep / (float)ACCEL_STEPS;
        return MAX_STEP_DELAY_US - (unsigned long)(ratio * (MAX_STEP_DELAY_US - MIN_STEP_DELAY_US));
    }
    
    // Phase 3: Deceleration (end of move)
    else if (currentStep >= (totalSteps - DECEL_STEPS)) {
        // Linear interpolation from MIN_STEP_DELAY_US to MAX_STEP_DELAY_US
        int stepsIntoDecel = currentStep - (totalSteps - DECEL_STEPS);
        float ratio = (float)stepsIntoDecel / (float)DECEL_STEPS;
        return MIN_STEP_DELAY_US + (unsigned long)(ratio * (MAX_STEP_DELAY_US - MIN_STEP_DELAY_US));
    }
    
    // Phase 2: Constant speed (middle of move)
    else {
        return MIN_STEP_DELAY_US;
    }
}

// ==================== STATUS ====================
void sendStatus() {
    Serial.println(F("=== SYSTEM STATUS ==="));
    Serial.print(F("Active: ")); Serial.println(systemActive ? F("YES") : F("NO"));
    Serial.print(F("Current Step: "));
    switch (currentSortingStep) {
        case STEP_IDLE: Serial.println(F("IDLE")); break;
        case STEP_LOAD_EGG_DOWN: Serial.println(F("LOADING_DOWN")); break;
        case STEP_LOAD_EGG_UP: Serial.println(F("LOADING_UP")); break;
        case STEP_MOVE_TO_SCALE_INIT: Serial.println(F("MOVE_INIT")); break;
        case STEP_STEPPER_MOVING: Serial.print(F("STEPPER_MOVING (Remaining: ")); Serial.print(stepsRemainingInMove); Serial.println(F(")")); break;
        case STEP_WEIGH_WAIT: Serial.println(F("SETTLING_VIBRATION")); break;
        case STEP_WEIGH_READ: Serial.println(F("WEIGHING")); break;
        case STEP_WAIT_FOR_QUALITY: Serial.println(F("WAITING_FOR_QUALITY_CHECK")); break; // New status line
        case STEP_SORT_ACTUATE: Serial.println(F("SORTING_ACTUATE")); break;
        case STEP_EGG_DROP_WAIT: Serial.println(F("EGG_DROP_WAIT - MG996R holding position")); break;
    }

    Serial.print(F("LOADER: ")); Serial.print(loader.read()); Serial.println(F("°"));
    Serial.print(F("MG996R: ")); Serial.print(mg996r.read()); Serial.println(F("°"));
    Serial.print(F("HX711 Calibrated: ")); Serial.println(hx711_calibrated ? F("YES") : F("NO"));

    if (hx711_calibrated) {
        if (hx711.is_ready()) {
            Serial.print(F("HX711 Reading: "));
            Serial.print(hx711.get_units(10));
            Serial.println(F(" g"));
        } else {
            Serial.println(F("HX711 Reading: ERROR (Not Ready)"));
        }
    }

    Serial.println(F("--- CONFIGURATION ---"));
    Serial.print(F("SMALL: ")); Serial.print(smallMin, 1); Serial.print(F("g - ")); Serial.print(smallMax, 1); Serial.println(F("g"));
    Serial.print(F("MEDIUM: ")); Serial.print(mediumMin, 1); Serial.print(F("g - ")); Serial.print(mediumMax, 1); Serial.println(F("g"));
    Serial.print(F("LARGE: ")); Serial.print(largeMin, 1); Serial.print(F("g - ")); Serial.print(largeMax, 1); Serial.println(F("g"));
    Serial.println(F("==================="));
}
