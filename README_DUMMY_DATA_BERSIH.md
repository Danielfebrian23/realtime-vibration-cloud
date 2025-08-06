# Data Dummy Berdasarkan Dataset_Bersih.xlsx

## 📋 Overview

File ini berisi data dummy yang dibuat berdasarkan struktur dan karakteristik asli dari `Dataset_Bersih.xlsx` Anda. Data dummy ini mensimulasikan 3 kondisi motor dengan karakteristik yang sama dengan data asli:

- **Suprax(Normal)**: Kondisi motor normal
- **BearingAus(Ringan)**: Kondisi motor dengan anomali ringan
- **Axelo(Berat)**: Kondisi motor dengan anomali berat

## 📁 File yang Dibuat

### `Dummy_Data_Based_on_Dataset_Bersih.xlsx`

File Excel dengan 5 sheet untuk berbagai scenario testing:

#### 📊 Sheet 1: `Scenario1_Normal_to_Ringan`
- **1500 samples** (1000 Normal + 500 Ringan)
- Mensimulasikan transisi dari kondisi normal ke anomali ringan
- Berguna untuk testing sensitivitas deteksi anomali awal

#### 📊 Sheet 2: `Scenario2_Normal_to_Berat`
- **1500 samples** (1000 Normal + 500 Berat)
- Mensimulasikan transisi dari kondisi normal ke anomali berat
- Berguna untuk testing deteksi anomali serius

#### 📊 Sheet 3: `Scenario3_Mixed_Training`
- **17,483 samples** (campuran semua kondisi)
- Data lengkap untuk training model
- Distribusi: Normal (5797), Ringan (5848), Berat (5838)

#### 📊 Sheet 4: `Scenario4_Realtime_Simulation`
- **3000 samples** (5 menit simulasi real-time)
- Mensimulasikan 5 menit data dengan perubahan kondisi:
  - 0-3.3 menit: Normal
  - 3.3-6.6 menit: Ringan
  - 6.6-10 menit: Berat
- Ideal untuk testing sistem real-time

#### 📊 Sheet 5: `Summary`
- Ringkasan semua scenario
- Statistik jumlah samples per kondisi
- Durasi simulasi

## 🚀 Cara Penggunaan

### 1. Testing Offline
```bash
# Test data dummy tanpa server
python test_dummy_data_realtime.py
```

### 2. Testing Real-Time
```bash
# 1. Start server real-time
python realtime_vibration_server.py

# 2. Di terminal lain, jalankan testing
python test_dummy_data_realtime.py
```

### 3. Manual Testing
```python
import pandas as pd

# Load data untuk testing
df = pd.read_excel("Dummy_Data_Based_on_Dataset_Bersih.xlsx", 
                   sheet_name='Scenario4_Realtime_Simulation')

# Akses data
print(f"Total samples: {len(df)}")
print(f"Conditions: {df['Source'].unique()}")
```

## 📊 Karakteristik Data

### Berdasarkan Analisis Dataset_Bersih.xlsx:

#### Suprax(Normal):
- X: 1.0859 ± 1.2323
- Y: -10.4824 ± 2.0763
- Z: 1.8492 ± 1.9800
- Count: 5797 samples

#### Axelo(Berat):
- X: 0.7083 ± 1.3938
- Y: 10.0188 ± 1.1485
- Z: 0.3893 ± 3.3622
- Count: 5838 samples

#### BearingAus(Ringan):
- X: 0.6280 ± 6.9119
- Y: -0.2017 ± 39.9527
- Z: 10.3364 ± 37.8159
- Count: 5848 samples

## 🧪 Testing Scenarios

### Scenario 1: Normal → Ringan
- **Tujuan**: Test deteksi anomali ringan
- **Durasi**: ~5 menit
- **Pola**: Normal stabil → Transisi → Ringan

### Scenario 2: Normal → Berat
- **Tujuan**: Test deteksi anomali berat
- **Durasi**: ~5 menit
- **Pola**: Normal stabil → Transisi → Berat

### Scenario 3: Mixed Training
- **Tujuan**: Training model
- **Data**: Semua kondisi tercampur
- **Gunakan**: Untuk melatih Isolation Forest

### Scenario 4: Real-Time Simulation
- **Tujuan**: Testing sistem real-time
- **Durasi**: 10 menit (5 menit simulasi)
- **Pola**: Normal → Ringan → Berat

## 🔧 Integration dengan Sistem Real-Time

### Format Data ESP32:
```json
{
    "x": [float],
    "y": [float],
    "z": [float],
    "timestamp": int
}
```

### Endpoint Testing:
- **URL**: `http://localhost:5000/predict`
- **Method**: POST
- **Content-Type**: application/json

### Response Format:
```json
{
    "timestamp": int,
    "severity": "NORMAL|RINGAN|BERAT",
    "confidence": float,
    "features": {
        "rms_x": float,
        "rms_y": float,
        "rms_z": float,
        "PC1": float,
        "PC2": float,
        "distance_from_normal": float
    },
    "status": "SUCCESS"
}
```

## 📈 Expected Results

### Untuk Data Normal:
- **Severity**: NORMAL (80-90%)
- **Confidence**: 0.7-0.95
- **Distance**: < 0.05

### Untuk Data Ringan:
- **Severity**: RINGAN (70-80%)
- **Confidence**: 0.6-0.85
- **Distance**: 0.05-0.1

### Untuk Data Berat:
- **Severity**: BERAT (80-90%)
- **Confidence**: 0.7-0.95
- **Distance**: > 0.1

## 🛠️ Troubleshooting

### Masalah Umum:

1. **Server tidak running**:
   ```bash
   python realtime_vibration_server.py
   ```

2. **Data tidak terload**:
   - Pastikan file Excel ada di folder yang sama
   - Cek nama sheet yang benar

3. **Error connection**:
   - Pastikan server berjalan di port 5000
   - Cek firewall/antivirus

4. **Data format error**:
   - Pastikan kolom: `X `, `Y `, `Z `, `Source`
   - Perhatikan spasi di akhir nama kolom

## 📝 Notes

- Data dummy dibuat berdasarkan karakteristik asli `Dataset_Bersih.xlsx`
- Struktur kolom sama persis dengan data asli
- Distribusi dan statistik disesuaikan dengan data real
- Cocok untuk testing algoritma Isolation Forest real-time
- Dapat digunakan untuk training dan testing model

## 🎯 Next Steps

1. **Testing Real-Time**: Jalankan `test_dummy_data_realtime.py`
2. **Training Model**: Gunakan `Scenario3_Mixed_Training`
3. **Performance Analysis**: Cek hasil di `realtime_test_results.csv`
4. **Model Optimization**: Sesuaikan parameter berdasarkan hasil testing

---

**Dibuat berdasarkan**: `Dataset_Bersih.xlsx`  
**Struktur**: 17,483 samples dengan 3 kondisi  
**Format**: Excel dengan 5 scenario testing  
**Compatibility**: Real-time vibration analysis system 