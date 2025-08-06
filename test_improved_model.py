import pandas as pd
import numpy as np
from sklearn.ensemble import IsolationForest
from sklearn.metrics import accuracy_score, classification_report

print("=" * 60)
print("TEST MODEL YANG DIPERBAIKI")
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

# Train Isolation Forest
X_pca = df_combined[['PC1_Source', 'PC2_Source']].dropna()
iso_forest = IsolationForest(contamination='auto', random_state=42)
iso_forest.fit(X_pca)

# Improved classification function (same as in server)
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
print("HASIL TEST MODEL YANG DIPERBAIKI")
print("=" * 40)

predictions = []
confidences = []
distances = []

for idx, row in df_combined.iterrows():
    if pd.isna(row['PC1_Source']) or pd.isna(row['PC2_Source']):
        continue
        
    # Get PCA features
    pc1, pc2 = row['PC1_Source'], row['PC2_Source']
    
    # Get anomaly prediction
    feature_vector = np.array([[pc1, pc2]])
    anomaly_score = iso_forest.decision_function(feature_vector)[0]
    is_anomaly = iso_forest.predict(feature_vector)[0]
    
    # Calculate distance
    distance = np.sqrt(pc1**2 + pc2**2)
    
    # Classify
    predicted_label, confidence = improved_classify_vibration(pc1, pc2, anomaly_score, is_anomaly)
    
    predictions.append(predicted_label)
    confidences.append(confidence)
    distances.append(distance)

# Calculate accuracy
accuracy = accuracy_score(df_combined['true_label'].iloc[:len(predictions)], predictions)

print(f"Improved Model Results:")
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

# Distance analysis
print("\n" + "=" * 40)
print("ANALISIS DISTANCE FROM NORMAL")
print("=" * 40)

for label in ['NORMAL', 'RINGAN', 'BERAT']:
    mask = df_combined['true_label'].iloc[:len(predictions)] == label
    if mask.sum() > 0:
        label_distances = np.array(distances)[mask]
        print(f"\n{label}:")
        print(f"  Mean distance: {label_distances.mean():.6f}")
        print(f"  Std distance: {label_distances.std():.6f}")
        print(f"  Min distance: {label_distances.min():.6f}")
        print(f"  Max distance: {label_distances.max():.6f}")

print("\n" + "=" * 40)
print("PERBANDINGAN SEBELUM vs SESUDAH")
print("=" * 40)

print("SEBELUM (RMS-based):")
print("  - NORMAL: ~92%")
print("  - RINGAN: 0%")
print("  - BERAT: ~32%")
print("  - Overall: 76.8%")

print(f"\nSESUDAH (PCA-based):")
print(f"  - Overall: {accuracy*100:.1f}%")

if accuracy > 0.768:
    improvement = (accuracy - 0.768) / 0.768 * 100
    print(f"  - Peningkatan: +{improvement:.1f}%")
else:
    decline = (0.768 - accuracy) / 0.768 * 100
    print(f"  - Penurunan: -{decline:.1f}%")

print("\n" + "=" * 40)
print("KESIMPULAN")
print("=" * 40)

if accuracy > 0.8:
    print("✅ Model yang diperbaiki menunjukkan hasil yang BAIK!")
    print("   - Siap untuk deployment")
    print("   - Monitor performa di production")
elif accuracy > 0.75:
    print("⚠️ Model yang diperbaiki menunjukkan hasil yang CUKUP")
    print("   - Bisa digunakan dengan monitoring ketat")
    print("   - Pertimbangkan fine-tuning lebih lanjut")
else:
    print("❌ Model yang diperbaiki masih perlu perbaikan")
    print("   - Review threshold values")
    print("   - Pertimbangkan algoritma lain")

print(f"\nModel sudah diupdate di realtime_vibration_server.py")
print("Silakan test dengan data real-time!") 