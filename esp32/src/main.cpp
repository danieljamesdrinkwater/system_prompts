/**
 * HGV-ADAS Radar Pod Firmware
 *
 * Reads Hi-Link LD2410 24GHz mmWave radar sensor via UART,
 * streams detection data over WiFi/UDP to the Raspberry Pi hub.
 *
 * Hardware: ESP32-C3 Mini + LD2410 + IP67 battery pack
 * All inside a 3D-printed ABS enclosure with neodymium magnetic base.
 *
 * UDP packet format (JSON):
 *   {"pod_id":"radar_left_front","distance":2.3,"moving":true,"energy":45,"t":12345}
 */

#include <Arduino.h>
#include <WiFi.h>
#include <WiFiUdp.h>
#include <ArduinoJson.h>
#include <ld2410.h>

// ── Configuration ──────────────────────────────────────────────
// Pod identity — change per pod before flashing
// Options: "radar_left_front", "radar_left_rear", "radar_rear"
const char* POD_ID = "radar_left_front";

// WiFi credentials — connect to the Pi's access point
const char* WIFI_SSID = "HGV-ADAS";
const char* WIFI_PASS = "adaspass123";

// Pi's IP on the AP network and UDP port
const IPAddress PI_IP(192, 168, 4, 1);
const uint16_t  PI_PORT = 5005;

// LD2410 UART pins (ESP32-C3)
const int LD2410_RX = 20;  // ESP32 RX ← LD2410 TX
const int LD2410_TX = 21;  // ESP32 TX → LD2410 RX

// Send rate
const unsigned long SEND_INTERVAL_MS = 100;  // 10Hz

// ── Globals ────────────────────────────────────────────────────
ld2410 radar;
WiFiUDP udp;
unsigned long lastSend = 0;
bool wifiConnected = false;

// ── Setup ──────────────────────────────────────────────────────
void setup() {
    Serial.begin(115200);
    delay(500);
    Serial.printf("\n[HGV-ADAS] Radar pod: %s\n", POD_ID);

    // Initialise LD2410 on Serial1
    Serial1.begin(256000, SERIAL_8N1, LD2410_RX, LD2410_TX);
    if (radar.begin(Serial1)) {
        Serial.println("[LD2410] Sensor connected");
    } else {
        Serial.println("[LD2410] ERROR: sensor not found");
    }

    // Connect to Pi's WiFi AP
    WiFi.mode(WIFI_STA);
    WiFi.begin(WIFI_SSID, WIFI_PASS);
    Serial.printf("[WiFi] Connecting to %s", WIFI_SSID);

    unsigned long wifiStart = millis();
    while (WiFi.status() != WL_CONNECTED && millis() - wifiStart < 15000) {
        delay(500);
        Serial.print(".");
    }

    if (WiFi.status() == WL_CONNECTED) {
        wifiConnected = true;
        Serial.printf("\n[WiFi] Connected — IP: %s\n", WiFi.localIP().toString().c_str());
        udp.begin(0);  // Ephemeral source port
    } else {
        Serial.println("\n[WiFi] Connection failed — will retry in loop");
    }
}

// ── Main Loop ──────────────────────────────────────────────────
void loop() {
    // Read radar data
    radar.read();

    // Reconnect WiFi if dropped
    if (!wifiConnected && WiFi.status() != WL_CONNECTED) {
        WiFi.begin(WIFI_SSID, WIFI_PASS);
        delay(1000);
        if (WiFi.status() == WL_CONNECTED) {
            wifiConnected = true;
            udp.begin(0);
            Serial.println("[WiFi] Reconnected");
        }
        return;
    }
    wifiConnected = (WiFi.status() == WL_CONNECTED);

    // Rate-limit sends
    unsigned long now = millis();
    if (now - lastSend < SEND_INTERVAL_MS) {
        return;
    }
    lastSend = now;

    if (!radar.isConnected()) {
        return;
    }

    // Get detection data
    bool movingTarget = radar.movingTargetDetected();
    bool stationaryTarget = radar.stationaryTargetDetected();

    float distance = 0;
    int energy = 0;
    bool moving = false;

    if (movingTarget) {
        distance = radar.movingTargetDistance() / 100.0;  // cm → metres
        energy = radar.movingTargetEnergy();
        moving = true;
    } else if (stationaryTarget) {
        distance = radar.stationaryTargetDistance() / 100.0;
        energy = radar.stationaryTargetEnergy();
        moving = false;
    }

    // Only send if something is detected
    if (distance <= 0) {
        return;
    }

    // Build JSON packet
    JsonDocument doc;
    doc["pod_id"] = POD_ID;
    doc["distance"] = round(distance * 10.0) / 10.0;  // 1 decimal place
    doc["moving"] = moving;
    doc["energy"] = energy;
    doc["t"] = now;

    char buffer[256];
    size_t len = serializeJson(doc, buffer);

    // Send UDP to Pi
    if (wifiConnected) {
        udp.beginPacket(PI_IP, PI_PORT);
        udp.write((const uint8_t*)buffer, len);
        udp.endPacket();
    }

    // Debug output
    Serial.printf("[%s] dist=%.1fm moving=%d energy=%d\n",
                  POD_ID, distance, moving, energy);
}
