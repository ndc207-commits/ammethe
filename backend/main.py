from fastapi import FastAPI, HTTPException, Depends, status
from fastapi.security import OAuth2PasswordBearer, OAuth2PasswordRequestForm
from pydantic import BaseModel
from sqlalchemy import create_engine, text
from jose import JWTError, jwt
from datetime import datetime, timedelta
from passlib.context import CryptContext
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
import io
from reportlab.pdfgen import canvas
import os

app = FastAPI(title="Kho AMME THE")

# ===== Database =====
DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///./test.db")
engine = create_engine(DATABASE_URL, connect_args={"check_same_thread": False} if "sqlite" in DATABASE_URL else {})

# ===== CORS =====
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ===== JWT =====
SECRET_KEY = "mysecretkey"
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 60
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="token")

# ===== Password =====
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

# ===== Models =====
class User(BaseModel):
    username: str
    password: str
    is_admin: bool = False

# ===== Create tables =====
with engine.begin() as conn:
    conn.execute(text("""
    CREATE TABLE IF NOT EXISTS users (
        username TEXT PRIMARY KEY,
        hashed_password TEXT,
        is_admin BOOLEAN DEFAULT FALSE
    );
    """))
    conn.execute(text("""
    CREATE TABLE IF NOT EXISTS products (
        sku TEXT PRIMARY KEY,
        name TEXT,
        is_active BOOLEAN DEFAULT TRUE
    );
    """))
    conn.execute(text("""
    CREATE TABLE IF NOT EXISTS warehouses (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT
    );
    """))
    conn.execute(text("""
    CREATE TABLE IF NOT EXISTS inventory (
        sku TEXT,
        warehouse_id INTEGER,
        quantity INTEGER DEFAULT 0,
        PRIMARY KEY(sku, warehouse_id)
    );
    """))
    conn.execute(text("""
    CREATE TABLE IF NOT EXISTS history (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        sku TEXT,
        type TEXT,
        quantity INTEGER,
        warehouse_id INTEGER,
        created_at TEXT
    );
    """))

# ===== Helper =====
def verify_password(plain, hashed):
    return pwd_context.verify(plain, hashed)

def get_password_hash(password):
    return pwd_context.hash(password)

def create_access_token(data: dict, expires_delta: timedelta = None):
    to_encode = data.copy()
    expire = datetime.utcnow() + (expires_delta or timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES))
    to_encode.update({"exp": expire})
    return jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)

def get_current_user(token: str = Depends(oauth2_scheme)):
    credentials_exception = HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Could not validate credentials")
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        username: str = payload.get("sub")
        if username is None:
            raise credentials_exception
        with engine.connect() as conn:
            user = conn.execute(text("SELECT * FROM users WHERE username=:username"), {"username": username}).fetchone()
            if not user:
                raise credentials_exception
        return {"username": username, "is_admin": user["is_admin"]}
    except JWTError:
        raise credentials_exception

# ===== Init admin =====
with engine.begin() as conn:
    admin = conn.execute(text("SELECT * FROM users WHERE username='admin'")).fetchone()
    if not admin:
        hashed = get_password_hash("admin1230")
        conn.execute(text("INSERT INTO users (username, hashed_password, is_admin) VALUES ('admin', :h, 1)"), {"h": hashed})

# ===== Routes =====
@app.post("/register")
def register(user: User, current_user: dict = Depends(get_current_user)):
    if not current_user["is_admin"]:
        raise HTTPException(status_code=403, detail="Only admin can create users")
    hashed = get_password_hash(user.password)
    with engine.begin() as conn:
        conn.execute(text("INSERT INTO users (username, hashed_password, is_admin) VALUES (:u,:p,:a)"),
                     {"u": user.username, "p": hashed, "a": user.is_admin})
    return {"msg": "User created"}

@app.post("/token")
def login(form_data: OAuth2PasswordRequestForm = Depends()):
    with engine.connect() as conn:
        user = conn.execute(text("SELECT * FROM users WHERE username=:u"), {"u": form_data.username}).fetchone()
        if not user or not verify_password(form_data.password, user["hashed_password"]):
            raise HTTPException(status_code=401, detail="Invalid credentials")
    access_token = create_access_token({"sub": form_data.username})
    return {"access_token": access_token, "token_type":"bearer"}

@app.get("/users/me")
def me(current_user: dict = Depends(get_current_user)):
    return current_user

# ===== Products =====
@app.get("/products")
def get_products(token: dict = Depends(get_current_user)):
    with engine.connect() as conn:
        res = conn.execute(text("SELECT * FROM products")).fetchall()
        return [{"sku": r[0], "name": r[1], "is_active": r[2]} for r in res]

@app.post("/products")
def create_product(prod: dict, token: dict = Depends(get_current_user)):
    with engine.begin() as conn:
        conn.execute(text("INSERT INTO products (sku,name) VALUES (:sku,:name)"), {"sku":prod["sku"], "name":prod["name"]})
    return {"msg":"Created"}

@app.put("/products/{sku}")
def update_product(sku:str, prod: dict, token: dict = Depends(get_current_user)):
    with engine.begin() as conn:
        conn.execute(text("UPDATE products SET name=:name WHERE sku=:sku"), {"name":prod["name"],"sku":sku})
    return {"msg":"Updated"}

@app.delete("/products/{sku}")
def delete_product(sku:str, token: dict = Depends(get_current_user)):
    with engine.begin() as conn:
        conn.execute(text("UPDATE products SET is_active=0 WHERE sku=:sku"), {"sku":sku})
    return {"msg":"Deleted"}

@app.post("/products/{sku}/recover")
def recover_product(sku:str, token: dict = Depends(get_current_user)):
    with engine.begin() as conn:
        conn.execute(text("UPDATE products SET is_active=1 WHERE sku=:sku"), {"sku":sku})
    return {"msg":"Recovered"}

# ===== Warehouses =====
@app.get("/warehouses")
def get_warehouses(token: dict = Depends(get_current_user)):
    with engine.connect() as conn:
        res = conn.execute(text("SELECT * FROM warehouses")).fetchall()
        return [{"id": r[0], "name": r[1]} for r in res]

@app.get("/inventory")
def get_inventory(token: dict = Depends(get_current_user)):
    with engine.connect() as conn:
        res = conn.execute(text("""
            SELECT w.name as warehouse, p.sku, p.name, COALESCE(i.quantity,0) as quantity
            FROM inventory i
            JOIN products p ON p.sku=i.sku
            JOIN warehouses w ON w.id=i.warehouse_id
            ORDER BY w.id, p.sku
        """)).fetchall()
        return [{"warehouse":r[0],"sku":r[1],"name":r[2],"quantity":r[3]} for r in res]

@app.get("/history")
def get_history(token: dict = Depends(get_current_user)):
    with engine.connect() as conn:
        res = conn.execute(text("SELECT * FROM history")).fetchall()
        return [{"id":r[0],"sku":r[1],"type":r[2],"quantity":r[3],"warehouse_id":r[4],"created_at":r[5]} for r in res]

# ===== PDF =====
@app.get("/invoice/pdf")
def pdf(sku: str, qty: int, type: str, token: dict = Depends(get_current_user)):
    buffer = io.BytesIO()
    c = canvas.Canvas(buffer)
    c.drawString(100, 800, f"PHIẾU {type.upper()}")
    c.drawString(100, 780, f"SKU: {sku}")
    c.drawString(100, 760, f"Số lượng: {qty}")
    c.drawString(100, 740, f"Ngày: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    c.save()
    buffer.seek(0)
    return StreamingResponse(buffer, media_type="application/pdf", headers={"Content-Disposition": f"attachment; filename=invoice_{sku}.pdf"})
