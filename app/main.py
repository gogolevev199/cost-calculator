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


def execute_sql_file(filename: str) -> None:
    root_dir = Path(__file__).resolve().parent.parent
    file_path = root_dir / filename

    if not file_path.exists():
        return

    with open(file_path, "r", encoding="utf-8") as f:
        sql = f.read()

    with conn.cursor() as cursor:
        cursor.execute(sql)


execute_sql_file("schema.sql")
execute_sql_file("seed.sql")


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


@app.get("/transport-types")
def transport_types():
    with conn.cursor() as cursor:
        cursor.execute("SELECT id, name, code FROM transport_types ORDER BY name")
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


@app.get("/transport-extra-cost-types")
def transport_extra_cost_types():
    with conn.cursor() as cursor:
        cursor.execute("SELECT id, name, code FROM transport_extra_cost_types ORDER BY name")
        rows = cursor.fetchall()
    return rows


@app.get("/users")
def users():
    with conn.cursor() as cursor:
        cursor.execute("SELECT id, login, full_name, role, is_active FROM users ORDER BY login")
        rows = cursor.fetchall()
    return rows