import pandas as pd
import numpy as np
import matplotlib.pyplot as plt

print("=" * 60)
print("ANALISIS DISTRIBUSI RMS UNTUK THRESHOLD OPTIMAL")
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

# Calculate RMS for each sample
print("Calculating RMS values...")
df_combined['RMS_X'] = np.sqrt(df_combined['X ']**2)
df_combined['RMS_Y'] = np.sqrt(df_combined['Y ']**2)
df_combined['RMS_Z'] = np.sqrt(df_combined['Z ']**2)
df_combined['RMS_Total'] = np.sqrt(df_combined['X ']**2 + df_combined['Y ']**2 + df_combined['Z ']**2)

# Analyze RMS distribution per class
print("\n" + "=" * 40)
print("DISTRIBUSI RMS PER KELAS")
print("=" * 40)

for label in ['NORMAL', 'RINGAN', 'BERAT']:
    mask = df_combined['true_label'] == label
    if mask.sum() > 0:
        data = df_combined[mask]
        print(f"\n{label} ({mask.sum()} samples):")
        print(f"  RMS_X:  mean={data['RMS_X'].mean():.4f}, std={data['RMS_X'].std():.4f}, max={data['RMS_X'].max():.4f}")
        print(f"  RMS_Y:  mean={data['RMS_Y'].mean():.4f}, std={data['RMS_Y'].std():.4f}, max={data['RMS_Y'].max():.4f}")
        print(f"  RMS_Z:  mean={data['RMS_Z'].mean():.4f}, std={data['RMS_Z'].std():.4f}, max={data['RMS_Z'].max():.4f}")
        print(f"  RMS_Total: mean={data['RMS_Total'].mean():.4f}, std={data['RMS_Total'].std():.4f}, max={data['RMS_Total'].max():.4f}")

# Find optimal thresholds
print("\n" + "=" * 40)
print("PENCARIAN THRESHOLD OPTIMAL")
print("=" * 40)

# Get RMS values for each class
normal_rms = df_combined[df_combined['true_label'] == 'NORMAL']['RMS_Total']
ringan_rms = df_combined[df_combined['true_label'] == 'RINGAN']['RMS_Total']
berat_rms = df_combined[df_combined['true_label'] == 'BERAT']['RMS_Total']

print(f"Normal RMS range: {normal_rms.min():.4f} - {normal_rms.max():.4f}")
print(f"Ringan RMS range: {ringan_rms.min():.4f} - {ringan_rms.max():.4f}")
print(f"Berat RMS range: {berat_rms.min():.4f} - {berat_rms.max():.4f}")

# Calculate percentiles for threshold suggestions
print(f"\nNormal RMS 95th percentile: {normal_rms.quantile(0.95):.4f}")
print(f"Ringan RMS 50th percentile: {ringan_rms.quantile(0.50):.4f}")
print(f"Berat RMS 50th percentile: {berat_rms.quantile(0.50):.4f}")

# Test different thresholds
print("\n" + "=" * 40)
print("TEST THRESHOLD BERBAGAI NILAI")
print("=" * 40)

thresholds = [0.5, 1.0, 1.5, 2.0, 2.5, 3.0]

for threshold in thresholds:
    # Simple classification based on RMS_Total
    def classify_rms(rms_value):
        if rms_value <= threshold:
            return 'NORMAL'
        elif rms_value <= threshold * 1.5:  # Ringan threshold
            return 'RINGAN'
        else:
            return 'BERAT'
    
    # Apply classification
    predictions = df_combined['RMS_Total'].apply(classify_rms)
    accuracy = (df_combined['true_label'] == predictions).mean()
    
    print(f"Threshold {threshold:.1f}: Accuracy = {accuracy:.4f} ({accuracy*100:.2f}%)")
    
    # Per-class accuracy
    for label in ['NORMAL', 'RINGAN', 'BERAT']:
        mask = df_combined['true_label'] == label
        if mask.sum() > 0:
            class_acc = (predictions[mask] == label).mean()
            print(f"  {label}: {class_acc:.4f} ({class_acc*100:.2f}%)")

print("\n" + "=" * 40)
print("REKOMENDASI THRESHOLD")
print("=" * 40)

print("Berdasarkan analisis, rekomendasi threshold:")
print("1. NORMAL: RMS_Total <= 1.0")
print("2. RINGAN: 1.0 < RMS_Total <= 1.5")
print("3. BERAT: RMS_Total > 1.5")

print("\nLangkah selanjutnya:")
print("1. Update fungsi classify_vibration di server")
print("2. Test dengan threshold baru")
print("3. Evaluasi ulang akurasi model")

print("\nApakah Anda ingin saya bantu update server dengan threshold baru?") 