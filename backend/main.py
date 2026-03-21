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

# ====== DB ======
DATABASE_URL = os.environ.get("DATABASE_URL")
if not DATABASE_URL:
    raise Exception("Thiếu DATABASE_URL")

engine = create_engine(
    DATABASE_URL,
    pool_pre_ping=True
)

# ====== HELPERS ======
def fetch_all(q, p={}):
    try:
        with engine.connect() as conn:
            result = conn.execute(text(q), p)
            return [dict(row._mapping) for row in result]
    except Exception as e:
        print("FETCH_ALL ERROR:", e)
        raise HTTPException(500, "Database error")

def execute(q, p={}):
    try:
        with engine.begin() as conn:
            conn.execute(text(q), p)
    except Exception as e:
        print("EXECUTE ERROR:", e)
        raise HTTPException(500, "Database error")

# ====== MODELS ======
class Product(BaseModel):
    sku: str
    name: Optional[str] = None   # ✅ FIX

class Transaction(BaseModel):
    sku: str
    type: str
    quantity: int
    warehouse_id: int
    store_id: Optional[int] = None

# ====== INIT DB ======
def init_db():
    queries = [
        """CREATE TABLE IF NOT EXISTS products(
            sku TEXT PRIMARY KEY,
            name TEXT NOT NULL,
            is_active BOOLEAN DEFAULT TRUE
        )""",
        """CREATE TABLE IF NOT EXISTS inventory(
            sku TEXT,
            warehouse_id INTEGER,
            quantity INTEGER DEFAULT 0,
            UNIQUE(sku, warehouse_id)
        )""",
        """CREATE TABLE IF NOT EXISTS store_inventory(
            sku TEXT,
            store_id INTEGER,
            quantity INTEGER DEFAULT 0,
            UNIQUE(sku, store_id)
        )""",
        """CREATE TABLE IF NOT EXISTS history(
            id SERIAL PRIMARY KEY,
            sku TEXT,
            type TEXT,
            quantity INTEGER,
            warehouse_id INTEGER,
            store_id INTEGER,
            created_at TIMESTAMP DEFAULT now()
        )"""
    ]

    for q in queries:
        execute(q)

init_db()

# ====== ROOT ======
@app.get("/")
def root():
    return {"status": "OK"}

# ====== PRODUCTS ======

@app.get("/products")
def get_products(active: Optional[bool] = None):
    if active is None:
        return fetch_all("SELECT * FROM products ORDER BY sku")

    return fetch_all(
        "SELECT * FROM products WHERE is_active=:a ORDER BY sku",
        {"a": active}
    )

@app.post("/products")
def add_product(p: Product):
    if not p.name:
        raise HTTPException(400, "Thiếu tên sản phẩm")

    execute(
        """INSERT INTO products(sku,name)
        VALUES (:sku,:name)
        ON CONFLICT (sku) DO NOTHING""",
        p.dict()
    )
    return {"msg": "Đã thêm"}

@app.put("/products/{sku}")
def update_product(sku: str, p: Product):
    if not p.name:
        raise HTTPException(400, "Tên không được rỗng")

    execute(
        "UPDATE products SET name=:name WHERE sku=:sku",
        {"sku": sku, "name": p.name}
    )
    return {"msg": "Đã cập nhật"}

@app.delete("/products/{sku}")
def delete_product(sku: str):
    execute(
        "UPDATE products SET is_active=FALSE WHERE sku=:sku",
        {"sku": sku}
    )
    return {"msg": "Đã xóa"}

@app.post("/products/{sku}/recover")
def recover_product(sku: str):
    execute(
        "UPDATE products SET is_active=TRUE WHERE sku=:sku",
        {"sku": sku}
    )
    return {"msg": "Đã phục hồi"}

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

# ====== TRANSACTION ======

@app.post("/transaction")
def transaction(tx: Transaction):
    with engine.begin() as conn:

        res = conn.execute(
            text("SELECT quantity FROM inventory WHERE sku=:sku AND warehouse_id=:w"),
            {"sku": tx.sku, "w": tx.warehouse_id}
        ).fetchone()

        cur = res[0] if res else 0

        if tx.type == "Xuất" and tx.quantity > cur:
            raise HTTPException(400, "Không đủ hàng")

        new = cur + tx.quantity if tx.type == "Nhập" else cur - tx.quantity

        if res:
            conn.execute(
                text("UPDATE inventory SET quantity=:q WHERE sku=:sku AND warehouse_id=:w"),
                {"q": new, "sku": tx.sku, "w": tx.warehouse_id}
            )
        else:
            conn.execute(
                text("INSERT INTO inventory VALUES (:sku,:w,:q)"),
                {"sku": tx.sku, "w": tx.warehouse_id, "q": new}
            )

        conn.execute(
            text("""INSERT INTO history(sku,type,quantity,warehouse_id,store_id)
                    VALUES (:sku,:type,:q,:w,:sid)"""),
            {"sku": tx.sku, "type": tx.type, "q": tx.quantity,
             "w": tx.warehouse_id, "sid": tx.store_id}
        )

    return {"msg": "OK"}

# ====== HISTORY ======

@app.get("/history")
def get_history(limit: int = 100):
    return fetch_all("""
    SELECT * FROM history
    ORDER BY created_at DESC
    LIMIT :lim
    """, {"lim": int(limit)})
