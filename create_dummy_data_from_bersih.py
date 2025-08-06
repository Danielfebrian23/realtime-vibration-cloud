import pandas as pd
import numpy as np
from datetime import datetime, timedelta
import random

def analyze_original_data():
    """
    Analyze the original Dataset_Bersih.xlsx to understand data characteristics
    """
    print("🔍 Analyzing original Dataset_Bersih.xlsx...")
    
    # Load original data
    df_original = pd.read_excel("Dataset_Bersih.xlsx")
    
    # Analyze characteristics per condition
    conditions = df_original['Source'].unique()
    characteristics = {}
    
    for condition in conditions:
        subset = df_original[df_original['Source'] == condition]
        characteristics[condition] = {
            'X_mean': subset['X '].mean(),
            'X_std': subset['X '].std(),
            'Y_mean': subset['Y '].mean(),
            'Y_std': subset['Y '].std(),
            'Z_mean': subset['Z '].mean(),
            'Z_std': subset['Z '].std(),
            'count': len(subset)
        }
        print(f"\n📊 {condition}:")
        print(f"   X: {characteristics[condition]['X_mean']:.4f} ± {characteristics[condition]['X_std']:.4f}")
        print(f"   Y: {characteristics[condition]['Y_mean']:.4f} ± {characteristics[condition]['Y_std']:.4f}")
        print(f"   Z: {characteristics[condition]['Z_mean']:.4f} ± {characteristics[condition]['Z_std']:.4f}")
        print(f"   Count: {characteristics[condition]['count']}")
    
    return characteristics

def generate_dummy_data_based_on_original(characteristics):
    """
    Generate dummy data based on original data characteristics
    """
    print("\n🚀 Generating dummy data based on original characteristics...")
    
    all_data = []
    start_time = datetime.now()
    
    # Generate data for each condition
    for condition, params in characteristics.items():
        print(f"Generating {condition} data...")
        
        # Generate samples based on original count
        samples_count = params['count']
        
        for i in range(samples_count):
            # Generate timestamp (every 100ms)
            timestamp = start_time + timedelta(milliseconds=i*100)
            
            # Generate vibration data based on original characteristics
            x = np.random.normal(params['X_mean'], params['X_std'])
            y = np.random.normal(params['Y_mean'], params['Y_std'])
            z = np.random.normal(params['Z_mean'], params['Z_std'])
            
            # Add some realistic variations
            if 'Ringan' in condition:
                # Add slight periodic variation for ringan
                x += 0.1 * np.sin(i * 0.05)
                y += 0.08 * np.cos(i * 0.04)
            elif 'Berat' in condition:
                # Add more pronounced variation for berat
                x += 0.3 * np.sin(i * 0.1)
                y += 0.25 * np.cos(i * 0.08)
                z += 0.2 * np.sin(i * 0.06)
            
            # Add occasional outliers (5% chance)
            if random.random() < 0.05:
                x += np.random.normal(0, params['X_std'] * 2)
                y += np.random.normal(0, params['Y_std'] * 2)
                z += np.random.normal(0, params['Z_std'] * 2)
            
            all_data.append({
                'X ': round(x, 4),
                'Y ': round(y, 4),
                'Z ': round(z, 4),
                'Source': condition
            })
    
    # Create DataFrame
    df = pd.DataFrame(all_data)
    
    # Shuffle the data to mix conditions
    df = df.sample(frac=1, random_state=42).reset_index(drop=True)
    
    return df

def create_test_scenarios(df):
    """
    Create different test scenarios for real-time testing
    """
    scenarios = {}
    
    # Scenario 1: Normal to Ringan transition
    print("Creating Scenario 1: Normal to Ringan transition...")
    normal_data = df[df['Source'] == 'Suprax(Normal)'].head(1000)
    ringan_data = df[df['Source'] == 'BearingAus(Ringan)'].head(500)
    scenario1 = pd.concat([normal_data, ringan_data], ignore_index=True)
    scenarios['Scenario1_Normal_to_Ringan'] = scenario1
    
    # Scenario 2: Normal to Berat transition
    print("Creating Scenario 2: Normal to Berat transition...")
    berat_data = df[df['Source'] == 'Axelo(Berat)'].head(500)
    scenario2 = pd.concat([normal_data, berat_data], ignore_index=True)
    scenarios['Scenario2_Normal_to_Berat'] = scenario2
    
    # Scenario 3: Mixed conditions (for training)
    print("Creating Scenario 3: Mixed conditions for training...")
    scenarios['Scenario3_Mixed_Training'] = df
    
    # Scenario 4: Real-time simulation data
    print("Creating Scenario 4: Real-time simulation data...")
    realtime_data = []
    start_time = datetime.now()
    
    # Simulate 5 minutes of data with condition changes
    for i in range(3000):  # 5 minutes * 60 seconds * 10 samples per second
        timestamp = start_time + timedelta(milliseconds=i*200)  # 200ms intervals
        
        # Change conditions over time
        if i < 1000:  # First 3.3 minutes: Normal
            condition = 'Suprax(Normal)'
            x = np.random.normal(0.0, 0.5)
            y = np.random.normal(0.0, 0.5)
            z = np.random.normal(9.8, 0.3)
        elif i < 2000:  # Next 3.3 minutes: Ringan
            condition = 'BearingAus(Ringan)'
            x = np.random.normal(0.5, 0.8)
            y = np.random.normal(0.3, 0.7)
            z = np.random.normal(9.5, 0.6)
        else:  # Last 3.3 minutes: Berat
            condition = 'Axelo(Berat)'
            x = np.random.normal(1.2, 1.5)
            y = np.random.normal(0.8, 1.2)
            z = np.random.normal(8.8, 1.0)
        
        realtime_data.append({
            'X ': round(x, 4),
            'Y ': round(y, 4),
            'Z ': round(z, 4),
            'Source': condition
        })
    
    scenarios['Scenario4_Realtime_Simulation'] = pd.DataFrame(realtime_data)
    
    return scenarios

def save_scenarios_to_excel(scenarios):
    """
    Save all scenarios to Excel file with multiple sheets
    """
    filename = "Dummy_Data_Based_on_Dataset_Bersih.xlsx"
    
    with pd.ExcelWriter(filename, engine='openpyxl') as writer:
        # Save each scenario to a separate sheet
        for scenario_name, data in scenarios.items():
            data.to_excel(writer, sheet_name=scenario_name, index=False)
        
        # Create summary sheet
        summary_data = []
        for scenario_name, data in scenarios.items():
            source_counts = data['Source'].value_counts()
            summary_data.append({
                'Scenario': scenario_name,
                'Total_Samples': len(data),
                'Suprax_Normal': source_counts.get('Suprax(Normal)', 0),
                'BearingAus_Ringan': source_counts.get('BearingAus(Ringan)', 0),
                'Axelo_Berat': source_counts.get('Axelo(Berat)', 0),
                'Duration_Seconds': len(data) * 0.2  # 200ms intervals
            })
        
        summary_df = pd.DataFrame(summary_data)
        summary_df.to_excel(writer, sheet_name='Summary', index=False)
    
    print(f"\n✅ Data saved to: {filename}")
    print(f"📊 Summary of created scenarios:")
    for scenario_name, data in scenarios.items():
        print(f"   {scenario_name}: {len(data)} samples")
    
    return filename

def main():
    """
    Main function to generate dummy data based on Dataset_Bersih.xlsx
    """
    print("🚀 Generating Dummy Data Based on Dataset_Bersih.xlsx")
    print("=" * 60)
    
    # Analyze original data
    characteristics = analyze_original_data()
    
    # Generate dummy data based on original characteristics
    df = generate_dummy_data_based_on_original(characteristics)
    
    # Create test scenarios
    scenarios = create_test_scenarios(df)
    
    # Save to Excel
    filename = save_scenarios_to_excel(scenarios)
    
    print("\n📋 File contains the following sheets:")
    print("   - Scenario1_Normal_to_Ringan: Transition from normal to light anomaly")
    print("   - Scenario2_Normal_to_Berat: Transition from normal to severe anomaly")
    print("   - Scenario3_Mixed_Training: Mixed data for model training")
    print("   - Scenario4_Realtime_Simulation: 5-minute real-time simulation")
    print("   - Summary: Overview of all scenarios")
    
    print(f"\n🎯 Ready for testing! Use '{filename}' with your real-time system.")
    print("\n💡 Usage tips:")
    print("   - Use Scenario4_Realtime_Simulation for real-time testing")
    print("   - Use Scenario3_Mixed_Training for model training")
    print("   - Scenarios 1 & 2 for specific transition testing")
    print("   - Data structure matches your original Dataset_Bersih.xlsx")

if __name__ == "__main__":
    main() 