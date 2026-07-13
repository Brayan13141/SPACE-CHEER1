"""
Generador de Manual de Atleta — Space Cheer
Cobertura completa ATLETA: 13 URLs + login
"""
import base64
import sys
from pathlib import Path
from playwright.sync_api import sync_playwright

# Importar helper compartido
sys.path.insert(0, str(Path(__file__).parent))
from highlight_utils import capture_with_button

LOGO_PATH = Path("C:/Users/Lenovo/Documents/SPACE-CHEER/space_cheer/static/IMAGES/Logo_sin_fondo_blanco.png")
BASE_URL   = "http://127.0.0.1:8000"
OUTPUT_PDF = "C:/Users/Lenovo/Documents/SPACE-CHEER/manual_atleta.pdf"
USERNAME   = "atleta_test"
PASSWORD   = "Test1234!"

PAGES = [
    ("/",                                  "home",             None, None),
    ("/teams/my-team/",                    "mi_equipo",        "/", "Mi Equipo"),
    ("/teams/join/",                       "unirse_equipo",    "/teams/my-team/", "Unirse"),
    ("/orders/",                           "mis_pedidos",      "/", "Mis Pedidos"),
    ("/orders/cart/",                      "carrito",          "/orders/", "Carrito"),
    ("/products/catalog/",                 "catalogo",         "/orders/", "Catálogo"),
    ("/orders/23/",                        "pedido_draft",     "/orders/", "23"),
    ("/events/",                           "eventos",          "/", "Eventos"),
    ("/events/8/",                         "evento_grandprix", "/events/", "Grand Prix"),
    ("/hospitality/event/8/my-stay/",      "mi_estancia",      "/events/8/", "Mi Estancia"),
    ("/hospitality/event/8/preferences/",  "preferencias",     "/hospitality/event/8/my-stay/", "Preferencias"),
    ("/accounts/profile/edit/",            "perfil_editar",    "/", "Perfil"),
    ("/accounts/profile/settings/",        "perfil_config",    "/accounts/profile/edit/", "Configuración"),
]


def logo_uri():
    if LOGO_PATH.exists():
        return f"data:image/png;base64,{base64.b64encode(LOGO_PATH.read_bytes()).decode()}"
    return ""


SCREENSHOTS_DIR = Path("C:/Users/Lenovo/Documents/SPACE-CHEER/manual_atleta_screenshots")
SCREENSHOTS_DIR.mkdir(parents=True, exist_ok=True)


def img_to_base64(path):
    """Convierte imagen a data URI base64."""
    with open(path, "rb") as f:
        data = base64.b64encode(f.read()).decode("utf-8")
    return f"data:image/png;base64,{data}"


def capture():
    shots = {}
    with sync_playwright() as p:
        browser = p.chromium.launch()
        ctx = browser.new_context(viewport={"width": 1280, "height": 800})
        page = ctx.new_page()

        # Captura pre-login
        page.goto(f"{BASE_URL}/accounts/login/", wait_until="load")
        shots["login_form"] = base64.b64encode(page.screenshot(full_page=True)).decode()
        print("  OK /accounts/login/ (pre-login)")

        # Login
        page.fill("input[name='login']", USERNAME)
        page.fill("input[name='password']", PASSWORD)
        page.click("button[type='submit']")
        try:
            page.wait_for_url(lambda url: "login" not in url, timeout=15000)
        except Exception:
            page.wait_for_timeout(3000)
        shots["login_ok"] = base64.b64encode(page.screenshot(full_page=True)).decode()
        print("  OK login -> post-login redirect")

        for path, key, from_path, link_hint in PAGES:
            try:
                result = capture_with_button(
                    page, BASE_URL, SCREENSHOTS_DIR,
                    from_path=from_path, to_path=path,
                    filename=key, link_text_hint=link_hint,
                    wait_ms=1000
                )
                if result["ok"]:
                    shots[key] = img_to_base64(result["path"])
                    print(f"  OK {path}")
                else:
                    print(f"  -- {path} ERROR: {result['path']}")
                    continue

                if result["button_ok"]:
                    shots[f"{key}_boton"] = img_to_base64(result["button_path"])
                    print(f"       BOTON OK: {result['button_path']}")
                elif from_path:
                    print(f"       BOTON no encontrado (origen: {from_path}, hint: {link_hint})")
            except Exception as e:
                print(f"  !! {path} ERROR: {e}")

        browser.close()
    return shots


def build_html(shots, logo):
    def ss(key, cap=""):
        if key not in shots:
            return f'<p class="no-cap">[Sin captura disponible: {key}]</p>'
        return (
            f'<div class="ss-wrap"><img src="data:image/png;base64,{shots[key]}" alt="{key}"></div>'
            + (f'<p class="ss-cap">{cap}</p>' if cap else "")
        )

    def ssb(key, cap=""):
        """Como ss(), pero antepone la captura con el botón resaltado (si existe)."""
        button_html = ""
        button_key = f"{key}_boton"
        if button_key in shots:
            button_html = (
                '<p class="button-caption">&#128073; Así se llega a esta pantalla &mdash; '
                'el botón resaltado en rojo:</p>'
                f'<div class="ss-wrap screenshot-button"><img src="data:image/png;base64,{shots[button_key]}" alt="Botón hacia {key}"></div>'
            )
        return button_html + ss(key, cap)

    logo_img = (
        f'<img src="{logo}" alt="Space Cheer" style="width:180px;margin-bottom:20px;filter:brightness(0) invert(1)">'
        if logo else '<div class="cover-icon">⭐</div>'
    )

    return f"""<!DOCTYPE html>
<html lang="es"><head><meta charset="UTF-8">
<title>Manual de Atleta — Space Cheer</title>
<style>
*,*::before,*::after{{box-sizing:border-box;margin:0;padding:0}}
body{{font-family:system-ui,-apple-system,"Segoe UI",sans-serif;font-size:10.5pt;color:#1a1a2e;background:#fff;line-height:1.6}}
.pb{{page-break-after:always;break-after:page}}
.cover{{background:linear-gradient(160deg,#0d0d1a,#0a1f3d);color:#fff;min-height:100vh;display:flex;flex-direction:column;align-items:center;justify-content:center;text-align:center;padding:60px 40px}}
.cover h1{{font-size:30pt;font-weight:800;margin-bottom:10px}}
.cover .sub{{font-size:13pt;color:#60a5fa;margin-bottom:8px}}
.cover .badge{{display:inline-block;background:rgba(37,99,235,.25);border:1px solid #3b82f6;color:#93c5fd;padding:4px 14px;border-radius:20px;font-size:9pt;margin-top:16px}}
.cover .meta{{font-size:9pt;color:#6b7280;margin-top:40px}}
.sec{{padding:44px 52px 32px;max-width:860px;margin:0 auto}}
.sec-hdr{{display:flex;align-items:center;gap:14px;border-left:5px solid #2563eb;padding-left:16px;margin-bottom:20px}}
.sec-hdr .num{{font-size:11pt;font-weight:700;color:#2563eb;min-width:28px}}
.sec-hdr h2{{font-size:17pt;font-weight:700;color:#1a1a2e}}
p{{margin-bottom:12px;color:#374151}}
.ss-wrap{{margin:20px 0;border-radius:8px;overflow:hidden;box-shadow:0 2px 12px rgba(0,0,0,.2)}}
.ss-wrap img{{width:100%;display:block;border-radius:8px}}
.ss-cap{{font-size:8.5pt;color:#6b7280;text-align:center;margin-top:6px;margin-bottom:18px;font-style:italic}}
.no-cap{{color:#9ca3af;font-style:italic;margin:10px 0}}
.info{{background:#eff6ff;border-left:4px solid #3b82f6;border-radius:0 8px 8px 0;padding:14px 18px;margin:18px 0;color:#1e40af;font-size:9.5pt}}
.warn{{background:#fffbeb;border-left:4px solid #f59e0b;border-radius:0 8px 8px 0;padding:14px 18px;margin:18px 0;color:#92400e;font-size:9.5pt}}
.button-caption{{color:#b91c1c;font-size:9pt;font-weight:600;margin:14px 0 4px}}
.screenshot-button img{{box-shadow:0 2px 12px rgba(0,0,0,.2),0 0 0 2px #ef4444}}
.use-case{{background:#f5f3ff;border:1px solid #a78bfa;border-left:4px solid #7c3aed;border-radius:0 8px 8px 0;padding:14px 18px;margin:18px 0}}
.use-case-title{{color:#6d28d9;font-weight:700;font-size:10.5pt;margin-bottom:8px}}
.use-case ol{{margin:6px 0 0 18px;padding:0}}
.use-case li{{color:#374151;font-size:9.5pt;margin-bottom:4px}}
table{{width:100%;border-collapse:collapse;margin:16px 0;font-size:9.5pt}}
th{{background:#2563eb;color:#fff;padding:8px 12px;text-align:left}}
td{{padding:8px 12px;border-bottom:1px solid #e5e7eb;color:#374151}}
tr:nth-child(even) td{{background:#f0f7ff}}
ol.steps{{list-style:none;counter-reset:s;padding:0;margin:18px 0}}
ol.steps li{{counter-increment:s;display:flex;align-items:flex-start;gap:12px;margin-bottom:14px;padding:12px 16px;background:#f0f7ff;border-radius:8px;border:1px solid #dbeafe}}
ol.steps li::before{{content:counter(s);background:#2563eb;color:#fff;border-radius:50%;min-width:24px;height:24px;display:flex;align-items:center;justify-content:center;font-size:9pt;font-weight:700;flex-shrink:0}}
ol.steps li strong{{display:block;margin-bottom:2px;color:#1a1a2e}}
ol.steps li span{{color:#4b5563;font-size:9.5pt}}
.backcover{{background:linear-gradient(160deg,#0d0d1a,#0a1f3d);color:#fff;min-height:100vh;display:flex;flex-direction:column;align-items:center;justify-content:center;text-align:center;padding:60px 40px}}
.backcover p{{color:#9ca3af}}
</style></head><body>

<!-- PORTADA -->
<div class="cover pb">
  {logo_img}
  <h1>Manual de Atleta</h1>
  <div class="sub">Space Cheer — Plataforma de Competencias</div>
  <div class="badge">Versión 1.0 · Junio 2026</div>
  <div class="meta">Documento de uso interno.<br>Para soporte contacta a tu HeadCoach.</div>
</div>

<!-- § 1 ACCESO AL SISTEMA -->
<div class="sec pb">
  <div class="sec-hdr"><span class="num">§ 1</span><h2>Acceso al Sistema</h2></div>
  <p>Para ingresar a Space Cheer escribe la dirección de la plataforma en tu navegador. Verás la pantalla de inicio de sesión donde debes ingresar tu usuario y contraseña proporcionados por tu HeadCoach. Haz clic en <strong>Iniciar Sesión</strong> para entrar.</p>
  <p>Si es tu primera vez ingresando, es posible que el sistema te pida completar tu perfil antes de acceder a todas las funciones.</p>
  {ss("login_form", "Pantalla de inicio de sesión — ingresa tu usuario y contraseña")}
  {ss("login_ok", "Pantalla post-login — el sistema confirma el acceso exitoso")}
  <div class="info"><strong>Tip:</strong> Si olvidaste tu contraseña, comunícate con tu HeadCoach para que la restablezca desde el panel de administración.</div>
</div>

<!-- § 2 HOME / DASHBOARD -->
<div class="sec pb">
  <div class="sec-hdr"><span class="num">§ 2</span><h2>Home / Dashboard</h2></div>
  <p>Después de iniciar sesión verás el <strong>Panel Principal</strong> (Dashboard). Desde aquí tienes acceso rápido a todas las secciones de la plataforma: tu equipo, tus pedidos, los eventos y tu perfil.</p>
  <p>El panel también muestra notificaciones importantes como fechas límite de pedidos, eventos próximos y mensajes de tu coach. Revísalo cada vez que ingreses a la plataforma.</p>
  {ss("home", "Dashboard principal del atleta")}
</div>

<!-- § 3 MI EQUIPO -->
<div class="sec pb">
  <div class="sec-hdr"><span class="num">§ 3</span><h2>Mi Equipo</h2></div>
  <p>En la sección <strong>Mi Equipo</strong> puedes ver la información del equipo al que perteneces: nombre, categoría, integrantes y el coach responsable. Es el espacio central de convivencia de tu equipo dentro de la plataforma.</p>
  <p>Si aún no perteneces a ningún equipo, el sistema te mostrará la opción de unirte mediante un código de invitación que te proporciona tu HeadCoach o coach.</p>
  {ssb("mi_equipo", "Vista de Mi Equipo — información del equipo y sus integrantes")}
  {ssb("unirse_equipo", "Pantalla Unirse a un equipo — ingresa el código de invitación")}
  <div class="use-case">
    <div class="use-case-title">Caso de uso &mdash; Unirme a un equipo con un código de invitación</div>
    <ol>
      <li>Pide a tu HeadCoach o coach el código de invitación de tu equipo.</li>
      <li>Desde el Dashboard, entra a <strong>Mi Equipo</strong>.</li>
      <li>Si aún no perteneces a ningún equipo, verás el botón para <strong>Unirse a un equipo</strong>.</li>
      <li>Ingresa el código y confirma. Tu equipo aparecerá de inmediato en Mi Equipo.</li>
    </ol>
  </div>
</div>

<!-- § 4 PEDIDOS Y TIENDA -->
<div class="sec pb">
  <div class="sec-hdr"><span class="num">§ 4</span><h2>Pedidos y Tienda</h2></div>
  <p>En <strong>Mis Pedidos</strong> puedes consultar el estado actual de tu pedido de uniforme y accesorios. Cada pedido muestra su estado actual, la fecha de creación y los artículos incluidos.</p>
  <p>El <strong>Carrito</strong> muestra los artículos seleccionados antes de confirmar el pedido. El <strong>Catálogo</strong> te permite explorar todos los productos disponibles para tu equipo.</p>
  {ssb("mis_pedidos", "Lista de mis pedidos y su estado actual")}
  {ssb("carrito", "Carrito de compras — artículos pendientes de confirmar")}
  {ssb("catalogo", "Catálogo de productos — uniformes y accesorios disponibles")}
  {ssb("pedido_draft", "Detalle de pedido en estado Borrador (pk=23)")}
  <table>
    <tr><th>Estado</th><th>Significado</th></tr>
    <tr><td>Borrador</td><td>El pedido aún no ha sido enviado para revisión.</td></tr>
    <tr><td>Pendiente</td><td>En espera de aprobación del diseño por parte del coach.</td></tr>
    <tr><td>Diseño aprobado</td><td>El diseño fue aceptado; pronto entrará a producción.</td></tr>
    <tr><td>En producción</td><td>Tu uniforme está siendo elaborado.</td></tr>
    <tr><td>Entregado</td><td>El pedido fue entregado al equipo.</td></tr>
    <tr><td>Cancelado</td><td>El pedido fue cancelado.</td></tr>
  </table>
  <div class="warn"><strong>Nota:</strong> Los pedidos son gestionados por tu coach. Si detectas un error en tus medidas o artículos, notifícalo antes de que el pedido pase a producción.</div>
  <div class="use-case">
    <div class="use-case-title">Caso de uso &mdash; Consultar el estado de mi pedido de uniforme</div>
    <ol>
      <li>Desde el Dashboard, entra a <strong>Mis Pedidos</strong>.</li>
      <li>Haz clic en el pedido que quieras revisar para ver su detalle.</li>
      <li>El estado (Borrador, Pendiente, Diseño aprobado, En producción, Entregado) te indica en qué etapa va.</li>
      <li>Si el estado no cambia después de varios días, contacta a tu coach para preguntar por el avance.</li>
    </ol>
  </div>
</div>

<!-- § 5 COMPETENCIAS Y EVENTOS -->
<div class="sec pb">
  <div class="sec-hdr"><span class="num">§ 5</span><h2>Competencias y Eventos</h2></div>
  <p>La sección <strong>Eventos</strong> muestra todas las competencias disponibles en la plataforma. Puedes ver la fecha, el lugar, la categoría y los equipos participantes de cada evento.</p>
  <p>Al entrar al detalle de un evento verás información específica como el reglamento, el horario de presentación de tu equipo y los hoteles disponibles para la hospitalidad.</p>
  {ssb("eventos", "Lista de competencias y eventos disponibles")}
  {ssb("evento_grandprix", "Detalle del evento Grand Prix (evento 8)")}
</div>

<!-- § 6 HOSPITALIDAD — MI ESTANCIA -->
<div class="sec pb">
  <div class="sec-hdr"><span class="num">§ 6</span><h2>Hospitalidad — Mi Estancia</h2></div>
  <p>La sección <strong>Mi Estancia</strong> muestra la información del hospedaje asignado para el evento: hotel, tipo de cuarto, fechas de check-in y check-out, y los compañeros de habitación.</p>
  <p>En <strong>Preferencias</strong> puedes indicar tus preferencias de alojamiento para que el HeadCoach las tome en cuenta al asignar cuartos: preferencias de cama, fumador/no fumador, necesidades especiales, entre otras.</p>
  {ssb("mi_estancia", "Mi Estancia — detalle del hospedaje asignado para el evento")}
  {ssb("preferencias", "Preferencias de hospitalidad — indica tus necesidades de alojamiento")}
  <ol class="steps">
    <li><strong>Consulta el hotel asignado</strong><span>Revisa el nombre del hotel, dirección y fechas de tu estancia para planear tu traslado.</span></li>
    <li><strong>Verifica fechas de check-in / check-out</strong><span>Anota las fechas exactas. Llega puntual al hotel para el registro en recepción.</span></li>
    <li><strong>Registra tus preferencias</strong><span>Si tienes alguna necesidad especial (alergias, cama individual, accesibilidad), ingrésala en la sección de Preferencias.</span></li>
    <li><strong>Contacta a tu HeadCoach</strong><span>Si hay un error en tu hospedaje (fechas, cuarto o compañeros), notifícalo para que lo corrija antes del evento.</span></li>
  </ol>
  <div class="info"><strong>Nota:</strong> Los hospedajes son asignados por el HeadCoach. Si aún no tienes hospedaje asignado, la sección puede aparecer vacía hasta que se confirme la reserva.</div>
</div>

<!-- § 7 MI PERFIL -->
<div class="sec pb">
  <div class="sec-hdr"><span class="num">§ 7</span><h2>Mi Perfil</h2></div>
  <p>Desde <strong>Editar Perfil</strong> puedes actualizar tus datos personales como nombre, foto de perfil, información de contacto y datos de tu tutor/guardián. Es importante mantener esta información actualizada para los registros de competencia.</p>
  <p>En <strong>Configuración de cuenta</strong> puedes cambiar tu contraseña y ajustar las preferencias de notificación y privacidad de tu cuenta.</p>
  {ssb("perfil_editar", "Editar perfil — datos personales y foto")}
  {ssb("perfil_config", "Configuración de cuenta — contraseña y preferencias")}
  <div class="warn"><strong>Datos sensibles:</strong> Tu CURP y medidas corporales son datos protegidos. Solo el HeadCoach y el administrador del sistema pueden acceder a esa información.</div>
</div>

<!-- CONTRAPORTADA -->
<div class="backcover">
  {logo_img}
  <h2 style="font-size:20pt;margin-bottom:12px">Space Cheer</h2>
  <p>Este manual es de uso interno y confidencial.<br>Generado automáticamente · Junio 2026</p>
</div>

</body></html>"""


def main():
    print("[*] Generando Manual de Atleta — cobertura completa...")
    logo  = logo_uri()
    shots = capture()
    html  = build_html(shots, logo)

    with sync_playwright() as p:
        browser = p.chromium.launch()
        page    = browser.new_page()
        page.set_content(html, wait_until="load")
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
