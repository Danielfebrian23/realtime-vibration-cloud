# RAW VIBRATION DATA RECORDING SYSTEM

Sistem untuk merekam data getaran mentah dari sensor ADXL345 ESP32 tanpa processing apapun.

## 🎯 TUJUAN

Mengumpulkan dataset getaran mentah untuk:
- Motor normal vs rusak ringan vs rusak berat
- Jalan lurus vs berbatu vs menanjak
- Ground truth data untuk training model klasifikasi

## 📁 FILE YANG DIBUTUHKAN

### Server Side:
- `realtime_vibration_server_raw_recording.py` - Server Flask + Telegram Bot
- `requirements_raw_recording.txt` - Dependencies Python
- `railway_raw_recording.json` - Konfigurasi Railway

### ESP32 Side:
- `esp32_adxl345_raw_recording/esp32_adxl345_raw_recording.ino` - Code ESP32

## 🚀 CARA DEPLOY

### 1. Deploy ke Railway:
```bash
# 1. Upload semua file ke GitHub repo
# 2. Connect repo ke Railway
# 3. Set environment variables di Railway dashboard:
TELEGRAM_TOKEN=your_bot_token
AUTHORIZED_USER_ID=your_telegram_user_id
PUBLIC_URL=https://your-app.up.railway.app
ESP32_IP=192.168.1.100
ESP32_HTTP_PORT=80
```

### 2. Upload Code ke ESP32:
```cpp
// Ganti URL server di ESP32 code:
const char* serverUrl = "https://your-app.up.railway.app/raw_data";

// Upload ke ESP32 via Arduino IDE
```

## 📱 COMMAND TELEGRAM

### Recording Commands:
```
/start - Mulai bot dan lihat info
/help - Lihat semua command yang tersedia

/record_start <durasi> <label> - Mulai recording
/record_stop - Stop recording
/record_status - Cek status recording
/record_export <label> - Download data CSV
```

### Format Recording:
```
/record_start <durasi_menit> <road_type>_<motor_condition>
```

### Road Types:
- `jalan_lurus` - Jalan lurus/datar
- `jalan_berbatu` - Jalan berbatu/bergelombang  
- `jalan_menanjak` - Jalan menanjak

### Motor Conditions:
- `normal` - Motor dalam kondisi normal
- `rusak_ringan` - Motor rusak ringan (aus)
- `rusak_berat` - Motor rusak berat (rantai patah)

### Contoh Command:
```
/record_start 30 jalan_lurus_normal
/record_start 45 jalan_berbatu_rusak_ringan
/record_start 60 jalan_menanjak_rusak_berat
```

## 📊 DATA YANG DIREKAM

### Format CSV Output:
```csv
timestamp,x,y,z,label,road_type,motor_condition
1234567890,1.234,0.567,9.812,jalan_lurus_normal,jalan_lurus,normal
1234567891,1.235,0.568,9.813,jalan_lurus_normal,jalan_lurus,normal
```

### Data Raw:
- **timestamp**: Waktu dalam millisecond
- **x,y,z**: Data akselerometer mentah dari sensor (satuan g)
- **label**: Kombinasi road_type + motor_condition
- **road_type**: Jenis jalan
- **motor_condition**: Kondisi motor

## 🔧 KONFIGURASI ESP32

### Sampling Rate:
- 20 Hz (50ms delay)
- 30 samples per transmission
- Auto-send setiap 5 detik

### Data Processing:
- **TIDAK ADA** filtering atau processing
- Data mentah langsung dari sensor
- **TIDAK ADA** offset removal atau kalibrasi

## 📈 WORKFLOW RECORDING

1. **Persiapan:**
   - Pastikan ESP32 terhubung WiFi
   - Pastikan server Railway running
   - Pastikan Telegram bot aktif

2. **Recording:**
   - Kirim command `/record_start` via Telegram
   - ESP32 otomatis mulai mengirim data
   - Data tersimpan ke CSV di server

3. **Monitoring:**
   - Gunakan `/record_status` untuk cek progress
   - Lihat log di ESP32 Serial Monitor

4. **Download:**
   - Gunakan `/record_export` untuk download CSV
   - File CSV berisi data mentah siap untuk analisis

## 🎯 STRATEGI PENGUMPULAN DATA

### Minimal Data per Kondisi:
- **30 menit** per kombinasi road_type + motor_condition
- **Total 9 kombinasi** = 4.5 jam recording

### Kombinasi yang Direkam:
1. `jalan_lurus_normal` - 30 menit
2. `jalan_berbatu_normal` - 30 menit  
3. `jalan_menanjak_normal` - 30 menit
4. `jalan_lurus_rusak_ringan` - 30 menit
5. `jalan_berbatu_rusak_ringan` - 30 menit
6. `jalan_menanjak_rusak_ringan` - 30 menit
7. `jalan_lurus_rusak_berat` - 30 menit
8. `jalan_berbatu_rusak_berat` - 30 menit
9. `jalan_menanjak_rusak_berat` - 30 menit

### Tips Recording:
- **Motor Normal**: Gunakan motor yang benar-benar normal
- **Rusak Ringan**: Motor dengan bearing aus atau rantai kendor
- **Rusak Berat**: Motor dengan rantai patah atau komponen rusak
- **Jalan Berbatu**: Cari jalan yang benar-benar berbatu
- **Jalan Menanjak**: Cari tanjakan yang cukup curam

## 🔍 TROUBLESHOOTING

### ESP32 Issues:
- Cek koneksi WiFi
- Cek koneksi sensor ADXL345
- Lihat Serial Monitor untuk error

### Server Issues:
- Cek Railway logs
- Cek environment variables
- Test endpoint `/status`

### Telegram Issues:
- Cek bot token
- Cek authorized user ID
- Test command `/start`

## 📋 NEXT STEPS

Setelah data terkumpul:
1. **Analisis data** untuk mencari pola perbedaan
2. **Buat feature extraction** yang lebih baik
3. **Train model klasifikasi** dengan data ground truth
4. **Set threshold** berdasarkan data nyata
5. **Implementasi** ke sistem real-time

## ⚠️ PENTING

- Data yang direkam adalah **RAW** tanpa processing
- Pastikan motor benar-benar dalam kondisi yang di-label
- Recording otomatis stop setelah durasi selesai
- Data tersimpan di server, download via Telegram
