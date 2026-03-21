# backend.py
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from sqlalchemy import create_engine, text
from typing import Optional
from fastapi.middleware.cors import CORSMiddleware
import os

app = FastAPI(title="Quản Lý Kho AMME THE")

# ====== CORS ======
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ====== DB CONFIG ======
DATABASE_URL = os.environ.get("DATABASE_URL", "postgresql://postgres.acwzgbfrlqykqlhanfdi:Nhutren9989@aws-1-eu-central-1.pooler.supabase.com:5432/postgres")
engine = create_engine(
    DATABASE_URL,
    pool_size=5,
    max_overflow=10,
    pool_pre_ping=True
)

# ====== HELPERS ======
def fetch_all(q, p={}):
    try:
        with engine.connect() as conn:
            result = conn.execute(text(q), p)
            return [dict(row._mapping) for row in result]
    except Exception:
        return []

def fetch_one(q, p={}):
    try:
        with engine.connect() as conn:
            result = conn.execute(text(q), p).fetchone()
            return dict(result._mapping) if result else None
    except Exception:
        return None

def execute(q, p={}):
    with engine.begin() as conn:
        conn.execute(text(q), p)

# ====== MODELS ======
class Product(BaseModel):
    sku: str
    name: str

class Transaction(BaseModel):
    sku: str
    type: str
    quantity: int
    warehouse_id: int
    store_id: Optional[int] = None

# ====== INIT TABLE ======
execute("""
CREATE TABLE IF NOT EXISTS products(
    sku TEXT PRIMARY KEY,
    name TEXT NOT NULL,
    is_active BOOLEAN DEFAULT TRUE
);
CREATE TABLE IF NOT EXISTS warehouses(
    id SERIAL PRIMARY KEY,
    name TEXT UNIQUE
);
CREATE TABLE IF NOT EXISTS stores(
    id SERIAL PRIMARY KEY,
    name TEXT UNIQUE
);
CREATE TABLE IF NOT EXISTS inventory(
    sku TEXT NOT NULL,
    warehouse_id INTEGER,
    quantity INTEGER DEFAULT 0,
    UNIQUE(sku, warehouse_id)
);
CREATE TABLE IF NOT EXISTS store_inventory(
    sku TEXT NOT NULL,
    store_id INTEGER,
    quantity INTEGER DEFAULT 0,
    UNIQUE(sku, store_id)
);
CREATE TABLE IF NOT EXISTS history(
    id SERIAL PRIMARY KEY,
    sku TEXT NOT NULL,
    type TEXT NOT NULL,
    quantity INTEGER NOT NULL,
    warehouse_id INTEGER,
    store_id INTEGER,
    created_at TIMESTAMP DEFAULT now()
);
""")

# ====== API ======
@app.get("/")
def root():
    return {"status": "OK"}

# ====== PRODUCTS ======
@app.get("/products")
def get_products():
    return fetch_all("SELECT sku, name, is_active FROM products ORDER BY sku")

@app.post("/products/add")
def add_product(p: Product):
    execute(
        "INSERT INTO products(sku,name) VALUES (:sku,:name) ON CONFLICT DO NOTHING",
        {"sku": p.sku, "name": p.name}
    )
    return {"msg": "Đã thêm sản phẩm"}

@app.post("/products/delete")
def delete_product(p: Product):
    execute("UPDATE products SET is_active=FALSE WHERE sku=:sku", {"sku": p.sku})
    return {"msg": "Đã xóa sản phẩm"}

@app.post("/products/recover")
def recover_product(p: Product):
    execute("UPDATE products SET is_active=TRUE WHERE sku=:sku", {"sku": p.sku})
    return {"msg": "Đã phục hồi sản phẩm"}

@app.post("/products/update")
def update_product(p: Product):
    execute("UPDATE products SET name=:name WHERE sku=:sku", {"sku": p.sku, "name": p.name})
    return {"msg": "Đã cập nhật"}

# ====== INVENTORY ======
@app.get("/inventory")
def get_inventory():
    return fetch_all("""
    SELECT p.sku, p.name, COALESCE(SUM(i.quantity),0) AS quantity
    FROM products p
    LEFT JOIN inventory i ON p.sku=i.sku
    WHERE p.is_active=TRUE
    GROUP BY p.sku, p.name
    ORDER BY p.sku
    """)

@app.get("/store_inventory")
def get_store_inventory():
    return fetch_all("""
    SELECT p.sku, p.name, COALESCE(s.name,'Chưa có') AS store, COALESCE(si.quantity,0) AS quantity
    FROM products p
    LEFT JOIN store_inventory si ON p.sku=si.sku
    LEFT JOIN stores s ON si.store_id=s.id
    WHERE p.is_active=TRUE
    ORDER BY p.sku
    """)

# ====== TRANSACTION ======
@app.post("/transaction")
def transaction(tx: Transaction):
    with engine.begin() as conn:
        # ===== inventory =====
        res = conn.execute(
            text("SELECT quantity FROM inventory WHERE sku=:sku AND warehouse_id=:w"),
            {"sku": tx.sku, "w": tx.warehouse_id}
        ).fetchone()
        cur_qty = res[0] if res else 0

        if tx.type == "Xuất" and tx.quantity > cur_qty:
            raise HTTPException(status_code=400, detail="Không đủ hàng")

        new_qty = cur_qty + tx.quantity if tx.type=="Nhập" else cur_qty - tx.quantity

        if res:
            conn.execute(
                text("UPDATE inventory SET quantity=:q WHERE sku=:sku AND warehouse_id=:w"),
                {"q": new_qty, "sku": tx.sku, "w": tx.warehouse_id}
            )
        else:
            conn.execute(
                text("INSERT INTO inventory(sku,warehouse_id,quantity) VALUES (:sku,:w,:q)"),
                {"sku": tx.sku, "w": tx.warehouse_id, "q": new_qty}
            )

        # ===== store inventory =====
        if tx.type=="Xuất" and tx.store_id:
            res2 = conn.execute(
                text("SELECT quantity FROM store_inventory WHERE sku=:sku AND store_id=:sid"),
                {"sku": tx.sku, "sid": tx.store_id}
            ).fetchone()
            cur2 = res2[0] if res2 else 0
            new2 = cur2 + tx.quantity
            if res2:
                conn.execute(
                    text("UPDATE store_inventory SET quantity=:q WHERE sku=:sku AND store_id=:sid"),
                    {"q": new2, "sku": tx.sku, "sid": tx.store_id}
                )
            else:
                conn.execute(
                    text("INSERT INTO store_inventory(sku,store_id,quantity) VALUES (:sku,:sid,:q)"),
                    {"sku": tx.sku, "sid": tx.store_id, "q": new2}
                )

        # ===== history =====
        conn.execute(
            text("INSERT INTO history(sku,type,quantity,warehouse_id,store_id) VALUES (:sku,:type,:q,:w,:sid)"),
            {"sku": tx.sku, "type": tx.type, "q": tx.quantity, "w": tx.warehouse_id, "sid": tx.store_id}
        )

    return {"msg": "OK"}

# ====== HISTORY ======
@app.get("/history")
def get_history(limit: int = 100):
    try:
        return fetch_all("""
        SELECT id, sku, type, quantity, warehouse_id, store_id, created_at
        FROM history
        ORDER BY created_at DESC
        LIMIT :lim
        """, {"lim": limit})
    except Exception:
        # Trả về list rỗng nếu lỗi
        return []
