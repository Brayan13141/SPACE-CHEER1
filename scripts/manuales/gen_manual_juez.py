"""
Generador de Manual de Juez — Space Cheer (cobertura completa)
"""
import base64
import sys
from pathlib import Path
from playwright.sync_api import sync_playwright

sys.path.insert(0, str(Path(__file__).parent))
from highlight_utils import capture_with_button

LOGO_PATH  = Path("C:/Users/Lenovo/Documents/SPACE-CHEER/space_cheer/static/IMAGES/Logo_sin_fondo_blanco.png")
BASE_URL   = "http://127.0.0.1:8000"
OUTPUT_PDF = "C:/Users/Lenovo/Documents/SPACE-CHEER/manual_juez.pdf"
USERNAME   = "juez_test"
PASSWORD   = "Test1234!"
SCREENSHOTS_DIR = Path("C:/Users/Lenovo/Documents/SPACE-CHEER/manual_juez_screenshots")

# (url_path, filename, from_path, link_text_hint)
PAGES = [
    ("/",                              "home",              None,                None),
    ("/events/",                       "eventos_lista",     "/",                 "Competencias"),
    ("/events/8/",                     "evento_grandprix",  "/events/",          "Grand Prix"),
    ("/events/9/",                     "evento_copa",       "/events/",          "Copa Galaxia"),
    ("/events/8/judge/",               "panel_juez_8",      "/events/8/",        "Juez"),
    ("/events/9/judge/",               "panel_juez_9",      "/events/9/",        "Juez"),
    ("/hospitality/event/8/my-stay/",  "mi_estancia",       "/events/8/",        "Hospitalidad"),
    ("/hospitality/event/8/preferences/", "preferencias",   "/hospitality/event/8/my-stay/", "Preferencias"),
    ("/accounts/profile/edit/",        "perfil_editar",     "/",                 "Perfil"),
    ("/accounts/profile/settings/",    "perfil_config",     "/accounts/profile/edit/", "Configuración"),
]


def logo_uri():
    if LOGO_PATH.exists():
        return f"data:image/png;base64,{base64.b64encode(LOGO_PATH.read_bytes()).decode()}"
    return ""


def capture():
    shots = {}
    json_responses = {}

    with sync_playwright() as p:
        browser = p.chromium.launch()
        ctx  = browser.new_context(viewport={"width": 1280, "height": 800})
        page = ctx.new_page()

        # Login
        page.goto(f"{BASE_URL}/accounts/login/", wait_until="load")
        # Capture login form before submit (for the manual)
        shots["login_form"] = base64.b64encode(page.screenshot(full_page=True)).decode()
        page.fill("input[name='login']", USERNAME)
        page.fill("input[name='password']", PASSWORD)
        # Check "remember me" so the session cookie persists across navigations
        try:
            page.check("input[name='remember']")
        except Exception:
            pass
        page.click("button[type='submit']")
        try:
            page.wait_for_url(lambda url: "login" not in url, timeout=15000)
        except Exception:
            page.wait_for_timeout(3000)
        shots["login_ok"] = base64.b64encode(page.screenshot(full_page=True)).decode()
        print(f"  Login -> {page.url}")
        print("  OK /accounts/login/")

        SCREENSHOTS_DIR.mkdir(parents=True, exist_ok=True)
        for path, key, from_path, link_hint in PAGES:
            try:
                result = capture_with_button(
                    page, BASE_URL, SCREENSHOTS_DIR,
                    from_path=from_path, to_path=path, filename=key,
                    link_text_hint=link_hint,
                )
                final = page.url.replace(BASE_URL, "")

                if result["ok"]:
                    with open(result["path"], "rb") as f:
                        shots[key] = base64.b64encode(f.read()).decode()
                else:
                    # Se captura igual la pantalla a la que redirigió, para
                    # documentar el comportamiento real (ej. acceso denegado).
                    shots[key] = base64.b64encode(page.screenshot(full_page=True)).decode()

                if path != "/" and not final.rstrip("/").startswith(path.rstrip("/")):
                    print(f"  -- {path} REDIRECTED -> {final} (capturado igualmente)")
                else:
                    print(f"  OK {path}")

                if result["button_ok"]:
                    with open(result["button_path"], "rb") as f:
                        shots[f"{key}_boton"] = base64.b64encode(f.read()).decode()
                    print(f"       BOTON OK: {result['button_path']}")
                elif from_path:
                    print(f"       BOTON no encontrado (origen: {from_path}, hint: {link_hint})")

            except Exception as e:
                print(f"  ERR {path}: {e}")

        browser.close()
    return shots, json_responses


def build_html(shots, json_responses, logo):
    def ss(key, cap=""):
        if key not in shots:
            return f'<p class="no-cap">[Sin captura: {key}]</p>'
        return (
            f'<div class="ss-wrap"><img src="data:image/png;base64,{shots[key]}" alt="{key}"></div>'
            + (f'<p class="ss-cap">{cap}</p>' if cap else "")
        )

    def ssb(key, cap=""):
        """Como ss(), pero antepone la captura con el botón resaltado (si existe)."""
        button_key = f"{key}_boton"
        button_html = ""
        if button_key in shots:
            button_html = (
                '<p class="button-caption">&#128073; Así se llega a esta pantalla &mdash; '
                'el botón resaltado en rojo:</p>'
                f'<div class="ss-wrap screenshot-button"><img src="data:image/png;base64,{shots[button_key]}" alt="Botón hacia {key}"></div>'
            )
        return button_html + ss(key, cap)

    def json_block(key):
        content = json_responses.get(key, "")
        if not content:
            return ""
        # truncate for display
        display = content[:800] + ("..." if len(content) > 800 else "")
        return f'<pre class="json-block">{display}</pre>'

    logo_img = (
        f'<img src="{logo}" alt="Space Cheer" style="width:180px;margin-bottom:20px;filter:brightness(0) invert(1)">'
        if logo else '<div class="cover-icon">⚖️</div>'
    )

    return f"""<!DOCTYPE html>
<html lang="es"><head><meta charset="UTF-8">
<title>Manual de Juez — Space Cheer</title>
<style>
*,*::before,*::after{{box-sizing:border-box;margin:0;padding:0}}
body{{font-family:system-ui,-apple-system,"Segoe UI",sans-serif;font-size:10.5pt;color:#1a1a2e;background:#fff;line-height:1.6}}
.pb{{page-break-after:always;break-after:page}}
.cover{{background:linear-gradient(160deg,#1a0d0d,#3d1a0a);color:#fff;min-height:100vh;display:flex;flex-direction:column;align-items:center;justify-content:center;text-align:center;padding:60px 40px}}
.cover h1{{font-size:30pt;font-weight:800;margin-bottom:10px}}
.cover .sub{{font-size:13pt;color:#fca5a5;margin-bottom:8px}}
.cover .badge{{display:inline-block;background:rgba(239,68,68,.2);border:1px solid #ef4444;color:#fca5a5;padding:4px 14px;border-radius:20px;font-size:9pt;margin-top:16px}}
.cover .meta{{font-size:9pt;color:#6b7280;margin-top:40px}}
.sec{{padding:44px 52px 32px;max-width:860px;margin:0 auto}}
.sec-hdr{{display:flex;align-items:center;gap:14px;border-left:5px solid #dc2626;padding-left:16px;margin-bottom:24px}}
.sec-hdr .num{{font-size:11pt;font-weight:700;color:#dc2626;min-width:28px}}
.sec-hdr h2{{font-size:17pt;font-weight:700;color:#1a1a2e}}
h3{{font-size:12pt;font-weight:700;color:#1a1a2e;margin:22px 0 10px;padding-left:12px;border-left:3px solid #fca5a5}}
p{{margin-bottom:12px;color:#374151}}
.ss-wrap{{margin:20px 0;border-radius:8px;overflow:hidden;box-shadow:0 2px 12px rgba(0,0,0,.2)}}
.ss-wrap img{{width:100%;display:block;border-radius:8px}}
.ss-cap{{font-size:8.5pt;color:#6b7280;text-align:center;margin-top:6px;margin-bottom:18px;font-style:italic}}
.no-cap{{color:#9ca3af;font-style:italic;margin:10px 0}}
.info{{background:#fff1f2;border-left:4px solid #ef4444;border-radius:0 8px 8px 0;padding:14px 18px;margin:18px 0;color:#991b1b;font-size:9.5pt}}
.warn{{background:#fffbeb;border-left:4px solid #f59e0b;border-radius:0 8px 8px 0;padding:14px 18px;margin:18px 0;color:#92400e;font-size:9.5pt}}
.tip{{background:#f0fdf4;border-left:4px solid #22c55e;border-radius:0 8px 8px 0;padding:14px 18px;margin:18px 0;color:#14532d;font-size:9.5pt}}
table{{width:100%;border-collapse:collapse;margin:16px 0;font-size:9.5pt}}
th{{background:#dc2626;color:#fff;padding:8px 12px;text-align:left}}
td{{padding:8px 12px;border-bottom:1px solid #e5e7eb;color:#374151}}
tr:nth-child(even) td{{background:#fff5f5}}
ol.steps{{list-style:none;counter-reset:s;padding:0;margin:18px 0}}
ol.steps li{{counter-increment:s;display:flex;align-items:flex-start;gap:12px;margin-bottom:14px;padding:12px 16px;background:#fff5f5;border-radius:8px;border:1px solid #fecaca}}
ol.steps li::before{{content:counter(s);background:#dc2626;color:#fff;border-radius:50%;min-width:24px;height:24px;display:flex;align-items:center;justify-content:center;font-size:9pt;font-weight:700;flex-shrink:0}}
ol.steps li strong{{display:block;margin-bottom:2px;color:#1a1a2e}}
ol.steps li span{{color:#4b5563;font-size:9.5pt}}
.json-block{{background:#0f172a;color:#a3e635;font-family:monospace;font-size:7.5pt;padding:14px;border-radius:8px;overflow:hidden;margin:14px 0;white-space:pre-wrap;word-break:break-all}}
.api-badge{{display:inline-block;background:#1e3a5f;color:#93c5fd;font-size:8pt;font-weight:700;padding:2px 10px;border-radius:4px;margin-bottom:10px;letter-spacing:.05em}}
.status-chip{{display:inline-block;padding:2px 10px;border-radius:12px;font-size:8pt;font-weight:600}}
.status-open{{background:#dcfce7;color:#166534}}
.status-done{{background:#f3f4f6;color:#374151}}
.backcover{{background:linear-gradient(160deg,#1a0d0d,#3d1a0a);color:#fff;min-height:100vh;display:flex;flex-direction:column;align-items:center;justify-content:center;text-align:center;padding:60px 40px}}
.backcover p{{color:#fca5a5}}
.button-caption{{color:#b91c1c;font-size:9pt;font-weight:600;margin:14px 0 4px}}
.screenshot-button img{{box-shadow:0 2px 12px rgba(0,0,0,.2),0 0 0 2px #ef4444}}
.use-case{{background:#fff5f5;border:1px solid #fca5a5;border-left:4px solid #dc2626;border-radius:0 8px 8px 0;padding:14px 18px;margin:18px 0}}
.use-case-title{{color:#b91c1c;font-weight:700;font-size:10.5pt;margin-bottom:8px}}
.use-case ol{{margin:6px 0 0 18px;padding:0}}
.use-case li{{color:#374151;font-size:9.5pt;margin-bottom:4px}}
</style></head><body>

<!-- PORTADA -->
<div class="cover pb">
  {logo_img}
  <h1>Manual de Juez</h1>
  <div class="sub">Space Cheer — Panel de Evaluación en Tiempo Real</div>
  <div class="badge">Versión 1.0 &middot; Junio 2026</div>
  <div class="meta">Documento de uso interno.<br>Para soporte contacta al administrador del evento.</div>
</div>

<!-- § 1 ACCESO AL SISTEMA -->
<div class="sec pb">
  <div class="sec-hdr"><span class="num">§ 1</span><h2>Acceso al Sistema</h2></div>
  <p>Ingresa al sistema Space Cheer con el usuario y contraseña que te proporcionó el organizador del evento. Utiliza el navegador en la tablet o computadora asignada durante la competencia.</p>

  <ol class="steps">
    <li><strong>Abre el navegador</strong><span>Escribe la dirección del sistema Space Cheer en la barra de direcciones.</span></li>
    <li><strong>Introduce tus credenciales</strong><span>Escribe tu nombre de usuario y contraseña. Ambos son sensibles a mayúsculas.</span></li>
    <li><strong>Haz clic en "Iniciar sesión"</strong><span>Si los datos son correctos, serás redirigido al panel principal.</span></li>
  </ol>

  {ss("login_form", "Formulario de inicio de sesion")}
  {ss("login_ok", "Dashboard tras iniciar sesion correctamente")}

  <div class="info"><strong>Importante:</strong> Tu cuenta de Juez es personal e intransferible. No compartas tus credenciales con ningun otro participante o personal del evento.</div>
  <div class="warn"><strong>Sesion expirada:</strong> Si el sistema te pide iniciar sesion de nuevo, es porque tu sesion expiro por inactividad. Vuelve a ingresar tus credenciales.</div>
</div>

<!-- § 2 LISTA DE EVENTOS -->
<div class="sec pb">
  <div class="sec-hdr"><span class="num">§ 2</span><h2>Lista de Eventos</h2></div>
  <p>Al acceder al sistema encontraras el panel principal con accesos rapidos. Desde la seccion <strong>Eventos</strong> puedes ver todas las competencias disponibles.</p>

  {ss("home", "Panel principal tras iniciar sesion")}

  <h3>Directorio de Competencias</h3>
  <p>En <strong>/events/</strong> se muestra el catalogo de todos los eventos registrados en el sistema. Como juez veras los eventos donde estas asignado.</p>
  {ssb("eventos_lista", "Listado de todos los eventos")}

  <table>
    <tr><th>Campo</th><th>Descripcion</th></tr>
    <tr><td>Nombre del evento</td><td>Identificador unico de la competencia.</td></tr>
    <tr><td>Estado</td><td><span class="status-chip status-open">REGISTRATION_OPEN</span> &nbsp; <span class="status-chip status-done">COMPLETED</span></td></tr>
    <tr><td>Fecha</td><td>Fecha programada para la realizacion del evento.</td></tr>
    <tr><td>Acciones</td><td>Ver detalles, acceder al Panel de Juez.</td></tr>
  </table>

  <h3>Detalle: Grand Prix (Evento 8 — REGISTRATION_OPEN)</h3>
  <p>El Grand Prix es el evento activo donde estas asignado como juez. Su estado es <strong>REGISTRATION_OPEN</strong>, lo que significa que la evaluacion esta disponible.</p>
  {ssb("evento_grandprix", "Pagina de detalle del Grand Prix (evento activo)")}

  <h3>Detalle: Copa Galaxia (Evento 9 — COMPLETED)</h3>
  <p>La Copa Galaxia es un evento ya finalizado. Puede mostrarse en modo de solo lectura con los resultados definitivos.</p>
  {ssb("evento_copa", "Pagina de detalle de Copa Galaxia (evento completado)")}
</div>

<!-- § 3 PANEL DE EVALUACION -->
<div class="sec pb">
  <div class="sec-hdr"><span class="num">§ 3</span><h2>Panel de Evaluacion</h2></div>
  <p>El <strong>Panel de Juez</strong> es la interfaz principal para registrar puntuaciones en tiempo real. Cada evento tiene su propio panel accesible desde la pagina de detalle del evento.</p>

  <h3>Panel de Juez — Grand Prix (Evento 8, activo)</h3>
  <p>Como juez asignado al Grand Prix (pk=8), tienes acceso completo al formulario de evaluacion. Aqui ingresaras los puntajes para cada equipo durante la competencia.</p>
  {ssb("panel_juez_8", "Panel de evaluacion en tiempo real — Grand Prix")}

  <ol class="steps">
    <li><strong>Selecciona el equipo a evaluar</strong><span>El panel muestra la lista de equipos participantes en turno. Selecciona el equipo que se esta presentando.</span></li>
    <li><strong>Ingresa las puntuaciones por categoria</strong><span>Completa cada criterio de evaluacion segun el reglamento del evento (tecnica, sincronizacion, dificultad, presentacion, etc.).</span></li>
    <li><strong>Revisa antes de confirmar</strong><span>Verifica que todos los campos esten completos y que los puntajes sean correctos.</span></li>
    <li><strong>Envia la evaluacion</strong><span>Haz clic en el boton de envio. La puntuacion se registra con tu usuario y es inmediata.</span></li>
    <li><strong>Continua con el siguiente equipo</strong><span>Repite el proceso para cada equipo en competencia.</span></li>
  </ol>

  <div class="warn"><strong>Imparcialidad:</strong> Las evaluaciones se registran con tu usuario y son auditables por el organizador. Califica objetivamente segun el reglamento vigente del evento.</div>
  <div class="info"><strong>Sin modificaciones:</strong> Una vez confirmada la puntuacion, no podra modificarse sin autorizacion expresa del organizador del evento.</div>
  <div class="use-case">
    <div class="use-case-title">Caso de uso &mdash; Evaluar un equipo durante la competencia</div>
    <ol>
      <li>Desde el detalle del evento activo, entra al <strong>Panel de Juez</strong>.</li>
      <li>Selecciona el equipo que se está presentando en ese momento.</li>
      <li>Llena cada categoría de evaluación según el reglamento del evento.</li>
      <li>Revisa los puntajes y confirma el envío &mdash; una vez enviado, no se puede editar sin autorización del organizador.</li>
    </ol>
  </div>

  <h3>Panel de Juez — Copa Galaxia (Evento 9, completado)</h3>
  <p>La Copa Galaxia ya ha concluido. El panel puede mostrar los resultados finales o estar en modo de solo lectura.</p>
  {ssb("panel_juez_9", "Panel de evaluacion — Copa Galaxia (evento completado)")}

  <table>
    <tr><th>Accion</th><th>Descripcion</th></tr>
    <tr><td>Evaluar equipo</td><td>Asignar puntajes por categoria segun la actuacion observada.</td></tr>
    <tr><td>Ver marcador</td><td>Consultar la clasificacion general actualizada en tiempo real.</td></tr>
    <tr><td>Historial</td><td>Revisar evaluaciones anteriores enviadas en el mismo evento.</td></tr>
    <tr><td>Evento completado</td><td>Ver resultados finales de eventos ya cerrados (solo lectura).</td></tr>
  </table>
</div>

<!-- § 4 HOSPITALIDAD Y ESTANCIA -->
<div class="sec pb">
  <div class="sec-hdr"><span class="num">§ 4</span><h2>Hospitalidad y Estancia</h2></div>
  <p>Si el evento incluye servicios de hospitalidad para jueces (alojamiento, comidas, traslados), puedes consultarlos y gestionarlos desde esta seccion.</p>

  <h3>Mi Estancia</h3>
  <p>La seccion <strong>Mi Estancia</strong> muestra los detalles de tu alojamiento asignado para el Grand Prix: hotel, habitacion, fechas de check-in y check-out.</p>
  {ssb("mi_estancia", "Mi Estancia — detalles del alojamiento (Grand Prix)")}

  <h3>Preferencias</h3>
  <p>En <strong>Preferencias</strong> puedes indicar necesidades especiales: tipo de habitacion, restricciones alimentarias, accesibilidad u otras solicitudes al organizador.</p>
  {ssb("preferencias", "Formulario de preferencias de estancia")}

  <div class="tip"><strong>Recomendacion:</strong> Completa tus preferencias lo antes posible para que el organizador pueda gestionarlas con suficiente anticipacion al evento.</div>

  <table>
    <tr><th>Servicio</th><th>Descripcion</th></tr>
    <tr><td>Alojamiento</td><td>Hotel y habitacion asignados para el periodo del evento.</td></tr>
    <tr><td>Preferencias</td><td>Requisitos especiales: dieta, accesibilidad, tipo de cama, etc.</td></tr>
    <tr><td>Check-in / Check-out</td><td>Fechas y horarios de llegada y salida del alojamiento.</td></tr>
  </table>
</div>

<!-- § 5 MI PERFIL -->
<div class="sec pb">
  <div class="sec-hdr"><span class="num">§ 5</span><h2>Mi Perfil</h2></div>
  <p>Mantén tu informacion personal actualizada. Los datos del juez son necesarios para los registros oficiales del evento y los certificados de participacion.</p>

  <h3>Editar Perfil</h3>
  <p>Desde <strong>Editar Perfil</strong> puedes actualizar tu nombre, apellidos, foto, numero de contacto y cualquier otro dato personal.</p>
  {ssb("perfil_editar", "Formulario de edicion de perfil")}

  <ol class="steps">
    <li><strong>Accede a "Mi Perfil"</strong><span>Haz clic en tu nombre o avatar en la barra superior de navegacion.</span></li>
    <li><strong>Selecciona "Editar perfil"</strong><span>Esto abrira el formulario con tus datos actuales.</span></li>
    <li><strong>Actualiza los campos necesarios</strong><span>Modifica nombre, contacto, fotografia u otros campos disponibles.</span></li>
    <li><strong>Guarda los cambios</strong><span>Haz clic en "Guardar" para aplicar las actualizaciones.</span></li>
  </ol>

  <h3>Configuracion de Cuenta</h3>
  <p>En <strong>Configuracion</strong> puedes cambiar tu contrasena, ajustar notificaciones y gestionar la seguridad de tu cuenta.</p>
  {ssb("perfil_config", "Configuracion de cuenta y seguridad")}

  <div class="info"><strong>Contrasena:</strong> Si necesitas cambiar tu contrasena de acceso, hazlo desde esta seccion. Usa una contrasena segura de al menos 8 caracteres con letras y numeros.</div>
</div>

<!-- CONTRAPORTADA -->
<div class="backcover">
  {logo_img}
  <h2 style="margin-bottom:16px">Space Cheer</h2>
  <p>Manual de Juez &mdash; Documento de uso interno y confidencial.</p>
  <p style="margin-top:12px;color:#6b7280;font-size:9pt">Para soporte tecnico contacta al administrador del sistema.</p>
  <p style="margin-top:8px;color:#6b7280;font-size:9pt">Junio 2026 &mdash; Version 1.0</p>
</div>

</body></html>"""


def main():
    print("[*] Generando Manual de Juez (cobertura completa)...")
    logo  = logo_uri()
    shots, json_responses = capture()
    html  = build_html(shots, json_responses, logo)

    with sync_playwright() as p:
        browser = p.chromium.launch()
        page    = browser.new_page()
        page.set_content(html, wait_until="networkidle")
        page.pdf(
            path=OUTPUT_PDF,
            format="A4",
            margin={"top": "15mm", "bottom": "15mm", "left": "14mm", "right": "14mm"},
            print_background=True,
        )
        browser.close()

    size = Path(OUTPUT_PDF).stat().st_size
    print(f"[OK] {OUTPUT_PDF}  ({size // 1024} KB,  {len(shots)} capturas)")


if __name__ == "__main__":
    main()
