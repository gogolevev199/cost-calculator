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
@app.get("/customers-page", response_class=HTMLResponse)
def customers_page(request: Request):
    with conn.cursor() as cursor:
        cursor.execute("""
            SELECT id, name, country, city, default_payment_delay_days
            FROM customers
            ORDER BY name
        """)
        rows = cursor.fetchall()

    customers = []
    for row in rows:
        customers.append({
            "id": row[0],
            "name": row[1],
            "country": row[2],
            "city": row[3],
            "delay": row[4],
        })

    return templates.TemplateResponse(
        request,
        "customers.html",
        {
            "customers": customers
        }
    )
@app.get("/customers/new", response_class=HTMLResponse)
def customer_new_page(request: Request):
    return templates.TemplateResponse(
        request,
        "customer_form.html",
        {}
    )


@app.post("/customers/new")
def customer_create(
    name: str = Form(...),
    code: str = Form(""),
    country: str = Form(""),
    region: str = Form(""),
    city: str = Form(""),
    address: str = Form(""),
    default_payment_delay_days: int = Form(0),
    notes: str = Form("")
):
    with conn.cursor() as cursor:
        cursor.execute(
            """
            INSERT INTO customers
            (name, code, country, region, city, address,
             default_payment_delay_days, notes)
            VALUES (%s,%s,%s,%s,%s,%s,%s,%s)
            """,
            (
                name,
                code,
                country,
                region,
                city,
                address,
                default_payment_delay_days,
                notes
            )
        )

    return RedirectResponse(
        url="/customers-page",
        status_code=303
    )
@app.get("/customers/{customer_id}/edit", response_class=HTMLResponse)
def customer_edit_page(request: Request, customer_id: str):
    with conn.cursor() as cursor:
        cursor.execute(
            """
            SELECT id, name, code, country, region, city, address,
                   default_payment_delay_days, notes
            FROM customers
            WHERE id = %s
            """,
            (customer_id,)
        )
        row = cursor.fetchone()

    if not row:
        return RedirectResponse(url="/customers-page", status_code=303)

    customer = {
        "id": row[0],
        "name": row[1],
        "code": row[2],
        "country": row[3],
        "region": row[4],
        "city": row[5],
        "address": row[6],
        "default_payment_delay_days": row[7],
        "notes": row[8],
    }

    return templates.TemplateResponse(
        request,
        "customer_form.html",
        {
            "customer": customer
        }
    )


@app.post("/customers/{customer_id}/edit")
def customer_update(
    customer_id: str,
    name: str = Form(...),
    code: str = Form(""),
    country: str = Form(""),
    region: str = Form(""),
    city: str = Form(""),
    address: str = Form(""),
    default_payment_delay_days: int = Form(0),
    notes: str = Form("")
):
    with conn.cursor() as cursor:
        cursor.execute(
            """
            UPDATE customers
            SET name = %s,
                code = %s,
                country = %s,
                region = %s,
                city = %s,
                address = %s,
                default_payment_delay_days = %s,
                notes = %s
            WHERE id = %s
            """,
            (
                name,
                code,
                country,
                region,
                city,
                address,
                default_payment_delay_days,
                notes,
                customer_id
            )
        )

    return RedirectResponse(url="/customers-page", status_code=303)
@app.get("/transport-page", response_class=HTMLResponse)
def transport_page(request: Request):
    with conn.cursor() as cursor:
        cursor.execute("""
            SELECT
                trh.id,
                c.name AS customer_name,
                ts.name AS scheme_name,
                trh.price,
                trh.currency,
                trh.price_per,
                trh.valid_from,
                trh.valid_to,
                trh.includes_loading,
                trh.includes_unloading,
                trh.includes_packaging
            FROM transport_rate_history trh
            JOIN customers c ON c.id = trh.customer_id
            JOIN transport_schemes ts ON ts.id = trh.transport_scheme_id
            ORDER BY trh.valid_from DESC, c.name, ts.name
        """)
        rows = cursor.fetchall()

    rates = []
    for row in rows:
        rates.append({
            "id": row[0],
            "customer_name": row[1],
            "scheme_name": row[2],
            "price": float(row[3]),
            "currency": row[4],
            "price_per": row[5],
            "valid_from": str(row[6]),
            "valid_to": str(row[7]) if row[7] else None,
            "includes_loading": row[8],
            "includes_unloading": row[9],
            "includes_packaging": row[10],
        })

    return templates.TemplateResponse(
        request,
        "transport_rates.html",
        {
            "rates": rates
        }
    )
@app.get("/transport-rates/new", response_class=HTMLResponse)
def transport_rate_new_page(request: Request):
    with conn.cursor() as cursor:
        cursor.execute("SELECT id, name FROM customers ORDER BY name")
        customer_rows = cursor.fetchall()

        cursor.execute("SELECT id, name FROM transport_schemes ORDER BY name")
        scheme_rows = cursor.fetchall()

    customers = [{"id": row[0], "name": row[1]} for row in customer_rows]
    schemes = [{"id": row[0], "name": row[1]} for row in scheme_rows]

    return templates.TemplateResponse(
        request,
        "transport_rate_form.html",
        {
            "customers": customers,
            "schemes": schemes,
            "rate": None
        }
    )


@app.post("/transport-rates/new")
def transport_rate_create(
    customer_id: str = Form(...),
    transport_scheme_id: str = Form(...),
    price: float = Form(...),
    currency: str = Form("RUB"),
    price_per: str = Form("trip"),
    valid_from: str = Form(...),
    valid_to: str = Form(""),
    includes_loading: str | None = Form(None),
    includes_unloading: str | None = Form(None),
    includes_packaging: str | None = Form(None),
    notes: str = Form("")
):
    with conn.cursor() as cursor:
        cursor.execute(
            """
            INSERT INTO transport_rate_history
            (
                customer_id,
                transport_scheme_id,
                price,
                currency,
                price_per,
                valid_from,
                valid_to,
                includes_loading,
                includes_unloading,
                includes_packaging,
                notes
            )
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
            """,
            (
                customer_id,
                transport_scheme_id,
                price,
                currency,
                price_per,
                valid_from,
                valid_to if valid_to else None,
                includes_loading is not None,
                includes_unloading is not None,
                includes_packaging is not None,
                notes
            )
        )

    return RedirectResponse(url="/transport-page", status_code=303)