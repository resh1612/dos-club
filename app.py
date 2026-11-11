from flask import Flask, request, jsonify, render_template
from flask_cors import CORS
from database import get_db, init_db
from datetime import date, datetime, timedelta
import re

app = Flask(__name__)
CORS(app)

# ── helpers ────────────────────────────────────────────────────────────────────

VALID_CATEGORIES = {
    "Dairy", "Meat & Seafood", "Fruits", "Vegetables",
    "Grains & Bread", "Beverages", "Snacks", "Condiments",
    "Frozen", "Canned Goods", "Spices & Herbs", "Bakery", "Other"
}

VALID_UNITS = {
    "pcs", "kg", "g", "lbs", "oz", "L", "mL",
    "cups", "tbsp", "tsp", "dozen", "pack", "bottle", "can", "box"
}


def compute_status(expiry_date_str: str) -> dict:
    """Return expiry status label and days_remaining for a given date string."""
    try:
        expiry = datetime.strptime(expiry_date_str, "%Y-%m-%d").date()
    except (ValueError, TypeError):
        return {"status": "unknown", "days_remaining": None}

    today = date.today()
    delta = (expiry - today).days

    if delta < 0:
        status = "expired"
    elif delta == 0:
        status = "expires_today"
    elif delta <= 7:
        status = "expiring_soon"
    else:
        status = "fresh"

    return {"status": status, "days_remaining": delta}


def row_to_dict(row) -> dict:
    d = dict(row)
    info = compute_status(d.get("expiry_date"))
    d["status"] = info["status"]
    d["days_remaining"] = info["days_remaining"]
    return d


def validate_item(data: dict, require_all: bool = True) -> tuple[dict | None, str | None]:
    """Validate item payload. Returns (cleaned_data, error_message)."""
    cleaned = {}

    item_name = data.get("item_name", "").strip()
    if require_all or "item_name" in data:
        if not item_name:
            return None, "item_name is required and cannot be empty."
        if len(item_name) > 120:
            return None, "item_name must be 120 characters or fewer."
        cleaned["item_name"] = item_name

    if "category" in data:
        cat = data["category"].strip() if data["category"] else "Other"
        if cat not in VALID_CATEGORIES:
            cat = "Other"
        cleaned["category"] = cat

    if "quantity" in data:
        try:
            qty = float(data["quantity"])
            if qty <= 0:
                return None, "quantity must be a positive number."
            cleaned["quantity"] = qty
        except (TypeError, ValueError):
            return None, "quantity must be a valid number."

    if "unit" in data:
        unit = data["unit"].strip() if data["unit"] else "pcs"
        if unit not in VALID_UNITS:
            unit = "pcs"
        cleaned["unit"] = unit

    DATE_RE = re.compile(r"^\d{4}-\d{2}-\d{2}$")

    if "purchase_date" in data and data["purchase_date"]:
        pd_str = data["purchase_date"].strip()
        if pd_str and not DATE_RE.match(pd_str):
            return None, "purchase_date must be in YYYY-MM-DD format."
        cleaned["purchase_date"] = pd_str or None

    expiry_date = data.get("expiry_date", "").strip() if data.get("expiry_date") else ""
    if require_all or "expiry_date" in data:
        if not expiry_date:
            return None, "expiry_date is required."
        if not DATE_RE.match(expiry_date):
            return None, "expiry_date must be in YYYY-MM-DD format."
        try:
            datetime.strptime(expiry_date, "%Y-%m-%d")
        except ValueError:
            return None, "expiry_date is not a valid date."
        cleaned["expiry_date"] = expiry_date

    return cleaned, None


# ── routes ─────────────────────────────────────────────────────────────────────

@app.route("/")
def index():
    return render_template("index.html")


@app.route("/signin")
def signin():
    return render_template("signin.html")


# GET /api/items  – list all items (with optional search & filter)
@app.route("/api/items", methods=["GET"])
def get_items():
    search = request.args.get("search", "").strip()
    category = request.args.get("category", "").strip()
    status_filter = request.args.get("status", "").strip()

    conn = get_db()
    query = "SELECT * FROM pantry_items WHERE 1=1"
    params = []

    if search:
        query += " AND item_name LIKE ?"
        params.append(f"%{search}%")

    if category and category != "all":
        query += " AND category = ?"
        params.append(category)

    query += " ORDER BY expiry_date ASC"
    rows = conn.execute(query, params).fetchall()
    conn.close()

    items = [row_to_dict(r) for r in rows]

    # filter by status in Python (status is computed, not stored)
    if status_filter and status_filter != "all":
        items = [i for i in items if i["status"] == status_filter]

    return jsonify({"items": items, "total": len(items)})


# POST /api/items  – add a new item
@app.route("/api/items", methods=["POST"])
def add_item():
    data = request.get_json(silent=True)
    if not data:
        return jsonify({"error": "Request body must be JSON."}), 400

    cleaned, err = validate_item(data, require_all=True)
    if err:
        return jsonify({"error": err}), 422

    cleaned.setdefault("category", "Other")
    cleaned.setdefault("quantity", 1)
    cleaned.setdefault("unit", "pcs")
    cleaned.setdefault("purchase_date", None)

    conn = get_db()
    cur = conn.execute(
        """INSERT INTO pantry_items (item_name, category, quantity, unit, purchase_date, expiry_date)
           VALUES (?, ?, ?, ?, ?, ?)""",
        (cleaned["item_name"], cleaned["category"], cleaned["quantity"],
         cleaned["unit"], cleaned["purchase_date"], cleaned["expiry_date"])
    )
    conn.commit()
    new_id = cur.lastrowid
    row = conn.execute("SELECT * FROM pantry_items WHERE id=?", (new_id,)).fetchone()
    conn.close()
    return jsonify(row_to_dict(row)), 201


# PUT /api/items/<id>  – replace an item
@app.route("/api/items/<int:item_id>", methods=["PUT"])
def update_item(item_id):
    conn = get_db()
    existing = conn.execute("SELECT * FROM pantry_items WHERE id=?", (item_id,)).fetchone()
    if not existing:
        conn.close()
        return jsonify({"error": "Item not found."}), 404

    data = request.get_json(silent=True)
    if not data:
        conn.close()
        return jsonify({"error": "Request body must be JSON."}), 400

    cleaned, err = validate_item(data, require_all=True)
    if err:
        conn.close()
        return jsonify({"error": err}), 422

    cleaned.setdefault("category", "Other")
    cleaned.setdefault("quantity", 1)
    cleaned.setdefault("unit", "pcs")
    cleaned.setdefault("purchase_date", None)

    conn.execute(
        """UPDATE pantry_items
           SET item_name=?, category=?, quantity=?, unit=?, purchase_date=?, expiry_date=?
           WHERE id=?""",
        (cleaned["item_name"], cleaned["category"], cleaned["quantity"],
         cleaned["unit"], cleaned["purchase_date"], cleaned["expiry_date"], item_id)
    )
    conn.commit()
    row = conn.execute("SELECT * FROM pantry_items WHERE id=?", (item_id,)).fetchone()
    conn.close()
    return jsonify(row_to_dict(row))


# DELETE /api/items/<id>
@app.route("/api/items/<int:item_id>", methods=["DELETE"])
def delete_item(item_id):
    conn = get_db()
    existing = conn.execute("SELECT id FROM pantry_items WHERE id=?", (item_id,)).fetchone()
    if not existing:
        conn.close()
        return jsonify({"error": "Item not found."}), 404
    conn.execute("DELETE FROM pantry_items WHERE id=?", (item_id,))
    conn.commit()
    conn.close()
    return jsonify({"message": "Item deleted successfully."}), 200


# PATCH /api/items/<id>/consume  – remove item (mark as consumed)
@app.route("/api/items/<int:item_id>/consume", methods=["PATCH"])
def consume_item(item_id):
    conn = get_db()
    existing = conn.execute("SELECT id FROM pantry_items WHERE id=?", (item_id,)).fetchone()
    if not existing:
        conn.close()
        return jsonify({"error": "Item not found."}), 404
    conn.execute("DELETE FROM pantry_items WHERE id=?", (item_id,))
    conn.commit()
    conn.close()
    return jsonify({"message": "Item marked as consumed and removed."}), 200


# GET /api/dashboard
@app.route("/api/dashboard", methods=["GET"])
def dashboard():
    conn = get_db()
    rows = conn.execute("SELECT expiry_date FROM pantry_items").fetchall()
    conn.close()

    total = len(rows)
    fresh = expiring_soon = expires_today = expired = 0

    for r in rows:
        s = compute_status(r["expiry_date"])["status"]
        if s == "fresh":
            fresh += 1
        elif s == "expiring_soon":
            expiring_soon += 1
        elif s == "expires_today":
            expires_today += 1
        elif s == "expired":
            expired += 1

    return jsonify({
        "total": total,
        "fresh": fresh,
        "expiring_soon": expiring_soon,
        "expires_today": expires_today,
        "expired": expired,
        "last_updated": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    })


# ── entry point ────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    init_db()
    app.run(debug=True, port=5000)
