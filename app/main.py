import os
from pathlib import Path

import psycopg2
from fastapi import FastAPI

app = FastAPI()

DATABASE_URL = os.getenv("DATABASE_URL")
if not DATABASE_URL:
    raise RuntimeError("DATABASE_URL is not set")

conn = psycopg2.connect(DATABASE_URL)
conn.autocommit = True

def apply_schema() -> None:
    root_dir = Path(__file__).resolve().parent.parent
    schema_path = root_dir / "schema.sql"

    with open(schema_path, "r", encoding="utf-8") as f:
        sql = f.read()

    with conn.cursor() as cursor:
        cursor.execute(sql)

apply_schema()

@app.get("/")
def home():
    return {"status": "Cost calculator 3.1 running"}

@app.get("/health")
def health():
    return {"ok": True}

@app.get("/materials")
def materials():
    with conn.cursor() as cursor:
        cursor.execute("SELECT id, name, default_price FROM materials ORDER BY name")
        rows = cursor.fetchall()
    return rows

@app.get("/customers")
def customers():
    with conn.cursor() as cursor:
        cursor.execute("SELECT id, name, city FROM customers ORDER BY name")
        rows = cursor.fetchall()
    return rows

@app.get("/transport-schemes")
def transport_schemes():
    with conn.cursor() as cursor:
        cursor.execute("""
            SELECT ts.id, ts.name, ts.capacity_tons, tt.name
            FROM transport_schemes ts
            LEFT JOIN transport_types tt ON tt.id = ts.transport_type_id
            ORDER BY ts.name
        """)
        rows = cursor.fetchall()
    return rows