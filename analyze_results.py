import pandas as pd
import numpy as np

# Load results
df = pd.read_csv('model_evaluation_details.csv')

print("=" * 60)
print("MODEL EVALUATION RESULTS ANALYSIS")
print("=" * 60)

# Overall accuracy
overall_accuracy = (df['True_Label'] == df['Predicted_Label']).mean()
print(f"Overall Accuracy: {overall_accuracy:.4f} ({overall_accuracy*100:.2f}%)")

print("\n" + "=" * 40)
print("DETAILED ANALYSIS")
print("=" * 40)

# Per-class accuracy
print("\nPer-Class Accuracy:")
for label in ['NORMAL', 'RINGAN', 'BERAT']:
    mask = df['True_Label'] == label
    if mask.sum() > 0:
        acc = (df.loc[mask, 'True_Label'] == df.loc[mask, 'Predicted_Label']).mean()
        print(f"  {label}: {acc:.4f} ({acc*100:.2f}%) - {mask.sum()} samples")

# Confusion matrix
print("\nConfusion Matrix:")
confusion = pd.crosstab(df['True_Label'], df['Predicted_Label'], margins=True)
print(confusion)

# Confidence analysis
print("\nConfidence Analysis:")
print(f"  Mean Confidence: {df['Confidence'].mean():.4f}")
print(f"  Std Confidence: {df['Confidence'].std():.4f}")
print(f"  Min Confidence: {df['Confidence'].min():.4f}")
print(f"  Max Confidence: {df['Confidence'].max():.4f}")

# Confidence by class
print("\nConfidence by True Label:")
for label in ['NORMAL', 'RINGAN', 'BERAT']:
    mask = df['True_Label'] == label
    if mask.sum() > 0:
        conf_mean = df.loc[mask, 'Confidence'].mean()
        conf_std = df.loc[mask, 'Confidence'].std()
        print(f"  {label}: {conf_mean:.4f} ± {conf_std:.4f}")

# Error analysis
print("\nError Analysis:")
errors = df[df['True_Label'] != df['Predicted_Label']]
print(f"  Total Errors: {len(errors)}")
print(f"  Error Rate: {len(errors)/len(df):.4f} ({len(errors)/len(df)*100:.2f}%)")

if len(errors) > 0:
    print("\nError Patterns:")
    error_patterns = errors.groupby(['True_Label', 'Predicted_Label']).size()
    for (true, pred), count in error_patterns.items():
        print(f"  {true} → {pred}: {count} errors")

# Performance assessment
print("\n" + "=" * 40)
print("PERFORMANCE ASSESSMENT")
print("=" * 40)

if overall_accuracy >= 0.9:
    print("✅ EXCELLENT: Model accuracy is very high!")
    print("   - Model is ready for production use")
    print("   - Consider periodic retraining with new data")
elif overall_accuracy >= 0.8:
    print("✅ GOOD: Model accuracy is good for real-time monitoring.")
    print("   - Model can be deployed with confidence")
    print("   - Monitor performance in production")
elif overall_accuracy >= 0.7:
    print("⚠️  FAIR: Model accuracy is acceptable but could be improved.")
    print("   - Consider collecting more training data")
    print("   - Review feature extraction methods")
else:
    print("❌ POOR: Model accuracy needs significant improvement.")
    print("   - Collect more diverse training data")
    print("   - Try different anomaly detection algorithms")

print(f"\nFinal Assessment: Model accuracy is {overall_accuracy*100:.1f}%") 