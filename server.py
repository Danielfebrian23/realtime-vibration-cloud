import os
import time
import threading
import numpy as np
import pandas as pd
import joblib
import json
import matplotlib
matplotlib.use('Agg') # Backend non-GUI untuk server
import matplotlib.pyplot as plt
import io
import csv
from datetime import datetime
from flask import Flask, request, jsonify
from scipy.fft import fft
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, InputFile
from telegram.ext import Application, CommandHandler, CallbackQueryHandler, ContextTypes

# ==============================================================================
# KONFIGURASI
# ==============================================================================
# Load env manual jika perlu, atau set di Railway Variable
TOKEN = os.getenv("TELEGRAM_TOKEN")
AUTHORIZED_USER_ID = os.getenv("AUTHORIZED_USER_ID") 
MODEL_PATH = "MODEL_SIAP_DEPLOY.pkl"
RECORDING_DIR = "recordings_field"

if not os.path.exists(RECORDING_DIR):
    os.makedirs(RECORDING_DIR)

app = Flask(__name__)

# --- TAMBAHAN UNTUK HEALTHCHECK RAILWAY ---
@app.route('/', methods=['GET'])
def index():
    return "Server is Running!", 200

@app.route('/status', methods=['GET'])
def health_check():
    return jsonify({"status": "healthy", "model_loaded": model_data is not None}), 200
# ------------------------------------------

# Global Variables
model_data = None
# Struktur Session: {chat_id: {start_time, duration, predictions, raw_buffer, csv_path, is_stopped}}
active_sessions = {} 
data_lock = threading.Lock()

# ==============================================================================
# 1. LOAD MODEL (OTAK GOLDEN)
# ==============================================================================
def load_model():
    global model_data
    try:
        model_data = joblib.load(MODEL_PATH)
        print("[INFO] Model Random Forest Loaded!")
    except Exception as e:
        print(f"[CRITICAL ERROR] Gagal load model: {e}")
        model_data = None

# ==============================================================================
# 2. FEATURE EXTRACTION (GOLDEN LOGIC)
# ==============================================================================
def extract_features_live(signal_data):
    WINDOW_SIZE = 256
    START_BIN = 2
    
    # CLIPPING (Jurus Anti-Jalan Rusak)
    signal_clip = np.clip(signal_data, -5.0, 5.0)
    
    wx = signal_clip[:, 0]; wy = signal_clip[:, 1]; wz = signal_clip[:, 2]
    
    # FFT
    N = len(wx)
    END_BIN = N // 2
    fx = np.abs(fft(wx))[START_BIN:END_BIN]
    fy = np.abs(fft(wy))[START_BIN:END_BIN]
    fz = np.abs(fft(wz))[START_BIN:END_BIN]
    
    # TILT
    tilt_x = np.mean(wx); tilt_y = np.mean(wy); tilt_z = np.mean(wz)
    
    feat = np.concatenate([[tilt_x, tilt_y, tilt_z], fx, fy, fz])
    return feat.reshape(1, -1)

def predict_chunk(chunk_data):
    if model_data is None: return "Model Error"
    try:
        features = extract_features_live(chunk_data)
        features_scaled = model_data['scaler'].transform(features)
        features_pca = model_data['pca'].transform(features_scaled)

        # --- PERUBAHAN DIMULAI DISINI ---
        
        # 1. Ambil Probabilitas (Bukan cuma Label)
        # Outputnya array, misal: [0.1, 0.8, 0.1] (urutan sesuai classes_)
        probs = model_data['model'].predict_proba(features_pca)[0]
        classes = model_data['model'].classes_
        
        # 2. Hitung "Skor Kerusakan Fisik" (0.0 s/d 1.0)
        # Normal = 0.0, Ringan = 0.5, Berat = 1.0
        damage_score = 0.0
        
        for label, prob in zip(classes, probs):
            if label == 'rusak_berat':
                damage_score += (prob * 1.0)
            elif label == 'rusak_ringan':
                damage_score += (prob * 0.5)
            # Normal tidak nambah skor (tetap 0)
        
        # 3. Ambil Label Dominan (Untuk Laporan Akhir Pie Chart)
        prediction_label = model_data['model'].predict(features_pca)[0]
        
        return prediction_label, damage_score
        # ---------------------------------------------------------------
    except Exception as e:
        print(f"Error Prediction: {e}")
        return "Error"

# ==============================================================================
# 3. FITUR TAMBAHAN: VISUALISASI WAVEFORM (SNAPSHOT)
# ==============================================================================
def generate_waveform_snapshot(data_chunk):
    """Membuat gambar snapshot dan analisa singkat sinyal"""
    plt.figure(figsize=(8, 4))
    plt.plot(data_chunk[:, 0], label='X', color='r', alpha=0.7)
    plt.plot(data_chunk[:, 1], label='Y', color='g', alpha=0.7)
    plt.plot(data_chunk[:, 2], label='Z', color='b', alpha=0.7)
    plt.title("Live Sensor Monitor (Raw Data)")
    plt.ylim(-15, 15) 
    plt.legend()
    plt.grid(True, which='both', linestyle='--', linewidth=0.5)
    
    img_io = io.BytesIO()
    plt.savefig(img_io, format='png')
    img_io.seek(0)
    plt.close()
    
    # Analisa Sederhana (Standard Deviation)
    std_dev = np.std(data_chunk)
    status_text = ""
    
    # Ambang batas std_dev untuk menentukan hidup/mati
    # Jika sensor mati/kabel putus, biasanya nilai konstan atau noise sangat kecil (< 0.05)
    if std_dev < 0.05:
        status_text = (
            "⚠️ **PERINGATAN: SINYAL DATAR / MATI**\n\n"
            "Grafik menunjukkan garis lurus. Sensor tidak mendeteksi getaran.\n"
            "Saran Perbaikan:\n"
            "1. Cek kabel sensor, pastikan tidak putus.\n"
            "2. Pastikan alat menyala dan baterai terisi.\n"
            "3. Bawa ke teknisi jika masalah berlanjut."
        )
    else:
        status_text = (
            "✅ **STATUS: SENSOR AKTIF**\n\n"
            "Grafik menunjukkan getaran yang wajar.\n"
            "Alat berfungsi normal. Silakan lanjutkan pengujian."
        )
        
    return img_io, status_text

# ==============================================================================
# 4. TELEGRAM BOT LOGIC
# ==============================================================================
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    # --- CEK OTORISASI ---
    user_id = str(update.effective_user.id)
    if AUTHORIZED_USER_ID and user_id != AUTHORIZED_USER_ID:
        await update.message.reply_text(f"⛔ **AKSES DITOLAK.** ID Anda: {user_id}")
        return
    # ---------------------

    keyboard = [
        [InlineKeyboardButton("⏱️ Tes 5 Menit", callback_data='5'),
         InlineKeyboardButton("⏱️ Tes 15 Menit", callback_data='15')],
        [InlineKeyboardButton("⏱️ Tes 30 Menit", callback_data='30')],
        [InlineKeyboardButton("📊 Cek Status", callback_data='status'),
         InlineKeyboardButton("📈 Cek Sinyal", callback_data='snapshot')] 
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    await update.message.reply_text(
        "🛠️ *Sistem Diagnosa Roda Gigi (RF + Clipping)*\n\n"
        "Menu Utama:\n"
        "1. Pilih durasi tes untuk mulai.\n"
        "2. 'Cek Sinyal' untuk memastikan sensor hidup.\n\n"
        "_Pastikan motor aman sebelum tes!_",
        reply_markup=reply_markup, parse_mode='Markdown'
    )

async def button_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    
    user_id = str(query.from_user.id)
    if AUTHORIZED_USER_ID and user_id != AUTHORIZED_USER_ID:
        await query.answer("Akses Ditolak!", show_alert=True)
        return

    await query.answer()
    chat_id = query.message.chat_id
    data = query.data
    
    # --- TOMBOL STOP (FITUR BARU) ---
    if data == 'stop':
        if chat_id in active_sessions:
            active_sessions[chat_id]['is_stopped'] = True # Trigger flag berhenti
            await query.edit_message_text("🛑 **Menghentikan Pengujian...**\nMenunggu data terakhir diproses...")
        else:
            await query.edit_message_text("❌ Tidak ada pengujian yang berjalan.")
        return

    # --- FITUR SNAPSHOT (CEK KONEKSI SENSOR) ---
    if data == 'snapshot':
        if chat_id in active_sessions and len(active_sessions[chat_id]['raw_buffer']) > 50:
            snapshot_data = np.array(active_sessions[chat_id]['raw_buffer'][-200:])
            img, status_txt = generate_waveform_snapshot(snapshot_data)
            await context.bot.send_photo(chat_id=chat_id, photo=img, caption=status_txt, parse_mode='Markdown')
        else:
            # Jika belum ada sesi, coba cek global buffer (opsional) atau suruh mulai dulu
            await query.edit_message_text("❌ Data belum masuk. Silakan mulai tes sebentar lalu cek lagi.")
        return

    # --- CEK STATUS ---
    if data == 'status':
        if chat_id in active_sessions:
            elapsed = (time.time() - active_sessions[chat_id]['start_time']) / 60
            dur = active_sessions[chat_id]['duration']
            count = len(active_sessions[chat_id]['predictions'])
            
            # Tambahkan tombol STOP di status
            kb_stop = [[InlineKeyboardButton("🛑 Hentikan Sekarang", callback_data='stop')]]
            
            await query.edit_message_text(
                f"⏳ *Merekam...*\nWaktu: {elapsed:.1f}/{dur} menit.\nData: {count} segmen.",
                parse_mode='Markdown',
                reply_markup=InlineKeyboardMarkup(kb_stop)
            )
        else:
            await query.edit_message_text("💤 Tidak ada sesi aktif.")
        return

    # --- MULAI RECORDING ---
    duration = int(data)
    filename = f"field_test_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv"
    filepath = os.path.join(RECORDING_DIR, filename)
    
    with open(filepath, 'w', newline='') as f:
        writer = csv.writer(f, delimiter=';')
        writer.writerow(['timestamp', 'x', 'y', 'z'])

    active_sessions[chat_id] = {
        'start_time': time.time(),
        'duration': duration,
        'predictions': [], 
        'raw_buffer': [],
        'csv_path': filepath,
        'is_stopped': False, # Flag untuk stop manual
        # --- TAMBAHAN BARU ---
        'ema_condition': 0.0  # Nilai awal kondisi motor (dianggap sehat/0.0)
        # ---------------------
        
    }
    
    # Tampilkan tombol STOP saat mulai
    kb_stop = [[InlineKeyboardButton("🛑 Hentikan Sekarang", callback_data='stop')]]
    
    await query.edit_message_text(
        f"✅ *Tes {duration} Menit Dimulai!*\n"
        f"💾 Log: `{filename}`\n\n"
        "Jalan kan motor sekarang. Tekan tombol di bawah jika ingin berhenti lebih awal.",
        parse_mode='Markdown',
        reply_markup=InlineKeyboardMarkup(kb_stop)
    )

def generate_final_report(predictions, duration_set, start_time, csv_filename):
    actual_duration = (time.time() - start_time) / 60
    
    df_res = pd.DataFrame(predictions, columns=['kondisi'])
    
    if len(predictions) == 0:
        return "⚠️ Tidak ada data yang terkumpul. Cek sensor.", None
        
    counts = df_res['kondisi'].value_counts()
    majority = counts.idxmax()
    percent = (counts.max() / len(predictions)) * 100
    
    # Pie Chart
    plt.figure(figsize=(6, 6))
    plt.pie(counts, labels=counts.index, autopct='%1.1f%%', colors=['#66b3ff','#99ff99','#ffcc99','#ff9999'])
    plt.title(f"Diagnosa Akhir (Durasi: {actual_duration:.1f} m)")
    img_io = io.BytesIO()
    plt.savefig(img_io, format='png')
    img_io.seek(0)
    plt.close()
    
    # --- TIPS & SARAN LENGKAP ---
    tips_map = {
        'normal': (
            "✅ **KONDISI: NORMAL (SEHAT)**\n"
            "Mesin dalam keadaan prima. Getaran berada dalam batas wajar.\n\n"
            "🔧 **Saran Perawatan:**\n"
            "- Lanjutkan jadwal ganti oli gardan rutin (setiap 8.000 km).\n"
            "- Periksa tekanan ban agar getaran jalan tetap minim.\n"
            "- Tidak perlu tindakan perbaikan saat ini."
        ),
        'rusak_ringan': (
            "⚠️ **KONDISI: RUSAK RINGAN (GEJALA AWAL)**\n"
            "Terdeteksi pola getaran abnormal yang mengindikasikan keausan awal pada gigi transmisi.\n\n"
            "🔧 **Saran Perbaikan:**\n"
            "- **Segera ganti oli gardan** untuk melumasi gigi yang mulai aus.\n"
            "- Hindari membawa beban berlebih atau 'hentakan gas' mendadak.\n"
            "- Jadwalkan pemeriksaan ke bengkel dalam 1-2 minggu ke depan."
        ),
        'rusak_berat': (
            "⛔ **KONDISI: RUSAK BERAT (BAHAYA)**\n"
            "Pola getaran sangat kasar! Indikasi gigi rompal, bearing pecah, atau keausan ekstrim.\n\n"
            "🔧 **Saran Perbaikan:**\n"
            "- **JANGAN PAKSA JALAN JAUH.** Risiko mogok atau terkunci sangat tinggi.\n"
            "- Segera bawa ke bengkel resmi untuk bongkar gearbox (CVT).\n"
            "- Siapkan biaya untuk penggantian set gigi rasio/bearing."
        )
    }
    
    advice = tips_map.get(majority, "Hubungi teknisi untuk analisa manual.")
    
    text = (
        f"📊 **LAPORAN DIAGNOSA AKHIR**\n"
        f"-----------------------------\n"
        f"⏱ Durasi Aktual: {actual_duration:.1f} Menit\n"
        f"📈 Sampel Data: {len(predictions)}\n\n"
        f"🏆 **HASIL: {majority.upper().replace('_', ' ')}**\n"
        f"Kepercayaan: {percent:.1f}%\n\n"
        f"{advice}"
    )
    return text, img_io

# ==============================================================================
# 5. FLASK ENDPOINT (MERGED LOGIC)
# ==============================================================================
@app.route('/raw_data', methods=['POST'])
def receive_data():
    try:
        content = request.json
        raw_chunk = np.array(content['data']) 
        # === TAMBAHAN DEBUGGING (Supaya muncul di Log Railway) ===
        # Kita print data pertama saja biar log gak meledak
        if len(raw_chunk) > 0:
            print(f"[DATA MASUK] {len(raw_chunk)} Sampel. Data #1: {raw_chunk[0]}")
        # =========================================================
        
        users_done = []
        
        for chat_id, session in active_sessions.items():
            # 1. Cek Apakah Waktu Habis ATAU Tombol Stop Ditekan
            elapsed = (time.time() - session['start_time']) / 60
            is_time_up = elapsed >= session['duration']
            is_force_stop = session.get('is_stopped', False)
            
            if is_time_up or is_force_stop:
                users_done.append(chat_id)
                continue
            
            # 2. SIMPAN CSV (VERSI ANTI-GADO-GADO)
            # Kita paksa format f"{val:.4f}" -> Selalu pakai TITIK, 4 angka belakang koma.
            # Ini mengabaikan setting Laptop (Indo/US), pokoknya outputnya pasti TITIK.
            with open(session['csv_path'], 'a', newline='') as f:
                writer = csv.writer(f, delimiter=';') # Tetap pakai titik koma sebagai pemisah kolom
                now_str = datetime.now().strftime('%Y-%m-%d %H:%M:%S.%f')[:-3]
                
                for row in raw_chunk:
                    # row[0], row[1], row[2] adalah float.
                    # Kita ubah jadi string manual dengan format '.4f' (Standard US)
                    x_str = f"{row[0]:.4f}"
                    y_str = f"{row[1]:.4f}"
                    z_str = f"{row[2]:.4f}"
                    
                    writer.writerow([now_str, x_str, y_str, z_str])

                    
            # 3. BUFFER & PREDICT
            session['raw_buffer'].extend(raw_chunk)
            while len(session['raw_buffer']) >= 256:
                window = np.array(session['raw_buffer'][:256])
                session['raw_buffer'] = session['raw_buffer'][128:] 
                # Panggil fungsi baru (terima 2 output: Label & Skor)
                res_label, raw_score = predict_chunk(window)
                session['predictions'].append(res_label)
                
                # --- IMPLEMENTASI EMA (PENGHALUSAN FISIKA) ---
                ALPHA = 0.15  # Sensitivitas (0.1 = Sangat Halus, 0.5 = Agresif)
                
                # Rumus: Nilai Baru = (Skor Mentah * Alpha) + (Nilai Lama * (1 - Alpha))
                prev_ema = session['ema_condition']
                current_ema = (raw_score * ALPHA) + (prev_ema * (1.0 - ALPHA))
                
                # Simpan kembali ke sesi untuk loop berikutnya
                session['ema_condition'] = current_ema

                # === TAMBAHAN: KIRIM NOTIF KE TELEGRAM KALO BAHAYA ===
                # Jika skor kerusakan > 0.75 (75%) dan belum pernah kirim warning
                if current_ema > 0.75 and not session.get('warning_sent', False):
                    
                    # 1. Tandai biar gak nyepam (kirim sekali aja)
                    session['warning_sent'] = True 
                    
                    # 2. Kirim Pesan Bahaya ke Telegram
                    import requests
                    pesan_bahaya = (
                        "⚠️ **PERINGATAN DINI TERDETEKSI!** ⚠️\n\n"
                        f"Skor Kerusakan Fisik: **{current_ema*100:.1f}%**\n"
                        "Sistem mendeteksi tren getaran yang sangat berbahaya secara konsisten.\n"
                        "Sebaiknya hentikan motor untuk pengecekan fisik."
                    )
                    requests.post(
                        f"https://api.telegram.org/bot{TOKEN}/sendMessage", 
                        data={'chat_id': chat_id, 'text': pesan_bahaya, 'parse_mode': 'Markdown'}
                    )
                
                # --- CEK KONDISI REAL-TIME (OPSIONAL LOGGING) ---
                # Sekarang Anda punya variabel 'current_ema' yang sangat akurat!
                # 0.0 - 0.3 = Sehat
                # 0.3 - 0.6 = Gejala (Ringan)
                # > 0.6     = Bahaya (Berat)
                
                print(f"Label: {res_label}, Raw: {raw_score:.2f}, Physics-EMA: {current_ema:.2f}")
        
        # Handle User Selesai / Stop
        for chat_id in users_done:
            session = active_sessions.pop(chat_id)
            report_txt, chart = generate_final_report(
                session['predictions'], 
                session['duration'], 
                session['start_time'],
                os.path.basename(session['csv_path'])
            )
            
            import requests
            url = f"https://api.telegram.org/bot{TOKEN}/sendPhoto"
            
            # Kirim Report Gambar + Teks
            if chart:
                requests.post(url, files={'photo': chart}, data={'chat_id': chat_id, 'caption': report_txt, 'parse_mode': 'Markdown'})
            else:
                requests.post(f"https://api.telegram.org/bot{TOKEN}/sendMessage", data={'chat_id': chat_id, 'text': report_txt})
            
            # Kirim File CSV
            url_doc = f"https://api.telegram.org/bot{TOKEN}/sendDocument"
            with open(session['csv_path'], 'rb') as f:
                requests.post(url_doc, data={'chat_id': chat_id}, files={'document': f})

        return jsonify({"status": "ok"}), 200

    except Exception as e:
        print(f"Error: {e}")
        return jsonify({"status": "error"}), 500

# ==============================================================================
# MAIN
# ==============================================================================
def run_flask():
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port)

def run_telegram():
    app_bot = Application.builder().token(TOKEN).build()
    app_bot.add_handler(CommandHandler("start", start))
    app_bot.add_handler(CallbackQueryHandler(button_handler))
    print("Bot Polling...")
    app_bot.run_polling()

if __name__ == '__main__':
    load_model()
    t = threading.Thread(target=run_flask)
    t.start()
    if TOKEN: run_telegram()

    else: print("TOKEN TELEGRAM KOSONG!")




