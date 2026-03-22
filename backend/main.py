from fastapi import FastAPI, HTTPException, Depends
from fastapi.security import OAuth2PasswordBearer, OAuth2PasswordRequestForm
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import create_engine, text
from jose import jwt, JWTError
from datetime import datetime, timedelta
from passlib.context import CryptContext
import os, io
import pandas as pd
from fastapi.responses import StreamingResponse
from reportlab.pdfgen import canvas

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ===== CONFIG =====
DATABASE_URL = os.getenv("DATABASE_URL")
SECRET_KEY = os.getenv("SECRET_KEY", "secret")
ALGORITHM = "HS256"

engine = create_engine(DATABASE_URL)
pwd = CryptContext(schemes=["bcrypt"], deprecated="auto")
oauth2 = OAuth2PasswordBearer(tokenUrl="token")

# ===== DB =====
def exec_sql(q, p={}):
    with engine.begin() as c:
        c.execute(text(q), p)

def fetch(q, p={}):
    with engine.connect() as c:
        return [dict(r._mapping) for r in c.execute(text(q), p)]

def one(q, p={}):
    with engine.connect() as c:
        r = c.execute(text(q), p).fetchone()
        return dict(r._mapping) if r else None

# ===== TABLE =====
exec_sql("""
CREATE TABLE IF NOT EXISTS users (
 username TEXT PRIMARY KEY,
 hashed_password TEXT,
 is_admin BOOLEAN DEFAULT TRUE
);
""")

exec_sql("""
CREATE TABLE IF NOT EXISTS products (
 sku TEXT PRIMARY KEY,
 name TEXT,
 is_active BOOLEAN DEFAULT TRUE
);
""")

exec_sql("""
CREATE TABLE IF NOT EXISTS warehouses (
 id SERIAL PRIMARY KEY,
 name TEXT
);
""")

exec_sql("""
CREATE TABLE IF NOT EXISTS inventory (
 sku TEXT,
 warehouse_id INT,
 quantity INT DEFAULT 0
);
""")

exec_sql("""
CREATE TABLE IF NOT EXISTS history (
 id SERIAL PRIMARY KEY,
 sku TEXT,
 type TEXT,
 quantity INT,
 warehouse_id INT,
 created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
""")

# ===== ADMIN =====
def init_admin():
    if not one("SELECT * FROM users WHERE username='admin'"):
        exec_sql("INSERT INTO users VALUES ('admin', :p, true)",
                 {"p": pwd.hash("admin1230")})
init_admin()

# ===== AUTH =====
def get_user(token=Depends(oauth2)):
    try:
        u = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])["sub"]
    except:
        raise HTTPException(401)
    user = one("SELECT * FROM users WHERE username=:u", {"u": u})
    if not user: raise HTTPException(401)
    return user

# ===== LOGIN =====
@app.post("/token")
def login(f: OAuth2PasswordRequestForm = Depends()):
    user = one("SELECT * FROM users WHERE username=:u", {"u": f.username})
    if not user or not pwd.verify(f.password, user["hashed_password"]):
        raise HTTPException(401)
    token = jwt.encode({"sub": user["username"], "exp": datetime.utcnow()+timedelta(minutes=60)}, SECRET_KEY)
    return {"access_token": token}

# ===== PRODUCTS =====
@app.get("/products")
def products(u=Depends(get_user)):
    return fetch("SELECT * FROM products")

@app.post("/products")
def add_product(p: dict, u=Depends(get_user)):
    exec_sql("INSERT INTO products VALUES (:sku,:name,true)", p)
    return {"ok": True}

@app.put("/products/{sku}")
def update(sku: str, p: dict, u=Depends(get_user)):
    exec_sql("UPDATE products SET name=:name WHERE sku=:sku", p)
    return {"ok": True}

@app.delete("/products/{sku}")
def delete(sku: str, u=Depends(get_user)):
    exec_sql("UPDATE products SET is_active=false WHERE sku=:s", {"s": sku})
    return {"ok": True}

@app.post("/products/{sku}/recover")
def recover(sku: str, u=Depends(get_user)):
    exec_sql("UPDATE products SET is_active=true WHERE sku=:s", {"s": sku})
    return {"ok": True}

@app.get("/products/search")
def search(q: str, u=Depends(get_user)):
    return fetch("SELECT * FROM products WHERE name ILIKE :q OR sku ILIKE :q", {"q": f"%{q}%"})

# ===== WAREHOUSE =====
@app.get("/warehouses")
def wh(u=Depends(get_user)):
    return fetch("SELECT * FROM warehouses")

# ===== INVENTORY =====
@app.get("/inventory")
def inv(u=Depends(get_user)):
    return fetch("""
    SELECT w.name warehouse,p.sku,p.name,COALESCE(i.quantity,0) quantity
    FROM products p
    LEFT JOIN inventory i ON p.sku=i.sku
    LEFT JOIN warehouses w ON w.id=i.warehouse_id
    """)

@app.get("/inventory/low-stock")
def low(threshold:int=10, u=Depends(get_user)):
    return fetch("SELECT * FROM inventory WHERE quantity < :t", {"t": threshold})

# ===== TRANSACTION =====
@app.post("/transaction")
def trans(d: dict, u=Depends(get_user)):
    q = d["quantity"] if d["type"]=="Nhập" else -d["quantity"]
    exec_sql("""
    INSERT INTO inventory VALUES (:sku,:w,:q)
    ON CONFLICT DO NOTHING
    """, {"sku":d["sku"],"w":d["warehouse_id"],"q":q})

    exec_sql("""
    UPDATE inventory SET quantity = quantity + :q
    WHERE sku=:sku AND warehouse_id=:w
    """, {"q":q,"sku":d["sku"],"w":d["warehouse_id"]})

    exec_sql("""
    INSERT INTO history (sku,type,quantity,warehouse_id)
    VALUES (:sku,:t,:q,:w)
    """, {"sku":d["sku"],"t":d["type"],"q":d["quantity"],"w":d["warehouse_id"]})

    return {"ok": True}

# ===== HISTORY =====
@app.get("/history")
def hist(u=Depends(get_user)):
    return fetch("SELECT * FROM history ORDER BY created_at DESC")

# ===== PDF =====
@app.get("/invoice/pdf")
def pdf(sku:str,qty:int,type:str):
    b=io.BytesIO()
    c=canvas.Canvas(b)
    c.drawString(100,800,f"{type}")
    c.drawString(100,780,sku)
    c.drawString(100,760,str(qty))
    c.save()
    b.seek(0)
    return StreamingResponse(b, media_type="application/pdf")
