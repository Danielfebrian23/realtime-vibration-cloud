from flask import Flask, request, jsonify
from flask_cors import CORS
import pandas as pd
import numpy as np
from sklearn.ensemble import IsolationForest
from sklearn.decomposition import PCA
from sklearn.preprocessing import StandardScaler
import joblib
import json
from datetime import datetime
import threading
import time
import os
import sys
import scipy.stats
from scipy import signal

try:
    from dotenv import load_dotenv
    load_dotenv()
except Exception:
    print("python-dotenv not available; skipping .env loading.")


# Optional Telegram imports
try:
    from telegram import Update
    from telegram.ext import Application, CommandHandler, ContextTypes
    import matplotlib.pyplot as plt
    import io
    import requests
    TELEGRAM_AVAILABLE = True
except ImportError:
    TELEGRAM_AVAILABLE = False
    print("Telegram libraries not available. Running without Telegram bot.")

app = Flask(__name__)
CORS(app)  # Enable CORS for all routes

# Global variables untuk model dan preprocessing
iso_forest_model = None
pca_model = None
scaler_model = None
is_model_loaded = False

# Data buffer untuk real-time analysis
realtime_buffer = []
buffer_lock = threading.Lock()

# Variabel global untuk status pengukuran real-time
measuring_status = {'active': True}

# Global variables untuk recording
recording_status = {
    'active': False,
    'start_time': None,
    'duration_minutes': 0,
    'label': '',
    'data_points': 0,
    'file_path': ''
}

recording_data = []
recording_lock = threading.Lock()



# Telegram configuration (only if available)
if TELEGRAM_AVAILABLE:
    TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")
    AUTHORIZED_USER_ID_RAW = os.getenv("AUTHORIZED_USER_ID")
    PUBLIC_URL = os.getenv("PUBLIC_URL")
    ESP32_IP = os.getenv("ESP32_IP")
    ESP32_HTTP_PORT_RAW = os.getenv("ESP32_HTTP_PORT")

    missing_envs = [
        name for name, val in [
            ("TELEGRAM_TOKEN", TELEGRAM_TOKEN),
            ("AUTHORIZED_USER_ID", AUTHORIZED_USER_ID_RAW),
            ("PUBLIC_URL", PUBLIC_URL),
            ("ESP32_IP", ESP32_IP),
            ("ESP32_HTTP_PORT", ESP32_HTTP_PORT_RAW),
        ] if not val
    ]

    try:
        AUTHORIZED_USER_ID = int(AUTHORIZED_USER_ID_RAW) if AUTHORIZED_USER_ID_RAW else None
    except Exception:
        AUTHORIZED_USER_ID = None
        if "AUTHORIZED_USER_ID" not in missing_envs:
            missing_envs.append("AUTHORIZED_USER_ID (invalid integer)")

    try:
        ESP32_HTTP_PORT = int(ESP32_HTTP_PORT_RAW) if ESP32_HTTP_PORT_RAW else None
    except Exception:
        ESP32_HTTP_PORT = None
        if "ESP32_HTTP_PORT" not in missing_envs:
            missing_envs.append("ESP32_HTTP_PORT (invalid integer)")

    if missing_envs:
        print(f"Missing/invalid Telegram env vars: {', '.join(missing_envs)}. Telegram bot will be disabled.")
        TELEGRAM_AVAILABLE = False

# Simpan status terakhir
last_status = {
    'severity': 'NORMAL',
    'confidence': 0.98,
    'penjelasan': 'Motor dalam kondisi normal.',
    'tips': 'Cek motor setiap hari atau perminggu dengan menambahkan pelumas rantai atau chain cleaner agar dapat memperpanjang waktu masa rantai, dan untuk mengecek lebih akurat kapan mulai menyimpang bisa pakai smart device ini setiap saat!',
    'riwayat': [("NORMAL", 0.98), ("RINGAN", 0.6), ("BERAT", 0.2)]
}

# Dictionary untuk tips berdasarkan kondisi
TIPS_BY_CONDITION = {
    'NORMAL': "Cek motor setiap hari atau perminggu dengan menambahkan pelumas rantai atau chain cleaner agar dapat memperpanjang waktu masa rantai, dan untuk mengecek lebih akurat kapan mulai menyimpang bisa pakai smart device ini setiap saat!",
    'RINGAN': "Segera diganti pelumas jika belum diganti lama, jika ada serpihan logam atau sekedar menghindari hal yang lebih bermasalah dari keausan, bawa ke bengkel terdekat untuk menghindari hal yang lebih parah",
    'BERAT': "Segera bawa ke bengkel segera sebelum meluas permasalahannya ke poros atau transmisi motor atau lebih parah lagi mesin utama, pastikan komponen motor dibongkar untuk melihat permasalahannya"
}

# Dictionary untuk penjelasan berdasarkan kondisi
PENJELASAN_BY_CONDITION = {
    'NORMAL': "Motor dalam kondisi normal. Getaran yang terdeteksi masih dalam batas wajar dan tidak menunjukkan tanda-tanda kerusakan pada komponen motor.",
    'RINGAN': "Motor menunjukkan tanda-tanda awal anomali. Terdeteksi getaran yang sedikit menyimpang dari kondisi normal, kemungkinan ada keausan ringan pada komponen.",
    'BERAT': "Motor dalam kondisi yang memerlukan perhatian serius. Terdeteksi getaran yang sangat menyimpang dari kondisi normal, kemungkinan ada kerusakan pada komponen motor."
}

# Telegram functions (only if available)
if TELEGRAM_AVAILABLE:
    async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
        if update.effective_user.id != AUTHORIZED_USER_ID:
            await update.message.reply_text("Maaf, Anda tidak diizinkan mengakses bot ini.")
            return
        
        measuring_status['active'] = True
        await update.message.reply_text("✅ Pengukuran real-time DIMULAI.\nServer siap memproses data dari ESP32.\nKirim /cek untuk lihat status motor.")

    async def stop(update: Update, context: ContextTypes.DEFAULT_TYPE):
        if update.effective_user.id != AUTHORIZED_USER_ID:
            await update.message.reply_text("Maaf, Anda tidak diizinkan mengakses bot ini.")
            return
        
        measuring_status['active'] = False
        await update.message.reply_text("✅ Pengukuran real-time DIHENTIKAN.\nServer berhenti memproses data dari ESP32.")

    async def cek(update: Update, context: ContextTypes.DEFAULT_TYPE):
        if update.effective_user.id != AUTHORIZED_USER_ID:
            await update.message.reply_text("Maaf, Anda tidak diizinkan mengakses bot ini.")
            return
        
        status = last_status['severity']
        confidence = last_status['confidence']
        buffer_size = len(realtime_buffer)
        
        message = f"📊 STATUS MOTOR:\n"
        message += f"Kondisi: {status}\n"
        message += f"Confidence: {confidence:.3f}\n"
        message += f"Buffer Size: {buffer_size}\n"
        message += f"Measuring: {'Aktif' if measuring_status['active'] else 'Berhenti'}"
        
        await update.message.reply_text(message)

    async def penjelasan(update: Update, context: ContextTypes.DEFAULT_TYPE):
        if update.effective_user.id != AUTHORIZED_USER_ID:
            await update.message.reply_text("Maaf, Anda tidak diizinkan mengakses bot ini.")
            return
        
        current_severity = last_status['severity']
        if current_severity in PENJELASAN_BY_CONDITION:
            explanation_message = PENJELASAN_BY_CONDITION[current_severity]
        else:
            explanation_message = PENJELASAN_BY_CONDITION['NORMAL']
        
        message = f"📊 PENJELASAN KONDISI {current_severity}:\n\n{explanation_message}"
        await update.message.reply_text(message)

    async def tips(update: Update, context: ContextTypes.DEFAULT_TYPE):
        if update.effective_user.id != AUTHORIZED_USER_ID:
            await update.message.reply_text("Maaf, Anda tidak diizinkan mengakses bot ini.")
            return
        
        current_severity = last_status['severity']
        if current_severity in TIPS_BY_CONDITION:
            tip_message = TIPS_BY_CONDITION[current_severity]
        else:
            tip_message = TIPS_BY_CONDITION['NORMAL']
        
        message = f"🔧 TIPS UNTUK KONDISI {current_severity}:\n\n{tip_message}"
        await update.message.reply_text(message)

    async def grafik(update: Update, context: ContextTypes.DEFAULT_TYPE):
        if update.effective_user.id != AUTHORIZED_USER_ID:
            await update.message.reply_text("Maaf, Anda tidak diizinkan mengakses bot ini.")
            return
        
        riwayat = last_status['riwayat']
        if len(riwayat) < 2:
            await update.message.reply_text("Belum ada cukup data untuk membuat grafik.")
            return
            
        labels = [x[0] for x in riwayat]
        values = [x[1] for x in riwayat]
        
        plt.figure(figsize=(8,4))
        plt.plot(values, marker='o', linewidth=2, markersize=6)
        plt.xticks(range(len(labels)), labels, rotation=45)
        plt.title("Riwayat Anomali Motor", fontsize=14, fontweight='bold')
        plt.xlabel("Waktu")
        plt.ylabel("Confidence")
        plt.grid(True, alpha=0.3)
        plt.tight_layout()
        
        buf = io.BytesIO()
        plt.savefig(buf, format='png', dpi=150, bbox_inches='tight')
        buf.seek(0)
        await update.message.reply_photo(photo=buf, caption="📈 Grafik Riwayat Anomali Motor")
        buf.close()
        plt.close()

    async def status(update: Update, context: ContextTypes.DEFAULT_TYPE):
        if update.effective_user.id != AUTHORIZED_USER_ID:
            await update.message.reply_text("Maaf, Anda tidak diizinkan mengakses bot ini.")
            return
        
        # Check ESP32 connection
        try:
            response = requests.get(f"http://{ESP32_IP}:{ESP32_HTTP_PORT}/ping", timeout=3)
            esp32_status = "Terhubung" if response.status_code == 200 else "Tidak terhubung"
        except:
            esp32_status = "Tidak terhubung"
        
        message = f"🖥️ STATUS SERVER:\n"
        message += f"Server: Aktif ✅\n"
        message += f"Model: Loaded ✅\n"
        message += f"Buffer: {len(realtime_buffer)} samples\n"
        message += f"Measuring: {'Aktif' if measuring_status['active'] else 'Berhenti'}\n"
        message += f"ESP32: {esp32_status}"
        
        await update.message.reply_text(message)

    async def riwayat(update: Update, context: ContextTypes.DEFAULT_TYPE):
        if update.effective_user.id != AUTHORIZED_USER_ID:
            await update.message.reply_text("Maaf, Anda tidak diizinkan mengakses bot ini.")
            return
        
        try:
            # Get minutes from command argument
            minutes = 5  # default 5 menit
            if context.args and context.args[0].isdigit():
                minutes = int(context.args[0])
                if minutes > 60:  # Limit to 60 minutes max
                    minutes = 60
                    await update.message.reply_text("⚠️ Maksimal 60 menit. Menggunakan 60 menit.")
            
            # Request data from Flask server
            url = f"{PUBLIC_URL}/history?minutes={minutes}"
            response = requests.get(url, timeout=5)
            data = response.json()
            
            if 'error' in data:
                await update.message.reply_text(f"❌ Error: {data['error']}")
                return
            
            history_data = data.get('history', [])
            count = data.get('count', 0)
            
            if count == 0:
                await update.message.reply_text(f"📊 Tidak ada data getaran dalam {minutes} menit terakhir.")
                return
            
            # Calculate summary statistics
            if history_data:
                x_values = [d['x'] for d in history_data]
                y_values = [d['y'] for d in history_data]
                z_values = [d['z'] for d in history_data]
                
                # Calculate RMS values
                rms_x = np.sqrt(np.mean(np.array(x_values)**2))
                rms_y = np.sqrt(np.mean(np.array(y_values)**2))
                rms_z = np.sqrt(np.mean(np.array(z_values)**2))
                
                # Calculate ranges
                range_x = max(x_values) - min(x_values)
                range_y = max(y_values) - min(y_values)
                range_z = max(z_values) - min(z_values)
                
                # Determine overall condition based on RMS values
                max_rms = max(rms_x, rms_y, rms_z)
                if max_rms > 15:
                    condition = "🔴 TINGGI"
                elif max_rms > 8:
                    condition = "🟡 SEDANG"
                else:
                    condition = "🟢 RENDAH"
                
                # Create summary text
                summary = f"📊 **RIWAYAT GETARAN ({minutes} MENIT)**\n\n"
                summary += f"📈 **Data Points**: {count}\n"
                summary += f"⚡ **Kondisi Getaran**: {condition}\n\n"
                summary += f"📊 **RMS Values**:\n"
                summary += f"• X-axis: {rms_x:.2f}\n"
                summary += f"• Y-axis: {rms_y:.2f}\n"
                summary += f"• Z-axis: {rms_z:.2f}\n\n"
                summary += f"📏 **Range Values**:\n"
                summary += f"• X-axis: {range_x:.2f}\n"
                summary += f"• Y-axis: {range_y:.2f}\n"
                summary += f"• Z-axis: {range_z:.2f}\n\n"
                summary += f"⏰ **Waktu**: {minutes} menit terakhir"
                
                await update.message.reply_text(summary, parse_mode='Markdown')
                
                # Create and send plot
                await create_and_send_plot(update, history_data, minutes)
                
            else:
                await update.message.reply_text(f"📊 Tidak ada data getaran dalam {minutes} menit terakhir.")
                
        except Exception as e:
            print(f"Error in riwayat command: {e}")
            await update.message.reply_text(f"❌ Error: {str(e)}")

    async def create_and_send_plot(update: Update, history_data, minutes):
        """Create and send vibration plot"""
        try:
            # Prepare data for plotting
            timestamps = [d['timestamp'] for d in history_data]
            x_values = [d['x'] for d in history_data]
            y_values = [d['y'] for d in history_data]
            z_values = [d['z'] for d in history_data]
            
            # Convert timestamps to relative time (seconds from start)
            start_time = min(timestamps)
            relative_times = [(t - start_time) / 1000 for t in timestamps]  # Convert to seconds
            
            # Create subplots
            fig, (ax1, ax2) = plt.subplots(2, 1, figsize=(10, 8))
            
            # Plot 1: Raw vibration data
            ax1.plot(relative_times, x_values, label='X-axis', alpha=0.7, linewidth=1)
            ax1.plot(relative_times, y_values, label='Y-axis', alpha=0.7, linewidth=1)
            ax1.plot(relative_times, z_values, label='Z-axis', alpha=0.7, linewidth=1)
            ax1.set_title(f'Raw Vibration Data ({minutes} menit)', fontsize=12, fontweight='bold')
            ax1.set_xlabel('Waktu (detik)')
            ax1.set_ylabel('Akselerasi (g)')
            ax1.legend()
            ax1.grid(True, alpha=0.3)
            
            # Plot 2: RMS values over time (rolling window)
            window_size = max(1, len(history_data) // 10)  # 10% of data points
            if window_size > 1:
                rms_x_rolling = []
                rms_y_rolling = []
                rms_z_rolling = []
                time_centers = []
                
                for i in range(0, len(history_data) - window_size + 1, max(1, window_size // 5)):
                    window_x = x_values[i:i+window_size]
                    window_y = y_values[i:i+window_size]
                    window_z = z_values[i:i+window_size]
                    
                    rms_x_rolling.append(np.sqrt(np.mean(np.array(window_x)**2)))
                    rms_y_rolling.append(np.sqrt(np.mean(np.array(window_y)**2)))
                    rms_z_rolling.append(np.sqrt(np.mean(np.array(window_z)**2)))
                    time_centers.append(relative_times[i + window_size // 2])
                
                ax2.plot(time_centers, rms_x_rolling, label='RMS X', marker='o', markersize=3)
                ax2.plot(time_centers, rms_y_rolling, label='RMS Y', marker='s', markersize=3)
                ax2.plot(time_centers, rms_z_rolling, label='RMS Z', marker='^', markersize=3)
                ax2.set_title(f'RMS Values Over Time ({minutes} menit)', fontsize=12, fontweight='bold')
                ax2.set_xlabel('Waktu (detik)')
                ax2.set_ylabel('RMS (g)')
                ax2.legend()
                ax2.grid(True, alpha=0.3)
            
            plt.tight_layout()
            
            # Save and send plot
            buf = io.BytesIO()
            plt.savefig(buf, format='png', dpi=150, bbox_inches='tight')
            buf.seek(0)
            
            await update.message.reply_photo(
                photo=buf, 
                caption=f"📈 Grafik Getaran {minutes} Menit Terakhir\nData points: {len(history_data)}"
            )
            
            buf.close()
            plt.close()
            
        except Exception as e:
            print(f"Error creating plot: {e}")
            await update.message.reply_text(f"❌ Error membuat grafik: {str(e)}")

    async def record_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Start recording vibration data"""
        if update.effective_user.id != AUTHORIZED_USER_ID:
            await update.message.reply_text("Maaf, Anda tidak diizinkan mengakses bot ini.")
            return
        
        try:
            # Parse arguments
            duration_minutes = 30  # default 30 menit
            label = "recording"
            
            if context.args:
                if context.args[0].isdigit():
                    duration_minutes = int(context.args[0])
                    if duration_minutes > 120:  # Max 2 hours
                        duration_minutes = 120
                        await update.message.reply_text("⚠️ Maksimal 120 menit. Menggunakan 120 menit.")
                else:
                    label = context.args[0]
                
                if len(context.args) > 1 and context.args[1].isdigit():
                    duration_minutes = int(context.args[1])
                    if duration_minutes > 120:
                        duration_minutes = 120
                        await update.message.reply_text("⚠️ Maksimal 120 menit. Menggunakan 120 menit.")
            
            # Start recording via API
            url = f"{PUBLIC_URL}/record_start"
            data = {
                'duration_minutes': duration_minutes,
                'label': label
            }
            response = requests.post(url, json=data, timeout=5)
            result = response.json()
            
            if result.get('status') == 'RECORDING_STARTED':
                message = f"🎬 **RECORDING STARTED**\n\n"
                message += f"📝 **Label**: {label}\n"
                message += f"⏱️ **Duration**: {duration_minutes} menit\n"
                message += f"📁 **File**: {result.get('filename', 'N/A')}\n\n"
                message += f"📊 Data akan disimpan otomatis ke CSV\n"
                message += f"🔄 Gunakan /record_status untuk cek progress\n"
                message += f"⏹️ Gunakan /record_stop untuk stop recording"
                
                await update.message.reply_text(message)
            else:
                await update.message.reply_text(f"❌ Error: {result.get('error', 'Unknown error')}")
                
        except Exception as e:
            print(f"Error in record_start: {e}")
            await update.message.reply_text(f"❌ Error: {str(e)}")

    async def record_stop(update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Stop recording and show summary"""
        if update.effective_user.id != AUTHORIZED_USER_ID:
            await update.message.reply_text("Maaf, Anda tidak diizinkan mengakses bot ini.")
            return
        
        try:
            # Stop recording via API
            url = f"{PUBLIC_URL}/record_stop"
            response = requests.post(url, timeout=5)
            result = response.json()
            
            if result.get('status') == 'RECORDING_STOPPED':
                duration_seconds = result.get('duration_seconds', 0)
                data_points = result.get('data_points', 0)
                filename = result.get('filename', 'N/A')
                label = result.get('label', 'N/A')
                
                duration_minutes = duration_seconds / 60
                
                message = f"⏹️ **RECORDING STOPPED**\n\n"
                message += f"📝 **Label**: {label}\n"
                message += f"⏱️ **Duration**: {duration_minutes:.1f} menit\n"
                message += f"📊 **Data Points**: {data_points:,}\n"
                message += f"📁 **File**: {filename}\n\n"
                message += f"💾 Data tersimpan di server\n"
                message += f"📥 Gunakan /record_export {label} untuk download"
                
                await update.message.reply_text(message)
            else:
                await update.message.reply_text(f"❌ Error: {result.get('error', 'Unknown error')}")
                
        except Exception as e:
            print(f"Error in record_stop: {e}")
            await update.message.reply_text(f"❌ Error: {str(e)}")

    async def record_status(update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Check recording status"""
        if update.effective_user.id != AUTHORIZED_USER_ID:
            await update.message.reply_text("Maaf, Anda tidak diizinkan mengakses bot ini.")
            return
        
        try:
            # Get recording status via API
            url = f"{PUBLIC_URL}/record_status"
            response = requests.get(url, timeout=5)
            result = response.json()
            
            if result.get('status') == 'RECORDING':
                label = result.get('label', 'N/A')
                duration_minutes = result.get('duration_minutes', 0)
                elapsed_minutes = result.get('elapsed_minutes', 0)
                progress_percent = result.get('progress_percent', 0)
                data_points = result.get('data_points', 0)
                
                # Create progress bar
                progress_bar_length = 20
                filled_length = int(progress_bar_length * progress_percent / 100)
                progress_bar = "█" * filled_length + "░" * (progress_bar_length - filled_length)
                
                message = f"🎬 **RECORDING STATUS**\n\n"
                message += f"📝 **Label**: {label}\n"
                message += f"⏱️ **Progress**: {elapsed_minutes:.1f} / {duration_minutes} menit\n"
                message += f"📊 **Data Points**: {data_points:,}\n\n"
                message += f"📈 **Progress Bar**:\n"
                message += f"`{progress_bar}` {progress_percent:.1f}%\n\n"
                message += f"⏹️ Gunakan /record_stop untuk stop"
                
                await update.message.reply_text(message)
            else:
                await update.message.reply_text("📹 Tidak ada recording yang aktif.\n\nGunakan /record_start untuk mulai recording.")
                
        except Exception as e:
            print(f"Error in record_status: {e}")
            await update.message.reply_text(f"❌ Error: {str(e)}")

    async def record_export(update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Export recording data as CSV"""
        if update.effective_user.id != AUTHORIZED_USER_ID:
            await update.message.reply_text("Maaf, Anda tidak diizinkan mengakses bot ini.")
            return
        
        try:
            if not context.args:
                await update.message.reply_text("❌ Format: /record_export <label>\n\nContoh: /record_export jalan_lurus")
                return
            
            label = context.args[0]
            
            # Export recording via API
            url = f"{PUBLIC_URL}/record_export/{label}"
            response = requests.get(url, timeout=10)
            result = response.json()
            
            if result.get('status') == 'SUCCESS':
                filename = result.get('filename', 'N/A')
                data_points = result.get('data_points', 0)
                csv_data = result.get('data', '')
                
                # Create CSV file and send
                csv_filename = f"vibration_data_{label}.csv"
                
                # Send as document
                csv_bytes = csv_data.encode('utf-8')
                csv_io = io.BytesIO(csv_bytes)
                csv_io.name = csv_filename
                
                message = f"📥 **EXPORT SUCCESS**\n\n"
                message += f"📝 **Label**: {label}\n"
                message += f"📊 **Data Points**: {data_points:,}\n"
                message += f"📁 **File**: {filename}\n\n"
                message += f"💾 File CSV siap download"
                
                await update.message.reply_document(
                    document=csv_io,
                    filename=csv_filename,
                    caption=message
                )
                
                csv_io.close()
            else:
                await update.message.reply_text(f"❌ Error: {result.get('error', 'Unknown error')}")
                
        except Exception as e:
            print(f"Error in record_export: {e}")
            await update.message.reply_text(f"❌ Error: {str(e)}")

    async def error_handler(update: object, context: ContextTypes.DEFAULT_TYPE) -> None:
        """Handle errors in the Telegram bot"""
        error_msg = str(context.error)
        print(f"Telegram bot error: {error_msg}")
        
        if "Conflict" in error_msg or "terminated by other getUpdates" in error_msg:
            print("Bot conflict detected. Stopping Telegram bot gracefully...")
            try:
                await context.application.stop()
                await context.application.shutdown()
            except:
                pass
            print("Telegram bot stopped. Continuing with Flask server only.")
            return
        
        # For other errors, just log them
        print(f"Telegram error (non-critical): {error_msg}")

    def main_telegram():
        """Start Telegram bot with better error handling"""
        try:
            print("Initializing Telegram bot...")
            application = Application.builder().token(TELEGRAM_TOKEN).build()
            
            # Add handlers
            application.add_handler(CommandHandler("start", start))
            application.add_handler(CommandHandler("stop", stop))
            application.add_handler(CommandHandler("cek", cek))
            application.add_handler(CommandHandler("penjelasan", penjelasan))
            application.add_handler(CommandHandler("tips", tips))
            application.add_handler(CommandHandler("grafik", grafik))
            application.add_handler(CommandHandler("status", status))
            application.add_handler(CommandHandler("riwayat", riwayat))
            application.add_handler(CommandHandler("record_start", record_start))
            application.add_handler(CommandHandler("record_stop", record_stop))
            application.add_handler(CommandHandler("record_status", record_status))
            application.add_handler(CommandHandler("record_export", record_export))
            application.add_error_handler(error_handler)
            
            print("Telegram bot handlers registered!")
            print("Starting Telegram bot polling...")
            
            # Start polling with better conflict resolution
            application.run_polling(
                allowed_updates=Update.ALL_TYPES, 
                drop_pending_updates=True,
                close_loop=False,
                timeout=30,
                read_timeout=30
            )
            
        except Exception as e:
            print(f"Telegram bot failed to start: {e}")
            print("Continuing with Flask server only...")
            return False
        
        return True

def load_trained_models():
    """Load trained models from files"""
    global iso_forest_model, pca_model, scaler_model, is_model_loaded
    try:
        print("Training new models...")
        train_models_from_data()
        is_model_loaded = True
        print("Models loaded successfully!")
    except Exception as e:
        print(f"Error loading models: {e}")
        print("Will train new models from data...")
        train_models_from_data()
        is_model_loaded = True

def train_models_from_data():
    """Train models from existing dataset"""
    global iso_forest_model, pca_model, scaler_model
    try:
        # Load training data
        df_normal_ringan = pd.read_excel("Dataset PCA (Normal 80 + Ringan 20).xlsx")
        df_normal_berat = pd.read_excel("Dataset PCA (Normal 80 + Berat 20).xlsx")
        
        # Extract ONLY normal data from both datasets
        normal_data = pd.concat([
            df_normal_ringan[df_normal_ringan['Source'] == 'Suprax(Normal)'],
            df_normal_berat[df_normal_berat['Source'] == 'Suprax(Normal)']
        ], ignore_index=True)
        
        # Prepare raw features from normal data only (center to remove global offsets)
        raw = normal_data[["X ", "Y ", "Z "]].dropna().values
        # Global centering to reduce gravity/offset bias in PCA space
        raw_centered = raw - raw.mean(axis=0, keepdims=True)
        
        # Fit scaler and PCA on centered normal data only
        scaler_model = StandardScaler()
        X_scaled = scaler_model.fit_transform(raw_centered)
        pca_model = PCA(n_components=2, random_state=42)
        pca_model.fit(X_scaled)
        
        # Create training features for Isolation Forest in the same PC space
        pca_features_train = pca_model.transform(X_scaled)
        
        # Train Isolation Forest ONLY on normal data with higher sensitivity
        iso_forest_model = IsolationForest(
            contamination=0.15,  # Increased from 0.02 to 0.15 for better sensitivity
            random_state=42,
            n_estimators=200,
            bootstrap=False
        )
        iso_forest_model.fit(pca_features_train)
        
        print("Models trained successfully (IF trained on NORMAL data only with higher sensitivity)!")
    except Exception as e:
        print(f"Error training models: {e}")
        # Fallback: create simple models
        iso_forest_model = IsolationForest(contamination=0.15, random_state=42)
        pca_model = PCA(n_components=2, random_state=42)
        scaler_model = StandardScaler()

def remove_gravity_dc(data, cutoff=0.1, fs=10):
    """Remove DC component (gravity) using high-pass filter"""
    if len(data) < 4:  # Need minimum samples for filter
        return data
    try:
        b, a = signal.butter(4, cutoff/(fs/2), btype='high')
        return signal.filtfilt(b, a, data)
    except:
        # Fallback: simple detrend
        return data - np.mean(data)

def extract_features_from_buffer(data_buffer):
    """Extract features from vibration data buffer with improved sensitivity"""
    if len(data_buffer) < 30:  # Increased minimum buffer size
        return None
    
    # Convert to DataFrame
    df = pd.DataFrame(data_buffer, columns=['x', 'y', 'z'])
    
    # Apply high-pass filter to remove gravity DC component
    x_filtered = remove_gravity_dc(df['x'].values)
    y_filtered = remove_gravity_dc(df['y'].values)
    z_filtered = remove_gravity_dc(df['z'].values)
    
    # Calculate enhanced statistical features
    features = {
        # Basic statistical features
        'mean_x': np.mean(x_filtered),
        'mean_y': np.mean(y_filtered),
        'mean_z': np.mean(z_filtered),
        'std_x': np.std(x_filtered),
        'std_y': np.std(y_filtered),
        'std_z': np.std(z_filtered),
        
        # RMS features (more sensitive to vibration)
        'rms_x': np.sqrt(np.mean(x_filtered**2)),
        'rms_y': np.sqrt(np.mean(y_filtered**2)),
        'rms_z': np.sqrt(np.mean(z_filtered**2)),
        
        # Peak-to-peak features (detect extreme vibrations)
        'peak_to_peak_x': np.max(x_filtered) - np.min(x_filtered),
        'peak_to_peak_y': np.max(y_filtered) - np.min(y_filtered),
        'peak_to_peak_z': np.max(z_filtered) - np.min(z_filtered),
        
        # Higher-order statistics (detect unusual patterns)
        'kurtosis_x': scipy.stats.kurtosis(x_filtered),
        'kurtosis_y': scipy.stats.kurtosis(y_filtered),
        'kurtosis_z': scipy.stats.kurtosis(z_filtered),
        'skewness_x': scipy.stats.skew(x_filtered),
        'skewness_y': scipy.stats.skew(y_filtered),
        'skewness_z': scipy.stats.skew(z_filtered),
        
        # Range features
        'max_x': np.max(x_filtered),
        'max_y': np.max(y_filtered),
        'max_z': np.max(z_filtered),
        'min_x': np.min(x_filtered),
        'min_y': np.min(y_filtered),
        'min_z': np.min(z_filtered)
    }
    
    # Apply PCA transformation for compatibility (use filtered means to align with features)
    if scaler_model and pca_model:
        # Build one representative vector from filtered signals
        pca_input = np.array([[np.mean(x_filtered), np.mean(y_filtered), np.mean(z_filtered)]])
        scaled_input = scaler_model.transform(pca_input)
        pca_vec = pca_model.transform(scaled_input)
        features['PC1'] = float(pca_vec[0, 0])
        features['PC2'] = float(pca_vec[0, 1])
    
    return features

def classify_vibration(features):
    """Classify vibration severity (NORMAL/RINGAN/BERAT) and confidence.
    - Detection by IsolationForest (trained on NORMAL only)
    - Severity by distance in PCA space
    - Confidence by IF score + distance to thresholds
    """
    if not is_model_loaded or iso_forest_model is None:
        return "UNKNOWN", 0.0
    try:
        # Deteksi kondisi sangat tenang (idle/stasioner) - lebih toleran
        total_rms = np.sqrt(features['rms_x']**2 + features['rms_y']**2 + features['rms_z']**2)
        stationary_threshold = 0.30  # Increased from 0.15 to be more tolerant
        if total_rms < stationary_threshold:
            return "NORMAL", 0.95

        # Vektor fitur untuk IF (PC1/PC2)
        feature_vector = np.array([features['PC1'], features['PC2']]).reshape(1, -1)
        if_score = iso_forest_model.decision_function(feature_vector)[0]
        distance = np.sqrt(features['PC1']**2 + features['PC2']**2)

        # Ambang jarak (lebih konservatif untuk dinamis)
        ringan_threshold = 0.60  
        berat_threshold = 0.80   

        # Keputusan severity dengan zona transisi yang lebih luas dan toleran
        if if_score > -0.20 and distance < ringan_threshold:  # More tolerant IF score
            severity = "NORMAL"
        elif distance >= berat_threshold:
            severity = "BERAT"
        elif distance >= ringan_threshold:
            severity = "RINGAN"
        else:
            # Zona transisi: gunakan kombinasi IF score dan distance
            if if_score > -0.30 and distance < (ringan_threshold + berat_threshold) / 2:
                severity = "NORMAL"
            else:
                severity = "RINGAN"

        # Confidence calculation
        if severity == "NORMAL":
            # Semakin dekat pusat dan IF score tinggi → makin yakin
            conf_from_dist = 1.0 - min(1.0, distance / max(1e-6, ringan_threshold))
            conf_from_if = min(1.0, 0.8 + max(0.0, if_score))
            confidence = max(0.7, 0.5 * conf_from_dist + 0.5 * conf_from_if)
        elif severity == "RINGAN":
            # Jarak relatif antara ringan→berat
            span = max(1e-6, berat_threshold - ringan_threshold)
            rel = min(1.0, max(0.0, (distance - ringan_threshold) / span))
            confidence = max(0.6, 0.6 + 0.3 * rel)
        else:  # BERAT
            # Seberapa jauh melewati berat_threshold
            rel_heavy = min(1.0, (distance - berat_threshold) / (berat_threshold))
            confidence = max(0.7, 0.75 + 0.2 * rel_heavy)

        confidence = float(min(0.99, max(0.5, confidence)))
        return severity, confidence
    except Exception as e:
        print(f"Error in classification: {e}")
        return "ERROR", 0.0

@app.route('/record_start', methods=['POST'])
def start_recording():
    """Start recording vibration data"""
    global recording_status, recording_data
    
    try:
        data = request.get_json()
        duration_minutes = data.get('duration_minutes', 30)
        label = data.get('label', 'recording')
        
        with recording_lock:
            if recording_status['active']:
                return jsonify({
                    'error': 'Recording already active',
                    'status': 'ERROR'
                }), 400
            
            # Initialize recording
            recording_status['active'] = True
            recording_status['start_time'] = int(time.time() * 1000)
            recording_status['duration_minutes'] = duration_minutes
            recording_status['label'] = label
            recording_status['data_points'] = 0
            
            # Create filename
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            filename = f"recording_{label}_{timestamp}.csv"
            recording_status['file_path'] = filename
            
            # Clear previous data
            recording_data.clear()
            
            # Create CSV header
            csv_header = "timestamp,x,y,z,label,condition,total_rms,distance\n"
            with open(filename, 'w') as f:
                f.write(csv_header)
        
        return jsonify({
            'status': 'RECORDING_STARTED',
            'duration_minutes': duration_minutes,
            'label': label,
            'filename': filename
        })
        
    except Exception as e:
        print(f"Error starting recording: {e}")
        return jsonify({'error': str(e)}), 500

@app.route('/record_stop', methods=['POST'])
def stop_recording():
    """Stop recording and save data"""
    global recording_status
    
    try:
        with recording_lock:
            if not recording_status['active']:
                return jsonify({
                    'error': 'No active recording',
                    'status': 'ERROR'
                }), 400
            
            # Stop recording
            recording_status['active'] = False
            end_time = int(time.time() * 1000)
            
            # Calculate statistics
            duration_seconds = (end_time - recording_status['start_time']) / 1000
            data_points = recording_status['data_points']
            
            result = {
                'status': 'RECORDING_STOPPED',
                'duration_seconds': duration_seconds,
                'data_points': data_points,
                'filename': recording_status['file_path'],
                'label': recording_status['label']
            }
            
            # Reset recording status
            recording_status = {
                'active': False,
                'start_time': None,
                'duration_minutes': 0,
                'label': '',
                'data_points': 0,
                'file_path': ''
            }
        
        return jsonify(result)
        
    except Exception as e:
        print(f"Error stopping recording: {e}")
        return jsonify({'error': str(e)}), 500

@app.route('/record_status', methods=['GET'])
def get_recording_status():
    """Get current recording status"""
    try:
        with recording_lock:
            if not recording_status['active']:
                return jsonify({
                    'status': 'NOT_RECORDING',
                    'message': 'No active recording'
                })
            
            # Calculate progress
            current_time = int(time.time() * 1000)
            elapsed_ms = current_time - recording_status['start_time']
            total_ms = recording_status['duration_minutes'] * 60 * 1000
            progress_percent = min(100, (elapsed_ms / total_ms) * 100)
            
            elapsed_minutes = elapsed_ms / (60 * 1000)
            
            return jsonify({
                'status': 'RECORDING',
                'label': recording_status['label'],
                'duration_minutes': recording_status['duration_minutes'],
                'elapsed_minutes': round(elapsed_minutes, 1),
                'progress_percent': round(progress_percent, 1),
                'data_points': recording_status['data_points'],
                'filename': recording_status['file_path']
            })
            
    except Exception as e:
        print(f"Error getting recording status: {e}")
        return jsonify({'error': str(e)}), 500

@app.route('/record_export/<label>', methods=['GET'])
def export_recording(label):
    """Export recording data as CSV"""
    try:
        # Find the most recent recording file for this label
        import glob
        import os
        
        pattern = f"recording_{label}_*.csv"
        files = glob.glob(pattern)
        
        if not files:
            return jsonify({
                'error': f'No recording found for label: {label}',
                'status': 'ERROR'
            }), 404
        
        # Get the most recent file
        latest_file = max(files, key=os.path.getctime)
        
        # Read file and return as CSV
        with open(latest_file, 'r') as f:
            csv_content = f.read()
        
        return jsonify({
            'status': 'SUCCESS',
            'filename': latest_file,
            'data': csv_content,
            'data_points': len(csv_content.split('\n')) - 2  # Exclude header and empty line
        })
        
    except Exception as e:
        print(f"Error exporting recording: {e}")
        return jsonify({'error': str(e)}), 500

@app.route('/predict', methods=['POST'])
def predict_vibration():
    """Endpoint untuk prediksi real-time"""
    if not measuring_status['active']:
        return jsonify({
            'status': 'STOPPED',
            'message': 'Pengukuran sedang dihentikan oleh user.'
        }), 200
    try:
        # Get data from ESP32
        data = request.get_json()
        if not data or 'x' not in data or 'y' not in data or 'z' not in data:
            return jsonify({
                'error': 'Invalid data format',
                'status': 'ERROR'
            }), 400
        
        # Extract vibration data
        x_data = data['x']
        y_data = data['y']
        z_data = data['z']
        timestamp = data.get('timestamp', int(time.time() * 1000))
        
        # Debug logging
        print(f"Received data: {len(x_data)} samples, timestamp: {timestamp}")
        print(f"X range: {min(x_data):.3f} to {max(x_data):.3f}")
        print(f"Y range: {min(y_data):.3f} to {max(y_data):.3f}")
        print(f"Z range: {min(z_data):.3f} to {max(z_data):.3f}")
        
        # Add to buffer
        with buffer_lock:
            for i in range(len(x_data)):
                realtime_buffer.append({
                    'x': float(x_data[i]),
                    'y': float(y_data[i]),
                    'z': float(z_data[i]),
                    'timestamp': timestamp
                })
            # Keep only last 100 samples
            if len(realtime_buffer) > 100:
                realtime_buffer[:] = realtime_buffer[-100:]
        
        # Save to recording time window state (without writing yet); we'll write after classification
        with recording_lock:
            if recording_status['active']:
                # Check if recording time is up
                current_time = int(time.time() * 1000)
                elapsed_ms = current_time - recording_status['start_time']
                total_ms = recording_status['duration_minutes'] * 60 * 1000
                if elapsed_ms >= total_ms:
                    recording_status['active'] = False
                    print(f"Recording auto-stopped after {recording_status['duration_minutes']} minutes")
        
        # Extract features
        features = extract_features_from_buffer(realtime_buffer)
        if features is None:
            return jsonify({
                'error': 'Insufficient data for analysis',
                'status': 'WAITING'
            }), 200
        
        # Validate features before classification
        if not all(key in features for key in ['rms_x', 'rms_y', 'rms_z', 'PC1', 'PC2']):
            print(f"Invalid features: {features}")
            return jsonify({
                'error': 'Invalid features extracted',
                'status': 'ERROR'
            }), 400
        
        # Classify vibration
        try:
            severity, confidence = classify_vibration(features)
        except Exception as e:
            print(f"Classification error: {e}")
            return jsonify({
                'error': f'Classification failed: {str(e)}',
                'status': 'ERROR'
            }), 500
        
        # Write recording samples with classified severity, total_rms, and distance
        with recording_lock:
            if recording_status['active']:
                try:
                    # Calculate total_rms and distance for this batch
                    total_rms = np.sqrt(features['rms_x']**2 + features['rms_y']**2 + features['rms_z']**2)
                    distance = np.sqrt(features['PC1']**2 + features['PC2']**2)
                    
                    with open(recording_status['file_path'], 'a') as f:
                        for i in range(len(x_data)):
                            csv_line = f"{timestamp},{x_data[i]},{y_data[i]},{z_data[i]},{recording_status['label']},{severity.lower()},{total_rms:.4f},{distance:.4f}\n"
                            f.write(csv_line)
                            recording_status['data_points'] += 1
                except Exception as e:
                    print(f"Error writing recording CSV: {e}")
        
        # Update last_status dengan penjelasan dan tips yang sesuai
        last_status['severity'] = severity
        last_status['confidence'] = confidence
        
        # Update penjelasan berdasarkan kondisi
        if severity in PENJELASAN_BY_CONDITION:
            last_status['penjelasan'] = PENJELASAN_BY_CONDITION[severity]
        else:
            last_status['penjelasan'] = PENJELASAN_BY_CONDITION['NORMAL']
        
        # Update tips berdasarkan kondisi
        if severity in TIPS_BY_CONDITION:
            last_status['tips'] = TIPS_BY_CONDITION[severity]
        else:
            last_status['tips'] = TIPS_BY_CONDITION['NORMAL']
        
        last_status['riwayat'].append((severity, confidence))
        if len(last_status['riwayat']) > 10: # Keep last 10 records
            last_status['riwayat'] = last_status['riwayat'][-10:]
        
        # Calculate distance from normal for monitoring
        distance_from_normal = np.sqrt(features['PC1']**2 + features['PC2']**2)
        total_rms = np.sqrt(features['rms_x']**2 + features['rms_y']**2 + features['rms_z']**2)
        
        # Prepare response
        response = {
            'timestamp': timestamp,
            'severity': severity,
            'confidence': round(confidence, 3),
            'features': {
                'rms_x': round(features['rms_x'], 3),
                'rms_y': round(features['rms_y'], 3),
                'rms_z': round(features['rms_z'], 3),
                'total_rms': round(total_rms, 4),
                'PC1': round(features['PC1'], 3),
                'PC2': round(features['PC2'], 3),
                'distance_from_normal': round(distance_from_normal, 4)
            },
            'status': 'SUCCESS'
        }
        
        # Add recording status to response
        with recording_lock:
            if recording_status['active']:
                response['recording'] = {
                    'active': True,
                    'label': recording_status['label'],
                    'data_points': recording_status['data_points'],
                    'duration_minutes': recording_status['duration_minutes']
                }
        
        print(f"Prediction: {severity} (confidence: {confidence:.3f}, total_rms: {total_rms:.4f}, distance: {distance_from_normal:.4f})")
        return jsonify(response)
        
    except Exception as e:
        print(f"Error in prediction endpoint: {e}")
        return jsonify({
            'error': str(e),
            'status': 'ERROR'
        }), 500

@app.route('/history', methods=['GET'])
def get_history():
    """Get vibration history within specified minutes"""
    try:
        minutes = int(request.args.get('minutes', 5))
        now = int(time.time() * 1000)
        window = minutes * 60 * 1000  # Convert minutes to milliseconds
        
        with buffer_lock:
            filtered_data = [
                d for d in realtime_buffer
                if now - d['timestamp'] <= window
            ]
        
        return jsonify({
            'history': filtered_data,
            'count': len(filtered_data),
            'minutes': minutes,
            'window_start': now - window
        })
    except Exception as e:
        print(f"Error in history endpoint: {e}")
        return jsonify({'error': str(e)}), 500

@app.route('/status', methods=['GET'])
def get_status():
    """Check server status"""
    return jsonify({
        'status': 'RUNNING',
        'model_loaded': is_model_loaded,
        'buffer_size': len(realtime_buffer),
        'timestamp': datetime.now().isoformat(),
        'measuring_status': measuring_status['active'],
        'telegram_available': TELEGRAM_AVAILABLE
    })

@app.route('/clear_buffer', methods=['POST'])
def clear_buffer():
    """Clear the data buffer"""
    global realtime_buffer
    with buffer_lock:
        realtime_buffer.clear()
    return jsonify({'status': 'Buffer cleared'})

if __name__ == '__main__':
    # Load models on startup
    load_trained_models()
    
    # Jalankan Flask di thread terpisah
    def run_flask():
        # Get port from environment variable (Railway) or use default
        port = int(os.environ.get('PORT', 5000))
        print(f"Starting Flask server on port {port}...")
        print(f"Server will be available at: http://localhost:{port}")
        print(f"Prediction endpoint: http://localhost:{port}/predict")
        app.run(host='0.0.0.0', port=port, debug=False)
    
    flask_thread = threading.Thread(target=run_flask, daemon=True)
    flask_thread.start()
    
    # Wait a moment for Flask to start
    time.sleep(3)
    
    # Jalankan Telegram bot jika tersedia
    if TELEGRAM_AVAILABLE:
        telegram_success = False
        try:
            print("Starting Telegram bot...")
            # Add longer delay to avoid conflict
            time.sleep(10)
            telegram_success = main_telegram()
        except KeyboardInterrupt:
            print("\nShutting down server...")
        except Exception as e:
            print(f"Telegram bot error: {e}")
            print("Continuing with Flask server only...")
        
        # Keep Flask running
        if not telegram_success:
            print("Telegram bot failed to start. Continuing with Flask server only...")
        
        port = int(os.environ.get('PORT', 5000))
        print(f"Flask server is still running at http://localhost:{port}")
        print("Press CTRL+C to quit")
        try:
            while True:
                time.sleep(1)
        except KeyboardInterrupt:
            print("\nShutting down server...")
    else:
        print("Running Flask server only (no Telegram bot)")
        port = int(os.environ.get('PORT', 5000))
        print(f"Flask server is running at http://localhost:{port}")
        print("Press CTRL+C to quit")
        
        try:
            while True:
                time.sleep(1)
        except KeyboardInterrupt:
            print("\nShutting down server...") 