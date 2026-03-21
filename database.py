from sqlalchemy import create_engine

DB_URL = "postgresql://postgres.acwzgbfrlqykqlhanfdi:Nhutren9989@aws-1-eu-central-1.pooler.supabase.com:5432/postgres"
engine = create_engine(DB_URL, pool_size=5, max_overflow=10, pool_pre_ping=True