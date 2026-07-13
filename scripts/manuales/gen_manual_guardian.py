"""
Generador de Manual de Acompañante / Guardian — Space Cheer
Cobertura completa: 11 URLs, 6 secciones
"""
import base64
import sys
from pathlib import Path
from playwright.sync_api import sync_playwright

sys.path.insert(0, str(Path(__file__).parent))
from highlight_utils import capture_with_button

LOGO_PATH  = Path("C:/Users/Lenovo/Documents/SPACE-CHEER/space_cheer/static/IMAGES/Logo_sin_fondo_blanco.png")
BASE_URL   = "http://127.0.0.1:8000"
OUTPUT_PDF = "C:/Users/Lenovo/Documents/SPACE-CHEER/manual_acompanante.pdf"
USERNAME   = "guardian_test"
PASSWORD   = "Test1234!"
SCREENSHOTS_DIR = Path("C:/Users/Lenovo/Documents/SPACE-CHEER/manual_acompanante_screenshots")

# (url_path, filename, from_path, link_text_hint) — from_path/hint = None si no
# hay una forma natural de llegar por clic (ej. pantallas de entrada).
PAGES = [
    ("/",                                 "home",               None,               None),
    ("/guardian/dashboard/",              "guardian_dashboard", "/",                "Dashboard"),
    ("/orders/",                          "pedidos",            "/",                "Pedidos"),
    ("/orders/cart/",                     "carrito",            "/orders/",         "Carrito"),
    ("/products/catalog/",                "catalogo",           "/orders/",         "Catálogo"),
    ("/events/",                          "eventos",            "/",                "Competencias"),
    ("/events/8/",                        "evento_grandprix",   "/events/",         "Grand Prix"),
    ("/hospitality/event/8/my-stay/",     "mi_estancia",        "/events/8/",       "Hospitalidad"),
    ("/hospitality/event/8/preferences/", "preferencias",       "/hospitality/event/8/my-stay/", "Preferencias"),
    ("/accounts/profile/edit/",           "perfil_editar",      "/",                "Perfil"),
    ("/accounts/profile/settings/",       "perfil_config",      "/accounts/profile/edit/", "Configuración"),
]


def logo_uri():
    if LOGO_PATH.exists():
        return f"data:image/png;base64,{base64.b64encode(LOGO_PATH.read_bytes()).decode()}"
    return ""


def capture():
    shots = {}
    with sync_playwright() as p:
        browser = p.chromium.launch()
        ctx  = browser.new_context(viewport={"width": 1280, "height": 800})
        page = ctx.new_page()

        # --- Login ---
        page.goto(f"{BASE_URL}/accounts/login/")
        page.wait_for_load_state("domcontentloaded")
        shots["login_page"] = base64.b64encode(page.screenshot(full_page=True)).decode()

        page.fill("input[name='login']", USERNAME)
        page.fill("input[name='password']", PASSWORD)
        page.click("button[type='submit']")

        # Wait for navigation away from login page (up to 10s)
        try:
            page.wait_for_url(lambda url: "/accounts/login" not in url, timeout=10000)
        except Exception:
            pass
        page.wait_for_load_state("domcontentloaded")
        page.wait_for_timeout(500)

        final_login_url = page.url
        print(f"  Login -> {final_login_url}")
        shots["login_ok"] = base64.b64encode(page.screenshot(full_page=True)).decode()

        # Verify session is alive
        if "/accounts/login" in final_login_url:
            print("  !! Login failed — check credentials or server")

        # --- Capture pages ---
        REDIRECT_BLOCKERS = ("/accounts/login", "/accounts/profile", "/accounts/curp")
        SCREENSHOTS_DIR.mkdir(parents=True, exist_ok=True)
        for path, key, from_path, link_hint in PAGES:
            result = capture_with_button(
                page, BASE_URL, SCREENSHOTS_DIR,
                from_path=from_path, to_path=path, filename=key,
                link_text_hint=link_hint, wait_ms=300,
            )
            if not result["ok"]:
                print(f"  -- {path} ERROR: {result['path']}")
                continue

            final = page.url.replace(BASE_URL, "")
            if path != "/" and final != path and any(b in final for b in REDIRECT_BLOCKERS):
                print(f"  -- {path} DENIED (→ {final})")
                continue
            title = page.title().lower()
            if any(t in title for t in ("500", "404", "server error", "not found", "page not found")):
                print(f"  -- {path} ERROR ({page.title()})")
                continue

            with open(result["path"], "rb") as f:
                shots[key] = base64.b64encode(f.read()).decode()
            print(f"  OK {path}")

            if result["button_ok"]:
                with open(result["button_path"], "rb") as f:
                    shots[f"{key}_boton"] = base64.b64encode(f.read()).decode()
                print(f"       BOTON OK: {result['button_path']}")
            elif from_path:
                print(f"       BOTON no encontrado (origen: {from_path}, hint: {link_hint})")

        browser.close()
    return shots


def build_html(shots, logo):
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

    logo_img = (
        f'<img src="{logo}" alt="Space Cheer" style="width:180px;margin-bottom:20px;filter:brightness(0) invert(1)">'
        if logo else '<div class="cover-icon">&#x1F46A;</div>'
    )

    return f"""<!DOCTYPE html>
<html lang="es"><head><meta charset="UTF-8">
<title>Manual de Acompañante — Space Cheer</title>
<style>
*,*::before,*::after{{box-sizing:border-box;margin:0;padding:0}}
body{{font-family:system-ui,-apple-system,"Segoe UI",sans-serif;font-size:10.5pt;color:#1a1a2e;background:#fff;line-height:1.6}}
.pb{{page-break-after:always;break-after:page}}
.cover{{background:linear-gradient(160deg,#0d0d1a,#134e1a);color:#fff;min-height:100vh;display:flex;flex-direction:column;align-items:center;justify-content:center;text-align:center;padding:60px 40px}}
.cover h1{{font-size:30pt;font-weight:800;margin-bottom:10px}}
.cover .sub{{font-size:13pt;color:#86efac;margin-bottom:8px}}
.cover .badge{{display:inline-block;background:rgba(34,197,94,.2);border:1px solid #22c55e;color:#86efac;padding:4px 14px;border-radius:20px;font-size:9pt;margin-top:16px}}
.cover .meta{{font-size:9pt;color:#6b7280;margin-top:40px}}
.sec{{padding:44px 52px 32px;max-width:860px;margin:0 auto}}
.sec-hdr{{display:flex;align-items:center;gap:14px;border-left:5px solid #16a34a;padding-left:16px;margin-bottom:24px}}
.sec-hdr .num{{font-size:11pt;font-weight:700;color:#16a34a;min-width:28px}}
.sec-hdr h2{{font-size:17pt;font-weight:700;color:#1a1a2e}}
p{{margin-bottom:12px;color:#374151}}
ul{{margin:0 0 14px 22px;color:#374151}}
ul li{{margin-bottom:6px}}
.ss-wrap{{margin:20px 0;border-radius:8px;overflow:hidden;box-shadow:0 2px 12px rgba(0,0,0,.2)}}
.ss-wrap img{{width:100%;display:block;border-radius:8px}}
.ss-cap{{font-size:8.5pt;color:#6b7280;text-align:center;margin-top:6px;margin-bottom:18px;font-style:italic}}
.no-cap{{color:#9ca3af;font-style:italic;margin:10px 0}}
.info{{background:#f0fdf4;border-left:4px solid #22c55e;border-radius:0 8px 8px 0;padding:14px 18px;margin:18px 0;color:#14532d;font-size:9.5pt}}
.warn{{background:#fefce8;border-left:4px solid #eab308;border-radius:0 8px 8px 0;padding:14px 18px;margin:18px 0;color:#713f12;font-size:9.5pt}}
table{{width:100%;border-collapse:collapse;margin:16px 0;font-size:9.5pt}}
th{{background:#16a34a;color:#fff;padding:8px 12px;text-align:left}}
td{{padding:8px 12px;border-bottom:1px solid #e5e7eb;color:#374151}}
tr:nth-child(even) td{{background:#f0fdf4}}
.backcover{{background:linear-gradient(160deg,#0d0d1a,#134e1a);color:#fff;min-height:100vh;display:flex;flex-direction:column;align-items:center;justify-content:center;text-align:center;padding:60px 40px}}
h3{{font-size:12pt;font-weight:700;color:#1a1a2e;margin:20px 0 8px}}
.button-caption{{color:#b91c1c;font-size:9pt;font-weight:600;margin:14px 0 4px}}
.screenshot-button img{{box-shadow:0 2px 12px rgba(0,0,0,.2),0 0 0 2px #ef4444}}
.use-case{{background:#f0fdf4;border:1px solid #4ade80;border-left:4px solid #16a34a;border-radius:0 8px 8px 0;padding:14px 18px;margin:18px 0}}
.use-case-title{{color:#15803d;font-weight:700;font-size:10.5pt;margin-bottom:8px}}
.use-case ol{{margin:6px 0 0 18px;padding:0}}
.use-case li{{color:#374151;font-size:9.5pt;margin-bottom:4px}}
</style></head><body>

<!-- PORTADA -->
<div class="cover pb">
  {logo_img}
  <h1>Manual de Acompañante</h1>
  <div class="sub">Space Cheer — Custodia y Tutores</div>
  <div class="badge">Version 1.0 · Junio 2026</div>
  <div class="meta">Documento de uso interno.<br>Para soporte contacta al administrador.</div>
</div>

<!-- § 1 ACCESO AL SISTEMA -->
<div class="sec pb">
  <div class="sec-hdr"><span class="num">§ 1</span><h2>Acceso al Sistema</h2></div>
  <p>Como <strong>Acompañante</strong> registrado en Space Cheer, recibes credenciales de acceso del administrador. Ingresa tu usuario y contraseña en la pantalla de inicio de sesión para entrar a la plataforma.</p>
  {ss("login_page", "Pantalla de inicio de sesion — ingresa tus credenciales")}
  <p>Al iniciar sesion llegas a la pantalla de inicio que muestra un resumen de las actividades relacionadas con los atletas a tu cargo.</p>
  {ss("home", "Pantalla de inicio tras iniciar sesion")}
  <div class="info"><strong>Rol Acompañante:</strong> Tu cuenta tiene el rol <em>ACOMPANANTE</em>. Este rol te permite ver y gestionar informacion de los atletas menores de edad que tienes a cargo. No tienes acceso a funciones de administracion de equipo ni de pagos.</div>
  <table>
    <tr><th>Datos de acceso</th><th>Descripcion</th></tr>
    <tr><td>URL del sistema</td><td>http://127.0.0.1:8000 (dev) / spacecheer.com (produccion)</td></tr>
    <tr><td>Usuario</td><td>Proporcionado por el administrador</td></tr>
    <tr><td>Contrasena</td><td>Proporcionada por el administrador (cambiar al primer uso)</td></tr>
    <tr><td>Recuperacion</td><td>Usa "Olvide mi contrasena" en la pantalla de login</td></tr>
  </table>
</div>

<!-- § 2 DASHBOARD DE ACOMPAÑANTE -->
<div class="sec pb">
  <div class="sec-hdr"><span class="num">§ 2</span><h2>Dashboard de Acompañante</h2></div>
  <p>El <strong>Dashboard de Acompañante</strong> es tu pantalla central de supervision. Desde aqui puedes ver todos los atletas menores que tienes a cargo, su estado de inscripcion, equipo asignado y cualquier accion pendiente.</p>
  {ssb("guardian_dashboard", "Dashboard principal del acompañante — lista de atletas a cargo")}
  <h3>Responsabilidades del Acompañante</h3>
  <ul>
    <li>Supervisar la informacion de registro de cada atleta menor de edad.</li>
    <li>Gestionar los pedidos de uniforme y equipamiento para los atletas a cargo.</li>
    <li>Confirmar asistencia a eventos y competencias.</li>
    <li>Mantener datos de contacto actualizados para emergencias.</li>
    <li>Coordinar con el HeadCoach cualquier cambio en las medidas o preferencias del atleta.</li>
  </ul>
  <h3>Roles y permisos</h3>
  <table>
    <tr><th>Funcion</th><th>Acompañante</th><th>HeadCoach</th></tr>
    <tr><td>Ver atletas a cargo</td><td>Si</td><td>Si (todos)</td></tr>
    <tr><td>Crear pedidos para el menor</td><td>Si</td><td>Si</td></tr>
    <tr><td>Aprobar diseño del pedido</td><td>No</td><td>Si</td></tr>
    <tr><td>Gestionar equipos</td><td>No</td><td>Si</td></tr>
    <tr><td>Administrar usuarios</td><td>No</td><td>No (solo Admin)</td></tr>
    <tr><td>Ver hospitalidad del evento</td><td>Si (propia)</td><td>Si (todo el equipo)</td></tr>
  </table>
  <div class="info"><strong>Proteccion de datos:</strong> La informacion de los menores esta protegida bajo la Ley General de los Derechos de Ninas, Ninos y Adolescentes (LGDNNA) y la Ley Federal de Proteccion de Datos Personales en Posesion de los Particulares (LFPDPPP). El sistema registra todos los accesos a datos sensibles.</div>
</div>

<!-- § 3 GESTIÓN DE PEDIDOS PARA EL MENOR -->
<div class="sec pb">
  <div class="sec-hdr"><span class="num">§ 3</span><h2>Gestion de Pedidos para el Menor</h2></div>
  <p>Como acompañante puedes crear y hacer seguimiento de pedidos de uniforme y equipamiento para los atletas a tu cargo. El proceso sigue un flujo de estados definido que garantiza la supervision del HeadCoach.</p>
  <h3>Lista de pedidos</h3>
  <p>En <strong>Pedidos</strong> encontraras todos los pedidos asociados a los atletas que supervisas, con su estado actual.</p>
  {ssb("pedidos", "Lista de pedidos — muestra estado y detalles de cada orden")}
  <h3>Estados de un pedido</h3>
  <table>
    <tr><th>Estado</th><th>Descripcion</th><th>Quien actua</th></tr>
    <tr><td>BORRADOR</td><td>Pedido en construccion, aun editable</td><td>Acompañante / HeadCoach</td></tr>
    <tr><td>PENDIENTE</td><td>Enviado al HeadCoach para revision</td><td>HeadCoach</td></tr>
    <tr><td>DISEÑO APROBADO</td><td>Diseño confirmado, medidas bloqueadas</td><td>HeadCoach</td></tr>
    <tr><td>EN PRODUCCION</td><td>Fabricacion en curso</td><td>Admin</td></tr>
    <tr><td>ENTREGADO</td><td>Uniforme entregado</td><td>Admin</td></tr>
    <tr><td>CANCELADO</td><td>Pedido cancelado</td><td>HeadCoach / Admin</td></tr>
  </table>
  <h3>Carrito de compras</h3>
  <p>Usa el <strong>Carrito</strong> para agregar productos del catalogo antes de confirmar un pedido.</p>
  {ssb("carrito", "Carrito de compras — agrega productos para el atleta")}
  <h3>Catalogo de productos</h3>
  <p>El <strong>Catalogo</strong> muestra todos los productos disponibles para el atleta: uniformes, accesorios y equipamiento aprobado por el equipo.</p>
  {ssb("catalogo", "Catalogo de productos disponibles")}
  <div class="info"><strong>Medidas:</strong> Algunos productos requieren medidas corporales del atleta. El sistema te solicitara ingresarlas durante el proceso de pedido. Una vez que el HeadCoach aprueba el diseño, las medidas quedan bloqueadas y no pueden modificarse.</div>
  <div class="warn"><strong>Atencion:</strong> Solo puedes crear pedidos para atletas que esten bajo tu custodia registrada. Si necesitas realizar un pedido para otro menor, contacta al administrador.</div>
  <div class="use-case">
    <div class="use-case-title">Caso de uso &mdash; Crear un pedido de uniforme para mi atleta</div>
    <ol>
      <li>Entra a <strong>Catalogo</strong> y elige el producto (uniforme o accesorio) que necesita el atleta.</li>
      <li>Agrega el producto al <strong>Carrito</strong>, ingresando las medidas si el producto las requiere.</li>
      <li>Confirma el pedido desde el carrito. El pedido queda en estado BORRADOR.</li>
      <li>Revisa en <strong>Pedidos</strong> el avance: el HeadCoach debe enviarlo a revision y aprobar el diseño antes de producción.</li>
    </ol>
  </div>
</div>

<!-- § 4 COMPETENCIAS Y EVENTOS -->
<div class="sec pb">
  <div class="sec-hdr"><span class="num">§ 4</span><h2>Competencias y Eventos</h2></div>
  <p>La seccion <strong>Eventos</strong> muestra todas las competencias programadas en las que participan los atletas de tu equipo. Puedes consultar fechas, ubicaciones, categorias y requisitos de participacion.</p>
  {ssb("eventos", "Lista de competencias y eventos programados")}
  <h3>Detalle de evento — Grand Prix Espacial</h3>
  <p>Cada evento tiene una pagina de detalle con informacion completa sobre la competencia, incluyendo sede, categorias participantes, itinerario y requerimientos especiales.</p>
  {ssb("evento_grandprix", "Detalle del evento Grand Prix Espacial (evento pk=8)")}
  <table>
    <tr><th>Dato</th><th>Descripcion</th></tr>
    <tr><td>Nombre</td><td>Grand Prix Espacial</td></tr>
    <tr><td>Identificador</td><td>Evento #8</td></tr>
    <tr><td>Acceso</td><td>/events/8/</td></tr>
    <tr><td>Hospitalidad</td><td>Disponible — ver seccion § 5</td></tr>
  </table>
  <div class="info"><strong>Notificaciones:</strong> El sistema envia correos electronicos cuando hay cambios importantes en el estado de un evento o cuando el HeadCoach actualiza informacion relevante para los acompañantes.</div>
</div>

<!-- § 5 HOSPITALIDAD — MI ESTANCIA -->
<div class="sec pb">
  <div class="sec-hdr"><span class="num">§ 5</span><h2>Hospitalidad — Mi Estancia</h2></div>
  <p>La seccion <strong>Hospitalidad</strong> te permite gestionar tu alojamiento durante el evento. Como acompañante registrado en el Grand Prix Espacial (evento #8, estancia pk=4), tienes acceso directo a tu reservacion.</p>
  <h3>Mi reservacion</h3>
  <p>En <strong>Mi Estancia</strong> puedes ver el detalle de tu reservacion: tipo de habitacion, fechas, servicios incluidos y estado de la confirmacion.</p>
  {ssb("mi_estancia", "Mi estancia — detalle de reservacion en el Grand Prix Espacial")}
  <h3>Preferencias de hospedaje</h3>
  <p>Puedes indicar tus preferencias de hospedaje: tipo de cama, planta del hotel, requerimientos especiales de accesibilidad, dieta, u otras necesidades.</p>
  {ssb("preferencias", "Formulario de preferencias de hospedaje")}
  <table>
    <tr><th>Opcion</th><th>Descripcion</th></tr>
    <tr><td>Tipo de habitacion</td><td>Individual / Doble / Suite</td></tr>
    <tr><td>Planta</td><td>Baja / Alta (segun disponibilidad)</td></tr>
    <tr><td>Dieta especial</td><td>Vegetariano, sin gluten, alergias</td></tr>
    <tr><td>Accesibilidad</td><td>Habitacion adaptada si se requiere</td></tr>
    <tr><td>Llegada / Salida</td><td>Horarios estimados de check-in y check-out</td></tr>
  </table>
  <div class="info"><strong>Plazo de preferencias:</strong> Ingresa tus preferencias con al menos 7 dias de anticipacion al evento para que el HeadCoach pueda gestionar la asignacion de habitaciones con el hotel sede.</div>
  <div class="warn"><strong>Nota:</strong> Las reservaciones de habitaciones son gestionadas y confirmadas por el HeadCoach. Tus preferencias son una solicitud, no una garantia de disponibilidad.</div>
  <div class="use-case">
    <div class="use-case-title">Caso de uso &mdash; Registrar mis preferencias de hospedaje antes de un evento</div>
    <ol>
      <li>Entra al detalle del evento y luego a <strong>Mi Estancia</strong> para confirmar que tienes reservacion asignada.</li>
      <li>Entra a <strong>Preferencias</strong> y llena el formulario: tipo de habitacion, dieta especial, accesibilidad, etc.</li>
      <li>Guarda tus preferencias con al menos 7 dias de anticipacion al evento.</li>
      <li>Si necesitas un cambio despues de guardarlas, contacta directamente al HeadCoach.</li>
    </ol>
  </div>
</div>

<!-- § 6 MI PERFIL -->
<div class="sec pb">
  <div class="sec-hdr"><span class="num">§ 6</span><h2>Mi Perfil</h2></div>
  <p>Mantener tu informacion personal actualizada es fundamental para el correcto funcionamiento de la custodia en la plataforma. Los datos del acompañante son necesarios para los registros oficiales de los atletas en competencias.</p>
  <h3>Editar perfil</h3>
  <p>En <strong>Editar Perfil</strong> puedes actualizar tu nombre, foto, datos de contacto (telefono, correo alternativo) y domicilio.</p>
  {ssb("perfil_editar", "Formulario de edicion de perfil del acompañante")}
  <h3>Configuracion de cuenta</h3>
  <p>La <strong>Configuracion</strong> te permite gestionar tu contrasena, preferencias de notificaciones y opciones de privacidad.</p>
  {ssb("perfil_config", "Configuracion de cuenta — contrasena y notificaciones")}
  <h3>Datos recomendados mantener actualizados</h3>
  <table>
    <tr><th>Campo</th><th>Importancia</th></tr>
    <tr><td>Telefono movil</td><td>Contacto de emergencia durante competencias</td></tr>
    <tr><td>Correo electronico</td><td>Recepcion de notificaciones y documentos</td></tr>
    <tr><td>Documento de identidad</td><td>Requerido para acreditacion en eventos</td></tr>
    <tr><td>CURP</td><td>Obligatorio para registro de custodia oficial</td></tr>
    <tr><td>Domicilio</td><td>Requerido en documentos de custodia</td></tr>
  </table>
  <div class="warn"><strong>Importante:</strong> Si cambias tu correo o telefono, notifica de inmediato al HeadCoach para que actualice los registros de custodia correspondientes ante las autoridades de la competencia.</div>
  <div class="info"><strong>Seguridad:</strong> Cambia tu contrasena periodicamente. Nunca compartas tus credenciales con terceros. Si sospechas que tu cuenta fue comprometida, contacta al administrador de inmediato.</div>
</div>

<!-- CONTRAPORTADA -->
<div class="backcover">
  {logo_img}
  <h2 style="margin-bottom:16px">Space Cheer</h2>
  <p style="color:#86efac;margin-bottom:8px">Manual de Acompañante — Version 1.0 · Junio 2026</p>
  <p style="color:#6b7280;font-size:9pt">Este manual es de uso interno y confidencial.<br>Para soporte contacta al administrador del sistema.</p>
</div>

</body></html>"""


def main():
    print("[*] Generando Manual de Acompañante / Guardian...")
    logo  = logo_uri()
    shots = capture()
    print(f"[*] Capturas obtenidas: {len(shots)}")
    html  = build_html(shots, logo)

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
