from database import engine
from sqlalchemy import text

with engine.begin() as conn:
    # Tạo bảng
    conn.execute(text("""
    CREATE TABLE IF NOT EXISTS stores(
        id SERIAL PRIMARY KEY,
        name TEXT UNIQUE NOT NULL
    );
    CREATE TABLE IF NOT EXISTS products(
        id SERIAL PRIMARY KEY,
        sku TEXT UNIQUE NOT NULL,
        name TEXT NOT NULL,
        created_at TIMESTAMP WITH TIME ZONE DEFAULT now(),
        is_active BOOLEAN DEFAULT TRUE
    );
    CREATE TABLE IF NOT EXISTS users(
        id SERIAL PRIMARY KEY,
        username TEXT UNIQUE NOT NULL,
        password TEXT NOT NULL,
        role TEXT,
        store_id INTEGER REFERENCES stores(id)
    );
    CREATE TABLE IF NOT EXISTS warehouses(
        id SERIAL PRIMARY KEY,
        name TEXT UNIQUE NOT NULL
    );
    CREATE TABLE IF NOT EXISTS inventory(
        id SERIAL PRIMARY KEY,
        sku TEXT NOT NULL,
        warehouse_id INTEGER REFERENCES warehouses(id),
        quantity INTEGER NOT NULL DEFAULT 0,
        UNIQUE(sku, warehouse_id)
    );
    CREATE TABLE IF NOT EXISTS store_inventory(
        id SERIAL PRIMARY KEY,
        sku TEXT NOT NULL,
        store_id INTEGER REFERENCES stores(id),
        quantity INTEGER NOT NULL DEFAULT 0,
        UNIQUE(sku, store_id)
    );
    CREATE TABLE IF NOT EXISTS history(
        id SERIAL PRIMARY KEY,
        sku TEXT NOT NULL,
        type TEXT NOT NULL,
        quantity INTEGER NOT NULL,
        created_at TIMESTAMP WITH TIME ZONE DEFAULT now(),
        warehouse_id INTEGER REFERENCES warehouses(id),
        note TEXT
    );
    """))

    # Thêm dữ liệu mẫu nếu chưa có
    if conn.execute(text("SELECT COUNT(*) FROM warehouses")).fetchone()[0]==0:
        conn.execute(text("INSERT INTO warehouses(name) VALUES ('Kho La Pagode'),('Kho Muse'),('Kho Metz Ville'),('Kho Nancy')"))
    if conn.execute(text("SELECT COUNT(*) FROM stores")).fetchone()[0]==0:
        conn.execute(text("INSERT INTO stores(name) VALUES ('Muse'),('Metz Ville'),('Nancy')"))