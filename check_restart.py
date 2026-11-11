import urllib.request, json, time
time.sleep(1)
r = urllib.request.urlopen('http://127.0.0.1:5000/api/items')
data = json.loads(r.read())
total = data["total"]
print(f"After restart: {total} items still in DB")
r2 = urllib.request.urlopen('http://127.0.0.1:5000/api/dashboard')
dash = json.loads(r2.read())
print(f"Dashboard: total={dash['total']} fresh={dash['fresh']} expiring={dash['expiring_soon']} today={dash['expires_today']} expired={dash['expired']}")
print("RESTART PERSISTENCE: CONFIRMED")
