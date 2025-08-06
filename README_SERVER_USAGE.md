# 🚀 Real-Time Vibration Analysis Server - Panduan Penggunaan

## 📋 Overview

Sistem analisis getaran real-time yang dapat mendeteksi anomali pada motor menggunakan algoritma Isolation Forest dan PCA. Sistem ini mendukung integrasi dengan Telegram bot untuk monitoring jarak jauh.

## 🎯 Status Saat Ini

✅ **Server berjalan dengan baik**  
✅ **Model ML berfungsi** (Isolation Forest + PCA)  
✅ **Real-time processing** dari ESP32  
✅ **Telegram bot integration** (opsional)  
✅ **Error handling** yang robust  

## 🚀 Cara Menjalankan Server

### Opsi 1: Menggunakan Script Mudah
```bash
python run_server.py
```
Kemudian pilih:
- **1**: Dengan Telegram bot
- **2**: Tanpa Telegram bot (direkomendasikan)

### Opsi 2: Langsung dari Command Line

#### Tanpa Telegram Bot (Direkomendasikan)
```bash
python realtime_vibration_server_clean.py --no-telegram
```

#### Dengan Telegram Bot
```bash
python realtime_vibration_server_clean.py
```

### Opsi 3: Server Tanpa Telegram
```bash
python realtime_vibration_server_no_telegram.py
```

## 🔧 Troubleshooting

### Masalah Telegram Bot Conflict

Jika muncul error:
```
Conflict: terminated by other getUpdates request; make sure that only one bot instance is running
```

**Solusi:**
1. Matikan semua instance bot yang berjalan:
   ```bash
   python kill_bot_instances.py
   ```

2. Jalankan server tanpa Telegram bot:
   ```bash
   python realtime_vibration_server_clean.py --no-telegram
   ```

### Test Server

Untuk memastikan server berjalan dengan baik:
```bash
python test_server_simple.py
```

## 📊 Endpoints API

### 1. Status Server
```
GET http://localhost:5000/status
```

### 2. Prediksi Real-Time
```
POST http://localhost:5000/predict
Content-Type: application/json

{
    "x": [1.0, 1.1, 1.2],
    "y": [-10.0, -10.1, -10.2],
    "z": [1.8, 1.9, 2.0],
    "timestamp": 1234567890
}
```

### 3. Clear Buffer
```
POST http://localhost:5000/clear_buffer
```

## 📈 Response Format

### Prediksi Response
```json
{
    "timestamp": 1234567890,
    "severity": "BERAT|RINGAN|NORMAL",
    "confidence": 0.85,
    "features": {
        "rms_x": 0.462,
        "rms_y": 10.078,
        "rms_z": 3.335,
        "PC1": -1.313,
        "PC2": -0.064,
        "distance_from_normal": 1.315
    },
    "status": "SUCCESS"
}
```

## 🤖 Telegram Bot Commands

Jika Telegram bot berjalan, gunakan command berikut:

- `/start` - Mulai pengukuran real-time
- `/stop` - Hentikan pengukuran real-time
- `/cek` - Cek kondisi motor saat ini
- `/penjelasan` - Penjelasan kondisi motor
- `/tips` - Tips berdasarkan kondisi motor
- `/grafik` - Grafik riwayat anomali

## 📁 File Penting

### Server Files
- `realtime_vibration_server_clean.py` - Server utama dengan Telegram
- `realtime_vibration_server_no_telegram.py` - Server tanpa Telegram
- `run_server.py` - Script mudah untuk menjalankan server

### Utility Files
- `kill_bot_instances.py` - Matikan instance bot yang konflik
- `test_server_simple.py` - Test server endpoints
- `start_server.py` - Menu interaktif lengkap

### Data Files
- `Dataset PCA (Normal 80 + Ringan 20).xlsx` - Data training
- `Dataset PCA (Normal 80 + Berat 20).xlsx` - Data training

## 🔍 Monitoring

### Log Output
Server akan menampilkan:
```
Training new models...
Models trained successfully!
Starting Flask server...
Server will be available at: http://localhost:5000
Prediction: BERAT (confidence: 0.201)
```

### Real-Time Data
Data dari ESP32 akan diproses dan ditampilkan:
```
192.168.43.223 - - [04/Aug/2025 18:09:16] "POST /predict HTTP/1.1" 200 -
Prediction: BERAT (confidence: 0.201)
```

## ⚡ Performance

### Expected Results
- **NORMAL**: Confidence 0.7-0.95, Distance < 0.05
- **RINGAN**: Confidence 0.6-0.85, Distance 0.05-0.1
- **BERAT**: Confidence 0.7-0.95, Distance > 0.1

### Processing Time
- **Latency**: < 100ms per prediction
- **Throughput**: 10+ predictions/second
- **Buffer Size**: 100 samples (sliding window)

## 🛠️ Development

### Menambah Fitur Baru
1. Edit `realtime_vibration_server_clean.py`
2. Tambah endpoint baru di Flask
3. Test dengan `test_server_simple.py`

### Debug Mode
Untuk debugging, tambahkan `debug=True` di `app.run()`:
```python
app.run(host='0.0.0.0', port=5000, debug=True)
```

## 📞 Support

Jika ada masalah:
1. Cek log output untuk error messages
2. Test server dengan `test_server_simple.py`
3. Matikan semua instance dengan `kill_bot_instances.py`
4. Jalankan ulang dengan `--no-telegram` flag

---

**Status**: ✅ Production Ready  
**Last Updated**: August 4, 2025  
**Version**: 2.0 (Clean Version) 