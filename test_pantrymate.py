"""
PantryMate - Full Integration & Functionality Test Suite
Runs against a live Flask server on http://127.0.0.1:5000
"""
import io
import sys
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')

import urllib.request
import urllib.error
import json
import sqlite3
import os
from datetime import date, timedelta

BASE = "http://127.0.0.1:5000"
DB_PATH = os.path.join(os.path.dirname(__file__), "pantrymate.db")

results = []


def section(title):
    print(f"\n{'=' * 58}")
    print(f"  {title}")
    print(f"{'=' * 58}")


def ok(label, detail=""):
    msg = f"  [PASS] {label}"
    if detail:
        msg += f"  =>  {detail}"
    print(msg)
    results.append(("PASS", label))


def fail(label, detail=""):
    msg = f"  [FAIL] {label}"
    if detail:
        msg += f"  =>  {detail}"
    print(msg)
    results.append(("FAIL", label))


def info(label):
    print(f"  [INFO] {label}")


def api(method, path, payload=None, expected_status=None):
    url = BASE + path
    data = json.dumps(payload).encode() if payload else None
    req = urllib.request.Request(
        url,
        data=data,
        headers={"Content-Type": "application/json"},
        method=method,
    )
    try:
        with urllib.request.urlopen(req) as r:
            status = r.status
            body = json.loads(r.read())
        if expected_status and status != expected_status:
            raise AssertionError(f"Expected HTTP {expected_status}, got {status}")
        return status, body
    except urllib.error.HTTPError as e:
        status = e.code
        body = json.loads(e.read()) if e.fp else {}
        if expected_status and status != expected_status:
            raise AssertionError(
                f"Expected HTTP {expected_status}, got {status}: {body}"
            )
        return status, body


# =============================================================================
# TEST 1 - Flask backend starts & homepage loads
# =============================================================================
section("TEST 1 - Flask backend startup & homepage")

try:
    with urllib.request.urlopen(BASE + "/") as r:
        body = r.read().decode()
    assert r.status == 200
    assert "PantryMate" in body
    ok("GET /  =>  200 OK, HTML contains 'PantryMate'")
except Exception as e:
    fail("GET /  =>  homepage failed", str(e))

# =============================================================================
# TEST 2 - SQLite DB created & table exists
# =============================================================================
section("TEST 2 - SQLite database creation & schema")

try:
    assert os.path.exists(DB_PATH), "pantrymate.db not found"
    ok("pantrymate.db exists on disk", DB_PATH)
except AssertionError as e:
    fail("DB file", str(e))

try:
    conn = sqlite3.connect(DB_PATH)
    cur = conn.execute(
        "SELECT name FROM sqlite_master WHERE type='table' AND name='pantry_items'"
    )
    assert cur.fetchone() is not None, "pantry_items table missing"
    ok("pantry_items table present in DB")

    cols = {row[1] for row in conn.execute("PRAGMA table_info(pantry_items)")}
    expected = {"id", "item_name", "category", "quantity", "unit",
                "purchase_date", "expiry_date", "created_at"}
    missing = expected - cols
    if missing:
        fail("Schema columns", f"Missing: {missing}")
    else:
        ok("All required columns present", ", ".join(sorted(cols)))
    conn.close()
except Exception as e:
    fail("DB schema check", str(e))

# =============================================================================
# TEST 3 - GET /api/dashboard (baseline)
# =============================================================================
section("TEST 3 - GET /api/dashboard")

try:
    status, body = api("GET", "/api/dashboard", expected_status=200)
    for key in ("total", "fresh", "expiring_soon", "expires_today", "expired", "last_updated"):
        assert key in body, f"Missing key: {key}"
    ok("All dashboard keys present", str(body))
except Exception as e:
    fail("GET /api/dashboard", str(e))

# =============================================================================
# TEST 4 - POST /api/items  (add items covering all statuses)
# =============================================================================
section("TEST 4 - POST /api/items  - add items for all statuses")

today = date.today()
items_to_add = [
    {
        "item_name": "Fresh Apple",
        "category": "Fruits",
        "quantity": 6,
        "unit": "pcs",
        "purchase_date": str(today - timedelta(days=2)),
        "expiry_date": str(today + timedelta(days=15)),
        "expected_status": "fresh",
    },
    {
        "item_name": "Expiring Milk",
        "category": "Dairy",
        "quantity": 1,
        "unit": "L",
        "purchase_date": str(today - timedelta(days=5)),
        "expiry_date": str(today + timedelta(days=4)),
        "expected_status": "expiring_soon",
    },
    {
        "item_name": "Todays Yogurt",
        "category": "Dairy",
        "quantity": 2,
        "unit": "pcs",
        "purchase_date": str(today),
        "expiry_date": str(today),
        "expected_status": "expires_today",
    },
    {
        "item_name": "Stale Bread",
        "category": "Bakery",
        "quantity": 1,
        "unit": "pack",
        "purchase_date": str(today - timedelta(days=10)),
        "expiry_date": str(today - timedelta(days=3)),
        "expected_status": "expired",
    },
]

created_ids = {}
for item in items_to_add:
    payload = {k: v for k, v in item.items() if k != "expected_status"}
    try:
        status, body = api("POST", "/api/items", payload, expected_status=201)
        assert "id" in body
        assert body["status"] == item["expected_status"], (
            f"Expected status '{item['expected_status']}', got '{body['status']}'"
        )
        created_ids[item["item_name"]] = body["id"]
        ok(
            f"POST /api/items  '{item['item_name']}'",
            f"id={body['id']}  status={body['status']}  days_remaining={body['days_remaining']}",
        )
    except Exception as e:
        fail(f"POST /api/items  '{item['item_name']}'", str(e))

# Validation: missing item_name
try:
    status, body = api("POST", "/api/items",
                       {"expiry_date": str(today + timedelta(days=5))},
                       expected_status=422)
    ok("POST /api/items  missing item_name  =>  422", body.get("error", ""))
except Exception as e:
    fail("POST /api/items  validation (missing name)", str(e))

# Validation: missing expiry_date
try:
    status, body = api("POST", "/api/items",
                       {"item_name": "No Expiry"},
                       expected_status=422)
    ok("POST /api/items  missing expiry_date  =>  422", body.get("error", ""))
except Exception as e:
    fail("POST /api/items  validation (missing expiry)", str(e))

# =============================================================================
# TEST 5 - GET /api/items  (display & filter)
# =============================================================================
section("TEST 5 - GET /api/items  - display, search & filter")

try:
    status, body = api("GET", "/api/items", expected_status=200)
    assert "items" in body and "total" in body
    assert body["total"] >= 4
    ok(f"GET /api/items  =>  {body['total']} item(s) returned")
except Exception as e:
    fail("GET /api/items  (all)", str(e))

# Search by name
try:
    status, body = api("GET", "/api/items?search=apple", expected_status=200)
    assert all("apple" in i["item_name"].lower() for i in body["items"])
    ok(f"GET /api/items?search=apple  =>  {body['total']} match(es)")
except Exception as e:
    fail("GET /api/items?search=apple", str(e))

# Filter by category
try:
    status, body = api("GET", "/api/items?category=Dairy", expected_status=200)
    assert all(i["category"] == "Dairy" for i in body["items"])
    ok(f"GET /api/items?category=Dairy  =>  {body['total']} item(s)")
except Exception as e:
    fail("GET /api/items?category=Dairy", str(e))

# Filter by status - expired
try:
    status, body = api("GET", "/api/items?status=expired", expected_status=200)
    assert all(i["status"] == "expired" for i in body["items"])
    ok(f"GET /api/items?status=expired  =>  {body['total']} item(s)")
except Exception as e:
    fail("GET /api/items?status=expired", str(e))

# Filter by status - fresh
try:
    status, body = api("GET", "/api/items?status=fresh", expected_status=200)
    assert all(i["status"] == "fresh" for i in body["items"])
    ok(f"GET /api/items?status=fresh  =>  {body['total']} item(s)")
except Exception as e:
    fail("GET /api/items?status=fresh", str(e))

# =============================================================================
# TEST 6 - PUT /api/items/<id>  (edit)
# =============================================================================
section("TEST 6 - PUT /api/items/<id>  - edit item")

edit_id = created_ids.get("Fresh Apple")
if edit_id:
    try:
        new_expiry = str(today + timedelta(days=3))  # will become expiring_soon
        payload = {
            "item_name": "Fresh Apple (edited)",
            "category": "Fruits",
            "quantity": 10,
            "unit": "pcs",
            "purchase_date": str(today - timedelta(days=2)),
            "expiry_date": new_expiry,
        }
        status, body = api("PUT", f"/api/items/{edit_id}", payload, expected_status=200)
        assert body["item_name"] == "Fresh Apple (edited)"
        assert body["quantity"] == 10.0
        assert body["status"] == "expiring_soon"
        ok(
            f"PUT /api/items/{edit_id}  updated name, qty, expiry",
            f"new_status={body['status']}  days={body['days_remaining']}",
        )
    except Exception as e:
        fail(f"PUT /api/items/{edit_id}", str(e))

    # 404 check
    try:
        status, body = api("PUT", "/api/items/99999", {
            "item_name": "Ghost",
            "expiry_date": str(today + timedelta(days=5))
        }, expected_status=404)
        ok("PUT /api/items/99999  =>  404 not found", body.get("error", ""))
    except Exception as e:
        fail("PUT /api/items/99999  (404 check)", str(e))
else:
    fail("PUT test skipped - Fresh Apple id not found")

# =============================================================================
# TEST 7 - DELETE /api/items/<id>
# =============================================================================
section("TEST 7 - DELETE /api/items/<id>")

try:
    _, new_item = api("POST", "/api/items", {
        "item_name": "Throwaway Item",
        "expiry_date": str(today + timedelta(days=20)),
    }, expected_status=201)
    del_id = new_item["id"]

    status, body = api("DELETE", f"/api/items/{del_id}", expected_status=200)
    assert "deleted" in body.get("message", "").lower()
    ok(f"DELETE /api/items/{del_id}  =>  200 OK", body.get("message", ""))

    _, all_items = api("GET", "/api/items")
    ids_left = [i["id"] for i in all_items["items"]]
    assert del_id not in ids_left
    ok("Deleted item is absent from subsequent GET /api/items")
except Exception as e:
    fail("DELETE /api/items/<id>", str(e))

# 404 check
try:
    status, body = api("DELETE", "/api/items/88888", expected_status=404)
    ok("DELETE /api/items/88888  =>  404", body.get("error", ""))
except Exception as e:
    fail("DELETE /api/items/88888  (404 check)", str(e))

# =============================================================================
# TEST 8 - PATCH /api/items/<id>/consume
# =============================================================================
section("TEST 8 - PATCH /api/items/<id>/consume")

try:
    _, new_item = api("POST", "/api/items", {
        "item_name": "Consume Me",
        "category": "Snacks",
        "quantity": 1,
        "unit": "pcs",
        "expiry_date": str(today + timedelta(days=10)),
    }, expected_status=201)
    con_id = new_item["id"]

    status, body = api("PATCH", f"/api/items/{con_id}/consume", expected_status=200)
    assert "consumed" in body.get("message", "").lower()
    ok(f"PATCH /api/items/{con_id}/consume  =>  200 OK", body.get("message", ""))

    _, all_items = api("GET", "/api/items")
    ids_left = [i["id"] for i in all_items["items"]]
    assert con_id not in ids_left
    ok("Consumed item is absent from subsequent GET /api/items")
except Exception as e:
    fail("PATCH /api/items/<id>/consume", str(e))

# 404 check
try:
    status, body = api("PATCH", "/api/items/77777/consume", expected_status=404)
    ok("PATCH /api/items/77777/consume  =>  404", body.get("error", ""))
except Exception as e:
    fail("PATCH /api/items/77777/consume  (404 check)", str(e))

# =============================================================================
# TEST 9 - Expiry status accuracy
# =============================================================================
section("TEST 9 - Expiry status accuracy (dynamic calculation)")

status_checks = [
    (today + timedelta(days=20), "fresh",         "20 days ahead"),
    (today + timedelta(days=7),  "expiring_soon", "7 days ahead"),
    (today + timedelta(days=1),  "expiring_soon", "1 day ahead"),
    (today,                      "expires_today", "today"),
    (today - timedelta(days=1),  "expired",       "1 day ago"),
    (today - timedelta(days=30), "expired",       "30 days ago"),
]

for exp_date, expected_status, label in status_checks:
    try:
        _, item = api("POST", "/api/items", {
            "item_name": f"Status Test {label}",
            "expiry_date": str(exp_date),
        }, expected_status=201)
        actual = item["status"]
        days = item["days_remaining"]
        if actual == expected_status:
            ok(f"Expiry {label}  =>  status='{actual}'  days_remaining={days}")
        else:
            fail(f"Expiry {label}  =>  expected='{expected_status}' got='{actual}'")
    except Exception as e:
        fail(f"Status check ({label})", str(e))

# =============================================================================
# TEST 10 - Dashboard statistics update dynamically
# =============================================================================
section("TEST 10 - Dashboard statistics update after operations")

try:
    _, dash_before = api("GET", "/api/dashboard", expected_status=200)
    total_before = dash_before["total"]
    info(f"Dashboard before add: total={total_before}")

    # Add one item
    _, new_item = api("POST", "/api/items", {
        "item_name": "Dashboard Test Item",
        "expiry_date": str(today + timedelta(days=25)),
    }, expected_status=201)
    dash_item_id = new_item["id"]

    _, dash_after_add = api("GET", "/api/dashboard", expected_status=200)
    assert dash_after_add["total"] == total_before + 1
    ok(f"After add: total {total_before} -> {dash_after_add['total']}")

    # Delete the item
    api("DELETE", f"/api/items/{dash_item_id}", expected_status=200)
    _, dash_after_del = api("GET", "/api/dashboard", expected_status=200)
    assert dash_after_del["total"] == total_before
    ok(f"After delete: total {dash_after_add['total']} -> {dash_after_del['total']}")

    # Verify individual counters sum to total
    d = dash_after_del
    counter_sum = d["fresh"] + d["expiring_soon"] + d["expires_today"] + d["expired"]
    assert counter_sum == d["total"], (
        f"Counter sum {counter_sum} != total {d['total']}"
    )
    ok(f"Counter sanity: fresh={d['fresh']} expiring={d['expiring_soon']} "
       f"today={d['expires_today']} expired={d['expired']} => total={d['total']}")

except Exception as e:
    fail("Dashboard update test", str(e))

# =============================================================================
# TEST 11 - Data persistence (simulate restart by reading SQLite directly)
# =============================================================================
section("TEST 11 - Data persistence across restart")

try:
    _, api_data = api("GET", "/api/items", expected_status=200)
    api_total = api_data["total"]
    info(f"Items via API: {api_total}")

    conn = sqlite3.connect(DB_PATH)
    db_count = conn.execute("SELECT COUNT(*) FROM pantry_items").fetchone()[0]
    conn.close()
    info(f"Items in pantrymate.db: {db_count}")

    assert api_total == db_count, f"API total {api_total} != DB count {db_count}"
    ok(f"API and SQLite row count match: {db_count} items")
    ok("Data is persisted in pantrymate.db and will survive a server restart")
except Exception as e:
    fail("Persistence check", str(e))

# =============================================================================
# SUMMARY
# =============================================================================
section("TEST SUMMARY")

passed = sum(1 for r in results if r[0] == "PASS")
failed = sum(1 for r in results if r[0] == "FAIL")
total = len(results)

print(f"\n  Total checks : {total}")
print(f"  Passed       : {passed}")
if failed:
    print(f"  Failed       : {failed}")
    print("\n  Failed checks:")
    for r in results:
        if r[0] == "FAIL":
            print(f"    FAIL: {r[1]}")
else:
    print("  Failed       : 0")

print()
if failed == 0:
    print("  >>> ALL TESTS PASSED - PantryMate is fully functional. <<<")
else:
    print(f"  >>> {failed} check(s) FAILED - see details above. <<<")
print()

sys.exit(0 if failed == 0 else 1)
