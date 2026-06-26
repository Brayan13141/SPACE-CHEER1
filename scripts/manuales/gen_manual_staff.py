# -*- coding: utf-8 -*-
"""
Manual de Staff - Space Cheer
Generador de PDF con capturas reales del entorno local
Ejecutar: PYTHONUTF8=1 python gen_manual_staff.py
"""
import sys
import time
import base64
from pathlib import Path
from playwright.sync_api import sync_playwright

LOGO_PATH = Path("C:/Users/Lenovo/Documents/SPACE-CHEER/space_cheer/static/IMAGES/Logo_sin_fondo_blanco.png")

BASE_URL  = "http://127.0.0.1:8000"
USERNAME  = "staff_test"
PASSWORD  = "Test1234!"
SCREENSHOTS_DIR = Path("C:/Users/Lenovo/Documents/SPACE-CHEER/manual_screenshots_staff")
OUTPUT_PDF      = Path("C:/Users/Lenovo/Documents/SPACE-CHEER/manual_staff.pdf")

# (url_path, filename, title, desc, section)
PAGES = [
    # § 1 Acceso al sistema  — se captura login_ok por separado
    # § 2 Gestión de Pedidos
    ("/orders/admin/orders/",                   "pedidos_admin",    "Lista de Pedidos",               "Vista general de todos los pedidos del sistema",                       "orders"),
    # § 3 Módulo de Producción
    ("/production/admin/",                      "produccion_panel", "Panel de Producción",            "Vista general de trabajos activos y su progreso",                      "production"),
    ("/production/admin/job/2/",                "produccion_job2",  "Job #2 — Detalle",               "Detalle del job con tareas y operarios asignados (pedido #20, 5 tareas)","production"),
    ("/production/reglamento/",                 "reglamento",       "Reglamento de Producción",       "Normas, etapas y responsabilidades del proceso de fabricación",         "production"),
    ("/production/errores/",                    "errores_lista",    "Lista de Reportes de Error",     "Todos los incidentes reportados por operarios",                         "production"),
    ("/production/errores/1/",                  "error_detalle",    "Reporte de Error #1",            "Detalle del reporte con historial y estado actual",                     "production"),
    # § 4 Configuración de Producción
    ("/production/config/stages/",              "config_etapas",    "Catálogo de Etapas",             "Etapas configurables del proceso de producción",                        "config"),
    ("/production/config/roles/",               "config_roles",     "Roles de Producción",            "Roles asignables a operarios",                                          "config"),
    ("/production/config/responsabilidades/",   "config_resp",      "Responsabilidades",              "Responsabilidades vinculadas a cada rol",                               "config"),
    ("/production/config/operarios/",           "config_operarios", "Gestión de Operarios",           "Lista y datos de los operarios del taller",                             "config"),
    # § 5 Competencias y Eventos
    ("/events/",                                "eventos",          "Competencias",                   "Lista de eventos / competencias activas",                               "events"),
    ("/events/8/",                              "evento_grandprix", "Evento Grand Prix",              "Detalle del evento #8",                                                "events"),
    ("/events/8/registrations/",                "inscripciones",    "Inscripciones del Evento",       "Equipos e inscripciones del evento #8",                                "events"),
    ("/events/8/staff/",                        "staff_evento",     "Staff del Evento",               "Personal asignado al evento #8",                                       "events"),
    # § 6 Hospitalidad
    ("/hospitality/",                           "hospitalidad_index","Hospitalidad — Inicio",         "Índice general del módulo de hospitalidad",                            "hospitality"),
    ("/hospitality/event/8/hotels/",            "hoteles",          "Hoteles del Evento",             "Opciones de alojamiento para el evento #8",                            "hospitality"),
    ("/hospitality/event/8/stays/",             "reservaciones",    "Reservaciones",                  "Estancias confirmadas para el evento #8",                              "hospitality"),
    # § 7 Mi Perfil
    ("/accounts/profile/edit/",                 "perfil_editar",    "Editar Perfil",                  "Datos personales y de contacto del staff",                             "profile"),
    ("/accounts/profile/settings/",             "perfil_config",    "Configuración de Cuenta",        "Preferencias y seguridad de la cuenta",                                "profile"),
]


def logo_data_uri() -> str:
    if LOGO_PATH.exists():
        with open(LOGO_PATH, "rb") as f:
            return f"data:image/png;base64,{base64.b64encode(f.read()).decode()}"
    return ""


def ensure_dir():
    SCREENSHOTS_DIR.mkdir(parents=True, exist_ok=True)


def login_capture(page, base_url):
    print(f"    Navegando a {base_url}/accounts/login/")
    try:
        page.goto(f"{base_url}/accounts/login/", wait_until="load", timeout=30000)
    except Exception as e:
        print(f"    WARN goto login: {e}")
    try:
        page.fill('input[name="login"]', USERNAME)
        page.fill('input[name="password"]', PASSWORD)
        page.click('button[type="submit"]')
        page.wait_for_load_state("load", timeout=15000)
        time.sleep(2)
    except Exception as e:
        print(f"    WARN al hacer login: {e}")
    result_url = page.url
    print(f"    URL tras login: {result_url}")
    return result_url


def capture_page_at(page, base_url, url_path, filename):
    full_url = f"{base_url}{url_path}"
    try:
        response = page.goto(full_url, wait_until="load", timeout=30000)
        time.sleep(0.9)
        status = response.status if response else 0

        if status in (404, 500):
            return False, f"HTTP {status}"

        if status == 403:
            # Captura el 403 de todas formas (no es bloqueante para STAFF)
            screenshot_path = SCREENSHOTS_DIR / f"{filename}.png"
            page.screenshot(path=str(screenshot_path), full_page=True)
            return "denied", str(screenshot_path)

        if "/accounts/login/" in page.url or "/login/" in page.url:
            return False, "Redirigido al login — sesion perdida"

        screenshot_path = SCREENSHOTS_DIR / f"{filename}.png"
        page.screenshot(path=str(screenshot_path), full_page=True)
        return True, str(screenshot_path)
    except Exception as e:
        return False, str(e)[:150]


def img_to_base64(path):
    with open(path, "rb") as f:
        data = base64.b64encode(f.read()).decode("utf-8")
    return f"data:image/png;base64,{data}"


def build_html(results, login_path):
    _logo_uri = logo_data_uri()
    logo_img = (
        f'<img src="{_logo_uri}" alt="Space Cheer" '
        f'style="width:200px;margin-bottom:24px;position:relative;z-index:1;'
        f'filter:drop-shadow(0 0 20px rgba(13,148,136,0.4))">'
        if _logo_uri else '<div style="font-size:48px;margin-bottom:24px">★</div>'
    )

    # ── helpers ──────────────────────────────────────────────────────────────
    def render_screenshot(key, data):
        title = data["title"]
        desc  = data["desc"]
        ok    = data["ok"]
        path  = data["path"]
        url   = data["url"]

        if ok in (True, "denied") and Path(path).exists():
            img_src  = img_to_base64(path)
            img_html = f'<img src="{img_src}" alt="{title}" class="screenshot" />'
            if ok == "denied":
                img_html += '<div class="denied-badge">Acceso denegado (403) — solo lectura para STAFF</div>'
        else:
            img_html = f'<div class="no-screenshot"><span>Pantalla no disponible: {path}</span></div>'

        return f"""
        <div class="page-section">
          <h3>{title}</h3>
          <p class="page-desc">{desc}</p>
          <div class="url-badge"><code>{url}</code></div>
          {img_html}
        </div>"""

    def filter_section(sec):
        return [(k, v) for k, v in results.items() if v["section"] == sec]

    orders_pages      = filter_section("orders")
    production_pages  = filter_section("production")
    config_pages      = filter_section("config")
    events_pages      = filter_section("events")
    hospitality_pages = filter_section("hospitality")
    profile_pages     = filter_section("profile")

    # ── login screenshot ──────────────────────────────────────────────────────
    if login_path and Path(login_path).exists():
        login_img = f'<img src="{img_to_base64(login_path)}" alt="Login" class="screenshot" />'
    else:
        login_img = '<div class="no-screenshot"><span>Captura de login no disponible</span></div>'

    html = f"""<!DOCTYPE html>
<html lang="es">
<head>
<meta charset="UTF-8"/>
<title>Manual de Staff — Space Cheer</title>
<style>
  @import url('https://fonts.googleapis.com/css2?family=Inter:wght@300;400;600;700;900&display=swap');
  *,*::before,*::after {{ box-sizing: border-box; margin: 0; padding: 0; }}
  body {{
    font-family: 'Inter','Segoe UI',Arial,sans-serif;
    background: #0f172a;
    color: #e2e8f0;
    font-size: 13px;
    line-height: 1.6;
  }}

  /* ── PORTADA ── */
  .cover {{
    page-break-after: always;
    width: 210mm;
    min-height: 297mm;
    background: linear-gradient(135deg, #0f172a 0%, #134e4a 50%, #0f172a 100%);
    display: flex;
    flex-direction: column;
    align-items: center;
    justify-content: center;
    text-align: center;
    padding: 60px 40px;
    position: relative;
    overflow: hidden;
  }}
  .cover::before {{
    content: '';
    position: absolute;
    top: -100px; left: -100px;
    width: 500px; height: 500px;
    background: radial-gradient(circle, rgba(13,148,136,0.18) 0%, transparent 70%);
    border-radius: 50%;
  }}
  .cover::after {{
    content: '';
    position: absolute;
    bottom: -100px; right: -100px;
    width: 400px; height: 400px;
    background: radial-gradient(circle, rgba(20,184,166,0.12) 0%, transparent 70%);
    border-radius: 50%;
  }}
  .cover-badge {{
    background: linear-gradient(135deg, #0d9488, #14b8a6);
    color: white;
    font-size: 11px;
    font-weight: 700;
    letter-spacing: 3px;
    text-transform: uppercase;
    padding: 6px 20px;
    border-radius: 20px;
    margin-bottom: 32px;
    position: relative;
    z-index: 1;
  }}
  .cover h1 {{
    font-size: 36px;
    font-weight: 900;
    color: #f8fafc;
    line-height: 1.2;
    margin-bottom: 16px;
    position: relative;
    z-index: 1;
  }}
  .cover h1 span {{
    background: linear-gradient(135deg, #0d9488, #14b8a6);
    -webkit-background-clip: text;
    -webkit-text-fill-color: transparent;
    background-clip: text;
  }}
  .cover-subtitle {{
    font-size: 18px;
    color: #94a3b8;
    margin-bottom: 48px;
    position: relative;
    z-index: 1;
  }}
  .cover-divider {{
    width: 80px; height: 4px;
    background: linear-gradient(90deg, #0d9488, #14b8a6);
    border-radius: 2px;
    margin: 32px auto;
    position: relative; z-index: 1;
  }}

  /* ── ÍNDICE ── */
  .toc {{
    page-break-after: always;
    padding: 50px 40px;
    min-height: 297mm;
  }}
  .toc h2 {{
    font-size: 28px; font-weight: 800; color: #f8fafc;
    margin-bottom: 32px; padding-bottom: 12px;
    border-bottom: 3px solid #0d9488;
  }}
  .toc-item {{
    display: flex;
    justify-content: space-between;
    align-items: center;
    padding: 10px 0;
    border-bottom: 1px solid #1e293b;
    color: #cbd5e1;
  }}
  .toc-item.part {{
    font-weight: 700; color: #f8fafc; font-size: 14px;
    margin-top: 16px; border-bottom: 2px solid #334155;
    padding-bottom: 8px;
  }}
  .toc-item.part .toc-num {{
    background: linear-gradient(135deg, #0d9488, #14b8a6);
    color: white; padding: 2px 10px;
    border-radius: 12px; font-size: 11px;
  }}
  .toc-sub {{
    padding-left: 20px; color: #94a3b8; font-size: 12px;
  }}
  .toc-dots {{
    flex: 1; margin: 0 12px;
    border-bottom: 1px dotted #334155;
  }}

  /* ── SECCIONES ── */
  section {{
    padding: 40px;
    page-break-before: always;
  }}
  .section-title {{
    font-size: 24px; font-weight: 800; color: #f8fafc;
    padding: 16px 24px;
    background: linear-gradient(135deg, #1e293b, #0f172a);
    border-left: 5px solid #0d9488;
    border-radius: 0 8px 8px 0;
    margin-bottom: 32px;
  }}
  h3 {{
    font-size: 16px; font-weight: 700; color: #f1f5f9;
    margin: 32px 0 8px 0;
    padding-bottom: 6px;
    border-bottom: 1px solid #334155;
  }}

  /* ── CAPTURAS ── */
  .page-section {{
    margin-bottom: 40px;
    page-break-inside: avoid;
  }}
  .page-desc {{
    color: #94a3b8; margin-bottom: 10px; font-size: 12px;
  }}
  .url-badge {{
    display: inline-block;
    background: #1e293b;
    border: 1px solid #334155;
    border-radius: 6px;
    padding: 4px 12px;
    margin-bottom: 14px;
    font-size: 11px;
  }}
  .url-badge code {{
    color: #5eead4;
    font-family: 'Consolas',monospace;
  }}
  .screenshot {{
    width: 100%;
    border-radius: 8px;
    box-shadow: 0 8px 30px rgba(0,0,0,0.5), 0 0 0 1px rgba(255,255,255,0.05);
    display: block;
    margin-top: 4px;
  }}
  .no-screenshot {{
    background: #1e293b;
    border: 2px dashed #334155;
    border-radius: 8px;
    padding: 32px; text-align: center;
    color: #64748b; font-size: 12px;
  }}
  .denied-badge {{
    background: #422006;
    border: 1px solid #d97706;
    color: #fde68a;
    border-radius: 6px;
    padding: 6px 14px;
    font-size: 11px;
    margin-top: 8px;
    display: inline-block;
  }}

  /* ── INFO / WARN / STEPS BOXES ── */
  .info-box {{
    background: linear-gradient(135deg, #0f2a26, #0c1e1c);
    border: 1px solid #0d9488;
    border-left: 4px solid #14b8a6;
    border-radius: 8px;
    padding: 16px 20px; margin: 20px 0;
    color: #99f6e4;
  }}
  .info-box strong {{ color: #5eead4; display: block; margin-bottom: 10px; }}
  .warning-box {{
    background: linear-gradient(135deg, #2d1f00, #1c1400);
    border: 1px solid #d97706;
    border-left: 4px solid #f59e0b;
    border-radius: 8px;
    padding: 16px 20px; margin: 20px 0;
    color: #fde68a;
  }}
  .warning-box strong {{ color: #fbbf24; }}
  .steps-box {{
    background: #0f172a;
    border: 1px solid #334155;
    border-radius: 8px;
    padding: 16px 20px; margin: 20px 0;
    color: #cbd5e1;
  }}
  .steps-box strong {{ color: #f1f5f9; display: block; margin-bottom: 12px; }}
  .steps-list {{
    counter-reset: steps; list-style: none; padding: 0;
  }}
  .steps-list li {{
    counter-increment: steps;
    padding: 8px 0 8px 40px;
    position: relative;
    border-bottom: 1px solid #1e293b;
    font-size: 12px;
  }}
  .steps-list li:last-child {{ border-bottom: none; }}
  .steps-list li::before {{
    content: counter(steps);
    position: absolute; left: 0;
    width: 26px; height: 26px;
    background: linear-gradient(135deg, #0d9488, #14b8a6);
    color: white; border-radius: 50%;
    display: flex; align-items: center; justify-content: center;
    font-size: 11px; font-weight: 700;
    line-height: 26px; text-align: center;
  }}
  table {{ width:100%; border-collapse:collapse; margin:16px 0; font-size:11px; }}
  th {{ background:#0d9488; color:#fff; padding:8px 12px; text-align:left; }}
  td {{ padding:8px 12px; border-bottom:1px solid #1e293b; color:#cbd5e1; }}
  tr:nth-child(even) td {{ background:#1e293b; }}

  /* ── CONTRAPORTADA ── */
  .backcover {{
    page-break-before: always;
    width: 210mm; min-height: 297mm;
    background: linear-gradient(135deg, #0f172a, #134e4a);
    display: flex; flex-direction: column;
    align-items: center; justify-content: center;
    text-align: center; padding: 60px 40px;
  }}
  .backcover h2 {{
    font-size: 28px; font-weight: 800; color: #f8fafc; margin-bottom: 16px;
  }}
  .backcover p {{
    color: #64748b; font-size: 13px;
    max-width: 400px; line-height: 1.8;
  }}
  .backcover .logo-text {{
    font-size: 48px; font-weight: 900;
    background: linear-gradient(135deg, #0d9488, #14b8a6);
    -webkit-background-clip: text;
    -webkit-text-fill-color: transparent;
    background-clip: text;
    margin-bottom: 24px;
  }}

  @media print {{
    body {{ background: #0f172a; }}
    .cover, .toc, section, .backcover {{ page-break-after: always; }}
  }}
</style>
</head>
<body>

<!-- ════ PORTADA ════ -->
<div class="cover">
  <div class="cover-badge">Documentación Interna</div>
  {logo_img}
  <h1>Manual de <span>Staff</span></h1>
  <div class="cover-subtitle">Space Cheer — Operaciones, Eventos y Hospitalidad</div>
  <div class="cover-divider"></div>
  <div style="position:relative;z-index:1;color:#94a3b8;font-size:13px;line-height:2">
    <div>Versión 1.0 &nbsp;·&nbsp; Junio 2026</div>
    <div style="margin-top:24px;color:#475569;font-size:11px">
      Este documento cubre pedidos, producción, configuración,<br/>
      competencias, hospitalidad y perfil de usuario para el rol Staff.
    </div>
  </div>
</div>

<!-- ════ ÍNDICE ════ -->
<div class="toc">
  <h2>Índice de Contenidos</h2>

  <div class="toc-item part">
    <span>§ 1 — Acceso al Sistema</span>
    <span class="toc-num">Pág. 3</span>
  </div>

  <div class="toc-item part">
    <span>§ 2 — Gestión de Pedidos</span>
    <span class="toc-num">Pág. 4</span>
  </div>
  <div class="toc-item toc-sub"><span>Lista de pedidos</span><span class="toc-dots"></span><span>4</span></div>

  <div class="toc-item part">
    <span>§ 3 — Módulo de Producción</span>
    <span class="toc-num">Pág. 5</span>
  </div>
  <div class="toc-item toc-sub"><span>Panel de producción</span><span class="toc-dots"></span><span>5</span></div>
  <div class="toc-item toc-sub"><span>Job #2 — Detalle</span><span class="toc-dots"></span><span>5</span></div>
  <div class="toc-item toc-sub"><span>Reglamento</span><span class="toc-dots"></span><span>5</span></div>
  <div class="toc-item toc-sub"><span>Reportes de error</span><span class="toc-dots"></span><span>5</span></div>

  <div class="toc-item part">
    <span>§ 4 — Configuración de Producción</span>
    <span class="toc-num">Pág. 6</span>
  </div>
  <div class="toc-item toc-sub"><span>Etapas</span><span class="toc-dots"></span><span>6</span></div>
  <div class="toc-item toc-sub"><span>Roles</span><span class="toc-dots"></span><span>6</span></div>
  <div class="toc-item toc-sub"><span>Responsabilidades</span><span class="toc-dots"></span><span>6</span></div>
  <div class="toc-item toc-sub"><span>Operarios</span><span class="toc-dots"></span><span>6</span></div>

  <div class="toc-item part">
    <span>§ 5 — Competencias y Eventos</span>
    <span class="toc-num">Pág. 7</span>
  </div>
  <div class="toc-item toc-sub"><span>Lista de eventos</span><span class="toc-dots"></span><span>7</span></div>
  <div class="toc-item toc-sub"><span>Evento Grand Prix</span><span class="toc-dots"></span><span>7</span></div>
  <div class="toc-item toc-sub"><span>Inscripciones</span><span class="toc-dots"></span><span>7</span></div>
  <div class="toc-item toc-sub"><span>Staff del evento</span><span class="toc-dots"></span><span>7</span></div>

  <div class="toc-item part">
    <span>§ 6 — Hospitalidad</span>
    <span class="toc-num">Pág. 8</span>
  </div>
  <div class="toc-item toc-sub"><span>Índice hospitalidad</span><span class="toc-dots"></span><span>8</span></div>
  <div class="toc-item toc-sub"><span>Hoteles del evento</span><span class="toc-dots"></span><span>8</span></div>
  <div class="toc-item toc-sub"><span>Reservaciones</span><span class="toc-dots"></span><span>8</span></div>

  <div class="toc-item part">
    <span>§ 7 — Mi Perfil</span>
    <span class="toc-num">Pág. 9</span>
  </div>
  <div class="toc-item toc-sub"><span>Editar perfil</span><span class="toc-dots"></span><span>9</span></div>
  <div class="toc-item toc-sub"><span>Configuración de cuenta</span><span class="toc-dots"></span><span>9</span></div>
</div>

<!-- ════ § 1 ACCESO AL SISTEMA ════ -->
<section>
  <h2 class="section-title">§ 1 — Acceso al Sistema</h2>

  <p style="color:#94a3b8;margin-bottom:24px">
    Ingresa a Space Cheer en
    <code style="color:#5eead4;background:#1e293b;padding:2px 6px;border-radius:4px">/accounts/login/</code>
    con tu usuario y contraseña de Staff. Tras el login accedes directamente al dashboard.
  </p>

  <div class="info-box">
    <strong>Permisos del rol Staff</strong>
    <table>
      <tr><th>Módulo</th><th>Acceso</th></tr>
      <tr><td>Pedidos (admin)</td><td>Lectura y gestión</td></tr>
      <tr><td>Panel de Producción</td><td>Lectura y seguimiento</td></tr>
      <tr><td>Reglamento</td><td>Lectura</td></tr>
      <tr><td>Reportes de Error</td><td>Lectura</td></tr>
      <tr><td>Configuración de Producción</td><td>Lectura (etapas, roles, operarios)</td></tr>
      <tr><td>Competencias y Eventos</td><td>Lectura y coordinación</td></tr>
      <tr><td>Hospitalidad</td><td>Lectura y coordinación</td></tr>
      <tr><td>Mi Perfil</td><td>Edición propia</td></tr>
    </table>
  </div>

  <div class="steps-box">
    <strong>Cómo iniciar sesión</strong>
    <ol class="steps-list">
      <li>Abre el navegador y accede a <code>/accounts/login/</code>.</li>
      <li>Ingresa tu nombre de usuario (sin @ ni correo).</li>
      <li>Ingresa tu contraseña y haz clic en <strong>Iniciar sesión</strong>.</li>
      <li>Si el sistema te pide completar tu perfil, llena los datos obligatorios antes de continuar.</li>
    </ol>
  </div>

  <div class="page-section">
    <h3>Pantalla de Login</h3>
    <p class="page-desc">Formulario de inicio de sesión con usuario y contraseña</p>
    <div class="url-badge"><code>/accounts/login/</code></div>
    {login_img}
  </div>
</section>

<!-- ════ § 2 GESTIÓN DE PEDIDOS ════ -->
<section>
  <h2 class="section-title">§ 2 — Gestión de Pedidos</h2>

  <p style="color:#94a3b8;margin-bottom:24px">
    Como Staff tienes acceso al panel de administración de pedidos en
    <code style="color:#5eead4;background:#1e293b;padding:2px 6px;border-radius:4px">/orders/admin/orders/</code>.
    Desde aquí puedes consultar el estado de todos los pedidos y coordinar las acciones correspondientes.
  </p>

  <div class="info-box">
    <strong>Estados de un pedido</strong>
    <table>
      <tr><th>Estado</th><th>Significado</th></tr>
      <tr><td>DRAFT</td><td>Borrador — en construcción por el equipo</td></tr>
      <tr><td>PENDING</td><td>Pendiente — esperando aprobación del administrador</td></tr>
      <tr><td>DESIGN_APPROVED</td><td>Diseño aprobado — listo para producción</td></tr>
      <tr><td>IN_PRODUCTION</td><td>En producción activa</td></tr>
      <tr><td>DELIVERED</td><td>Entregado al cliente</td></tr>
      <tr><td>CANCELLED</td><td>Cancelado</td></tr>
    </table>
  </div>

  <div class="warning-box">
    <strong>Importante:</strong> Los cambios de estado son irreversibles sin autorización del administrador.
    Verifica la información antes de confirmar cualquier acción.
  </div>

  {"".join(render_screenshot(k, v) for k, v in orders_pages)}
</section>

<!-- ════ § 3 MÓDULO DE PRODUCCIÓN ════ -->
<section>
  <h2 class="section-title">§ 3 — Módulo de Producción</h2>

  <p style="color:#94a3b8;margin-bottom:24px">
    El módulo de producción en
    <code style="color:#5eead4;background:#1e293b;padding:2px 6px;border-radius:4px">/production/admin/</code>
    muestra todos los Jobs activos, su progreso y las tareas de cada operario.
  </p>

  <div class="info-box">
    <strong>Conceptos clave</strong>
    <ul style="margin-top:8px;padding-left:20px;color:#99f6e4;font-size:12px">
      <li><strong>Job</strong>: Unidad de trabajo vinculada a un pedido aprobado (IN_PRODUCTION).</li>
      <li><strong>Tarea</strong>: Paso específico del Job (corte, costura, acabado…).</li>
      <li><strong>Reglamento</strong>: Normas del proceso — lectura obligatoria para todo el Staff.</li>
      <li><strong>Reporte de Error</strong>: Incidencia documentada por un operario durante producción.</li>
    </ul>
  </div>

  <div class="steps-box">
    <strong>Monitoreo de producción — flujo diario</strong>
    <ol class="steps-list">
      <li>Revisa el panel <code>/production/admin/</code> al inicio del turno para ver el estado general.</li>
      <li>Entra al Job urgente (indicador rojo) y verifica las tareas pendientes.</li>
      <li>Consulta los reportes de error en <code>/production/errores/</code> y escala al administrador.</li>
      <li>Actualiza al equipo sobre bloqueos o retrasos detectados.</li>
    </ol>
  </div>

  {"".join(render_screenshot(k, v) for k, v in production_pages)}
</section>

<!-- ════ § 4 CONFIGURACIÓN DE PRODUCCIÓN ════ -->
<section>
  <h2 class="section-title">§ 4 — Configuración de Producción</h2>

  <p style="color:#94a3b8;margin-bottom:24px">
    La sección de configuración permite al Staff consultar (y según permisos, gestionar) los catálogos
    que parametrizan el sistema de producción: etapas, roles, responsabilidades y operarios.
  </p>

  <div class="info-box">
    <strong>Catálogos disponibles para Staff</strong>
    <table>
      <tr><th>Catálogo</th><th>URL</th><th>Descripción</th></tr>
      <tr><td>Etapas</td><td>/production/config/stages/</td><td>Fases del proceso de fabricación</td></tr>
      <tr><td>Roles</td><td>/production/config/roles/</td><td>Perfiles de operario configurables</td></tr>
      <tr><td>Responsabilidades</td><td>/production/config/responsabilidades/</td><td>Qué hace cada rol en cada etapa</td></tr>
      <tr><td>Operarios</td><td>/production/config/operarios/</td><td>Trabajadores registrados en el sistema</td></tr>
    </table>
  </div>

  {"".join(render_screenshot(k, v) for k, v in config_pages)}
</section>

<!-- ════ § 5 COMPETENCIAS Y EVENTOS ════ -->
<section>
  <h2 class="section-title">§ 5 — Competencias y Eventos</h2>

  <p style="color:#94a3b8;margin-bottom:24px">
    El módulo de Competencias en
    <code style="color:#5eead4;background:#1e293b;padding:2px 6px;border-radius:4px">/events/</code>
    gestiona los eventos de cheerleading: inscripciones de equipos, asignación de staff y logística del día.
  </p>

  <div class="steps-box">
    <strong>Responsabilidades del Staff en un evento</strong>
    <ol class="steps-list">
      <li>Consulta la lista de eventos activos y el detalle de cada uno.</li>
      <li>Verifica las inscripciones de los equipos participantes.</li>
      <li>Confirma tu asignación como Staff del evento y los roles asignados.</li>
      <li>Coordina con hospitalidad para el alojamiento de equipos y jueces.</li>
    </ol>
  </div>

  {"".join(render_screenshot(k, v) for k, v in events_pages)}
</section>

<!-- ════ § 6 HOSPITALIDAD ════ -->
<section>
  <h2 class="section-title">§ 6 — Hospitalidad</h2>

  <p style="color:#94a3b8;margin-bottom:24px">
    El módulo de Hospitalidad en
    <code style="color:#5eead4;background:#1e293b;padding:2px 6px;border-radius:4px">/hospitality/</code>
    centraliza el alojamiento para competencias: hoteles disponibles, reservaciones activas y
    coordinación con los equipos participantes.
  </p>

  <div class="info-box">
    <strong>Flujo de hospitalidad para un evento</strong>
    <ol style="margin-top:8px;padding-left:20px;color:#99f6e4;font-size:12px;line-height:2">
      <li>Revisar la lista de hoteles disponibles para el evento.</li>
      <li>Verificar las reservaciones ya confirmadas.</li>
      <li>Coordinar con los equipos sobre check-in y check-out.</li>
      <li>Reportar cualquier incidencia al administrador.</li>
    </ol>
  </div>

  {"".join(render_screenshot(k, v) for k, v in hospitality_pages)}
</section>

<!-- ════ § 7 MI PERFIL ════ -->
<section>
  <h2 class="section-title">§ 7 — Mi Perfil</h2>

  <p style="color:#94a3b8;margin-bottom:24px">
    Mantén tus datos actualizados en
    <code style="color:#5eead4;background:#1e293b;padding:2px 6px;border-radius:4px">/accounts/profile/edit/</code>.
    Tu información de contacto es esencial para la coordinación del equipo.
  </p>

  <div class="warning-box">
    <strong>Recuerda:</strong> Un perfil incompleto puede impedirte acceder a ciertas vistas del sistema.
    Asegúrate de que <em>profile_completed</em> esté marcado como verdadero.
  </div>

  {"".join(render_screenshot(k, v) for k, v in profile_pages)}
</section>

<!-- ════ CONTRAPORTADA ════ -->
<div class="backcover">
  <div class="logo-text">★ SPACE CHEER</div>
  <h2>Manual de Staff</h2>
  <p>
    Operaciones, Eventos y Hospitalidad<br/>
    Versión 1.0 — Junio 2026<br/><br/>
    Este documento es de uso interno.<br/>
    Ante dudas, contactar al administrador del sistema.
  </p>
  <div style="margin-top:48px;color:#334155;font-size:11px">
    Generado automáticamente con capturas reales del entorno local<br/>
    http://127.0.0.1:8000
  </div>
</div>

</body>
</html>"""
    return html


def main():
    print("=" * 60)
    print("GENERADOR DE MANUAL STAFF — SPACE CHEER")
    print("=" * 60)
    ensure_dir()

    # Clasificar páginas en diccionario indexado por filename
    section_map = {}
    for url_path, filename, title, desc, section in PAGES:
        section_map[filename] = {
            "url": url_path,
            "title": title,
            "desc": desc,
            "section": section,
            "ok": False,
            "path": "",
        }

    ok_count     = 0
    denied_count = 0
    error_count  = 0
    errors_detail = []
    login_screenshot_path = ""

    print("\n[1] Iniciando Playwright...")
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        context = browser.new_context(
            viewport={"width": 1440, "height": 900},
            ignore_https_errors=True,
        )
        page = context.new_page()

        # ── LOGIN ──
        print(f"\n[2] Realizando login como {USERNAME}...")
        final_url = login_capture(page, BASE_URL)
        if "/accounts/login/" in final_url:
            print("    ERROR: Login fallido. Verifica que el servidor corra en :8000 y el usuario exista.")
            browser.close()
            return
        print("    Login exitoso.")

        # Captura de la pantalla post-login (dashboard)
        login_ss_path = SCREENSHOTS_DIR / "login_ok.png"
        page.screenshot(path=str(login_ss_path), full_page=True)
        login_screenshot_path = str(login_ss_path)
        print(f"    Login screenshot: {login_screenshot_path}")

        # ── CAPTURAS ──
        print("\n[3] Capturando paginas...")
        for url_path, filename, title, desc, section in PAGES:
            print(f"    -> {title} ({url_path})")
            ok, result = capture_page_at(page, BASE_URL, url_path, filename)
            section_map[filename]["ok"] = ok
            section_map[filename]["path"] = result

            if ok is True:
                ok_count += 1
                print(f"       OK: {result}")
            elif ok == "denied":
                denied_count += 1
                print(f"       DENIED (403, capturado): {result}")
            else:
                error_count += 1
                errors_detail.append((title, url_path, result))
                print(f"       ERROR: {result}")

        browser.close()

    # ── GENERAR HTML ──
    print("\n[4] Generando HTML del manual...")
    html_content = build_html(section_map, login_screenshot_path)
    html_path = SCREENSHOTS_DIR / "manual_staff.html"
    with open(str(html_path), "w", encoding="utf-8") as f:
        f.write(html_content)
    print(f"    HTML guardado: {html_path}")

    # ── CONVERTIR A PDF ──
    print("\n[5] Convirtiendo a PDF...")
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        pg = browser.new_page()
        pg.goto(f"file:///{html_path.as_posix()}", wait_until="networkidle")
        time.sleep(2)
        pg.pdf(
            path=str(OUTPUT_PDF),
            format="A4",
            print_background=True,
            margin={"top": "0", "bottom": "0", "left": "0", "right": "0"},
        )
        browser.close()

    # ── REPORTE FINAL ──
    pdf_size = OUTPUT_PDF.stat().st_size if OUTPUT_PDF.exists() else 0
    pdf_size_mb = pdf_size / (1024 * 1024)
    total_captures = ok_count + denied_count

    print("\n" + "=" * 60)
    print("REPORTE FINAL")
    print("=" * 60)
    print(f"  Capturas OK           : {ok_count}")
    print(f"  Capturas 403 (denied) : {denied_count}")
    print(f"  Capturas con error    : {error_count}")
    if errors_detail:
        for t, u, e in errors_detail:
            print(f"    - {t} ({u}): {e}")
    print(f"  Total capturas en PDF : {total_captures + 1}  (incluye login)")
    print(f"  PDF generado en       : {OUTPUT_PDF}")
    print(f"  Tamano del PDF        : {pdf_size_mb:.2f} MB")
    print("=" * 60)


if __name__ == "__main__":
    main()
