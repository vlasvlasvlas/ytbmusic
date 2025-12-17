
import yt_dlp
import json
import sys

# URL from the logs that failed
TEST_URL = "https://www.youtube.com/watch?v=6HKCwYjt5eY&list=PLfpevK0pYncjTQejYqOQ35j5CBxKfBUFz"

def test_extraction():
    ydl_opts = {
        "quiet": False,
        "no_warnings": False,
        "extract_flat": True,  # This is what we use in the app
        "dump_single_json": True,
    }

    print(f"Attempting to extract: {TEST_URL}")
    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(TEST_URL, download=False)
            
            print(f"\nTitle: {info.get('title')}")
            print(f"Type: {info.get('_type')}")
            
            entries = info.get('entries', [])
            if not entries:
                # sometimes it is a generator
                print("Entries is likely a generator or empty, converting to list...")
                entries = list(entries)
            
            print(f"Entries count: {len(entries)}")
            
            if len(entries) > 0:
                print("First entry sample:")
                print(json.dumps(entries[0], indent=2))
            else:
                print("NO ENTRIES FOUND.")
                print("Keys in info dict:", info.keys())

    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    test_extraction()
