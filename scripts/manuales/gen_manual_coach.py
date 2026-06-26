#!/usr/bin/env python3
"""
Genera el Manual de HeadCoach y Coach para Space Cheer.
Usa Playwright (sync API) contra http://127.0.0.1:8000.
Viewport: 1440x900. Salida: manual_coach.pdf (A4).

Cobertura completa:
  HEADCOACH — 18 capturas específicas por URL
  COACH     — 10 capturas específicas por URL
"""
import base64
import sys
from datetime import datetime
from pathlib import Path

from playwright.sync_api import sync_playwright, Page

BASE_URL = "http://127.0.0.1:8000"
OUTPUT_PDF = Path(__file__).parent.parent.parent / "manual_coach.pdf"
LOGO_PATH = Path(__file__).parent.parent.parent / "space_cheer/static/IMAGES/Logo_sin_fondo_blanco.png"

HEADCOACH_USER = "headcoach_test"
HEADCOACH_PASS = "Test1234!"
COACH_USER = "coach_test"
COACH_PASS = "Test1234!"

shots: dict[str, str] = {}   # key -> base64 PNG


def logo_data_uri() -> str:
    if LOGO_PATH.exists():
        with open(LOGO_PATH, "rb") as f:
            return f"data:image/png;base64,{base64.b64encode(f.read()).decode()}"
    return ""


# ─────────────────────────────────────── helpers ──────────────────────────────

def goto(page: Page, path: str, timeout: int = 25_000) -> str:
    """Navigate to path, return page title."""
    url = f"{BASE_URL}{path}"
    try:
        page.goto(url, wait_until="load", timeout=timeout)
        page.wait_for_timeout(1000)
    except Exception as e:
        print(f"  [WARN] goto {path} -> {e}")
    try:
        return page.title()
    except Exception:
        return ""


def snap(page: Page, key: str, *, full_page: bool = True) -> None:
    """Capture screenshot and store as base64."""
    try:
        data = page.screenshot(full_page=full_page)
        shots[key] = base64.b64encode(data).decode()
        print(f"  [snap] {key}")
    except Exception as e:
        print(f"  [WARN] snap {key} -> {e}")


def snap_viewport(page: Page, key: str) -> None:
    """Capture viewport-only screenshot."""
    snap(page, key, full_page=False)


def is_accessible(page: Page, intended_path: str) -> bool:
    """True if page is accessible (not 403/404/500/login redirect/curp redirect)."""
    title = page.title().lower()
    url = page.url.lower()
    if "403" in title or "404" in title or "500" in title:
        return False
    if "accounts/login" in url:
        return False
    if "page not found" in title or "server error" in title:
        return False
    if "curp" in url or "complete-profile" in url or "curp" in title:
        return False
    return True


def img(key: str, caption: str = "", width: str = "100%") -> str:
    """Return <figure> HTML with embedded base64 image."""
    if key not in shots:
        return f'<div class="placeholder">[Captura no disponible: {key}]</div>'
    tag = (
        f'<img src="data:image/png;base64,{shots[key]}" '
        f'alt="{caption}" style="width:{width};border-radius:8px;'
        f'box-shadow:0 4px 16px rgba(0,0,0,.35)">'
    )
    cap = f"<figcaption>{caption}</figcaption>" if caption else ""
    return f'<figure class="sc">{tag}{cap}</figure>'


def login(page: Page, username: str, password: str) -> bool:
    """Login with given credentials. Returns True if successful."""
    page.goto(f"{BASE_URL}/accounts/login/", wait_until="domcontentloaded", timeout=25_000)
    page.wait_for_timeout(1500)
    try:
        page.wait_for_selector('input[name="login"]', timeout=15_000)
        page.fill('input[name="login"]', username)
        page.fill('input[name="password"]', password)
        page.click('button[type="submit"]')
        page.wait_for_load_state("load")
        page.wait_for_timeout(1200)
        return "login" not in page.url.lower()
    except Exception as e:
        print(f"  [ERROR] login {username} -> {e}")
        return False


def logout(page: Page) -> None:
    """Logout and return to a clean state."""
    try:
        page.goto(f"{BASE_URL}/accounts/logout/", wait_until="load", timeout=15_000)
        page.wait_for_timeout(800)
        # Try clicking confirm button if a logout form is shown
        try:
            btn = page.query_selector('button[type="submit"]')
            if btn:
                btn.click()
                page.wait_for_load_state("load")
                page.wait_for_timeout(600)
        except Exception:
            pass
    except Exception:
        pass


# ─────────────────────────── capture helpers ──────────────────────────────────

def capture_url(page: Page, prefix: str, path: str, label: str) -> bool:
    """Navigate to path, snap if accessible. Returns True if accessible."""
    key = f"{prefix}_{path.strip('/').replace('/', '_') or 'home'}"
    goto(page, path)
    ok = is_accessible(page, path)
    if ok:
        snap(page, key)
        print(f"    OK  {path} — {page.title()}")
    else:
        print(f"    --  {path} — DENIED/REDIRECT ({page.title()})")
    return ok


# ─────────────────────── HEADCOACH session ────────────────────────────────────

def capture_headcoach(page: Page) -> dict:
    """Capture all HeadCoach screens. Returns access dict."""
    print("\n[*] === SESIÓN HEADCOACH ===")

    # ── Login screen (before login)
    goto(page, "/accounts/login/")
    snap_viewport(page, "hc_login_screen")

    ok = login(page, HEADCOACH_USER, HEADCOACH_PASS)
    if not ok:
        print("  [ERROR] No se pudo hacer login como headcoach_test")
        return {}

    # Post-login dashboard
    snap(page, "hc_dashboard")
    print("  [snap] hc_dashboard")

    access = {}

    # ── § 1 Dashboard / Home
    print("\n  -- Sección: Dashboard --")
    goto(page, "/")
    access["home"] = is_accessible(page, "/")
    if access["home"]:
        snap(page, "hc_home")

    # ── § 2 Gestión de Equipos
    print("\n  -- Sección: Equipos --")
    goto(page, "/teams/coach/")
    access["teams_coach"] = is_accessible(page, "/teams/coach/")
    if access["teams_coach"]:
        snap(page, "hc_teams_coach")

    goto(page, "/teams/manage_athletes/")
    access["teams_manage_athletes"] = is_accessible(page, "/teams/manage_athletes/")
    if access["teams_manage_athletes"]:
        snap(page, "hc_teams_manage_athletes")

    goto(page, "/teams/16/members/")
    access["teams_16_members"] = is_accessible(page, "/teams/16/members/")
    if access["teams_16_members"]:
        snap(page, "hc_teams_16_members")
    access["teams_members"] = access["teams_16_members"]

    # ── § 3 Pedidos
    print("\n  -- Sección: Pedidos --")
    goto(page, "/orders/")
    access["orders"] = is_accessible(page, "/orders/")
    if access["orders"]:
        snap(page, "hc_orders_list")

    goto(page, "/orders/create/")
    access["orders_create"] = is_accessible(page, "/orders/create/")
    if access["orders_create"]:
        snap(page, "hc_orders_create")

    # Pedido DRAFT
    goto(page, "/orders/17/")
    access["orders_17"] = is_accessible(page, "/orders/17/")
    if access["orders_17"]:
        snap(page, "hc_order_17_draft")

    # Pedido PENDING
    goto(page, "/orders/18/")
    access["orders_18"] = is_accessible(page, "/orders/18/")
    if access["orders_18"]:
        snap(page, "hc_order_18_pending")

    # Pedido DESIGN_APPROVED
    goto(page, "/orders/19/")
    access["orders_19"] = is_accessible(page, "/orders/19/")
    if access["orders_19"]:
        snap(page, "hc_order_19_design_approved")

    # Pedido IN_PRODUCTION
    goto(page, "/orders/20/")
    access["orders_20"] = is_accessible(page, "/orders/20/")
    if access["orders_20"]:
        snap(page, "hc_order_20_in_production")

    # ── § 4 Eventos / Competencias
    print("\n  -- Sección: Eventos --")
    goto(page, "/events/")
    access["events"] = is_accessible(page, "/events/")
    if access["events"]:
        snap(page, "hc_events_list")

    goto(page, "/events/8/")
    access["events_8"] = is_accessible(page, "/events/8/")
    if access["events_8"]:
        snap(page, "hc_events_8_detail")

    goto(page, "/events/8/register/")
    access["events_8_register"] = is_accessible(page, "/events/8/register/")
    if access["events_8_register"]:
        snap(page, "hc_events_8_register")

    goto(page, "/events/my-registrations/")
    access["events_my_registrations"] = is_accessible(page, "/events/my-registrations/")
    if access["events_my_registrations"]:
        snap(page, "hc_events_my_registrations")

    # ── § 5 Hospitalidad
    print("\n  -- Sección: Hospitalidad --")
    goto(page, "/hospitality/event/8/my-stay/")
    access["hospitality_my_stay"] = is_accessible(page, "/hospitality/event/8/my-stay/")
    if access["hospitality_my_stay"]:
        snap(page, "hc_hospitality_my_stay")

    goto(page, "/hospitality/event/8/preferences/")
    access["hospitality_preferences"] = is_accessible(page, "/hospitality/event/8/preferences/")
    if access["hospitality_preferences"]:
        snap(page, "hc_hospitality_preferences")

    # ── § 6 Perfil
    print("\n  -- Sección: Perfil --")
    goto(page, "/accounts/profile/edit/")
    access["profile_edit"] = is_accessible(page, "/accounts/profile/edit/")
    if access["profile_edit"]:
        snap(page, "hc_profile_edit")

    goto(page, "/accounts/profile/settings/")
    access["profile_settings"] = is_accessible(page, "/accounts/profile/settings/")
    if access["profile_settings"]:
        snap(page, "hc_profile_settings")

    print(f"\n  [HeadCoach] Accesibles: {sum(1 for v in access.values() if v)}/{len(access)}")
    return access


# ─────────────────────── COACH session ────────────────────────────────────────

def capture_coach(page: Page) -> dict:
    """Capture all Coach screens. Returns access dict."""
    print("\n[*] === SESIÓN COACH ===")

    # ── Login screen (before login)
    goto(page, "/accounts/login/")
    snap_viewport(page, "coach_login_screen")

    ok = login(page, COACH_USER, COACH_PASS)
    if not ok:
        print("  [ERROR] No se pudo hacer login como coach_test")
        return {}

    # Post-login dashboard
    snap(page, "coach_dashboard")
    print("  [snap] coach_dashboard")

    access = {}

    # ── Dashboard / Home
    print("\n  -- Sección: Dashboard --")
    goto(page, "/")
    access["home"] = is_accessible(page, "/")
    if access["home"]:
        snap(page, "coach_home")

    # ── Equipos
    print("\n  -- Sección: Equipos --")
    goto(page, "/teams/coach/")
    access["teams_coach"] = is_accessible(page, "/teams/coach/")
    if access["teams_coach"]:
        snap(page, "coach_teams_coach")
        # Find the first team's members link and navigate to it
        members_href = page.evaluate("""
            () => {
                const links = document.querySelectorAll('a[href]');
                for (const a of links) {
                    const href = a.getAttribute('href');
                    if (href && /\\/teams\\/\\d+\\/members\\//.test(href)) return href;
                }
                return null;
            }
        """)
        if members_href:
            goto(page, members_href)
            access["teams_members"] = is_accessible(page, members_href)
            if access["teams_members"]:
                snap(page, "coach_teams_members")
                print(f"    OK  {members_href} — {page.title()}")
            else:
                print(f"    --  {members_href} — DENIED")
        else:
            access["teams_members"] = False
            print("    -- No se encontró enlace a miembros del equipo")
    else:
        access["teams_members"] = False

    # ── Pedidos
    print("\n  -- Sección: Pedidos --")
    goto(page, "/orders/")
    access["orders"] = is_accessible(page, "/orders/")
    if access["orders"]:
        snap(page, "coach_orders_list")

    goto(page, "/orders/create/")
    access["orders_create"] = is_accessible(page, "/orders/create/")
    if access["orders_create"]:
        snap(page, "coach_orders_create")

    # ── Eventos
    print("\n  -- Sección: Eventos --")
    goto(page, "/events/")
    access["events"] = is_accessible(page, "/events/")
    if access["events"]:
        snap(page, "coach_events_list")

    goto(page, "/events/8/")
    access["events_8"] = is_accessible(page, "/events/8/")
    if access["events_8"]:
        snap(page, "coach_events_8_detail")

    goto(page, "/events/8/register/")
    access["events_8_register"] = is_accessible(page, "/events/8/register/")
    if access["events_8_register"]:
        snap(page, "coach_events_8_register")

    goto(page, "/events/my-registrations/")
    access["events_my_registrations"] = is_accessible(page, "/events/my-registrations/")
    if access["events_my_registrations"]:
        snap(page, "coach_events_my_registrations")

    # ── Hospitalidad
    print("\n  -- Sección: Hospitalidad --")
    goto(page, "/hospitality/event/8/my-stay/")
    access["hospitality_my_stay"] = is_accessible(page, "/hospitality/event/8/my-stay/")
    if access["hospitality_my_stay"]:
        snap(page, "coach_hospitality_my_stay")

    goto(page, "/hospitality/event/8/preferences/")
    access["hospitality_preferences"] = is_accessible(page, "/hospitality/event/8/preferences/")
    if access["hospitality_preferences"]:
        snap(page, "coach_hospitality_preferences")

    # ── Perfil
    print("\n  -- Sección: Perfil --")
    goto(page, "/accounts/profile/edit/")
    access["profile_edit"] = is_accessible(page, "/accounts/profile/edit/")
    if access["profile_edit"]:
        snap(page, "coach_profile_edit")

    goto(page, "/accounts/profile/settings/")
    access["profile_settings"] = is_accessible(page, "/accounts/profile/settings/")
    if access["profile_settings"]:
        snap(page, "coach_profile_settings")

    print(f"\n  [Coach] Accesibles: {sum(1 for v in access.values() if v)}/{len(access)}")
    return access


# ─────────────────────────────────────── CSS ──────────────────────────────────

CSS = """
*, *::before, *::after { box-sizing: border-box; margin: 0; padding: 0; }
body {
  font-family: 'Segoe UI', system-ui, sans-serif;
  background: #0f172a;
  color: #e2e8f0;
  font-size: 14px;
  line-height: 1.7;
}

/* ─── page breaks ─── */
.page-break { page-break-after: always; break-after: page; }
.avoid-break { page-break-inside: avoid; break-inside: avoid; }

/* ─── cover ─── */
.cover {
  display: flex; flex-direction: column; align-items: center; justify-content: center;
  min-height: 100vh;
  background: linear-gradient(145deg, #0f172a 0%, #1e293b 45%, #0c1f3f 100%);
  text-align: center; padding: 60px 40px;
}
.cover h1 { font-size: 40px; font-weight: 700; color: #f8fafc; margin-bottom: 10px; letter-spacing: -1px; }
.cover .subtitle { font-size: 18px; color: #94a3b8; margin-bottom: 36px; }
.cover .badge {
  display: inline-block;
  background: #059669; color: #fff; border-radius: 9999px;
  padding: 6px 22px; font-size: 12px; font-weight: 700; letter-spacing: 1px;
  margin-bottom: 14px;
}
.cover .date { color: #64748b; font-size: 12px; margin-top: 8px; }
.cover .roles-row {
  display: flex; gap: 24px; justify-content: center; margin: 32px 0 24px;
}
.role-pill {
  background: #1e293b; border: 1px solid #334155; border-radius: 10px;
  padding: 14px 28px; text-align: center;
}
.role-pill .role-icon { font-size: 36px; margin-bottom: 6px; }
.role-pill .role-name { font-size: 15px; font-weight: 700; color: #f8fafc; }
.role-pill .role-sub { font-size: 11px; color: #64748b; margin-top: 2px; }

/* ─── section ─── */
.section { background: #0f172a; padding: 48px 52px; }
.section + .section { border-top: 2px solid #1e293b; }

h2 {
  font-size: 26px; font-weight: 700; color: #059669;
  border-bottom: 2px solid #059669; padding-bottom: 10px; margin-bottom: 26px;
}
h3 {
  font-size: 18px; font-weight: 600; color: #38bdf8;
  margin: 30px 0 12px; border-left: 4px solid #38bdf8; padding-left: 12px;
}
h4 { font-size: 13px; font-weight: 600; color: #94a3b8; margin: 20px 0 6px; text-transform: uppercase; letter-spacing: .6px; }

p { margin-bottom: 12px; color: #cbd5e1; }
ul, ol { color: #cbd5e1; padding-left: 22px; margin-bottom: 12px; }
li { margin-bottom: 6px; }

/* ─── info boxes ─── */
.info-box {
  background: #0f2544; color: #bfdbfe;
  border-left: 5px solid #3b82f6;
  border-radius: 0 8px 8px 0;
  padding: 14px 18px; margin: 18px 0;
}
.info-box strong { color: #93c5fd; }
.warn-box {
  background: #2d1f06; color: #fde68a;
  border-left: 5px solid #f59e0b;
  border-radius: 0 8px 8px 0;
  padding: 14px 18px; margin: 18px 0;
}
.warn-box strong { color: #fbbf24; }
.success-box {
  background: #052e16; color: #bbf7d0;
  border-left: 5px solid #22c55e;
  border-radius: 0 8px 8px 0;
  padding: 14px 18px; margin: 18px 0;
}
.success-box strong { color: #4ade80; }

/* ─── steps ─── */
.steps { counter-reset: step; margin: 18px 0; }
.step {
  counter-increment: step;
  position: relative;
  padding: 12px 12px 12px 54px;
  margin-bottom: 10px;
  background: #1e293b; border-radius: 10px;
  color: #e2e8f0;
}
.step::before {
  content: counter(step);
  position: absolute; left: 12px; top: 50%; transform: translateY(-50%);
  width: 30px; height: 30px; line-height: 30px; text-align: center;
  background: #059669; color: #fff; border-radius: 50%; font-weight: 700; font-size: 13px;
}

/* ─── screenshots ─── */
figure.sc { margin: 18px 0; }
figure.sc img { display: block; width: 100%; border-radius: 8px; box-shadow: 0 4px 20px rgba(0,0,0,.5); }
figure.sc figcaption {
  text-align: center; margin-top: 7px;
  font-size: 11px; color: #64748b; font-style: italic;
}
.placeholder {
  background: #1e293b; border: 1px dashed #334155; border-radius: 8px;
  padding: 24px; text-align: center; color: #475569; font-size: 12px;
  margin: 12px 0;
}

/* ─── comparison grid (2 columns) ─── */
.compare-grid {
  display: grid; grid-template-columns: 1fr 1fr; gap: 20px; margin: 18px 0;
}
.compare-col h4 { margin-top: 0; }
.role-label-hc {
  display: inline-block; background: #1e3a5f; color: #93c5fd;
  border-radius: 6px; padding: 3px 10px; font-size: 11px; font-weight: 700;
  margin-bottom: 8px; letter-spacing: .5px;
}
.role-label-c {
  display: inline-block; background: #1a2e1a; color: #86efac;
  border-radius: 6px; padding: 3px 10px; font-size: 11px; font-weight: 700;
  margin-bottom: 8px; letter-spacing: .5px;
}

/* ─── comparison table ─── */
.cmp-table { width: 100%; border-collapse: collapse; margin: 20px 0; font-size: 13px; }
.cmp-table th {
  background: #1e3a5f; color: #93c5fd;
  padding: 9px 12px; text-align: left; text-transform: uppercase; letter-spacing: .4px;
}
.cmp-table td { padding: 9px 12px; border-bottom: 1px solid #1e293b; color: #cbd5e1; }
.cmp-table tr:nth-child(even) td { background: #0f172a; }
.cmp-table tr:nth-child(odd) td { background: #111827; }
.check { color: #22c55e; font-weight: 700; }
.cross { color: #ef4444; font-weight: 700; }

/* ─── status badges ─── */
.status-badge {
  display: inline-block; border-radius: 9999px; padding: 2px 10px;
  font-size: 11px; font-weight: 700; letter-spacing: .4px;
}
.s-draft    { background: #334155; color: #94a3b8; }
.s-pending  { background: #1e3a5f; color: #93c5fd; }
.s-approved { background: #134e2e; color: #4ade80; }
.s-prod     { background: #3b1f00; color: #fb923c; }
.s-deliver  { background: #1a2e1a; color: #86efac; }
.s-cancel   { background: #3b1212; color: #f87171; }

/* ─── code ─── */
code {
  background: #1e293b; color: #7dd3fc;
  padding: 2px 7px; border-radius: 4px; font-size: 12px; font-family: monospace;
}

/* ─── back cover ─── */
.backcover {
  display: flex; flex-direction: column; align-items: center; justify-content: center;
  min-height: 100vh;
  background: linear-gradient(145deg, #052e16 0%, #0f172a 60%);
  text-align: center; padding: 60px;
}
.backcover h2 { border: none; font-size: 30px; color: #4ade80; margin-bottom: 14px; }
.backcover p { color: #94a3b8; max-width: 500px; font-size: 13px; }
"""


# ─────────────────────────────────────── HTML ─────────────────────────────────

def build_html(hc: dict, c: dict) -> str:
    today = datetime.now().strftime("%d de %B de %Y")

    _logo_uri = logo_data_uri()
    logo_img = (
        f'<img src="{_logo_uri}" alt="Space Cheer" '
        f'style="width:180px;margin-bottom:22px;filter:brightness(0) invert(1)">'
        if _logo_uri else '<div style="font-size:72px;margin-bottom:22px">🏆</div>'
    )

    # ── Comparison table
    SECTION_NAMES = {
        "home": "Dashboard / Inicio",
        "teams_coach": "Mis Equipos",
        "teams_manage_athletes": "Gestión de Atletas (todos)",
        "teams_members": "Miembros del Equipo (propio)",
        "orders": "Lista de Pedidos",
        "orders_create": "Crear Pedido",
        "orders_17": "Pedido #17 (DRAFT)",
        "orders_18": "Pedido #18 (PENDING)",
        "orders_19": "Pedido #19 (DESIGN APPROVED)",
        "orders_20": "Pedido #20 (IN PRODUCTION)",
        "events": "Lista de Eventos",
        "events_8": "Detalle Evento #8",
        "events_8_register": "Registro a Evento",
        "events_my_registrations": "Mis Inscripciones",
        "hospitality_my_stay": "Mi Reservación (Hospitalidad)",
        "hospitality_preferences": "Preferencias de Hospedaje",
        "profile_edit": "Editar Perfil",
        "profile_settings": "Configuración",
    }

    all_keys = list(SECTION_NAMES.keys())
    cmp_rows = ""
    for key in all_keys:
        label = SECTION_NAMES[key]
        hc_ok = hc.get(key, False)
        c_ok = c.get(key, False)
        hc_cell = '<span class="check">&#10003; Sí</span>' if hc_ok else '<span class="cross">&#10007; No</span>'
        c_cell = '<span class="check">&#10003; Sí</span>' if c_ok else '<span class="cross">&#10007; No</span>'
        cmp_rows += f"<tr><td>{label}</td><td>{hc_cell}</td><td>{c_cell}</td></tr>\n"

    return f"""<!DOCTYPE html>
<html lang="es">
<head>
  <meta charset="UTF-8">
  <title>Manual HeadCoach y Coach — Space Cheer</title>
  <style>{CSS}</style>
</head>
<body>

<!-- ═══════════════════════════ PORTADA ═══════════════════════════ -->
<div class="cover page-break">
  {logo_img}
  <div class="badge">DOCUMENTACIÓN INTERNA &nbsp;·&nbsp; ROLES DE COACH</div>
  <h1>Manual de HeadCoach y Coach</h1>
  <p class="subtitle">Guía completa de acceso, navegación y gestión del equipo en Space Cheer</p>
  <div class="roles-row">
    <div class="role-pill">
      <div class="role-icon">👑</div>
      <div class="role-name">HEADCOACH</div>
      <div class="role-sub">Gestión completa de la organización</div>
    </div>
    <div class="role-pill">
      <div class="role-icon">🏅</div>
      <div class="role-name">COACH</div>
      <div class="role-sub">Gestión de su equipo asignado</div>
    </div>
  </div>
  <div class="date">Space Cheer &nbsp;·&nbsp; {today}</div>
</div>

<!-- ═══════════════════════════ § 1 ACCESO ═══════════════════════════ -->
<div class="section page-break">
  <h2>§ 1 &nbsp; Acceso al Sistema</h2>
  <p>
    Tanto el <strong>HeadCoach</strong> como el <strong>Coach</strong> acceden a Space Cheer
    mediante la misma pantalla de inicio de sesión. El sistema asigna los permisos y secciones
    disponibles automáticamente según el rol configurado en la cuenta.
  </p>

  <h3>1.1 Pantalla de inicio de sesión</h3>
  {img("hc_login_screen", "Pantalla de inicio de sesión de Space Cheer", "85%")}

  <div class="steps">
    <div class="step">Abre el navegador y accede a la URL del sistema Space Cheer.</div>
    <div class="step">Escribe tu <strong>nombre de usuario</strong> en el campo correspondiente.</div>
    <div class="step">Escribe tu <strong>contraseña</strong> (distingue mayúsculas y minúsculas).</div>
    <div class="step">Haz clic en <strong>Iniciar Sesión</strong>. El sistema te llevará al dashboard según tu rol.</div>
  </div>

  <div class="warn-box">
    <strong>Atención:</strong> Si ves el mensaje "Credenciales incorrectas", verifica que el
    Bloq Mayús no esté activado. Si el problema persiste, contacta al administrador del sistema.
  </div>

  <div class="info-box">
    <strong>Primera vez:</strong> Si es tu primer acceso, el sistema puede pedirte completar
    tu perfil (nombre completo, foto, datos de contacto) antes de acceder a las secciones del sistema.
    El administrador debe haberte asignado el rol correcto (HEADCOACH o COACH).
  </div>

  <h3>1.2 Dashboard post-login — HeadCoach</h3>
  {img("hc_dashboard", "Dashboard del HeadCoach tras iniciar sesión")}

  <h3>1.3 Dashboard post-login — Coach</h3>
  {img("coach_dashboard", "Dashboard del Coach tras iniciar sesión")}
</div>

<!-- ═══════════════════════════ § 2 COMPARATIVA ═══════════════════════════ -->
<div class="section page-break">
  <h2>§ 2 &nbsp; Comparativa de Acceso: HeadCoach vs. Coach</h2>
  <p>
    La siguiente tabla muestra qué secciones del sistema están disponibles para cada rol.
    El <strong>HeadCoach</strong> tiene acceso completo a la organización, mientras que el
    <strong>Coach</strong> gestiona únicamente su equipo asignado y sus propios pedidos.
  </p>

  <table class="cmp-table">
    <thead>
      <tr>
        <th style="width:50%">Sección</th>
        <th style="width:25%">HeadCoach</th>
        <th style="width:25%">Coach</th>
      </tr>
    </thead>
    <tbody>
      {cmp_rows}
    </tbody>
  </table>

  <h3>2.1 Jerarquía de roles</h3>
  <div class="steps">
    <div class="step"><strong>HEADCOACH</strong> — Gestión de la organización: todos los equipos, coaches, atletas, pedidos y hospitalidad.</div>
    <div class="step"><strong>COACH</strong> — Gestión de su equipo: atletas asignados, pedidos propios y eventos.</div>
    <div class="step"><strong>ATLETA / ACOMPAÑANTE</strong> — Solo lectura de su información personal y medidas.</div>
  </div>

  <div class="info-box">
    <strong>Nota sobre hospitalidad:</strong> Las secciones de reservación y preferencias de hospedaje
    están disponibles para el HeadCoach como responsable de la delegación. El Coach puede ver
    los eventos pero la gestión de estancias la coordina el HeadCoach.
  </div>
</div>

<!-- ═══════════════════════════ § 3 GESTIÓN DE EQUIPOS ═══════════════════════════ -->
<div class="section page-break">
  <h2>§ 3 &nbsp; Gestión de Equipos</h2>
  <p>
    La sección de equipos permite visualizar y administrar los equipos, sus atletas
    y el personal bajo la supervisión del coach.
  </p>

  <h3>3.1 Mis Equipos — HeadCoach</h3>
  <span class="role-label-hc">HEADCOACH</span>
  {img("hc_teams_coach", "Vista de equipos del HeadCoach")}
  <p>
    El HeadCoach ve todos los equipos de su organización, con acceso a la información
    completa de cada uno: membresías, estadísticas y configuración.
  </p>

  <h3>3.2 Mis Equipos — Coach</h3>
  <span class="role-label-c">COACH</span>
  {img("coach_teams_coach", "Vista de equipos del Coach")}
  <p>
    El Coach ve únicamente los equipos en los que está asignado como entrenador.
  </p>

  <h3>3.3 Gestión de Atletas (HeadCoach)</h3>
  <span class="role-label-hc">HEADCOACH</span>
  {img("hc_teams_manage_athletes", "Pantalla de gestión de atletas — HeadCoach")}
  <p>
    El HeadCoach puede ver y administrar todos los atletas de la organización:
    editar perfiles, reasignar equipos y gestionar documentación.
  </p>

  <h3>3.4 Miembros del Equipo</h3>
  <p>
    Tanto el HeadCoach como el Coach pueden ver los miembros de su equipo propio.
    El Coach solo accede al equipo del que es responsable; el HeadCoach puede acceder a cualquier equipo de la organización.
  </p>
  <div class="compare-grid">
    <div class="compare-col">
      <span class="role-label-hc">HEADCOACH</span>
      {img("hc_teams_16_members", "Lista de miembros del equipo — HeadCoach")}
    </div>
    <div class="compare-col">
      <span class="role-label-c">COACH</span>
      {img("coach_teams_members", "Lista de miembros del equipo — Coach")}
    </div>
  </div>

  <div class="steps">
    <div class="step">Ve a <strong>Mis Equipos</strong> y selecciona el equipo que deseas administrar.</div>
    <div class="step">Haz clic en <strong>Ver Miembros</strong> para acceder al listado completo.</div>
    <div class="step">Selecciona un miembro para editar su información, medidas o estado.</div>
    <div class="step">Usa el código de invitación del equipo para agregar nuevos miembros.</div>
  </div>

  <div class="warn-box">
    <strong>Exclusivo HeadCoach:</strong> La sección <em>Gestión de Atletas</em> (vista global de todos los atletas)
    no está disponible para el rol Coach. El Coach gestiona a sus atletas únicamente desde la vista de su equipo asignado.
  </div>
</div>

<!-- ═══════════════════════════ § 4 GESTIÓN DE PEDIDOS ═══════════════════════════ -->
<div class="section page-break">
  <h2>§ 4 &nbsp; Gestión de Pedidos del Equipo</h2>
  <p>
    La sección de <strong>Pedidos</strong> es el corazón del sistema. Aquí gestionas
    los pedidos de uniformes y artículos para tu equipo. Cada pedido sigue un ciclo
    de vida definido con estados progresivos.
  </p>

  <h3>4.1 Lista de Pedidos — Comparativa</h3>
  <div class="compare-grid">
    <div class="compare-col">
      <span class="role-label-hc">HEADCOACH</span>
      {img("hc_orders_list", "Lista de pedidos — HeadCoach")}
    </div>
    <div class="compare-col">
      <span class="role-label-c">COACH</span>
      {img("coach_orders_list", "Lista de pedidos — Coach")}
    </div>
  </div>
  <p>
    El HeadCoach ve todos los pedidos de su organización. El Coach ve únicamente
    los pedidos de su equipo asignado.
  </p>

  <h3>4.2 Ciclo de Vida de un Pedido</h3>
  <table class="cmp-table">
    <thead>
      <tr><th>Estado</th><th>Descripción</th><th>Medidas</th></tr>
    </thead>
    <tbody>
      <tr>
        <td><span class="status-badge s-draft">DRAFT</span></td>
        <td>El pedido está en construcción. Puedes agregar/quitar productos.</td>
        <td>Editables</td>
      </tr>
      <tr>
        <td><span class="status-badge s-pending">PENDING</span></td>
        <td>Pedido enviado para revisión de diseño.</td>
        <td>Editables si están abiertas</td>
      </tr>
      <tr>
        <td><span class="status-badge s-approved">DESIGN APPROVED</span></td>
        <td>El diseño fue aceptado. Las medidas quedan bloqueadas.</td>
        <td><strong>Bloqueadas</strong></td>
      </tr>
      <tr>
        <td><span class="status-badge s-prod">IN PRODUCTION</span></td>
        <td>El pedido está siendo fabricado en taller.</td>
        <td>Bloqueadas</td>
      </tr>
      <tr>
        <td><span class="status-badge s-deliver">DELIVERED</span></td>
        <td>El pedido fue recibido por el equipo.</td>
        <td>Bloqueadas</td>
      </tr>
      <tr>
        <td><span class="status-badge s-cancel">CANCELLED</span></td>
        <td>El pedido fue cancelado.</td>
        <td>N/A</td>
      </tr>
    </tbody>
  </table>

  <div class="warn-box">
    <strong>Importante:</strong> Una vez que un pedido avanza a <em>DESIGN APPROVED</em>,
    las medidas quedan <strong>bloqueadas permanentemente</strong>. No podrás modificarlas
    sin contactar al administrador del sistema.
  </div>

  <h3>4.3 Pedido en estado DRAFT (Borrador)</h3>
  <span class="role-label-hc">HEADCOACH</span>
  {img("hc_order_17_draft", "Detalle del pedido #17 en estado DRAFT")}
  <p>
    En estado DRAFT puedes modificar el pedido libremente: agregar/quitar líneas,
    editar medidas de atletas y actualizar cantidades.
  </p>

  <h3>4.4 Pedido en estado PENDING</h3>
  {img("hc_order_18_pending", "Detalle del pedido #18 en estado PENDING")}

  <h3>4.5 Pedido con DESIGN APPROVED</h3>
  {img("hc_order_19_design_approved", "Detalle del pedido #19 con diseño aprobado")}
  <p>
    Las medidas aparecen bloqueadas en este estado. El diseño del uniforme ha sido
    confirmado y no puede modificarse sin autorización especial.
  </p>

  <h3>4.6 Pedido IN PRODUCTION</h3>
  {img("hc_order_20_in_production", "Detalle del pedido #20 en producción")}

  <h3>4.7 Crear un Pedido</h3>
  <div class="compare-grid">
    <div class="compare-col">
      <span class="role-label-hc">HEADCOACH</span>
      {img("hc_orders_create", "Formulario de creación de pedido — HeadCoach")}
    </div>
    <div class="compare-col">
      <span class="role-label-c">COACH</span>
      {img("coach_orders_create", "Formulario de creación de pedido — Coach")}
    </div>
  </div>

  <div class="steps">
    <div class="step">Ve a <strong>Pedidos</strong> y haz clic en <strong>"+ Crear Pedido"</strong>.</div>
    <div class="step">Selecciona el equipo para el cual es el pedido.</div>
    <div class="step">Agrega los productos deseados desde el catálogo.</div>
    <div class="step">Asigna atletas a cada línea del pedido e introduce sus medidas.</div>
    <div class="step">Revisa el resumen y haz clic en <strong>Enviar</strong> para mover el pedido a PENDING.</div>
  </div>

  <div class="info-box">
    <strong>Importar atletas del equipo:</strong> En la vista de detalle del ítem, usa el
    botón <em>"Importar atletas del equipo"</em> para cargar automáticamente todos los
    atletas del equipo, evitando agregarlos uno por uno.
  </div>
</div>

<!-- ═══════════════════════════ § 5 EVENTOS Y COMPETENCIAS ═══════════════════════════ -->
<div class="section page-break">
  <h2>§ 5 &nbsp; Competencias y Eventos</h2>
  <p>
    La sección de <strong>Eventos</strong> muestra las competencias disponibles y permite
    registrar al equipo en los torneos activos con registro abierto.
  </p>

  <h3>5.1 Lista de Eventos — Comparativa</h3>
  <div class="compare-grid">
    <div class="compare-col">
      <span class="role-label-hc">HEADCOACH</span>
      {img("hc_events_list", "Lista de eventos — HeadCoach")}
    </div>
    <div class="compare-col">
      <span class="role-label-c">COACH</span>
      {img("coach_events_list", "Lista de eventos — Coach")}
    </div>
  </div>

  <h3>5.2 Detalle del Evento — Grand Prix Espacial (pk=8)</h3>
  <div class="compare-grid">
    <div class="compare-col">
      <span class="role-label-hc">HEADCOACH</span>
      {img("hc_events_8_detail", "Detalle del Grand Prix Espacial — HeadCoach")}
    </div>
    <div class="compare-col">
      <span class="role-label-c">COACH</span>
      {img("coach_events_8_detail", "Detalle del Grand Prix Espacial — Coach")}
    </div>
  </div>
  <p>
    El detalle del evento muestra: fechas, sede, categorías disponibles, reglamento
    y el estado del registro (REGISTRATION_OPEN, COMPLETED, etc.).
  </p>

  <h3>5.3 Registro del Equipo al Evento</h3>
  <div class="compare-grid">
    <div class="compare-col">
      <span class="role-label-hc">HEADCOACH</span>
      {img("hc_events_8_register", "Pantalla de registro al evento — HeadCoach")}
    </div>
    <div class="compare-col">
      <span class="role-label-c">COACH</span>
      {img("coach_events_8_register", "Pantalla de registro al evento — Coach")}
    </div>
  </div>

  <div class="steps">
    <div class="step">Ve a <strong>Eventos</strong> y selecciona el evento al que deseas registrar tu equipo.</div>
    <div class="step">Verifica que el evento tenga estado <strong>REGISTRATION_OPEN</strong>.</div>
    <div class="step">Haz clic en <strong>Registrar Equipo</strong>.</div>
    <div class="step">Selecciona la categoría y los atletas que participarán.</div>
    <div class="step">Confirma el registro. El sistema enviará una confirmación.</div>
  </div>

  <div class="warn-box">
    <strong>Fechas límite:</strong> Cada evento tiene una fecha de cierre de registro.
    Pasada esa fecha, el botón de registro se desactiva automáticamente.
  </div>

  <h3>5.4 Mis Inscripciones</h3>
  <div class="compare-grid">
    <div class="compare-col">
      <span class="role-label-hc">HEADCOACH</span>
      {img("hc_events_my_registrations", "Vista mis inscripciones — HeadCoach")}
    </div>
    <div class="compare-col">
      <span class="role-label-c">COACH</span>
      {img("coach_events_my_registrations", "Vista mis inscripciones — Coach")}
    </div>
  </div>
  <p>
    Esta sección muestra el historial de registros del equipo a eventos pasados y futuros,
    con su estado actual (confirmado, pendiente, cancelado).
  </p>
</div>

<!-- ═══════════════════════════ § 6 HOSPITALIDAD ═══════════════════════════ -->
<div class="section page-break">
  <h2>§ 6 &nbsp; Hospitalidad y Alojamiento</h2>
  <p>
    El módulo de <strong>Hospitalidad</strong> permite gestionar las reservaciones de hospedaje
    para los eventos que incluyen servicio de alojamiento integrado.
    Tanto el <strong>HeadCoach</strong> como el <strong>Coach</strong> tienen acceso a su propia reservación y preferencias.
  </p>

  <h3>6.1 Mi Reservación en el Evento</h3>
  <div class="compare-grid">
    <div class="compare-col">
      <span class="role-label-hc">HEADCOACH</span>
      {img("hc_hospitality_my_stay", "Mi reservación de hospedaje — HeadCoach")}
    </div>
    <div class="compare-col">
      <span class="role-label-c">COACH</span>
      {img("coach_hospitality_my_stay", "Mi reservación de hospedaje — Coach")}
    </div>
  </div>
  <p>
    Esta pantalla muestra el detalle de tu reservación para el evento seleccionado:
    habitación asignada, fechas de check-in/check-out y estado de la reserva.
  </p>

  <h3>6.2 Preferencias de Hospedaje</h3>
  <div class="compare-grid">
    <div class="compare-col">
      <span class="role-label-hc">HEADCOACH</span>
      {img("hc_hospitality_preferences", "Preferencias de hospedaje — HeadCoach")}
    </div>
    <div class="compare-col">
      <span class="role-label-c">COACH</span>
      {img("coach_hospitality_preferences", "Preferencias de hospedaje — Coach")}
    </div>
  </div>
  <p>
    Antes de que el sistema asigne habitaciones, puedes configurar tus preferencias:
    tipo de habitación, requerimientos especiales, dieta, accesibilidad y horarios estimados.
  </p>

  <div class="steps">
    <div class="step">Ve a <strong>Eventos</strong> y selecciona el evento con hospitalidad incluida.</div>
    <div class="step">Accede a <strong>Mi Reservación</strong> para ver el estado actual de tu hospedaje.</div>
    <div class="step">Si el sistema lo permite, configura tus <strong>Preferencias</strong> antes de la fecha límite.</div>
    <div class="step">Una vez asignado el hospedaje, recibirás notificación con los detalles de tu habitación.</div>
  </div>

  <div class="info-box">
    <strong>Nota:</strong> La gestión de hospedaje solo está disponible para eventos que
    incluyen el servicio de hospitalidad integrado. No todos los eventos cuentan con
    esta funcionalidad. Las reservaciones son confirmadas por el administrador del evento.
  </div>
</div>

<!-- ═══════════════════════════ § 7 PERFIL Y CONFIGURACIÓN ═══════════════════════════ -->
<div class="section page-break">
  <h2>§ 7 &nbsp; Perfil y Configuración de Cuenta</h2>
  <p>
    Ambos roles pueden gestionar su perfil personal y configurar sus preferencias de cuenta.
  </p>

  <h3>7.1 Editar Perfil — Comparativa</h3>
  <div class="compare-grid">
    <div class="compare-col">
      <span class="role-label-hc">HEADCOACH</span>
      {img("hc_profile_edit", "Edición de perfil — HeadCoach")}
    </div>
    <div class="compare-col">
      <span class="role-label-c">COACH</span>
      {img("coach_profile_edit", "Edición de perfil — Coach")}
    </div>
  </div>

  <p>
    En el perfil puedes actualizar: foto de perfil, nombre completo, datos de contacto,
    información del equipo y otros datos relevantes para el sistema.
  </p>

  <div class="steps">
    <div class="step">Haz clic en tu avatar (esquina superior derecha) y selecciona <strong>Mi Perfil</strong>.</div>
    <div class="step">Edita los campos que deseas actualizar.</div>
    <div class="step">Haz clic en <strong>Guardar cambios</strong> para confirmar.</div>
  </div>

  <h3>7.2 Configuración de Cuenta — Comparativa</h3>
  <div class="compare-grid">
    <div class="compare-col">
      <span class="role-label-hc">HEADCOACH</span>
      {img("hc_profile_settings", "Configuración de cuenta — HeadCoach")}
    </div>
    <div class="compare-col">
      <span class="role-label-c">COACH</span>
      {img("coach_profile_settings", "Configuración de cuenta — Coach")}
    </div>
  </div>

  <p>
    En la configuración puedes gestionar: cambio de contraseña, preferencias de notificaciones,
    privacidad de datos y otros ajustes de seguridad.
  </p>

  <div class="info-box">
    <strong>Seguridad:</strong> Se recomienda usar una contraseña de al menos 12 caracteres
    con combinación de letras, números y símbolos. Cambia tu contraseña periódicamente y
    nunca la compartas con terceros.
  </div>

  <h3>7.3 Cerrar Sesión</h3>
  <div class="steps">
    <div class="step">Haz clic en tu avatar en la esquina superior derecha.</div>
    <div class="step">Selecciona <strong>Cerrar Sesión</strong> en el menú desplegable.</div>
    <div class="step">Confirma si el sistema lo solicita. Serás redirigido a la pantalla de login.</div>
  </div>

  <div class="warn-box">
    <strong>Importante:</strong> Siempre cierra sesión cuando uses un equipo compartido o público.
    No cierres el navegador directamente sin hacer logout primero.
  </div>
</div>

<!-- ═══════════════════════════ CONTRAPORTADA ═══════════════════════════ -->
<div class="backcover">
  {logo_img}
  <h2>Space Cheer</h2>
  <p>
    Manual de roles: HeadCoach y Coach.<br>
    Este documento es de uso interno y confidencial.<br>
    Generado automáticamente el {today}.
  </p>
  <p style="margin-top:20px; font-size:12px; color:#475569;">
    Para soporte técnico o acceso al sistema, contacta al administrador.
  </p>
</div>

</body>
</html>
"""


# ─────────────────────────────────────── main ─────────────────────────────────

def main():
    print("[*] Iniciando generación del Manual de Coach/HeadCoach...")
    print(f"    Base URL : {BASE_URL}")
    print(f"    Salida   : {OUTPUT_PDF}\n")

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)

        def new_ctx():
            return browser.new_context(
                viewport={"width": 1440, "height": 900},
                ignore_https_errors=True,
                extra_http_headers={"X-Forwarded-Proto": "https"},
            )

        # ── HeadCoach — contexto aislado
        ctx_hc = new_ctx()
        page_hc = ctx_hc.new_page()
        hc_access = capture_headcoach(page_hc)
        ctx_hc.close()

        # ── Coach — contexto aislado
        ctx_c = new_ctx()
        page_c = ctx_c.new_page()
        c_access = capture_coach(page_c)
        ctx_c.close()

        # ── Construir HTML
        print("\n[*] Construyendo HTML...")
        html = build_html(hc_access, c_access)

        # ── Renderizar PDF (contexto limpio)
        print("[*] Renderizando PDF...")
        ctx_pdf = new_ctx()
        pdf_page = ctx_pdf.new_page()
        pdf_page.set_content(html, wait_until="networkidle")
        pdf_page.wait_for_timeout(2000)
        pdf_page.pdf(
            path=str(OUTPUT_PDF),
            format="A4",
            print_background=True,
            margin={"top": "10mm", "right": "10mm", "bottom": "10mm", "left": "10mm"},
        )

        browser.close()

    size = OUTPUT_PDF.stat().st_size
    print(f"\n[OK] PDF generado: {OUTPUT_PDF}")
    print(f"     Tamaño: {size:,} bytes ({size / 1024 / 1024:.2f} MB)")
    print(f"     Screenshots capturados: {len(shots)}")

    hc_ok = sum(1 for v in hc_access.values() if v)
    c_ok = sum(1 for v in c_access.values() if v)
    print(f"     Páginas accesibles — HeadCoach: {hc_ok}/{len(hc_access)}  | Coach: {c_ok}/{len(c_access)}")


if __name__ == "__main__":
    main()
