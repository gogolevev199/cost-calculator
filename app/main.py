import os
from pathlib import Path

import psycopg2
from fastapi import FastAPI
from fastapi.templating import Jinja2Templates
from fastapi import Request, Form
from fastapi.responses import HTMLResponse, RedirectResponse

app = FastAPI()
templates = Jinja2Templates(directory="templates")

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


@app.get("/", response_class=HTMLResponse)
def home(request: Request):

    with conn.cursor() as cursor:

        cursor.execute("SELECT COUNT(*) FROM materials")
        materials_count = cursor.fetchone()[0]

        cursor.execute("SELECT COUNT(*) FROM customers")
        customers_count = cursor.fetchone()[0]

        cursor.execute("SELECT COUNT(*) FROM transport_schemes")
        transport_schemes_count = cursor.fetchone()[0]

        cursor.execute("SELECT COUNT(*) FROM recipes")
        recipes_count = cursor.fetchone()[0]

        return templates.TemplateResponse(
            request,
            "dashboard.html",
            {
                "materials_count": materials_count,
                "customers_count": customers_count,
                "transport_schemes_count": transport_schemes_count,
                "recipes_count": recipes_count
            }
        )

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
@app.get("/materials-page", response_class=HTMLResponse)
def materials_page(request: Request):
    with conn.cursor() as cursor:
        cursor.execute("""
            SELECT
                m.id,
                m.name,
                m.supplier,
                m.fraction,
                mph.price AS current_price,
                mph.valid_from AS price_date
            FROM materials m
            LEFT JOIN LATERAL (
                SELECT price, valid_from
                FROM material_price_history
                WHERE material_id = m.id
                  AND valid_to IS NULL
                ORDER BY valid_from DESC
                LIMIT 1
            ) mph ON TRUE
            ORDER BY m.name
        """)
        rows = cursor.fetchall()

    materials = []
    for row in rows:
        materials.append({
            "id": row[0],
            "name": row[1],
            "supplier": row[2],
            "fraction": row[3],
            "current_price": float(row[4]) if row[4] is not None else None,
            "price_date": str(row[5]) if row[5] is not None else None,
        })

    return templates.TemplateResponse(
        request,
        "materials.html",
        {
            "materials": materials
        }
    )
@app.get("/materials/new", response_class=HTMLResponse)
def material_new_page(request: Request):
    return templates.TemplateResponse(
        request,
        "material_form.html",
        {}
    )


@app.post("/materials/new")
def material_create(
    name: str = Form(...),
    code: str = Form(""),
    unit: str = Form("t"),
    supplier: str = Form(""),
    fraction: str = Form(""),
    notes: str = Form("")
):
    with conn.cursor() as cursor:
        cursor.execute(
            """
            INSERT INTO materials (name, code, unit, supplier, fraction, notes)
            VALUES (%s, %s, %s, %s, %s, %s)
            """,
            (name, code, unit, supplier, fraction, notes)
        )

    return RedirectResponse(url="/materials-page", status_code=303)