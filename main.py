# backend/main.py
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from sqlalchemy import create_engine, text
from typing import Optional
from fastapi.middleware.cors import CORSMiddleware
import os

app = FastAPI(title="API Quản Lý Kho AMME THE")

# ====== CORS ======
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # hoặc chỉ front-end của bạn
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ====== DB CONFIG ======
DATABASE_URL = os.environ.get("DATABASE_URL", "postgresql://postgres.acwzgbfrlqykqlhanfdi:Nhutren9989@aws-1-eu-central-1.pooler.supabase.com:5432/postgres")
engine = create_engine(DATABASE_URL, pool_size=5, max_overflow=10, pool_pre_ping=True)

def run_query(q, p={}):
    with engine.connect() as conn:
        return conn.execute(text(q), p)

def run_commit(q, p={}):
    with engine.begin() as conn:
        conn.execute(text(q), p)

# ====== MODELS ======
class Product(BaseModel):
    sku: str
    name: str

class Transaction(BaseModel):
    sku: str
    type: str  # Nhập/Xuất
    quantity: int
    warehouse_id: int
    store_id: Optional[int] = None

# ====== INIT TABLE ======
run_commit("""
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

# ====== API ENDPOINTS ======

# Lấy danh sách sản phẩm
@app.get("/products")
def get_products():
    df = run_query("SELECT * FROM products ORDER BY sku").fetchall()
    return [dict(row) for row in df]

# Thêm sản phẩm
@app.post("/products/add")
def add_product(p: Product):
    run_commit("INSERT INTO products(sku,name) VALUES (:sku,:name) ON CONFLICT DO NOTHING", {"sku":p.sku,"name":p.name})
    return {"msg":"Đã thêm sản phẩm"}

# Xóa sản phẩm
@app.post("/products/delete")
def delete_product(p: Product):
    run_commit("UPDATE products SET is_active=FALSE WHERE sku=:sku", {"sku":p.sku})
    return {"msg":"Đã xóa sản phẩm"}

# Phục hồi sản phẩm
@app.post("/products/recover")
def recover_product(p: Product):
    run_commit("UPDATE products SET is_active=TRUE WHERE sku=:sku", {"sku":p.sku})
    return {"msg":"Đã phục hồi sản phẩm"}

# Cập nhật tên sản phẩm
@app.post("/products/update")
def update_product(p: Product):
    run_commit("UPDATE products SET name=:name WHERE sku=:sku", {"sku":p.sku,"name":p.name})
    return {"msg":"Đã cập nhật sản phẩm"}

# Xem tồn kho tổng
@app.get("/inventory")
def get_inventory():
    df = run_query("""
    SELECT p.sku, p.name, COALESCE(SUM(i.quantity),0) AS quantity
    FROM products p
    LEFT JOIN inventory i ON p.sku=i.sku
    WHERE p.is_active=TRUE
    GROUP BY p.sku, p.name
    ORDER BY p.sku
    """).fetchall()
    return [dict(row) for row in df]

# Xem tồn kho cửa hàng
@app.get("/store_inventory")
def get_store_inventory():
    df = run_query("""
    SELECT p.sku, p.name, s.name AS store, COALESCE(si.quantity,0) AS quantity
    FROM products p
    LEFT JOIN store_inventory si ON p.sku=si.sku
    LEFT JOIN stores s ON si.store_id=s.id
    WHERE p.is_active=TRUE
    ORDER BY p.sku
    """).fetchall()
    return [dict(row) for row in df]

# Nhập/Xuất kho
@app.post("/transaction")
def transaction(tx: Transaction):
    # Cập nhật inventory
    res = run_query("SELECT quantity FROM inventory WHERE sku=:sku AND warehouse_id=:w FOR UPDATE",
                    {"sku":tx.sku,"w":tx.warehouse_id}).fetchone()
    cur_qty = res[0] if res else 0
    if tx.type=="Xuất" and tx.quantity>cur_qty:
        raise HTTPException(status_code=400, detail="Không đủ hàng")
    new_qty = cur_qty + tx.quantity if tx.type=="Nhập" else cur_qty - tx.quantity
    if res:
        run_commit("UPDATE inventory SET quantity=:q WHERE sku=:sku AND warehouse_id=:w", {"q":new_qty,"sku":tx.sku,"w":tx.warehouse_id})
    else:
        run_commit("INSERT INTO inventory(sku,warehouse_id,quantity) VALUES (:sku,:w,:q)", {"sku":tx.sku,"w":tx.warehouse_id,"q":new_qty})
    
    # Cập nhật kho cửa hàng nếu xuất
    if tx.type=="Xuất" and tx.store_id:
        res2 = run_query("SELECT quantity FROM store_inventory WHERE sku=:sku AND store_id=:sid FOR UPDATE",
                         {"sku":tx.sku,"sid":tx.store_id}).fetchone()
        cur2 = res2[0] if res2 else 0
        new2 = cur2 + tx.quantity
        if res2:
            run_commit("UPDATE store_inventory SET quantity=:q WHERE sku=:sku AND store_id=:sid",
                       {"q":new2,"sku":tx.sku,"sid":tx.store_id})
        else:
            run_commit("INSERT INTO store_inventory(sku,store_id,quantity) VALUES (:sku,:sid,:q)",
                       {"sku":tx.sku,"sid":tx.store_id,"q":new2})
    
    # Ghi lịch sử
    run_commit("INSERT INTO history(sku,type,quantity,warehouse_id,store_id) VALUES (:sku,:type,:q,:w,:sid)",
               {"sku":tx.sku,"type":tx.type,"q":tx.quantity,"w":tx.warehouse_id,"sid":tx.store_id})
    return {"msg":"Hoàn tất giao dịch"}

# Lấy lịch sử giao dịch
@app.get("/history")
def get_history(limit: int = 100):
    df = run_query("SELECT * FROM history ORDER BY created_at DESC LIMIT :lim", {"lim":limit}).fetchall()
    return [dict(row) for row in df]
