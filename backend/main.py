# backend/main.py
from fastapi import FastAPI, HTTPException, Depends, status
from fastapi.security import OAuth2PasswordBearer, OAuth2PasswordRequestForm
from sqlalchemy import create_engine, text
from jose import JWTError, jwt
from datetime import datetime, timedelta
from passlib.context import CryptContext
from pydantic import BaseModel
from fastapi.responses import StreamingResponse
import io
from reportlab.pdfgen import canvas
import os
import pandas as pd

app = FastAPI(title="KHO AMME THE")

# ========= DATABASE CONFIG =========
DATABASE_URL = os.getenv("DATABASE_URL")
engine = create_engine(DATABASE_URL, pool_pre_ping=True)

# ========= JWT CONFIG =========
SECRET_KEY = os.getenv("SECRET_KEY","mysecretkey")
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 30
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="token")

# ========= PASSWORD HASH =========
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

# ========= HELPER =========
def exec_sql(query, params={}):
    with engine.begin() as conn:
        conn.execute(text(query), params)

def fetch_all(query, params={}):
    with engine.connect() as conn:
        return [dict(r._mapping) for r in conn.execute(text(query), params)]

def one(query, params={}):
    with engine.connect() as conn:
        r = conn.execute(text(query), params).fetchone()
        return dict(r._mapping) if r else None

# ========= TABLES =========
exec_sql("""
CREATE TABLE IF NOT EXISTS users (
    username TEXT PRIMARY KEY,
    hashed_password TEXT,
    is_admin BOOLEAN DEFAULT FALSE
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

# ========= INIT ADMIN =========
def init_admin():
    admin = one("SELECT * FROM users WHERE username='admin'")
    if not admin:
        exec_sql(
            "INSERT INTO users(username, hashed_password, is_admin) VALUES (:u,:p,true)",
            {"u":"admin", "p":pwd_context.hash("admin1230")}
        )
init_admin()

# ========= UTILS =========
def verify_password(plain_password, hashed_password):
    return pwd_context.verify(plain_password, hashed_password)

def get_password_hash(password):
    return pwd_context.hash(password)

def create_access_token(data: dict, expires_delta: timedelta = timedelta(minutes=15)):
    to_encode = data.copy()
    expire = datetime.utcnow() + expires_delta
    to_encode.update({"exp": expire})
    return jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)

def get_current_user(token: str = Depends(oauth2_scheme)):
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate":"Bearer"}
    )
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        username: str = payload.get("sub")
        if username is None:
            raise credentials_exception
    except JWTError:
        raise credentials_exception
    user = one("SELECT * FROM users WHERE username=:u", {"u": username})
    if not user:
        raise credentials_exception
    return user

# ========= MODELS =========
class User(BaseModel):
    username: str
    password: str
    is_admin: bool = False

# ========= AUTH =========
@app.post("/token")
def login(form_data: OAuth2PasswordRequestForm = Depends()):
    user = one("SELECT * FROM users WHERE username=:u", {"u":form_data.username})
    if not user or not verify_password(form_data.password, user["hashed_password"]):
        raise HTTPException(status_code=401, detail="Invalid credentials")
    access_token = create_access_token({"sub":user["username"]})
    return {"access_token": access_token, "token_type":"bearer"}

# ========= REGISTER (CHỈ ADMIN) =========
@app.post("/register")
def register(user: User, current_user=Depends(get_current_user)):
    if not current_user["is_admin"]:
        raise HTTPException(status_code=403, detail="Chỉ admin mới được tạo user")
    exist = one("SELECT * FROM users WHERE username=:u", {"u":user.username})
    if exist:
        raise HTTPException(status_code=400, detail="Username đã tồn tại")
    hashed_password = get_password_hash(user.password)
    exec_sql("INSERT INTO users(username, hashed_password, is_admin) VALUES (:u,:p,:a)",
             {"u":user.username,"p":hashed_password,"a":user.is_admin})
    return {"msg":f"User {user.username} đã được tạo"}

# ========= PRODUCTS =========
@app.get("/products")
def get_products(user=Depends(get_current_user)):
    return fetch_all("SELECT * FROM products")

@app.post("/products")
def add_product(p: dict, user=Depends(get_current_user)):
    exec_sql("INSERT INTO products(sku,name,is_active) VALUES (:sku,:name,true)", p)
    return {"ok":True}

@app.put("/products/{sku}")
def update_product(sku:str, p: dict, user=Depends(get_current_user)):
    exec_sql("UPDATE products SET name=:name WHERE sku=:sku", p)
    return {"ok":True}

@app.delete("/products/{sku}")
def delete_product(sku:str, user=Depends(get_current_user)):
    exec_sql("UPDATE products SET is_active=false WHERE sku=:s", {"s":sku})
    return {"ok":True}

@app.post("/products/{sku}/recover")
def recover_product(sku:str, user=Depends(get_current_user)):
    exec_sql("UPDATE products SET is_active=true WHERE sku=:s", {"s":sku})
    return {"ok":True}

@app.get("/products/search")
def search_product(q:str, user=Depends(get_current_user)):
    return fetch_all("SELECT * FROM products WHERE name ILIKE :q OR sku ILIKE :q", {"q":f"%{q}%"})

# ========= WAREHOUSES / INVENTORY =========
@app.get("/warehouses")
def get_warehouses(user=Depends(get_current_user)):
    return fetch_all("SELECT * FROM warehouses")

@app.get("/inventory")
def get_inventory(user=Depends(get_current_user)):
    return fetch_all("""
        SELECT w.name warehouse,p.sku,p.name,COALESCE(i.quantity,0) quantity
        FROM products p
        LEFT JOIN inventory i ON p.sku=i.sku
        LEFT JOIN warehouses w ON w.id=i.warehouse_id
    """)

@app.get("/inventory/low-stock")
def low_stock(threshold:int=10,user=Depends(get_current_user)):
    return fetch_all("SELECT * FROM inventory WHERE quantity<:t", {"t":threshold})

# ========= TRANSACTION =========
@app.post("/transaction")
def transaction(d: dict, user=Depends(get_current_user)):
    q = d["quantity"] if d["type"]=="Nhập" else -d["quantity"]
    exec_sql("""
        INSERT INTO inventory(sku,warehouse_id,quantity)
        VALUES (:sku,:w,:q)
        ON CONFLICT(sku,warehouse_id) DO UPDATE SET quantity=inventory.quantity+:q
    """, {"sku":d["sku"],"w":d["warehouse_id"],"q":q})
    exec_sql("""
        INSERT INTO history(sku,type,quantity,warehouse_id)
        VALUES (:sku,:t,:q,:w)
    """, {"sku":d["sku"],"t":d["type"],"q":d["quantity"],"w":d["warehouse_id"]})
    return {"ok":True}

@app.get("/history")
def get_history(user=Depends(get_current_user)):
    return fetch_all("SELECT * FROM history ORDER BY created_at DESC")

# ========= PDF =========
@app.get("/invoice/pdf")
def pdf_invoice(sku:str, qty:int, type:str):
    buffer = io.BytesIO()
    c = canvas.Canvas(buffer)
    c.drawString(100,800,f"PHIẾU {type}")
    c.drawString(100,780,f"SKU: {sku}")
    c.drawString(100,760,f"Số lượng: {qty}")
    c.drawString(100,740,f"Ngày: {datetime.now()}")
    c.save()
    buffer.seek(0)
    return StreamingResponse(buffer, media_type="application/pdf")
