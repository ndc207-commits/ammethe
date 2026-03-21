from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from sqlalchemy import create_engine, text
from fastapi.responses import StreamingResponse
import os
import io
from reportlab.pdfgen import canvas
from datetime import datetime

app = FastAPI(title="Kho AMME THE")

DATABASE_URL = os.environ.get("DATABASE_URL")
engine = create_engine(DATABASE_URL, pool_pre_ping=True)

# ================= INIT DB =================
def execute(q):
    with engine.begin() as conn:
        conn.execute(text(q))

execute("""
CREATE TABLE IF NOT EXISTS products(
    sku TEXT PRIMARY KEY,
    name TEXT,
    is_active BOOLEAN DEFAULT TRUE
);

CREATE TABLE IF NOT EXISTS warehouses(
    id SERIAL PRIMARY KEY,
    name TEXT UNIQUE
);

CREATE TABLE IF NOT EXISTS inventory(
    sku TEXT,
    warehouse_id INT,
    quantity INT DEFAULT 0,
    UNIQUE(sku, warehouse_id)
);

CREATE TABLE IF NOT EXISTS history(
    id SERIAL PRIMARY KEY,
    sku TEXT,
    type TEXT,
    quantity INT,
    warehouse_id INT,
    created_at TIMESTAMP DEFAULT now()
);
""")

with engine.begin() as conn:
    conn.execute(text("""
    INSERT INTO warehouses(name)
    VALUES ('La Pagode'), ('Muse'), ('Metz Ville'), ('Nancy')
    ON CONFLICT DO NOTHING;
    """))

# ================= MODELS =================
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

# ================= HELPERS =================
def fetch_all(q, p={}):
    with engine.connect() as conn:
        res = conn.execute(text(q), p)
        return [dict(r._mapping) for r in res]

# ================= PRODUCTS =================
@app.get("/products")
def get_products():
    return fetch_all("SELECT * FROM products ORDER BY sku")

@app.get("/products/search")
def search(q: str):
    return fetch_all("""
    SELECT * FROM products
    WHERE sku ILIKE :q OR name ILIKE :q
    """, {"q": f"%{q}%"})

@app.post("/products")
def add_product(p: Product):
    with engine.begin() as conn:
        conn.execute(text("""
        INSERT INTO products(sku,name)
        VALUES(:sku,:name)
        ON CONFLICT DO NOTHING
        """), p.dict())
    return {"msg": "OK"}

@app.put("/products/{sku}")
def update_product(sku: str, p: Product):
    with engine.begin() as conn:
        conn.execute(text("UPDATE products SET name=:name WHERE sku=:sku"),
                     {"sku": sku, "name": p.name})
    return {"msg": "Updated"}

@app.delete("/products/{sku}")
def delete_product(sku: str):
    with engine.begin() as conn:
        conn.execute(text("UPDATE products SET is_active=FALSE WHERE sku=:sku"), {"sku": sku})
    return {"msg": "Deleted"}

@app.post("/products/{sku}/recover")
def recover_product(sku: str):
    with engine.begin() as conn:
        conn.execute(text("UPDATE products SET is_active=TRUE WHERE sku=:sku"), {"sku": sku})
    return {"msg": "Recovered"}

# ================= WAREHOUSE =================
@app.get("/warehouses")
def warehouses():
    return fetch_all("SELECT * FROM warehouses ORDER BY id")

# ================= INVENTORY =================
@app.get("/inventory")
def inventory():
    return fetch_all("""
    SELECT w.name as warehouse, p.sku, p.name, COALESCE(i.quantity,0) quantity
    FROM products p
    CROSS JOIN warehouses w
    LEFT JOIN inventory i
        ON i.sku=p.sku AND i.warehouse_id=w.id
    WHERE p.is_active=TRUE
    ORDER BY w.id
    """)

@app.get("/inventory/low-stock")
def low_stock(threshold: int = 10):
    return fetch_all("""
    SELECT w.name as warehouse, p.sku, p.name, i.quantity
    FROM inventory i
    JOIN products p ON p.sku=i.sku
    JOIN warehouses w ON w.id=i.warehouse_id
    WHERE i.quantity <= :t
    """, {"t": threshold})

# ================= TRANSACTION =================
@app.post("/transaction")
def transaction(tx: Transaction):
    with engine.begin() as conn:

        res = conn.execute(text("""
        SELECT quantity FROM inventory
        WHERE sku=:sku AND warehouse_id=:w
        """), {"sku": tx.sku, "w": tx.warehouse_id}).fetchone()

        cur = res[0] if res else 0

        if tx.type == "Xuất" and tx.quantity > cur:
            raise HTTPException(400, "Không đủ hàng")

        new_qty = cur + tx.quantity if tx.type == "Nhập" else cur - tx.quantity

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

# ================= TRANSFER =================
@app.post("/transfer")
def transfer(t: Transfer):
    with engine.begin() as conn:

        res = conn.execute(text("""
        SELECT quantity FROM inventory
        WHERE sku=:sku AND warehouse_id=:w
        """), {"sku": t.sku, "w": t.from_warehouse_id}).fetchone()

        cur = res[0] if res else 0

        if t.quantity > cur:
            raise HTTPException(400, "Không đủ hàng")

        conn.execute(text("""
        UPDATE inventory SET quantity=quantity-:q
        WHERE sku=:sku AND warehouse_id=:w
        """), {"q": t.quantity, "sku": t.sku, "w": t.from_warehouse_id})

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

# ================= HISTORY =================
@app.get("/history")
def history():
    return fetch_all("""
    SELECT h.*, w.name as warehouse
    FROM history h
    LEFT JOIN warehouses w ON w.id=h.warehouse_id
    ORDER BY created_at DESC
    """)

# ================= PDF =================
@app.get("/invoice/pdf")
def pdf(sku: str, qty: int, type: str):
    buffer = io.BytesIO()
    c = canvas.Canvas(buffer)

    c.drawString(100, 800, f"PHIẾU {type}")
    c.drawString(100, 780, f"SKU: {sku}")
    c.drawString(100, 760, f"Số lượng: {qty}")
    c.drawString(100, 740, f"Ngày: {datetime.now()}")

    c.save()
    buffer.seek(0)

    return StreamingResponse(buffer, media_type="application/pdf")
