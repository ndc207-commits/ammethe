from fastapi import FastAPI, HTTPException
from fastapi.responses import StreamingResponse
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import create_engine, text
from datetime import datetime
import io
from reportlab.pdfgen import canvas
import os

app = FastAPI(title="KHO AMME THE")

# ===== DATABASE =====
DATABASE_URL = os.getenv("DATABASE_URL")  # Supabase
if not DATABASE_URL:
    raise Exception("Bạn cần set DATABASE_URL từ Supabase")

engine = create_engine(DATABASE_URL, connect_args={"sslmode":"require"}, pool_pre_ping=True)

# ===== CORS =====
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ===== PRODUCTS CRUD =====
@app.get("/products")
def get_products():
    with engine.connect() as conn:
        res = conn.execute(text("SELECT sku,name,is_active FROM products")).fetchall()
        return [{"sku": r[0], "name": r[1], "is_active": r[2]} for r in res]

@app.post("/products")
def create_product(prod: dict):
    with engine.begin() as conn:
        conn.execute(text("INSERT INTO products(sku,name) VALUES (:sku,:name)"), {"sku":prod["sku"], "name":prod["name"]})
    return {"msg":"Created"}

@app.put("/products/{sku}")
def update_product(sku:str, prod: dict):
    with engine.begin() as conn:
        conn.execute(text("UPDATE products SET name=:name WHERE sku=:sku"), {"name":prod["name"],"sku":sku})
    return {"msg":"Updated"}

@app.delete("/products/{sku}")
def delete_product(sku:str):
    with engine.begin() as conn:
        conn.execute(text("UPDATE products SET is_active=FALSE WHERE sku=:sku"), {"sku":sku})
    return {"msg":"Deleted"}

@app.post("/products/{sku}/recover")
def recover_product(sku:str):
    with engine.begin() as conn:
        conn.execute(text("UPDATE products SET is_active=TRUE WHERE sku=:sku"), {"sku":sku})
    return {"msg":"Recovered"}

# ===== INVENTORY =====
@app.get("/inventory")
def get_inventory():
    with engine.connect() as conn:
        res = conn.execute(text("""
            SELECT w.name as warehouse, p.sku, p.name, COALESCE(i.quantity,0) as quantity
            FROM inventory i
            JOIN products p ON p.sku=i.sku
            JOIN warehouses w ON w.id=i.warehouse_id
        """)).fetchall()
        return [{"warehouse":r[0],"sku":r[1],"name":r[2],"quantity":r[3]} for r in res]

# ===== WAREHOUSES =====
@app.get("/warehouses")
def get_warehouses():
    with engine.connect() as conn:
        res = conn.execute(text("SELECT id,name FROM warehouses")).fetchall()
        return [{"id":r[0],"name":r[1]} for r in res]

# ===== TRANSACTIONS =====
@app.post("/transaction")
def transaction(data: dict):
    sku = data["sku"]
    type_ = data["type"]
    qty = data["quantity"]
    wh_id = data["warehouse_id"]

    with engine.begin() as conn:
        # Cập nhật inventory
        inv = conn.execute(text("SELECT quantity FROM inventory WHERE sku=:sku AND warehouse_id=:wh_id"),
                           {"sku":sku,"wh_id":wh_id}).fetchone()
        if inv:
            new_qty = inv[0] + qty if type_=="Nhập" else inv[0]-qty
            conn.execute(text("UPDATE inventory SET quantity=:q WHERE sku=:sku AND warehouse_id=:wh_id"),
                         {"q":new_qty,"sku":sku,"wh_id":wh_id})
        else:
            conn.execute(text("INSERT INTO inventory(sku,warehouse_id,quantity) VALUES (:sku,:wh_id,:q)"),
                         {"sku":sku,"wh_id":wh_id,"q":qty if type_=="Nhập" else -qty})
        # Lưu lịch sử
        conn.execute(text("INSERT INTO history(sku,type,quantity,warehouse_id,created_at) VALUES (:sku,:t,:q,:wh,:dt)"),
                     {"sku":sku,"t":type_,"q":qty,"wh":wh_id,"dt":datetime.utcnow()})
    return {"msg":"OK"}

# ===== HISTORY =====
@app.get("/history")
def history():
    with engine.connect() as conn:
        res = conn.execute(text("""
            SELECT h.id, h.sku, h.type, h.quantity, h.created_at, w.name as warehouse
            FROM history h
            JOIN warehouses w ON h.warehouse_id=w.id
            ORDER BY h.created_at DESC
        """)).fetchall()
        return [{"id":r[0],"sku":r[1],"type":r[2],"quantity":r[3],"created_at":r[4].isoformat(),"warehouse":r[5]} for r in res]

# ===== PDF =====
@app.get("/invoice/pdf")
def pdf(sku: str, qty: int, type: str):
    buffer = io.BytesIO()
    c = canvas.Canvas(buffer)
    c.drawString(100, 800, f"PHIẾU {type.upper()}")
    c.drawString(100, 780, f"SKU: {sku}")
    c.drawString(100, 760, f"Số lượng: {qty}")
    c.drawString(100, 740, f"Ngày: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    c.save()
    buffer.seek(0)
    return StreamingResponse(buffer, media_type="application/pdf",
                             headers={"Content-Disposition": f"attachment; filename=invoice_{sku}.pdf"})
