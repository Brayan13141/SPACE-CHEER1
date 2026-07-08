# -*- coding: utf-8 -*-
"""
Manual de Administrador - Space Cheer
Generador de PDF con capturas reales del entorno local
Ejecutar: PYTHONUTF8=1 python gen_manual_admin.py
"""
import sys
import time
import base64
from pathlib import Path
from playwright.sync_api import sync_playwright

LOGO_PATH = Path("C:/Users/Lenovo/Documents/SPACE-CHEER/space_cheer/static/IMAGES/Logo_sin_fondo_blanco.png")


def logo_data_uri() -> str:
    if LOGO_PATH.exists():
        with open(LOGO_PATH, "rb") as f:
            return f"data:image/png;base64,{base64.b64encode(f.read()).decode()}"
    return ""


# ─── Configuración ───────────────────────────────────────────────────────────
BASE_URL = "http://127.0.0.1:8000"
LOGIN_URL = f"{BASE_URL}/accounts/login/"
USERNAME = "admin_test"
PASSWORD = "Test1234!"
SCREENSHOTS_DIR = Path("C:/Users/Lenovo/Documents/SPACE-CHEER/manual_screenshots")
OUTPUT_PDF = Path("C:/Users/Lenovo/Documents/SPACE-CHEER/manual_admin.pdf")

PAGES = [
    # (url_path, filename, título, descripción)

    # ── ÓRDENES ──────────────────────────────────────────────────────────────
    ("/orders/admin/orders/",          "orders_list",         "Lista de Pedidos",              "Vista general de todos los pedidos del sistema"),
    ("/orders/admin/orders/18/",       "order_18_pending",    "Pedido #18 — PENDIENTE",        "Pedido en estado Pendiente con opciones de acción"),
    ("/orders/admin/orders/19/",       "order_19_approved",   "Pedido #19 — DISEÑO APROBADO",  "Pedido con diseño aprobado listo para producción"),
    ("/orders/admin/orders/20/",       "order_20_production", "Pedido #20 — EN PRODUCCIÓN",    "Pedido en producción activa"),
    ("/orders/admin/orders/21/",       "order_21_delivered",  "Pedido #21 — ENTREGADO",        "Pedido ya entregado al equipo"),
    ("/orders/admin/orders/17/",       "order_17_draft",      "Pedido #17 — BORRADOR",         "Pedido en estado borrador pendiente de confirmación"),

    # ── PEDIDOS PERSONALES (OFFLINE) ────────────────────────────────────────
    ("/orders/admin/orders/?type=OFFLINE", "orders_offline_filter", "Filtro — Pedidos Personales", "Lista de pedidos filtrada por tipo Personal (offline)"),
    ("/orders/admin/offline/nuevo/",   "offline_order_create", "Nuevo Pedido Personal (Offline)", "Formulario de captura: cliente, productos y anticipo"),
    ("/orders/admin/clientes/",        "customer_list",        "Clientes",                      "Directorio de clientes de pedidos personales"),
    ("/orders/admin/orders/24/",       "order_24_offline",     "Pedido #24 — PERSONAL (Offline)", "Detalle de un pedido offline: cliente, pagos y medidas por producto"),

    # ── PRODUCCIÓN ────────────────────────────────────────────────────────────
    ("/production/admin/",             "production_panel",    "Panel de Producción",           "Vista general de estadísticas y jobs activos"),
    ("/production/admin/job/2/",       "production_job2",     "Job #2 — Detalle",              "Detalle del job con tareas y operarios asignados"),
    ("/production/reglamento/",        "production_reglamento","Reglamento de Operarios",      "Reglamento y políticas del área de producción"),
    ("/production/errores/",           "errors_list",         "Reportes de Error",             "Lista de todos los reportes de error"),
    ("/production/errores/1/",         "error_1_detail",      "Reporte de Error #1",           "Detalle del reporte con formulario de revisión integrado"),

    # ── CONFIGURACIÓN PRODUCCIÓN ─────────────────────────────────────────────
    ("/production/config/stages/",     "config_stages",       "Catálogo de Etapas",            "Configuración de etapas del proceso de producción"),
    ("/production/config/roles/",      "config_roles",        "Roles de Producción",           "Gestión de roles asignables a operarios"),
    ("/production/config/responsabilidades/", "config_resp",  "Responsabilidades",             "Configuración de responsabilidades por rol y etapa"),
    ("/production/config/operarios/",  "config_operarios",    "Gestión de Operarios",          "Lista y gestión de operarios del sistema"),
    ("/production/config/plantillas/", "config_plantillas",   "Plantillas de Producción",      "Plantillas de proceso reutilizables por tipo de producto"),
    ("/production/config/product-stages/", "config_prod_stages", "Etapas por Producto",        "Etapas del proceso asociadas a cada tipo de producto"),

    # ── EVENTOS ──────────────────────────────────────────────────────────────
    ("/events/",                       "events_list",         "Lista de Eventos",              "Vista general de todos los eventos/competencias"),
    ("/events/8/",                     "event_8_detail",      "Evento #8 — Grand Prix Espacial","Detalle del evento Grand Prix Espacial (REGISTRATION_OPEN)"),
    ("/events/8/registrations/",       "event_8_registrations","Inscripciones — Grand Prix",   "Equipos e individuos inscritos al Grand Prix Espacial"),
    ("/events/8/staff/",               "event_8_staff",       "Staff — Grand Prix",            "Personal asignado al Grand Prix Espacial"),
    ("/events/8/scores/",              "event_8_scores",      "Puntajes — Grand Prix",         "Registro de puntajes de participantes"),
    ("/events/8/results/",             "event_8_results",     "Resultados — Grand Prix",       "Resultados finales del Grand Prix Espacial"),

    # ── HOSPITALIDAD ─────────────────────────────────────────────────────────
    ("/hospitality/",                  "hospitality_panel",   "Panel de Hospitalidad",         "Vista general del módulo de hospitalidad"),
    ("/hospitality/event/8/hotels/",   "hospitality_hotels",  "Hoteles — Grand Prix",          "Hoteles disponibles para el Grand Prix Espacial"),
    ("/hospitality/event/8/stays/",    "hospitality_stays",   "Reservaciones — Grand Prix",    "Reservaciones de hospedaje del Grand Prix Espacial"),

    # ── PRODUCTOS Y EQUIPOS ───────────────────────────────────────────────────
    ("/products/catalog/",             "products_catalog",    "Catálogo de Productos",         "Catálogo completo de productos disponibles"),
    ("/teams/teams/",                  "teams_list",          "Gestión de Equipos",            "Lista y administración de todos los equipos"),
    ("/teams/categories/",             "teams_categories",    "Categorías de Equipos",         "Categorías de competencia configurables"),
    ("/teams/manage_athletes/",        "teams_athletes",      "Gestión de Atletas",            "Administración de atletas registrados en el sistema"),

    # ── PERFIL ────────────────────────────────────────────────────────────────
    ("/accounts/profile/edit/",        "profile_edit",        "Editar Perfil",                 "Formulario de edición del perfil del administrador"),
    ("/accounts/profile/settings/",    "profile_settings",    "Configuración de Cuenta",       "Ajustes de seguridad y preferencias de la cuenta"),
]


def ensure_dir():
    SCREENSHOTS_DIR.mkdir(parents=True, exist_ok=True)


def img_to_base64(path):
    """Convierte imagen a data URI base64."""
    with open(path, "rb") as f:
        data = base64.b64encode(f.read()).decode("utf-8")
    return f"data:image/png;base64,{data}"


def build_html(results):
    """Construye el HTML completo del manual."""
    _logo_uri = logo_data_uri()
    logo_img = (
        f'<img src="{_logo_uri}" alt="Space Cheer" '
        f'style="width:200px;margin-bottom:24px;position:relative;z-index:1;'
        f'filter:drop-shadow(0 0 20px rgba(220,38,38,0.4))">'
        if _logo_uri else ""
    )

    # Separar resultados por sección
    orders_pages      = [(r, results[r]) for r in results if results[r]["section"] == "orders"]
    prod_pages        = [(r, results[r]) for r in results if results[r]["section"] == "production"]
    error_pages       = [(r, results[r]) for r in results if results[r]["section"] == "errors"]
    config_pages      = [(r, results[r]) for r in results if results[r]["section"] == "config"]
    events_pages      = [(r, results[r]) for r in results if results[r]["section"] == "events"]
    hospitality_pages = [(r, results[r]) for r in results if results[r]["section"] == "hospitality"]
    products_pages    = [(r, results[r]) for r in results if results[r]["section"] == "products"]
    teams_pages       = [(r, results[r]) for r in results if results[r]["section"] == "teams"]
    profile_pages     = [(r, results[r]) for r in results if results[r]["section"] == "profile"]

    def render_page_section(key, data):
        title = data["title"]
        desc  = data["desc"]
        ok    = data["ok"]
        path  = data["path"]
        url   = data["url"]

        if ok and Path(path).exists():
            img_src = img_to_base64(path)
            img_html = f'<img src="{img_src}" alt="{title}" class="screenshot" />'
        else:
            img_html = f'<div class="no-screenshot"><span>&#9888; Pantalla no disponible: {path}</span></div>'

        return f"""
        <div class="page-section">
            <h3>{title}</h3>
            <p class="page-desc">{desc}</p>
            <div class="url-badge"><code>{url}</code></div>
            {img_html}
        </div>
        """

    def render_section(title, pages, section_num, extra_content=""):
        content = "".join(render_page_section(k, d) for k, d in pages)
        return f"""
        <section>
            <h2 class="section-title">Parte {section_num} &mdash; {title}</h2>
            {extra_content}
            {content}
        </section>
        """

    # ── Contenido extra para cada sección ────────────────────────────────────

    flow_diagram = """
    <div class="info-box">
        <strong>Flujo de estados de un Pedido</strong>
        <div class="state-flow">
            <span class="state draft">DRAFT</span>
            <span class="arrow">-&gt;</span>
            <span class="state pending">PENDING</span>
            <span class="arrow">-&gt;</span>
            <span class="state approved">DESIGN_APPROVED</span>
            <span class="arrow">-&gt;</span>
            <span class="state production">IN_PRODUCTION</span>
            <span class="arrow">-&gt;</span>
            <span class="state delivered">DELIVERED</span>
        </div>
        <div class="state-flow" style="margin-top:8px">
            <span style="color:#6b7280;font-size:0.85em">Desde cualquier estado:</span>
            <span class="arrow">-&gt;</span>
            <span class="state cancelled">CANCELLED</span>
        </div>
    </div>
    """

    approval_steps = """
    <div class="steps-box">
        <strong>Flujo de Aprobación &mdash; Paso a paso</strong>
        <ol class="steps-list">
            <li>El equipo crea el pedido en estado <strong>DRAFT</strong> &mdash; borrador inicial con datos básicos.</li>
            <li>Al confirmar los detalles, el pedido pasa a <strong>PENDING</strong> &mdash; esperando revisión del administrador.</li>
            <li>El administrador revisa el diseño y aprueba -&gt; estado <strong>DESIGN_APPROVED</strong>.</li>
            <li>Se genera un Job de producción y el pedido entra a <strong>IN_PRODUCTION</strong>.</li>
            <li>Una vez fabricado y entregado, se marca como <strong>DELIVERED</strong>.</li>
            <li>En cualquier punto se puede cancelar -&gt; <strong>CANCELLED</strong>.</li>
        </ol>
    </div>
    <div class="warning-box">
        <strong>Advertencia:</strong> La cancelación de un pedido <em>IN_PRODUCTION</em> debe coordinarse con el área de producción, ya que puede haber materiales en proceso.
    </div>
    """

    production_intro = """
    <p style="color:#94a3b8;margin-bottom:24px">
        El módulo de producción gestiona los Jobs (trabajos de fabricación) asociados a los pedidos aprobados.
        Cada Job contiene tareas asignadas a operarios específicos con seguimiento de progreso en tiempo real.
    </p>
    <div class="info-box">
        <strong>Conceptos clave</strong>
        <ul style="margin-top:8px;padding-left:20px;color:#bfdbfe;font-size:12px">
            <li><strong>Job</strong>: Unidad de trabajo de producción vinculada a un pedido aprobado.</li>
            <li><strong>Tarea</strong>: Paso específico dentro del Job (ej: corte, costura, acabado).</li>
            <li><strong>Operario</strong>: Trabajador asignado a una o más tareas.</li>
            <li><strong>Etapa</strong>: Fase del proceso de producción (configurable en /config/stages/).</li>
            <li><strong>Reglamento</strong>: Políticas y normas que rigen el trabajo del área de producción.</li>
        </ul>
    </div>
    """

    errors_intro = """
    <p style="color:#94a3b8;margin-bottom:24px">
        Los reportes de error permiten a operarios y supervisores documentar incidencias durante la producción.
        El administrador revisa cada reporte y toma la decisión: corregir, rechazar o escalar.
    </p>
    <div class="steps-box">
        <strong>Proceso de revisión de un reporte de error</strong>
        <ol class="steps-list">
            <li>Ir a <code>/production/errores/</code> para ver todos los reportes pendientes.</li>
            <li>Hacer clic en el reporte para ver el detalle completo del incidente.</li>
            <li>Revisar el reporte desde <code>/production/errores/[id]/revisar/</code>.</li>
            <li>Registrar la decisión: <strong>RESUELTO</strong> (error corregido) o <strong>RECHAZADO</strong> (no procede).</li>
            <li>Si el error afecta el Job de producción, coordinar con el supervisor de planta.</li>
        </ol>
    </div>
    <div class="warning-box">
        <strong>Advertencia:</strong> Los reportes en estado <strong>PENDING</strong> bloquean el avance de la tarea asociada
        hasta que el administrador los revise y resuelva.
    </div>
    """

    config_intro = """
    <p style="color:#94a3b8;margin-bottom:24px">
        La sección de configuración permite al administrador parametrizar el sistema de producción:
        etapas del proceso, roles de los trabajadores, responsabilidades, plantillas reutilizables
        y la asignación de etapas por tipo de producto.
    </p>
    <div class="info-box">
        <strong>Orden recomendado de configuración (primera vez)</strong>
        <ol style="margin-top:8px;padding-left:20px;color:#bfdbfe;font-size:12px;line-height:2">
            <li>Crear <strong>Etapas</strong> -&gt; define los pasos del proceso de producción.</li>
            <li>Crear <strong>Roles</strong> -&gt; define los perfiles de operario.</li>
            <li>Asignar <strong>Responsabilidades</strong> -&gt; vincula roles con etapas.</li>
            <li>Crear <strong>Plantillas</strong> -&gt; agrupa etapas en procesos reutilizables.</li>
            <li>Configurar <strong>Etapas por Producto</strong> -&gt; adapta el proceso a cada tipo de producto.</li>
            <li>Dar de alta <strong>Operarios</strong> -&gt; registra a los trabajadores del taller.</li>
        </ol>
    </div>
    """

    events_intro = """
    <p style="color:#94a3b8;margin-bottom:24px">
        El módulo de eventos gestiona competencias y torneos de cheerleading. El administrador
        puede crear eventos, gestionar inscripciones de equipos, asignar staff, registrar
        puntajes y publicar resultados finales.
    </p>
    <div class="info-box">
        <strong>Estados de un Evento</strong>
        <div class="state-flow" style="margin-top:12px">
            <span class="state draft">DRAFT</span>
            <span class="arrow">-&gt;</span>
            <span class="state pending">REGISTRATION_OPEN</span>
            <span class="arrow">-&gt;</span>
            <span class="state production">IN_PROGRESS</span>
            <span class="arrow">-&gt;</span>
            <span class="state delivered">COMPLETED</span>
        </div>
    </div>
    <div class="steps-box">
        <strong>Gestión de un Evento &mdash; Flujo completo</strong>
        <ol class="steps-list">
            <li>Crear el evento con fecha, lugar y categorías disponibles.</li>
            <li>Abrir inscripciones: los equipos pueden registrarse desde el portal.</li>
            <li>Asignar staff: jueces, coordinadores y personal de apoyo.</li>
            <li>Durante el evento: registrar puntajes en tiempo real por rutina.</li>
            <li>Al finalizar: publicar resultados y cerrar el evento como COMPLETED.</li>
        </ol>
    </div>
    """

    hospitality_intro = """
    <p style="color:#94a3b8;margin-bottom:24px">
        El módulo de hospitalidad gestiona el alojamiento de equipos durante los eventos.
        El administrador puede registrar hoteles disponibles, gestionar habitaciones
        y administrar las reservaciones (stays) de los equipos participantes.
    </p>
    <div class="info-box">
        <strong>Conceptos clave de Hospitalidad</strong>
        <ul style="margin-top:8px;padding-left:20px;color:#bfdbfe;font-size:12px">
            <li><strong>Hotel</strong>: Establecimiento disponible para el evento, con habitaciones configuradas.</li>
            <li><strong>Stay</strong>: Reservación de un equipo o persona en un hotel para fechas específicas.</li>
            <li><strong>Room</strong>: Habitación individual dentro del hotel con capacidad y precio.</li>
        </ul>
    </div>
    """

    products_teams_intro = """
    <p style="color:#94a3b8;margin-bottom:24px">
        El catálogo de productos define los uniformes y artículos disponibles para ordenar.
        La gestión de equipos permite al administrador ver, editar y supervisar todos los
        equipos registrados en la plataforma, así como sus atletas y categorías.
    </p>
    <div class="info-box">
        <strong>Tipos de producto</strong>
        <ul style="margin-top:8px;padding-left:20px;color:#bfdbfe;font-size:12px">
            <li><strong>GLOBAL</strong>: Disponible para todos los equipos, talla estándar.</li>
            <li><strong>TEAM_CUSTOM</strong>: Personalizado con colores/logotipo del equipo.</li>
            <li><strong>ATHLETE_CUSTOM</strong>: Fabricado con medidas individuales del atleta.</li>
        </ul>
    </div>
    """

    profile_intro = """
    <p style="color:#94a3b8;margin-bottom:24px">
        La sección de perfil permite al administrador actualizar sus datos personales,
        foto de perfil, información de contacto y configurar las preferencias
        de seguridad de su cuenta.
    </p>
    <div class="warning-box">
        <strong>Nota de seguridad:</strong> Los cambios de contraseña requieren confirmar la contraseña actual.
        Se recomienda usar contraseñas de al menos 12 caracteres con letras, números y símbolos.
    </div>
    """

    html = f"""<!DOCTYPE html>
<html lang="es">
<head>
<meta charset="UTF-8"/>
<meta name="viewport" content="width=device-width, initial-scale=1"/>
<title>Manual de Administrador &mdash; Space Cheer</title>
<style>
  @import url('https://fonts.googleapis.com/css2?family=Inter:wght@300;400;600;700;900&display=swap');

  * {{ box-sizing: border-box; margin: 0; padding: 0; }}

  body {{
    font-family: 'Inter', 'Segoe UI', Arial, sans-serif;
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
    background: linear-gradient(135deg, #0f172a 0%, #1e293b 50%, #0f172a 100%);
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
    background: radial-gradient(circle, rgba(220,38,38,0.15) 0%, transparent 70%);
    border-radius: 50%;
  }}
  .cover::after {{
    content: '';
    position: absolute;
    bottom: -100px; right: -100px;
    width: 400px; height: 400px;
    background: radial-gradient(circle, rgba(234,88,12,0.12) 0%, transparent 70%);
    border-radius: 50%;
  }}
  .cover-badge {{
    background: linear-gradient(135deg, #dc2626, #ea580c);
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
    background: linear-gradient(135deg, #dc2626, #ea580c);
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
    width: 80px;
    height: 4px;
    background: linear-gradient(90deg, #dc2626, #ea580c);
    border-radius: 2px;
    margin: 32px auto;
    position: relative;
    z-index: 1;
  }}
  .cover-meta {{
    position: relative;
    z-index: 1;
    color: #64748b;
    font-size: 12px;
  }}
  .cover-meta strong {{ color: #94a3b8; }}

  /* ── ÍNDICE ── */
  .toc {{
    page-break-after: always;
    padding: 50px 40px;
    min-height: 297mm;
  }}
  .toc h2 {{
    font-size: 28px;
    font-weight: 800;
    color: #f8fafc;
    margin-bottom: 32px;
    padding-bottom: 12px;
    border-bottom: 3px solid #dc2626;
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
    font-weight: 700;
    color: #f8fafc;
    font-size: 14px;
    margin-top: 16px;
    border-bottom: 2px solid #334155;
    padding-bottom: 8px;
  }}
  .toc-item.part .toc-num {{
    background: linear-gradient(135deg, #dc2626, #ea580c);
    color: white;
    padding: 2px 10px;
    border-radius: 12px;
    font-size: 11px;
  }}
  .toc-sub {{
    padding-left: 20px;
    color: #94a3b8;
    font-size: 12px;
  }}
  .toc-dots {{
    flex: 1;
    margin: 0 12px;
    border-bottom: 1px dotted #334155;
  }}

  /* ── SECCIONES ── */
  section {{
    padding: 40px;
    page-break-before: always;
  }}
  .section-title {{
    font-size: 24px;
    font-weight: 800;
    color: #f8fafc;
    padding: 16px 24px;
    background: linear-gradient(135deg, #1e293b, #0f172a);
    border-left: 5px solid #dc2626;
    border-radius: 0 8px 8px 0;
    margin-bottom: 32px;
  }}
  h3 {{
    font-size: 16px;
    font-weight: 700;
    color: #f1f5f9;
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
    color: #94a3b8;
    margin-bottom: 10px;
    font-size: 12px;
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
    color: #7dd3fc;
    font-family: 'Consolas', monospace;
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
    padding: 32px;
    text-align: center;
    color: #64748b;
    font-size: 12px;
  }}

  /* ── INFO BOXES ── */
  .info-box {{
    background: linear-gradient(135deg, #0f2a4a, #0c1a2e);
    border: 1px solid #1d4ed8;
    border-left: 4px solid #3b82f6;
    border-radius: 8px;
    padding: 16px 20px;
    margin: 20px 0;
    color: #bfdbfe;
  }}
  .info-box strong {{ color: #93c5fd; display: block; margin-bottom: 10px; }}
  .warning-box {{
    background: linear-gradient(135deg, #2d1f00, #1c1400);
    border: 1px solid #d97706;
    border-left: 4px solid #f59e0b;
    border-radius: 8px;
    padding: 16px 20px;
    margin: 20px 0;
    color: #fde68a;
  }}
  .warning-box strong {{ color: #fbbf24; }}

  /* ── FLUJO DE ESTADOS ── */
  .state-flow {{
    display: flex;
    align-items: center;
    flex-wrap: wrap;
    gap: 8px;
    margin-top: 12px;
  }}
  .state {{
    padding: 5px 14px;
    border-radius: 20px;
    font-size: 11px;
    font-weight: 700;
    letter-spacing: 0.5px;
    text-transform: uppercase;
  }}
  .state.draft     {{ background: #374151; color: #9ca3af; border: 1px solid #4b5563; }}
  .state.pending   {{ background: #1e3a5f; color: #60a5fa; border: 1px solid #2563eb; }}
  .state.approved  {{ background: #14532d; color: #4ade80; border: 1px solid #16a34a; }}
  .state.production{{ background: #7c2d12; color: #fb923c; border: 1px solid #ea580c; }}
  .state.delivered {{ background: #1e1b4b; color: #a78bfa; border: 1px solid #7c3aed; }}
  .state.cancelled {{ background: #450a0a; color: #f87171; border: 1px solid #dc2626; }}
  .arrow {{ color: #475569; font-size: 18px; font-weight: bold; }}

  /* ── PASOS ── */
  .steps-box {{
    background: #0f172a;
    border: 1px solid #334155;
    border-radius: 8px;
    padding: 16px 20px;
    margin: 20px 0;
    color: #cbd5e1;
  }}
  .steps-box strong {{ color: #f1f5f9; display: block; margin-bottom: 12px; }}
  .steps-list {{
    counter-reset: steps;
    list-style: none;
    padding: 0;
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
    position: absolute;
    left: 0;
    width: 26px;
    height: 26px;
    background: linear-gradient(135deg, #dc2626, #ea580c);
    color: white;
    border-radius: 50%;
    display: flex;
    align-items: center;
    justify-content: center;
    font-size: 11px;
    font-weight: 700;
    line-height: 26px;
    text-align: center;
  }}

  /* ── CONTRAPORTADA ── */
  .backcover {{
    page-break-before: always;
    width: 210mm;
    min-height: 297mm;
    background: linear-gradient(135deg, #0f172a, #1e293b);
    display: flex;
    flex-direction: column;
    align-items: center;
    justify-content: center;
    text-align: center;
    padding: 60px 40px;
  }}
  .backcover h2 {{
    font-size: 28px;
    font-weight: 800;
    color: #f8fafc;
    margin-bottom: 16px;
  }}
  .backcover p {{
    color: #64748b;
    font-size: 13px;
    max-width: 400px;
    line-height: 1.8;
  }}
  .backcover .logo-text {{
    font-size: 48px;
    font-weight: 900;
    background: linear-gradient(135deg, #dc2626, #ea580c);
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

<!-- =====================================
     PORTADA
     ===================================== -->
<div class="cover">
  <div class="cover-badge">Documentación Interna</div>
  {logo_img}
  <h1>Manual de <span>Administrador</span></h1>
  <div class="cover-subtitle">Space Cheer &mdash; Sistema de Producción</div>
  <div class="cover-divider"></div>
  <div style="position:relative;z-index:1;color:#94a3b8;font-size:13px;line-height:2">
    <div>Versión 2.0 &nbsp;&middot;&nbsp; Junio 2026</div>
    <div style="margin-top:24px;color:#475569;font-size:11px">
      Este documento cubre la gestión de pedidos, producción, reportes de error,<br/>
      configuración del sistema, eventos, hospitalidad, productos, equipos y perfil.
    </div>
  </div>
</div>

<!-- =====================================
     ÍNDICE
     ===================================== -->
<div class="toc">
  <h2>Índice de Contenidos</h2>

  <div class="toc-item part">
    <span>Parte 1 &mdash; Gestión de Pedidos</span>
    <span class="toc-num">Pág. 3</span>
  </div>
  <div class="toc-item toc-sub"><span>Lista de pedidos</span><span class="toc-dots"></span><span>3</span></div>
  <div class="toc-item toc-sub"><span>Pedido #17 &mdash; DRAFT</span><span class="toc-dots"></span><span>3</span></div>
  <div class="toc-item toc-sub"><span>Pedido #18 &mdash; PENDING</span><span class="toc-dots"></span><span>3</span></div>
  <div class="toc-item toc-sub"><span>Pedido #19 &mdash; DESIGN_APPROVED</span><span class="toc-dots"></span><span>3</span></div>
  <div class="toc-item toc-sub"><span>Pedido #20 &mdash; IN_PRODUCTION</span><span class="toc-dots"></span><span>3</span></div>
  <div class="toc-item toc-sub"><span>Pedido #21 &mdash; DELIVERED</span><span class="toc-dots"></span><span>3</span></div>

  <div class="toc-item part">
    <span>Parte 2 &mdash; Módulo de Producción</span>
    <span class="toc-num">Pág. 4</span>
  </div>
  <div class="toc-item toc-sub"><span>Panel de producción</span><span class="toc-dots"></span><span>4</span></div>
  <div class="toc-item toc-sub"><span>Detalle del Job #2</span><span class="toc-dots"></span><span>4</span></div>
  <div class="toc-item toc-sub"><span>Reglamento de operarios</span><span class="toc-dots"></span><span>4</span></div>

  <div class="toc-item part">
    <span>Parte 3 &mdash; Reportes de Error</span>
    <span class="toc-num">Pág. 5</span>
  </div>
  <div class="toc-item toc-sub"><span>Lista de reportes</span><span class="toc-dots"></span><span>5</span></div>
  <div class="toc-item toc-sub"><span>Detalle del reporte #1</span><span class="toc-dots"></span><span>5</span></div>

  <div class="toc-item part">
    <span>Parte 4 &mdash; Configuración del Sistema</span>
    <span class="toc-num">Pág. 6</span>
  </div>
  <div class="toc-item toc-sub"><span>Catálogo de Etapas</span><span class="toc-dots"></span><span>6</span></div>
  <div class="toc-item toc-sub"><span>Roles de Producción</span><span class="toc-dots"></span><span>6</span></div>
  <div class="toc-item toc-sub"><span>Responsabilidades</span><span class="toc-dots"></span><span>6</span></div>
  <div class="toc-item toc-sub"><span>Gestión de Operarios</span><span class="toc-dots"></span><span>6</span></div>
  <div class="toc-item toc-sub"><span>Plantillas</span><span class="toc-dots"></span><span>6</span></div>
  <div class="toc-item toc-sub"><span>Etapas por Producto</span><span class="toc-dots"></span><span>6</span></div>

  <div class="toc-item part">
    <span>Parte 5 &mdash; Eventos y Competencias</span>
    <span class="toc-num">Pág. 7</span>
  </div>
  <div class="toc-item toc-sub"><span>Lista de eventos</span><span class="toc-dots"></span><span>7</span></div>
  <div class="toc-item toc-sub"><span>Detalle Grand Prix Espacial</span><span class="toc-dots"></span><span>7</span></div>
  <div class="toc-item toc-sub"><span>Inscripciones, Staff, Puntajes, Resultados</span><span class="toc-dots"></span><span>7</span></div>

  <div class="toc-item part">
    <span>Parte 6 &mdash; Hospitalidad</span>
    <span class="toc-num">Pág. 8</span>
  </div>
  <div class="toc-item toc-sub"><span>Panel de hospitalidad</span><span class="toc-dots"></span><span>8</span></div>
  <div class="toc-item toc-sub"><span>Hoteles y reservaciones</span><span class="toc-dots"></span><span>8</span></div>

  <div class="toc-item part">
    <span>Parte 7 &mdash; Productos y Equipos</span>
    <span class="toc-num">Pág. 9</span>
  </div>
  <div class="toc-item toc-sub"><span>Catálogo de productos</span><span class="toc-dots"></span><span>9</span></div>
  <div class="toc-item toc-sub"><span>Gestión de equipos y atletas</span><span class="toc-dots"></span><span>9</span></div>

  <div class="toc-item part">
    <span>Parte 8 &mdash; Perfil de Administrador</span>
    <span class="toc-num">Pág. 10</span>
  </div>
  <div class="toc-item toc-sub"><span>Editar perfil</span><span class="toc-dots"></span><span>10</span></div>
  <div class="toc-item toc-sub"><span>Configuración de cuenta</span><span class="toc-dots"></span><span>10</span></div>
</div>

<!-- =====================================
     PARTE 1 — GESTIÓN DE PEDIDOS
     ===================================== -->
<section>
  <h2 class="section-title">Parte 1 &mdash; Gestión de Pedidos</h2>
  <p style="color:#94a3b8;margin-bottom:24px">
    La sección de pedidos permite al administrador gestionar el ciclo de vida completo de cada orden,
    desde su creación como borrador hasta la entrega final. El acceso se realiza desde
    <code style="color:#7dd3fc;background:#1e293b;padding:2px 6px;border-radius:4px">/orders/admin/orders/</code>.
  </p>
  {flow_diagram}
  {approval_steps}
  {"".join(render_page_section(k, d) for k, d in orders_pages)}
</section>

<!-- =====================================
     PARTE 2 — MÓDULO DE PRODUCCIÓN
     ===================================== -->
<section>
  <h2 class="section-title">Parte 2 &mdash; Módulo de Producción</h2>
  {production_intro}
  {"".join(render_page_section(k, d) for k, d in prod_pages)}
</section>

<!-- =====================================
     PARTE 3 — REPORTES DE ERROR
     ===================================== -->
<section>
  <h2 class="section-title">Parte 3 &mdash; Reportes de Error</h2>
  {errors_intro}
  {"".join(render_page_section(k, d) for k, d in error_pages)}
</section>

<!-- =====================================
     PARTE 4 — CONFIGURACIÓN DEL SISTEMA
     ===================================== -->
<section>
  <h2 class="section-title">Parte 4 &mdash; Configuración del Sistema</h2>
  {config_intro}
  {"".join(render_page_section(k, d) for k, d in config_pages)}
</section>

<!-- =====================================
     PARTE 5 — EVENTOS Y COMPETENCIAS
     ===================================== -->
<section>
  <h2 class="section-title">Parte 5 &mdash; Eventos y Competencias</h2>
  {events_intro}
  {"".join(render_page_section(k, d) for k, d in events_pages)}
</section>

<!-- =====================================
     PARTE 6 — HOSPITALIDAD
     ===================================== -->
<section>
  <h2 class="section-title">Parte 6 &mdash; Hospitalidad</h2>
  {hospitality_intro}
  {"".join(render_page_section(k, d) for k, d in hospitality_pages)}
</section>

<!-- =====================================
     PARTE 7 — PRODUCTOS Y EQUIPOS
     ===================================== -->
<section>
  <h2 class="section-title">Parte 7 &mdash; Productos y Equipos</h2>
  {products_teams_intro}
  {"".join(render_page_section(k, d) for k, d in products_pages)}
  {"".join(render_page_section(k, d) for k, d in teams_pages)}
</section>

<!-- =====================================
     PARTE 8 — PERFIL DE ADMINISTRADOR
     ===================================== -->
<section>
  <h2 class="section-title">Parte 8 &mdash; Perfil de Administrador</h2>
  {profile_intro}
  {"".join(render_page_section(k, d) for k, d in profile_pages)}
</section>

<!-- =====================================
     CONTRAPORTADA
     ===================================== -->
<div class="backcover">
  <div class="logo-text">&#9733; SPACE CHEER</div>
  <h2>Manual de Administrador</h2>
  <p>
    Sistema de Producción y Gestión de Pedidos<br/>
    Versión 2.0 &mdash; Junio 2026<br/><br/>
    Este documento es de uso interno.<br/>
    Ante dudas, contactar al equipo de desarrollo.
  </p>
  <div style="margin-top:48px;color:#334155;font-size:11px">
    Generado automáticamente con capturas reales del entorno local<br/>
    http://127.0.0.1:8000
  </div>
</div>

</body>
</html>"""

    return html


CAPTURE_BASE_URL = BASE_URL


def login_capture(page, base_url):
    """Login via allauth y verifica que fue exitoso."""
    print(f"    Navegando a {base_url}/accounts/login/")
    try:
        page.goto(f"{base_url}/accounts/login/", wait_until="domcontentloaded", timeout=20000)
    except Exception as e:
        print(f"    WARN goto login: {e}")

    try:
        page.fill('input[name="login"]', USERNAME)
        page.fill('input[name="password"]', PASSWORD)
        page.click('button[type="submit"]')
        # Esperar a que la URL cambie (redirección tras login exitoso)
        try:
            page.wait_for_url(lambda url: "/accounts/login/" not in url, timeout=10000)
        except Exception:
            pass
        page.wait_for_timeout(2000)
    except Exception as e:
        print(f"    WARN al hacer login: {e}")

    result_url = page.url
    print(f"    URL tras login: {result_url}")
    return result_url


def capture_page_at(page, base_url, url_path, filename):
    """Captura una página del servidor en base_url y devuelve (ok, path_or_error)."""
    full_url = f"{base_url}{url_path}"
    try:
        response = page.goto(full_url, wait_until="load", timeout=30000)
        time.sleep(0.9)
        status = response.status if response else 0

        if status in (404, 403, 500):
            return False, f"HTTP {status}"

        # Verificar que no redirigió al login
        if "/accounts/login/" in page.url or "/login/" in page.url:
            return False, "Redirigido al login — sesion perdida"

        screenshot_path = SCREENSHOTS_DIR / f"{filename}.png"
        page.screenshot(path=str(screenshot_path), full_page=True)
        return True, str(screenshot_path)
    except Exception as e:
        return False, str(e)[:150]


def main():
    print("=" * 60)
    print("GENERADOR DE MANUAL ADMIN — SPACE CHEER v2.0")
    print("=" * 60)
    SCREENSHOTS_DIR.mkdir(parents=True, exist_ok=True)

    # ── CLASIFICAR PÁGINAS ──────────────────────────────────────────────────
    section_map = {}
    for url_path, filename, title, desc in PAGES:
        if url_path.startswith("/orders"):
            section = "orders"
        elif "errores" in url_path:
            section = "errors"
        elif url_path.startswith("/production/admin") or "/job/" in url_path or url_path == "/production/reglamento/":
            section = "production"
        elif url_path.startswith("/production/config"):
            section = "config"
        elif url_path.startswith("/events"):
            section = "events"
        elif url_path.startswith("/hospitality"):
            section = "hospitality"
        elif url_path.startswith("/products"):
            section = "products"
        elif url_path.startswith("/teams"):
            section = "teams"
        elif url_path.startswith("/accounts/profile"):
            section = "profile"
        else:
            section = "other"

        section_map[filename] = {
            "url": url_path,
            "title": title,
            "desc": desc,
            "section": section,
            "ok": False,
            "path": "",
        }

    ok_count = 0
    error_count = 0
    errors_detail = []

    print("\n[1] Iniciando Playwright...")
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        context = browser.new_context(
            viewport={"width": 1440, "height": 900},
            ignore_https_errors=True,
            extra_http_headers={"X-Forwarded-Proto": "https"},
        )
        page = context.new_page()

        # ── LOGIN ──────────────────────────────────────────────────────────
        print("\n[2] Realizando login como admin_test...")
        final_url = login_capture(page, CAPTURE_BASE_URL)

        if "/accounts/login/" in final_url:
            print("    ERROR: Login fallido. Verifica que el servidor corra en :8000 y que admin_test existe con password Test1234!")
            browser.close()
            return

        print("    Login exitoso.")

        # ── CAPTURAS ───────────────────────────────────────────────────────
        print(f"\n[3] Capturando {len(PAGES)} paginas...")
        for url_path, filename, title, desc in PAGES:
            print(f"    -> {title} ({url_path})")
            ok, result = capture_page_at(page, CAPTURE_BASE_URL, url_path, filename)
            section_map[filename]["ok"] = ok
            section_map[filename]["path"] = result

            if ok:
                ok_count += 1
                print(f"       OK: {result}")
            else:
                error_count += 1
                errors_detail.append((title, url_path, result))
                print(f"       ERROR: {result}")

        browser.close()

    # ── GENERAR HTML ────────────────────────────────────────────────────────
    print("\n[4] Generando HTML del manual...")
    html_content = build_html(section_map)
    html_path = SCREENSHOTS_DIR / "manual_admin.html"
    with open(str(html_path), "w", encoding="utf-8") as f:
        f.write(html_content)
    print(f"    HTML guardado: {html_path}")

    # ── CONVERTIR A PDF ─────────────────────────────────────────────────────
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

    # ── REPORTE FINAL ───────────────────────────────────────────────────────
    pdf_size = OUTPUT_PDF.stat().st_size if OUTPUT_PDF.exists() else 0
    pdf_size_mb = pdf_size / (1024 * 1024)

    print("\n" + "=" * 60)
    print("REPORTE FINAL")
    print("=" * 60)
    print(f"  Paginas totales       : {len(PAGES)}")
    print(f"  Paginas capturadas OK : {ok_count}")
    print(f"  Paginas con error     : {error_count}")
    if errors_detail:
        print("\n  Detalle de errores:")
        for t, u, e in errors_detail:
            print(f"    - {t} ({u}): {e}")
    print(f"\n  PDF generado en       : {OUTPUT_PDF}")
    print(f"  Tamano del PDF        : {pdf_size_mb:.2f} MB")
    print("=" * 60)


if __name__ == "__main__":
    main()
