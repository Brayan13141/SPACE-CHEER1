HELP_REGISTRY = {
    # ── DASHBOARD ──────────────────────────────────────────────────────────
    ("core:dashboard", "ADMIN"):
        "Panel de administración: gestiona usuarios, pedidos, producción y configuración del sistema.",
    ("core:dashboard", "HEADCOACH"):
        "Tu panel principal: crea pedidos, gestiona tu equipo y sigue el estado de producción.",
    ("core:dashboard", "ATHLETE"):
        "Tu espacio personal: revisa tus pedidos, tus medidas y los próximos eventos del equipo.",
    ("core:dashboard", "GUARDIAN"):
        "Como tutor puedes ver el historial de pedidos de tu atleta y su estado actual.",
    ("core:dashboard", "OPERARIO"):
        "Aquí están tus tareas de producción activas. Completa cada etapa en orden — no puedes saltar una etapa pendiente.",
    ("core:dashboard", "COACH"):
        "Como coach ves a los atletas y equipos bajo tu cargo. Desde aquí puedes gestionar sus medidas.",

    # ── PEDIDOS ────────────────────────────────────────────────────────────
    ("orders:manage_orders", None):
        "Lista de tus pedidos. Cada pedido tiene un estado: Borrador → Pendiente → Diseño aprobado → En producción → Entregado.",
    ("orders:create_order", None):
        "Crea un pedido eligiendo productos del catálogo. Después podrás asignar atletas y capturar medidas.",
    ("orders:detail_order", None):
        "Detalle del pedido: agrega o elimina productos, captura información de contacto y sigue el progreso de producción.",
    ("orders:admin_order_list", "ADMIN"):
        "Vista de todos los pedidos de la plataforma. Puedes avanzar el estado de cualquier pedido desde aquí.",
    ("orders:admin_order_detail", "ADMIN"):
        "Detalle de pedido (vista admin): sube el diseño, actualiza fechas y avanza el estado de producción.",
    ("orders:cart", None):
        "Tu carrito de compras. Revisa los productos seleccionados antes de crear el pedido formal.",
    ("orders:order_item_measurements", None):
        "Captura las medidas de cada atleta para este producto. Las medidas solo pueden editarse mientras estén abiertas.",

    # ── PRODUCCIÓN ─────────────────────────────────────────────────────────
    ("production:dashboard", "OPERARIO"):
        "Tus tareas activas ordenadas por urgencia. Marca cada etapa como completada en secuencia — no puedes adelantar pasos.",
    ("production:admin_overview", "ADMIN"):
        "Vista general de producción: todos los pedidos en proceso, tareas pendientes y operarios activos.",
    ("production:manage_operarios", "ADMIN"):
        "Crea nuevos operarios o asigna el rol a usuarios ya registrados. Los operarios solo ven su panel de tareas.",
    ("production:manage_stages", "ADMIN"):
        "Configura las etapas del proceso de producción (corte, costura, sublimado, etc.) y su orden de ejecución.",
    ("production:manage_roles", "ADMIN"):
        "Define roles de producción y asígnales las etapas que les corresponden.",
    ("production:error_report_list", "ADMIN"):
        "Lista de reportes de error generados en producción. Aquí los revisas y decides si ameritan reposición.",
    ("production:error_report_list", "OPERARIO"):
        "Aquí puedes ver los reportes de error que has enviado y su estado de revisión.",
    ("production:create_error_report", None):
        "Reporta un problema detectado durante la producción: tipo de error, área afectada y acciones correctivas tomadas.",

    # ── EQUIPOS Y PERSONAS ─────────────────────────────────────────────────
    ("teams:manage_teams", "HEADCOACH"):
        "Crea y administra los equipos del club. Cada equipo tiene un código de invitación para que los atletas se unan.",
    ("teams:manage_teams", "ADMIN"):
        "Vista de todos los equipos registrados en la plataforma.",
    ("teams:athlete_team", "ATHLETE"):
        "Tu equipo actual: ve a tus compañeros y el código para invitar a otros.",
    ("teams:manage_athletes", "HEADCOACH"):
        "Lista de todos los atletas del club. Puedes asignarles tutores y ver su estado de onboarding.",
    ("coach:manage_owned_users", "COACH"):
        "Atletas y personal de tu equipo. Desde aquí puedes editar sus medidas y ver su información.",
    ("coach:manage_owned_users", "HEADCOACH"):
        "Todos los usuarios bajo tu cargo: atletas y personal técnico.",

    # ── CATÁLOGO Y PRODUCTOS ───────────────────────────────────────────────
    ("products:catalog", None):
        "Catálogo de uniformes disponibles. Selecciona un producto para agregarlo a un pedido.",
    ("products:list_products", "ADMIN"):
        "Lista de todos los productos configurados. Puedes activar/desactivar, editar tallas y campos de medida.",
    ("products:product_detail", "ADMIN"):
        "Configuración del producto: tallas estándar, campos de medida requeridos y disponibilidad en catálogo.",

    # ── CUENTAS Y ONBOARDING ───────────────────────────────────────────────
    ("accounts:profile_setup", None):
        "Completa tu perfil para acceder a la plataforma. Elige tu rol: Atleta, HeadCoach o Tutor.",
    ("accounts:profile_edit", None):
        "Edita tu información personal: nombre, foto de perfil y datos de contacto.",
    ("accounts:headcoach_approvals", "ADMIN"):
        "Solicitudes de registro de nuevos HeadCoach pendientes de aprobación.",
    ("guardian:dashboard", "GUARDIAN"):
        "Tu panel como tutor: ve el estado de tu atleta, sus pedidos y datos de perfil.",
    ("guardian:headcoach_dashboard", "HEADCOACH"):
        "Resumen de tutores asignados y atletas que aún no tienen tutor vinculado.",
    ("measures:manage_measurement_fields", "ADMIN"):
        "Define qué medidas se capturan para cada producto (talla de pecho, cintura, etc.).",
}


def get_help_text(view_name, user):
    """Return help text for (view_name, user's role). Empty string if no match."""
    if not user or not getattr(user, "is_authenticated", False):
        return ""
    for role in user.roles.values_list("name", flat=True):
        text = HELP_REGISTRY.get((view_name, role))
        if text:
            return text
    return HELP_REGISTRY.get((view_name, None), "")
