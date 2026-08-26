"""Genera CHEATSHEET_SIMULACION.md a partir de SIMULACION.json."""
import io
import json
from collections import defaultdict

SRC = "../SIMULACION.json"
DST = "../CHEATSHEET_SIMULACION.md"

d = json.load(io.open(SRC, encoding="utf-8"))
out = []
w = out.append

PWD = d["password"]
fecha = d["generated_at"][:10]

ROLE_ORDER = ["ADMIN", "STAFF", "JUEZ", "HEADCOACH", "COACH", "ATHLETE", "GUARDIAN", "OPERARIO"]
ROLE_TITLE = {
    "ADMIN": "Administración",
    "STAFF": "Staff de oficina",
    "JUEZ": "Jueces",
    "HEADCOACH": "Head coaches",
    "COACH": "Coaches auxiliares",
    "ATHLETE": "Atletas",
    "GUARDIAN": "Tutores / acompañantes",
    "OPERARIO": "Operarios de taller",
}

STATUS_ES = {
    "DRAFT": "Borrador",
    "PENDING": "Pendiente",
    "DESIGN_APPROVED": "Diseño aprobado",
    "IN_PRODUCTION": "En producción",
    "DELIVERED": "Entregado",
    "CANCELLED": "Cancelado",
}
JOB_ES = {
    "PENDING": "Pendiente",
    "IN_PROGRESS": "En progreso",
    "PAUSED": "Pausado",
    "COMPLETED": "Completado",
    "CANCELLED": "Cancelado",
    "": "—",
}

# ───────────────────────────────────────────────────────────────
w(f"# Space Cheer — Cheatsheet de la simulación")
w("")
w(f"> Generado el **{fecha}** por `python manage.py simulate_platform`.")
w("> Base local PostgreSQL `SPACE`. Todos los usuarios comparten la contraseña "
  f"**`{PWD}`**.")
w("")
w("## Cómo levantar el entorno")
w("")
w("```bash")
w("cd C:\\Users\\Lenovo\\Documents\\SPACE-CHEER\\space_cheer")
w("../venv/Scripts/python.exe manage.py runserver 8000")
w("# → http://127.0.0.1:8000/")
w("```")
w("")
w("Para reconstruir la simulación desde cero (borra y recrea la base `SPACE`):")
w("")
w("```bash")
w("psql -h localhost -U postgres -c 'DROP DATABASE \"SPACE\";'")
w("psql -h localhost -U postgres -c 'CREATE DATABASE \"SPACE\" OWNER postgres;'")
w("../venv/Scripts/python.exe manage.py migrate")
w("../venv/Scripts/python.exe manage.py seed_all")
w("../venv/Scripts/python.exe manage.py seed_products")
w("../venv/Scripts/python.exe manage.py seed_full_data")
w("CELERY_BROKER_URL=memory:// ../venv/Scripts/python.exe manage.py simulate_platform \\")
w("    --json-out ../SIMULACION.json")
w("```")
w("")
w("> `CELERY_BROKER_URL=memory://` no es opcional: sin Redis vivo, cada "
  "notificación espera 3 s reintentando contra `redis:6379` y la corrida pasa "
  "de 40 s a ~20 min.")
w("")

# ── Resumen ────────────────────────────────────────────────────
w("## Qué hay cargado")
w("")
w("| Módulo | Contenido |")
w("|---|---|")
w(f"| Usuarios | {len(d['users'])}, todos con perfil completo, CURP y dirección |")
w(f"| Equipos | {len(d['teams'])} con head coach, 2 coaches y 8 atletas cada uno |")
w(f"| Pedidos | {len(d['orders'])} cubriendo los 6 estados del ciclo |")
w(f"| Jobs de producción | {len(d['production'])} con tareas asignadas por etapa |")
w(f"| Reportes de error | {len(d['error_reports'])} con las 3 resoluciones de dirección |")
w(f"| Eventos | {len(d['events'])} (uno abierto, dos cerrados con resultados) |")
w(f"| Hospedaje | {len(d['hospitality'])} habitaciones de equipo + una de staff |")
w("")

# ── Usuarios ───────────────────────────────────────────────────
w("---")
w("")
w("## Usuarios")
w("")
w(f"Contraseña para **todos**: `{PWD}`")
w("")
w("Los 48 tienen el correo **verificado y primario** en allauth, así que se "
  "entra directo aunque `ACCOUNT_EMAIL_VERIFICATION` esté en `mandatory` "
  "(el default del settings; el `.env` local lo baja a `none`).")
w("")

by_role = defaultdict(list)
for u in d["users"]:
    by_role[u["role"]].append(u)

for role in ROLE_ORDER:
    users = by_role.get(role)
    if not users:
        continue
    w(f"### {ROLE_TITLE[role]}")
    w("")
    if role == "ATHLETE":
        # 24 atletas: tabla compacta por equipo.
        w("Todos son menores de edad (fuerza el flujo de tutor) y tienen las 8 "
          "medidas cargadas en su perfil.")
        w("")
        w("| Equipo | Correos | Nombres |")
        w("|---|---|---|")
        per_team = defaultdict(list)
        for u in users:
            per_team[u["team"]].append(u)
        for team, lst in sorted(per_team.items()):
            lst = sorted(lst, key=lambda x: x["email"])
            correos = f"`{lst[0]['email']}` … `{lst[-1]['email']}`"
            nombres = ", ".join(x["name"] for x in lst)
            w(f"| {team} | {correos} | {nombres} |")
        w("")
        continue

    w("| Correo | Nombre | Equipo | Qué hace en la simulación |")
    w("|---|---|---|---|")
    for u in users:
        w(f"| `{u['email']}` | {u['name']} | {u['team'] or '—'} | {u['note']} |")
    w("")

# ── Equipos ────────────────────────────────────────────────────
w("---")
w("")
w("## Equipos")
w("")
w("| Equipo | Ciudad | Código de ingreso | Head coach | Atletas |")
w("|---|---|---|---|---|")
for t in d["teams"]:
    w(f"| {t['name']} | {t['city']} | `{t['join_code']}` | `{t['headcoach']}` | {t['athletes']} |")
w("")

# ── Pedidos ────────────────────────────────────────────────────
w("---")
w("")
w("## Pedidos")
w("")
w("Un pedido por cada estado del ciclo de vida, más los tres tipos "
  "(`TEAM`, `PERSONAL`, `OFFLINE`).")
w("")
w("| # | Tipo | Dueño | Estado | Job | Creado por | Total |")
w("|---|---|---|---|---|---|---|")
for o in d["orders"]:
    total = o["agreed_price"] or o["total"]
    w(f"| **{o['id']}** | {o['type']} | {o['owner']} | {STATUS_ES.get(o['status'], o['status'])} "
      f"| {JOB_ES.get(o['job_status'], o['job_status'])} | `{o['created_by']}` | ${total} |")
w("")
w("### Detalle por pedido")
w("")
for o in d["orders"]:
    w(f"#### Pedido #{o['id']} — {STATUS_ES.get(o['status'], o['status'])}")
    w("")
    w(f"- **Dueño:** {o['owner']} · **tipo:** `{o['type']}` · **creado por:** `{o['created_by']}`")
    items = "; ".join(
        f"{i['qty']}× {i['product']}"
        + (f" (talla {i['size']})" if i["size"] else "")
        + (f" — {i['athletes']} atletas asignados" if i["athletes"] else "")
        for i in o["items"]
    )
    w(f"- **Contenido:** {items}")
    med = ("bloqueadas" if o["measurements_locked"]
           else ("abiertas" if o["measurements_open"] else "cerradas (reabribles)"))
    w(f"- **Medidas:** {med}" + (f" · límite {o['measurements_due']}" if o["measurements_due"] else ""))
    if o["delivery_date"]:
        w(f"- **Entrega comprometida:** {o['delivery_date']}")
    if o["agreed_price"]:
        w(f"- **Pagos:** precio acordado ${o['agreed_price']} · estado `{o['payment_status']}`")
    w(f"- **Para qué sirve:** {o['note']}")
    if o["log"]:
        w(f"- **Bitácora:** {' · '.join(o['log'])}")
    w("")

# ── Produccion ─────────────────────────────────────────────────
w("---")
w("")
w("## Producción")
w("")
w("Cada job nace automáticamente al pasar su pedido a `IN_PRODUCTION`. "
  "Las tareas se crean por **item × etapa** y se asignan al operario responsable "
  "de esa etapa según `StageResponsibility`.")
w("")
w("| Job | Pedido | Estado | Urgente | Avance | Qué muestra |")
w("|---|---|---|---|---|---|")
for p in d["production"]:
    urgente = "🔴 sí" if p["is_urgent"] else "no"
    w(f"| **{p['job_id']}** | #{p['order_id']} | {JOB_ES.get(p['status'], p['status'])} | {urgente} "
      f"| {p['tasks_done']}/{p['tasks_total']} etapas | {p['note']} |")
w("")

w("### Quién tiene qué asignado")
w("")
carga = defaultdict(lambda: {"pend": 0, "hechas": 0, "etapas": set()})
for p in d["production"]:
    for a in p["assignments"]:
        if not a["assigned_to"]:
            continue
        c = carga[a["assigned_to"]]
        c["etapas"].add(a["stage"])
        if a["status"] == "COMPLETED":
            c["hechas"] += 1
        else:
            c["pend"] += 1
w("| Operario | Etapas a su cargo | Pendientes | Completadas |")
w("|---|---|---|---|")
for nombre, c in sorted(carga.items(), key=lambda kv: -kv[1]["pend"]):
    w(f"| {nombre} | {', '.join(sorted(c['etapas']))} | {c['pend']} | {c['hechas']} |")
w("")

w("### Tareas pendientes por job")
w("")
for p in d["production"]:
    pend = [a for a in p["assignments"] if a["status"] != "COMPLETED"]
    if not pend:
        w(f"- **Job {p['job_id']}** (pedido #{p['order_id']}): sin pendientes, cerrado.")
        continue
    prox = pend[0]
    w(f"- **Job {p['job_id']}** (pedido #{p['order_id']}, {JOB_ES.get(p['status'])}): "
      f"{len(pend)} tareas abiertas. La siguiente es **{prox['stage']}** "
      f"sobre *{prox['product']}*, a cargo de **{prox['assigned_to'] or 'sin asignar'}**.")
w("")

# ── Reportes de error ──────────────────────────────────────────
w("---")
w("")
w("## Reportes de error")
w("")
REV_ES = {
    "PENDING": "Pendiente de revisión",
    "REVIEWED": "Revisado",
    "EXCEPTION_GRANTED": "Excepción otorgada",
    "REPOSITION_REQUIRED": "Reposición requerida",
}
for r in d["error_reports"]:
    w(f"### Reporte #{r['id']} — {REV_ES.get(r['review_status'], r['review_status'])}")
    w("")
    w(f"- **Pedido:** #{r['order_id']} · **job:** {r['job_id']} · **etapa:** {r['stage']}")
    w(f"- **Lo reportó:** {r['reported_by']} · **responsable:** {r['responsible']}")
    w(f"- **Tipo:** {', '.join(r['types'])}")
    w(f"- **Descripción:** {r['description']}")
    w(f"- **Reposición requerida:** {'sí' if r['requires_reposition'] else 'no'}"
      + (f" · **revisó:** {r['reviewed_by']}" if r["reviewed_by"] else ""))
    w("")

# ── Eventos ────────────────────────────────────────────────────
w("---")
w("")
w("## Eventos y concursos")
w("")
EV_ES = {
    "DRAFT": "Borrador",
    "REGISTRATION_OPEN": "Inscripciones abiertas",
    "REGISTRATION_CLOSED": "Inscripciones cerradas",
    "IN_PROGRESS": "En progreso",
    "COMPLETED": "Completado",
    "CANCELLED": "Cancelado",
}
for e in d["events"]:
    w(f"### {e['name']}")
    w("")
    w(f"- **Estado:** {EV_ES.get(e['status'], e['status'])} · **sede:** {e['venue']} · "
      f"**fechas:** {e['start']} → {e['end']}")
    w(f"- **Equipos inscritos:** {e['teams']} · **participantes:** {e['participants']}")
    if e["judges"]:
        w(f"- **Panel de jueces:** {', '.join(e['judges'])}")
    if e["criteria"]:
        crits = ", ".join(f"{c['name']} (máx {c['max']})" for c in e["criteria"])
        w(f"- **Criterios:** {crits}")
    w(f"- **Calificaciones capturadas:** {e['scores']}")
    if e["results"]:
        w("- **Resultados publicados:**")
        for r in e["results"]:
            w(f"  - {r['placement']}º **{r['team']}** — {r['score']} pts")
    w("")

# ── Hospedaje ──────────────────────────────────────────────────
w("---")
w("")
w("## Hospedaje")
w("")
if d["hospitality"]:
    h0 = d["hospitality"][0]
    w(f"**{h0['hotel']}** — check-in {h0['check_in']}, check-out {h0['check_out']}.")
    w("")
    w("| Habitación | Tipo | Equipo | Ocupantes |")
    w("|---|---|---|---|")
    for h in d["hospitality"]:
        w(f"| {h['room']} | {h['room_type']} (cap. {h['capacity']}) | {h['team']} | "
          f"{', '.join(h['occupants']) or '—'} |")
    w("")
    w(f"Los tres head coaches comparten la habitación **{d['hospitality'][0]['headcoach_room']}**.")
    w("")

# ── Pendientes ─────────────────────────────────────────────────
w("---")
w("")
w("## Pendientes")
w("")
w("Dos resueltos el 2026-08-24 con las reglas que definió Bryan; dos abiertos.")
w("")

w("### ✅ Resuelto — capacidad real por cama")
w("")
w("Antes `BedAssignment` rechazaba cualquier segundo huésped en una cama, sin "
  "importar el tipo: una KING valía lo mismo que una individual, y un padre no "
  "podía compartir cama con su hijo.")
w("")
w("Ahora `Bed` tiene **capacidad con default por tipo y override por cama**:")
w("")
w("| Tipo | Capacidad por defecto |")
w("|---|---|")
w("| Individual | 1 |")
w("| Doble / Queen / King / Litera | 2 |")
w("")
w("El campo `Bed.capacity` queda vacío para usar el default, o se llena para "
  "declarar lo que sea esa cama en particular (una matrimonial angosta para 1, "
  "una litera de 3). `Bed.effective_capacity` resuelve cuál manda. No se puede "
  "bajar la capacidad por debajo de los huéspedes ya asignados.")
w("")
w("Migración: `hospitality/migrations/0003_bed_capacity.py`.")
w("")

w("### ✅ Resuelto — un menor ya no se aloja con un adulto ajeno")
w("")
w("Regla nueva en `hospitality/policies.py` (`MinorLodgingPolicy`), aplicada "
  "tanto en el `clean()` de los modelos como en los servicios de asignación. "
  "**La cama es más estricta que el cuarto:**")
w("")
w("| Ámbito | Con quién puede estar un menor |")
w("|---|---|")
w("| Habitación | Su tutor asignado, **o** el cuerpo técnico de su equipo (head coach, coach o staff con membresía activa) |")
w("| Cama | **Solo** su tutor asignado |")
w("")
w("Entre menores no hay restricción, y entre adultos tampoco. Un coach puede "
  "dormir en el mismo cuarto que una atleta menor —eso es acompañamiento "
  "normal de equipo— pero no en su misma cama.")
w("")
w("La simulación lo muestra en la habitación **204**: la tutora Alicia Cruz "
  "comparte la cama matrimonial con su hija Sofía Cruz, y Valeria Torres —la "
  "otra atleta a su cargo— duerme en la individual.")
w("")
w("Cubierto por 22 tests en `hospitality/tests.py`.")
w("")

w("### ✅ Resuelto — el pedido ya dice qué falta, y a quién le toca")
w("")
w("`next_step_requirements()` reporta de una sola vez todo lo que falta para el "
  "siguiente estado, en cualquier punto del ciclo, con el responsable de cada "
  "cosa. Antes las validaciones solo hablaban cuando alguien ya había intentado "
  "avanzar, y de a un error por vez.")
w("")
w("**El cliente no ve el detalle interno.** Admin y staff ven todo; el head "
  "coach ve solo lo suyo y del resto sabe que el pedido está en curso. El corte "
  "lo hace `can_administer_orders()`.")
w("")

w("### ✅ Resuelto — respaldo de la tutela legal")
w("")
w("`TUTOR` registra documento, quién verificó y cuándo; solo un ADMIN puede "
  "hacerlo, y cambiar la relación invalida la verificación previa. `PADRE` y "
  "`ACOMP` siguen declarativos.")
w("")
w("**Sin tope de atletas por tutor**: por encima de 4 la pantalla avisa y deja "
  "seguir. El riesgo está en que el vínculo sea falso, no en el número, y un "
  "error duro ahí solo enseñaría a elegir «Acompañante» para esquivarlo.")
w("")

w("### 🔴 Abierto — un menor tiene un solo tutor")
w("")
w("`AthleteProfile.guardian` es un FK simple. En la práctica los padres se "
  "turnan según el viaje. **Es la limitación que más va a doler** si se sigue "
  "trabajando en hospedaje o custodia.")
w("")

w("### 🔴 Abierto — STAFF no abre el detalle de un pedido")
w("")
w("`/orders/<id>/` admite ADMIN, HEADCOACH, GUARDIAN, COACH y ATHLETE, pero no "
  "STAFF, y `visible_for_user` tampoco le da los pedidos offline. A nivel de "
  "servicio staff sí ve todos los pendientes con detalle. Es comportamiento "
  "previo; ampliar accesos es decisión de producto.")
w("")

# ── Notas ──────────────────────────────────────────────────────
w("---")
w("")
w("## Notas sobre la simulación")
w("")
w("- **Las imágenes de diseño son PNG de 1×1.** `OrderDesignImage` exige un "
  "mínimo de 35 MB, pero ese validador solo corre en el formulario; el ORM no "
  "lo dispara. Si subes un diseño desde la interfaz, el mínimo sí aplica.")
w("- **`seed_full_data` tenía fechas fijas de 2026** que ya caducaron y hacían "
  "fallar la validación `registration_close >= registration_open`. Ahora son "
  "relativas a la fecha de ejecución.")
w("- **Nada de esto está commiteado.** El comando nuevo es "
  "`core/management/commands/simulate_platform.py`.")
w("")

io.open(DST, "w", encoding="utf-8").write("\n".join(out))
print(f"escrito {DST} — {len(out)} lineas")
