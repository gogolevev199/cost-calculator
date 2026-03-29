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
        UPDATE transport_rate_history
        SET valid_to = %s::date - INTERVAL '1 day'
        WHERE customer_id = %s
          AND transport_scheme_id = %s
          AND valid_to IS NULL
        """,
        (
            valid_from,
            customer_id,
            transport_scheme_id
        )
        )

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
@app.get("/transport-rates/{rate_id}/edit", response_class=HTMLResponse)
def transport_rate_edit_page(request: Request, rate_id: str):
    with conn.cursor() as cursor:
        cursor.execute("SELECT id, name FROM customers ORDER BY name")
        customer_rows = cursor.fetchall()

        cursor.execute("SELECT id, name FROM transport_schemes ORDER BY name")
        scheme_rows = cursor.fetchall()

        cursor.execute(
            """
            SELECT
                id,
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
            FROM transport_rate_history
            WHERE id = %s
            """,
            (rate_id,)
        )
        row = cursor.fetchone()

    if not row:
        return RedirectResponse(url="/transport-page", status_code=303)

    customers = [{"id": r[0], "name": r[1]} for r in customer_rows]
    schemes = [{"id": r[0], "name": r[1]} for r in scheme_rows]

    rate = {
        "id": row[0],
        "customer_id": row[1],
        "transport_scheme_id": row[2],
        "price": float(row[3]),
        "currency": row[4],
        "price_per": row[5],
        "valid_from": str(row[6]) if row[6] else "",
        "valid_to": str(row[7]) if row[7] else "",
        "includes_loading": row[8],
        "includes_unloading": row[9],
        "includes_packaging": row[10],
        "notes": row[11] or "",
    }

    return templates.TemplateResponse(
        request,
        "transport_rate_form.html",
        {
            "customers": customers,
            "schemes": schemes,
            "rate": rate
        }
    )


@app.post("/transport-rates/{rate_id}/edit")
def transport_rate_update(
    rate_id: str,
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
            UPDATE transport_rate_history
            SET customer_id = %s,
                transport_scheme_id = %s,
                price = %s,
                currency = %s,
                price_per = %s,
                valid_from = %s,
                valid_to = %s,
                includes_loading = %s,
                includes_unloading = %s,
                includes_packaging = %s,
                notes = %s
            WHERE id = %s
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
                notes,
                rate_id
            )
        )

    return RedirectResponse(url="/transport-page", status_code=303)
@app.get("/recipes-page", response_class=HTMLResponse)
def recipes_page(request: Request):

    with conn.cursor() as cursor:
        cursor.execute("""
            SELECT
                r.id,
                r.name,
                r.code,
                r.description,
                COUNT(rv.id) as versions_count
            FROM recipes r
            LEFT JOIN recipe_versions rv
                ON rv.recipe_id = r.id
            GROUP BY r.id
            ORDER BY r.name
        """)

        rows = cursor.fetchall()

    recipes = []

    for row in rows:
        recipes.append({
            "id": row[0],
            "name": row[1],
            "code": row[2],
            "description": row[3],
            "versions_count": row[4]
        })

    return templates.TemplateResponse(
        request,
        "recipes.html",
        {
            "recipes": recipes
        }
    )
@app.get("/recipes/new", response_class=HTMLResponse)
def recipe_new_page(request: Request):
    return templates.TemplateResponse(
        request,
        "recipe_form.html",
        {}
    )


@app.post("/recipes/new")
def recipe_create(
    name: str = Form(...),
    code: str = Form(""),
    description: str = Form("")
):
    with conn.cursor() as cursor:
        cursor.execute(
            """
            INSERT INTO recipes (name, code, description)
            VALUES (%s, %s, %s)
            """,
            (name, code, description)
        )

    return RedirectResponse(url="/recipes-page", status_code=303)
@app.get("/recipes/{recipe_id}/versions", response_class=HTMLResponse)
def recipe_versions_page(request: Request, recipe_id: str):

    with conn.cursor() as cursor:

        cursor.execute(
            "SELECT id, name FROM recipes WHERE id = %s",
            (recipe_id,)
        )

        recipe_row = cursor.fetchone()

        if not recipe_row:
            return RedirectResponse("/recipes-page", status_code=303)

        recipe = {
            "id": recipe_row[0],
            "name": recipe_row[1]
        }

        cursor.execute("""
            SELECT
                id,
                version_number,
                version_name,
                status,
                comment,
                created_at
            FROM recipe_versions
            WHERE recipe_id = %s
            ORDER BY created_at DESC
        """, (recipe_id,))

        rows = cursor.fetchall()

    versions = []

    for row in rows:
        versions.append({
            "id": row[0],
            "version_number": row[1],
            "version_name": row[2],
            "status": row[3],
            "comment": row[4],
            "created_at": str(row[5])
        })

    return templates.TemplateResponse(
        request,
        "recipe_versions.html",
        {
            "recipe": recipe,
            "versions": versions
        }
    )
@app.get("/recipes/{recipe_id}/versions/new", response_class=HTMLResponse)
def recipe_version_new_page(request: Request, recipe_id: str):

    with conn.cursor() as cursor:

        cursor.execute(
            "SELECT id, name FROM recipes WHERE id = %s",
            (recipe_id,)
        )

        recipe_row = cursor.fetchone()

        if not recipe_row:
            return RedirectResponse("/recipes-page", status_code=303)

        recipe = {
            "id": recipe_row[0],
            "name": recipe_row[1]
        }

        cursor.execute("""
            SELECT COALESCE(MAX(version_number),0) + 1
            FROM recipe_versions
            WHERE recipe_id = %s
        """, (recipe_id,))

        next_version_number = cursor.fetchone()[0]

    return templates.TemplateResponse(
        request,
        "recipe_version_form.html",
        {
            "recipe": recipe,
            "next_version_number": next_version_number
        }
    )


@app.post("/recipes/{recipe_id}/versions/new")
def recipe_version_create(
    recipe_id: str,
    version_number: int = Form(...),
    version_name: str = Form(""),
    status: str = Form("draft"),
    comment: str = Form("")
):
    with conn.cursor() as cursor:
        cursor.execute(
            """
            INSERT INTO recipe_versions
            (recipe_id, version_number, version_name, status, comment)
            VALUES (%s,%s,%s,%s,%s)
            """,
            (
                recipe_id,
                version_number,
                version_name,
                status,
                comment
            )
        )

    return RedirectResponse(
        url=f"/recipes/{recipe_id}/versions",
        status_code=303
    )
@app.get("/recipe-versions/{version_id}/items", response_class=HTMLResponse)
def recipe_version_items_page(request: Request, version_id: str):

    with conn.cursor() as cursor:

        cursor.execute("""
            SELECT
                rv.id,
                rv.version_number,
                rv.version_name,
                r.id,
                r.name
            FROM recipe_versions rv
            JOIN recipes r ON r.id = rv.recipe_id
            WHERE rv.id = %s
        """, (version_id,))

        row = cursor.fetchone()

        if not row:
            return RedirectResponse("/recipes-page", status_code=303)

        version = {
            "id": row[0],
            "version_number": row[1],
            "version_name": row[2]
        }

        recipe = {
            "id": row[3],
            "name": row[4]
        }

        cursor.execute("""
            SELECT
                ri.id,
                m.name,
                ri.quantity,
                (
                    SELECT COUNT(*)
                    FROM recipe_item_processes rip
                    WHERE rip.recipe_item_id = ri.id
                ) as process_count
            FROM recipe_items ri
            JOIN materials m ON m.id = ri.material_id
            WHERE ri.recipe_version_id = %s
            ORDER BY m.name
        """, (version_id,))

        rows = cursor.fetchall()

    items = []

    for row in rows:
        items.append({
            "id": row[0],
            "material_name": row[1],
            "quantity": float(row[2]),
            "process_count": row[3]
        })

    return templates.TemplateResponse(
        request,
        "recipe_version_items.html",
        {
            "recipe": recipe,
            "version": version,
            "items": items
        }
    )
@app.get("/recipe-versions/{version_id}/items/new", response_class=HTMLResponse)
def recipe_item_new_page(request: Request, version_id: str):

    with conn.cursor() as cursor:
        cursor.execute("""
            SELECT
                rv.id,
                rv.version_number,
                rv.version_name,
                r.id,
                r.name
            FROM recipe_versions rv
            JOIN recipes r ON r.id = rv.recipe_id
            WHERE rv.id = %s
        """, (version_id,))

        row = cursor.fetchone()

        if not row:
            return RedirectResponse("/recipes-page", status_code=303)

        version = {
            "id": row[0],
            "version_number": row[1],
            "version_name": row[2]
        }

        recipe = {
            "id": row[3],
            "name": row[4]
        }

        cursor.execute("""
            SELECT id, name
            FROM materials
            WHERE is_active = TRUE
            ORDER BY name
        """)
        material_rows = cursor.fetchall()

    materials = [{"id": r[0], "name": r[1]} for r in material_rows]

    return templates.TemplateResponse(
        request,
        "recipe_item_form.html",
        {
            "recipe": recipe,
            "version": version,
            "materials": materials
        }
    )


@app.post("/recipe-versions/{version_id}/items/new")
def recipe_item_create(
    version_id: str,
    material_id: str = Form(...),
    quantity: float = Form(...)
):
    with conn.cursor() as cursor:
        cursor.execute(
            """
            INSERT INTO recipe_items (recipe_version_id, material_id, quantity)
            VALUES (%s, %s, %s)
            """,
            (version_id, material_id, quantity)
        )

    return RedirectResponse(
        url=f"/recipe-versions/{version_id}/items",
        status_code=303
    )

@app.get("/recipe-items/{item_id}/processes", response_class=HTMLResponse)
def recipe_item_processes_page(request: Request, item_id: str):

    with conn.cursor() as cursor:
        cursor.execute("""
            SELECT
                ri.id,
                ri.quantity,
                m.name,
                rv.id,
                rv.version_number,
                rv.version_name,
                r.id,
                r.name
            FROM recipe_items ri
            JOIN materials m ON m.id = ri.material_id
            JOIN recipe_versions rv ON rv.id = ri.recipe_version_id
            JOIN recipes r ON r.id = rv.recipe_id
            WHERE ri.id = %s
        """, (item_id,))

        row = cursor.fetchone()

        if not row:
            return RedirectResponse("/recipes-page", status_code=303)

        item = {
            "id": row[0],
            "quantity": float(row[1]),
            "material_name": row[2]
        }

        version = {
            "id": row[3],
            "version_number": row[4],
            "version_name": row[5]
        }

        recipe = {
            "id": row[6],
            "name": row[7]
        }

        cursor.execute("""
            SELECT
                rip.id,
                rip.sort_order,
                p.name,
                rip.loss_coefficient
            FROM recipe_item_processes rip
            JOIN processes p ON p.id = rip.process_id
            WHERE rip.recipe_item_id = %s
            ORDER BY rip.sort_order, p.name
        """, (item_id,))

        process_rows = cursor.fetchall()

    processes = []
    for p in process_rows:
        processes.append({
            "id": p[0],
            "sort_order": p[1],
            "process_name": p[2],
            "loss_coefficient": float(p[3])
        })

    return templates.TemplateResponse(
        request,
        "recipe_item_processes.html",
        {
            "recipe": recipe,
            "version": version,
            "item": item,
            "processes": processes
        }
    )
@app.get("/recipe-items/{item_id}/processes/new", response_class=HTMLResponse)
def recipe_item_process_new_page(request: Request, item_id: str):
    with conn.cursor() as cursor:
        cursor.execute("""
            SELECT
                ri.id,
                m.name,
                rv.id,
                rv.version_number,
                rv.version_name
            FROM recipe_items ri
            JOIN materials m ON m.id = ri.material_id
            JOIN recipe_versions rv ON rv.id = ri.recipe_version_id
            WHERE ri.id = %s
        """, (item_id,))
        row = cursor.fetchone()

        if not row:
            return RedirectResponse("/recipes-page", status_code=303)

        item = {
            "id": row[0],
            "material_name": row[1]
        }

        version = {
            "id": row[2],
            "version_number": row[3],
            "version_name": row[4]
        }

        cursor.execute("""
            SELECT id, name
            FROM processes
            WHERE is_active = TRUE
            ORDER BY name
        """)
        process_rows = cursor.fetchall()

        cursor.execute("""
            SELECT COALESCE(MAX(sort_order), 0) + 1
            FROM recipe_item_processes
            WHERE recipe_item_id = %s
        """, (item_id,))
        next_sort_order = cursor.fetchone()[0]

    processes = [{"id": r[0], "name": r[1]} for r in process_rows]

    return templates.TemplateResponse(
        request,
        "recipe_item_process_form.html",
        {
            "item": item,
            "version": version,
            "processes": processes,
            "next_sort_order": next_sort_order
        }
    )


@app.post("/recipe-items/{item_id}/processes/new")
def recipe_item_process_create(
    item_id: str,
    process_id: str = Form(...),
    sort_order: int = Form(...),
    loss_coefficient: float = Form(...),
    comment: str = Form("")
):
    with conn.cursor() as cursor:
        cursor.execute(
            """
            INSERT INTO recipe_item_processes
            (recipe_item_id, process_id, sort_order, loss_coefficient, comment)
            VALUES (%s, %s, %s, %s, %s)
            """,
            (item_id, process_id, sort_order, loss_coefficient, comment)
        )

    return RedirectResponse(
        url=f"/recipe-items/{item_id}/processes",
        status_code=303
    )
@app.get("/processes-page", response_class=HTMLResponse)
def processes_page(request: Request):
    with conn.cursor() as cursor:
        cursor.execute("""
            SELECT
                p.id,
                p.name,
                p.code,
                pch.cost AS current_cost,
                pch.valid_from AS cost_date
            FROM processes p
            LEFT JOIN LATERAL (
                SELECT cost, valid_from
                FROM process_cost_history
                WHERE process_id = p.id
                  AND valid_to IS NULL
                ORDER BY valid_from DESC
                LIMIT 1
            ) pch ON TRUE
            ORDER BY p.name
        """)
        rows = cursor.fetchall()

    processes = []
    for row in rows:
        processes.append({
            "id": row[0],
            "name": row[1],
            "code": row[2],
            "current_cost": float(row[3]) if row[3] is not None else None,
            "cost_date": str(row[4]) if row[4] is not None else None,
        })

    return templates.TemplateResponse(
        request,
        "processes.html",
        {
            "processes": processes
        }
    )
@app.get("/processes/new", response_class=HTMLResponse)
def process_new_page(request: Request):
    return templates.TemplateResponse(
        request,
        "process_form.html",
        {}
    )


@app.post("/processes/new")
def process_create(
    name: str = Form(...),
    code: str = Form(""),
    description: str = Form("")
):
    with conn.cursor() as cursor:
        cursor.execute(
            """
            INSERT INTO processes (name, code, notes)
            VALUES (%s, %s, %s)
            """,
            (
                name,
                code,
                description
            )
        )

    return RedirectResponse(
        url="/processes-page",
        status_code=303
    )
@app.get("/processes/{process_id}/costs", response_class=HTMLResponse)
def process_costs_page(request: Request, process_id: str):
    with conn.cursor() as cursor:
        cursor.execute(
            "SELECT id, name FROM processes WHERE id = %s",
            (process_id,)
        )
        process_row = cursor.fetchone()

        if not process_row:
            return RedirectResponse("/processes-page", status_code=303)

        process = {
            "id": process_row[0],
            "name": process_row[1]
        }

        cursor.execute("""
            SELECT
                cost,
                currency,
                valid_from,
                valid_to,
                comment
            FROM process_cost_history
            WHERE process_id = %s
            ORDER BY valid_from DESC
        """, (process_id,))
        rows = cursor.fetchall()

    costs = []
    for row in rows:
        costs.append({
            "cost": float(row[0]),
            "currency": row[1],
            "valid_from": str(row[2]),
            "valid_to": str(row[3]) if row[3] else None,
            "comment": row[4]
        })

    return templates.TemplateResponse(
        request,
        "process_costs.html",
        {
            "process": process,
            "costs": costs
        }
    )
@app.get("/processes/{process_id}/costs/new", response_class=HTMLResponse)
def process_cost_new_page(request: Request, process_id: str):
    with conn.cursor() as cursor:
        cursor.execute(
            "SELECT id, name FROM processes WHERE id = %s",
            (process_id,)
        )
        process_row = cursor.fetchone()

    if not process_row:
        return RedirectResponse("/processes-page", status_code=303)

    process = {
        "id": process_row[0],
        "name": process_row[1]
    }

    return templates.TemplateResponse(
        request,
        "process_cost_form.html",
        {
            "process": process
        }
    )


@app.post("/processes/{process_id}/costs/new")
def process_cost_create(
    process_id: str,
    cost: float = Form(...),
    currency: str = Form("RUB"),
    valid_from: str = Form(...),
    comment: str = Form("")
):
    with conn.cursor() as cursor:
        cursor.execute(
            "SELECT id FROM processes WHERE id = %s",
            (process_id,)
        )
        process_row = cursor.fetchone()

        if not process_row:
            return RedirectResponse("/processes-page", status_code=303)

        cursor.execute(
            """
            UPDATE process_cost_history
            SET valid_to = %s::date - INTERVAL '1 day'
            WHERE process_id = %s
              AND valid_to IS NULL
            """,
            (valid_from, process_id)
        )

        cursor.execute(
            """
            INSERT INTO process_cost_history
            (process_id, cost, currency, valid_from, valid_to, comment)
            VALUES (%s, %s, %s, %s, NULL, %s)
            """,
            (process_id, cost, currency, valid_from, comment)
        )

        cursor.execute(
            """
            UPDATE processes
            SET default_cost = %s
            WHERE id = %s
            """,
            (cost, process_id)
        )

    return RedirectResponse(
        url=f"/processes/{process_id}/costs",
        status_code=303
    )
@app.get("/recipe-versions/{version_id}/calculate", response_class=HTMLResponse)
def recipe_version_calculate_page(
    request: Request,
    version_id: str,
    overhead_percent: float = 20.0,
    mixing_cost_per_ton: float = 0.0,
    packaging_type_id: str | None = None,
    customer_id: str | None = None,
    transport_scheme_id: str | None = None
):
    with conn.cursor() as cursor:
        cursor.execute("""
            SELECT
                rv.id,
                rv.version_number,
                rv.version_name,
                r.id,
                r.name
            FROM recipe_versions rv
            JOIN recipes r ON r.id = rv.recipe_id
            WHERE rv.id = %s
        """, (version_id,))
        row = cursor.fetchone()

        if not row:
            return RedirectResponse("/recipes-page", status_code=303)

        version = {
            "id": row[0],
            "version_number": row[1],
            "version_name": row[2]
        }

        recipe = {
            "id": row[3],
            "name": row[4]
        }

        cursor.execute("""
            SELECT id, name, capacity_value, capacity_unit, cost_per_ton, package_price
            FROM packaging_types
            WHERE is_active = TRUE
            ORDER BY name
        """)
        packaging_rows = cursor.fetchall()

        packaging_types = []
        for p in packaging_rows:
            packaging_types.append({
                "id": p[0],
                "name": p[1],
                "capacity_value": float(p[2]) if p[2] is not None else None,
                "capacity_unit": p[3],
                "cost_per_ton": float(p[4]),
                "package_price": float(p[5]),
            })

        cursor.execute("""
            SELECT id, name
            FROM customers
            ORDER BY name
        """)
        customer_rows = cursor.fetchall()

        customers = []
        for c in customer_rows:
            customers.append({
                "id": c[0],
                "name": c[1]
            })

        cursor.execute("""
            SELECT
                ts.id,
                ts.name,
                ts.capacity_tons,
                tt.name
            FROM transport_schemes ts
            LEFT JOIN transport_types tt ON tt.id = ts.transport_type_id
            WHERE ts.is_active = TRUE
            ORDER BY ts.name
        """)
        transport_rows = cursor.fetchall()

        transport_schemes = []
        for t in transport_rows:
            transport_schemes.append({
                "id": t[0],
                "name": t[1],
                "capacity_tons": float(t[2]) if t[2] is not None else None,
                "transport_type": t[3]
            })

        selected_packaging = None
        if packaging_type_id:
            cursor.execute("""
                SELECT id, name, capacity_value, capacity_unit, cost_per_ton, package_price
                FROM packaging_types
                WHERE id = %s
            """, (packaging_type_id,))
            p = cursor.fetchone()
            if p:
                selected_packaging = {
                    "id": p[0],
                    "name": p[1],
                    "capacity_value": float(p[2]) if p[2] is not None else None,
                    "capacity_unit": p[3],
                    "cost_per_ton": float(p[4]),
                    "package_price": float(p[5]),
                }

        selected_transport_scheme = None
        if transport_scheme_id:
            cursor.execute("""
                SELECT
                    ts.id,
                    ts.name,
                    ts.capacity_tons,
                    tt.name
                FROM transport_schemes ts
                LEFT JOIN transport_types tt ON tt.id = ts.transport_type_id
                WHERE ts.id = %s
            """, (transport_scheme_id,))
            t = cursor.fetchone()
            if t:
                selected_transport_scheme = {
                    "id": t[0],
                    "name": t[1],
                    "capacity_tons": float(t[2]) if t[2] is not None else None,
                    "transport_type": t[3]
                }

        selected_transport_rate = None
        if customer_id and transport_scheme_id:
            cursor.execute("""
                SELECT
                    price,
                    currency,
                    price_per,
                    valid_from,
                    valid_to,
                    includes_loading,
                    includes_unloading,
                    includes_packaging
                FROM transport_rate_history
                WHERE customer_id = %s
                  AND transport_scheme_id = %s
                  AND valid_to IS NULL
                ORDER BY valid_from DESC
                LIMIT 1
            """, (customer_id, transport_scheme_id))
            tr = cursor.fetchone()
            if tr:
                selected_transport_rate = {
                    "price": float(tr[0]),
                    "currency": tr[1],
                    "price_per": tr[2],
                    "valid_from": str(tr[3]) if tr[3] else None,
                    "valid_to": str(tr[4]) if tr[4] else None,
                    "includes_loading": tr[5],
                    "includes_unloading": tr[6],
                    "includes_packaging": tr[7],
                }

        cursor.execute("""
            SELECT
                ri.id,
                m.id,
                m.name,
                ri.quantity,
                COALESCE(mp.price, m.default_price, 0) AS material_price
            FROM recipe_items ri
            JOIN materials m ON m.id = ri.material_id
            LEFT JOIN LATERAL (
                SELECT price
                FROM material_price_history
                WHERE material_id = m.id
                  AND valid_to IS NULL
                ORDER BY valid_from DESC
                LIMIT 1
            ) mp ON TRUE
            WHERE ri.recipe_version_id = %s
            ORDER BY m.name
        """, (version_id,))
        item_rows = cursor.fetchall()

    items = []
    direct_cost = 0.0
    total_final_quantity = 0.0

    for row in item_rows:
        item_id = row[0]
        material_name = row[2]
        base_quantity = float(row[3])
        material_price = float(row[4] or 0)

        with conn.cursor() as cursor:
            cursor.execute("""
                SELECT
                    rip.loss_coefficient,
                    COALESCE(pch.cost, p.default_cost, 0) AS process_cost
                FROM recipe_item_processes rip
                JOIN processes p ON p.id = rip.process_id
                LEFT JOIN LATERAL (
                    SELECT cost
                    FROM process_cost_history
                    WHERE process_id = p.id
                      AND valid_to IS NULL
                    ORDER BY valid_from DESC
                    LIMIT 1
                ) pch ON TRUE
                WHERE rip.recipe_item_id = %s
                ORDER BY rip.sort_order, p.name
            """, (item_id,))
            process_rows = cursor.fetchall()

        total_loss = 1.0
        total_process_cost = 0.0

        for p in process_rows:
            total_loss *= float(p[0] or 1)
            total_process_cost += float(p[1] or 0)

        final_quantity = base_quantity * total_loss
        material_cost = final_quantity * material_price
        process_cost = final_quantity * total_process_cost
        total_item_cost = material_cost + process_cost

        direct_cost += total_item_cost
        total_final_quantity += final_quantity

        items.append({
            "material_name": material_name,
            "base_quantity": round(base_quantity, 6),
            "total_loss": round(total_loss, 6),
            "final_quantity": round(final_quantity, 6),
            "material_price": round(material_price, 2),
            "material_cost": round(material_cost, 2),
            "total_process_cost": round(total_process_cost, 2),
            "process_cost": round(process_cost, 2),
            "total_cost": round(total_item_cost, 2),
        })

    mixing_cost_total = total_final_quantity * mixing_cost_per_ton

    packaging_work_cost_total = 0.0
    packaging_material_cost_total = 0.0
    package_count = 0.0

    if selected_packaging:
        packaging_work_cost_total = total_final_quantity * selected_packaging["cost_per_ton"]

        capacity_value = selected_packaging["capacity_value"]
        capacity_unit = selected_packaging["capacity_unit"]

        if capacity_value and capacity_value > 0:
            capacity_tons = None

            if capacity_unit == "т":
                capacity_tons = capacity_value
            elif capacity_unit in ("kg", "кг"):
                capacity_tons = capacity_value / 1000.0

            if capacity_tons and capacity_tons > 0:
                package_count = total_final_quantity / capacity_tons
                packaging_material_cost_total = package_count * selected_packaging["package_price"]

    transport_cost_total = 0.0
    transport_units_count = 0.0
    transport_cost_per_ton = 0.0

    if selected_transport_rate and selected_transport_scheme and total_final_quantity > 0:
        price = selected_transport_rate["price"]
        price_per = selected_transport_rate["price_per"]
        capacity_tons = selected_transport_scheme["capacity_tons"]

        if price_per == "ton":
            transport_cost_total = total_final_quantity * price
            transport_cost_per_ton = price

        elif price_per in ("trip", "wagon"):
            if capacity_tons and capacity_tons > 0:
                transport_units_count = total_final_quantity / capacity_tons
                transport_cost_total = transport_units_count * price
                transport_cost_per_ton = transport_cost_total / total_final_quantity if total_final_quantity > 0 else 0.0

    overhead_base = (
        direct_cost
        + mixing_cost_total
        + packaging_work_cost_total
        + packaging_material_cost_total
        + transport_cost_total
    )
    overhead_cost = overhead_base * overhead_percent / 100.0
    total_cost = overhead_base + overhead_cost

    return templates.TemplateResponse(
        request,
        "recipe_version_calculation.html",
        {
            "recipe": recipe,
            "version": version,
            "items": items,
            "packaging_types": packaging_types,
            "selected_packaging_type_id": packaging_type_id,
            "selected_packaging": selected_packaging,
            "customers": customers,
            "selected_customer_id": customer_id,
            "transport_schemes": transport_schemes,
            "selected_transport_scheme_id": transport_scheme_id,
            "selected_transport_scheme": selected_transport_scheme,
            "selected_transport_rate": selected_transport_rate,
            "overhead_percent": overhead_percent,
            "mixing_cost_per_ton": mixing_cost_per_ton,
            "direct_cost": round(direct_cost, 2),
            "mixing_cost_total": round(mixing_cost_total, 2),
            "packaging_work_cost_total": round(packaging_work_cost_total, 2),
            "packaging_material_cost_total": round(packaging_material_cost_total, 2),
            "package_count": round(package_count, 3),
            "transport_units_count": round(transport_units_count, 3),
            "transport_cost_per_ton": round(transport_cost_per_ton, 2),
            "transport_cost_total": round(transport_cost_total, 2),
            "overhead_cost": round(overhead_cost, 2),
            "total_cost": round(total_cost, 2),
        }
    )
@app.get("/packaging-page", response_class=HTMLResponse)
def packaging_page(request: Request):
    with conn.cursor() as cursor:
        cursor.execute("""
            SELECT id, name, code, capacity_value, capacity_unit, cost_per_ton, package_price
            FROM packaging_types
            WHERE is_active = TRUE
            ORDER BY name
        """)
        rows = cursor.fetchall()

    packaging_types = []
    for row in rows:
        packaging_types.append({
            "id": row[0],
            "name": row[1],
            "code": row[2],
            "capacity_value": float(row[3]) if row[3] is not None else None,
            "capacity_unit": row[4],
            "cost_per_ton": float(row[5]),
            "package_price": float(row[6]),
        })

    return templates.TemplateResponse(
        request,
        "packaging_types.html",
        {
            "packaging_types": packaging_types
        }
    )
@app.get("/packaging-types/new", response_class=HTMLResponse)
def packaging_type_new_page(request: Request):
    return templates.TemplateResponse(
        request,
        "packaging_type_form.html",
        {}
    )


@app.post("/packaging-types/new")
def packaging_type_create(
    name: str = Form(...),
    code: str = Form(""),
    capacity_value: float | None = Form(None),
    capacity_unit: str = Form(""),
    cost_per_ton: float = Form(...),
    package_price: float = Form(...)
):
    with conn.cursor() as cursor:
        cursor.execute(
            """
            INSERT INTO packaging_types
            (name, code, capacity_value, capacity_unit, cost_per_ton, package_price)
            VALUES (%s, %s, %s, %s, %s, %s)
            """,
            (
                name,
                code,
                capacity_value,
                capacity_unit,
                cost_per_ton,
                package_price
            )
        )

    return RedirectResponse(
        url="/packaging-page",
        status_code=303
    )
@app.get("/saved-calculations-page", response_class=HTMLResponse)
def saved_calculations_page(request: Request):
    with conn.cursor() as cursor:
        cursor.execute("""
            SELECT
                id,
                recipe_name_snapshot,
                customer_name_snapshot,
                version_number_snapshot,
                version_name_snapshot,
                packaging_name_snapshot,
                transport_scheme_name_snapshot,
                overhead_percent,
                total_cost,
                created_at
            FROM saved_calculations
            ORDER BY created_at DESC
        """)
        rows = cursor.fetchall()

    calculations = []
    for row in rows:
        calculations.append({
            "id": row[0],
            "recipe_name": row[1],
            "customer_name": row[2],
            "version_number": row[3],
            "version_name": row[4],
            "packaging_name": row[5],
            "transport_scheme_name": row[6],
            "overhead_percent": float(row[7]),
            "total_cost": float(row[8]),
            "created_at": str(row[9]),
        })

    return templates.TemplateResponse(
        request,
        "saved_calculations.html",
        {
            "calculations": calculations
        }
    )
@app.post("/recipe-versions/{version_id}/save-calculation")
def save_recipe_version_calculation(
    version_id: str,
    overhead_percent: float = Form(...),
    mixing_cost_per_ton: float = Form(...),
    packaging_type_id: str = Form(""),
    customer_id: str = Form(""),
    transport_scheme_id: str = Form("")
):
    with conn.cursor() as cursor:
        cursor.execute("""
            SELECT
                rv.id,
                rv.version_number,
                rv.version_name,
                r.id,
                r.name
            FROM recipe_versions rv
            JOIN recipes r ON r.id = rv.recipe_id
            WHERE rv.id = %s
        """, (version_id,))
        row = cursor.fetchone()

        if not row:
            return RedirectResponse("/recipes-page", status_code=303)

        recipe_version_id = row[0]
        version_number = row[1]
        version_name = row[2]
        recipe_id = row[3]
        recipe_name = row[4]

        customer_name = None
        if customer_id:
            cursor.execute("""
                SELECT name
                FROM customers
                WHERE id = %s
            """, (customer_id,))
            c = cursor.fetchone()
            if c:
                customer_name = c[0]

        selected_packaging = None
        if packaging_type_id:
            cursor.execute("""
                SELECT id, name, capacity_value, capacity_unit, cost_per_ton, package_price
                FROM packaging_types
                WHERE id = %s
            """, (packaging_type_id,))
            p = cursor.fetchone()
            if p:
                selected_packaging = {
                    "id": p[0],
                    "name": p[1],
                    "capacity_value": float(p[2]) if p[2] is not None else None,
                    "capacity_unit": p[3],
                    "cost_per_ton": float(p[4]),
                    "package_price": float(p[5]),
                }

        selected_transport_scheme = None
        if transport_scheme_id:
            cursor.execute("""
                SELECT
                    ts.id,
                    ts.name,
                    ts.capacity_tons,
                    tt.name
                FROM transport_schemes ts
                LEFT JOIN transport_types tt ON tt.id = ts.transport_type_id
                WHERE ts.id = %s
            """, (transport_scheme_id,))
            t = cursor.fetchone()
            if t:
                selected_transport_scheme = {
                    "id": t[0],
                    "name": t[1],
                    "capacity_tons": float(t[2]) if t[2] is not None else None,
                    "transport_type": t[3]
                }

        selected_transport_rate = None
        if customer_id and transport_scheme_id:
            cursor.execute("""
                SELECT
                    price,
                    currency,
                    price_per
                FROM transport_rate_history
                WHERE customer_id = %s
                  AND transport_scheme_id = %s
                  AND valid_to IS NULL
                ORDER BY valid_from DESC
                LIMIT 1
            """, (customer_id, transport_scheme_id))
            tr = cursor.fetchone()
            if tr:
                selected_transport_rate = {
                    "price": float(tr[0]),
                    "currency": tr[1],
                    "price_per": tr[2],
                }

        cursor.execute("""
            SELECT
                ri.id,
                m.name,
                ri.quantity,
                COALESCE(mp.price, m.default_price, 0) AS material_price
            FROM recipe_items ri
            JOIN materials m ON m.id = ri.material_id
            LEFT JOIN LATERAL (
                SELECT price
                FROM material_price_history
                WHERE material_id = m.id
                  AND valid_to IS NULL
                ORDER BY valid_from DESC
                LIMIT 1
            ) mp ON TRUE
            WHERE ri.recipe_version_id = %s
            ORDER BY m.name
        """, (version_id,))
        item_rows = cursor.fetchall()

    item_snapshots = []
    direct_cost = 0.0
    total_final_quantity = 0.0

    for row in item_rows:
        item_id = row[0]
        material_name = row[1]
        base_quantity = float(row[2])
        material_price = float(row[3] or 0)

        with conn.cursor() as cursor:
            cursor.execute("""
                SELECT
                    rip.loss_coefficient,
                    COALESCE(pch.cost, p.default_cost, 0) AS process_cost
                FROM recipe_item_processes rip
                JOIN processes p ON p.id = rip.process_id
                LEFT JOIN LATERAL (
                    SELECT cost
                    FROM process_cost_history
                    WHERE process_id = p.id
                      AND valid_to IS NULL
                    ORDER BY valid_from DESC
                    LIMIT 1
                ) pch ON TRUE
                WHERE rip.recipe_item_id = %s
                ORDER BY rip.sort_order, p.name
            """, (item_id,))
            process_rows = cursor.fetchall()

        total_loss = 1.0
        total_process_cost = 0.0

        for p in process_rows:
            total_loss *= float(p[0] or 1)
            total_process_cost += float(p[1] or 0)

        final_quantity = base_quantity * total_loss
        material_cost = final_quantity * material_price
        process_cost = final_quantity * total_process_cost
        total_item_cost = material_cost + process_cost

        direct_cost += total_item_cost
        total_final_quantity += final_quantity

        item_snapshots.append({
            "material_name": material_name,
            "base_quantity": base_quantity,
            "total_loss": total_loss,
            "final_quantity": final_quantity,
            "material_price": material_price,
            "material_cost": material_cost,
            "total_process_cost": total_process_cost,
            "process_cost": process_cost,
            "total_cost": total_item_cost,
        })

    mixing_cost_total = total_final_quantity * mixing_cost_per_ton

    packaging_work_cost_total = 0.0
    packaging_material_cost_total = 0.0
    package_count = 0.0

    if selected_packaging:
        packaging_work_cost_total = total_final_quantity * selected_packaging["cost_per_ton"]

        capacity_value = selected_packaging["capacity_value"]
        capacity_unit = selected_packaging["capacity_unit"]

        if capacity_value and capacity_value > 0:
            capacity_tons = None

            if capacity_unit == "т":
                capacity_tons = capacity_value
            elif capacity_unit in ("kg", "кг"):
                capacity_tons = capacity_value / 1000.0

            if capacity_tons and capacity_tons > 0:
                package_count = total_final_quantity / capacity_tons
                packaging_material_cost_total = package_count * selected_packaging["package_price"]

    transport_cost_total = 0.0
    transport_units_count = 0.0
    transport_cost_per_ton = 0.0

    if selected_transport_rate and selected_transport_scheme and total_final_quantity > 0:
        price = selected_transport_rate["price"]
        price_per = selected_transport_rate["price_per"]
        capacity_tons = selected_transport_scheme["capacity_tons"]

        if price_per == "ton":
            transport_cost_total = total_final_quantity * price
            transport_cost_per_ton = price

        elif price_per in ("trip", "wagon"):
            if capacity_tons and capacity_tons > 0:
                transport_units_count = total_final_quantity / capacity_tons
                transport_cost_total = transport_units_count * price
                transport_cost_per_ton = transport_cost_total / total_final_quantity if total_final_quantity > 0 else 0.0

    overhead_base = (
        direct_cost
        + mixing_cost_total
        + packaging_work_cost_total
        + packaging_material_cost_total
        + transport_cost_total
    )
    overhead_cost = overhead_base * overhead_percent / 100.0
    total_cost = overhead_base + overhead_cost

    with conn.cursor() as cursor:
        cursor.execute("""
            INSERT INTO saved_calculations (
                recipe_id,
                recipe_version_id,
                customer_id,
                customer_name_snapshot,
                recipe_name_snapshot,
                version_number_snapshot,
                version_name_snapshot,
                overhead_percent,
                mixing_cost_per_ton,
                packaging_type_id,
                packaging_name_snapshot,
                packaging_capacity_value_snapshot,
                packaging_capacity_unit_snapshot,
                packaging_cost_per_ton_snapshot,
                package_price_snapshot,
                transport_scheme_id,
                transport_scheme_name_snapshot,
                transport_rate_snapshot,
                transport_rate_price_per_snapshot,
                transport_capacity_tons_snapshot,
                transport_units_count,
                transport_cost_per_ton,
                transport_cost_total,
                direct_cost,
                mixing_cost_total,
                packaging_work_cost_total,
                packaging_material_cost_total,
                overhead_cost,
                total_cost,
                total_final_quantity,
                package_count
            )
            VALUES (
                %s,%s,%s,%s,%s,%s,%s,
                %s,%s,%s,%s,%s,%s,%s,%s,
                %s,%s,%s,%s,%s,%s,%s,%s,
                %s,%s,%s,%s,%s,%s,%s,%s
            )
            RETURNING id
        """, (
            recipe_id,
            recipe_version_id,
            customer_id if customer_id else None,
            customer_name,
            recipe_name,
            version_number,
            version_name,
            overhead_percent,
            mixing_cost_per_ton,
            selected_packaging["id"] if selected_packaging else None,
            selected_packaging["name"] if selected_packaging else None,
            selected_packaging["capacity_value"] if selected_packaging else None,
            selected_packaging["capacity_unit"] if selected_packaging else None,
            selected_packaging["cost_per_ton"] if selected_packaging else 0,
            selected_packaging["package_price"] if selected_packaging else 0,
            selected_transport_scheme["id"] if selected_transport_scheme else None,
            selected_transport_scheme["name"] if selected_transport_scheme else None,
            selected_transport_rate["price"] if selected_transport_rate else 0,
            selected_transport_rate["price_per"] if selected_transport_rate else None,
            selected_transport_scheme["capacity_tons"] if selected_transport_scheme else None,
            transport_units_count,
            transport_cost_per_ton,
            transport_cost_total,
            direct_cost,
            mixing_cost_total,
            packaging_work_cost_total,
            packaging_material_cost_total,
            overhead_cost,
            total_cost,
            total_final_quantity,
            package_count
        ))
        saved_calculation_id = cursor.fetchone()[0]

        for item in item_snapshots:
            cursor.execute("""
                INSERT INTO saved_calculation_items (
                    saved_calculation_id,
                    material_name_snapshot,
                    base_quantity,
                    total_loss,
                    final_quantity,
                    material_price_snapshot,
                    material_cost,
                    total_process_cost,
                    process_cost,
                    total_cost
                )
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
            """, (
                saved_calculation_id,
                item["material_name"],
                item["base_quantity"],
                item["total_loss"],
                item["final_quantity"],
                item["material_price"],
                item["material_cost"],
                item["total_process_cost"],
                item["process_cost"],
                item["total_cost"],
            ))

    return RedirectResponse(
        url="/saved-calculations-page",
        status_code=303
    )
@app.get("/saved-calculations/{calc_id}", response_class=HTMLResponse)
def saved_calculation_details_page(request: Request, calc_id: str):
    with conn.cursor() as cursor:
        cursor.execute("""
            SELECT
                id,
                recipe_name_snapshot,
                customer_name_snapshot,
                version_number_snapshot,
                version_name_snapshot,
                packaging_name_snapshot,
                overhead_percent,
                mixing_cost_per_ton,
                packaging_capacity_value_snapshot,
                packaging_capacity_unit_snapshot,
                packaging_cost_per_ton_snapshot,
                package_price_snapshot,
                transport_scheme_name_snapshot,
                transport_rate_snapshot,
                transport_rate_price_per_snapshot,
                transport_capacity_tons_snapshot,
                transport_units_count,
                transport_cost_per_ton,
                transport_cost_total,
                direct_cost,
                mixing_cost_total,
                packaging_work_cost_total,
                packaging_material_cost_total,
                overhead_cost,
                total_cost,
                total_final_quantity,
                package_count,
                created_at
            FROM saved_calculations
            WHERE id = %s
        """, (calc_id,))
        row = cursor.fetchone()

        if not row:
            return RedirectResponse("/saved-calculations-page", status_code=303)

        calc = {
            "id": row[0],
            "recipe_name": row[1],
            "customer_name": row[2],
            "version_number": row[3],
            "version_name": row[4],
            "packaging_name": row[5],
            "overhead_percent": float(row[6]),
            "mixing_cost_per_ton": float(row[7]),
            "packaging_capacity_value": float(row[8]) if row[8] is not None else None,
            "packaging_capacity_unit": row[9],
            "packaging_cost_per_ton": float(row[10]),
            "package_price": float(row[11]),
            "transport_scheme_name": row[12],
            "transport_rate": float(row[13]),
            "transport_rate_price_per": row[14],
            "transport_capacity_tons": float(row[15]) if row[15] is not None else None,
            "transport_units_count": float(row[16]),
            "transport_cost_per_ton": float(row[17]),
            "transport_cost_total": float(row[18]),
            "direct_cost": float(row[19]),
            "mixing_cost_total": float(row[20]),
            "packaging_work_cost_total": float(row[21]),
            "packaging_material_cost_total": float(row[22]),
            "overhead_cost": float(row[23]),
            "total_cost": float(row[24]),
            "total_final_quantity": float(row[25]),
            "package_count": float(row[26]),
            "created_at": str(row[27]),
        }

        cursor.execute("""
            SELECT
                material_name_snapshot,
                base_quantity,
                total_loss,
                final_quantity,
                material_price_snapshot,
                material_cost,
                total_process_cost,
                process_cost,
                total_cost
            FROM saved_calculation_items
            WHERE saved_calculation_id = %s
            ORDER BY material_name_snapshot
        """, (calc_id,))
        rows = cursor.fetchall()

    items = []
    for row in rows:
        items.append({
            "material_name": row[0],
            "base_quantity": float(row[1]),
            "total_loss": float(row[2]),
            "final_quantity": float(row[3]),
            "material_price": float(row[4]),
            "material_cost": float(row[5]),
            "total_process_cost": float(row[6]),
            "process_cost": float(row[7]),
            "total_cost": float(row[8]),
        })

    return templates.TemplateResponse(
        request,
        "saved_calculation_details.html",
        {
            "calc": calc,
            "items": items
        }
    )