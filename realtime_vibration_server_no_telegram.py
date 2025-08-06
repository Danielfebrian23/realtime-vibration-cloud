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

# Simpan status terakhir
last_status = {
    'severity': 'NORMAL',
    'confidence': 0.98,
    'penjelasan': 'Motor dalam kondisi normal.',
    'tips': 'Cek motor setiap hari atau perminggu dengan menambahkan pelumas rantai atau chain cleaner agar dapat memperpanjang waktu masa rantai, dan untuk mengecek lebih akurat kapan mulai menyimpang bisa pakai smart device ini setiap saat!',
    'riwayat': [("NORMAL", 0.98), ("RINGAN", 0.6), ("BERAT", 0.2)]
}

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
        # Combine datasets
        df_combined = pd.concat([df_normal_ringan, df_normal_berat], ignore_index=True)
        df_combined.columns = df_combined.columns.str.strip()
        # Prepare features
        X = df_combined[['PC1_Source', 'PC2_Source']].dropna()
        # Train Isolation Forest
        iso_forest_model = IsolationForest(contamination='auto', random_state=42)
        iso_forest_model.fit(X)
        # Train PCA (untuk feature extraction dari raw data)
        raw_features = df_combined[['X','Y','Z']].dropna()
        scaler_model = StandardScaler()
        X_scaled = scaler_model.fit_transform(raw_features)
        pca_model = PCA(n_components=2)
        pca_model.fit(X_scaled)
        print("Models trained successfully!")
    except Exception as e:
        print(f"Error training models: {e}")
        # Fallback: create simple models
        iso_forest_model = IsolationForest(contamination=0.1, random_state=42)
        pca_model = PCA(n_components=2)
        scaler_model = StandardScaler()

def extract_features_from_buffer(data_buffer):
    """Extract features from vibration data buffer"""
    if len(data_buffer) < 10:
        return None
    # Convert to DataFrame
    df = pd.DataFrame(data_buffer, columns=['x', 'y', 'z'])
    # Calculate statistical features
    features = {
        'mean_x': df['x'].mean(),
        'mean_y': df['y'].mean(),
        'mean_z': df['z'].mean(),
        'std_x': df['x'].std(),
        'std_y': df['y'].std(),
        'std_z': df['z'].std(),
        'max_x': df['x'].max(),
        'max_y': df['y'].max(),
        'max_z': df['z'].max(),
        'min_x': df['x'].min(),
        'min_y': df['y'].min(),
        'min_z': df['z'].min(),
        'rms_x': np.sqrt(np.mean(df['x']**2)),
        'rms_y': np.sqrt(np.mean(df['y']**2)),
        'rms_z': np.sqrt(np.mean(df['z']**2))
    }
    # Apply PCA transformation
    if scaler_model and pca_model:
        raw_data = df[['x', 'y', 'z']].values
        scaled_data = scaler_model.transform(raw_data)
        pca_features = pca_model.transform(scaled_data)
        # Use mean of PCA components
        features['PC1'] = pca_features[:, 0].mean()
        features['PC2'] = pca_features[:, 1].mean()
    return features

def classify_vibration(features):
    """Classify vibration condition using Isolation Forest with improved PCA-based classification"""
    if not is_model_loaded or iso_forest_model is None:
        return "UNKNOWN", 0.0
    try:
        # Prepare features for prediction
        feature_vector = np.array([
            features['PC1'], features['PC2']
        ]).reshape(1, -1)
        
        # Predict anomaly score
        anomaly_score = iso_forest_model.decision_function(feature_vector)[0]
        is_anomaly = iso_forest_model.predict(feature_vector)[0]
        
        # Calculate distance from normal center (0,0) using PCA features
        distance_from_normal = np.sqrt(features['PC1']**2 + features['PC2']**2)
        
        # Improved classification logic using PCA distance and PC1 deviation
        if is_anomaly == -1:  # Anomaly detected
            if distance_from_normal > 0.08:  # Far from normal center
                if abs(features['PC1']) > 0.05:  # High PC1 deviation indicates severe anomaly
                    severity = "BERAT"
                    confidence = min(abs(anomaly_score) * 0.8, 0.95)
                else:
                    severity = "RINGAN"
                    confidence = min(abs(anomaly_score) * 0.6, 0.85)
            else:
                # Close to normal but still anomaly
                severity = "RINGAN"
                confidence = min(abs(anomaly_score) * 0.5, 0.75)
        else:
            # No anomaly detected
            severity = "NORMAL"
            confidence = 1.0 - abs(anomaly_score)
            
        return severity, confidence
    except Exception as e:
        print(f"Error in classification: {e}")
        return "ERROR", 0.0

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
        # Extract features
        features = extract_features_from_buffer(realtime_buffer)
        if features is None:
            return jsonify({
                'error': 'Insufficient data for analysis',
                'status': 'WAITING'
            }), 200
        # Classify vibration
        severity, confidence = classify_vibration(features)
        # Update last_status
        last_status['severity'] = severity
        last_status['confidence'] = confidence
        last_status['riwayat'].append((severity, confidence))
        if len(last_status['riwayat']) > 10: # Keep last 10 records
            last_status['riwayat'] = last_status['riwayat'][-10:]
        # Calculate distance from normal for monitoring
        distance_from_normal = np.sqrt(features['PC1']**2 + features['PC2']**2)
        
        # Prepare response
        response = {
            'timestamp': timestamp,
            'severity': severity,
            'confidence': round(confidence, 3),
            'features': {
                'rms_x': round(features['rms_x'], 3),
                'rms_y': round(features['rms_y'], 3),
                'rms_z': round(features['rms_z'], 3),
                'PC1': round(features['PC1'], 3),
                'PC2': round(features['PC2'], 3),
                'distance_from_normal': round(distance_from_normal, 4)
            },
            'status': 'SUCCESS'
        }
        print(f"Prediction: {severity} (confidence: {confidence:.3f})")
        return jsonify(response)
    except Exception as e:
        print(f"Error in prediction endpoint: {e}")
        return jsonify({
            'error': str(e),
            'status': 'ERROR'
        }), 500

@app.route('/status', methods=['GET'])
def get_status():
    """Check server status"""
    return jsonify({
        'status': 'RUNNING',
        'model_loaded': is_model_loaded,
        'buffer_size': len(realtime_buffer),
        'timestamp': datetime.now().isoformat(),
        'measuring_status': measuring_status['active']
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
    
    print("Starting Flask server without Telegram bot...")
    print("Server will be available at: http://localhost:5000")
    print("Prediction endpoint: http://localhost:5000/predict")
    print("Press CTRL+C to quit")
    
    app.run(host='0.0.0.0', port=5000, debug=False) 