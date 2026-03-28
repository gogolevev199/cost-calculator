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
@app.get("/materials/{material_id}/prices", response_class=HTMLResponse)
def material_prices(request: Request, material_id: str):

    with conn.cursor() as cursor:

        cursor.execute(
            "SELECT id, name FROM materials WHERE id = %s",
            (material_id,)
        )

        material_row = cursor.fetchone()

        if not material_row:
            return RedirectResponse("/materials-page", status_code=303)

        material = {
            "id": material_row[0],
            "name": material_row[1]
        }

        cursor.execute("""
            SELECT
                price,
                currency,
                valid_from,
                valid_to,
                comment
            FROM material_price_history
            WHERE material_id = %s
            ORDER BY valid_from DESC
        """, (material_id,))

        rows = cursor.fetchall()

    prices = []

    for row in rows:
        prices.append({
            "price": float(row[0]),
            "currency": row[1],
            "valid_from": str(row[2]),
            "valid_to": str(row[3]) if row[3] else None,
            "comment": row[4]
        })

    return templates.TemplateResponse(
        request,
        "material_prices.html",
        {
            "material": material,
            "prices": prices
        }
    )
@app.get("/materials/{material_id}/prices/new", response_class=HTMLResponse)
def material_price_new_page(request: Request, material_id: str):

    with conn.cursor() as cursor:
        cursor.execute(
            "SELECT id, name FROM materials WHERE id = %s",
            (material_id,)
        )
        material_row = cursor.fetchone()

    if not material_row:
        return RedirectResponse("/materials-page", status_code=303)

    material = {
        "id": material_row[0],
        "name": material_row[1]
    }

    return templates.TemplateResponse(
        request,
        "material_price_form.html",
        {
            "material": material
        }
    )


@app.post("/materials/{material_id}/prices/new")
def material_price_create(
    material_id: str,
    price: float = Form(...),
    currency: str = Form("RUB"),
    valid_from: str = Form(...),
    comment: str = Form("")
):
    with conn.cursor() as cursor:
        cursor.execute(
            "SELECT id FROM materials WHERE id = %s",
            (material_id,)
        )
        material_row = cursor.fetchone()

        if not material_row:
            return RedirectResponse("/materials-page", status_code=303)

        cursor.execute(
            """
            UPDATE material_price_history
            SET valid_to = %s::date - INTERVAL '1 day'
            WHERE material_id = %s
              AND valid_to IS NULL
            """,
            (valid_from, material_id)
        )

        cursor.execute(
            """
            INSERT INTO material_price_history
            (material_id, price, currency, valid_from, valid_to, comment)
            VALUES (%s, %s, %s, %s, NULL, %s)
            """,
            (material_id, price, currency, valid_from, comment)
        )

        cursor.execute(
            """
            UPDATE materials
            SET default_price = %s
            WHERE id = %s
            """,
            (price, material_id)
        )

    return RedirectResponse(
        url=f"/materials/{material_id}/prices",
        status_code=303
    )