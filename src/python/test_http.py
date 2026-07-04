import urllib.request

try:
    response = urllib.request.urlopen("http://localhost:8000/")
    data = response.read()
    print(f"Status Code: {response.status}")
    print("Success! Page loaded.")
except urllib.error.HTTPError as e:
    print(f"HTTP Error: {e.code}")
    print(f"Response: {e.read().decode('utf-8')}")
except Exception as e:
    print(f"Error: {e}")
