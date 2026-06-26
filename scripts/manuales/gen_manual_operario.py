"""
Generador de Manual de Operario — Space Cheer
Usa playwright.sync_api (modo sync)
Cobertura completa OPERARIO: 7 secciones
"""

import base64
from pathlib import Path
from playwright.sync_api import sync_playwright

LOGO_PATH = Path("C:/Users/Lenovo/Documents/SPACE-CHEER/space_cheer/static/IMAGES/Logo_sin_fondo_blanco.png")


def logo_data_uri() -> str:
    if LOGO_PATH.exists():
        with open(LOGO_PATH, "rb") as f:
            return f"data:image/png;base64,{base64.b64encode(f.read()).decode()}"
    return ""


BASE_URL = "http://127.0.0.1:8000"
OUTPUT_PDF = "C:/Users/Lenovo/Documents/SPACE-CHEER/manual_operario.pdf"


def img_to_b64(png_bytes: bytes) -> str:
    return base64.b64encode(png_bytes).decode("utf-8")


def img_tag(key: str, screenshots: dict) -> str:
    if key in screenshots and screenshots[key]:
        return f'<img src="data:image/png;base64,{screenshots[key]}" alt="{key}">'
    return f'<div class="placeholder-img">[Captura no disponible: {key}]</div>'


def build_html(screenshots: dict) -> str:
    _logo_uri = logo_data_uri()
    logo_img = (
        f'<img src="{_logo_uri}" alt="Space Cheer" '
        f'style="width:180px;margin-bottom:20px;filter:brightness(0) invert(1)">'
        if _logo_uri else '<div class="logo-icon">&#128640;</div>'
    )

    def ss(key):
        return img_tag(key, screenshots)

    html = f"""<!DOCTYPE html>
<html lang="es">
<head>
<meta charset="UTF-8">
<title>Manual de Operario — Space Cheer</title>
<style>
  /* ---- reset & base ---- */
  *, *::before, *::after {{ box-sizing: border-box; margin: 0; padding: 0; }}

  body {{
    font-family: system-ui, -apple-system, "Segoe UI", sans-serif;
    font-size: 10.5pt;
    color: #1a1a2e;
    background: #ffffff;
    line-height: 1.6;
  }}

  /* ---- page breaks ---- */
  .page-break {{ page-break-after: always; break-after: page; }}

  /* ---- portada ---- */
  .cover {{
    background: linear-gradient(160deg, #0d0d1a 0%, #1a1140 100%);
    color: #ffffff;
    min-height: 100vh;
    display: flex;
    flex-direction: column;
    align-items: center;
    justify-content: center;
    text-align: center;
    padding: 60px 40px;
  }}
  .cover .logo-icon {{
    font-size: 64px;
    margin-bottom: 24px;
  }}
  .cover h1 {{
    font-size: 32pt;
    font-weight: 800;
    letter-spacing: -0.5px;
    margin-bottom: 12px;
    color: #ffffff;
  }}
  .cover .subtitle {{
    font-size: 13pt;
    color: #a78bfa;
    margin-bottom: 8px;
  }}
  .cover .meta {{
    font-size: 9pt;
    color: #6b7280;
    margin-top: 48px;
  }}
  .cover .badge {{
    display: inline-block;
    background: rgba(124,58,237,.25);
    border: 1px solid #7c3aed;
    color: #c4b5fd;
    padding: 4px 14px;
    border-radius: 20px;
    font-size: 9pt;
    margin-top: 16px;
  }}

  /* ---- secciones ---- */
  .section {{
    padding: 48px 52px 36px;
    max-width: 860px;
    margin: 0 auto;
  }}

  .section-header {{
    display: flex;
    align-items: center;
    gap: 14px;
    border-left: 5px solid #7c3aed;
    padding-left: 16px;
    margin-bottom: 28px;
  }}
  .section-header .num {{
    font-size: 11pt;
    font-weight: 700;
    color: #7c3aed;
    min-width: 28px;
  }}
  .section-header h2 {{
    font-size: 18pt;
    font-weight: 700;
    color: #1a1a2e;
  }}

  p {{
    margin-bottom: 12px;
    color: #374151;
  }}

  /* ---- screenshots ---- */
  .screenshot-wrap {{
    margin: 24px 0;
    border-radius: 8px;
    overflow: hidden;
    box-shadow: 0 2px 12px rgba(0,0,0,.25);
  }}
  .screenshot-wrap img {{
    width: 100%;
    border-radius: 8px;
    display: block;
  }}
  .screenshot-caption {{
    font-size: 8.5pt;
    color: #6b7280;
    text-align: center;
    margin-top: 6px;
    margin-bottom: 20px;
    font-style: italic;
  }}

  /* ---- placeholder ---- */
  .placeholder-img {{
    background: #f3f4f6;
    border: 2px dashed #d1d5db;
    border-radius: 8px;
    padding: 32px;
    text-align: center;
    color: #9ca3af;
    font-size: 9pt;
    margin: 16px 0;
  }}

  /* ---- pasos numerados ---- */
  ol.steps {{
    list-style: none;
    counter-reset: step;
    padding: 0;
    margin: 20px 0;
  }}
  ol.steps li {{
    counter-increment: step;
    display: flex;
    align-items: flex-start;
    gap: 14px;
    margin-bottom: 16px;
    padding: 14px 18px;
    background: #f9f7ff;
    border-radius: 8px;
    border: 1px solid #ede9fe;
  }}
  ol.steps li::before {{
    content: counter(step);
    background: #7c3aed;
    color: #ffffff;
    border-radius: 50%;
    min-width: 26px;
    height: 26px;
    display: flex;
    align-items: center;
    justify-content: center;
    font-size: 9pt;
    font-weight: 700;
    flex-shrink: 0;
  }}
  ol.steps li .step-body {{
    flex: 1;
  }}
  ol.steps li strong {{
    display: block;
    margin-bottom: 2px;
    color: #1a1a2e;
  }}
  ol.steps li span {{
    color: #4b5563;
    font-size: 9.5pt;
  }}

  /* ---- advertencia ---- */
  .warning {{
    background: #fffbeb;
    border-left: 4px solid #f59e0b;
    border-radius: 0 8px 8px 0;
    padding: 14px 18px;
    margin: 20px 0;
    color: #92400e;
    font-size: 9.5pt;
  }}
  .warning strong {{ color: #78350f; }}

  /* ---- info box ---- */
  .info-box {{
    background: #f0fdf4;
    border-left: 4px solid #22c55e;
    border-radius: 0 8px 8px 0;
    padding: 14px 18px;
    margin: 20px 0;
    color: #14532d;
    font-size: 9.5pt;
  }}

  /* ---- tabla ---- */
  table {{
    width: 100%;
    border-collapse: collapse;
    margin: 16px 0;
    font-size: 9.5pt;
  }}
  th {{
    background: #7c3aed;
    color: #fff;
    padding: 8px 12px;
    text-align: left;
  }}
  td {{
    padding: 8px 12px;
    border-bottom: 1px solid #e5e7eb;
    color: #374151;
  }}
  tr:nth-child(even) td {{
    background: #faf5ff;
  }}

  h3 {{
    font-size: 12pt;
    color: #4c1d95;
    margin: 24px 0 10px;
  }}
</style>
</head>
<body>

<!-- ============================================================
     PORTADA
     ============================================================ -->
<div class="cover page-break">
  {logo_img}
  <h1>Manual de Operario</h1>
  <div class="subtitle">Space Cheer — Sistema de Producción</div>
  <div class="badge">Versión 1.0 · Junio 2026</div>
  <div class="meta">
    Documento confidencial para uso interno.<br>
    Prohibida su reproducción sin autorización.
  </div>
</div>


<!-- ============================================================
     § 1  ACCESO AL SISTEMA
     ============================================================ -->
<div class="section page-break">
  <div class="section-header">
    <span class="num">§ 1</span>
    <h2>Acceso al sistema</h2>
  </div>

  <p>
    Para ingresar al sistema de producción de Space Cheer, abre tu navegador y
    visita la dirección que te proporcionó tu supervisor. Verás la pantalla de inicio
    de sesión que se muestra a continuación.
  </p>

  <div class="screenshot-wrap">
    {ss("login")}
  </div>
  <p class="screenshot-caption">Pantalla de inicio de sesión — Space Cheer Producción</p>

  <ol class="steps">
    <li>
      <div class="step-body">
        <strong>Ingresa tu nombre de usuario</strong>
        <span>Escribe el usuario asignado por tu supervisor en el campo "Usuario".</span>
      </div>
    </li>
    <li>
      <div class="step-body">
        <strong>Ingresa tu contraseña</strong>
        <span>Escribe tu contraseña en el campo "Contraseña". Los caracteres aparecerán ocultos.</span>
      </div>
    </li>
    <li>
      <div class="step-body">
        <strong>Haz clic en "Iniciar sesión"</strong>
        <span>Si tus credenciales son correctas, serás redirigido al panel principal.</span>
      </div>
    </li>
  </ol>

  <div class="warning">
    <strong>Importante:</strong> No compartas tu usuario ni contraseña con nadie.
    Si olvidas tu contraseña, comunícate con tu supervisor para restablecerla.
  </div>
</div>


<!-- ============================================================
     § 2  DASHBOARD DE PRODUCCIÓN
     ============================================================ -->
<div class="section page-break">
  <div class="section-header">
    <span class="num">§ 2</span>
    <h2>Dashboard de Producción</h2>
  </div>

  <p>
    Al iniciar sesión accedes al <strong>Dashboard de Producción</strong>. Desde aquí
    puedes ver todas las tareas asignadas a tu rol: tarjetas con el nombre de la etapa,
    orden correspondiente y su estado actual.
  </p>

  <div class="screenshot-wrap">
    {ss("dashboard")}
  </div>
  <p class="screenshot-caption">Dashboard de producción — tarjetas de tareas filtradas por rol del operario</p>

  <table>
    <tr><th>Elemento</th><th>Descripción</th></tr>
    <tr><td>Tarjetas de tarea</td><td>Cada tarjeta representa una tarea asignada a tu rol. Muestra la etapa, número de orden y estado.</td></tr>
    <tr><td>Borde de color</td><td>Rojo = urgente o atrasada. Verde = en progreso normal.</td></tr>
    <tr><td>Botón "Completar"</td><td>Botón verde en cada tarjeta para registrar la finalización de la tarea.</td></tr>
    <tr><td>Icono de diseño</td><td>Si está disponible, permite ver el diseño del uniforme antes de trabajar.</td></tr>
    <tr><td>Menú superior</td><td>Acceso rápido a Mi Área, Reglamento y Reportar Errores.</td></tr>
  </table>

  <div class="info-box">
    <strong>Tip:</strong> Revisa el dashboard al inicio de cada turno para conocer
    tus tareas asignadas y las prioridades del día.
  </div>
</div>


<!-- ============================================================
     § 3  COMPLETAR UNA TAREA
     ============================================================ -->
<div class="section page-break">
  <div class="section-header">
    <span class="num">§ 3</span>
    <h2>Completar una tarea</h2>
  </div>

  <p>
    Cada tarjeta de tarea en el Dashboard tiene un botón verde <strong>"Completar"</strong>.
    Al hacer clic se abre un formulario emergente (modal) donde debes confirmar la finalización
    de la tarea y agregar observaciones si es necesario.
  </p>

  <h3>Vista del dashboard antes de completar</h3>
  <div class="screenshot-wrap">
    {ss("dashboard")}
  </div>
  <p class="screenshot-caption">Dashboard — localiza la tarea y haz clic en el botón verde "Completar"</p>

  <h3>Formulario de confirmación</h3>
  <div class="screenshot-wrap">
    {ss("dashboard_modal")}
  </div>
  <p class="screenshot-caption">Modal de confirmación — aparece al hacer clic en "Completar"</p>

  <ol class="steps">
    <li>
      <div class="step-body">
        <strong>Localiza tu tarea en el Dashboard</strong>
        <span>Identifica la tarjeta correspondiente a tu etapa y orden de trabajo.</span>
      </div>
    </li>
    <li>
      <div class="step-body">
        <strong>Haz clic en el botón verde "Completar"</strong>
        <span>Se abrirá un formulario emergente sobre la pantalla.</span>
      </div>
    </li>
    <li>
      <div class="step-body">
        <strong>Revisa los datos del formulario</strong>
        <span>Verifica que la tarea mostrada corresponde a la que terminaste.</span>
      </div>
    </li>
    <li>
      <div class="step-body">
        <strong>Agrega observaciones si es necesario</strong>
        <span>Si hay algo que el supervisor deba saber, escríbelo en el campo de notas.</span>
      </div>
    </li>
    <li>
      <div class="step-body">
        <strong>Presiona "Confirmar" o "Guardar"</strong>
        <span>El sistema registra la tarea como completada. Desaparecerá del Dashboard y quedará en el historial.</span>
      </div>
    </li>
  </ol>

  <div class="warning">
    <strong>Importante:</strong> Una vez confirmada, la tarea no puede editarse.
    Si cometiste un error en los datos registrados, repórtalo usando la sección
    Reportar un error (§ 7) para que el supervisor lo corrija.
  </div>

  <div class="info-box">
    <strong>Buenas prácticas:</strong> Si una tarea está bloqueada (icono de candado), espera
    a que la etapa anterior sea completada. Completa siempre las tareas en el orden
    que indica el sistema. Si hay un impedimento (falta de material, equipo dañado),
    repórtalo antes de saltar a la siguiente tarea.
  </div>
</div>


<!-- ============================================================
     § 4  MI ÁREA
     ============================================================ -->
<div class="section page-break">
  <div class="section-header">
    <span class="num">§ 4</span>
    <h2>Mi Área</h2>
  </div>

  <p>
    La sección <strong>Mi Área</strong> muestra tu perfil dentro del sistema de producción:
    los roles que tienes asignados (Diseñador, Cristalero, Logística, etc.), las etapas en las
    que eres responsable principal y en cuáles participas como auxiliar.
  </p>

  <div class="screenshot-wrap">
    {ss("mi_area")}
  </div>
  <p class="screenshot-caption">Mi Área — roles asignados y etapas de responsabilidad del operario</p>

  <table>
    <tr><th>Información</th><th>Descripción</th></tr>
    <tr><td>Roles asignados</td><td>Lista de roles que tiene el operario (ej. Diseñador, Cristalero, Logística).</td></tr>
    <tr><td>Etapas como responsable</td><td>Etapas de producción donde el operario es el responsable principal de completar la tarea.</td></tr>
    <tr><td>Etapas como auxiliar</td><td>Etapas en las que el operario apoya sin ser el responsable directo.</td></tr>
    <tr><td>Historial de tareas</td><td>Registro de tareas completadas por el operario en el sistema.</td></tr>
  </table>

  <div class="info-box">
    <strong>Nota:</strong> Si consideras que falta algún rol o que tus etapas asignadas
    son incorrectas, consulta con tu supervisor para que realice los ajustes necesarios.
    Los roles determinan qué tareas verás en el Dashboard.
  </div>
</div>


<!-- ============================================================
     § 5  REGLAMENTO
     ============================================================ -->
<div class="section page-break">
  <div class="section-header">
    <span class="num">§ 5</span>
    <h2>Reglamento</h2>
  </div>

  <p>
    La sección de <strong>Reglamento</strong> contiene las normas de conducta,
    seguridad y operación que todo operario debe conocer y cumplir.
    Su lectura es obligatoria al incorporarse al equipo de producción.
  </p>

  <div class="screenshot-wrap">
    {ss("reglamento")}
  </div>
  <p class="screenshot-caption">Sección de Reglamento — normas y políticas de operación del sistema de producción</p>

  <div class="warning">
    <strong>Obligatorio:</strong> El desconocimiento del reglamento no exime
    de responsabilidad ante una infracción. Léelo completo y consulta con tu
    supervisor si tienes dudas sobre alguna norma.
  </div>

  <div class="info-box">
    <strong>Acceso:</strong> Puedes consultar el reglamento en cualquier momento
    desde el menú de navegación superior, sección "Reglamento". Está disponible
    durante todo tu turno de trabajo.
  </div>
</div>


<!-- ============================================================
     § 6  DISEÑO DEL PEDIDO
     ============================================================ -->
<div class="section page-break">
  <div class="section-header">
    <span class="num">§ 6</span>
    <h2>Diseño del pedido</h2>
  </div>

  <p>
    Antes de iniciar el trabajo en una etapa, es fundamental revisar el
    <strong>diseño del uniforme</strong> correspondiente al pedido. Esta vista
    muestra las especificaciones visuales, colores, logotipos y detalles del
    uniforme que debes producir.
  </p>

  <div class="screenshot-wrap">
    {ss("order_design")}
  </div>
  <p class="screenshot-caption">Vista de diseño del pedido — especificaciones visuales del uniforme a producir</p>

  <ol class="steps">
    <li>
      <div class="step-body">
        <strong>Accede al diseño desde la tarjeta de tarea</strong>
        <span>En el Dashboard, cada tarjeta puede tener un icono o enlace que lleva al diseño del pedido.</span>
      </div>
    </li>
    <li>
      <div class="step-body">
        <strong>Revisa los colores y especificaciones</strong>
        <span>Verifica los colores exactos, posición de logotipos y cualquier detalle especial indicado en el diseño.</span>
      </div>
    </li>
    <li>
      <div class="step-body">
        <strong>Consulta al supervisor ante dudas</strong>
        <span>Si algún elemento del diseño no es claro o parece diferente a lo que tienes disponible, consulta antes de comenzar.</span>
      </div>
    </li>
  </ol>

  <div class="warning">
    <strong>Importante:</strong> Nunca comiences a trabajar en un uniforme sin
    haber revisado el diseño aprobado. Un error en los materiales o colores puede
    resultar en el rechazo del producto terminado.
  </div>
</div>


<!-- ============================================================
     § 7  REPORTAR UN ERROR
     ============================================================ -->
<div class="section">
  <div class="section-header">
    <span class="num">§ 7</span>
    <h2>Reportar un error</h2>
  </div>

  <p>
    Si durante tu turno encuentras un problema — ya sea en el sistema, en los
    materiales o en el proceso de producción — debes reportarlo inmediatamente en la sección
    <strong>Errores</strong>. Esto ayuda al equipo a resolver el problema rápido
    y evita que afecte la producción general.
  </p>

  <div class="info-box">
    <strong>Nota:</strong> La lista completa de reportes de error es accesible sólo para
    supervisores y administradores. Como operario, puedes <em>crear</em> reportes pero no
    ver el historial completo del sistema.
  </div>

  <h3>Formulario de nuevo error</h3>
  <div class="screenshot-wrap">
    {ss("errores_nuevo")}
  </div>
  <p class="screenshot-caption">Formulario para reportar un nuevo error o incidencia de producción</p>

  <ol class="steps">
    <li>
      <div class="step-body">
        <strong>Ve a Errores > Nuevo error</strong>
        <span>En el menú de navegación superior, selecciona "Errores" y luego "Reportar nuevo".</span>
      </div>
    </li>
    <li>
      <div class="step-body">
        <strong>Selecciona el tipo de error</strong>
        <span>Elige la categoría que mejor describe el problema (sistema, proceso, material, equipo, etc.).</span>
      </div>
    </li>
    <li>
      <div class="step-body">
        <strong>Describe el problema con detalle</strong>
        <span>Explica qué ocurrió, en qué paso de la tarea y qué observaste. Cuanto más detalle, más fácil es resolverlo.</span>
      </div>
    </li>
    <li>
      <div class="step-body">
        <strong>Adjunta evidencia si es posible</strong>
        <span>Si el formulario permite subir una foto o captura de pantalla, inclúyela para facilitar el diagnóstico.</span>
      </div>
    </li>
    <li>
      <div class="step-body">
        <strong>Haz clic en "Enviar reporte"</strong>
        <span>El supervisor recibirá una notificación y atenderá el error a la brevedad posible.</span>
      </div>
    </li>
  </ol>

  <div class="info-box">
    <strong>Recuerda:</strong> Reportar errores no es un signo de falla personal.
    Al contrario, es parte fundamental de mantener la calidad del proceso.
    <em>No reportar</em> un error conocido si puede ser considerado una falta disciplinaria.
  </div>
</div>

</body>
</html>"""
    return html


def main():
    print("[1/3] Iniciando Playwright...")
    with sync_playwright() as p:
        browser = p.chromium.launch(
            headless=True,
            args=["--ignore-certificate-errors", "--disable-web-security"],
        )
        context = browser.new_context(
            viewport={"width": 1440, "height": 900},
            ignore_https_errors=True,
        )
        page = context.new_page()

        screenshots = {}

        # ------------------------------------------------------------------
        # § 1 — Login page screenshot (before login)
        # ------------------------------------------------------------------
        print("[2/3] Capturando páginas...")
        print("  -> login page...")
        page.goto(f"{BASE_URL}/accounts/login/", wait_until="load")
        screenshots["login"] = img_to_b64(page.screenshot(full_page=False))
        print("  OK login capturado")

        # ------------------------------------------------------------------
        # Perform login
        # ------------------------------------------------------------------
        print("  -> Haciendo login con operario1...")
        page.fill('input[name="login"]', "operario1")
        page.fill('input[name="password"]', "Test1234!")
        # Use click with no_wait_after so we don't block on navigation
        try:
            page.click('button[type="submit"]', timeout=5000)
        except Exception:
            pass  # timeout on navigation is expected with some allauth versions
        # Wait for navigation to settle
        try:
            page.wait_for_load_state("load", timeout=8000)
        except Exception:
            pass
        page.wait_for_timeout(2000)
        print(f"  OK post-login URL: {page.url}")
        # If still on login page, check for error message
        if "/accounts/login/" in page.url:
            error_text = page.text_content("body")
            print(f"  -- page text snippet: {error_text[:300]}")
            raise RuntimeError(
                f"Login fallido para operario1 — URL sigue en login: {page.url}\n"
                "Verifica que el servidor corra en :8000 y el usuario existe con password Test1234!"
            )

        # ------------------------------------------------------------------
        # § 2 — Dashboard (full_page=True)
        # ------------------------------------------------------------------
        print("  -> /production/ (dashboard)...")
        page.goto(f"{BASE_URL}/production/", wait_until="load")
        page.wait_for_timeout(800)
        screenshots["dashboard"] = img_to_b64(page.screenshot(full_page=True))
        print("  OK dashboard capturado")

        # ------------------------------------------------------------------
        # § 3 — Modal de completar tarea (click en botón verde "Completar")
        # ------------------------------------------------------------------
        print("  -> Modal de completar tarea...")
        # We are already on /production/ from above; click the first "Completar" btn
        try:
            # Try several selectors — may vary by template
            selectors = [
                "button.btn-success",
                "button:has-text('Completar')",
                "a:has-text('Completar')",
                ".btn-success",
            ]
            found = False
            for sel in selectors:
                btn = page.query_selector(sel)
                if btn:
                    btn.click()
                    page.wait_for_timeout(800)
                    screenshots["dashboard_modal"] = img_to_b64(
                        page.screenshot(full_page=False)
                    )
                    print(f"  OK dashboard_modal capturado (selector: {sel})")
                    found = True
                    break
            if not found:
                print("  -- no se encontró botón 'Completar'; modal no capturado")
        except Exception as e:
            print(f"  -- modal error: {e}")

        # ------------------------------------------------------------------
        # § 4 — Mi Área
        # ------------------------------------------------------------------
        print("  -> /production/mi-area/...")
        page.goto(f"{BASE_URL}/production/mi-area/", wait_until="load")
        page.wait_for_timeout(600)
        screenshots["mi_area"] = img_to_b64(page.screenshot(full_page=True))
        print("  OK mi_area capturado")

        # ------------------------------------------------------------------
        # § 5 — Reglamento
        # ------------------------------------------------------------------
        print("  -> /production/reglamento/...")
        page.goto(f"{BASE_URL}/production/reglamento/", wait_until="load")
        page.wait_for_timeout(600)
        screenshots["reglamento"] = img_to_b64(page.screenshot(full_page=True))
        print("  OK reglamento capturado")

        # ------------------------------------------------------------------
        # § 6 — Vista de diseño del pedido (order 20)
        # ------------------------------------------------------------------
        print("  -> /production/order/2/design/...")
        try:
            resp = page.goto(
                f"{BASE_URL}/production/order/2/design/",
                wait_until="load",
            )
            page.wait_for_timeout(600)
            screenshots["order_design"] = img_to_b64(page.screenshot(full_page=True))
            status = resp.status if resp else "?"
            print(f"  OK order_design capturado (status {status})")
        except Exception as e:
            print(f"  -- order_design error: {e}; capturando como está...")
            screenshots["order_design"] = img_to_b64(page.screenshot(full_page=True))

        # ------------------------------------------------------------------
        # § 7 — Formulario de nuevo error
        # ------------------------------------------------------------------
        print("  -> /production/errores/nuevo/...")
        page.goto(f"{BASE_URL}/production/errores/nuevo/", wait_until="load")
        page.wait_for_timeout(600)
        screenshots["errores_nuevo"] = img_to_b64(page.screenshot(full_page=True))
        print("  OK errores_nuevo capturado")

        # ------------------------------------------------------------------
        # Build HTML & render PDF
        # ------------------------------------------------------------------
        print("[3/3] Construyendo HTML...")
        html_content = build_html(screenshots)

        print("  -> Renderizando PDF...")
        pdf_page = context.new_page()
        pdf_page.set_content(html_content, wait_until="load")
        pdf_page.pdf(
            path=OUTPUT_PDF,
            format="A4",
            print_background=True,
            margin={"top": "0", "bottom": "0", "left": "0", "right": "0"},
        )
        print(f"  OK PDF generado en: {OUTPUT_PDF}")

        browser.close()

    # Report size
    size = Path(OUTPUT_PDF).stat().st_size
    captured = list(screenshots.keys())
    print(f"\n  PDF listo — tamaño: {size:,} bytes ({size / 1024:.1f} KB)")
    print(f"  Capturas incluidas: {captured}")


if __name__ == "__main__":
    main()
