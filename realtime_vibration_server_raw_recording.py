from flask import Flask, request, jsonify
from flask_cors import CORS
import pandas as pd
import numpy as np
import json
from datetime import datetime
import threading
import time
import os
import sys
import traceback
import re

try:
    from dotenv import load_dotenv
    load_dotenv()
except Exception:
    print("python-dotenv not available; skipping .env loading.")

# Optional Telegram imports
try:
    from telegram import Update
    from telegram.ext import Application, CommandHandler, ContextTypes
    import requests
    import io
    TELEGRAM_AVAILABLE = True
except ImportError:
    TELEGRAM_AVAILABLE = False
    print("Telegram libraries not available. Running without Telegram bot.")

app = Flask(__name__)
CORS(app)  # Enable CORS for all routes

# Global variables untuk recording
recording_status = {
    'active': False,
    'start_time': None,
    'duration_minutes': 0,
    'label': '',
    'data_points': 0,
    'file_path': '',
    'road_type': '',
    'motor_condition': '',
    'gear_or_test': '',
    'battery_level': 0  
}

recording_data = []
recording_lock = threading.Lock()

# Telegram configuration (only if available)
if TELEGRAM_AVAILABLE:
    # Prefer RAW_* envs to avoid conflicts with realtime service. Fallback to generic names.
    RAW_TELEGRAM_TOKEN = (os.getenv("RAW_TELEGRAM_TOKEN") or os.getenv("TELEGRAM_TOKEN") or "").strip()
    RAW_AUTHORIZED_USER_ID = (os.getenv("RAW_AUTHORIZED_USER_ID") or os.getenv("AUTHORIZED_USER_ID") or "").strip()
    RAW_PUBLIC_URL = (os.getenv("RAW_PUBLIC_URL") or os.getenv("PUBLIC_URL") or "").strip().rstrip('/')
    RAW_ESP32_IP = (os.getenv("RAW_ESP32_IP") or os.getenv("ESP32_IP") or "").strip()
    RAW_ESP32_HTTP_PORT = (os.getenv("RAW_ESP32_HTTP_PORT") or os.getenv("ESP32_HTTP_PORT") or "").strip()

    # Bind to local variable names used throughout the file
    TELEGRAM_TOKEN = RAW_TELEGRAM_TOKEN
    AUTHORIZED_USER_ID_RAW = RAW_AUTHORIZED_USER_ID
    PUBLIC_URL = RAW_PUBLIC_URL
    ESP32_IP = RAW_ESP32_IP
    ESP32_HTTP_PORT_RAW = RAW_ESP32_HTTP_PORT

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

    # Allow disabling telegram explicitly via RAW_DISABLE_TELEGRAM or DISABLE_TELEGRAM
    disable_telegram = os.getenv("RAW_DISABLE_TELEGRAM") or os.getenv("DISABLE_TELEGRAM")
    if disable_telegram and disable_telegram.strip().lower() in ("1", "true", "yes"): 
        TELEGRAM_AVAILABLE = False
    if missing_envs and TELEGRAM_AVAILABLE:
        print(f"Missing/invalid Telegram env vars: {', '.join(missing_envs)}. Telegram bot will be disabled.")
        TELEGRAM_AVAILABLE = False

# Telegram functions (only if available)
if TELEGRAM_AVAILABLE:
    def get_base_url():
        """Return PUBLIC_URL cleaned from whitespace and trailing slash."""
        if not PUBLIC_URL:
            return None
        return PUBLIC_URL.strip().rstrip('/')

    async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
        if update.effective_user.id != AUTHORIZED_USER_ID:
            await update.message.reply_text("Maaf, Anda tidak diizinkan mengakses bot ini.")
            return
            
      # --- TAMBAHKAN LOGIKA BATERAI DI SINI ---
        lvl = recording_status.get('battery_level', 0)
        emoji = "🪫" if lvl < 20 else "🔋"
      # ---------------------------------------   
        
        await update.message.reply_text("✅ **RAW DATA RECORDING SERVER**\n\n"
                                      f"{emoji} **Status Baterai Alat**: {lvl:.1f}%\n"  
                                      "Server siap untuk recording data raw dari ESP32.\n"
                                      "Gunakan /record_start untuk mulai recording.\n\n"
                                      "**Format command:**\n"
                                      "`/record_start <durasi_menit> <label>`\n\n"
                                      "**Format label:**\n"
                                      "`<road_type>_<motor_condition>_[gigi|tes]`\n\n"
                                      "**Contoh dengan gigi:**\n"
                                      "• `/record_start 30 jalan_mulus_normal_gigi1`\n"
                                      "• `/record_start 45 jalan_berbatu_rusak_ringan_gigi2`\n"
                                      "• `/record_start 60 jalan_menanjak_rusak_berat_gigi4`\n"
                                      "• `/record_start 30 jalan_menurun_normal_gigi1`\n\n"
                                      "**Contoh dengan test:**\n"
                                      "• `/record_start 30 jalan_mulus_tes1`\n"
                                      "• `/record_start 45 jalan_berbatu_tes2`\n"
                                      "• `/record_start 30 jalan_menurun_tes1`\n\n"
                                      "**Contoh tanpa gigi/test:**\n"
                                      "• `/record_start 30 jalan_mulus_normal`\n"
                                      "• `/record_start 30 jalan_menurun_normal`")

    async def record_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Start recording raw vibration data"""
        if update.effective_user.id != AUTHORIZED_USER_ID:
            await update.message.reply_text("Maaf, Anda tidak diizinkan mengakses bot ini.")
            return
        
        try:
            # Parse arguments
            if not context.args or len(context.args) < 2:
                await update.message.reply_text("❌ **Format salah!**\n\n"
                                              "**Format:** `/record_start <durasi_menit> <label>`\n\n"
                                              "**Format label:**\n"
                                              "`<road_type>_<motor_condition>_[gigi|tes]`\n\n"
                                              "**Contoh dengan gigi:**\n"
                                              "• `/record_start 30 jalan_mulus_normal_gigi1`\n"
                                              "• `/record_start 45 jalan_berbatu_rusak_ringan_gigi2`\n\n"
                                              "**Contoh dengan test:**\n"
                                              "• `/record_start 30 jalan_mulus_tes1`\n"
                                              "• `/record_start 45 jalan_berbatu_tes2`\n\n"
                                              "**Road types:** jalan_mulus, jalan_berbatu, jalan_menanjak, jalan_menurun\n"
                                              "**Motor conditions:** normal, rusak_ringan, rusak_berat\n"
                                              "**Gear:** gigi1, gigi2, gigi3, gigi4\n"
                                              "**Test:** tes1, tes2, tes3, ... (fleksibel)")
                return
            
            duration_minutes = int(context.args[0])
            if duration_minutes > 180:  # Max 3 hours
                duration_minutes = 180
                await update.message.reply_text("⚠️ Maksimal 180 menit. Menggunakan 180 menit.")
            
            label_input = context.args[1]
            label_lower = label_input.lower().strip()
            
            # Secara internal kita pakai nama standar 'jalan_mulus' (bukan 'jalan_lurus')
            # tetapi parser tetap menerima input lama 'jalan_lurus' dan memetakan ke 'jalan_mulus'
            valid_roads = ['jalan_mulus', 'jalan_berbatu', 'jalan_menanjak', 'jalan_menurun']
            valid_conditions = ['normal', 'rusak_ringan', 'rusak_berat']
            
            road_type = None
            motor_condition = None
            gear_or_test = ''
            
            # Split label menjadi parts
            label_parts = label_lower.split('_')
            
            # 1. Identifikasi road_type (harus di awal)
            for road in valid_roads:
                if label_lower.startswith(road):
                    road_type = road
                    # Hapus road_type dari label_parts
                    road_parts = road.split('_')
                    label_parts = label_parts[len(road_parts):]
                    break
            
            # Fallback: coba cari road_type di parts
            if not road_type and len(label_parts) >= 2:
                possible_road = f"{label_parts[0]}_{label_parts[1]}"
                if possible_road in valid_roads:
                    road_type = possible_road
                    label_parts = label_parts[2:]
            
            # Validasi road_type
            if road_type:
                # Normalisasi road_type
                if 'lurus' in road_type.lower() or 'mulus' in road_type.lower():
                    # Input lama 'jalan_lurus_*' dan baru 'jalan_mulus_*' sama‑sama dianggap 'jalan_mulus'
                    road_type = 'jalan_mulus'
                elif 'berbatu' in road_type.lower():
                    road_type = 'jalan_berbatu'
                elif 'menanjak' in road_type.lower():
                    road_type = 'jalan_menanjak'
                elif 'menurun' in road_type.lower():
                    road_type = 'jalan_menurun'
                elif road_type not in valid_roads:
                    # Coba match partial
                    for valid_road in valid_roads:
                        if valid_road.lower() in road_type.lower() or road_type.lower() in valid_road.lower():
                            road_type = valid_road
                            break
                    if road_type not in valid_roads:
                        await update.message.reply_text(f"❌ **Road type tidak valid!**\n\n"
                                                      f"Pilih dari: {', '.join(valid_roads)}\n\n"
                                                      f"Input yang diterima: `{label_input}`")
                        return
            else:
                await update.message.reply_text(f"❌ **Road type tidak ditemukan!**\n\n"
                                              f"Format: `/record_start <durasi> <label>`\n\n"
                                              f"Label harus dimulai dengan: {', '.join(valid_roads)}\n"
                                              f"Contoh: `/record_start 30 jalan_mulus_normal_gigi1`")
                return
            
            # 2. Identifikasi gear_or_test di akhir (bisa gigi1-4 atau tesN)
            if label_parts:
                last_part = label_parts[-1].lower()
                
                # Check untuk gigi (gigi1, gigi2, gigi3, gigi4)
                if re.match(r'^gigi[1-4]$', last_part):
                    gear_or_test = last_part  # gigi1, gigi2, gigi3, atau gigi4
                    label_parts = label_parts[:-1]  # Hapus dari parts
                # Check untuk tes (tes1, tes2, tes3, dll - fleksibel)
                elif re.match(r'^tes\d+$', last_part):
                    gear_or_test = last_part  # tes1, tes2, tes3, dll
                    label_parts = label_parts[:-1]  # Hapus dari parts
            
            # 3. Identifikasi motor_condition dari sisa parts
            if label_parts:
                remaining = '_'.join(label_parts)
                motor_condition_lower = remaining.lower()
                
                # Exact match
                for valid_cond in valid_conditions:
                    if valid_cond.lower() == motor_condition_lower:
                        motor_condition = valid_cond
                        break
                
                # Partial match jika belum ketemu
                if not motor_condition:
                    if 'normal' in motor_condition_lower or 'tes' in motor_condition_lower:
                        motor_condition = 'normal'
                    elif 'ringan' in motor_condition_lower:
                        motor_condition = 'rusak_ringan'
                    elif 'berat' in motor_condition_lower:
                        motor_condition = 'rusak_berat'
                    else:
                        motor_condition = 'normal'
                        await update.message.reply_text(f"⚠️ **Motor condition tidak jelas, menggunakan 'normal'**\n\n"
                                                      f"Input: `{remaining}`\n"
                                                      f"Valid conditions: {', '.join(valid_conditions)}")
            else:
                # Default jika tidak ada motor_condition
                motor_condition = 'normal'
            
            base_url = get_base_url()
            if not base_url:
                await update.message.reply_text("❌ **Error: PUBLIC_URL tidak terkonfigurasi!**\n\n"
                                              "Pastikan environment variable RAW_PUBLIC_URL atau PUBLIC_URL sudah di-set di Railway.")
                return
            
            # Buat label lengkap
            if gear_or_test:
                full_label = f"{road_type}_{motor_condition}_{gear_or_test}"
            else:
                full_label = f"{road_type}_{motor_condition}"
            
            url = f"{base_url}/record_start"
            data = {
                'duration_minutes': duration_minutes,
                'label': full_label,
                'road_type': road_type,
                'motor_condition': motor_condition,
                'gear_or_test': gear_or_test
            }
            
            try:
                response = requests.post(url, json=data, timeout=10)
                response.raise_for_status()
                result = response.json()
                
                if result.get('status') == 'RECORDING_STARTED':
                    message = f"🎬 **RAW DATA RECORDING STARTED**\n\n"
                    message += f"📝 **Label**: {full_label}\n"
                    message += f"🛣️ **Road Type**: {road_type}\n"
                    message += f"🏍️ **Motor Condition**: {motor_condition}\n"
                    if gear_or_test:
                        if gear_or_test.startswith('gigi'):
                            message += f"⚙️ **Gear**: {gear_or_test}\n"
                        else:
                            message += f"🧪 **Test**: {gear_or_test}\n"
                    message += f"⏱️ **Duration**: {duration_minutes} menit\n"
                    message += f"📁 **File**: {result.get('filename', 'N/A')}\n\n"
                    message += f"📊 Data RAW akan disimpan otomatis ke CSV\n"
                    message += f"🔄 Gunakan /record_status untuk cek progress\n"
                    message += f"⏹️ Gunakan /record_stop untuk stop recording\n\n"
                    message += f"⚠️ **Pastikan ESP32 terhubung dan mengirim data!**"
                    
                    await update.message.reply_text(message)
                else:
                    error_msg = result.get('error', 'Unknown error')
                    await update.message.reply_text(f"❌ **Error dari server:** {error_msg}\n\n"
                                                  f"URL: `{url}`")
            except requests.exceptions.RequestException as e:
                error_detail = str(e)
                if "Failed to resolve" in error_detail:
                    error_detail = f"Gagal resolve hostname. Cek PUBLIC_URL: `{base_url}`"
                elif "Max retries exceeded" in error_detail:
                    error_detail = f"Tidak bisa connect ke server. Cek URL: `{base_url}`"
                
                print(f"Request error in record_start: {e}")
                await update.message.reply_text(f"❌ **Error koneksi ke server:**\n\n"
                                              f"{error_detail}\n\n"
                                              f"URL yang digunakan: `{url}`\n\n"
                                              f"Pastikan:\n"
                                              f"1. Server RAW recording sudah running\n"
                                              f"2. PUBLIC_URL benar di environment variables\n"
                                              f"3. Tidak ada spasi di akhir URL")
        except ValueError:
            await update.message.reply_text("❌ **Durasi harus berupa angka!**\n\n"
                                          "Contoh: `/record_start 30 jalan_mulus_normal`")
        except Exception as e:
            print(f"Error in record_start: {e}")
            import traceback
            traceback.print_exc()
            await update.message.reply_text(f"❌ **Error:** {str(e)}\n\n"
                                          f"Tipe error: {type(e).__name__}")

    async def record_stop(update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Stop recording and show summary"""
        if update.effective_user.id != AUTHORIZED_USER_ID:
            await update.message.reply_text("Maaf, Anda tidak diizinkan mengakses bot ini.")
            return
        
        try:
            base_url = get_base_url()
            if not base_url:
                await update.message.reply_text("❌ **Error: PUBLIC_URL tidak terkonfigurasi!**")
                return
            
            url = f"{base_url}/record_stop"
            response = requests.post(url, timeout=10)
            response.raise_for_status()
            result = response.json()
            
            if result.get('status') == 'RECORDING_STOPPED':
                duration_seconds = result.get('duration_seconds', 0)
                data_points = result.get('data_points', 0)
                filename = result.get('filename', 'N/A')
                label = result.get('label', 'N/A')
                road_type = result.get('road_type', 'N/A')
                motor_condition = result.get('motor_condition', 'N/A')
                
                duration_minutes = duration_seconds / 60
                gear_or_test = result.get('gear_or_test', '')
                
                message = f"⏹️ **RAW DATA RECORDING STOPPED**\n\n"
                message += f"📝 **Label**: {label}\n"
                message += f"🛣️ **Road Type**: {road_type}\n"
                message += f"🏍️ **Motor Condition**: {motor_condition}\n"
                if gear_or_test:
                    if gear_or_test.startswith('gigi'):
                        message += f"⚙️ **Gear**: {gear_or_test}\n"
                    else:
                        message += f"🧪 **Test**: {gear_or_test}\n"
                message += f"⏱️ **Duration**: {duration_minutes:.1f} menit\n"
                message += f"📊 **Data Points**: {data_points:,}\n"
                message += f"📁 **File**: {filename}\n\n"
                message += f"💾 Data RAW tersimpan di server\n"
                message += f"📥 Gunakan /record_export {label} untuk download"
                
                await update.message.reply_text(message)
            else:
                await update.message.reply_text(f"❌ Error: {result.get('error', 'Unknown error')}")
        except requests.exceptions.RequestException as e:
            print(f"Request error in record_stop: {e}")
            await update.message.reply_text(f"❌ **Error koneksi:** {str(e)}\n\nURL: `{get_base_url()}/record_stop`")
        except Exception as e:
            print(f"Error in record_stop: {e}")
            await update.message.reply_text(f"❌ Error: {str(e)}")

    async def record_status(update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Check recording status"""
        if update.effective_user.id != AUTHORIZED_USER_ID:
            await update.message.reply_text("Maaf, Anda tidak diizinkan mengakses bot ini.")
            return
        
        try:
            base_url = get_base_url()
            if not base_url:
                await update.message.reply_text("❌ **Error: PUBLIC_URL tidak terkonfigurasi!**")
                return
            
            url = f"{base_url}/record_status"
            response = requests.get(url, timeout=10)
            response.raise_for_status()
            result = response.json()
            
            if result.get('status') == 'RECORDING':
                label = result.get('label', 'N/A')
                road_type = result.get('road_type', 'N/A')
                motor_condition = result.get('motor_condition', 'N/A')
                duration_minutes = result.get('duration_minutes', 0)
                elapsed_minutes = result.get('elapsed_minutes', 0)
                progress_percent = result.get('progress_percent', 0)
                data_points = result.get('data_points', 0)
                
                progress_bar_length = 20
                filled_length = int(progress_bar_length * progress_percent / 100)
                progress_bar = "█" * filled_length + "░" * (progress_bar_length - filled_length)
                gear_or_test = result.get('gear_or_test', '')
                
                message = f"🎬 **RAW DATA RECORDING STATUS**\n\n"
                message += f"📝 **Label**: {label}\n"
                message += f"🛣️ **Road Type**: {road_type}\n"
                message += f"🏍️ **Motor Condition**: {motor_condition}\n"
                if gear_or_test:
                    if gear_or_test.startswith('gigi'):
                        message += f"⚙️ **Gear**: {gear_or_test}\n"
                    else:
                        message += f"🧪 **Test**: {gear_or_test}\n"
                message += f"⏱️ **Progress**: {elapsed_minutes:.1f} / {duration_minutes} menit\n"
                message += f"🔋 **Baterai Alat**: {recording_status['battery_level']:.1f}%\n"
                message += f"📊 **Data Points**: {data_points:,}\n\n"
                message += f"📈 **Progress Bar**:\n"
                message += f"`{progress_bar}` {progress_percent:.1f}%\n\n"
                message += f"⏹️ Gunakan /record_stop untuk stop"
                
                await update.message.reply_text(message)
            else:
                await update.message.reply_text("📹 Tidak ada recording yang aktif.\n\n"
                                              "Gunakan /record_start untuk mulai recording.")
        except requests.exceptions.RequestException as e:
            print(f"Request error in record_status: {e}")
            await update.message.reply_text(f"❌ **Error koneksi:** {str(e)}\n\nURL: `{get_base_url()}/record_status`")
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
                await update.message.reply_text("❌ Format: /record_export <label>\n\n"
                                              "Contoh: /record_export jalan_mulus_normal")
                return
            
            label = context.args[0]
            base_url = get_base_url()
            if not base_url:
                await update.message.reply_text("❌ **Error: PUBLIC_URL tidak terkonfigurasi!**")
                return
            
            url = f"{base_url}/record_export/{label}"
            response = requests.get(url, timeout=10)
            response.raise_for_status()
            result = response.json()
            
            if result.get('status') == 'SUCCESS':
                filename = result.get('filename', 'N/A')
                data_points = result.get('data_points', 0)
                csv_data = result.get('data', '')
                
                csv_filename = f"raw_vibration_data_{label}.csv"
                csv_bytes = csv_data.encode('utf-8')
                csv_io = io.BytesIO(csv_bytes)
                csv_io.name = csv_filename
                
                message = f"📥 **RAW DATA EXPORT SUCCESS**\n\n"
                message += f"📝 **Label**: {label}\n"
                message += f"📊 **Data Points**: {data_points:,}\n"
                message += f"📁 **File**: {filename}\n\n"
                message += f"💾 File CSV RAW data siap download"
                
                await update.message.reply_document(
                    document=csv_io,
                    filename=csv_filename,
                    caption=message
                )
                
                csv_io.close()
            else:
                await update.message.reply_text(f"❌ Error: {result.get('error', 'Unknown error')}")
        except requests.exceptions.RequestException as e:
            print(f"Request error in record_export: {e}")
            await update.message.reply_text(f"❌ **Error koneksi:** {str(e)}\n\nURL: `{get_base_url()}/record_export/{label if 'label' in locals() else 'N/A'}`")
        except Exception as e:
            print(f"Error in record_export: {e}")
            import traceback
            traceback.print_exc()
            await update.message.reply_text(f"❌ Error: {str(e)}")

    async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Show help information"""
        if update.effective_user.id != AUTHORIZED_USER_ID:
            await update.message.reply_text("Maaf, Anda tidak diizinkan mengakses bot ini.")
            return
        
        message = "🤖 **RAW DATA RECORDING BOT HELP**\n\n"
        message += "**Available Commands:**\n\n"
        message += "🎬 **Recording Commands:**\n"
        message += "• `/start` - Mulai bot dan lihat info\n"
        message += "• `/record_start <durasi> <label>` - Mulai recording\n"
        message += "• `/record_stop` - Stop recording\n"
        message += "• `/record_status` - Cek status recording\n"
        message += "• `/record_export <label>` - Download data CSV\n\n"
        message += "**Recording Format:**\n"
        message += "`/record_start <durasi_menit> <label>`\n"
        message += "`Label: <road_type>_<motor_condition>_[gigi|tes]`\n\n"
        message += "**Road Types:**\n"
        message += "• `jalan_mulus` - Jalan halus/mulus/datar\n"
        message += "• `jalan_berbatu` - Jalan berbatu/bergelombang\n"
        message += "• `jalan_menanjak` - Jalan menanjak\n"
        message += "• `jalan_menurun` - Jalan menurun/turun\n\n"
        message += "**Motor Conditions:**\n"
        message += "• `normal` - Motor dalam kondisi normal\n"
        message += "• `rusak_ringan` - Motor rusak ringan (aus)\n"
        message += "• `rusak_berat` - Motor rusak berat (rantai patah)\n\n"
        message += "**Gear (Opsional):**\n"
        message += "• `gigi1`, `gigi2`, `gigi3`, `gigi4`\n\n"
        message += "**Test Number (Opsional, Fleksibel):**\n"
        message += "• `tes1`, `tes2`, `tes3`, ... (nomor bebas)\n\n"
        message += "**Examples dengan Gigi:**\n"
        message += "• `/record_start 30 jalan_mulus_normal_gigi1`\n"
        message += "• `/record_start 45 jalan_berbatu_rusak_ringan_gigi2`\n"
        message += "• `/record_start 60 jalan_menanjak_rusak_berat_gigi4`\n"
        message += "• `/record_start 30 jalan_menurun_normal_gigi1`\n\n"
        message += "**Examples dengan Test:**\n"
        message += "• `/record_start 30 jalan_mulus_tes1`\n"
        message += "• `/record_start 45 jalan_berbatu_tes2`\n"
        message += "• `/record_start 30 jalan_menurun_tes1`\n\n"
        message += "**Examples tanpa Gigi/Test:**\n"
        message += "• `/record_start 30 jalan_mulus_normal`\n"
        message += "• `/record_start 45 jalan_berbatu_rusak_ringan`\n"
        message += "• `/record_start 30 jalan_menurun_normal`"
        
        await update.message.reply_text(message)

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
            application.add_handler(CommandHandler("help", help_command))
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

# Flask API endpoints
@app.route('/record_start', methods=['POST'])
def start_recording():
    """Start recording raw vibration data"""
    global recording_status, recording_data
    
    try:
        data = request.get_json()
        duration_minutes = data.get('duration_minutes', 30)
        label = data.get('label', 'recording')
        road_type = data.get('road_type', 'unknown')
        motor_condition = data.get('motor_condition', 'unknown')
        gear_or_test = data.get('gear_or_test', '')
        
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
            recording_status['road_type'] = road_type
            recording_status['motor_condition'] = motor_condition
            recording_status['gear_or_test'] = gear_or_test
            recording_status['data_points'] = 0
            
            # Create filename
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            filename = f"raw_vibration_data_{label}_{timestamp}.csv"
            recording_status['file_path'] = filename
            
            # Clear previous data
            recording_data.clear()
            
            # Create CSV header (dengan kolom gear_or_test)
            csv_header = "timestamp,x,y,z,label,road_type,motor_condition,gear_or_test\n"
            with open(filename, 'w') as f:
                f.write(csv_header)
        
        return jsonify({
            'status': 'RECORDING_STARTED',
            'duration_minutes': duration_minutes,
            'label': label,
            'road_type': road_type,
            'motor_condition': motor_condition,
            'gear_or_test': gear_or_test,
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
                'label': recording_status['label'],
                'road_type': recording_status['road_type'],
                'motor_condition': recording_status['motor_condition'],
                'gear_or_test': recording_status.get('gear_or_test', '')
            }
            
            # Reset recording status
            recording_status = {
                'active': False,
                'start_time': None,
                'duration_minutes': 0,
                'label': '',
                'data_points': 0,
                'file_path': '',
                'road_type': '',
                'motor_condition': '',
                'gear_or_test': ''
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
                'road_type': recording_status['road_type'],
                'motor_condition': recording_status['motor_condition'],
                'gear_or_test': recording_status.get('gear_or_test', ''),
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
        
        pattern = f"raw_vibration_data_{label}_*.csv"
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

@app.route('/raw_data', methods=['POST'])
def receive_raw_data():
    """Receive raw vibration data from ESP32"""

    # --- SAFETY NET: Definisi Awal ---
    # Kita set nilai default dulu supaya variabel ini PASTI ADA
    # Apapun yang terjadi nanti, variabel ini tidak akan null/undefined
    arrival_timestamp = int(time.time() * 1000)
    
    try:
        # 1. Validasi Data Masuk (DIPERKUAT)
        data = request.get_json()
        if not data:
            return jsonify({'error': 'No JSON received', 'status': 'ERROR'}), 400

        # --- TAMBAHKAN KODE INI ---
        if 'vbat' in data:
            recording_status['battery_level'] = data['vbat']
         
        # Cek kelengkapan key (FITUR TAMBAHAN)
        if 'x' not in data or 'y' not in data or 'z' not in data:
            print("Error: JSON missing x, y, z keys")
            return jsonify({'error': 'Invalid keys', 'status': 'ERROR'}), 400
        
        # Extract vibration data
        x_data = data['x']
        y_data = data['y']
        z_data = data['z']
        
        # Debug logging
        print(f"Received raw data: {len(x_data)} samples, timestamp: {arrival_timestamp}")
        print(f"X range: {min(x_data):.3f} to {max(x_data):.3f}")
        print(f"Y range: {min(y_data):.3f} to {max(y_data):.3f}")
        print(f"Z range: {min(z_data):.3f} to {max(z_data):.3f}")

        # Define Sampling Rate (MUST match ESP32)
        FS = 1600  # <--- LOCKED AT 1600 Hz
        time_step_ms = 1000 / FS
        # -------------------------------------------

        # Write to recording file if active
        with recording_lock:
            if recording_status['active']:
                try:
                    # Validasi File Path (FITUR TAMBAHAN - Mencegah Crash)
                    if not recording_status['file_path']:
                        print("Error: File path is empty! Cannot write data.")
                        return jsonify({'status': 'ERROR', 'msg': 'No file path set'}), 500
                        
                    with open(recording_status['file_path'], 'a') as f:
                        num_samples = len(x_data)
                        
                        for i in range(num_samples):
                            # --- TIMESTAMP CALCULATION ---
                            # Calculate precise time for THIS specific sample by working backwards
                            # Sample N (last one) = arrival_timestamp
                            # Sample 0 (first one) = arrival_timestamp - duration
                            samples_from_end = num_samples - 1 - i
                            time_offset = samples_from_end * time_step_ms
                            exact_time_ms = arrival_timestamp - time_offset
                            
                            # Format as ISO String for readability/thesis verification
                            dt_object = datetime.fromtimestamp(exact_time_ms / 1000.0)
                            time_str = dt_object.strftime('%Y-%m-%d %H:%M:%S.%f')[:-3]

                            # Casting Float (FITUR TAMBAHAN - Data Safety)
                            val_x = float(x_data[i])
                            val_y = float(y_data[i])
                            val_z = float(z_data[i])
                            
                            # --- CSV WRITING (PRESERVING ALL COLUMNS) ---
                            # Format: timestamp, x, y, z, label, road_type, motor_condition, gear_or_test
                            # Note: We use 'time_str' instead of the raw 'timestamp'
                            gear_or_test_value = recording_status.get('gear_or_test', '')
                            csv_line = f"{time_str},{x_data[i]},{y_data[i]},{z_data[i]},{recording_status['label']},{recording_status['road_type']},{recording_status['motor_condition']},{gear_or_test_value}\n"
                            f.write(csv_line)
                            
                            recording_status['data_points'] += 1

                    # Debug print (Optional: Keep your existing logging style)
                    print(f"Raw data written: {len(x_data)} samples to {recording_status['file_path']}")
                except Exception as e:
                    print(f"CRITICAL WRITE ERROR: {e}")
                    traceback.print_exc() # Cetak error lengkap di log Railway
                
                # Check if recording time is up
                current_time = int(time.time() * 1000)
                
                # SAFETY CHECK: Pastikan start_time ada sebelum menghitung selisih
                if recording_status['start_time'] is not None:
                    elapsed_ms = current_time - recording_status['start_time']
                    total_ms = recording_status['duration_minutes'] * 60 * 1000
                    
                    if elapsed_ms >= total_ms:
                        recording_status['active'] = False
                        print(f"Recording auto-stopped after {recording_status['duration_minutes']} minutes")
                else:
                    # Jika start_time None tapi active True, ini aneh.
                    # Opsional: Set start_time ke sekarang atau matikan recording.
                    # Untuk aman, biarkan saja atau log warning.
                    pass            
        # Prepare response
        response = {
            'timestamp': arrival_timestamp,
            'samples_received': len(x_data),
            'recording_active': recording_status['active'],
            'status': 'SUCCESS'
        }
        
        if recording_status['active']:
            response['recording'] = {
                'label': recording_status['label'],
                'data_points': recording_status['data_points'],
                'duration_minutes': recording_status['duration_minutes']
            }
        
        print(f"Raw data processed: {len(x_data)} samples, recording: {recording_status['active']}")
        return jsonify(response)
        
    except Exception as e:
        print(f"Error in raw data endpoint: {e}")
        traceback.print_exc()
        return jsonify({'error': str(e), 'status': 'ERROR'}), 500

@app.route('/status', methods=['GET'])
def get_status():
    """Check server status"""
    return jsonify({
        'status': 'RUNNING',
        'recording_active': recording_status['active'],
        'timestamp': datetime.now().isoformat(),
        'telegram_available': TELEGRAM_AVAILABLE
    })

if __name__ == '__main__':
    # Jalankan Flask di thread terpisah
    def run_flask():
        # Get port from environment variable (Railway) or use default
        port = int(os.environ.get('PORT', 5000))
        print(f"Starting RAW DATA RECORDING server on port {port}...")
        print(f"Server will be available at: http://localhost:{port}")
        print(f"Raw data endpoint: http://localhost:{port}/raw_data")
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
