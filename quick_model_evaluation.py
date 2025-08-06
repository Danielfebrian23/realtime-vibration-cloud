import pandas as pd
import numpy as np
from sklearn.ensemble import IsolationForest
from sklearn.decomposition import PCA
from sklearn.preprocessing import StandardScaler
from sklearn.metrics import accuracy_score, classification_report
import warnings
warnings.filterwarnings('ignore')

def quick_evaluate_model():
    """Quick model evaluation without extensive warnings"""
    print("=" * 50)
    print("QUICK MODEL ACCURACY EVALUATION")
    print("=" * 50)
    
    # Load datasets
    print("Loading datasets...")
    df_normal_ringan = pd.read_excel("Dataset PCA (Normal 80 + Ringan 20).xlsx")
    df_normal_berat = pd.read_excel("Dataset PCA (Normal 80 + Berat 20).xlsx")
    
    # Combine datasets
    df_combined = pd.concat([df_normal_ringan, df_normal_berat], ignore_index=True)
    df_combined.columns = df_combined.columns.str.strip()
    
    print(f"Total samples: {len(df_combined)}")
    
    # Create labels based on dataset source
    # For Normal + Ringan dataset: first 80% Normal, last 20% Ringan
    normal_ringan_count = len(df_normal_ringan)
    normal_berat_count = len(df_normal_berat)
    
    normal_ringan_labels = ['NORMAL'] * int(0.8 * normal_ringan_count) + ['RINGAN'] * (normal_ringan_count - int(0.8 * normal_ringan_count))
    normal_berat_labels = ['NORMAL'] * int(0.8 * normal_berat_count) + ['BERAT'] * (normal_berat_count - int(0.8 * normal_berat_count))
    
    df_normal_ringan['true_label'] = normal_ringan_labels
    df_normal_berat['true_label'] = normal_berat_labels
    
    df_combined = pd.concat([df_normal_ringan, df_normal_berat], ignore_index=True)
    
    print("Label distribution:")
    print(df_combined['true_label'].value_counts())
    
    # Prepare features
    if 'PC1_Source' in df_combined.columns and 'PC2_Source' in df_combined.columns:
        print("Using existing PCA features...")
        X_pca = df_combined[['PC1_Source', 'PC2_Source']].dropna()
        X_raw = df_combined[['X', 'Y', 'Z']].dropna()
        
        # Train models
        scaler = StandardScaler()
        scaler.fit(X_raw)
        
        pca = PCA(n_components=2)
        pca.fit(scaler.transform(X_raw))
        
        iso_forest = IsolationForest(contamination='auto', random_state=42)
        iso_forest.fit(X_pca)
    else:
        print("Computing PCA features...")
        X_raw = df_combined[['X', 'Y', 'Z']].dropna()
        
        scaler = StandardScaler()
        X_scaled = scaler.fit_transform(X_raw)
        
        pca = PCA(n_components=2)
        X_pca = pca.fit_transform(X_scaled)
        
        iso_forest = IsolationForest(contamination='auto', random_state=42)
        iso_forest.fit(X_pca)
    
    # Evaluate predictions
    print("Evaluating predictions...")
    predictions = []
    true_labels = []
    
    for idx, row in df_combined.iterrows():
        if pd.isna(row['X']) or pd.isna(row['Y']) or pd.isna(row['Z']):
            continue
            
        # Extract features
        if 'PC1_Source' in row and 'PC2_Source' in row:
            pc1, pc2 = row['PC1_Source'], row['PC2_Source']
        else:
            raw_data = np.array([[row['X'], row['Y'], row['Z']]])
            scaled_data = scaler.transform(raw_data)
            pca_data = pca.transform(scaled_data)
            pc1, pc2 = pca_data[0, 0], pca_data[0, 1]
        
        # Calculate RMS for classification
        rms_x, rms_y, rms_z = abs(row['X']), abs(row['Y']), abs(row['Z'])
        
        # Classify
        feature_vector = np.array([[pc1, pc2]])
        anomaly_score = iso_forest.decision_function(feature_vector)[0]
        is_anomaly = iso_forest.predict(feature_vector)[0]
        
        # Classification logic
        if is_anomaly == -1:  # Anomaly detected
            if rms_x > 2.0 or rms_y > 2.0 or rms_z > 2.0:
                predicted_label = "BERAT"
            else:
                predicted_label = "RINGAN"
        else:
            predicted_label = "NORMAL"
        
        predictions.append(predicted_label)
        true_labels.append(row['true_label'])
    
    # Calculate accuracy
    accuracy = accuracy_score(true_labels, predictions)
    
    print("\n" + "=" * 40)
    print("EVALUATION RESULTS")
    print("=" * 40)
    print(f"Overall Accuracy: {accuracy:.4f} ({accuracy*100:.2f}%)")
    
    # Detailed classification report
    print("\nDetailed Classification Report:")
    print(classification_report(true_labels, predictions, zero_division=0))
    
    # Per-class accuracy
    print("\nPer-class Accuracy:")
    for label in ['NORMAL', 'RINGAN', 'BERAT']:
        mask = np.array(true_labels) == label
        if np.sum(mask) > 0:
            class_acc = np.mean(np.array(predictions)[mask] == label)
            print(f"  {label}: {class_acc:.4f} ({class_acc*100:.2f}%)")
    
    # Performance assessment
    print("\n" + "=" * 40)
    print("PERFORMANCE ASSESSMENT")
    print("=" * 40)
    
    if accuracy >= 0.9:
        print("✅ EXCELLENT: Model accuracy is very high!")
        print("   - Model is ready for production use")
        print("   - Consider periodic retraining with new data")
    elif accuracy >= 0.8:
        print("✅ GOOD: Model accuracy is good for real-time monitoring.")
        print("   - Model can be deployed with confidence")
        print("   - Monitor performance in production")
    elif accuracy >= 0.7:
        print("⚠️  FAIR: Model accuracy is acceptable but could be improved.")
        print("   - Consider collecting more training data")
        print("   - Review feature extraction methods")
    else:
        print("❌ POOR: Model accuracy needs significant improvement.")
        print("   - Collect more diverse training data")
        print("   - Try different anomaly detection algorithms")
        print("   - Review data preprocessing steps")
    
    return accuracy

if __name__ == "__main__":
    accuracy = quick_evaluate_model()
    print(f"\nFinal Model Accuracy: {accuracy:.4f} ({accuracy*100:.2f}%)") 