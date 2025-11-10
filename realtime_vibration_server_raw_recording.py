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
    'motor_condition': ''
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
        """Get cleaned base URL without trailing slash or spaces"""
        if not PUBLIC_URL:
            return None
        return PUBLIC_URL.rstrip('/').strip()
    
    async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
        if update.effective_user.id != AUTHORIZED_USER_ID:
            await update.message.reply_text("Maaf, Anda tidak diizinkan mengakses bot ini.")
            return
        
        await update.message.reply_text("✅ **RAW DATA RECORDING SERVER**\n\n"
                                      "Server siap untuk recording data raw dari ESP32.\n"
                                      "Gunakan /record_start untuk mulai recording.\n\n"
                                      "**Format command:**\n"
                                      "`/record_start <durasi_menit> <road_type>_<motor_condition>`\n\n"
                                      "**Contoh:**\n"
                                      "• `/record_start 30 jalan_lurus_normal`\n"
                                      "• `/record_start 45 jalan_berbatu_rusak_ringan`\n"
                                      "• `/record_start 60 jalan_menanjak_rusak_berat`")

    async def record_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Start recording raw vibration data"""
        if update.effective_user.id != AUTHORIZED_USER_ID:
            await update.message.reply_text("Maaf, Anda tidak diizinkan mengakses bot ini.")
            return
        
        try:
            # Parse arguments
            if not context.args or len(context.args) < 2:
                await update.message.reply_text("❌ **Format salah!**\n\n"
                                              "**Format:** `/record_start <durasi_menit> <road_type>_<motor_condition>`\n\n"
                                              "**Contoh:**\n"
                                              "• `/record_start 30 jalan_lurus_normal`\n"
                                              "• `/record_start 45 jalan_berbatu_rusak_ringan`\n"
                                              "• `/record_start 60 jalan_menanjak_rusak_berat`\n\n"
                                              "**Road types:** jalan_lurus, jalan_berbatu, jalan_menanjak\n"
                                              "**Motor conditions:** normal, rusak_ringan, rusak_berat")
                return
            
            duration_minutes = int(context.args[0])
            if duration_minutes > 180:  # Max 3 hours
                duration_minutes = 180
                await update.message.reply_text("⚠️ Maksimal 180 menit. Menggunakan 180 menit.")
            
            # Parse label with flexible parsing
            label = context.args[1]
            label_lower = label.lower()
            
            # Valid road types and motor conditions
            valid_roads = ['jalan_lurus', 'jalan_berbatu', 'jalan_menanjak']
            valid_conditions = ['normal', 'rusak_ringan', 'rusak_berat']
            
            # Try to find road type by matching from the beginning
            road_type = None
            motor_condition = None
            
            for road in valid_roads:
                if label_lower.startswith(road.lower()):
                    road_type = road
                    # Get the rest after road type + underscore
                    remaining = label_lower[len(road):].lstrip('_')
                    if remaining:
                        motor_condition = remaining
                    break
            
            # If no road type found, try to extract from parts (more flexible)
            if not road_type:
                label_parts = label_lower.split('_')
                if len(label_parts) >= 2:
                    # Try to match road type from first two parts
                    possible_road = f"{label_parts[0]}_{label_parts[1]}"
                    if possible_road in valid_roads:
                        road_type = possible_road
                        motor_condition = '_'.join(label_parts[2:]) if len(label_parts) > 2 else None
                    else:
                        # Fallback: use first part as road type (for backward compatibility)
                        road_type = label_parts[0]
                        motor_condition = '_'.join(label_parts[1:])
                else:
                    road_type = label_parts[0] if label_parts else None
                    motor_condition = None
            
            # Validate road type (more lenient - allow partial matches)
            if road_type:
                # Check if road_type matches any valid road (case insensitive, allow partial)
                road_type_matched = None
                for valid_road in valid_roads:
                    if valid_road.lower() == road_type.lower() or road_type.lower() in valid_road.lower():
                        road_type_matched = valid_road
                        break
                
                if not road_type_matched:
                    # Try to find closest match
                    if 'lurus' in road_type.lower():
                        road_type_matched = 'jalan_lurus'
                    elif 'berbatu' in road_type.lower():
                        road_type_matched = 'jalan_berbatu'
                    elif 'menanjak' in road_type.lower():
                        road_type_matched = 'jalan_menanjak'
                
                if road_type_matched:
                    road_type = road_type_matched
                else:
                    await update.message.reply_text(f"❌ **Road type tidak valid!**\n\n"
                                                  f"Pilih dari: {', '.join(valid_roads)}\n\n"
                                                  f"Input yang diterima: `{label}`")
                    return
            else:
                await update.message.reply_text(f"❌ **Label tidak valid!**\n\n"
                                              f"Format: `/record_start <durasi> <road_type>_<motor_condition>`\n\n"
                                              f"Contoh: `/record_start 30 jalan_lurus_normal`")
                return
            
            # Validate motor condition (more lenient - allow partial matches and test variations)
            if motor_condition:
                motor_condition_matched = None
                motor_condition_lower = motor_condition.lower()
                
                # Check exact match first
                for valid_cond in valid_conditions:
                    if valid_cond.lower() == motor_condition_lower:
                        motor_condition_matched = valid_cond
                        break
                
                # If no exact match, try partial match
                if not motor_condition_matched:
                    if 'normal' in motor_condition_lower or 'test' in motor_condition_lower:
                        motor_condition_matched = 'normal'
                    elif 'ringan' in motor_condition_lower:
                        motor_condition_matched = 'rusak_ringan'
                    elif 'berat' in motor_condition_lower:
                        motor_condition_matched = 'rusak_berat'
                
                if motor_condition_matched:
                    motor_condition = motor_condition_matched
                else:
                    # Default to 'normal' if unclear (lenient mode)
                    original_input = motor_condition
                    motor_condition = 'normal'
                    await update.message.reply_text(f"⚠️ **Motor condition tidak jelas, menggunakan 'normal'**\n\n"
                                                  f"Input: `{original_input}`\n"
                                                  f"Valid conditions: {', '.join(valid_conditions)}")
            else:
                # Default to 'normal' if no motor condition specified
                motor_condition = 'normal'
            
            # Start recording via API
            base_url = get_base_url()
            if not base_url:
                await update.message.reply_text("❌ **Error: PUBLIC_URL tidak terkonfigurasi!**\n\n"
                                              "Pastikan environment variable RAW_PUBLIC_URL atau PUBLIC_URL sudah di-set di Railway.")
                return
            
            url = f"{base_url}/record_start"
            
            data = {
                'duration_minutes': duration_minutes,
                'label': f"{road_type}_{motor_condition}",
                'road_type': road_type,
                'motor_condition': motor_condition
            }
            
            try:
                response = requests.post(url, json=data, timeout=10)
                response.raise_for_status()  # Raise exception for bad status codes
                result = response.json()
                
                if result.get('status') == 'RECORDING_STARTED':
                    message = f"🎬 **RAW DATA RECORDING STARTED**\n\n"
                    message += f"📝 **Label**: {road_type}_{motor_condition}\n"
                    message += f"🛣️ **Road Type**: {road_type}\n"
                    message += f"🏍️ **Motor Condition**: {motor_condition}\n"
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
                # Clean up error message
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
            except ValueError as ve:
                await update.message.reply_text("❌ **Durasi harus berupa angka!**\n\n"
                                              "Contoh: `/record_start 30 jalan_lurus_normal`")
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
            
            # Stop recording via API
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
                
                message = f"⏹️ **RAW DATA RECORDING STOPPED**\n\n"
                message += f"📝 **Label**: {label}\n"
                message += f"🛣️ **Road Type**: {road_type}\n"
                message += f"🏍️ **Motor Condition**: {motor_condition}\n"
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
            
            # Get recording status via API
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
                
                # Create progress bar
                progress_bar_length = 20
                filled_length = int(progress_bar_length * progress_percent / 100)
                progress_bar = "█" * filled_length + "░" * (progress_bar_length - filled_length)
                
                message = f"🎬 **RAW DATA RECORDING STATUS**\n\n"
                message += f"📝 **Label**: {label}\n"
                message += f"🛣️ **Road Type**: {road_type}\n"
                message += f"🏍️ **Motor Condition**: {motor_condition}\n"
                message += f"⏱️ **Progress**: {elapsed_minutes:.1f} / {duration_minutes} menit\n"
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
                                              "Contoh: /record_export jalan_lurus_normal")
                return
            
            label = context.args[0]
            
            base_url = get_base_url()
            if not base_url:
                await update.message.reply_text("❌ **Error: PUBLIC_URL tidak terkonfigurasi!**")
                return
            
            # Export recording via API
            url = f"{base_url}/record_export/{label}"
            response = requests.get(url, timeout=10)
            response.raise_for_status()
            result = response.json()
            
            if result.get('status') == 'SUCCESS':
                filename = result.get('filename', 'N/A')
                data_points = result.get('data_points', 0)
                csv_data = result.get('data', '')
                
                # Create CSV file and send
                csv_filename = f"raw_vibration_data_{label}.csv"
                
                # Send as document
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
        message += "`/record_start <durasi_menit> <road_type>_<motor_condition>`\n\n"
        message += "**Road Types:**\n"
        message += "• `jalan_lurus` - Jalan lurus/datar\n"
        message += "• `jalan_berbatu` - Jalan berbatu/bergelombang\n"
        message += "• `jalan_menanjak` - Jalan menanjak\n\n"
        message += "**Motor Conditions:**\n"
        message += "• `normal` - Motor dalam kondisi normal\n"
        message += "• `rusak_ringan` - Motor rusak ringan (aus)\n"
        message += "• `rusak_berat` - Motor rusak berat (rantai patah)\n\n"
        message += "**Examples:**\n"
        message += "• `/record_start 30 jalan_lurus_normal`\n"
        message += "• `/record_start 45 jalan_berbatu_rusak_ringan`\n"
        message += "• `/record_start 60 jalan_menanjak_rusak_berat`"
        
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
            recording_status['data_points'] = 0
            
            # Create filename
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            filename = f"raw_vibration_data_{label}_{timestamp}.csv"
            recording_status['file_path'] = filename
            
            # Clear previous data
            recording_data.clear()
            
            # Create CSV header
            csv_header = "timestamp,x,y,z,label,road_type,motor_condition\n"
            with open(filename, 'w') as f:
                f.write(csv_header)
        
        return jsonify({
            'status': 'RECORDING_STARTED',
            'duration_minutes': duration_minutes,
            'label': label,
            'road_type': road_type,
            'motor_condition': motor_condition,
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
                'motor_condition': recording_status['motor_condition']
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
                'motor_condition': ''
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
        print(f"Received raw data: {len(x_data)} samples, timestamp: {timestamp}")
        print(f"X range: {min(x_data):.3f} to {max(x_data):.3f}")
        print(f"Y range: {min(y_data):.3f} to {max(y_data):.3f}")
        print(f"Z range: {min(z_data):.3f} to {max(z_data):.3f}")
        
        # Write to recording file if active
        with recording_lock:
            if recording_status['active']:
                try:
                    with open(recording_status['file_path'], 'a') as f:
                        for i in range(len(x_data)):
                            csv_line = f"{timestamp},{x_data[i]},{y_data[i]},{z_data[i]},{recording_status['label']},{recording_status['road_type']},{recording_status['motor_condition']}\n"
                            f.write(csv_line)
                            recording_status['data_points'] += 1
                    
                    print(f"Raw data written: {len(x_data)} samples to {recording_status['file_path']}")
                except Exception as e:
                    print(f"Error writing raw data: {e}")
                
                # Check if recording time is up
                current_time = int(time.time() * 1000)
                elapsed_ms = current_time - recording_status['start_time']
                total_ms = recording_status['duration_minutes'] * 60 * 1000
                if elapsed_ms >= total_ms:
                    recording_status['active'] = False
                    print(f"Recording auto-stopped after {recording_status['duration_minutes']} minutes")
        
        # Prepare response
        response = {
            'timestamp': timestamp,
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
        return jsonify({
            'error': str(e),
            'status': 'ERROR'
        }), 500

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
