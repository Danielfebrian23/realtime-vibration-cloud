import pandas as pd
import numpy as np
from sklearn.ensemble import IsolationForest
from sklearn.metrics import accuracy_score, classification_report

print("=" * 60)
print("PERBAIKAN KLASIFIKASI DENGAN PCA FEATURES")
print("=" * 60)

# Load datasets
print("Loading datasets...")
df_normal_ringan = pd.read_excel("Dataset PCA (Normal 80 + Ringan 20).xlsx")
df_normal_berat = pd.read_excel("Dataset PCA (Normal 80 + Berat 20).xlsx")

# Combine datasets
df_combined = pd.concat([df_normal_ringan, df_normal_berat], ignore_index=True)
df_combined.columns = df_combined.columns.str.strip()

# Create labels
normal_ringan_count = len(df_normal_ringan)
normal_berat_count = len(df_normal_berat)

normal_ringan_labels = ['NORMAL'] * int(0.8 * normal_ringan_count) + ['RINGAN'] * (normal_ringan_count - int(0.8 * normal_ringan_count))
normal_berat_labels = ['NORMAL'] * int(0.8 * normal_berat_count) + ['BERAT'] * (normal_berat_count - int(0.8 * normal_berat_count))

df_normal_ringan['true_label'] = normal_ringan_labels
df_normal_berat['true_label'] = normal_berat_labels

df_combined = pd.concat([df_normal_ringan, df_normal_berat], ignore_index=True)

print(f"Total samples: {len(df_combined)}")
print("Label distribution:")
print(df_combined['true_label'].value_counts())

# Analyze PCA features
print("\n" + "=" * 40)
print("ANALISIS PCA FEATURES")
print("=" * 40)

for label in ['NORMAL', 'RINGAN', 'BERAT']:
    mask = df_combined['true_label'] == label
    if mask.sum() > 0:
        data = df_combined[mask]
        print(f"\n{label} ({mask.sum()} samples):")
        print(f"  PC1: mean={data['PC1_Source'].mean():.6f}, std={data['PC1_Source'].std():.6f}")
        print(f"  PC2: mean={data['PC2_Source'].mean():.6f}, std={data['PC2_Source'].std():.6f}")
        print(f"  PC1 range: {data['PC1_Source'].min():.6f} to {data['PC1_Source'].max():.6f}")
        print(f"  PC2 range: {data['PC2_Source'].min():.6f} to {data['PC2_Source'].max():.6f}")

# Improved classification function
def improved_classify_vibration(pc1, pc2, anomaly_score, is_anomaly):
    """Improved classification using PCA features and anomaly score"""
    
    # Calculate distance from normal center (0,0)
    distance_from_normal = np.sqrt(pc1**2 + pc2**2)
    
    # Classification logic
    if is_anomaly == -1:  # Anomaly detected
        if distance_from_normal > 0.08:  # Far from normal
            if abs(pc1) > 0.05:  # High PC1 deviation
                return "BERAT", min(abs(anomaly_score) * 0.8, 0.95)
            else:
                return "RINGAN", min(abs(anomaly_score) * 0.6, 0.85)
        else:
            return "RINGAN", min(abs(anomaly_score) * 0.5, 0.75)
    else:
        return "NORMAL", 1.0 - abs(anomaly_score)

# Test improved classification
print("\n" + "=" * 40)
print("TEST KLASIFIKASI YANG DIPERBAIKI")
print("=" * 40)

# Train Isolation Forest
X_pca = df_combined[['PC1_Source', 'PC2_Source']].dropna()
iso_forest = IsolationForest(contamination='auto', random_state=42)
iso_forest.fit(X_pca)

# Apply improved classification
predictions = []
confidences = []

for idx, row in df_combined.iterrows():
    if pd.isna(row['PC1_Source']) or pd.isna(row['PC2_Source']):
        continue
        
    # Get PCA features
    pc1, pc2 = row['PC1_Source'], row['PC2_Source']
    
    # Get anomaly prediction
    feature_vector = np.array([[pc1, pc2]])
    anomaly_score = iso_forest.decision_function(feature_vector)[0]
    is_anomaly = iso_forest.predict(feature_vector)[0]
    
    # Classify
    predicted_label, confidence = improved_classify_vibration(pc1, pc2, anomaly_score, is_anomaly)
    
    predictions.append(predicted_label)
    confidences.append(confidence)

# Calculate accuracy
accuracy = accuracy_score(df_combined['true_label'].iloc[:len(predictions)], predictions)

print(f"Improved Classification Results:")
print(f"Overall Accuracy: {accuracy:.4f} ({accuracy*100:.2f}%)")

# Per-class accuracy
print("\nPer-class Accuracy:")
for label in ['NORMAL', 'RINGAN', 'BERAT']:
    mask = df_combined['true_label'].iloc[:len(predictions)] == label
    if mask.sum() > 0:
        class_acc = (np.array(predictions)[mask] == label).mean()
        print(f"  {label}: {class_acc:.4f} ({class_acc*100:.2f}%)")

# Detailed classification report
print("\nDetailed Classification Report:")
print(classification_report(df_combined['true_label'].iloc[:len(predictions)], predictions, zero_division=0))

print("\n" + "=" * 40)
print("REKOMENDASI UPDATE SERVER")
print("=" * 40)

print("Fungsi classify_vibration yang diperbaiki:")
print("""
def classify_vibration(features):
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
        
        # Calculate distance from normal center
        distance_from_normal = np.sqrt(features['PC1']**2 + features['PC2']**2)
        
        # Improved classification logic
        if is_anomaly == -1:  # Anomaly detected
            if distance_from_normal > 0.08:  # Far from normal
                if abs(features['PC1']) > 0.05:  # High PC1 deviation
                    severity = "BERAT"
                    confidence = min(abs(anomaly_score) * 0.8, 0.95)
                else:
                    severity = "RINGAN"
                    confidence = min(abs(anomaly_score) * 0.6, 0.85)
            else:
                severity = "RINGAN"
                confidence = min(abs(anomaly_score) * 0.5, 0.75)
        else:
            severity = "NORMAL"
            confidence = 1.0 - abs(anomaly_score)
            
        return severity, confidence
    except Exception as e:
        print(f"Error in classification: {e}")
        return "ERROR", 0.0
""")

print("\nApakah Anda ingin saya update server dengan fungsi yang diperbaiki ini?") 