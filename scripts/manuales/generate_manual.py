#!/usr/bin/env python3
"""
Genera el Manual de Usuario del Sistema de Producción Space Cheer.
Usa Playwright para capturar pantallas reales de spacecheer.com y genera un PDF profesional.
"""
import asyncio
import base64
import os
import re
import sys
from datetime import datetime
from pathlib import Path

from playwright.async_api import async_playwright

BASE_URL = "https://spacecheer.com"
USERNAME = os.environ.get("SPACECHEER_USERNAME")
PASSWORD = os.environ.get("SPACECHEER_PASSWORD")
OUTPUT_PDF = Path(__file__).parent.parent.parent / "manual_usuario_spacecheer.pdf"

if not USERNAME or not PASSWORD:
    sys.exit(
        "ERROR: Define las variables de entorno SPACECHEER_USERNAME y SPACECHEER_PASSWORD.\n"
        "  export SPACECHEER_USERNAME=tu_usuario\n"
        "  export SPACECHEER_PASSWORD=tu_password\n"
    )

shots: dict[str, str] = {}  # key → base64 PNG


# ─────────────────────────────────────── helpers ──────────────────────────────

async def goto(page, path: str) -> None:
    await page.goto(f"{BASE_URL}{path}", wait_until="networkidle", timeout=30_000)
    await page.wait_for_timeout(900)


async def snap(page, key: str, *, full_page: bool = True) -> None:
    data = await page.screenshot(full_page=full_page)
    shots[key] = base64.b64encode(data).decode()
    print(f"  📸 {key}")


def img(key: str, caption: str = "", width: str = "100%") -> str:
    if key not in shots:
        return f'<div class="placeholder">[Captura no disponible: {key}]</div>'
    tag = (
        f'<img src="data:image/png;base64,{shots[key]}" '
        f'alt="{caption}" style="width:{width};border-radius:8px;'
        f'box-shadow:0 2px 14px rgba(0,0,0,.3)">'
    )
    cap = f"<figcaption>{caption}</figcaption>" if caption else ""
    return f'<figure class="sc">{tag}{cap}</figure>'


# ─────────────────────────────────── capture pages ────────────────────────────

async def capture_all(page) -> dict:
    meta: dict = {}

    # LOGIN (antes de autenticar)
    await goto(page, "/accounts/login/")
    await snap(page, "login", full_page=False)

    await page.fill('input[name="login"]', USERNAME)
    await page.fill('input[name="password"]', PASSWORD)
    await page.click('button[type="submit"]')
    await page.wait_for_load_state("networkidle")
    await page.wait_for_timeout(1000)

    # OPERARIO: Dashboard
    await goto(page, "/production/")
    await snap(page, "op_dashboard")

    # OPERARIO: Mi Área
    await goto(page, "/production/mi-area/")
    await snap(page, "op_mi_area")

    # OPERARIO: Reglamento
    await goto(page, "/production/reglamento/")
    await snap(page, "op_reglamento")

    # OPERARIO: Nuevo reporte de error
    await goto(page, "/production/errores/nuevo/")
    await snap(page, "op_error_form")

    # OPERARIO: Lista de reportes
    await goto(page, "/production/errores/")
    await snap(page, "op_error_list")

    # ADMIN: Lista de pedidos
    await goto(page, "/orders/admin/orders/")
    await snap(page, "adm_orders_list")
    link = await page.query_selector("table tbody tr a, .table a[href*='/admin/orders/']")
    if link:
        href = await link.get_attribute("href")
        m = re.search(r"/orders/admin/orders/(\d+)/", href or "")
        if m:
            meta["order_id"] = m.group(1)

    # ADMIN: Detalle de pedido
    if "order_id" in meta:
        await goto(page, f"/orders/admin/orders/{meta['order_id']}/")
        await snap(page, "adm_order_detail_top", full_page=False)
        await snap(page, "adm_order_detail_full", full_page=True)

    # ADMIN: Vista general trabajos producción
    await goto(page, "/production/admin/")
    await snap(page, "adm_prod_overview")
    link = await page.query_selector("a[href*='/production/admin/job/']")
    if link:
        href = await link.get_attribute("href")
        m = re.search(r"/production/admin/job/(\d+)/", href or "")
        if m:
            meta["job_id"] = m.group(1)

    # ADMIN: Detalle de trabajo
    if "job_id" in meta:
        await goto(page, f"/production/admin/job/{meta['job_id']}/")
        await snap(page, "adm_job_detail")

    # CONFIG: Catálogo de etapas
    await goto(page, "/production/config/stages/")
    await snap(page, "cfg_stages")

    # CONFIG: Roles de producción
    await goto(page, "/production/config/roles/")
    await snap(page, "cfg_roles")

    # CONFIG: Responsabilidades
    await goto(page, "/production/config/responsabilidades/")
    await snap(page, "cfg_responsabilidades")

    # CONFIG: Plantillas
    await goto(page, "/production/config/plantillas/")
    await snap(page, "cfg_plantillas")

    # CONFIG: Etapas por producto
    await goto(page, "/production/config/product-stages/")
    await snap(page, "cfg_product_stages")

    # CONFIG: Operarios
    await goto(page, "/production/config/operarios/")
    await snap(page, "cfg_operarios")

    return meta


# ─────────────────────────────────────── HTML ─────────────────────────────────

def build_html(meta: dict) -> str:
    fecha = datetime.now().strftime("%d de %B de %Y").lstrip("0")

    def section(num, sid, title, content):
        return f"""
<div class="section" id="{sid}">
  <div class="section-header">
    <div class="snum">{num}</div>
    <h2>{title}</h2>
  </div>
  {content}
</div>"""

    def steps(*items):
        lis = "".join(f"<li>{i}</li>" for i in items)
        return f'<ol class="steps">{lis}</ol>'

    def info(text):
        return f'<div class="info-box"><p>💡 {text}</p></div>'

    def warn(text):
        return f'<div class="warn-box"><p>⚠️ {text}</p></div>'

    def part(num, title, subtitle, page_break=True):
        pb = 'style="page-break-before:always"' if page_break else ""
        return f"""
<div class="part-header" {pb}>
  <div class="part-num">Parte {num}</div>
  <h1>{title}</h1>
  <p>{subtitle}</p>
</div>"""

    def two_col(left_title, left_body, right_title, right_body):
        return f"""
<div class="two-col">
  <div class="card"><h4>{left_title}</h4>{left_body}</div>
  <div class="card"><h4>{right_title}</h4>{right_body}</div>
</div>"""

    css = """
* { box-sizing: border-box; margin: 0; padding: 0; }
@page { size: A4; margin: 18mm 16mm; }
body { font-family: 'Segoe UI', system-ui, sans-serif; color: #1a1a2e;
       font-size: 10.5pt; line-height: 1.65; }

/* COVER */
.cover { page-break-after: always; display: flex; flex-direction: column;
         justify-content: center; align-items: center; min-height: 100vh;
         background: linear-gradient(145deg,#0d0d1a 0%,#1a1140 55%,#0a1628 100%);
         color: white; text-align: center; padding: 48px 32px; }
.cover .rocket { font-size: 80pt; margin-bottom: 24px; line-height: 1; }
.cover h1 { font-size: 32pt; font-weight: 900; letter-spacing: -1.5px;
            background: linear-gradient(90deg,#c084fc,#60a5fa); -webkit-background-clip: text;
            -webkit-text-fill-color: transparent; background-clip: text; margin-bottom: 6px; }
.cover h2 { font-size: 14pt; font-weight: 300; color: #94a3b8; margin-bottom: 40px;
            letter-spacing: .5px; }
.cover .badge { background: rgba(192,132,252,.15); color: #c084fc;
                border: 1px solid rgba(192,132,252,.35); border-radius: 99px;
                padding: 7px 22px; font-size: 10pt; margin-bottom: 14px; }
.cover .meta { color: #475569; font-size: 9.5pt; }

/* TOC */
.toc { page-break-after: always; }
.toc h2 { font-size: 17pt; font-weight: 800; color: #1a1a2e;
           border-bottom: 3px solid #7c3aed; padding-bottom: 10px; margin-bottom: 24px; }
.toc-part { font-weight: 700; color: #7c3aed; font-size: 10.5pt;
             margin-top: 18px; margin-bottom: 6px; text-transform: uppercase; letter-spacing: .5px; }
.toc-item { padding: 3px 0 3px 12px; font-size: 10pt; color: #374151;
             border-left: 2px solid #e5e7eb; margin-bottom: 2px; }
.toc-item span { color: #9ca3af; margin-right: 6px; font-size: 9pt; }

/* PART HEADER */
.part-header { background: linear-gradient(135deg,#7c3aed 0%,#2563eb 100%);
               color: white; padding: 36px 28px; border-radius: 14px;
               margin-bottom: 32px; }
.part-header .part-num { font-size: 9.5pt; opacity: .65; text-transform: uppercase;
                          letter-spacing: 2px; margin-bottom: 6px; }
.part-header h1 { font-size: 22pt; font-weight: 800; margin-bottom: 8px; }
.part-header p { font-size: 10.5pt; opacity: .85; }

/* SECTIONS */
.section { margin-bottom: 36px; page-break-inside: avoid; }
.section-header { display: flex; align-items: center; gap: 10px; margin-bottom: 14px;
                   padding-bottom: 8px; border-bottom: 2px solid #e5e7eb; }
.snum { background: #7c3aed; color: white; width: 30px; height: 30px; border-radius: 50%;
         display: flex; align-items: center; justify-content: center;
         font-size: 10.5pt; font-weight: 700; flex-shrink: 0; }
.section h2 { font-size: 14pt; font-weight: 700; color: #1a1a2e; }
.section h3 { font-size: 11pt; font-weight: 700; color: #374151; margin: 14px 0 6px; }
.section p { margin-bottom: 10px; color: #374151; }

/* SCREENSHOTS */
figure.sc { margin: 14px 0; }
figure.sc img { width: 100%; }
figcaption { font-size: 8.5pt; color: #6b7280; text-align: center;
              margin-top: 5px; font-style: italic; }
.placeholder { background: #f3f4f6; border: 2px dashed #d1d5db; padding: 18px;
                text-align: center; color: #9ca3af; border-radius: 8px; font-size: 9.5pt; }

/* STEPS */
.steps { list-style: none; counter-reset: step; margin: 12px 0; padding: 0; }
.steps li { counter-increment: step; padding: 9px 12px 9px 42px; position: relative;
             background: #f9fafb; border-left: 3px solid #7c3aed; border-radius: 0 6px 6px 0;
             margin-bottom: 6px; font-size: 10pt; }
.steps li::before { content: counter(step); position: absolute; left: 11px; top: 50%;
                      transform: translateY(-50%); background: #7c3aed; color: white;
                      width: 19px; height: 19px; border-radius: 50%; font-size: 8.5pt;
                      font-weight: 700; display: flex; align-items: center; justify-content: center; }
.steps li strong { color: #1a1a2e; }

/* BOXES */
.info-box { background: #eff6ff; border-left: 4px solid #3b82f6; border-radius: 0 8px 8px 0;
             padding: 12px 14px; margin: 12px 0; }
.info-box p { margin: 0; font-size: 10pt; color: #1e40af; }
.warn-box { background: #fefce8; border-left: 4px solid #eab308; border-radius: 0 8px 8px 0;
             padding: 12px 14px; margin: 12px 0; }
.warn-box p { margin: 0; font-size: 10pt; color: #854d0e; }

/* FLOW */
.flow { display: flex; align-items: center; gap: 6px; flex-wrap: wrap; margin: 16px 0; }
.flow-step { background: #1e1e3f; color: #94a3b8; padding: 6px 14px; border-radius: 99px;
              font-size: 9pt; font-weight: 600; }
.flow-step.on { background: linear-gradient(90deg,#7c3aed,#2563eb); color: white; }
.flow-arrow { color: #7c3aed; font-size: 14pt; font-weight: 700; }

/* TWO COL */
.two-col { display: grid; grid-template-columns: 1fr 1fr; gap: 12px; margin: 12px 0; }
.card { background: #f9fafb; border: 1px solid #e5e7eb; border-radius: 8px; padding: 14px; }
.card h4 { font-size: 10.5pt; font-weight: 700; color: #374151; margin-bottom: 7px; }
.card p, .card li { font-size: 9.5pt; color: #6b7280; }
.card ul { padding-left: 14px; }
.card ul li { margin-bottom: 3px; }

/* BACK COVER */
.back { text-align: center; padding: 50px 32px; background: #f8fafc; border-radius: 12px;
         margin-top: 40px; page-break-before: always; }
"""

    return f"""<!DOCTYPE html>
<html lang="es">
<head><meta charset="UTF-8">
<style>{css}</style>
</head>
<body>

<!-- ═══════ PORTADA ═══════ -->
<div class="cover">
  <div class="rocket">🚀</div>
  <h1>Space Cheer</h1>
  <h2>Manual de Usuario — Sistema de Producción</h2>
  <div class="badge">spacecheer.com</div>
  <div class="meta">Versión 1.0 &nbsp;·&nbsp; {fecha}</div>
</div>

<!-- ═══════ ÍNDICE ═══════ -->
<div class="toc">
  <h2>Índice de Contenido</h2>

  <div class="toc-part">Parte 1 — Para Operarios</div>
  <div class="toc-item"><span>1.</span>Acceso al Sistema</div>
  <div class="toc-item"><span>2.</span>Panel Principal (Dashboard)</div>
  <div class="toc-item"><span>3.</span>Mi Área de Trabajo</div>
  <div class="toc-item"><span>4.</span>Completar una Tarea</div>
  <div class="toc-item"><span>5.</span>El Reglamento para Operarios</div>
  <div class="toc-item"><span>6.</span>Reportar un Error de Producción</div>

  <div class="toc-part">Parte 2 — Para Administradores: Gestión de Pedidos</div>
  <div class="toc-item"><span>7.</span>Lista de Pedidos</div>
  <div class="toc-item"><span>8.</span>Detalle de un Pedido</div>
  <div class="toc-item"><span>9.</span>Flujo de Aprobación de Pedidos</div>
  <div class="toc-item"><span>10.</span>Revisar Reportes de Error</div>

  <div class="toc-part">Parte 3 — Para Administradores: Módulo de Producción</div>
  <div class="toc-item"><span>11.</span>Vista General de Trabajos</div>
  <div class="toc-item"><span>12.</span>Detalle de un Trabajo de Producción</div>
  <div class="toc-item"><span>13.</span>Asignar y Reasignar Tareas</div>

  <div class="toc-part">Parte 4 — Configuración del Sistema (Solo Admin)</div>
  <div class="toc-item"><span>14.</span>Catálogo de Etapas de Producción</div>
  <div class="toc-item"><span>15.</span>Roles de Producción</div>
  <div class="toc-item"><span>16.</span>Responsabilidades por Etapa</div>
  <div class="toc-item"><span>17.</span>Plantillas de Producción</div>
  <div class="toc-item"><span>18.</span>Etapas por Producto</div>
  <div class="toc-item"><span>19.</span>Gestión de Operarios</div>
</div>


<!-- ═══════ PARTE 1: OPERARIOS ═══════ -->
{part(1, "Para Operarios", "Cómo acceder al sistema, revisar tareas asignadas, completarlas y reportar errores.", page_break=False)}

{section(1, "s1", "Acceso al Sistema", f"""
<p>Para ingresar al sistema abre un navegador y visita <strong>spacecheer.com</strong>.
Ingresa tus credenciales de operario que te proporcionó el administrador.</p>
{img("login", "Pantalla de inicio de sesión en spacecheer.com")}
{steps(
    "Abre un navegador y ve a <strong>spacecheer.com</strong>.",
    "Escribe tu <strong>usuario o correo electrónico</strong> en el primer campo.",
    "Escribe tu <strong>contraseña</strong> en el segundo campo.",
    "Haz clic en <em>Iniciar sesión</em>.",
)}
{info("Si olvidaste tu contraseña, contacta al administrador para que la restablezca desde el panel de configuración de operarios.")}
""")}

{section(2, "s2", "Panel Principal (Dashboard)", f"""
<p>Al iniciar sesión verás el <strong>panel principal de producción</strong>. Aquí se muestran
tus tareas pendientes, los pedidos activos y un resumen de tu actividad reciente.</p>
{img("op_dashboard", "Panel principal del operario")}
{two_col(
    "📋 Tareas pendientes",
    "<p>Lista de las tareas que tienes asignadas y que aún no has completado. Haz clic en una tarea para ver los detalles del pedido.</p>",
    "✅ Resumen de actividad",
    "<p>Indicadores de tareas completadas hoy y esta semana. Útil para llevar un registro de tu productividad.</p>"
)}
""")}

{section(3, "s3", "Mi Área de Trabajo", f"""
<p>En <strong>Mi Área</strong> puedes ver todas las tareas que te han sido asignadas, organizadas
por pedido y etapa de producción. Accede desde el menú de navegación superior.</p>
{img("op_mi_area", "Vista de Mi Área con todas las tareas asignadas")}
<p>Cada tarea muestra:</p>
{steps(
    "El <strong>pedido</strong> al que pertenece (número y equipo).",
    "La <strong>etapa de producción</strong> (ej. Sublimación, Corte, Costura).",
    "El <strong>artículo</strong> específico dentro del pedido (producto y talla).",
    "El <strong>estado</strong>: Pendiente o Completada.",
)}
""")}

{section(4, "s4", "Completar una Tarea", f"""
<p>Cuando termines tu etapa de trabajo debes <strong>marcar la tarea como completada</strong>
en el sistema. Esto notifica al administrador y al siguiente operario en la cadena.</p>
{steps(
    "En el Dashboard o en <em>Mi Área</em>, localiza la tarea que terminaste.",
    "Haz clic en el botón <strong>Completar</strong> (ícono de palomita ✓).",
    "Confirma si el sistema te lo solicita.",
    "El sistema registrará automáticamente la hora de finalización.",
)}
{warn("Solo marca una tarea como completada cuando hayas <strong>terminado físicamente</strong> esa etapa del pedido. Esta acción es registrada con tu nombre de usuario y la hora exacta.")}
""")}

{section(5, "s5", "El Reglamento para Operarios", f"""
<p>El reglamento establece las normas de conducta, procedimientos y sanciones aplicables
al personal operativo. Es <strong>obligatorio</strong> conocerlo y cumplirlo.</p>
{img("op_reglamento", "Pantalla del Reglamento para Operarios")}
{info("Accede al reglamento desde el menú de navegación. El administrador puede actualizarlo en cualquier momento; cualquier cambio quedará reflejado inmediatamente en el sistema.")}
""")}

{section(6, "s6", "Reportar un Error de Producción", f"""
<p>Si detectas un error en el proceso (talla incorrecta, corte equivocado, defecto en costura,
material incorrecto, etc.) debes <strong>reportarlo de inmediato</strong> a través del sistema.</p>
{img("op_error_form", "Formulario para reportar un error de producción")}
{steps(
    "Ve al menú y selecciona <strong>Reportar Error</strong>.",
    "Selecciona el pedido o trabajo afectado (si aplica).",
    "Elige el <strong>tipo de error</strong> de la lista (puedes seleccionar varios).",
    "Describe el error con detalle en el campo de texto.",
    "Identifica la causa probable (falta de atención, información incorrecta, etc.).",
    "Señala el impacto: retraso, reposición, costo adicional, etc.",
    "Describe las acciones correctivas inmediatas que tomaste.",
    "Haz clic en <strong>Enviar Reporte</strong>.",
)}
{info("El administrador revisará el reporte y determinará el resultado: Revisado, Excepción otorgada, o Reposición requerida. Podrás ver el resultado en la lista de reportes.")}
""")}


<!-- ═══════ PARTE 2: ADMIN PEDIDOS ═══════ -->
{part(2, "Gestión de Pedidos (Admin)", "Control completo del ciclo de vida de cada pedido: desde la recepción hasta la entrega al cliente.")}

{section(7, "s7", "Lista de Pedidos", f"""
<p>El panel de administración de pedidos muestra todos los pedidos del sistema con su estado
actual, equipo solicitante, fecha y acceso rápido al detalle.</p>
{img("adm_orders_list", "Lista de pedidos en el panel de administración")}
{two_col(
    "🔍 Filtros disponibles",
    "<ul><li>Por estado (PENDING, IN_PRODUCTION, etc.)</li><li>Por equipo o temporada</li><li>Búsqueda por texto</li></ul>",
    "📊 Columnas de la tabla",
    "<ul><li>Número de pedido</li><li>Equipo / Cliente</li><li>Estado actual</li><li>Fecha de creación</li><li>Acciones rápidas</li></ul>"
)}
""")}

{section(8, "s8", "Detalle de un Pedido", f"""
<p>Al hacer clic en un pedido verás toda su información: productos solicitados, atletas
incluidos, medidas tomadas, diseños adjuntos y los botones de transición de estado.</p>
{img("adm_order_detail_top", "Vista superior del detalle de un pedido (viewport)")}
{img("adm_order_detail_full", "Vista completa del detalle de un pedido con todos los ítems y acciones")}
""")}

{section(9, "s9", "Flujo de Aprobación de Pedidos", f"""
<p>Cada pedido sigue un flujo estricto de estados. Las transiciones se realizan desde el
detalle del pedido mediante botones de acción prominentes.</p>
<div class="flow">
  <div class="flow-step">DRAFT</div>
  <div class="flow-arrow">→</div>
  <div class="flow-step on">PENDING</div>
  <div class="flow-arrow">→</div>
  <div class="flow-step on">DESIGN APROBADO</div>
  <div class="flow-arrow">→</div>
  <div class="flow-step on">EN PRODUCCIÓN</div>
  <div class="flow-arrow">→</div>
  <div class="flow-step on">ENTREGADO</div>
</div>
<h3>Pasos para aprobar y enviar a producción</h3>
{steps(
    "<strong>Revisar el pedido</strong>: verifica productos, medidas y diseño adjunto.",
    "Si el diseño está aprobado, haz clic en el botón <strong>Aprobar Diseño</strong> (amarillo). El pedido pasa a DESIGN_APPROVED y las medidas quedan bloqueadas.",
    "Cuando esté listo para iniciar la manufactura, haz clic en <strong>Enviar a Producción</strong> (verde). Se abrirá una ventana de confirmación.",
    "Confirma la acción. El sistema crea automáticamente un <em>trabajo de producción</em> con todas las tareas por etapa para cada artículo del pedido.",
    "Al entregar físicamente el pedido al cliente, haz clic en <strong>Marcar como Entregado</strong> (azul).",
)}
{warn("Al hacer clic en <strong>Enviar a Producción</strong> las medidas se bloquean permanentemente. Asegúrate de que todas las medidas de los atletas estén completas y correctas antes de confirmar.")}
<p>Para cancelar un pedido en cualquier etapa, usa el botón <strong>Cancelar Pedido</strong> (rojo), que requiere confirmación adicional.</p>
""")}

{section(10, "s10", "Revisar Reportes de Error", f"""
<p>Cuando los operarios reportan errores durante la producción, como administrador debes
revisarlos y tomar una decisión.</p>
{img("op_error_list", "Lista de reportes de error pendientes de revisión")}
{steps(
    "Ve a <strong>Producción → Reportes de Error</strong>.",
    "Haz clic en el reporte que deseas revisar.",
    "Lee la descripción completa: tipo de error, causa, impacto y acciones tomadas.",
    "Selecciona el <strong>resultado de la revisión</strong>: Revisado, Excepción otorgada, o Reposición requerida.",
    "Agrega <strong>notas de revisión</strong> con instrucciones para el operario.",
    "Guarda la revisión. El estado del reporte se actualizará.",
)}
""")}


<!-- ═══════ PARTE 3: ADMIN PRODUCCIÓN ═══════ -->
{part(3, "Módulo de Producción (Admin)", "Supervisión de trabajos activos, seguimiento de tareas por etapa y asignación de operarios.")}

{section(11, "s11", "Vista General de Trabajos", f"""
<p>El <strong>Panel Admin de Producción</strong> muestra todos los trabajos activos. Cada trabajo
corresponde a un pedido que está en estado IN_PRODUCTION.</p>
{img("adm_prod_overview", "Vista general de trabajos de producción activos")}
{info("Los trabajos marcados como <strong>URGENTE</strong> aparecen resaltados. Puedes activar o desactivar la urgencia desde el detalle de cada trabajo según las necesidades de entrega.")}
""")}

{section(12, "s12", "Detalle de un Trabajo de Producción", f"""
<p>Al abrir un trabajo verás todas sus tareas agrupadas por artículo del pedido. Cada tarea
representa una etapa de producción para ese artículo específico.</p>
{img("adm_job_detail", "Detalle de trabajo con tareas por etapa y operario asignado")}
{two_col(
    "📋 Información del trabajo",
    "<ul><li>Pedido vinculado</li><li>Estado de urgencia (toggle)</li><li>Fecha de creación</li><li>Progreso general (%)</li></ul>",
    "✅ Por cada tarea verás",
    "<ul><li>Artículo (producto + talla/atleta)</li><li>Etapa de producción</li><li>Operario asignado</li><li>Estado: Pendiente / Completada</li></ul>"
)}
""")}

{section(13, "s13", "Asignar y Reasignar Tareas", f"""
<p>Puedes asignar operarios a tareas individuales o hacer una <strong>reasignación masiva</strong>
de todas las tareas pendientes de un trabajo.</p>
<h3>Asignación individual</h3>
{steps(
    "Abre el detalle del trabajo de producción.",
    "Localiza la tarea a asignar en la tabla.",
    "Usa el <strong>selector de Operario</strong> en la columna correspondiente.",
    "Selecciona el operario y el sistema guarda automáticamente.",
)}
<h3>Reasignación masiva</h3>
{steps(
    "En el detalle del trabajo, localiza la sección <strong>Reasignación Masiva</strong>.",
    "Selecciona el <strong>operario destino</strong> del desplegable.",
    "Marca las tareas individuales que deseas reasignar, o usa <em>Seleccionar todas</em>.",
    "Haz clic en <strong>Reasignar</strong>.",
)}
{info("El operario asignado recibe una notificación automática por el sistema al ser asignado a nuevas tareas.")}
""")}


<!-- ═══════ PARTE 4: CONFIGURACIÓN ═══════ -->
{part(4, "Configuración del Sistema", "Área exclusiva del administrador. Configura el módulo de producción: etapas, roles, plantillas y personal.")}

{section(14, "s14", "Catálogo de Etapas de Producción", f"""
<p>Las <strong>etapas</strong> son los pasos del proceso productivo (Corte, Sublimación, Costura,
Empaque, etc.). Definen qué tareas se generan automáticamente cuando un pedido entra a producción.</p>
{img("cfg_stages", "Catálogo de etapas con contadores de uso")}
<h3>Crear una nueva etapa</h3>
{steps(
    "Llena el formulario superior: <strong>Nombre</strong> (requerido), <strong>Slug</strong> (identificador único, requerido), ícono (emoji), orden numérico y descripción.",
    "Haz clic en <strong>Crear</strong>.",
)}
<h3>Editar una etapa existente</h3>
{steps(
    "Haz clic en el ícono de lápiz ✏️ en la fila de la etapa.",
    "Se desplegará un formulario de edición debajo de la fila.",
    "Modifica los campos necesarios y haz clic en <strong>Guardar</strong>.",
)}
<h3>Eliminar una etapa</h3>
{steps(
    "Haz clic en el ícono de papelera 🗑️ en la fila de la etapa.",
    "Confirma la eliminación en la ventana emergente.",
)}
{warn("No es posible eliminar una etapa si está asignada a productos, plantillas o tareas activas. Los contadores de uso (Prods., Plantillas, Tasks) en la tabla te indican si la etapa está en uso.")}
""")}

{section(15, "s15", "Roles de Producción", f"""
<p>Los <strong>roles de producción</strong> agrupan operarios por especialidad (ej. "Sublimador",
"Cortador", "Costurera"). Se usan para asignar responsabilidades por etapa y controlar
qué operarios ven qué tareas.</p>
{img("cfg_roles", "Gestión de roles de producción")}
{steps(
    "Escribe el <strong>nombre del rol</strong> en el formulario (ej. «Sublimador»).",
    "Asocia las etapas de producción que corresponden a ese rol.",
    "Haz clic en <strong>Crear Rol</strong>.",
    "Para agregar operarios al rol, haz clic en el botón <strong>Ver Operarios</strong> del rol.",
    "En la pantalla de asignación, usa los botones <strong>Asignar</strong> / <strong>Quitar</strong> por cada operario.",
)}
""")}

{section(16, "s16", "Responsabilidades por Etapa", f"""
<p>Define qué <strong>rol es responsable principal</strong> de cada etapa y qué roles actúan como
<strong>auxiliares</strong>. Esta configuración determina quién puede ver y completar las tareas
de cada etapa en el módulo operario.</p>
{img("cfg_responsabilidades", "Configuración de responsabilidades por etapa")}
{steps(
    "Selecciona la <strong>etapa</strong> a configurar en el desplegable.",
    "Elige el <strong>rol responsable principal</strong> — el que ejecuta esa etapa.",
    "Opcionalmente selecciona <strong>roles auxiliares</strong> que dan soporte.",
    "Haz clic en <strong>Guardar Responsabilidad</strong>.",
)}
{info("Si una etapa ya tiene responsabilidad asignada, el formulario la actualizará en lugar de crear una duplicada.")}
""")}

{section(17, "s17", "Plantillas de Producción", f"""
<p>Las <strong>plantillas</strong> son grupos reutilizables de etapas. Crea una plantilla
«Uniforme Completo» con todas las etapas típicas y aplícala a múltiples productos con un clic,
sin tener que configurar cada uno manualmente.</p>
{img("cfg_plantillas", "Gestión de plantillas de producción")}
<h3>Crear una plantilla</h3>
{steps(
    "Escribe el <strong>nombre</strong> y una descripción opcional.",
    "Haz clic en <strong>Crear Plantilla</strong>.",
    "En la plantilla recién creada, usa el selector <em>Agregar etapa</em> para incluir las etapas que la conforman.",
    "Repite hasta agregar todas las etapas necesarias.",
)}
<h3>Eliminar una plantilla</h3>
{steps(
    "Haz clic en el botón <strong>Eliminar</strong> de la plantilla.",
    "Confirma la acción. Las etapas de la plantilla no se eliminan — solo el grupo.",
)}
""")}

{section(18, "s18", "Etapas por Producto", f"""
<p>Define qué etapas de producción aplican a <strong>cada producto específico</strong>.
Una mochila no pasa por las mismas etapas que un uniforme. Esta matriz global te permite
configurar todo desde un solo lugar.</p>
{img("cfg_product_stages", "Matriz global de etapas por producto")}
<h3>Aplicar una plantilla a un producto</h3>
{steps(
    "Localiza el producto en la lista.",
    "Selecciona una <strong>plantilla</strong> del desplegable correspondiente.",
    "Elige el modo: <strong>Reemplazar</strong> (borra etapas actuales y aplica la plantilla) o <strong>Fusionar</strong> (agrega las etapas sin borrar las existentes).",
    "Haz clic en <strong>Aplicar Plantilla</strong>.",
)}
<h3>Agregar o quitar etapas manualmente</h3>
{steps(
    "En la tarjeta del producto, usa el desplegable <em>+ Agregar etapa</em>.",
    "Selecciona la etapa y el orden de ejecución deseado.",
    "Para quitar una etapa, haz clic en el botón × junto a ella.",
)}
{info("Las etapas configuradas aquí son las que se convierten en tareas cuando ese producto entra a producción. Si un producto no tiene etapas configuradas, no generará tareas de producción.")}
""")}

{section(19, "s19", "Gestión de Operarios", f"""
<p>Administra el personal de producción: crea cuentas nuevas, asigna roles, consulta
historial de actividad y restablece contraseñas desde un panel unificado.</p>
{img("cfg_operarios", "Panel de gestión de operarios activos e inactivos")}
<h3>Crear un operario nuevo</h3>
{steps(
    "Llena el formulario: usuario, nombre, apellido, correo electrónico y contraseña.",
    "Haz clic en <strong>Crear Operario</strong>.",
    "El nuevo operario ya podrá iniciar sesión con esas credenciales.",
)}
<h3>Asignar un usuario existente como operario</h3>
{steps(
    "Usa el buscador de usuarios existentes en la sección inferior.",
    "Escribe nombre o correo del usuario.",
    "Haz clic en <strong>Asignar como operario</strong>.",
)}
<h3>Restablecer contraseña de un operario</h3>
{steps(
    "Haz clic en el nombre del operario para abrir su perfil.",
    "Ve a la sección <em>Seguridad</em>.",
    "Escribe la nueva contraseña y haz clic en <strong>Actualizar Contraseña</strong>.",
)}
{info("Desde el perfil del operario también puedes ver su historial de tareas completadas, cuántas tareas tiene pendientes y asignarle o quitarle roles de producción.")}
""")}


<!-- CONTRAPORTADA -->
<div class="back">
  <div style="font-size:52pt;margin-bottom:16px">🚀</div>
  <h2 style="font-size:18pt;color:#1a1a2e;margin-bottom:6px">Space Cheer</h2>
  <p style="color:#6b7280;font-size:11pt">Sistema de Gestión de Producción</p>
  <p style="color:#9ca3af;font-size:9pt;margin-top:20px">Manual de Usuario · Versión 1.0 · {fecha}</p>
  <p style="color:#c4c4d4;font-size:9pt;margin-top:6px">spacecheer.com</p>
</div>

</body>
</html>"""


# ─────────────────────────────────────── main ─────────────────────────────────

async def main():
    print("🚀  Generando Manual de Usuario — Space Cheer\n")

    async with async_playwright() as p:
        # ── Captura de pantallas ──────────────────────────────────
        browser = await p.chromium.launch(headless=True)
        ctx = await browser.new_context(
            viewport={"width": 1440, "height": 900},
            locale="es-MX",
        )
        page = await ctx.new_page()

        print("📸  Capturando pantallas del sitio...\n")
        meta = await capture_all(page)
        await browser.close()
        print(f"\n   {len(shots)} capturas obtenidas.\n")

        # ── Generación del PDF ────────────────────────────────────
        print("📄  Generando PDF...")
        html = build_html(meta)

        pdf_browser = await p.chromium.launch(headless=True)
        pdf_page = await pdf_browser.new_page()
        await pdf_page.set_content(html, wait_until="networkidle")
        await pdf_page.wait_for_timeout(1500)

        await pdf_page.pdf(
            path=str(OUTPUT_PDF),
            format="A4",
            print_background=True,
            margin={"top": "14mm", "bottom": "14mm", "left": "14mm", "right": "14mm"},
        )
        await pdf_browser.close()

    print(f"\n✅  PDF generado: {OUTPUT_PDF}")


if __name__ == "__main__":
    asyncio.run(main())
