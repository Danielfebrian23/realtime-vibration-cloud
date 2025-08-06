#include <Wire.h>
#include <Adafruit_ADXL345_U.h>
#include <WiFi.h>
#include <HTTPClient.h>
#include <ArduinoJson.h>

Adafruit_ADXL345_Unified accel = Adafruit_ADXL345_Unified(12345);

// WiFi Configuration
const char* ssid = "ku_gaada_kuota";
const char* password = "akubutek";

// Server Configuration (Python Flask server)
const char* serverUrl = "http://192.168.43.7:5000/predict"; // Ganti dengan IP komputer Anda

#define ADXL345_ADDR_DEFAULT 0x53
#define ADXL345_ADDR_ALT     0x1D
bool measuring = true;

// Data buffer untuk PCA
#define BUFFER_SIZE 100
float xBuffer[BUFFER_SIZE];
float yBuffer[BUFFER_SIZE];
float zBuffer[BUFFER_SIZE];
int bufferIndex = 0;
bool bufferFull = false;

// Kalibrasi sensor
float xOffset = 0, yOffset = 0, zOffset = 0;
bool isCalibrated = false;

void scanI2CDevices() {
  byte error, address;
  int nDevices = 0;
  Serial.println("Scanning I2C devices...");
  for(address = 1; address < 127; address++ ) {
    Wire.beginTransmission(address);
    error = Wire.endTransmission();
    if (error == 0) {
      Serial.print("I2C device found at address 0x");
      if (address<16) Serial.print("0");
      Serial.print(address,HEX);
      Serial.println(" !");
      nDevices++;
    }
  }
  if (nDevices == 0)
    Serial.println("No I2C devices found. Cek koneksi VCC, GND, SCL, SDA, CS, dan SDO!");
  else
    Serial.println("I2C scan selesai.");
}

void diagnoseADXL345() {
  Wire.beginTransmission(ADXL345_ADDR_DEFAULT);
  if (Wire.endTransmission() == 0) {
    Serial.println("ADXL345 terdeteksi di alamat 0x53 (SDO ke GND).");
  } else {
    Wire.beginTransmission(ADXL345_ADDR_ALT);
    if (Wire.endTransmission() == 0) {
      Serial.println("ADXL345 terdeteksi di alamat 0x1D (SDO ke VCC).");
      Serial.println("Perhatian: SDO tidak ke GND, alamat I2C berubah!");
    } else {
      Serial.println("ADXL345 tidak terdeteksi di alamat 0x53 maupun 0x1D.");
      Serial.println("Cek koneksi berikut:");
      Serial.println("- VCC: Pastikan 3.3V/5V ke VCC ADXL345");
      Serial.println("- GND: Pastikan GND ke GND ADXL345");
      Serial.println("- SCL: Pastikan SCL ke SCL ADXL345");
      Serial.println("- SDA: Pastikan SDA ke SDA ADXL345");
      Serial.println("- CS: Pastikan CS ke VCC (mode I2C)");
      Serial.println("- SDO: Pastikan SDO ke GND (untuk alamat 0x53)");
    }
  }
}

void calibrateSensor() {
  Serial.println("Kalibrasi sensor...");
  float xSum = 0, ySum = 0, zSum = 0;
  int samples = 100;
  
  for(int i = 0; i < samples; i++) {
    sensors_event_t event;
    accel.getEvent(&event);
    xSum += event.acceleration.x;
    ySum += event.acceleration.y;
    zSum += event.acceleration.z;
    delay(10);
  }
  
  xOffset = xSum / samples;
  yOffset = ySum / samples;
  zOffset = zSum / samples;
  
  Serial.printf("Kalibrasi selesai - Offset: X=%.2f, Y=%.2f, Z=%.2f\n", xOffset, yOffset, zOffset);
  isCalibrated = true;
}

void addToBuffer(float x, float y, float z) {
  xBuffer[bufferIndex] = x - xOffset;
  yBuffer[bufferIndex] = y - yOffset;
  zBuffer[bufferIndex] = z - zOffset;
  
  bufferIndex++;
  if (bufferIndex >= BUFFER_SIZE) {
    bufferIndex = 0;
    bufferFull = true;
  }
}

void connectWiFi() {
  Serial.print("Connecting to WiFi");
  WiFi.begin(ssid, password);
  
  while (WiFi.status() != WL_CONNECTED) {
    delay(500);
    Serial.print(".");
  }
  
  if (WiFi.status() == WL_CONNECTED) {
    Serial.println();
    Serial.println("WiFi connected!");
    Serial.print("IP address: ");
    Serial.println(WiFi.localIP());
  } else {
    Serial.println();
    Serial.println("WiFi failed to connect!");
  }
}

String sendDataToServer() {
  if (WiFi.status() != WL_CONNECTED) {
    Serial.println("WiFi not connected!");
    return "ERROR: WiFi not connected";
  }
  
  HTTPClient http;
  http.begin(serverUrl);
  http.addHeader("Content-Type", "application/json");
  
  // Buat JSON dengan data sensor
  DynamicJsonDocument doc(4096);
  doc["timestamp"] = millis();
  
  JsonArray xData = doc.createNestedArray("x");
  JsonArray yData = doc.createNestedArray("y");
  JsonArray zData = doc.createNestedArray("z");
  
  int dataCount = bufferFull ? BUFFER_SIZE : bufferIndex;
  for(int i = 0; i < dataCount; i++) {
    xData.add(xBuffer[i]);
    yData.add(yBuffer[i]);
    zData.add(zBuffer[i]);
  }
  
  String jsonString;
  serializeJson(doc, jsonString);
  
  Serial.println("Sending data to server...");
  Serial.println(jsonString);
  
  int httpResponseCode = http.POST(jsonString);
  String response = "";
  
  if (httpResponseCode > 0) {
    response = http.getString();
    Serial.printf("HTTP Response code: %d\n", httpResponseCode);
    Serial.printf("Response: %s\n", response.c_str());
  } else {
    Serial.printf("Error code: %d\n", httpResponseCode);
    response = "ERROR: HTTP request failed";
  }
  
  http.end();
  return response;
}

void setup() {
    Serial.begin(115200);
  Serial.println("ESP32-S3 started.");

   connectWiFi();

  Wire.begin();
  delay(500);

  scanI2CDevices();

  if (!accel.begin()) {
    Serial.println("Sensor gagal.");
  } else {
    Serial.println("Sensor OK.");
  }
}

void loop() {
  // Cek perintah dari Serial
  if (Serial.available()) {
    String cmd = Serial.readStringUntil('\n');
    cmd.trim();
    
    if (cmd.equalsIgnoreCase("STOP")) {
      measuring = false;
      Serial.println("Pengukuran dihentikan.");
    } else if (cmd.equalsIgnoreCase("START")) {
      measuring = true;
      Serial.println("Pengukuran dimulai.");
    } else if (cmd.equalsIgnoreCase("CALIBRATE")) {
      calibrateSensor();
    } else if (cmd.equalsIgnoreCase("PREDICT")) {
      if (bufferFull || bufferIndex > 50) {
        String result = sendDataToServer();
        Serial.println("Prediction result: " + result);
      } else {
        Serial.println("Buffer belum penuh. Tunggu lebih banyak data.");
      }
    }
  }

  if (measuring) {
    sensors_event_t event;
    accel.getEvent(&event);

    // Tambahkan ke buffer
    addToBuffer(event.acceleration.x, event.acceleration.y, event.acceleration.z);
    
    // Kirim data setiap 100 sampel atau setiap 10 detik
    static unsigned long lastSend = 0;
    if ((bufferFull || bufferIndex >= 100) && (millis() - lastSend > 10000)) {
      String result = sendDataToServer();
      Serial.println("Real-time prediction: " + result);
      lastSend = millis();
      
      // Reset buffer setelah prediksi
      bufferIndex = 0;
      bufferFull = false;
    }

    // Debug output
    Serial.printf("[%lu],%.2f,%.2f,%.2f\n", 
                  millis(), 
                  event.acceleration.x - xOffset, 
                  event.acceleration.y - yOffset, 
                  event.acceleration.z - zOffset);

    delay(100); // 10 Hz sampling rate
  } else {
    delay(100);
  }
} 