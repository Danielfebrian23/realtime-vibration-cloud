#include <Wire.h>
#include <Adafruit_ADXL345_U.h>
#include <WiFi.h>
#include <HTTPClient.h>
#include <ArduinoJson.h>

/* ================= KONFIGURASI WIFI & SERVER ================= */
const char* ssid = "(Isi nama Wifinya)";        
const char* password = "(Isi nama passwordnya)"; 

// Dimasukkan URL Railway yang sudah dideploy
String serverUrl = "https://realtime-vibration-cloud-production.up.railway.app/raw_data"; 

Adafruit_ADXL345_Unified accel = Adafruit_ADXL345_Unified(12345);

/* ================= KONFIGURASI BUFFERING ================= */
// Dinaikan menjadi 512 (sekitar 2x Window Size).
// Tujuannya agar pengiriman data lebih efisien (tidak spamming server).
// Python server akan otomatis memotongnya menjadi window 256.
const int BUFFER_SIZE = 512; 

float xBuff[BUFFER_SIZE];
float yBuff[BUFFER_SIZE];
float zBuff[BUFFER_SIZE];
int bufIdx = 0;

void setup() {
  Serial.begin(115200);
  
  // 1. Init Sensor
  if(!accel.begin()) {
    Serial.println("CRITICAL ERROR: Sensor ADXL345 tidak terdeteksi!");
    while(1);
  }

  // 2. SETTING KUNCI UNTUK SENSOR ADXL345
  // Range +/- 16G: Agar hentakan keras jalanan terekam (lalu di-clip di server)
  // Rate 1600 Hz: Agar FFT resolusinya tinggi
  accel.setRange(ADXL345_RANGE_16_G); 
  accel.setDataRate(ADXL345_DATARATE_1600_HZ);
  
  Serial.println("Sensor OK. Range: 16G, Rate: 1600Hz");

  // 3. Connect WiFi
  WiFi.begin(ssid, password);
  Serial.print("Connecting to WiFi");
  while (WiFi.status() != WL_CONNECTED) {
    delay(500);
    Serial.print(".");
  }
  Serial.println("\nWiFi Connected!");
}

bool isPaused = false;

void loop() {
  // --- FITUR PAUSE/RESUME UNTUK DEMO ---
  if (Serial.available() > 0) {
    char cmd = Serial.read();
    if (cmd == 's' || cmd == 'S') {
      isPaused = true;
      Serial.println("\n==================================================");
      Serial.println("[SYSTEM] PAUSED - Pengambilan data dihentikan sementara.");
      Serial.println("[SYSTEM] Ketik 'r' lalu Enter untuk melanjutkan.");
      Serial.println("==================================================\n");
    } else if (cmd == 'r' || cmd == 'R') {
      isPaused = false;
      bufIdx = 0; // Reset buffer agar data tidak tercampur
      Serial.println("\n[SYSTEM] RESUMED - Melanjutkan pengambilan data...\n");
    }
  }

  // Jika sistem di-pause, lewati pembacaan sensor
  if (isPaused) {
    delay(100);
    return;
  }

  sensors_event_t event; 
  accel.getEvent(&event);

  // Masukkan data ke Buffer
  xBuff[bufIdx] = event.acceleration.x;
  yBuff[bufIdx] = event.acceleration.y;
  zBuff[bufIdx] = event.acceleration.z;
  bufIdx++;

  // Jika Buffer Penuh, Kirim Batch ke Server
  if (bufIdx >= BUFFER_SIZE) {
    sendDataBatch();
    bufIdx = 0; // Reset index buffer
  }
  
  // Delay mikro untuk menjaga sampling rate stabil (tidak terlalu cepat)
  // 1600Hz = 625us per cycle. Dikurangi overhead processing, 300-400us aman.
  delayMicroseconds(400); 
}

void sendDataBatch() {
  if(WiFi.status() == WL_CONNECTED) {
    HTTPClient http;
    http.begin(serverUrl);
    http.addHeader("Content-Type", "application/json");

    // --- MEMORY RESERVATION (Untuk mencegah terjadinya crash) ---
    // Dibuatkan string JSON manual agar cepat, Tetapi sebelumnya di jaga memori dulu.
    // JSON secara kasar membutuhkan: 512 data * 20 karakter per data = ~10KB.
    // Disiapkan 15KB agar aman. Tanpa ini, ESP32 bisa restart sendiri (Heap Fragmentation).
    String json;
    json.reserve(15000); 

    Serial.println("\n==================================================");
    Serial.print("[SYSTEM] Mengumpulkan ");
    Serial.print(BUFFER_SIZE);
    Serial.println(" Sampel Data Getaran (Batch Size)...");
    Serial.println("[DATA] Mengekstrak Sumbu X, Y, Z dari ADXL345:");

    json = "{\"data\":[";
    
    for(int i=0; i<BUFFER_SIZE; i++) {
      json += "[";
      json += String(xBuff[i], 2); json += ","; // 2 desimal cukup
      json += String(yBuff[i], 2); json += ",";
      json += String(zBuff[i], 2);
      json += "]";
      
      // SAMPEL DITAMPILKAN DI SERIAL MONITOR SUPAYA DETAIL
      if (i < 3) {
        Serial.print("       -> Sampel "); Serial.print(i+1);
        Serial.print(" | X: "); Serial.print(xBuff[i], 2);
        Serial.print(" | Y: "); Serial.print(yBuff[i], 2);
        Serial.print(" | Z: "); Serial.println(zBuff[i], 2);
      } else if (i == 3) {
        Serial.println("       -> ... (memproses hingga 512 sampel secara internal) ...");
      }

      // DITAMBAHKAN KOMA JIKA BUKAN DATA TERAKHIR
      if(i < BUFFER_SIZE-1) json += ",";
    }
    json += "]}";

    Serial.print("[NETWORK] Transmisi POST ke Cloud Server Railway...\n");

    unsigned long startSend = millis();
    // Kirim POST Request
    int httpResponseCode = http.POST(json);
    unsigned long endSend = millis();
    
    if (httpResponseCode > 0) {
      Serial.print("[SUCCESS] Data Sent | Batch Size : ");
      Serial.println(BUFFER_SIZE);
      Serial.print("[SUCCESS] HTTP Response Code : ");
      Serial.println(httpResponseCode);
      Serial.print("[LATENSI] Waktu Total          : ");
      Serial.print(endSend - startSend);
      Serial.println(" ms");
      
      String response = http.getString();
      Serial.print("[SERVER]  Respons              : ");
      Serial.println(response); 
    } else {
      // UNTUK PEMBERITAHUAN ADANYA ERROR JARINGAN
      Serial.print("[ERROR] Transmisi Gagal. Error Code: ");
      Serial.println(httpResponseCode);
    }
    Serial.println("==================================================\n");
    // PENTING: Bebaskan resource
    http.end();
    
  } else {
    Serial.println("WiFi Disconnected! Reconnecting...");
    WiFi.reconnect();
  }
} 
