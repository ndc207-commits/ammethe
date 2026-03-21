from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from sqlalchemy import create_engine, text
from fastapi.responses import StreamingResponse
import os, io
from reportlab.pdfgen import canvas
from datetime import datetime

app = FastAPI(title="Kho AMME THE")

DATABASE_URL = os.environ.get("DATABASE_URL")
engine = create_engine(DATABASE_URL, pool_pre_ping=True)

# ===== INIT TABLE =====
def exec_sql(q):
    with engine.begin() as conn:
        conn.execute(text(q))

exec_sql("""
CREATE TABLE IF NOT EXISTS products(
    sku TEXT PRIMARY KEY,
    name TEXT,
    is_active BOOLEAN DEFAULT TRUE
);

CREATE TABLE IF NOT EXISTS warehouses(
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT UNIQUE
);

CREATE TABLE IF NOT EXISTS inventory(
    sku TEXT,
    warehouse_id INT,
    quantity INT DEFAULT 0,
    UNIQUE(sku, warehouse_id)
);

CREATE TABLE IF NOT EXISTS history(
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    sku TEXT,
    type TEXT,
    quantity INT,
    warehouse_id INT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
""")

# seed warehouses
with engine.begin() as conn:
    conn.execute(text("""
    INSERT OR IGNORE INTO warehouses(name)
    VALUES ('La Pagode'), ('Muse'), ('Metz Ville'), ('Nancy')
    """))

# ===== MODELS =====
class Product(BaseModel):
    sku: str
    name: str

class Transaction(BaseModel):
    sku: str
    type: str
    quantity: int
    warehouse_id: int

class Transfer(BaseModel):
    sku: str
    from_warehouse_id: int
    to_warehouse_id: int
    quantity: int

# ===== HELPER =====
def fetch(q, p={}):
    with engine.connect() as conn:
        res = conn.execute(text(q), p)
        return [dict(r._mapping) for r in res]

# ===== PRODUCTS =====
@app.get("/products")
def get_products():
    return fetch("SELECT * FROM products")

@app.post("/products")
def add_product(p: Product):
    with engine.begin() as conn:
        conn.execute(text("""
        INSERT OR IGNORE INTO products(sku,name)
        VALUES(:sku,:name)
        """), p.dict())
    return {"msg": "OK"}

@app.put("/products/{sku}")
def update_product(sku: str, p: Product):
    with engine.begin() as conn:
        conn.execute(text("UPDATE products SET name=:name WHERE sku=:sku"),
                     {"sku": sku, "name": p.name})
    return {"msg": "OK"}

@app.delete("/products/{sku}")
def delete_product(sku: str):
    with engine.begin() as conn:
        conn.execute(text("UPDATE products SET is_active=0 WHERE sku=:sku"),
                     {"sku": sku})
    return {"msg": "Deleted"}

@app.post("/products/{sku}/recover")
def recover(sku: str):
    with engine.begin() as conn:
        conn.execute(text("UPDATE products SET is_active=1 WHERE sku=:sku"),
                     {"sku": sku})
    return {"msg": "Recovered"}

@app.get("/products/search")
def search(q: str):
    return fetch("""
    SELECT * FROM products
    WHERE sku LIKE :q OR name LIKE :q
    """, {"q": f"%{q}%"})

# ===== WAREHOUSES =====
@app.get("/warehouses")
def warehouses():
    return fetch("SELECT * FROM warehouses")

# ===== INVENTORY =====
@app.get("/inventory")
def inventory():
    return fetch("""
    SELECT w.name as warehouse, p.sku, p.name, COALESCE(i.quantity,0) quantity
    FROM products p
    JOIN warehouses w
    LEFT JOIN inventory i 
        ON i.sku=p.sku AND i.warehouse_id=w.id
    WHERE p.is_active=1
    ORDER BY w.id
    """)

# ===== TRANSACTION =====
@app.post("/transaction")
def transaction(tx: Transaction):
    with engine.begin() as conn:

        res = conn.execute(text("""
        SELECT quantity FROM inventory
        WHERE sku=:sku AND warehouse_id=:w
        """), {"sku": tx.sku, "w": tx.warehouse_id}).fetchone()

        current = res[0] if res else 0

        if tx.type == "Xuất" and tx.quantity > current:
            raise HTTPException(400, "Không đủ hàng")

        new_qty = current + tx.quantity if tx.type == "Nhập" else current - tx.quantity

        if res:
            conn.execute(text("""
            UPDATE inventory SET quantity=:q
            WHERE sku=:sku AND warehouse_id=:w
            """), {"q": new_qty, "sku": tx.sku, "w": tx.warehouse_id})
        else:
            conn.execute(text("""
            INSERT INTO inventory(sku,warehouse_id,quantity)
            VALUES(:sku,:w,:q)
            """), {"sku": tx.sku, "w": tx.warehouse_id, "q": new_qty})

        conn.execute(text("""
        INSERT INTO history(sku,type,quantity,warehouse_id)
        VALUES(:sku,:type,:q,:w)
        """), {"sku": tx.sku, "type": tx.type, "q": tx.quantity, "w": tx.warehouse_id})

    return {"msg": "OK"}

# ===== TRANSFER =====
@app.post("/transfer")
def transfer(t: Transfer):
    with engine.begin() as conn:

        res = conn.execute(text("""
        SELECT quantity FROM inventory
        WHERE sku=:sku AND warehouse_id=:w
        """), {"sku": t.sku, "w": t.from_warehouse_id}).fetchone()

        current = res[0] if res else 0

        if t.quantity > current:
            raise HTTPException(400, "Không đủ hàng")

        # minus source
        conn.execute(text("""
        UPDATE inventory SET quantity=quantity-:q
        WHERE sku=:sku AND warehouse_id=:w
        """), {"q": t.quantity, "sku": t.sku, "w": t.from_warehouse_id})

        # add dest
        res2 = conn.execute(text("""
        SELECT quantity FROM inventory
        WHERE sku=:sku AND warehouse_id=:w
        """), {"sku": t.sku, "w": t.to_warehouse_id}).fetchone()

        if res2:
            conn.execute(text("""
            UPDATE inventory SET quantity=quantity+:q
            WHERE sku=:sku AND warehouse_id=:w
            """), {"q": t.quantity, "sku": t.sku, "w": t.to_warehouse_id})
        else:
            conn.execute(text("""
            INSERT INTO inventory(sku,warehouse_id,quantity)
            VALUES(:sku,:w,:q)
            """), {"sku": t.sku, "w": t.to_warehouse_id, "q": t.quantity})

    return {"msg": "OK"}

# ===== LOW STOCK =====
@app.get("/inventory/low-stock")
def low_stock(threshold: int = 10):
    return fetch("""
    SELECT w.name as warehouse, p.sku, p.name, i.quantity
    FROM inventory i
    JOIN products p ON p.sku=i.sku
    JOIN warehouses w ON w.id=i.warehouse_id
    WHERE i.quantity <= :t
    """, {"t": threshold})

# ===== HISTORY =====
@app.get("/history")
def history():
    return fetch("SELECT * FROM history ORDER BY created_at DESC")

# ===== PDF =====
@app.get("/invoice/pdf")
def pdf(sku: str, qty: int, type: str):
    buffer = io.BytesIO()
    c = canvas.Canvas(buffer)
    c.drawString(100, 800, f"{type} - {sku}")
    c.drawString(100, 780, f"Qty: {qty}")
    c.drawString(100, 760, str(datetime.now()))
    c.save()
    buffer.seek(0)
    return StreamingResponse(buffer, media_type="application/pdf")
