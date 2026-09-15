from fastapi import FastAPI, Request, Depends, HTTPException
from fastapi.openapi.docs import get_swagger_ui_html
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

from app.database import engine
from sqlalchemy import inspect, text
from app import models
from app.auth import optional_user, current_user, ROLE_LABELS
from app.routers import auth, users, dashboard as dashboard_api, suppliers, registration, categories, units, reports, history
from app.database import SessionLocal
from app.services.catalog_service import import_existing_units
from app.services.price_migration import migrate_prices
from app.services.brand_migration import migrate_brands
from app.routers import brands
from app.database import get_db

from app.routers import (
    products,
    inventory,
    ai,
    receipts,
    issues,
)


# =========================================================
# DATABASE
# =========================================================

models.Base.metadata.create_all(bind=engine)
migrate_prices(engine)
migrate_brands(engine)
# create_all does not add columns to an existing SQLite database. Keep demo data
# compatible while introducing the recipient field for issue vouchers.
if "receiver" not in {column["name"] for column in inspect(engine).get_columns("issues")}:
    with engine.begin() as connection:
        connection.execute(text("ALTER TABLE issues ADD COLUMN receiver VARCHAR(200)"))
if "full_name" not in {column["name"] for column in inspect(engine).get_columns("users")}:
    with engine.begin() as connection:
        connection.execute(text("ALTER TABLE users ADD COLUMN full_name VARCHAR(200)"))
with SessionLocal() as catalog_db:
    import_existing_units(catalog_db)


# =========================================================
# FASTAPI
# =========================================================

app = FastAPI(
    title="Hệ thống Quản lý Kho",
    description=(
        "API quản lý sản phẩm, tồn kho, nhập xuất kho "
        "và hỗ trợ trợ lý AI."
    ),
    version="1.0.0",
    docs_url=None,
    redoc_url=None,
)


# =========================================================
# STATIC FILES
# =========================================================

app.mount(
    "/static",
    StaticFiles(directory="app/static"),
    name="static",
)


# =========================================================
# TEMPLATES
# =========================================================

templates = Jinja2Templates(
    directory="app/templates"
)


# =========================================================
# ROUTERS
# =========================================================

app.include_router(products.router)
app.include_router(inventory.router)
app.include_router(ai.router)
app.include_router(ai.chat_router)
app.include_router(brands.router)
app.include_router(receipts.router)
app.include_router(issues.router)
app.include_router(auth.router)
app.include_router(users.router)
app.include_router(dashboard_api.router)
app.include_router(suppliers.router)
app.include_router(registration.router)
app.include_router(categories.router)
app.include_router(units.router)
app.include_router(reports.router)
app.include_router(history.router)


@app.middleware("http")
async def response_security(request, call_next):
    response = await call_next(request)
    if not request.url.path.startswith("/static/"):
        response.headers["Cache-Control"] = "no-store"
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["X-Frame-Options"] = "DENY"
    response.headers["Referrer-Policy"] = "same-origin"
    return response


# =========================================================
# CUSTOM SWAGGER
# =========================================================

@app.get(
    "/docs",
    include_in_schema=False
)
async def custom_swagger_ui(user=Depends(current_user)):

    swagger_html = get_swagger_ui_html(
        openapi_url=app.openapi_url,
        title="Inventory AI - API",
        swagger_js_url=(
            "https://cdn.jsdelivr.net/npm/"
            "swagger-ui-dist@5/swagger-ui-bundle.js"
        ),
        swagger_css_url=(
            "https://cdn.jsdelivr.net/npm/"
            "swagger-ui-dist@5/swagger-ui.css"
        ),
    )

    # =====================================================
    # CSS
    # =====================================================

    custom_css = """
    <style>

    :root {
        --bg: #f5f7fb;
        --sidebar: #0b1220;
        --sidebar2: #111c34;

        --primary: #2563eb;
        --primary-dark: #1d4ed8;

        --text: #0f172a;
        --text2: #475569;
        --muted: #64748b;

        --border: #e2e8f0;
    }


    /* ==================================================
       RESET
    ================================================== */

    * {
        box-sizing: border-box;
    }

    body {
        margin: 0 !important;

        background:
            radial-gradient(
                circle at top left,
                rgba(37, 99, 235, 0.07),
                transparent 30%
            ),
            var(--bg) !important;

        font-family:
            "Segoe UI",
            Arial,
            Helvetica,
            sans-serif !important;
    }


    /* ==================================================
       ẨN TOPBAR SWAGGER
    ================================================== */

    .swagger-ui .topbar {
        display: none !important;
    }


    /* ==================================================
       SIDEBAR
    ================================================== */

    .docs-sidebar {
        position: fixed;

        top: 0;
        left: 0;
        bottom: 0;

        width: 260px;

        padding: 24px 18px;

        overflow-y: auto;

        color: white;

        background:
            linear-gradient(
                180deg,
                var(--sidebar),
                var(--sidebar2)
            );

        box-shadow:
            8px 0 30px
            rgba(15, 23, 42, 0.08);

        z-index: 9999;
    }


    .docs-brand {
        display: flex;
        align-items: center;

        gap: 12px;

        margin-bottom: 34px;
    }


    .docs-logo {
        width: 50px;
        height: 50px;

        flex-shrink: 0;

        display: flex;
        align-items: center;
        justify-content: center;

        border-radius: 15px;

        background:
            linear-gradient(
                135deg,
                #2563eb,
                #4f46e5
            );

        font-size: 25px;

        box-shadow:
            0 8px 24px
            rgba(37, 99, 235, 0.30);
    }


    .docs-brand h2 {
        margin: 0;

        font-size: 19px;
        font-weight: 800;
    }


    .docs-brand p {
        margin: 4px 0 0;

        color: #94a3b8;

        font-size: 11px;
    }


    .docs-menu-title {
        margin:
            23px 0
            8px 12px;

        color: #64748b;

        font-size: 10px;
        font-weight: 800;

        letter-spacing: 1.2px;
    }


    .docs-menu a {
        display: flex;
        align-items: center;

        gap: 11px;

        margin-bottom: 6px;

        padding: 12px 14px;

        color: #cbd5e1;

        text-decoration: none;

        border-radius: 11px;

        font-size: 14px;

        transition: 0.2s;
    }


    .docs-menu a:hover {
        color: white;

        background:
            rgba(255, 255, 255, 0.08);

        transform:
            translateX(3px);
    }


    .docs-menu a.active {
        color: white;

        background:
            linear-gradient(
                135deg,
                #2563eb,
                #4f46e5
            );

        box-shadow:
            0 7px 20px
            rgba(37, 99, 235, 0.25);
    }


    /* ==================================================
       SWAGGER MAIN
    ================================================== */

    .swagger-ui {
        margin-left: 260px !important;

        padding:
            30px 35px
            50px !important;
    }


    .swagger-ui .wrapper {
        max-width: 1250px !important;

        padding: 0 !important;
    }


    /* ==================================================
       HEADER
    ================================================== */

    .swagger-ui .info {
        position: relative;

        overflow: hidden;

        margin:
            0 0 30px !important;

        padding:
            30px !important;

        background:
            linear-gradient(
                135deg,
                #0f172a,
                #172554 55%,
                #1d4ed8
            ) !important;

        border-radius: 20px;

        box-shadow:
            0 15px 35px
            rgba(15, 23, 42, 0.13);
    }


    .swagger-ui .info::after {
        content: "";

        position: absolute;

        width: 220px;
        height: 220px;

        right: -80px;
        top: -110px;

        border-radius: 50%;

        background:
            rgba(255, 255, 255, 0.08);
    }


    .swagger-ui .info .title {
        position: relative;

        z-index: 2;

        color: white !important;

        font-size: 30px !important;
        font-weight: 800 !important;
    }


    .swagger-ui .info p {
        position: relative;

        z-index: 2;

        color:
            rgba(255, 255, 255, 0.76) !important;

        font-size: 14px !important;

        line-height: 1.7;
    }


    .swagger-ui .info a {
        color: #bfdbfe !important;
    }


    /* ==================================================
       NHÓM API
    ================================================== */

    .swagger-ui .opblock-tag-section {
        margin-bottom: 25px;
    }


    .swagger-ui .opblock-tag {
        position: relative;

        min-height: 78px;

        display: flex !important;
        align-items: center !important;

        margin:
            24px 0
            12px !important;

        padding:
            15px 60px
            15px 78px !important;

        overflow: hidden;

        color: var(--text) !important;

        background: white !important;

        border:
            1px solid
            var(--border) !important;

        border-radius: 16px !important;

        box-shadow:
            0 6px 20px
            rgba(15, 23, 42, 0.06);

        font-size: 18px !important;
        font-weight: 800 !important;

        transition: 0.2s;
    }


    .swagger-ui .opblock-tag:hover {
        transform:
            translateY(-2px);

        box-shadow:
            0 10px 26px
            rgba(15, 23, 42, 0.10);
    }


    .swagger-ui .opblock-tag a {
        width: 100%;

        text-decoration: none !important;
    }


    .swagger-ui .opblock-tag a span {
        color: var(--text) !important;

        font-size: 18px !important;
        font-weight: 800 !important;
    }


    .swagger-ui .opblock-tag::before {
        position: absolute;

        left: 18px;
        top: 50%;

        transform:
            translateY(-50%);

        width: 44px;
        height: 44px;

        display: flex;
        align-items: center;
        justify-content: center;

        border-radius: 13px;

        font-size: 22px;
    }


    /* ==================================================
       SẢN PHẨM
    ================================================== */

    .swagger-ui .tag-products {
        background:
            linear-gradient(
                135deg,
                #eff6ff,
                #ffffff
            ) !important;

        border-color:
            #bfdbfe !important;
    }


    .swagger-ui .tag-products::before {
        content: "📦";

        background: #dbeafe;
    }


    .swagger-ui .tag-products a::after {
        content:
            "Danh mục và thông tin hàng hóa";

        display: block;

        margin-top: 5px;

        color: var(--muted);

        font-size: 12px;
        font-weight: 500;
    }


    /* ==================================================
       TỒN KHO
    ================================================== */

    .swagger-ui .tag-inventory {
        background:
            linear-gradient(
                135deg,
                #ecfeff,
                #ffffff
            ) !important;

        border-color:
            #a5f3fc !important;
    }


    .swagger-ui .tag-inventory::before {
        content: "🏬";

        background: #cffafe;
    }


    .swagger-ui .tag-inventory a::after {
        content:
            "Theo dõi số lượng và trạng thái tồn kho";

        display: block;

        margin-top: 5px;

        color: var(--muted);

        font-size: 12px;
        font-weight: 500;
    }


    /* ==================================================
       AI
    ================================================== */

    .swagger-ui .tag-ai {
        background:
            linear-gradient(
                135deg,
                #f5f3ff,
                #ffffff
            ) !important;

        border-color:
            #ddd6fe !important;
    }


    .swagger-ui .tag-ai::before {
        content: "🤖";

        background: #ede9fe;
    }


    .swagger-ui .tag-ai a::after {
        content:
            "Phân tích dữ liệu kho bằng Gemini AI";

        display: block;

        margin-top: 5px;

        color: var(--muted);

        font-size: 12px;
        font-weight: 500;
    }


    /* ==================================================
       PHIẾU NHẬP
    ================================================== */

    .swagger-ui .tag-receipts {
        background:
            linear-gradient(
                135deg,
                #f0fdf4,
                #ffffff
            ) !important;

        border-color:
            #bbf7d0 !important;
    }


    .swagger-ui .tag-receipts::before {
        content: "📥";

        background: #dcfce7;
    }


    .swagger-ui .tag-receipts a::after {
        content:
            "Lập phiếu nhập và cập nhật hàng vào kho";

        display: block;

        margin-top: 5px;

        color: var(--muted);

        font-size: 12px;
        font-weight: 500;
    }


    /* ==================================================
       PHIẾU XUẤT
    ================================================== */

    .swagger-ui .tag-issues {
        background:
            linear-gradient(
                135deg,
                #fff7ed,
                #ffffff
            ) !important;

        border-color:
            #fed7aa !important;
    }


    .swagger-ui .tag-issues::before {
        content: "📤";

        background: #ffedd5;
    }


    .swagger-ui .tag-issues a::after {
        content:
            "Xuất hàng và kiểm tra số lượng còn lại";

        display: block;

        margin-top: 5px;

        color: var(--muted);

        font-size: 12px;
        font-weight: 500;
    }


    /* ==================================================
       ENDPOINT
    ================================================== */

    .swagger-ui .opblock {
        margin:
            9px 0 !important;

        overflow: hidden;

        border-radius:
            11px !important;

        box-shadow:
            0 3px 12px
            rgba(15, 23, 42, 0.04);

        transition: 0.18s;
    }


    .swagger-ui .opblock:hover {
        transform:
            translateY(-1px);

        box-shadow:
            0 7px 18px
            rgba(15, 23, 42, 0.07);
    }


    /* GET */

    .swagger-ui .opblock.opblock-get {
        background:
            #eff6ff !important;

        border-color:
            #3b82f6 !important;
    }

    .swagger-ui
    .opblock.opblock-get
    .opblock-summary-method {

        background:
            #2563eb !important;
    }


    /* POST */

    .swagger-ui .opblock.opblock-post {
        background:
            #f0fdf4 !important;

        border-color:
            #22c55e !important;
    }

    .swagger-ui
    .opblock.opblock-post
    .opblock-summary-method {

        background:
            #16a34a !important;
    }


    /* PUT */

    .swagger-ui .opblock.opblock-put {
        background:
            #fffbeb !important;

        border-color:
            #f59e0b !important;
    }

    .swagger-ui
    .opblock.opblock-put
    .opblock-summary-method {

        background:
            #f59e0b !important;
    }


    /* DELETE */

    .swagger-ui .opblock.opblock-delete {
        background:
            #fef2f2 !important;

        border-color:
            #ef4444 !important;
    }

    .swagger-ui
    .opblock.opblock-delete
    .opblock-summary-method {

        background:
            #dc2626 !important;
    }


    .swagger-ui .opblock-summary-method {
        min-width: 75px !important;

        padding:
            7px 10px !important;

        border-radius:
            7px !important;

        font-size:
            12px !important;

        font-weight:
            800 !important;
    }


    .swagger-ui .opblock-summary-path {
        color:
            var(--text) !important;

        font-size:
            14px !important;

        font-weight:
            700 !important;
    }


    .swagger-ui .opblock-summary-description {
        color:
            var(--muted) !important;

        font-size:
            12px !important;
    }


    /* ==================================================
       BODY API
    ================================================== */

    .swagger-ui .opblock-body {
        padding-bottom:
            18px !important;

        background:
            white !important;
    }


    /* ==================================================
       PARAMETERS / REQUEST / RESPONSE HEADER
    ================================================== */

    .swagger-ui .opblock-section-header {
        min-height:
            55px !important;

        padding:
            12px 18px !important;

        background:
            linear-gradient(
                135deg,
                #f8fafc,
                #f1f5f9
            ) !important;

        border-top:
            1px solid
            #e2e8f0 !important;

        border-bottom:
            1px solid
            #e2e8f0 !important;

        box-shadow:
            none !important;
    }


    .swagger-ui
    .opblock-section-header h4 {

        color:
            var(--text) !important;

        font-size:
            14px !important;

        font-weight:
            800 !important;
    }


    /* ==================================================
       PARAMETERS
    ================================================== */

    .swagger-ui
    .parameters-container {

        padding:
            5px 18px
            18px !important;
    }


    .swagger-ui
    table.parameters {

        border-collapse:
            separate !important;

        border-spacing:
            0 8px !important;
    }


    .swagger-ui
    table.parameters thead tr th {

        padding:
            10px 12px !important;

        color:
            var(--muted) !important;

        font-size:
            11px !important;

        font-weight:
            800 !important;

        text-transform:
            uppercase;

        letter-spacing:
            0.4px;
    }


    .swagger-ui
    table.parameters tbody tr {

        background:
            #f8fafc;
    }


    .swagger-ui
    table.parameters td {

        padding:
            14px 12px !important;

        border:
            none !important;
    }


    .swagger-ui .parameter__name {
        color:
            var(--text) !important;

        font-size:
            14px !important;

        font-weight:
            800 !important;
    }


    .swagger-ui .parameter__type {
        color:
            #2563eb !important;

        font-size:
            11px !important;

        font-weight:
            700 !important;
    }


    .swagger-ui .parameter__in {
        color:
            #94a3b8 !important;

        font-size:
            10px !important;
    }


    .swagger-ui .required {
        color:
            #ef4444 !important;
    }


    /* ==================================================
       INPUT
    ================================================== */

    .swagger-ui input[type=text],
    .swagger-ui input[type=number],
    .swagger-ui textarea,
    .swagger-ui select {

        min-height:
            42px;

        padding:
            9px 12px !important;

        color:
            var(--text) !important;

        background:
            white !important;

        border:
            1px solid
            #cbd5e1 !important;

        border-radius:
            10px !important;

        box-shadow:
            0 2px 6px
            rgba(15, 23, 42, 0.04);

        font-size:
            13px !important;

        transition:
            0.2s;
    }


    .swagger-ui input:focus,
    .swagger-ui textarea:focus,
    .swagger-ui select:focus {

        outline:
            none !important;

        border-color:
            #3b82f6 !important;

        box-shadow:
            0 0 0 3px
            rgba(59, 130, 246, 0.13) !important;
    }


    /* ==================================================
       DESCRIPTION
    ================================================== */

    .swagger-ui
    .opblock-description-wrapper {

        padding:
            14px 18px !important;
    }


    .swagger-ui .body-param {
        padding:
            0 18px
            18px !important;
    }


    /* ==================================================
       JSON
    ================================================== */

    .swagger-ui .highlight-code,
    .swagger-ui .microlight {

        padding:
            15px !important;

        color:
            #e2e8f0 !important;

        background:
            linear-gradient(
                145deg,
                #0f172a,
                #111827
            ) !important;

        border-radius:
            12px !important;

        border:
            1px solid
            rgba(255, 255, 255, 0.05);
    }


    .swagger-ui pre {
        font-family:
            Consolas,
            "Courier New",
            monospace !important;

        font-size:
            12px !important;

        line-height:
            1.65 !important;
    }


    /* ==================================================
       TABS
    ================================================== */

    .swagger-ui .tab {
        margin:
            12px 0 !important;
    }


    .swagger-ui
    .tab li button.tablinks {

        padding:
            6px 9px !important;

        border-radius:
            7px;

        color:
            var(--muted) !important;

        font-size:
            11px !important;

        font-weight:
            700 !important;
    }


    .swagger-ui
    .tab li.active
    button.tablinks {

        color:
            #2563eb !important;

        background:
            #eff6ff;
    }


    /* ==================================================
       BUTTON TRY
    ================================================== */

    .swagger-ui
    .btn.try-out__btn {

        min-width:
            105px;

        padding:
            9px 14px !important;

        color:
            #2563eb !important;

        background:
            #eff6ff !important;

        border:
            1px solid
            #93c5fd !important;

        border-radius:
            9px !important;

        font-weight:
            700 !important;

        box-shadow:
            0 3px 8px
            rgba(37, 99, 235, 0.08);
    }


    .swagger-ui
    .btn.try-out__btn:hover {

        color:
            white !important;

        background:
            #2563eb !important;
    }


    /* ==================================================
       EXECUTE
    ================================================== */

    .swagger-ui .btn.execute {
        min-height:
            44px;

        color:
            white !important;

        border:
            none !important;

        border-radius:
            10px !important;

        background:
            linear-gradient(
                135deg,
                #2563eb,
                #4f46e5
            ) !important;

        font-size:
            13px !important;

        font-weight:
            800 !important;

        box-shadow:
            0 7px 18px
            rgba(37, 99, 235, 0.22);
    }


    /* ==================================================
       RESPONSES
    ================================================== */

    .swagger-ui
    .responses-wrapper {

        padding:
            0 18px
            18px !important;
    }


    .swagger-ui
    .responses-table {

        overflow:
            hidden;

        border:
            1px solid
            #e2e8f0;

        border-radius:
            12px;
    }


    .swagger-ui
    .responses-table thead {

        background:
            #f8fafc;
    }


    .swagger-ui
    .responses-table th {

        padding:
            12px !important;

        color:
            var(--muted) !important;

        font-size:
            11px !important;

        font-weight:
            800 !important;

        text-transform:
            uppercase;
    }


    .swagger-ui
    .responses-table td {

        padding:
            14px 12px !important;

        border-top:
            1px solid
            #f1f5f9 !important;
    }


    .swagger-ui
    .response-col_status {

        width:
            78px !important;

        font-weight:
            800 !important;
    }


    /* ==================================================
       MODELS
    ================================================== */

    .swagger-ui section.models {
        margin-top:
            25px;

        padding:
            12px;

        background:
            white;

        border:
            1px solid
            #e2e8f0 !important;

        border-radius:
            14px !important;

        box-shadow:
            0 5px 18px
            rgba(15, 23, 42, 0.05);
    }


    /* ==================================================
       RESPONSIVE
    ================================================== */

    @media (max-width: 800px) {

        .docs-sidebar {
            display: none;
        }

        .swagger-ui {
            margin-left:
                0 !important;

            padding:
                15px !important;
        }

    }

    </style>
    """


    # =====================================================
    # SIDEBAR HTML
    # =====================================================

    custom_layout = """
    <aside class="docs-sidebar">

        <div class="docs-brand">

            <div class="docs-logo">
                📦
            </div>

            <div>
                <h2>
                    Inventory AI
                </h2>

                <p>
                    Quản lý kho thông minh
                </p>
            </div>

        </div>


        <div class="docs-menu">

            <a href="/">
                🏠
                <span>
                    Tổng quan
                </span>
            </a>


            <a
                href="/docs"
                class="active"
            >
                ⚙️

                <span>
                    API Documentation
                </span>
            </a>


            <div class="docs-menu-title">
                QUẢN LÝ KHO
            </div>


            <a href="/docs#/Quản%20lý%20Sản%20phẩm">
                📦
                <span>Sản phẩm</span>
            </a>


            <a href="/docs#/Quản%20lý%20Tồn%20kho">
                🏬
                <span>Tồn kho</span>
            </a>


            <a href="/docs#/Phiếu%20nhập%20kho">
                📥
                <span>Phiếu nhập</span>
            </a>


            <a href="/docs#/Phiếu%20xuất%20kho">
                📤
                <span>Phiếu xuất</span>
            </a>


            <div class="docs-menu-title">
                TRỢ LÝ THÔNG MINH
            </div>


            <a href="/docs#/Trợ%20lý%20AI">
                🤖
                <span>Trợ lý AI</span>
            </a>

        </div>

    </aside>
    """


    # =====================================================
    # JAVASCRIPT
    # =====================================================

    custom_script = """
    <script>

    function decorateSwagger() {

        /* =========================================
           TRANG TRÍ NHÓM API
        ========================================= */

        const groups = {
            "Quản lý Sản phẩm": "tag-products",
            "Quản lý Tồn kho": "tag-inventory",
            "Trợ lý AI": "tag-ai",
            "Phiếu nhập kho": "tag-receipts",
            "Phiếu xuất kho": "tag-issues"
        };


        document
            .querySelectorAll(
                ".swagger-ui .opblock-tag"
            )
            .forEach(function(tag) {

                const text =
                    tag.textContent.trim();


                Object
                    .keys(groups)
                    .forEach(function(name) {

                        if (
                            text.includes(name)
                        ) {

                            tag.classList.add(
                                groups[name]
                            );

                        }

                    });

            });


        /* =========================================
           ĐỔI MỘT SỐ CHỮ SANG TIẾNG VIỆT
        ========================================= */

        document
            .querySelectorAll(
                ".swagger-ui h4"
            )
            .forEach(function(element) {

                const text =
                    element.textContent.trim();

                if (text === "Parameters") {
                    element.textContent =
                        "Tham số";
                }

                if (text === "Request body") {
                    element.textContent =
                        "Dữ liệu gửi lên";
                }

                if (text === "Responses") {
                    element.textContent =
                        "Kết quả trả về";
                }

            });


        /* Try it out */

        document
            .querySelectorAll(
                ".try-out__btn"
            )
            .forEach(function(button) {

                if (
                    button.textContent
                        .trim()
                    === "Try it out"
                ) {

                    button.textContent =
                        "Thử API";

                }

            });


        /* Execute */

        document
            .querySelectorAll(
                ".execute"
            )
            .forEach(function(button) {

                if (
                    button.textContent
                        .trim()
                    === "Execute"
                ) {

                    button.textContent =
                        "Gửi yêu cầu";

                }

            });


        /* Successful Response */

        document
            .querySelectorAll(
                ".response-col_description"
            )
            .forEach(function(element) {

                if (
                    element.textContent
                        .trim()
                        .startsWith(
                            "Successful Response"
                        )
                ) {

                    const html =
                        element.innerHTML;

                    element.innerHTML =
                        html.replace(
                            "Successful Response",
                            "Thành công"
                        );

                }

            });

    }


    window.addEventListener(
        "load",
        function() {

            setTimeout(
                decorateSwagger,
                300
            );

            setTimeout(
                decorateSwagger,
                1000
            );

        }
    );


    const observer =
        new MutationObserver(
            function() {

                decorateSwagger();

            }
        );


    observer.observe(
        document.body,
        {
            childList: true,
            subtree: true
        }
    );

    </script>
    """


    # =====================================================
    # GHÉP HTML
    # =====================================================

    html = swagger_html.body.decode(
        "utf-8"
    )

    # Keep the docs layout while attaching the session CSRF token to Try it out.
    html = html.replace("presets: [", """requestInterceptor: async function(req) {
        if (!['GET', 'HEAD', 'OPTIONS'].includes(req.method.toUpperCase())) {
            const response = await fetch('/auth/me', {credentials: 'same-origin'});
            if (response.ok) {
                const session = await response.json();
                req.headers['X-CSRF-Token'] = session.csrf_token;
            }
        }
        return req;
    },
    presets: [""", 1)


    html = html.replace(
        "</head>",
        custom_css + "</head>"
    )


    html = html.replace(
        "<body>",
        "<body>" + custom_layout,
        1
    )


    html = html.replace(
        "</body>",
        custom_script + "</body>",
        1
    )


    return HTMLResponse(
        content=html
    )


# =========================================================
# DASHBOARD
# =========================================================

@app.get(
    "/",
    include_in_schema=False
)
def dashboard(
    request: Request, user=Depends(optional_user)
):
    if user is None:
        return RedirectResponse("/login", status_code=303)
    return templates.TemplateResponse(
        request=request,
        name="dashboard.html",
        context={"user": user, "role_label": ROLE_LABELS[user.role], "page": "dashboard"}
    )


@app.get("/login", include_in_schema=False)
def login_page(request: Request, user=Depends(optional_user)):
    if user:
        return RedirectResponse("/", status_code=303)
    return templates.TemplateResponse(request=request, name="login.html", context={})


@app.get("/workspace/{page}", include_in_schema=False)
def workspace_page(page: str, request: Request, user=Depends(optional_user)):
    if user is None:
        return RedirectResponse("/login", status_code=303)
    allowed = {"products": {"admin", "thu_kho"}, "inventory": {"admin", "thu_kho"},
               "brands": {"admin", "thu_kho"},
               "categories": {"admin", "thu_kho"}, "units": {"admin", "thu_kho"}, "suppliers": set(ROLE_LABELS),
               "receipts": set(ROLE_LABELS), "issues": set(ROLE_LABELS), "history": set(ROLE_LABELS),
               "users": {"admin"}, "reports": {"admin", "ke_toan"}}
    if page not in allowed:
        raise HTTPException(404, "Không tìm thấy trang.")
    if user.role not in allowed[page]:
        raise HTTPException(403, "Bạn không có quyền truy cập trang này.")
    titles = {"products": "Hàng hóa", "inventory": "Tồn kho", "receipts": "Phiếu nhập",
              "brands": "Nhãn hàng",
              "categories": "Nhóm hàng", "units": "Đơn vị tính", "suppliers": "Nhà cung cấp",
              "issues": "Phiếu xuất", "history": "Lịch sử nhập – xuất",
              "users": "Quản lý tài khoản", "reports": "Báo cáo – AI"}
    template = ('catalog.html' if page in ['categories', 'units', 'suppliers', 'brands'] else
                'products.html' if page == 'products' else
                'inventory.html' if page == 'inventory' else
                'reports.html' if page == 'reports' else
                'history.html' if page == 'history' else 'workspace.html')
    return templates.TemplateResponse(request=request, name=template,
        context={"user": user, "role_label": ROLE_LABELS[user.role], "page": page, "title": titles[page]})


@app.get("/register", include_in_schema=False)
def register_page(request: Request, user=Depends(optional_user), db=Depends(get_db)):
    if user:
        return RedirectResponse("/", status_code=303)
    return templates.TemplateResponse(request=request, name="register.html",
        context={"first_admin": registration.needs_initial_admin(db)})
