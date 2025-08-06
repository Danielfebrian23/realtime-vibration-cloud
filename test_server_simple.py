import requests
import json
import time

def test_server():
    """Test the Flask server endpoints"""
    base_url = "http://localhost:5000"
    
    # Test 1: Check server status
    print("Testing server status...")
    try:
        response = requests.get(f"{base_url}/status")
        print(f"Status: {response.status_code}")
        print(f"Response: {response.json()}")
    except Exception as e:
        print(f"Error testing status: {e}")
        return False
    
    # Test 2: Test prediction endpoint with dummy data
    print("\nTesting prediction endpoint...")
    dummy_data = {
        "x": [1.0, 1.1, 1.2, 1.3, 1.4],
        "y": [-10.0, -10.1, -10.2, -10.3, -10.4],
        "z": [1.8, 1.9, 2.0, 2.1, 2.2],
        "timestamp": int(time.time() * 1000)
    }
    
    try:
        response = requests.post(f"{base_url}/predict", 
                               json=dummy_data,
                               headers={'Content-Type': 'application/json'})
        print(f"Prediction Status: {response.status_code}")
        if response.status_code == 200:
            result = response.json()
            print(f"Severity: {result.get('severity')}")
            print(f"Confidence: {result.get('confidence')}")
            print(f"Features: {result.get('features')}")
        else:
            print(f"Error response: {response.text}")
    except Exception as e:
        print(f"Error testing prediction: {e}")
        return False
    
    # Test 3: Clear buffer
    print("\nTesting clear buffer...")
    try:
        response = requests.post(f"{base_url}/clear_buffer")
        print(f"Clear buffer status: {response.status_code}")
    except Exception as e:
        print(f"Error clearing buffer: {e}")
    
    print("\nServer test completed!")
    return True

if __name__ == "__main__":
    print("Starting server test...")
    test_server() 