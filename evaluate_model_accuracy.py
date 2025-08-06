import pandas as pd
import numpy as np
from sklearn.ensemble import IsolationForest
from sklearn.decomposition import PCA
from sklearn.preprocessing import StandardScaler
from sklearn.metrics import confusion_matrix, accuracy_score, precision_recall_fscore_support, classification_report
import matplotlib.pyplot as plt
import seaborn as sns
from datetime import datetime

def load_and_prepare_data():
    """Load and prepare datasets for evaluation"""
    print("Loading datasets...")
    
    # Load datasets
    df_normal_ringan = pd.read_excel("Dataset PCA (Normal 80 + Ringan 20).xlsx")
    df_normal_berat = pd.read_excel("Dataset PCA (Normal 80 + Berat 20).xlsx")
    
    # Combine datasets
    df_combined = pd.concat([df_normal_ringan, df_normal_berat], ignore_index=True)
    df_combined.columns = df_combined.columns.str.strip()
    
    print(f"Combined dataset shape: {df_combined.shape}")
    print(f"Columns: {list(df_combined.columns)}")
    
    # Check Source column values
    if 'Source' in df_combined.columns:
        print(f"Unique values in Source column: {df_combined['Source'].unique()}")
        print(f"Source column value counts:")
        print(df_combined['Source'].value_counts())
        
        # Create labels based on Source column
        label_mapping = {}
        for value in df_combined['Source'].unique():
            if pd.notna(value):
                if 'normal' in str(value).lower():
                    label_mapping[value] = 'NORMAL'
                elif 'ringan' in str(value).lower():
                    label_mapping[value] = 'RINGAN'
                elif 'berat' in str(value).lower():
                    label_mapping[value] = 'BERAT'
                else:
                    # Default mapping for unknown values
                    label_mapping[value] = 'NORMAL'
        
        print(f"Label mapping: {label_mapping}")
        df_combined['true_label'] = df_combined['Source'].map(label_mapping)
        
        # Remove rows with unknown labels
        df_combined = df_combined.dropna(subset=['true_label'])
        
        print(f"Final label distribution:")
        print(df_combined['true_label'].value_counts())
        
        return df_combined
    else:
        print("Warning: 'Source' column not found. Using manual labeling...")
        # Manual labeling based on dataset names
        normal_ringan_count = len(df_normal_ringan)
        normal_berat_count = len(df_normal_berat)
        
        # Assume first 80% of each dataset is Normal, rest are the respective anomaly
        df_normal_ringan['true_label'] = ['NORMAL'] * int(0.8 * normal_ringan_count) + ['RINGAN'] * (normal_ringan_count - int(0.8 * normal_ringan_count))
        df_normal_berat['true_label'] = ['NORMAL'] * int(0.8 * normal_berat_count) + ['BERAT'] * (normal_berat_count - int(0.8 * normal_berat_count))
        
        df_combined = pd.concat([df_normal_ringan, df_normal_berat], ignore_index=True)
        print(f"Manual label distribution:")
        print(df_combined['true_label'].value_counts())
        
        return df_combined

def train_evaluation_models(df):
    """Train models using the same approach as the server"""
    print("Training evaluation models...")
    
    # Prepare features - use existing PCA values if available
    if 'PC1_Source' in df.columns and 'PC2_Source' in df.columns:
        print("Using existing PCA features from dataset...")
        X_pca = df[['PC1_Source', 'PC2_Source']].dropna()
        print(f"PCA features shape: {X_pca.shape}")
        
        # For raw features, use X, Y, Z if available
        if all(col in df.columns for col in ['X', 'Y', 'Z']):
            X_raw = df[['X', 'Y', 'Z']].dropna()
            print(f"Raw features shape: {X_raw.shape}")
            
            # Train scaler and PCA
            scaler = StandardScaler()
            X_scaled = scaler.fit_transform(X_raw)
            
            pca = PCA(n_components=2)
            pca.fit(X_scaled)
        else:
            # Create dummy scaler and PCA if raw features not available
            scaler = StandardScaler()
            pca = PCA(n_components=2)
            print("Warning: Raw X, Y, Z features not available, using dummy models")
    else:
        print("PCA features not found, using raw X, Y, Z features...")
        X_raw = df[['X', 'Y', 'Z']].dropna()
        print(f"Raw features shape: {X_raw.shape}")
        
        # Train scaler and PCA
        scaler = StandardScaler()
        X_scaled = scaler.fit_transform(X_raw)
        
        pca = PCA(n_components=2)
        pca.fit(X_scaled)
        
        # Create PCA features for evaluation
        X_pca = pca.transform(X_scaled)
        X_pca = pd.DataFrame(X_pca, columns=['PC1_Source', 'PC2_Source'])
    
    # Train Isolation Forest
    iso_forest = IsolationForest(contamination='auto', random_state=42)
    iso_forest.fit(X_pca)
    
    print("Models trained successfully!")
    return scaler, pca, iso_forest

def classify_vibration_evaluation(features, iso_forest_model):
    """Classify vibration using the same logic as the server"""
    try:
        # Prepare features for prediction
        feature_vector = np.array([
            features['PC1'], features['PC2']
        ]).reshape(1, -1)
        
        # Predict anomaly score
        anomaly_score = iso_forest_model.decision_function(feature_vector)[0]
        is_anomaly = iso_forest_model.predict(feature_vector)[0]
        
        # Classify based on anomaly score and statistical features
        if is_anomaly == -1:  # Anomaly detected
            if features['rms_x'] > 2.0 or features['rms_y'] > 2.0 or features['rms_z'] > 2.0:
                severity = "BERAT"
                confidence = min(abs(anomaly_score) * 0.8, 0.95)
            else:
                severity = "RINGAN"
                confidence = min(abs(anomaly_score) * 0.6, 0.85)
        else:
            severity = "NORMAL"
            confidence = 1.0 - abs(anomaly_score)
            
        return severity, confidence
    except Exception as e:
        print(f"Error in classification: {e}")
        return "ERROR", 0.0

def extract_features_evaluation(row_data, scaler_model, pca_model):
    """Extract features from single row data"""
    try:
        # Calculate statistical features
        features = {
            'mean_x': row_data['X'],
            'mean_y': row_data['Y'], 
            'mean_z': row_data['Z'],
            'std_x': 0,  # Single sample, no std
            'std_y': 0,
            'std_z': 0,
            'max_x': row_data['X'],
            'max_y': row_data['Y'],
            'max_z': row_data['Z'],
            'min_x': row_data['X'],
            'min_y': row_data['Y'],
            'min_z': row_data['Z'],
            'rms_x': abs(row_data['X']),
            'rms_y': abs(row_data['Y']),
            'rms_z': abs(row_data['Z'])
        }
        
        # Use existing PCA values if available, otherwise compute
        if 'PC1_Source' in row_data and 'PC2_Source' in row_data:
            features['PC1'] = row_data['PC1_Source']
            features['PC2'] = row_data['PC2_Source']
        elif scaler_model and pca_model:
            # Apply PCA transformation
            raw_data = np.array([[row_data['X'], row_data['Y'], row_data['Z']]])
            scaled_data = scaler_model.transform(raw_data)
            pca_features = pca_model.transform(scaled_data)
            features['PC1'] = pca_features[0, 0]
            features['PC2'] = pca_features[0, 1]
        else:
            # Fallback values
            features['PC1'] = 0
            features['PC2'] = 0
            
        return features
    except Exception as e:
        print(f"Error extracting features: {e}")
        return None

def evaluate_model_accuracy():
    """Main evaluation function"""
    print("=" * 60)
    print("MODEL ACCURACY EVALUATION")
    print("=" * 60)
    print(f"Evaluation started at: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print()
    
    # Load and prepare data
    df = load_and_prepare_data()
    
    # Check if we have enough data
    if len(df) == 0:
        print("❌ ERROR: No valid data found for evaluation!")
        return 0, 0, 0, 0
    
    # Train models
    scaler, pca, iso_forest = train_evaluation_models(df)
    
    # Evaluate each sample
    predictions = []
    true_labels = []
    confidences = []
    
    print("Evaluating predictions...")
    for idx, row in df.iterrows():
        if pd.isna(row['X']) or pd.isna(row['Y']) or pd.isna(row['Z']):
            continue
            
        # Extract features
        features = extract_features_evaluation(row, scaler, pca)
        if features is None:
            continue
            
        # Classify
        predicted_label, confidence = classify_vibration_evaluation(features, iso_forest)
        
        predictions.append(predicted_label)
        true_labels.append(row['true_label'])
        confidences.append(confidence)
    
    # Check if we have predictions
    if len(predictions) == 0:
        print("❌ ERROR: No predictions generated!")
        return 0, 0, 0, 0
    
    # Calculate metrics
    print("\n" + "=" * 40)
    print("EVALUATION RESULTS")
    print("=" * 40)
    
    # Overall accuracy
    accuracy = accuracy_score(true_labels, predictions)
    print(f"Overall Accuracy: {accuracy:.4f} ({accuracy*100:.2f}%)")
    
    # Detailed metrics
    precision, recall, f1, support = precision_recall_fscore_support(
        true_labels, predictions, average='weighted', zero_division=0
    )
    
    print(f"Weighted Precision: {precision:.4f}")
    print(f"Weighted Recall: {recall:.4f}")
    print(f"Weighted F1-Score: {f1:.4f}")
    
    # Per-class metrics
    print("\nPer-class metrics:")
    class_report = classification_report(true_labels, predictions, zero_division=0)
    print(class_report)
    
    # Confusion matrix
    cm = confusion_matrix(true_labels, predictions, labels=['NORMAL', 'RINGAN', 'BERAT'])
    
    # Plot confusion matrix
    plt.figure(figsize=(12, 10))
    
    plt.subplot(2, 2, 1)
    sns.heatmap(cm, annot=True, fmt='d', cmap='Blues', 
                xticklabels=['NORMAL', 'RINGAN', 'BERAT'],
                yticklabels=['NORMAL', 'RINGAN', 'BERAT'])
    plt.title('Confusion Matrix')
    plt.ylabel('True Label')
    plt.xlabel('Predicted Label')
    
    # Plot confidence distribution
    plt.subplot(2, 2, 2)
    confidence_df = pd.DataFrame({
        'True_Label': true_labels,
        'Confidence': confidences,
        'Predicted_Label': predictions
    })
    
    for label in ['NORMAL', 'RINGAN', 'BERAT']:
        label_data = confidence_df[confidence_df['True_Label'] == label]['Confidence']
        if len(label_data) > 0:
            plt.hist(label_data, alpha=0.7, label=label, bins=20)
    
    plt.xlabel('Confidence Score')
    plt.ylabel('Frequency')
    plt.title('Confidence Distribution by True Label')
    plt.legend()
    
    # Plot accuracy by class
    plt.subplot(2, 2, 3)
    class_accuracy = {}
    for label in ['NORMAL', 'RINGAN', 'BERAT']:
        mask = np.array(true_labels) == label
        if np.sum(mask) > 0:
            class_acc = np.mean(np.array(predictions)[mask] == label)
            class_accuracy[label] = class_acc
    
    if class_accuracy:
        classes = list(class_accuracy.keys())
        accuracies = list(class_accuracy.values())
        plt.bar(classes, accuracies, color=['green', 'orange', 'red'])
        plt.ylabel('Accuracy')
        plt.title('Accuracy by Class')
        plt.ylim(0, 1)
        
        # Add accuracy values on bars
        for i, v in enumerate(accuracies):
            plt.text(i, v + 0.01, f'{v:.3f}', ha='center', va='bottom')
    
    # Plot prediction distribution
    plt.subplot(2, 2, 4)
    pred_counts = pd.Series(predictions).value_counts()
    plt.pie(pred_counts.values, labels=pred_counts.index, autopct='%1.1f%%')
    plt.title('Prediction Distribution')
    
    plt.tight_layout()
    plt.savefig('model_evaluation_results.png', dpi=300, bbox_inches='tight')
    plt.show()
    
    # Save detailed results
    results_df = pd.DataFrame({
        'True_Label': true_labels,
        'Predicted_Label': predictions,
        'Confidence': confidences
    })
    
    results_df.to_csv('model_evaluation_details.csv', index=False)
    
    print(f"\nDetailed results saved to 'model_evaluation_details.csv'")
    print(f"Visualization saved to 'model_evaluation_results.png'")
    
    # Summary statistics
    print("\n" + "=" * 40)
    print("SUMMARY STATISTICS")
    print("=" * 40)
    print(f"Total samples evaluated: {len(predictions)}")
    print(f"Average confidence: {np.mean(confidences):.4f}")
    print(f"Confidence std: {np.std(confidences):.4f}")
    
    # Error analysis
    errors = results_df[results_df['True_Label'] != results_df['Predicted_Label']]
    print(f"Total errors: {len(errors)}")
    
    if len(errors) > 0:
        print("\nError analysis:")
        error_patterns = errors.groupby(['True_Label', 'Predicted_Label']).size()
        print(error_patterns)
    
    return accuracy, precision, recall, f1

if __name__ == "__main__":
    # Run evaluation
    accuracy, precision, recall, f1 = evaluate_model_accuracy()
    
    print("\n" + "=" * 60)
    print("EVALUATION COMPLETE")
    print("=" * 60)
    print(f"Final Model Performance:")
    print(f"  Accuracy: {accuracy:.4f} ({accuracy*100:.2f}%)")
    print(f"  Precision: {precision:.4f}")
    print(f"  Recall: {recall:.4f}")
    print(f"  F1-Score: {f1:.4f}")
    
    # Performance assessment
    if accuracy >= 0.9:
        print("\n✅ EXCELLENT: Model accuracy is very high!")
    elif accuracy >= 0.8:
        print("\n✅ GOOD: Model accuracy is good for real-time monitoring.")
    elif accuracy >= 0.7:
        print("\n⚠️  FAIR: Model accuracy is acceptable but could be improved.")
    else:
        print("\n❌ POOR: Model accuracy needs significant improvement.")
    
    print("\nRecommendations:")
    if accuracy < 0.8:
        print("- Consider collecting more training data")
        print("- Try different anomaly detection algorithms")
        print("- Adjust feature extraction methods")
        print("- Review data preprocessing steps")
    else:
        print("- Model is ready for real-time deployment")
        print("- Consider periodic retraining with new data")
        print("- Monitor performance in production") 