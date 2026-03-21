from fastapi import FastAPI, HTTPException
from sqlalchemy import create_engine, text
import os
from dotenv import load_dotenv

load_dotenv()
DB_URL = os.getenv("DB_URL")
engine = create_engine(DB_URL, pool_pre_ping=True)

app = FastAPI(title="API Quản lý kho")

def run_query(q, params={}):
    with engine.connect() as conn:
        return conn.execute(text(q), params)

def run_commit(q, params={}):
    with engine.begin() as conn:
        conn.execute(text(q), params)

@app.get("/products")
def get_products():
    rows = run_query("SELECT * FROM products").mappings().all()
    return [dict(r) for r in rows]

@app.post("/products")
def add_product(sku: str, name: str):
    run_commit("INSERT INTO products(sku,name) VALUES (:sku,:name)", {"sku":sku,"name":name})
    return {"detail":"OK"}

@app.put("/products")
def update_product(sku: str, name: str):
    run_commit("UPDATE products SET name=:name WHERE sku=:sku", {"sku":sku,"name":name})
    return {"detail":"OK"}

@app.delete("/products/{sku}")
def delete_product(sku: str):
    run_commit("UPDATE products SET is_active=FALSE WHERE sku=:sku", {"sku":sku})
    return {"detail":"OK"}

@app.post("/products/recover/{sku}")
def recover_product(sku: str):
    run_commit("UPDATE products SET is_active=TRUE WHERE sku=:sku", {"sku":sku})
    return {"detail":"OK"}

@app.get("/stock")
def get_stock():
    rows = run_query("""
        SELECT p.sku,p.name,COALESCE(w.name,'Chưa có kho') AS warehouse,
        COALESCE(i.quantity,0) AS quantity
        FROM products p
        LEFT JOIN inventory i ON p.sku=i.sku
        LEFT JOIN warehouses w ON i.warehouse_id=w.id
        WHERE p.is_active=TRUE
    """).mappings().all()
    return [dict(r) for r in rows]

@app.post("/stock")
def stock_tx(sku:str, warehouse_id:int, quantity:int, type_tx:str, store_id:int=None):
    with engine.begin() as conn:
        # Kho tổng
        res = conn.execute(text("SELECT quantity FROM inventory WHERE sku=:sku AND warehouse_id=:w FOR UPDATE"),
                           {"sku":sku,"w":warehouse_id}).fetchone()
        cur = res[0] if res else 0
        new = cur + quantity if type_tx=="Nhập" else cur - quantity
        if new<0: raise HTTPException(status_code=400, detail="Không đủ hàng")
        if res:
            conn.execute(text("UPDATE inventory SET quantity=:q WHERE sku=:sku AND warehouse_id=:w"),
                         {"q":new,"sku":sku,"w":warehouse_id})
        else:
            conn.execute(text("INSERT INTO inventory(sku,warehouse_id,quantity) VALUES (:sku,:w,:q)",
                              {"sku":sku,"w":warehouse_id,"q":new}))
        # Store
        if type_tx=="Xuất" and store_id:
            res2=conn.execute(text("SELECT quantity FROM store_inventory WHERE sku=:sku AND store_id=:sid FOR UPDATE"),
                              {"sku":sku,"sid":store_id}).fetchone()
            cur2=res2[0] if res2 else 0
            new2=cur2+quantity
            if res2:
                conn.execute(text("UPDATE store_inventory SET quantity=:q WHERE sku=:sku AND store_id=:sid"),
                             {"q":new2,"sku":sku,"sid":store_id})
            else:
                conn.execute(text("INSERT INTO store_inventory(sku,store_id,quantity) VALUES (:sku,:sid,:q)",
                                  {"sku":sku,"sid":store_id,"q":new2}))
        # History
        conn.execute(text("INSERT INTO history(sku,type,quantity,warehouse_id,note) VALUES "
                          "(:sku,:type,:q,:w,:note)"),
                     {"sku":sku,"type":type_tx,"q":quantity,"w":warehouse_id,"note":store_id})
    return {"detail":"OK"}

@app.get("/history")
def get_history():
    rows = run_query("""
        SELECT h.id,h.sku,p.name AS product,h.type,h.quantity,h.created_at,w.name AS warehouse,h.note
        FROM history h
        LEFT JOIN products p ON h.sku=p.sku
        LEFT JOIN warehouses w ON h.warehouse_id=w.id
        ORDER BY h.created_at DESC LIMIT 200
    """).mappings().all()
    return [dict(r) for r in rows]