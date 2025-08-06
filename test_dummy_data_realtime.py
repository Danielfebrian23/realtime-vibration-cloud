import pandas as pd
import numpy as np
import requests
import time
import json
from datetime import datetime
import threading

def load_dummy_data_for_realtime():
    """
    Load dummy data for real-time testing
    """
    try:
        # Load real-time simulation data
        df = pd.read_excel("Dummy_Data_Based_on_Dataset_Bersih.xlsx", 
                          sheet_name='Scenario4_Realtime_Simulation')
        print(f"✅ Loaded {len(df)} samples for real-time testing")
        return df
    except Exception as e:
        print(f"❌ Error loading dummy data: {e}")
        return None

def simulate_esp32_data(df, server_url="http://localhost:5000/predict"):
    """
    Simulate ESP32 sending data to the server
    """
    print(f"🚀 Starting real-time simulation...")
    print(f"📡 Sending data to: {server_url}")
    print(f"⏱️  Total duration: {len(df) * 0.2:.1f} seconds")
    
    results = []
    
    for i, row in df.iterrows():
        try:
            # Prepare data in ESP32 format
            data = {
                'x': [float(row['X '])],
                'y': [float(row['Y '])],
                'z': [float(row['Z '])],
                'timestamp': int(time.time() * 1000)
            }
            
            # Send to server
            response = requests.post(server_url, json=data, timeout=5)
            
            if response.status_code == 200:
                result = response.json()
                results.append({
                    'sample': i,
                    'condition': row['Source'],
                    'severity': result.get('severity', 'UNKNOWN'),
                    'confidence': result.get('confidence', 0.0),
                    'timestamp': result.get('timestamp', 0)
                })
                
                # Print progress every 100 samples
                if i % 100 == 0:
                    print(f"📊 Sample {i}/{len(df)} - Condition: {row['Source']} -> Severity: {result.get('severity', 'UNKNOWN')} (Confidence: {result.get('confidence', 0.0):.3f})")
            else:
                print(f"❌ Error at sample {i}: HTTP {response.status_code}")
                
        except Exception as e:
            print(f"❌ Error at sample {i}: {e}")
        
        # Simulate 200ms intervals (5 samples per second)
        time.sleep(0.2)
    
    return results

def analyze_results(results):
    """
    Analyze the results of real-time testing
    """
    if not results:
        print("❌ No results to analyze")
        return
    
    print(f"\n📊 Analysis of {len(results)} samples:")
    
    # Convert to DataFrame for analysis
    df_results = pd.DataFrame(results)
    
    # Count predictions by severity
    severity_counts = df_results['severity'].value_counts()
    print(f"\n🎯 Severity Distribution:")
    for severity, count in severity_counts.items():
        percentage = (count / len(df_results)) * 100
        print(f"   {severity}: {count} samples ({percentage:.1f}%)")
    
    # Analyze confidence
    print(f"\n📈 Confidence Statistics:")
    print(f"   Mean: {df_results['confidence'].mean():.3f}")
    print(f"   Std: {df_results['confidence'].std():.3f}")
    print(f"   Min: {df_results['confidence'].min():.3f}")
    print(f"   Max: {df_results['confidence'].max():.3f}")
    
    # Analyze by condition
    print(f"\n🔍 Analysis by Original Condition:")
    for condition in df_results['condition'].unique():
        subset = df_results[df_results['condition'] == condition]
        print(f"\n   {condition}:")
        print(f"     Samples: {len(subset)}")
        print(f"     Mean Confidence: {subset['confidence'].mean():.3f}")
        print(f"     Severity Distribution:")
        for severity, count in subset['severity'].value_counts().items():
            percentage = (count / len(subset)) * 100
            print(f"       {severity}: {count} ({percentage:.1f}%)")
    
    return df_results

def save_results_to_csv(results, filename="realtime_test_results.csv"):
    """
    Save test results to CSV file
    """
    if results:
        df_results = pd.DataFrame(results)
        df_results.to_csv(filename, index=False)
        print(f"\n✅ Results saved to: {filename}")
        return filename
    return None

def test_offline_classification():
    """
    Test the classification algorithm offline with dummy data
    """
    print("\n🔬 Testing offline classification...")
    
    try:
        # Load training data
        df_training = pd.read_excel("Dummy_Data_Based_on_Dataset_Bersih.xlsx", 
                                  sheet_name='Scenario3_Mixed_Training')
        
        # Load test data
        df_test = pd.read_excel("Dummy_Data_Based_on_Dataset_Bersih.xlsx", 
                               sheet_name='Scenario4_Realtime_Simulation')
        
        print(f"📊 Training data: {len(df_training)} samples")
        print(f"📊 Test data: {len(df_test)} samples")
        
        # Simple statistical analysis
        print(f"\n📈 Statistical Analysis:")
        for condition in df_test['Source'].unique():
            subset = df_test[df_test['Source'] == condition]
            print(f"\n   {condition}:")
            print(f"     X: {subset['X '].mean():.3f} ± {subset['X '].std():.3f}")
            print(f"     Y: {subset['Y '].mean():.3f} ± {subset['Y '].std():.3f}")
            print(f"     Z: {subset['Z '].mean():.3f} ± {subset['Z '].std():.3f}")
        
        return True
        
    except Exception as e:
        print(f"❌ Error in offline testing: {e}")
        return False

def main():
    """
    Main function to test dummy data with real-time system
    """
    print("🧪 Testing Dummy Data with Real-Time System")
    print("=" * 50)
    
    # Test offline classification first
    test_offline_classification()
    
    # Load dummy data
    df = load_dummy_data_for_realtime()
    if df is None:
        print("❌ Could not load dummy data")
        return
    
    # Check if server is running
    try:
        response = requests.get("http://localhost:5000/status", timeout=5)
        if response.status_code == 200:
            print("✅ Server is running")
        else:
            print("⚠️  Server responded but with error")
            return
    except Exception as e:
        print(f"❌ Server not running: {e}")
        print("💡 Please start the real-time server first:")
        print("   python realtime_vibration_server.py")
        return
    
    # Start real-time simulation
    print(f"\n🎯 Starting real-time simulation...")
    results = simulate_esp32_data(df)
    
    # Analyze results
    if results:
        analyze_results(results)
        save_results_to_csv(results)
        
        print(f"\n✅ Testing completed!")
        print(f"📊 Processed {len(results)} samples")
        print(f"💡 Check 'realtime_test_results.csv' for detailed results")
    else:
        print(f"❌ No results obtained")

if __name__ == "__main__":
    main() 