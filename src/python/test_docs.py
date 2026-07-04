import urllib.request

urls = ["http://localhost:8000/docs", "http://localhost:8000/test", "http://localhost:8000/"]

for url in urls:
    try:
        r = urllib.request.urlopen(url)
        print(f"{url} -> Status: {r.status} ✓")
    except Exception as e:
        print(f"{url} -> Error: {e}")
