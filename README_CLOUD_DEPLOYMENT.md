# 🚀 Cloud Deployment Guide - Real-time Vibration Analysis

## 📋 Overview

Panduan lengkap untuk deploy sistem real-time vibration analysis ke Railway cloud dan update ESP32 untuk koneksi cloud.

---

## 🏗️ Arsitektur Cloud

```
ESP32 S3 + ADXL345 → WiFi/Internet → Railway Cloud → Telegram Bot
                    ↓
              Real-time ML Analysis
                    ↓
              Global Access 24/7
```

---

## 📁 File yang Dibutuhkan untuk GitHub

### **Wajib Upload ke GitHub:**
```
📁 Repository Root/
├── 📄 realtime_vibration_server_telegram_fixed.py  (Server utama)
├── 📄 requirements.txt                             (Dependencies)
├── 📄 railway.json                                 (Railway config)
├── 📄 Procfile                                     (Railway start command)
├── 📄 .gitignore                                   (Git ignore rules)
├── 📄 README_CLOUD_DEPLOYMENT.md                   (This file)
├── 📄 Dataset_Bersih.xlsx                          (Training data)
├── 📄 Dataset PCA (Normal 80 + Ringan 20).xlsx     (Training data)
└── 📄 Dataset PCA (Normal 80 + Berat 20).xlsx      (Training data)
```

### **Tidak Perlu Upload:**
- `esp32_adxl345_realtime/` (folder Arduino)
- `*.bat` files (Windows scripts)
- `test_*.py` files (testing scripts)
- `*.png`, `*.csv` (hasil testing)

---

## 🚀 Step-by-Step Deployment

### **1. Upload ke GitHub**

```bash
# Di folder RealTime_TA
git init
git add .
git commit -m "Initial commit for cloud deployment"
git branch -M main
git remote add origin https://github.com/USERNAME/REPOSITORY_NAME.git
git push -u origin main
```

### **2. Deploy ke Railway**

1. **Buka Railway Dashboard**
2. **Klik "New +"** → **"Deploy from GitHub repo"**
3. **Pilih repository** kamu
4. **Configure Service:**
   - **Name**: `realtime-vibration-server`
   - **Environment**: `Production`
   - **Branch**: `main`

### **3. Set Environment Variables**

Di Railway dashboard, tambahkan:
```
TELEGRAM_TOKEN=7755530909:AAFkS6jH2fMT5X-Kp8hubcsl9g-t23PJqdk
AUTHORIZED_USER_ID=6080177529
```

### **4. Deploy**

- Klik **"Deploy Now"**
- Tunggu build selesai
- Status harus **"Deployed"**

---

## 🔧 Update ESP32 untuk Cloud

### **File yang Diperlukan:**
- `esp32_adxl345_realtime_cloud.ino` (sudah dibuat)

### **Langkah Update:**

1. **Buka Arduino IDE**
2. **Buka file** `esp32_adxl345_realtime_cloud.ino`
3. **Update WiFi credentials:**
   ```cpp
   const char* ssid = "NAMA_WIFI_KAMU";
   const char* password = "PASSWORD_WIFI_KAMU";
   ```

4. **Update Railway URL** (setelah deploy berhasil):
   ```cpp
   const char* serverUrl = "https://YOUR_RAILWAY_URL.up.railway.app/predict";
   ```

5. **Upload ke ESP32 S3**

---

## 🌐 Dapatkan Railway URL

Setelah deploy berhasil di Railway:

1. **Buka service** di Railway dashboard
2. **Klik tab "Settings"**
3. **Copy "Domain"** yang muncul
4. **Format URL**: `https://DOMAIN.up.railway.app`

Contoh:
```
https://realtime-vibration-server-production.up.railway.app
```

---

## 🧪 Testing Cloud Deployment

### **1. Test Server Cloud**
```bash
# Test status endpoint
curl https://YOUR_RAILWAY_URL.up.railway.app/status

# Expected response:
{
  "status": "RUNNING",
  "model_loaded": true,
  "buffer_size": 0,
  "timestamp": "2024-01-01T12:00:00",
  "measuring_status": true
}
```

### **2. Test ESP32 Connection**
1. **Upload kode cloud** ke ESP32
2. **Buka Serial Monitor**
3. **Lihat output:**
   ```
   ESP32-S3 Cloud Version started.
   Connecting to cloud server...
   WiFi connected!
   IP address: 192.168.1.100
   Cloud server: https://YOUR_RAILWAY_URL.up.railway.app/predict
   System ready for cloud vibration analysis!
   ```

### **3. Test Telegram Bot**
1. **Buka Telegram**
2. **Chat dengan bot**
3. **Kirim `/start`**
4. **Kirim `/cek`**

---

## 🔄 Auto-Deploy Setup

### **GitHub Actions (Optional)**

Buat file `.github/workflows/deploy.yml`:

```yaml
name: Deploy to Railway
on:
  push:
    branches: [main]
jobs:
  deploy:
    runs-on: ubuntu-latest
    steps:
    - uses: actions/checkout@v2
    - name: Deploy to Railway
      uses: railway/deploy@v1
      with:
        railway_token: ${{ secrets.RAILWAY_TOKEN }}
```

---

## 🛠️ Troubleshooting

### **Error Railway Build:**
- ✅ **File `railway.json`** sudah dibuat
- ✅ **File `requirements.txt`** sudah ada
- ✅ **File `Procfile`** sudah ada
- ✅ **Dependencies** sudah lengkap

### **ESP32 Tidak Connect:**
- ✅ **WiFi credentials** sudah benar
- ✅ **Railway URL** sudah update
- ✅ **Server cloud** sudah running
- ✅ **Internet connection** stabil

### **Telegram Bot Error:**
- ✅ **Token** sudah benar
- ✅ **User ID** sudah benar
- ✅ **Server** sudah running

---

## 📊 Monitoring

### **Railway Dashboard:**
- **Logs**: Cek error dan status
- **Metrics**: CPU, Memory usage
- **Deployments**: History deployment

### **ESP32 Serial Monitor:**
- **WiFi status**
- **HTTP response codes**
- **Data transmission**

### **Telegram Bot:**
- **Command responses**
- **Prediction results**

---

## 🎯 Keuntungan Cloud Deployment

✅ **24/7 Availability** - Server selalu on  
✅ **Global Access** - Akses dari mana saja  
✅ **Auto Scaling** - Railway handle traffic  
✅ **Easy Updates** - Push ke GitHub = auto deploy  
✅ **No Local PC** - Tidak perlu laptop selalu on  
✅ **Professional** - URL domain yang proper  

---

## 📞 Support

Jika ada masalah:

1. **Cek Railway logs** di dashboard
2. **Cek ESP32 Serial Monitor**
3. **Test endpoints** dengan curl/Postman
4. **Verify environment variables**

---

**🎉 Setelah deploy berhasil, ESP32 kamu bisa kirim data ke cloud dari mana saja!** 