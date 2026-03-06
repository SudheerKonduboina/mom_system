import requests
import json
import os

def test_analysis():
    url = "http://127.0.0.1:8000/analyze-meeting"
    
    # Path to an existing audio file in storage for testing
    # Using one from the storage directory identified earlier
    storage_path = r"c:\Users\kondu\Downloads\mom_system\backend\storage"
    files = [f for f in os.listdir(storage_path) if f.endswith(".webm")]
    
    if not files:
        print("No .webm files found in storage to test with.")
        return

    test_file = os.path.join(storage_path, files[0])
    print(f"Testing with file: {test_file}")

    with open(test_file, "rb") as f:
        files_payload = {"file": ("test.webm", f, "audio/webm")}
        data_payload = {"attendance_events": json.dumps([{"name": "Test User", "at": "2026-02-23T15:00:00Z", "type": "PARTICIPANT_JOIN"}])}
        
        try:
            response = requests.post(url, files=files_payload, data=data_payload)
            if response.status_code == 200:
                print("✅ Analysis successful!")
                print(json.dumps(response.json(), indent=2))
            else:
                print(f"❌ Analysis failed with status {response.status_code}")
                print(response.text)
        except Exception as e:
            print(f"❌ Error: {e}")

if __name__ == "__main__":
    test_analysis()
