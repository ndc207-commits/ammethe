from fastapi import FastAPI, HTTPException, Depends, status
from fastapi.security import OAuth2PasswordBearer, OAuth2PasswordRequestForm
from pydantic import BaseModel
from sqlalchemy import create_engine, text
from jose import JWTError, jwt
from datetime import datetime, timedelta
from typing import List
import os
import io
from fastapi.responses import StreamingResponse
from passlib.context import CryptContext
import pandas as pd
import openpyxl

app = FastAPI(title="Kho AMME THE")

# ========= DATABASE CONFIG =========
DATABASE_URL = os.getenv("DATABASE_URL")
engine = create_engine(DATABASE_URL, pool_pre_ping=True)

# ========= JWT CONFIG =========
SECRET_KEY = "mysecretkey"  # Use environment variables in production!
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 30
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="token")

# Password hashing
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

class User(BaseModel):
    username: str
    password: str
    is_admin: bool = False

# ===== DATABASE TABLES =====
# Add user table for authentication
exec_sql("""
CREATE TABLE IF NOT EXISTS users (
    username TEXT PRIMARY KEY,
    hashed_password TEXT,
    is_admin BOOLEAN DEFAULT FALSE
);
""")

# ========= HELPER FUNCTIONS =========
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
        headers={"WWW-Authenticate": "Bearer"},
    )
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        username: str = payload.get("sub")
        if username is None:
            raise credentials_exception
    except JWTError:
        raise credentials_exception
    return username

# ========= API ROUTES =========

# Register new user (admin can create users)
@app.post("/register")
def register(user: User):
    hashed_password = get_password_hash(user.password)
    with engine.begin() as conn:
        conn.execute(text("""
        INSERT INTO users (username, hashed_password, is_admin)
        VALUES (:username, :hashed_password, :is_admin)
        """), {"username": user.username, "hashed_password": hashed_password, "is_admin": user.is_admin})
    return {"msg": "User registered successfully"}

# Login and get token
@app.post("/token")
def login_for_access_token(form_data: OAuth2PasswordRequestForm = Depends()):
    with engine.connect() as conn:
        result = conn.execute(text("SELECT * FROM users WHERE username=:username"), {"username": form_data.username}).fetchone()
    
    if result is None or not verify_password(form_data.password, result["hashed_password"]):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid credentials")
    
    access_token_expires = timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    access_token = create_access_token(data={"sub": form_data.username}, expires_delta=access_token_expires)
    return {"access_token": access_token, "token_type": "bearer"}

# Protect API with JWT (Example with /products)
@app.get("/products")
def get_products(token: str = Depends(oauth2_scheme)):
    with engine.connect() as conn:
        result = conn.execute(text("SELECT * FROM products")).fetchall()
        return [{"sku": row[0], "name": row[1]} for row in result]

# ===== INVENTORY =====
@app.get("/inventory")
def inventory(token: str = Depends(oauth2_scheme)):
    with engine.connect() as conn:
        result = conn.execute(text("""
        SELECT w.name as warehouse, p.sku, p.name, COALESCE(i.quantity,0) as quantity
        FROM inventory i
        JOIN products p ON p.sku = i.sku
        JOIN warehouses w ON w.id = i.warehouse_id
        WHERE p.is_active = TRUE
        ORDER BY w.id, p.sku
        """)).fetchall()
        return [{"warehouse": row[0], "sku": row[1], "name": row[2], "quantity": row[3]} for row in result]

# ===== PDF =====
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

# ===== EXPORT EXCEL =====
@app.get("/export/excel")
def export_excel(token: str = Depends(oauth2_scheme)):
    df = fetch_all("""
    SELECT w.name as warehouse, p.sku, p.name, COALESCE(i.quantity,0) as quantity
    FROM inventory i
    JOIN products p ON p.sku = i.sku
    JOIN warehouses w ON w.id = i.warehouse_id
    WHERE p.is_active = TRUE
    """)
    
    # Create Excel file
    df_excel = pd.DataFrame(df)
    output = io.BytesIO()
    with pd.ExcelWriter(output, engine="openpyxl") as writer:
        df_excel.to_excel(writer, index=False, sheet_name="Inventory")
    output.seek(0)

    return StreamingResponse(output, media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet", headers={"Content-Disposition": "attachment; filename=inventory.xlsx"})
