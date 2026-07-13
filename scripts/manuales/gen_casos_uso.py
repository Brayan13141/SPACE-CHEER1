"""
Generador de PDFs de Casos de Uso — Space Cheer (producción)
Narrativos (sin capturas, no requiere servidor). Usa playwright para HTML→PDF.

Genera 5 PDFs en la raíz del repo:
  1. caso_uso_1_pedido_completo.pdf       — Historia completa: de la solicitud al envío
  2. caso_uso_2_headcoach_crear_pedido.pdf — HeadCoach: crear pedido y gestionar medidas
  3. caso_uso_3_atleta_tutor.pdf           — Atleta y tutor: unirse, medirse y dar seguimiento
  4. caso_uso_4_admin_aprobacion.pdf       — Admin: aprobar, producir y entregar
  5. caso_uso_5_operario_etapas.pdf        — Operario: trabajar las etapas de producción

Uso:  python scripts/manuales/gen_casos_uso.py
"""

import base64
from pathlib import Path

from playwright.sync_api import sync_playwright

ROOT = Path("C:/Users/Lenovo/Documents/SPACE-CHEER")
LOGO_PATH = ROOT / "space_cheer/static/IMAGES/Logo_sin_fondo_blanco.png"
SITE = "spacecheer.com"


def logo_data_uri() -> str:
    if LOGO_PATH.exists():
        return "data:image/png;base64," + base64.b64encode(LOGO_PATH.read_bytes()).decode()
    return ""


# ─────────────────────────────────────────────────────────────────────────────
# Estilo compartido (mismo lenguaje visual que los manuales por rol)
# ─────────────────────────────────────────────────────────────────────────────
STYLE = """
*, *::before, *::after { box-sizing: border-box; margin: 0; padding: 0; }
body { font-family: system-ui, -apple-system, "Segoe UI", sans-serif; font-size: 10.5pt;
       color: #1a1a2e; background: #fff; line-height: 1.6; }
.page-break { page-break-after: always; break-after: page; }

/* portada */
.cover { background: linear-gradient(160deg, #0d0d1a 0%, #1a1140 100%); color: #fff;
         min-height: 100vh; display: flex; flex-direction: column; align-items: center;
         justify-content: center; text-align: center; padding: 60px 40px; }
.cover h1 { font-size: 26pt; font-weight: 800; letter-spacing: -0.5px; margin-bottom: 12px; }
.cover .subtitle { font-size: 13pt; color: #a78bfa; margin-bottom: 8px; }
.cover .badge { display: inline-block; background: rgba(127,90,240,.25); color: #c4b5fd;
                border: 1px solid #7f5af0; border-radius: 20px; padding: 6px 18px;
                font-size: 10pt; margin-top: 18px; letter-spacing: .08em; }
.cover .meta { font-size: 9pt; color: #6b7280; margin-top: 48px; }

/* contenido */
.content { padding: 42px 48px; }
h2 { font-size: 15pt; color: #1a1140; border-bottom: 3px solid #7f5af0;
     padding-bottom: 6px; margin: 26px 0 14px; }
h3 { font-size: 12pt; color: #4c1d95; margin: 18px 0 8px; }
p  { margin-bottom: 8px; }
ul, ol { margin: 6px 0 10px 22px; }
li { margin-bottom: 4px; }

/* personas / actores */
.actor { display: inline-block; border-radius: 14px; padding: 2px 12px; font-size: 8.5pt;
         font-weight: 700; letter-spacing: .04em; margin-right: 4px; }
.actor.hc   { background: #ede9fe; color: #6d28d9; border: 1px solid #a78bfa; }
.actor.ath  { background: #e0f2fe; color: #0369a1; border: 1px solid #7dd3fc; }
.actor.gua  { background: #fce7f3; color: #be185d; border: 1px solid #f9a8d4; }
.actor.adm  { background: #fef3c7; color: #92400e; border: 1px solid #fcd34d; }
.actor.ope  { background: #dcfce7; color: #166534; border: 1px solid #86efac; }
.actor.sys  { background: #f1f5f9; color: #334155; border: 1px solid #cbd5e1; }

/* tarjeta de escenario */
.scenario { background: #f5f3ff; border: 1px solid #ddd6fe; border-left: 5px solid #7f5af0;
            border-radius: 8px; padding: 14px 18px; margin: 14px 0; }
.scenario .t { font-weight: 800; color: #4c1d95; margin-bottom: 6px; }

/* pasos */
.step { display: flex; gap: 14px; margin: 12px 0; page-break-inside: avoid; }
.step .n { flex: 0 0 34px; height: 34px; border-radius: 50%; font-weight: 800; color: #fff;
           background: linear-gradient(135deg, #7f5af0, #2cb1ff); display: flex;
           align-items: center; justify-content: center; font-size: 12pt; }
.step .b { flex: 1; }
.step .b .t { font-weight: 700; color: #1a1140; }
.step .b .screen { font-size: 8.5pt; color: #6d28d9; background: #f5f3ff;
                   border: 1px solid #ddd6fe; border-radius: 5px; padding: 1px 8px;
                   display: inline-block; margin: 2px 0 4px; }

/* flujo de estados */
.flow { display: flex; flex-wrap: wrap; align-items: center; gap: 6px; margin: 12px 0;
        page-break-inside: avoid; }
.flow .st { border-radius: 8px; padding: 6px 12px; font-size: 9pt; font-weight: 700;
            border: 2px solid; }
.flow .st.draft { background: #f8fafc; color: #475569; border-color: #cbd5e1; }
.flow .st.pend  { background: #fefce8; color: #a16207; border-color: #fde047; }
.flow .st.appr  { background: #eff6ff; color: #1d4ed8; border-color: #93c5fd; }
.flow .st.prod  { background: #f5f3ff; color: #6d28d9; border-color: #c4b5fd; }
.flow .st.done  { background: #f0fdf4; color: #15803d; border-color: #86efac; }
.flow .arr { color: #94a3b8; font-weight: 800; }

/* tablas */
table { width: 100%; border-collapse: collapse; margin: 10px 0; font-size: 9.5pt;
        page-break-inside: avoid; }
th { background: #1a1140; color: #fff; text-align: left; padding: 7px 10px; }
td { border: 1px solid #e2e8f0; padding: 6px 10px; vertical-align: top; }
tr:nth-child(even) td { background: #fafaff; }

/* cajas */
.tip  { background: #ecfeff; border-left: 4px solid #06b6d4; border-radius: 6px;
        padding: 10px 14px; margin: 10px 0; font-size: 9.5pt; page-break-inside: avoid; }
.warn { background: #fff7ed; border-left: 4px solid #f97316; border-radius: 6px;
        padding: 10px 14px; margin: 10px 0; font-size: 9.5pt; page-break-inside: avoid; }
.gold { background: #fefce8; border: 1px solid #fde047; border-radius: 8px;
        padding: 12px 16px; margin: 12px 0; page-break-inside: avoid; }
.gold .t { font-weight: 800; color: #a16207; }

.footer { margin-top: 30px; padding-top: 10px; border-top: 1px solid #e2e8f0;
          font-size: 8pt; color: #94a3b8; text-align: center; }
"""


def doc(title: str, body: str) -> str:
    return (
        '<!DOCTYPE html><html lang="es"><head><meta charset="UTF-8">'
        f"<title>{title}</title><style>{STYLE}</style></head><body>{body}</body></html>"
    )


def cover(title: str, subtitle: str, badge: str) -> str:
    uri = logo_data_uri()
    logo = (
        f'<img src="{uri}" alt="Space Cheer" style="width:170px;margin-bottom:24px;'
        f'filter:brightness(0) invert(1)">'
        if uri else "<div style='font-size:64px'>&#128640;</div>"
    )
    return f"""
<div class="cover">
  {logo}
  <h1>{title}</h1>
  <div class="subtitle">{subtitle}</div>
  <span class="badge">{badge}</span>
  <div class="meta">Caso de uso &middot; {SITE} &middot; Documento para usuarios en producci&oacute;n</div>
</div>
<div class="page-break"></div>
"""


def step(n: int, title: str, screen: str, body: str) -> str:
    scr = f'<span class="screen">&#128204; {screen}</span><br>' if screen else ""
    return f"""
<div class="step"><div class="n">{n}</div><div class="b">
  <span class="t">{title}</span><br>{scr}{body}
</div></div>"""


FLOW_ORDER = """
<div class="flow">
  <span class="st draft">Borrador</span><span class="arr">&rarr;</span>
  <span class="st pend">Pendiente</span><span class="arr">&rarr;</span>
  <span class="st appr">Dise&ntilde;o aprobado</span><span class="arr">&rarr;</span>
  <span class="st prod">En producci&oacute;n</span><span class="arr">&rarr;</span>
  <span class="st done">Entregado</span>
</div>"""

ETAPAS_TABLE = """
<table>
  <tr><th>#</th><th>Etapa</th><th>Qu&eacute; pasa aqu&iacute;</th></tr>
  <tr><td>1</td><td>Planeaci&oacute;n de materiales</td><td>Se define qu&eacute; telas e insumos requiere el pedido.</td></tr>
  <tr><td>2</td><td>Control / surtido de materiales</td><td>Se surten y verifican los materiales planeados.</td></tr>
  <tr><td>3</td><td>Selecci&oacute;n de tallas</td><td>Se preparan tallas y medidas de cada prenda.</td></tr>
  <tr><td>4</td><td>Corte</td><td>Se cortan las piezas de cada prenda.</td></tr>
  <tr><td>5</td><td>Sublimaci&oacute;n</td><td>Se imprimen los dise&ntilde;os sobre la tela.</td></tr>
  <tr><td>6</td><td>Cristaler&iacute;a / Plantillas</td><td>Se aplican cristales y plantillas decorativas.</td></tr>
  <tr><td>7</td><td>Calidad de aplicaciones</td><td>Se revisa la calidad de sublimado y aplicaciones.</td></tr>
  <tr><td>8</td><td>Costura</td><td>Se confecciona la prenda completa.</td></tr>
  <tr><td>9</td><td>Calidad costura</td><td>Se inspecciona la costura terminada.</td></tr>
  <tr><td>10</td><td>Calidad final</td><td>Revisi&oacute;n integral de la prenda contra el dise&ntilde;o.</td></tr>
  <tr><td>11</td><td>Empaque</td><td>Se empaca el pedido por atleta / art&iacute;culo.</td></tr>
  <tr><td>12</td><td>Env&iacute;os</td><td>Se env&iacute;a o entrega el pedido al equipo.</td></tr>
</table>"""

REGLA_ORO = """
<div class="gold"><span class="t">&#11088; Regla de Oro de producci&oacute;n</span><br>
Ninguna etapa puede iniciarse sin haber completado la anterior. El sistema bloquea
autom&aacute;ticamente el intento de completar una tarea si existe una etapa previa pendiente.</div>"""

FOOTER = f'<div class="footer">Space Cheer &middot; {SITE} &middot; Si tienes dudas usa el bot&oacute;n de ayuda <b>?</b> disponible en cada pantalla, o escr&iacute;benos desde la p&aacute;gina de Contacto.</div>'


# ─────────────────────────────────────────────────────────────────────────────
# CASO 1 — Historia completa
# ─────────────────────────────────────────────────────────────────────────────
def caso_1() -> str:
    b = cover(
        "De la solicitud al env&iacute;o",
        "La historia completa de un pedido de uniformes",
        "CASO DE USO 1 — TODOS LOS ROLES",
    )
    b += f"""
<div class="content">
  <h2>El escenario</h2>
  <div class="scenario">
    <div class="t">Club &laquo;Nebula Stars&raquo; — 14 uniformes Elite para la temporada</div>
    <span class="actor hc">MARIANA — HEADCOACH</span>
    <span class="actor ath">SOF&Iacute;A — ATLETA (menor)</span>
    <span class="actor gua">LAURA — TUTORA</span>
    <span class="actor adm">ADMINISTRADOR</span>
    <span class="actor ope">OPERARIOS</span>
    <p style="margin-top:8px">Mariana necesita uniformes nuevos para su equipo antes del Grand Prix.
    Este documento muestra el recorrido completo: desde que entra a {SITE} hasta que el
    paquete sale de Env&iacute;os.</p>
  </div>

  <h2>El ciclo de vida del pedido</h2>
  {FLOW_ORDER}
  <p>Cada pedido avanza por estos estados. Las flechas solo van hacia adelante:
  el administrador es quien autoriza cada avance. Un pedido puede cancelarse
  mientras est&eacute; <b>Pendiente</b> o con <b>Dise&ntilde;o aprobado</b>; una vez
  en producci&oacute;n ya no.</p>

  <h2>Semana 1 — El pedido nace</h2>
  {step(1, "Mariana entra y arma su pedido", "Tienda &rarr; Cat&aacute;logo",
        "Inicia sesi&oacute;n, abre el cat&aacute;logo y elige el <b>Uniforme Elite</b>. "
        "Como es un producto personalizado por equipo, el sistema le pide elegir a "
        "<b>Nebula Stars</b> antes de agregarlo al carrito. Desde el carrito lo convierte en pedido.")}
  {step(2, "Asigna a sus 14 atletas", "Mis Pedidos &rarr; Detalle del pedido &rarr; Art&iacute;culo",
        "En el detalle del art&iacute;culo usa <b>Importar atletas del equipo</b>: en un clic "
        "quedan los 14 asignados. Captura tambi&eacute;n los datos de contacto y entrega del pedido.")}
  {step(3, "Abre la captura de medidas", "Detalle del pedido",
        "Mariana abre las medidas y avisa al equipo. Cada atleta captura las suyas; "
        "ella puede capturarlas por los que no puedan.")}
  {step(4, "Sof&iacute;a captura sus medidas", "Mis Pedidos &rarr; Mis medidas",
        "Sof&iacute;a (atleta) entra con su cuenta y llena pecho, cintura, cadera y largo, "
        "seg&uacute;n los campos que pide el producto. Su tutora Laura puede revisar todo desde "
        "su panel de tutora.")}
  {step(5, "Mariana env&iacute;a el pedido", "Detalle del pedido &rarr; Enviar",
        "Con las medidas completas, env&iacute;a el pedido. El estado pasa de "
        "<b>Borrador</b> a <b>Pendiente</b> y llega a la bandeja del administrador.")}

  <h2>Semana 2 — Aprobaci&oacute;n</h2>
  {step(6, "El administrador revisa", "Administrar pedidos &rarr; Detalle",
        "Verifica que las medidas est&eacute;n completas y sube el <b>dise&ntilde;o</b> del uniforme "
        "acordado con Mariana.")}
  {step(7, "Aprueba el dise&ntilde;o", "Detalle del pedido (admin)",
        "Primera autorizaci&oacute;n expl&iacute;cita: <b>Pendiente &rarr; Dise&ntilde;o aprobado</b>. "
        "En este momento las medidas quedan <b>bloqueadas</b>: ya nadie puede modificarlas, "
        "porque producci&oacute;n trabajar&aacute; con ellas.")}
  {step(8, "Env&iacute;a a producci&oacute;n", "Detalle del pedido (admin)",
        "Segunda autorizaci&oacute;n: <b>Dise&ntilde;o aprobado &rarr; En producci&oacute;n</b>. "
        "El sistema crea autom&aacute;ticamente el <b>trabajo de producci&oacute;n</b> con una tarea "
        "por cada art&iacute;culo y cada etapa que aplica al producto.")}

  <div class="page-break"></div>

  <h2>Semanas 3 y 4 — El piso de producci&oacute;n</h2>
  <p>El administrador asigna operarios a las tareas desde el <b>Panel de Producci&oacute;n</b>.
  Cada operario ve sus tareas y las completa en orden:</p>
  {ETAPAS_TABLE}
  {REGLA_ORO}
  {step(9, "Los operarios trabajan sus etapas", "Producci&oacute;n &rarr; Mis Tareas",
        "Cada operario completa su etapa y el sistema registra qui&eacute;n y cu&aacute;ndo. "
        "Si alguien detecta un defecto (una manga mal sublimada, por ejemplo), genera un "
        "<b>reporte de error</b> que el administrador revisa y decide si amerita reposici&oacute;n.")}
  {step(10, "Empaque y env&iacute;o", "Etapas 11 y 12",
        "Con las 12 etapas completas, el pedido se empaca por atleta y sale por Env&iacute;os. "
        "El administrador marca el pedido como <b>Entregado</b>.")}
  {step(11, "El equipo recibe sus uniformes", "",
        "Mariana ve el estado final en <b>Mis Pedidos</b>. Sof&iacute;a estrena uniforme "
        "en el Grand Prix. &#127942;")}

  <h2>Qui&eacute;n hace qu&eacute; (resumen)</h2>
  <table>
    <tr><th>Actor</th><th>Responsabilidades en el flujo</th></tr>
    <tr><td><span class="actor hc">HEADCOACH</span></td>
        <td>Crea el pedido, asigna atletas, gestiona medidas, env&iacute;a a revisi&oacute;n, da seguimiento.</td></tr>
    <tr><td><span class="actor ath">ATLETA</span></td>
        <td>Se une al equipo con c&oacute;digo, completa su perfil y captura sus medidas a tiempo.</td></tr>
    <tr><td><span class="actor gua">TUTOR</span></td>
        <td>Se vincula al atleta menor, supervisa sus datos y pedidos; puede pedir por &eacute;l.</td></tr>
    <tr><td><span class="actor adm">ADMIN</span></td>
        <td>Aprueba dise&ntilde;o y medidas, autoriza producci&oacute;n, asigna operarios, entrega.</td></tr>
    <tr><td><span class="actor ope">OPERARIO</span></td>
        <td>Completa sus etapas en orden y reporta errores de producci&oacute;n.</td></tr>
  </table>
  {FOOTER}
</div>"""
    return doc("Caso de uso 1 — Pedido completo", b)


# ─────────────────────────────────────────────────────────────────────────────
# CASO 2 — HeadCoach
# ─────────────────────────────────────────────────────────────────────────────
def caso_2() -> str:
    b = cover(
        "Crear un pedido y gestionar medidas",
        "Gu&iacute;a paso a paso para HeadCoach y Coach",
        "CASO DE USO 2 — HEADCOACH / COACH",
    )
    b += f"""
<div class="content">
  <div class="scenario">
    <div class="t">Objetivo</div>
    <p>Levantar un pedido de uniformes para tu equipo, lograr que todos capturen medidas
    a tiempo y enviarlo a revisi&oacute;n sin contratiempos.</p>
  </div>

  <h2>Antes de empezar</h2>
  <ul>
    <li>Tu equipo debe existir en <b>Equipos &rarr; Mis Equipos</b> y tus atletas deben estar dentro.</li>
    <li>Comparte el <b>c&oacute;digo de invitaci&oacute;n</b> del equipo para que los atletas se unan
        (t&uacute; apruebas cada solicitud).</li>
    <li>Los atletas menores necesitan un <b>tutor vinculado</b> para usar la plataforma.</li>
  </ul>

  <h2>Paso a paso</h2>
  {step(1, "Elige el producto", "Tienda &rarr; Cat&aacute;logo",
        "Abre el producto que necesitas. Si es personalizado por equipo, el sistema te pedir&aacute; "
        "elegir el equipo antes de agregarlo al carrito.")}
  {step(2, "Convierte el carrito en pedido", "Carrito (&iacute;cono superior derecho)",
        "Revisa cantidades y confirma. Se crea un pedido en estado <b>Borrador</b> — nada se ha "
        "enviado todav&iacute;a, puedes modificar todo.")}
  {step(3, "Completa los datos de contacto", "Detalle del pedido &rarr; Datos de contacto",
        "Captura tel&eacute;fono y direcci&oacute;n de entrega. Con esto te avisamos de avances y "
        "coordinamos la entrega.")}
  {step(4, "Asigna atletas a cada art&iacute;culo", "Detalle del pedido &rarr; Art&iacute;culo",
        "Usa <b>Importar atletas del equipo</b> para asignarlos todos de una vez, o agr&eacute;galos "
        "individualmente. Cada atleta asignado tendr&aacute; su propia prenda con sus medidas.")}
  {step(5, "Abre las medidas y pon fecha l&iacute;mite", "Detalle del pedido",
        "Al abrir medidas, cada atleta puede capturar las suyas desde su cuenta. Define la fecha "
        "l&iacute;mite: al vencer, el sistema cierra la captura autom&aacute;ticamente.")}
  {step(6, "Vigila el avance", "Detalle del pedido &rarr; Art&iacute;culo",
        "El detalle del art&iacute;culo muestra qui&eacute;n ya captur&oacute; y a qui&eacute;n le falta. "
        "Puedes capturar medidas por un atleta si es necesario (por ejemplo, los m&aacute;s peque&ntilde;os).")}
  {step(7, "Env&iacute;a el pedido", "Detalle del pedido &rarr; Enviar",
        "Con medidas completas, env&iacute;a. El estado pasa a <b>Pendiente</b> y el administrador "
        "lo recibe para revisi&oacute;n de dise&ntilde;o.")}

  <h2>Despu&eacute;s de enviar</h2>
  {FLOW_ORDER}
  <ul>
    <li><b>Pendiente:</b> el administrador revisa dise&ntilde;o y medidas. Puede pedirte correcciones.</li>
    <li><b>Dise&ntilde;o aprobado:</b> las medidas quedan <b>bloqueadas</b> permanentemente.</li>
    <li><b>En producci&oacute;n:</b> el taller trabaja las 12 etapas. Sigue el avance en el detalle.</li>
    <li><b>Entregado:</b> el pedido lleg&oacute; a su destino. &#127881;</li>
  </ul>

  <div class="warn"><b>&#9888;&#65039; Importante:</b> despu&eacute;s de la aprobaci&oacute;n del dise&ntilde;o
  ya no se pueden corregir medidas. Verifica dos veces antes de enviar — un error de medici&oacute;n
  a esta altura implica reposici&oacute;n y retraso para todo el equipo.</div>

  <div class="tip"><b>&#128161; Consejos:</b>
  <ul>
    <li>Pide a los atletas medirse con ayuda de otra persona y con cinta m&eacute;trica flexible.</li>
    <li>Si un atleta no aparece para asignarlo, revisa que su solicitud de equipo est&eacute; aceptada
        y su perfil completo.</li>
    <li>Puedes cancelar el pedido mientras est&eacute; Pendiente o con Dise&ntilde;o aprobado;
        en producci&oacute;n ya no.</li>
  </ul></div>
  {FOOTER}
</div>"""
    return doc("Caso de uso 2 — HeadCoach", b)


# ─────────────────────────────────────────────────────────────────────────────
# CASO 3 — Atleta y tutor
# ─────────────────────────────────────────────────────────────────────────────
def caso_3() -> str:
    b = cover(
        "Unirse, medirse y estrenar uniforme",
        "Gu&iacute;a para atletas y sus tutores",
        "CASO DE USO 3 — ATLETA / TUTOR",
    )
    b += f"""
<div class="content">
  <div class="scenario">
    <div class="t">Escenario</div>
    <p>Sof&iacute;a (13 a&ntilde;os) entra al equipo Nebula Stars. Su mam&aacute;, Laura, ser&aacute;
    su tutora en la plataforma. El equipo tiene un pedido de uniformes en curso y Sof&iacute;a
    debe capturar sus medidas antes de la fecha l&iacute;mite.</p>
  </div>

  <h2>Parte A — Sof&iacute;a (atleta)</h2>
  {step(1, "Crea tu cuenta y completa tu perfil", SITE + " &rarr; Registrarse",
        "Reg&iacute;strate con tu correo y completa el perfil. A los atletas se les pide "
        "<b>CURP</b> por requisito legal — verif&iacute;cala contra tu documento oficial.")}
  {step(2, "&Uacute;nete a tu equipo con el c&oacute;digo", "Equipos &rarr; Unirse con c&oacute;digo",
        "Tu coach te dar&aacute; un c&oacute;digo. Ingr&eacute;salo y espera a que acepte tu solicitud. "
        "A partir de ah&iacute; ver&aacute;s a tu equipo y sus pedidos.")}
  {step(3, "Espera tu vinculaci&oacute;n de tutor (menores)", "",
        "Si eres menor de edad, la plataforma se bloquea hasta que tu coach vincule a tu "
        "pap&aacute;, mam&aacute; o tutor. Av&iacute;sale a tu coach qui&eacute;n ser&aacute;.")}
  {step(4, "Captura tus medidas", "Mis Pedidos &rarr; pedido del equipo &rarr; Mis medidas",
        "Cuando el coach abra las medidas, captura cada campo que pide el producto "
        "(pecho, cintura, cadera, largo&hellip;). M&iacute;dete con ayuda y con cinta m&eacute;trica "
        "flexible, sin apretar.")}
  {step(5, "Da seguimiento", "Mis Pedidos",
        "Ver&aacute;s el estado del pedido avanzar: Pendiente &rarr; Dise&ntilde;o aprobado &rarr; "
        "En producci&oacute;n &rarr; Entregado. Cuando llegue, &iexcl;a estrenar! &#128640;")}

  <div class="warn"><b>&#9888;&#65039; La fecha l&iacute;mite importa:</b> si no capturas tus medidas
  a tiempo, la captura se cierra autom&aacute;ticamente y tu coach tendr&aacute; que hacerlo por ti —
  o tu prenda podr&iacute;a no entrar al pedido.</div>

  <h2>Parte B — Laura (tutora)</h2>
  {step(1, "Acepta la vinculaci&oacute;n", "",
        "El headcoach te vincula como tutora de Sof&iacute;a. Con tu cuenta ver&aacute;s un "
        "<b>panel de tutor</b> especial.")}
  {step(2, "Supervisa desde tu panel", "Mi Dashboard (tutor)",
        "Ve los pedidos de Sof&iacute;a, su estado, sus datos de perfil y su informaci&oacute;n "
        "de equipo. Los datos de menores est&aacute;n protegidos y cada acceso queda auditado.")}
  {step(3, "Pide por tu atleta si hace falta", "Panel de tutor &rarr; Crear pedido",
        "Puedes crear un pedido en nombre de Sof&iacute;a eligiendo productos del cat&aacute;logo, "
        "y capturar sus medidas si ella no puede.")}

  <div class="tip"><b>&#128161; Consejos:</b>
  <ul>
    <li>Mant&eacute;n tu direcci&oacute;n actualizada en <b>Mis Direcciones</b> — se usa para entregas.</li>
    <li>El bot&oacute;n <b>?</b> flotante de cada pantalla explica c&oacute;mo funciona esa p&aacute;gina.</li>
    <li>Las medidas solo se pueden editar mientras el pedido las tenga <b>abiertas</b>.</li>
  </ul></div>
  {FOOTER}
</div>"""
    return doc("Caso de uso 3 — Atleta y tutor", b)


# ─────────────────────────────────────────────────────────────────────────────
# CASO 4 — Admin
# ─────────────────────────────────────────────────────────────────────────────
def caso_4() -> str:
    b = cover(
        "Aprobar, producir y entregar",
        "Flujo de trabajo del administrador",
        "CASO DE USO 4 — ADMINISTRADOR",
    )
    b += f"""
<div class="content">
  <div class="scenario">
    <div class="t">Escenario</div>
    <p>Lleg&oacute; el pedido de Nebula Stars (14 uniformes Elite) a tu bandeja en estado
    <b>Pendiente</b>. Tu trabajo: validarlo, autorizar producci&oacute;n, mantener el taller
    fluyendo y entregar a tiempo.</p>
  </div>

  <h2>Las dos autorizaciones del admin</h2>
  {FLOW_ORDER}
  <p>El pedido no entra al taller con un solo clic — son <b>dos decisiones expl&iacute;citas</b>:</p>
  <ol>
    <li><b>Aprobar dise&ntilde;o</b> (Pendiente &rarr; Dise&ntilde;o aprobado): confirmas que el
        dise&ntilde;o est&aacute; listo y las medidas cerradas. Las medidas quedan bloqueadas.</li>
    <li><b>Enviar a producci&oacute;n</b> (Dise&ntilde;o aprobado &rarr; En producci&oacute;n):
        autorizas el trabajo f&iacute;sico. El sistema genera las tareas autom&aacute;ticamente.</li>
  </ol>

  <h2>Paso a paso</h2>
  {step(1, "Revisa el pedido entrante", "Tienda &rarr; Administrar pedidos",
        "Abre el detalle: productos, atletas asignados y estado de medidas. Si algo falta, "
        "cont&aacute;ctate con el headcoach y reabre medidas si es necesario.")}
  {step(2, "Sube el dise&ntilde;o", "Detalle del pedido (admin) &rarr; Subir dise&ntilde;o",
        "Carga el dise&ntilde;o final acordado. El piso de producci&oacute;n lo consultar&aacute; "
        "durante todo el proceso.")}
  {step(3, "Aprueba el dise&ntilde;o", "Detalle del pedido (admin)",
        "Ejecuta la transici&oacute;n <b>Pendiente &rarr; Dise&ntilde;o aprobado</b>. El sistema "
        "valida que las medidas est&eacute;n completas antes de permitir el bloqueo.")}
  {step(4, "Env&iacute;a a producci&oacute;n", "Detalle del pedido (admin)",
        "Transici&oacute;n <b>Dise&ntilde;o aprobado &rarr; En producci&oacute;n</b>. Se crea el "
        "trabajo de producci&oacute;n con una tarea por art&iacute;culo &times; etapa, seg&uacute;n "
        "la matriz de etapas del producto.")}
  {step(5, "Asigna operarios", "Producci&oacute;n &rarr; Panel de Producci&oacute;n &rarr; Trabajo",
        "Asigna cada tarea al operario del rol responsable (el reglamento te dice qui&eacute;n es). "
        "Puedes marcar el trabajo como <b>urgente</b> o reasignar tareas en bloque.")}
  {step(6, "Monitorea el avance", "Panel de Producci&oacute;n",
        "Sigue el progreso por etapa y detecta cuellos de botella. Los operarios completan "
        "en orden — la Regla de Oro lo garantiza.")}
  {step(7, "Atiende reportes de error", "Producci&oacute;n &rarr; Errores",
        "Revisa cada reporte y decide: revisado, o <b>requiere reposici&oacute;n</b> "
        "(rehacer la prenda y/o cobrarla, seg&uacute;n el caso).")}
  {step(8, "Entrega", "Detalle del pedido (admin)",
        "Con las 12 etapas completas y el pedido enviado, marca <b>En producci&oacute;n &rarr; "
        "Entregado</b>. El ciclo termina.")}

  {REGLA_ORO}

  <h2>Extra — Pedidos de mostrador (offline)</h2>
  {step(1, "Registra al cliente", "Administrar pedidos &rarr; Clientes",
        "Para ventas fuera de la plataforma, crea primero al cliente con su tel&eacute;fono y correo.")}
  {step(2, "Levanta el pedido offline", "Administrar pedidos &rarr; Pedido offline nuevo",
        "Elige cliente, productos internos y una <b>plantilla de producci&oacute;n</b> "
        "(el conjunto de etapas precargado). Captura las medidas directamente.")}
  {step(3, "Registra abonos", "Detalle del pedido (admin) &rarr; Pagos",
        "Registra anticipos y abonos (efectivo, transferencia&hellip;) hasta liquidar. "
        "El pedido offline sigue el mismo flujo de producci&oacute;n que los dem&aacute;s.")}

  <div class="tip"><b>&#128161; Consejos:</b>
  <ul>
    <li>Configura el reglamento en <b>Config. Producci&oacute;n &rarr; Responsabilidades</b>:
        responsable primario y auxiliares por etapa.</li>
    <li>La matriz <b>Etapas por producto</b> define qu&eacute; tareas se generan — rev&iacute;sala
        al crear productos nuevos.</li>
    <li>Al reasignar un operario de rol, sus tareas ya asignadas no cambian solas:
        reas&iacute;gnalas desde el detalle del trabajo.</li>
  </ul></div>
  {FOOTER}
</div>"""
    return doc("Caso de uso 4 — Administrador", b)


# ─────────────────────────────────────────────────────────────────────────────
# CASO 5 — Operario
# ─────────────────────────────────────────────────────────────────────────────
def caso_5() -> str:
    b = cover(
        "Trabajar las etapas de producci&oacute;n",
        "Gu&iacute;a del operario en el piso de taller",
        "CASO DE USO 5 — OPERARIO",
    )
    b += f"""
<div class="content">
  <div class="scenario">
    <div class="t">Escenario</div>
    <p>Eres CONE, operario responsable de <b>Sublimaci&oacute;n</b>, <b>Calidad final</b> y
    <b>Empaque</b>. Entr&oacute; el pedido de Nebula Stars (14 uniformes) y tienes tareas
    nuevas asignadas.</p>
  </div>

  <h2>Tu d&iacute;a a d&iacute;a</h2>
  {step(1, "Revisa tus tareas", "Producci&oacute;n &rarr; Mis Tareas",
        "Tu panel muestra las tareas activas ordenadas por urgencia: qu&eacute; art&iacute;culo, "
        "qu&eacute; etapa y de qu&eacute; pedido. Recibes una notificaci&oacute;n cuando te asignan "
        "una tarea nueva.")}
  {step(2, "Consulta el dise&ntilde;o y las medidas", "Tarea &rarr; Dise&ntilde;o / Medidas",
        "Antes de trabajar, abre el dise&ntilde;o aprobado de la orden y las medidas del "
        "art&iacute;culo. Produce siempre contra el dise&ntilde;o autorizado.")}
  {step(3, "Completa tu etapa", "Mis Tareas &rarr; Completar",
        "Al terminar tu parte f&iacute;sica, marca la tarea como completada. El sistema registra "
        "qui&eacute;n y cu&aacute;ndo la complet&oacute;.")}
  {REGLA_ORO}
  {step(4, "Si detectas un problema, rep&oacute;rtalo", "Producci&oacute;n &rarr; Reportar Error",
        "&iquest;Tela da&ntilde;ada, sublimado corrido, costura defectuosa? Genera un reporte: "
        "tipo de error, etapa afectada y las acciones correctivas que tomaste. El administrador "
        "lo revisa y decide si hay reposici&oacute;n.")}
  {step(5, "Conoce tu &aacute;rea", "Producci&oacute;n &rarr; Mi &Aacute;rea",
        "Ah&iacute; ves tus roles, las etapas donde eres <b>responsable primario</b>, en cu&aacute;les "
        "apoyas como <b>auxiliar</b>, y el estado de tus reportes de error.")}
  {step(6, "Consulta el reglamento", "Producci&oacute;n &rarr; Reglamento",
        "El reglamento muestra las 12 etapas del proceso y qui&eacute;n responde por cada una. "
        "Si tienes duda de a qui&eacute;n corresponde algo, emp&iacute;eza aqu&iacute;.")}

  <h2>Las 12 etapas y sus responsables</h2>
  {ETAPAS_TABLE}

  <div class="warn"><b>&#9888;&#65039; No fuerces el orden:</b> si el sistema no te deja completar
  tu tarea, es porque una etapa anterior sigue pendiente. Habla con el responsable de esa etapa
  o con el administrador — no busques la vuelta.</div>

  <div class="tip"><b>&#128161; Consejos:</b>
  <ul>
    <li>Revisa tus tareas al iniciar el turno; las urgentes aparecen destacadas.</li>
    <li>Reportar un error a tiempo ahorra reposiciones — nunca dejes pasar un defecto
        &laquo;peque&ntilde;o&raquo;.</li>
    <li>Tu trabajo queda registrado con fecha y hora: es tu respaldo de qu&eacute; completaste.</li>
  </ul></div>
  {FOOTER}
</div>"""
    return doc("Caso de uso 5 — Operario", b)


# ─────────────────────────────────────────────────────────────────────────────
# Main
# ─────────────────────────────────────────────────────────────────────────────
CASOS = [
    ("caso_uso_1_pedido_completo.pdf", caso_1),
    ("caso_uso_2_headcoach_crear_pedido.pdf", caso_2),
    ("caso_uso_3_atleta_tutor.pdf", caso_3),
    ("caso_uso_4_admin_aprobacion.pdf", caso_4),
    ("caso_uso_5_operario_etapas.pdf", caso_5),
]


def main():
    with sync_playwright() as p:
        browser = p.chromium.launch()
        page = browser.new_page()
        for filename, builder in CASOS:
            out = ROOT / filename
            print(f"-> {filename} ...")
            page.set_content(builder(), wait_until="load")
            page.pdf(
                path=str(out),
                format="A4",
                print_background=True,
                margin={"top": "0", "bottom": "0", "left": "0", "right": "0"},
            )
            print(f"   OK ({out.stat().st_size / 1024:.1f} KB)")
        browser.close()
    print("\nListo: 5 PDFs generados en", ROOT)


if __name__ == "__main__":
    main()
