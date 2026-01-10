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
TOKEN = os.getenv("TELEGRAM_TOKEN")
AUTHORIZED_USER_ID = os.getenv("AUTHORIZED_USER_ID") 
MODEL_PATH = "MODEL_SIAP_DEPLOY.pkl"
RECORDING_DIR = "recordings_field"

if not os.path.exists(RECORDING_DIR):
    os.makedirs(RECORDING_DIR)

app = Flask(__name__)

# --- HEALTHCHECK ---
@app.route('/', methods=['GET'])
def index(): return "Server Running!", 200

@app.route('/status', methods=['GET'])
def health_check(): return jsonify({"status": "healthy"}), 200

# Global Variables
model_data = None
active_sessions = {} 
data_lock = threading.Lock()

# ==============================================================================
# 1. LOAD MODEL
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
# 2. FEATURE EXTRACTION & PREDICTION
# ==============================================================================
def extract_features_live(signal_data):
    # CLIPPING (Jurus Anti-Jalan Rusak/Polisi Tidur)
    signal_clip = np.clip(signal_data, -5.0, 5.0)
    wx = signal_clip[:, 0]; wy = signal_clip[:, 1]; wz = signal_clip[:, 2]
    
    START_BIN = 2
    N = len(wx)
    END_BIN = N // 2
    
    fx = np.abs(fft(wx))[START_BIN:END_BIN]
    fy = np.abs(fft(wy))[START_BIN:END_BIN]
    fz = np.abs(fft(wz))[START_BIN:END_BIN]
    
    tilt_x = np.mean(wx); tilt_y = np.mean(wy); tilt_z = np.mean(wz)
    feat = np.concatenate([[tilt_x, tilt_y, tilt_z], fx, fy, fz])
    return feat.reshape(1, -1)

def predict_chunk(chunk_data):
    if model_data is None: return "Model Error", 0.0
    try:
        features = extract_features_live(chunk_data)
        features_scaled = model_data['scaler'].transform(features)
        features_pca = model_data['pca'].transform(features_scaled)
        
        # 1. Ambil Probabilitas
        probs = model_data['model'].predict_proba(features_pca)[0]
        classes = model_data['model'].classes_
        
        # 2. Hitung Skor Kerusakan Fisik (0.0 - 1.0)
        damage_score = 0.0
        for label, prob in zip(classes, probs):
            if label == 'rusak_berat':
                damage_score += (prob * 1.0)
            elif label == 'rusak_ringan':
                damage_score += (prob * 0.5)
        
        # 3. Ambil Label Utama
        prediction_label = model_data['model'].predict(features_pca)[0]
        
        return prediction_label, damage_score
    except Exception as e:
        print(f"Error Prediction: {e}")
        return "Error", 0.0

# ==============================================================================
# 3. VISUALISASI SINYAL (SNAPSHOT)
# ==============================================================================
def generate_waveform_snapshot(data_chunk):
    plt.figure(figsize=(8, 4))
    plt.plot(data_chunk[:, 0], label='X', color='r', alpha=0.7)
    plt.plot(data_chunk[:, 1], label='Y', color='g', alpha=0.7)
    plt.plot(data_chunk[:, 2], label='Z', color='b', alpha=0.7)
    plt.title("Live Sensor Monitor (Raw Data)")
    plt.ylim(-15, 15) 
    plt.legend()
    plt.grid(True, linestyle='--', linewidth=0.5)
    
    img_io = io.BytesIO()
    plt.savefig(img_io, format='png')
    img_io.seek(0)
    plt.close()
    
    std_dev = np.std(data_chunk)
    if std_dev < 0.05:
        status_text = "⚠️ **PERINGATAN: SINYAL DATAR / MATI**\nCek kabel sensor!"
    else:
        status_text = "✅ **STATUS: SENSOR AKTIF**\nGrafik getaran terdeteksi."
        
    return img_io, status_text

# ==============================================================================
# 4. GENERATE LAPORAN AKHIR (GABUNGAN GRAFIK TREN + TEKS SARAN)
# ==============================================================================
def generate_final_report(session_data):
    scores = session_data['history_scores'] # List skor 0-100
    times = session_data['history_times']   # List waktu (menit)
    duration_actual = (time.time() - session_data['start_time']) / 60
    
    if not scores:
        return "⚠️ Tidak ada data yang terkumpul. Cek sensor.", None

    # 1. Hitung Statistik
    avg_score = np.mean(scores)
    max_score = np.max(scores)
    
    # 2. Tentukan Status Akhir (Logika Fisika EMA)
    # < 30% = Normal, 30-60% = Rusak Ringan, > 60% = Rusak Berat
    majority_key = 'normal'
    status_label = "NORMAL (SEHAT)"
    
    if avg_score > 65: 
        majority_key = 'rusak_berat'
        status_label = "BAHAYA (RUSAK BERAT)"
    elif avg_score > 40: 
        majority_key = 'rusak_ringan'
        status_label = "WARNING (RUSAK RINGAN)"
    
    # 3. BIKIN GRAFIK TREN KESEHATAN (Line Chart)
    # Ini lebih baik dari Pie Chart untuk melihat kapan rusaknya terjadi
    plt.figure(figsize=(10, 6)) # Agak tinggi biar jelas
    plt.plot(times, scores, color='blue', linewidth=2, label='Kondisi Motor')
    
    # Zona Warna Threshold
    plt.axhspan(0, 30, facecolor='green', alpha=0.1, label='Zona Aman')
    plt.axhspan(30, 60, facecolor='yellow', alpha=0.1, label='Zona Gejala')
    plt.axhspan(60, 100, facecolor='red', alpha=0.1, label='Zona Bahaya')
    
    plt.title(f"Grafik Kesehatan Motor (Durasi: {duration_actual:.1f} m)")
    plt.xlabel("Waktu (Menit)")
    plt.ylabel("Tingkat Kerusakan (%)")
    plt.ylim(0, 100)
    plt.grid(True, linestyle='--', alpha=0.5)
    plt.legend(loc='upper left')
    plt.tight_layout()
    
    img_io = io.BytesIO()
    plt.savefig(img_io, format='png')
    img_io.seek(0)
    plt.close()

    # 4. TEKS SARAN LENGKAP (Dari snippet kamu)
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
    
    advice = tips_map.get(majority_key, "Hubungi teknisi.")

    # Gabungkan Statistik + Saran
    text = (
        f"📊 **LAPORAN DIAGNOSA AKHIR**\n"
        f"-----------------------------\n"
        f"⏱ Durasi: {duration_actual:.1f} Menit\n"
        f"📈 Rata-rata Kerusakan: {avg_score:.1f}%\n"
        f"💥 Puncak Kerusakan: {max_score:.1f}%\n\n"
        f"{advice}\n\n"
        f"_Lihat grafik di atas untuk detail fluktuasi kondisi._"
    )
    
    return text, img_io

# ==============================================================================
# 5. TELEGRAM BOT LOGIC
# ==============================================================================
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = str(update.effective_user.id)
    if AUTHORIZED_USER_ID and user_id != AUTHORIZED_USER_ID:
        await update.message.reply_text("⛔ AKSES DITOLAK.")
        return

    keyboard = [
        [InlineKeyboardButton("⏱️ 5 Menit", callback_data='5'),
         InlineKeyboardButton("⏱️ 15 Menit", callback_data='15')],
        [InlineKeyboardButton("⏱️ 30 Menit", callback_data='30'),
         InlineKeyboardButton("♾️ Mode Bebas", callback_data='60')],
        [InlineKeyboardButton("📊 Cek Status", callback_data='status'),
         InlineKeyboardButton("📈 Cek Sinyal", callback_data='snapshot')] 
    ]
    await update.message.reply_text(
        "🛠️ *Sistem Diagnosa Roda Gigi (Dr. Motor)*\n"
        "Silakan pilih durasi tes atau cek sinyal.",
        reply_markup=InlineKeyboardMarkup(keyboard), parse_mode='Markdown'
    )

async def button_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    user_id = str(query.from_user.id)
    if AUTHORIZED_USER_ID and user_id != AUTHORIZED_USER_ID: return

    await query.answer()
    chat_id = query.message.chat_id
    data = query.data
    
    # --- STOP ---
    if data == 'stop':
        if chat_id in active_sessions:
            active_sessions[chat_id]['is_stopped'] = True 
            await query.edit_message_text("🛑 **Menghentikan Pengujian...**\nFinalisasi data...")
        else:
            await query.edit_message_text("❌ Tidak ada pengujian.")
        return

    # --- SNAPSHOT ---
    if data == 'snapshot':
        if chat_id in active_sessions and len(active_sessions[chat_id]['raw_buffer']) > 50:
            snapshot_data = np.array(active_sessions[chat_id]['raw_buffer'][-200:])
            img, status_txt = generate_waveform_snapshot(snapshot_data)
            await context.bot.send_photo(chat_id=chat_id, photo=img, caption=status_txt, parse_mode='Markdown')
        else:
            await query.edit_message_text("❌ Data belum masuk. Coba lagi nanti.")
        return

    # --- STATUS ---
    if data == 'status':
        if chat_id in active_sessions:
            elapsed = (time.time() - active_sessions[chat_id]['start_time']) / 60
            dur = active_sessions[chat_id]['duration']
            
            kb_control = [
                [InlineKeyboardButton("🔄 Refresh", callback_data='status'),
                 InlineKeyboardButton("📈 Cek Sinyal", callback_data='snapshot')],
                [InlineKeyboardButton("🛑 Hentikan Sekarang", callback_data='stop')]
            ]            
            await query.edit_message_text(
                f"⏳ *Status Rekaman*\n⏱ Waktu: {elapsed:.1f} / {dur} m\n\nKlik 'Cek Sinyal' untuk validasi sensor.",
                parse_mode='Markdown', reply_markup=InlineKeyboardMarkup(kb_control)
            )
        else:
            await query.edit_message_text("💤 Tidak ada sesi aktif.")
        return

    # --- MULAI RECORDING ---
    duration = int(data)
    
    # 1. FILE RAW (Data Teknis - Field Test)
    filename_raw = f"field_test_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv"
    filepath_raw = os.path.join(RECORDING_DIR, filename_raw)
    with open(filepath_raw, 'w', newline='') as f:
        csv.writer(f, delimiter=';').writerow(['timestamp', 'x', 'y', 'z'])

    # 2. FILE LAPORAN USER (Readable)
    filename_report = f"Laporan_Kondisi_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv"
    filepath_report = os.path.join(RECORDING_DIR, filename_report)
    with open(filepath_report, 'w', newline='') as f:
        csv.writer(f, delimiter=';').writerow(['Jam', 'Persentase_Kerusakan', 'Status_Diagnosa'])

    active_sessions[chat_id] = {
        'start_time': time.time(),
        'duration': duration,
        'predictions': [], 
        'raw_buffer': [],
        'csv_path_raw': filepath_raw,      
        'csv_path_report': filepath_report, 
        'history_scores': [], 
        'history_times': [],
        'is_stopped': False,
        'ema_condition': 0.0,
        'warning_sent': False
    }
    
    kb_control = [
        [InlineKeyboardButton("📊 Cek Status", callback_data='status'),
         InlineKeyboardButton("📈 Cek Sinyal", callback_data='snapshot')],
        [InlineKeyboardButton("🛑 Hentikan Sekarang", callback_data='stop')]
    ]
    
    await query.edit_message_text(
        f"✅ *Tes {duration} Menit Dimulai!*\n"
        f"📝 Mencatat ke: `{filename_raw}`\n\n"
        "Motor sedang direkam. Gunakan tombol di bawah untuk memantau.",
        parse_mode='Markdown', reply_markup=InlineKeyboardMarkup(kb_control)
    )

# ==============================================================================
# 6. FLASK ENDPOINT (MERGED LOGIC)
# ==============================================================================
@app.route('/raw_data', methods=['POST'])
def receive_data():
    try:
        # --- PENGAMAN 1: Cek apakah data valid JSON? ---
        # silent=True bikin dia gak langsung Error 400 kalau datanya rusak, tapi return None
        content = request.get_json(silent=True) 
        
        if not content:
            # Kalau data kosong/rusak, kita return 400 tapi print alasan biar jelas
            print("[WARNING] Terima data kosong/corrupt. Skip.")
            return jsonify({"status": "error", "msg": "Bad JSON"}), 400
            
        # --- PENGAMAN 2: Cek apakah ada kunci 'data'? ---
        if 'data' not in content:
            print("[WARNING] JSON valid tapi tidak ada key 'data'.")
            return jsonify({"status": "error", "msg": "No data key"}), 400

        raw_chunk = np.array(content['data']) 
        
        # --- PENGAMAN 3: Cek apakah isinya kosong? ---
        if len(raw_chunk) == 0:
            return jsonify({"status": "ok", "msg": "Empty data skipped"}), 200

        users_done = []
        
        # Lock thread biar gak tabrakan saat nulis file (Optional tapi bagus)
        with data_lock:
            for chat_id, session in active_sessions.items():
                elapsed = (time.time() - session['start_time']) / 60
                is_time_up = elapsed >= session['duration']
                is_force_stop = session.get('is_stopped', False)
                
                if is_time_up or is_force_stop:
                    users_done.append(chat_id)
                    continue
                
                # A. SIMPAN RAW DATA
                try:
                    with open(session['csv_path_raw'], 'a', newline='') as f:
                        writer = csv.writer(f, delimiter=';')
                        now_str = datetime.now().strftime('%Y-%m-%d %H:%M:%S.%f')[:-3]
                        for row in raw_chunk:
                            # Pastikan row punya 3 elemen (x,y,z)
                            if len(row) >= 3:
                                x_str = f"{row[0]:.4f}"; y_str = f"{row[1]:.4f}"; z_str = f"{row[2]:.4f}"
                                writer.writerow([now_str, x_str, y_str, z_str])
                except Exception as e:
                    print(f"[ERROR WRITE CSV] {e}")

                # B. BUFFER & PREDICT
                session['raw_buffer'].extend(raw_chunk)
                while len(session['raw_buffer']) >= 256:
                    window = np.array(session['raw_buffer'][:256])
                    session['raw_buffer'] = session['raw_buffer'][128:] 
                    
                    res_label, raw_score = predict_chunk(window)
                    session['predictions'].append(res_label)
                    
                    # C. EMA
                    ALPHA = 0.15
                    prev_ema = session['ema_condition']
                    current_ema = (raw_score * ALPHA) + (prev_ema * (1.0 - ALPHA))
                    session['ema_condition'] = current_ema

                    # D. REPORT USER
                    session['history_scores'].append(current_ema * 100)
                    session['history_times'].append(elapsed)

                    try:
                        with open(session['csv_path_report'], 'a', newline='') as f:
                            writer = csv.writer(f, delimiter=';')
                            jam = datetime.now().strftime('%H:%M:%S')
                            writer.writerow([jam, f"{current_ema * 100:.1f}%", res_label.upper()])
                    except Exception as e:
                        print(f"[ERROR REPORT] {e}")
                    
                    # E. WARNING
                    if current_ema > 0.75 and not session.get('warning_sent', False):
                        session['warning_sent'] = True 
                        import requests
                        try:
                            requests.post(
                                f"https://api.telegram.org/bot{TOKEN}/sendMessage", 
                                data={'chat_id': chat_id, 'text': "⚠️ **BAHAYA DETECTED!**", 'parse_mode': 'Markdown'},
                                timeout=5 # Timeout biar server gak bengong
                            )
                        except: pass
        
        # Handle Selesai (Di luar lock biar gak nge-block data masuk)
        for chat_id in users_done:
            session = active_sessions.pop(chat_id)
            try:
                report_txt, chart = generate_final_report(session)
                import requests
                
                # Kirim-kirim Telegram
                if chart:
                    requests.post(f"https://api.telegram.org/bot{TOKEN}/sendPhoto", 
                        files={'photo': chart}, data={'chat_id': chat_id, 'caption': report_txt, 'parse_mode': 'Markdown'})
                
                with open(session['csv_path_report'], 'rb') as f:
                    requests.post(f"https://api.telegram.org/bot{TOKEN}/sendDocument", 
                        data={'chat_id': chat_id, 'caption': "📄 Laporan User"}, files={'document': f})

                with open(session['csv_path_raw'], 'rb') as f:
                    requests.post(f"https://api.telegram.org/bot{TOKEN}/sendDocument", 
                        data={'chat_id': chat_id, 'caption': "💾 Data Mentah"}, files={'document': f})
            except Exception as e:
                print(f"[ERROR FINALIZE] {e}")

        return jsonify({"status": "ok"}), 200

    except Exception as e:
        # Print error lengkap biar tau kenapa 500
        import traceback
        traceback.print_exc() 
        return jsonify({"status": "error", "details": str(e)}), 500

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
    else: print("TOKEN KOSONG!")


