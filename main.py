# api_main.py
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
import pandas as pd
from sqlalchemy import create_engine, text
from datetime import datetime

DB_URL = "postgresql://postgres.acwzgbfrlqykqlhanfdi:Nhutren9989@aws-1-eu-central-1.pooler.supabase.com:5432/postgres"
engine = create_engine(DB_URL, pool_size=5, max_overflow=10, pool_pre_ping=True)

app = FastAPI()
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

def run_query(q, p={}):
    with engine.connect() as conn:
        return conn.execute(text(q), p)

def df_to_list(q):
    df = pd.read_sql(q, engine)
    return df.to_dict(orient="records")

# -------------------- Sản phẩm --------------------
@app.get("/products")
def get_products():
    return df_to_list("SELECT sku,name FROM products WHERE is_active=TRUE")

@app.get("/deleted_products")
def get_deleted_products():
    return df_to_list("SELECT sku,name FROM products WHERE is_active=FALSE")

# -------------------- Kho --------------------
@app.get("/stock")
def get_stock():
    return df_to_list("""
        SELECT p.sku,p.name,COALESCE(w.name,'Chưa có kho') AS kho,COALESCE(i.quantity,0) AS so_luong
        FROM products p
        LEFT JOIN inventory i ON p.sku=i.sku
        LEFT JOIN warehouses w ON i.warehouse_id=w.id
        WHERE p.is_active=TRUE
    """)

@app.get("/store_stock")
def get_store_stock():
    return df_to_list("""
        SELECT p.sku,p.name,s.name AS cua_hang,COALESCE(si.quantity,0) AS so_luong
        FROM products p
        LEFT JOIN store_inventory si ON p.sku=si.sku
        LEFT JOIN stores s ON si.store_id=s.id
        WHERE p.is_active=TRUE
    """)

@app.get("/warehouses")
def get_warehouses():
    return df_to_list("SELECT id,name FROM warehouses")

@app.get("/stores")
def get_stores():
    return df_to_list("SELECT id,name FROM stores")

# -------------------- Lịch sử --------------------
@app.get("/history")
def get_history():
    return df_to_list("""
        SELECT h.id,h.sku,p.name AS san_pham,h.type,h.quantity,h.created_at,w.name AS kho,h.note
        FROM history h
        LEFT JOIN products p ON h.sku=p.sku
        LEFT JOIN warehouses w ON h.warehouse_id=w.id
        ORDER BY h.created_at DESC
    """)

@app.get("/export_history")
def export_history():
    df = pd.read_sql("""
        SELECT h.id,h.sku,p.name AS san_pham,h.type,h.quantity,h.created_at,w.name AS kho,h.note
        FROM history h
        LEFT JOIN products p ON h.sku=p.sku
        LEFT JOIN warehouses w ON h.warehouse_id=w.id
        ORDER BY h.created_at DESC
    """, engine)
    file_name = "history.xlsx"
    df.to_excel(file_name, index=False)
    return FileResponse(file_name,
                        media_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
                        filename=file_name)

# -------------------- Nhập / Xuất --------------------
@app.post("/transaction")
def transaction(sku: str, type_tx: str, quantity: int, warehouse_id: int, store_id: int = None):
    with engine.begin() as conn:
        # Cập nhật kho tổng
        res = conn.execute(text("SELECT quantity FROM inventory WHERE sku=:s AND warehouse_id=:w FOR UPDATE"), {"s":sku,"w":warehouse_id}).fetchone()
        current = res[0] if res else 0
        new_qty = current + quantity if type_tx=="Nhập" else current - quantity
        if type_tx=="Xuất" and quantity>current:
            return {"error":"Không đủ hàng"}
        if res:
            conn.execute(text("UPDATE inventory SET quantity=:q WHERE sku=:s AND warehouse_id=:w"),
                         {"q":new_qty,"s":sku,"w":warehouse_id})
        else:
            conn.execute(text("INSERT INTO inventory(sku,warehouse_id,quantity) VALUES (:s,:w,:q)"),
                         {"s":sku,"w":warehouse_id,"q":new_qty})
        # Cập nhật kho cửa hàng
        if type_tx=="Xuất" and store_id:
            res2 = conn.execute(text("SELECT quantity FROM store_inventory WHERE sku=:s AND store_id=:sid FOR UPDATE"),
                                {"s":sku,"sid":store_id}).fetchone()
            cur2 = res2[0] if res2 else 0
            new2 = cur2 + quantity
            if res2:
                conn.execute(text("UPDATE store_inventory SET quantity=:q WHERE sku=:s AND store_id=:sid"),
                             {"q":new2,"s":sku,"sid":store_id})
            else:
                conn.execute(text("INSERT INTO store_inventory(sku,store_id,quantity) VALUES (:s,:sid,:q)"),
                             {"s":sku,"sid":store_id,"q":new2})
        # Ghi lịch sử
        note = None
        if store_id:
            note = run_query("SELECT name FROM stores WHERE id=:id",{"id":store_id}).fetchone()[0]
        conn.execute(text("INSERT INTO history(sku,type,quantity,warehouse_id,note,created_at) VALUES "
                          "(:s,:t,:q,:w,:n,:d)"),
                     {"s":sku,"t":type_tx,"q":quantity,"w":warehouse_id,"n":note,"d":datetime.now()})
    return {"success":True}
