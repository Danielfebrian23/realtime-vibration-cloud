# 🤖 Telegram Bot Commands - Real-Time Vibration Analysis

## 📋 Daftar Command yang Tersedia

### 🔄 **Control Commands**
- `/start` - Mulai pengukuran real-time
- `/stop` - Hentikan pengukuran real-time

### 📊 **Status & Monitoring**
- `/cek` - Cek kondisi motor saat ini
- `/status` - Status server dan koneksi ESP32
- `/penjelasan` - Penjelasan kondisi motor
- `/tips` - Tips berdasarkan kondisi motor

### 📈 **Data & Analytics**
- `/grafik` - Grafik riwayat anomali motor
- `/riwayat <menit>` - **NEW!** Riwayat data getaran dalam X menit terakhir

### 🎬 **Recording System** - **NEW!**
- `/record_start <label> <menit>` - Mulai recording data getaran
- `/record_stop` - Stop recording dan simpan data
- `/record_status` - Cek status recording
- `/record_export <label>` - Download data recording sebagai CSV

---

## 🆕 **Command Baru: `/riwayat`**

### **Cara Penggunaan**
```
/riwayat 5    → Data 5 menit terakhir
/riwayat 10   → Data 10 menit terakhir
/riwayat 15   → Data 15 menit terakhir
/riwayat      → Data 5 menit terakhir (default)
```

### **Output yang Dihasilkan**

#### 1. **Ringkasan Teks** (dalam chat)
```
📊 **RIWAYAT GETARAN (5 MENIT)**

📈 **Data Points**: 150
⚡ **Kondisi Getaran**: 🟡 SEDANG

📊 **RMS Values**:
• X-axis: 2.45
• Y-axis: 12.34
• Z-axis: 3.67

📏 **Range Values**:
• X-axis: 4.23
• Y-axis: 18.56
• Z-axis: 6.78

⏰ **Waktu**: 5 menit terakhir
```

#### 2. **Gambar Plot** (dikirim sebagai foto)
- **Plot 1**: Raw vibration data (X, Y, Z axes)
- **Plot 2**: RMS values over time (rolling window)

### **Kondisi Getaran**
- 🟢 **RENDAH**: RMS < 8
- 🟡 **SEDANG**: RMS 8-15
- 🔴 **TINGGI**: RMS > 15

---

## 🎯 **Contoh Penggunaan**

### **Monitoring Rutin**
```
/riwayat 5    → Cek data 5 menit terakhir
/cek          → Cek kondisi saat ini
/penjelasan   → Penjelasan kondisi
```

### **Analisis Jangka Pendek**
```
/riwayat 10   → Analisis 10 menit terakhir
/grafik       → Grafik riwayat anomali
```

### **Monitoring Jangka Panjang**
```
/riwayat 30   → Analisis 30 menit terakhir
/status       → Cek status server
```

---

## ⚠️ **Batasan**

- **Maksimal**: 60 menit (jika input > 60, otomatis jadi 60)
- **Minimal**: 1 menit
- **Default**: 5 menit (jika tidak ada parameter)

---

## 🔧 **Troubleshooting**

### **Jika tidak ada data**
```
📊 Tidak ada data getaran dalam 5 menit terakhir.
```
**Solusi**: Pastikan ESP32 mengirim data dan server aktif.

### **Jika error**
```
❌ Error: [pesan error]
```
**Solusi**: Cek koneksi server dan coba lagi.

---

## 📱 **Tips Penggunaan**

1. **Untuk monitoring rutin**: Gunakan `/riwayat 5` setiap 5-10 menit
2. **Untuk analisis detail**: Gunakan `/riwayat 15` atau `/riwayat 30`
3. **Untuk troubleshooting**: Kombinasikan dengan `/status` dan `/cek`
4. **Untuk grafik**: Gunakan `/grafik` untuk melihat tren anomali

---

## 🚀 **Fitur Tambahan**

### **Auto-Response**
- Bot akan otomatis membatasi input > 60 menit
- Memberikan warning jika input terlalu besar

### **Rich Formatting**
- Menggunakan Markdown untuk formatting teks
- Emoji untuk indikator visual
- Grafik yang informatif dan mudah dibaca

### **Error Handling**
- Graceful error handling
- Informative error messages
- Fallback untuk data kosong

---

---

## 🎬 **Recording System - Data Collection**

### **Cara Penggunaan Recording:**

#### **1. Mulai Recording**
```
/record_start jalan_lurus 30     → Record 30 menit, label "jalan_lurus"
/record_start jalan_berlubang 60 → Record 60 menit, label "jalan_berlubang"
/record_start test 15            → Record 15 menit, label "test"
/record_start 30                 → Record 30 menit, label "recording" (default)
```

#### **2. Cek Status Recording**
```
/record_status                   → Lihat progress recording
```

**Output:**
```
🎬 **RECORDING STATUS**

📝 **Label**: jalan_lurus
⏱️ **Progress**: 12.5 / 30 menit
📊 **Data Points**: 7,500

📈 **Progress Bar**:
████████████░░░░░░░░ 41.7%

⏹️ Gunakan /record_stop untuk stop
```

#### **3. Stop Recording**
```
/record_stop                     → Stop recording dan simpan data
```

**Output:**
```
⏹️ **RECORDING STOPPED**

📝 **Label**: jalan_lurus
⏱️ **Duration**: 30.2 menit
📊 **Data Points**: 18,120
📁 **File**: recording_jalan_lurus_20250804_143022.csv

💾 Data tersimpan di server
📥 Gunakan /record_export jalan_lurus untuk download
```

#### **4. Download Data CSV**
```
/record_export jalan_lurus       → Download file CSV
```

**Output:** File CSV dikirim ke Telegram dengan format:
```csv
timestamp,x,y,z,label,condition
1703123456789,1.23,-9.87,2.45,jalan_lurus,normal
1703123456889,1.25,-9.85,2.47,jalan_lurus,normal
...
```

### **Workflow Testing Motor:**

#### **Testing Jalan Lurus:**
1. **HP**: `/record_start jalan_lurus 30`
2. **Motor**: Jalan lurus 30 menit
3. **HP**: `/record_stop`
4. **HP**: `/record_export jalan_lurus`

#### **Testing Jalan Berlubang:**
1. **HP**: `/record_start jalan_berlubang 60`
2. **Motor**: Jalan berlubang 60 menit
3. **HP**: `/record_stop`
4. **HP**: `/record_export jalan_berlubang`

#### **Testing Jalan Tanjakan:**
1. **HP**: `/record_start jalan_tanjakan 45`
2. **Motor**: Jalan tanjakan 45 menit
3. **HP**: `/record_stop`
4. **HP**: `/record_export jalan_tanjakan`

### **Keunggulan Recording System:**

✅ **Real-time Progress**: Lihat progress recording langsung di HP  
✅ **Auto-save**: Data tersimpan otomatis ke CSV  
✅ **Organized**: Data terlabel per kondisi jalan  
✅ **High Volume**: Support ribuan data points  
✅ **Easy Export**: Download CSV langsung dari Telegram  
✅ **No Laptop**: Tidak perlu bawa laptop saat testing  

### **Data yang Direcord:**

- **Timestamp**: Waktu pengukuran (milliseconds)
- **X, Y, Z**: Nilai akselerasi dari ADXL345
- **Label**: Kondisi jalan (jalan_lurus, jalan_berlubang, dll)
- **Condition**: Status motor (normal, ringan, berat)

### **Estimasi Data Points:**

- **10 Hz sampling**: 600 data points per menit
- **30 menit**: ~18,000 data points
- **60 menit**: ~36,000 data points
- **120 menit**: ~72,000 data points

---

**Status**: ✅ Ready to Use  
**Last Updated**: August 4, 2025  
**Version**: 3.0 (with Recording System)
