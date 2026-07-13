# -*- coding: utf-8 -*-
"""
Helper compartido para los generadores de manuales (gen_manual_*.py).

Provee capture_with_button(): antes de capturar la pantalla destino, primero
navega a la pantalla "origen" (donde vive el botón/link que lleva a ese
destino), lo resalta visualmente con un recuadro rojo y toma una captura
extra (<filename>_boton.png). Si no encuentra el link, sigue de largo y
captura solo la pantalla destino, sin fallar el manual completo.
"""
import time
from pathlib import Path

_HIGHLIGHT_JS = """
async (args) => {
    const targetPath = args.targetPath;
    const textHint = (args.textHint || "").toLowerCase();
    const links = Array.from(document.querySelectorAll('a[href]'));

    // Normaliza quitando querystring y la barra final, para comparar rutas
    // "de verdad" en vez de solo texto — así "/orders/" no hace match falso
    // contra "/orders/cart/" (que también empieza con "/orders/").
    const norm = (u) => (u || "").split("?")[0].replace(/\\/+$/, "");
    const targetNorm = norm(targetPath);

    // 1) Match exacto de ruta (ignorando querystring/slash final) — el más confiable.
    let el = links.find(a => norm(a.getAttribute('href') || "") === targetNorm);

    // 2) Match exacto incluyendo querystring (para casos tipo ?type=OFFLINE).
    if (!el) {
        el = links.find(a => (a.getAttribute('href') || "") === targetPath);
    }

    // 3) href == targetPath + querystring/hash propios (mismo recurso, con params).
    if (!el) {
        el = links.find(a => {
            const href = a.getAttribute('href') || "";
            if (!href || norm(href) !== targetNorm) return false;
            const rest = href.slice(norm(href).length);
            return rest === "" || rest.startsWith("?") || rest.startsWith("#");
        });
    }

    // 4) Último recurso: coincidencia de texto visible (menos preciso que la
    // ruta, pero mejor que adivinar por un substring de href ambiguo).
    if (!el && textHint) {
        el = links.find(a => a.textContent.trim().toLowerCase().indexOf(textHint) !== -1);
    }

    if (!el) return false;

    const isVisible = (node) => {
        if (!node) return false;
        const rect = node.getBoundingClientRect();
        return rect.width > 0 && rect.height > 0 && node.offsetParent !== null;
    };

    // Si el link vive dentro de uno o varios dropdowns/submenús cerrados
    // (Bootstrap estándar, o un toggle custom con <button>+d-none como el
    // submenú de "Config. Producción"), resaltarlo no sirve de nada — hay
    // que abrir cada nivel primero, de afuera hacia adentro, igual que
    // haría un usuario real haciendo clic paso a paso.
    if (!isVisible(el)) {
        const toggles = [];
        let node = el.parentElement;
        for (let i = 0; i < 8 && node; i++) {
            let t = node.querySelector(':scope > .dropdown-toggle, :scope > a.dropdown-toggle');
            if (!t) {
                const prevSibling = node.previousElementSibling;
                if (prevSibling) {
                    t = prevSibling.matches('.dropdown-toggle, button')
                        ? prevSibling
                        : prevSibling.querySelector('.dropdown-toggle, button');
                }
            }
            if (t && toggles.indexOf(t) === -1) toggles.push(t);
            node = node.parentElement;
        }
        // Los toggles más lejanos (contenedores externos) deben abrirse
        // primero para que los internos siquiera existan visibles en el DOM.
        toggles.reverse();
        for (const t of toggles) {
            t.click();
            await new Promise(r => setTimeout(r, 200));
        }
    }

    if (!isVisible(el)) return false;

    el.scrollIntoView({ block: 'center', inline: 'center' });
    el.setAttribute('data-manual-highlight', '1');
    el.style.outline = '4px solid #ef4444';
    el.style.outlineOffset = '3px';
    el.style.boxShadow = '0 0 0 8px rgba(239,68,68,0.35), 0 0 24px 6px rgba(239,68,68,0.65)';
    el.style.borderRadius = '6px';
    if (!el.style.position || el.style.position === 'static') {
        el.style.position = 'relative';
    }
    el.style.zIndex = '9999';
    return true;
}
"""

_CLEAR_JS = """
() => {
    document.querySelectorAll('[data-manual-highlight]').forEach(el => {
        el.style.outline = '';
        el.style.boxShadow = '';
        el.removeAttribute('data-manual-highlight');
    });
}
"""


def find_and_highlight(page, target_url_path, link_text_hint=None):
    """Busca un <a> en la página actual que apunte a target_url_path
    (o, si no lo encuentra, cuyo texto visible coincida con link_text_hint)
    y le agrega un resaltado visual. Devuelve True si encontró algo."""
    try:
        return bool(page.evaluate(_HIGHLIGHT_JS, {
            "targetPath": target_url_path,
            "textHint": link_text_hint or "",
        }))
    except Exception:
        return False


def clear_highlight(page):
    try:
        page.evaluate(_CLEAR_JS)
    except Exception:
        pass


def capture_with_button(page, base_url, screenshots_dir, from_path, to_path,
                         filename, link_text_hint=None, wait_ms=900):
    """
    1. Navega a from_path y busca+resalta el link que lleva a to_path.
    2. Si lo encuentra, captura <filename>_boton.png.
    3. Navega a to_path y captura <filename>.png (captura normal).

    Devuelve un dict:
      {
        "ok": bool,            # si la captura destino fue exitosa
        "path": str,           # ruta de la captura destino (o mensaje de error)
        "button_ok": bool,     # si se encontró y resaltó el botón de origen
        "button_path": str|None,
      }
    """
    screenshots_dir = Path(screenshots_dir)
    button_ok, button_path = False, None

    if from_path:
        try:
            page.goto(f"{base_url}{from_path}", wait_until="load", timeout=30000)
            time.sleep(wait_ms / 1000)
            if find_and_highlight(page, to_path, link_text_hint):
                time.sleep(0.3)
                button_screenshot = screenshots_dir / f"{filename}_boton.png"
                page.screenshot(path=str(button_screenshot), full_page=True)
                button_ok, button_path = True, str(button_screenshot)
                clear_highlight(page)
        except Exception:
            pass

    try:
        response = page.goto(f"{base_url}{to_path}", wait_until="load", timeout=30000)
        time.sleep(wait_ms / 1000)
        status = response.status if response else 0

        if status in (404, 403, 500):
            return {"ok": False, "path": f"HTTP {status}",
                    "button_ok": button_ok, "button_path": button_path}

        if "/accounts/login/" in page.url or "/login/" in page.url:
            return {"ok": False, "path": "Redirigido al login — sesion perdida",
                    "button_ok": button_ok, "button_path": button_path}

        dest_screenshot = screenshots_dir / f"{filename}.png"
        page.screenshot(path=str(dest_screenshot), full_page=True)
        return {"ok": True, "path": str(dest_screenshot),
                "button_ok": button_ok, "button_path": button_path}
    except Exception as e:
        return {"ok": False, "path": str(e)[:150],
                "button_ok": button_ok, "button_path": button_path}
