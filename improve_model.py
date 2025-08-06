import pandas as pd
import numpy as np
import matplotlib.pyplot as plt

print("=" * 60)
print("ANALISIS MASALAH KLASIFIKASI RINGAN vs BERAT")
print("=" * 60)

# Load datasets
print("Loading datasets...")
df_normal_ringan = pd.read_excel("Dataset PCA (Normal 80 + Ringan 20).xlsx")
df_normal_berat = pd.read_excel("Dataset PCA (Normal 80 + Berat 20).xlsx")

# Combine datasets
df_combined = pd.concat([df_normal_ringan, df_normal_berat], ignore_index=True)
df_combined.columns = df_combined.columns.str.strip()

print(f"Total samples: {len(df_combined)}")

# Create labels
normal_ringan_count = len(df_normal_ringan)
normal_berat_count = len(df_normal_berat)

normal_ringan_labels = ['NORMAL'] * int(0.8 * normal_ringan_count) + ['RINGAN'] * (normal_ringan_count - int(0.8 * normal_ringan_count))
normal_berat_labels = ['NORMAL'] * int(0.8 * normal_berat_count) + ['BERAT'] * (normal_berat_count - int(0.8 * normal_berat_count))

df_normal_ringan['true_label'] = normal_ringan_labels
df_normal_berat['true_label'] = normal_berat_labels

df_combined = pd.concat([df_normal_ringan, df_normal_berat], ignore_index=True)

print("\nLabel distribution:")
print(df_combined['true_label'].value_counts())

# Analyze features for each class
print("\n" + "=" * 40)
print("ANALISIS FITUR PER KELAS")
print("=" * 40)

# Check available columns
print("Available columns:", list(df_combined.columns))

# Analyze raw features if available
if all(col in df_combined.columns for col in ['X', 'Y', 'Z']):
    print("\nAnalisis fitur X, Y, Z:")
    for label in ['NORMAL', 'RINGAN', 'BERAT']:
        mask = df_combined['true_label'] == label
        if mask.sum() > 0:
            data = df_combined[mask]
            print(f"\n{label}:")
            print(f"  X: mean={data['X'].mean():.4f}, std={data['X'].std():.4f}, max={data['X'].max():.4f}")
            print(f"  Y: mean={data['Y'].mean():.4f}, std={data['Y'].std():.4f}, max={data['Y'].max():.4f}")
            print(f"  Z: mean={data['Z'].mean():.4f}, std={data['Z'].std():.4f}, max={data['Z'].max():.4f}")
            
            # Calculate RMS
            rms_x = np.sqrt(np.mean(data['X']**2))
            rms_y = np.sqrt(np.mean(data['Y']**2))
            rms_z = np.sqrt(np.mean(data['Z']**2))
            print(f"  RMS: X={rms_x:.4f}, Y={rms_y:.4f}, Z={rms_z:.4f}")

# Analyze PCA features if available
if all(col in df_combined.columns for col in ['PC1_Source', 'PC2_Source']):
    print("\nAnalisis fitur PCA:")
    for label in ['NORMAL', 'RINGAN', 'BERAT']:
        mask = df_combined['true_label'] == label
        if mask.sum() > 0:
            data = df_combined[mask]
            print(f"\n{label}:")
            print(f"  PC1: mean={data['PC1_Source'].mean():.4f}, std={data['PC1_Source'].std():.4f}")
            print(f"  PC2: mean={data['PC2_Source'].mean():.4f}, std={data['PC2_Source'].std():.4f}")

print("\n" + "=" * 40)
print("REKOMENDASI PERBAIKAN")
print("=" * 40)

print("1. MASALAH IDENTIFIKASI:")
print("   - Model tidak bisa membedakan RINGAN vs BERAT")
print("   - Semua anomali diklasifikasi sebagai BERAT")
print("   - Threshold RMS (2.0) terlalu tinggi")

print("\n2. SOLUSI YANG DISARANKAN:")
print("   - Sesuaikan threshold RMS untuk RINGAN (misal: 1.0-1.5)")
print("   - Tambah fitur RMS total (sqrt(X²+Y²+Z²))")
print("   - Gunakan range nilai untuk klasifikasi")

print("\n3. LANGKAH SELANJUTNYA:")
print("   - Analisis distribusi RMS per kelas")
print("   - Tentukan threshold yang optimal")
print("   - Test dengan threshold baru")

print("\nApakah Anda ingin melanjutkan dengan analisis distribusi RMS?") 