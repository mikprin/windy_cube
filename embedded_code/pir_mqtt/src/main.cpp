/*
 * ESP32 FreeRTOS with PIR motion sensor and MQTT publishing.
 * Detects motion on pin 14 and publishes MQTT messages with debouncing.
 * Based on the same architecture as the mushroom controller.
 */

#include <Arduino.h>
#include <WiFi.h>            // For Wi-Fi
#include <AsyncMqttClient.h> // For Async MQTT
#include <Preferences.h>     // For storing data in non-volatile storage (NVS)

// ------------------- Wi-Fi Credentials -------------------
#include "wifi_config.h"

// ------------------- MQTT Settings -----------------------
// #define MQTT_HOST "192.168.8.5"
#define MQTT_HOST "192.168.8.4" // Laptop
#define MQTT_PORT 1883

// MQTT Topics
#define TOPIC_MOTION "motion/detected"
#define TOPIC_STATUS "motion/status"
#define TOPIC_EVENTS "motion/events"
#define ERROR_TOPIC "motion/error"

// ------------------- Hardware Pins -----------------------
#define PIR_SENSOR_PIN 14

// ------------------- Motion Detection Settings -----------
#define MOTION_DEBOUNCE_TIME 1000  // 1 seconds debounce to avoid spam
#define STATUS_PUBLISH_INTERVAL 30000  // Publish status every 30 seconds

// ------------------- Global Objects ----------------------
AsyncMqttClient mqttClient;
Preferences prefs;

// ------------------- FreeRTOS Task Handles --------------
TaskHandle_t pirTaskHandle = NULL;
TaskHandle_t mqttTaskHandle = NULL;

// ------------------- Motion Detection Variables ----------
volatile bool motionDetected = false;
volatile unsigned long lastMotionTime = 0;
volatile unsigned long motionCount = 0;

// --------------------------------------------------------
// WIFI & MQTT Helper Functions
// --------------------------------------------------------
void connectToWifi()
{
  Serial.printf("[Wi-Fi] Connecting to %s...\n", WIFI_SSID);
  WiFi.begin(WIFI_SSID, WIFI_PASS);
}

void connectToMqtt()
{
  if (!mqttClient.connected())
  {
    Serial.println("[MQTT] Connecting to MQTT...");
    mqttClient.connect();
  }
}

// Called when MQTT is connected
void onMqttConnect(bool sessionPresent)
{
  Serial.println("[MQTT] Connected to broker!");
  
  // Publish startup message
  String startupMsg = "{\"status\":\"online\",\"device\":\"ESP32_PIR_Detector\",\"timestamp\":" + String(millis()) + "}";
  mqttClient.publish(TOPIC_STATUS, 1, true, startupMsg.c_str()); // retained message
}

// Called when MQTT is disconnected
void onMqttDisconnect(AsyncMqttClientDisconnectReason reason)
{
  Serial.printf("[MQTT] MQTT disconnected. Reason: %d\n", (int)reason);
  delay(2000);
  connectToMqtt();
}

// Wi-Fi event handler
void WiFiEvent(WiFiEvent_t event)
{
  switch (event)
  {
  case SYSTEM_EVENT_STA_GOT_IP:
    Serial.print("[Wi-Fi] Connected. IP: ");
    Serial.println(WiFi.localIP());
    connectToMqtt();
    break;
  case SYSTEM_EVENT_STA_DISCONNECTED:
    Serial.println("[Wi-Fi] Disconnected! Reconnecting...");
    connectToWifi();
    break;
  default:
    break;
  }
}

// --------------------------------------------------------
// FREE RTOS TASK: PIR Motion Detection
// --------------------------------------------------------
void pirMotionTask(void *parameter)
{
  (void)parameter;
  
  bool lastPirState = LOW;
  bool currentPirState = LOW;
  unsigned long lastDebounceTime = 0;
  
  // Configure PIR sensor pin
  pinMode(PIR_SENSOR_PIN, INPUT);
  
  Serial.println("[PIR] Motion detection task started");
  
  for (;;)
  {
    // Read current PIR state
    currentPirState = digitalRead(PIR_SENSOR_PIN);
    unsigned long currentTime = millis();
    
    // Check for state change (LOW to HIGH = motion detected)
    if (currentPirState == HIGH && lastPirState == LOW)
    {
      // Motion detected, check debounce
      if (currentTime - lastDebounceTime > MOTION_DEBOUNCE_TIME)
      {
        Serial.println("[PIR] Motion detected!");
        
        motionDetected = true;
        lastMotionTime = currentTime;
        lastDebounceTime = currentTime;
        motionCount++;
        
        // Publish motion detection immediately
        if (mqttClient.connected())
        {
          String motionPayload = "{";
          motionPayload += "\"motion\":true,";
          motionPayload += "\"timestamp\":" + String(currentTime) + ",";
          motionPayload += "\"count\":" + String(motionCount) + ",";
          motionPayload += "\"uptime\":" + String(currentTime / 1000);
          motionPayload += "}";
          
          mqttClient.publish(TOPIC_MOTION, 1, false, motionPayload.c_str());
          mqttClient.publish(TOPIC_EVENTS, 1, false, "Motion Detected");
          
          Serial.print("[MQTT] Published motion: ");
          Serial.println(motionPayload);
        }
        
        // Save motion count to preferences
        // prefs.putULong("motionCount", motionCount);
      }
      else
      {
        Serial.println("[PIR] Motion detected but debounced (too soon)");
      }
    }
    
    lastPirState = currentPirState;
    
    // Check every 100ms
    vTaskDelay(100 / portTICK_PERIOD_MS);
  }
}

// --------------------------------------------------------
// FREE RTOS TASK: MQTT Status Publisher
// --------------------------------------------------------
void mqttStatusTask(void *parameter)
{
  (void)parameter;
  
  for (;;)
  {
    if (mqttClient.connected())
    {
      // Publish periodic status update
      String statusPayload = "{";
      statusPayload += "\"status\":\"online\",";
      statusPayload += "\"uptime\":" + String(millis() / 1000) + ",";
      statusPayload += "\"motion_count\":" + String(motionCount) + ",";
      statusPayload += "\"last_motion\":" + String(lastMotionTime) + ",";
      statusPayload += "\"free_heap\":" + String(ESP.getFreeHeap()) + ",";
      statusPayload += "\"wifi_rssi\":" + String(WiFi.RSSI());
      statusPayload += "}";
      
      mqttClient.publish(TOPIC_STATUS, 1, true, statusPayload.c_str()); // retained
      
      Serial.print("[MQTT] Status published: ");
      Serial.println(statusPayload);
    }
    
    // Publish status every 30 seconds
    vTaskDelay(STATUS_PUBLISH_INTERVAL / portTICK_PERIOD_MS);
  }
}

// --------------------------------------------------------
// ARDUINO SETUP
// --------------------------------------------------------
void setup()
{
  Serial.begin(115200);
  delay(1000);
  
  Serial.println("ESP32 PIR Motion Detector Starting...");

  // Start Preferences
  if (!prefs.begin("pirapp", false))
  {
    Serial.println("[Prefs] Failed to initialize NVS namespace!");
  }
  else
  {
    Serial.println("[Prefs] NVS preferences initialized.");
    
    motionCount = 0;
    // Load previously saved motion count
    // motionCount = prefs.getULong("motionCount", 0);
    // Serial.printf("[Prefs] Loaded motion count: %lu\n", motionCount);
  }

  // Initialize PIR sensor pin
  pinMode(PIR_SENSOR_PIN, INPUT);
  Serial.printf("[PIR] PIR sensor initialized on pin %d\n", PIR_SENSOR_PIN);

  // Initialize Wi-Fi + MQTT
  WiFi.onEvent(WiFiEvent);
  WiFi.mode(WIFI_STA);
  connectToWifi();

  // Register MQTT callbacks
  mqttClient.onConnect(onMqttConnect);
  mqttClient.onDisconnect(onMqttDisconnect);
  mqttClient.setServer(MQTT_HOST, MQTT_PORT);
  // mqttClient.setCredentials("user", "pass"); // if authentication needed

  // -----------------------------------------------------------------
  // Create FreeRTOS tasks
  // -----------------------------------------------------------------

  // Task 1: PIR Motion Detection
  xTaskCreate(
      pirMotionTask,
      "PIRTask",
      2048,
      NULL,
      2,  // Higher priority for motion detection
      &pirTaskHandle);

  // Task 2: MQTT Status Publishing
  xTaskCreate(
      mqttStatusTask,
      "MQTTStatusTask",
      4096,
      NULL,
      1,
      &mqttTaskHandle);

  Serial.println("Setup complete. All tasks created.");
  Serial.println("Waiting for motion detection...");
}

// --------------------------------------------------------
// ARDUINO LOOP
// --------------------------------------------------------
void loop()
{
  // Main loop monitoring and debug output
  static unsigned long lastPrint = 0;
  unsigned long now = millis();
  
  if (now - lastPrint >= 10000) // Print every 10 seconds
  {
    lastPrint = now;
    Serial.printf("[MainLoop] Uptime: %lu s, Motion Count: %lu, WiFi: %s, MQTT: %s\n",
                  now / 1000,
                  motionCount,
                  WiFi.isConnected() ? "Connected" : "Disconnected",
                  mqttClient.connected() ? "Connected" : "Disconnected");
                  
    // Check for low memory
    if (ESP.getFreeHeap() < 10000)
    {
      Serial.printf("[Warning] Low free heap: %d bytes\n", ESP.getFreeHeap());
      if (mqttClient.connected())
      {
        mqttClient.publish(ERROR_TOPIC, 1, false, "Low memory warning");
      }
    }
  }
  
  delay(1000);
}