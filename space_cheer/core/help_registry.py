from django.utils.translation import gettext_lazy as _

# Registry mapping (view_name, role_or_None) -> list of help cards (list[str]).
# Each card is one tip shown as a slide in the help modal carousel.
# Role-specific entries take precedence over the None-keyed fallback.
HELP_REGISTRY = {
    # ── DASHBOARD ──────────────────────────────────────────────────────────
    ("core:dashboard", "ADMIN"): [
        _("Panel de administración: gestiona usuarios, pedidos, producción y configuración del sistema."),
        _("Desde aquí apruebas HeadCoaches, gestionas operarios y revisas los reportes de error de producción."),
    ],
    ("core:dashboard", "HEADCOACH"): [
        _("Tu panel principal: crea pedidos, gestiona tu equipo y sigue el estado de producción."),
        _("Invita atletas con el código de equipo y revisa que completen sus medidas a tiempo."),
    ],
    ("core:dashboard", "ATHLETE"): [
        _("Tu espacio personal: revisa tus pedidos, tus medidas y los próximos eventos del equipo."),
        _("Mantén tus medidas actualizadas: solo puedes editarlas mientras el pedido las tenga abiertas."),
    ],
    ("core:dashboard", "GUARDIAN"): [
        _("Como tutor puedes ver el historial de pedidos de tu atleta y su estado actual."),
        _("También revisas sus datos de perfil y autorizas la información requerida para competencias."),
    ],
    ("core:dashboard", "OPERARIO"): [
        _("Aquí están tus tareas de producción activas. Completa cada etapa en orden — no puedes saltar una etapa pendiente."),
        _("Si detectas un problema en una prenda, genera un reporte de error desde la tarea correspondiente."),
    ],
    ("core:dashboard", "COACH"): [
        _("Como coach ves a los atletas y equipos bajo tu cargo. Desde aquí puedes gestionar sus medidas."),
        _("Revisa el estado de onboarding de tus atletas para asegurarte de que su perfil esté completo."),
    ],

    # ── COMPETENCIAS / EVENTS ──────────────────────────────────────────────
    ("events:event_list", None): [
        _("¿Qué es una competencia? Un evento donde los equipos presentan sus rutinas ante jueces calificados."),
        _("¿Cómo funciona? Regístrate, asigna tu equipo y sigue los resultados en tiempo real."),
        _("Las competencias se organizan en categorías según el nivel y el tipo de equipo."),
    ],
    ("events:event_detail", None): [
        _("Detalle del evento: fechas, sede, categorías disponibles y equipos ya registrados."),
        _("Para participar, registra tu equipo desde aquí antes de que cierre la inscripción."),
    ],
    ("events:event_create", "ADMIN"): [
        _("Crea un evento definiendo nombre, fechas, sede y las categorías que estarán disponibles."),
        _("Después configura los criterios de calificación y asigna a los jueces que evaluarán."),
    ],

    # ── COMUNIDAD / SOCIAL ─────────────────────────────────────────────────
    ("social:send_invite", None): [
        _("Invita a nuevas personas a la comunidad de Space Cheer enviándoles una invitación."),
        _("La persona invitada recibe un enlace para registrarse y unirse a la plataforma."),
    ],

    # ── HOSPEDAJE / HOSPITALITY ────────────────────────────────────────────
    ("hospitality:index", None): [
        _("El hospedaje organiza los hoteles y habitaciones para los equipos durante las competencias."),
        _("Desde aquí accedes a los hoteles del evento y a la gestión de estancias."),
    ],
    ("hospitality:hotel_list", "ADMIN"): [
        _("Gestiona los hoteles disponibles para el evento: agrega, edita y configura sus habitaciones."),
        _("Asigna tipos de habitación y camas para poder distribuir a los participantes después."),
    ],
    ("hospitality:my_stay", None): [
        _("Aquí ves tus datos de hospedaje: hotel asignado, habitación y compañeros de cuarto."),
        _("Revisa tu información de check-in y las fechas de entrada y salida de tu estancia."),
    ],

    # ── PEDIDOS ────────────────────────────────────────────────────────────
    ("orders:manage_orders", None): [
        _("Lista de tus pedidos. Cada pedido sigue un estado: Borrador → Pendiente → Diseño aprobado → En producción → Entregado."),
        _("Abre un pedido para ver su detalle, agregar productos o capturar medidas de los atletas."),
    ],
    ("orders:create_order", None): [
        _("Crea un pedido eligiendo productos del catálogo."),
        _("Después podrás asignar atletas a cada producto y capturar sus medidas."),
    ],
    ("orders:detail_order", None): [
        _("Detalle del pedido: agrega o elimina productos y captura la información de contacto."),
        _("Sigue el progreso de producción etapa por etapa hasta la entrega final."),
    ],
    ("orders:admin_order_list", "ADMIN"): [
        _("Vista de todos los pedidos de la plataforma."),
        _("Puedes avanzar el estado de cualquier pedido y dar seguimiento a la producción global."),
    ],
    ("orders:admin_order_detail", "ADMIN"): [
        _("Detalle de pedido (vista admin): sube el diseño y actualiza las fechas clave."),
        _("Avanza el estado de producción usando siempre las transiciones permitidas."),
    ],
    ("orders:cart", None): [
        _("Tu carrito de compras con los productos que has seleccionado."),
        _("Revisa las cantidades antes de convertirlo en un pedido formal."),
    ],
    ("orders:order_item_measurements", None): [
        _("Captura las medidas de cada atleta para este producto."),
        _("Las medidas solo pueden editarse mientras estén abiertas; una vez cerradas quedan bloqueadas."),
    ],

    # ── PRODUCCIÓN ─────────────────────────────────────────────────────────
    ("production:dashboard", "OPERARIO"): [
        _("Tus tareas activas ordenadas por urgencia."),
        _("Marca cada etapa como completada en secuencia — no puedes adelantar pasos pendientes."),
    ],
    ("production:admin_overview", "ADMIN"): [
        _("Vista general de producción: todos los pedidos en proceso y sus tareas pendientes."),
        _("Identifica cuellos de botella revisando qué operarios tienen tareas activas."),
    ],
    ("production:manage_operarios", "ADMIN"): [
        _("Crea nuevos operarios o asigna el rol a usuarios ya registrados."),
        _("Los operarios solo ven su panel de tareas; aquí controlas quién tiene acceso."),
    ],
    ("production:manage_stages", "ADMIN"): [
        _("Configura las etapas del proceso de producción (corte, costura, sublimado, etc.)."),
        _("El orden de las etapas define la secuencia que los operarios deben seguir."),
    ],
    ("production:manage_roles", "ADMIN"): [
        _("Define roles de producción y asígnales las etapas que les corresponden."),
        _("Así cada operario solo recibe las tareas de las etapas para las que está habilitado."),
    ],
    ("production:error_report_list", "ADMIN"): [
        _("Lista de reportes de error generados en producción."),
        _("Revísalos y decide si ameritan reposición o corrección de la prenda."),
    ],
    ("production:error_report_list", "OPERARIO"): [
        _("Aquí ves los reportes de error que has enviado."),
        _("Da seguimiento a su estado de revisión por parte del administrador."),
    ],
    ("production:create_error_report", None): [
        _("Reporta un problema detectado durante la producción: tipo de error y área afectada."),
        _("Describe las acciones correctivas tomadas para que el administrador pueda evaluarlas."),
    ],

    # ── EQUIPOS Y PERSONAS ─────────────────────────────────────────────────
    ("teams:manage_teams", "HEADCOACH"): [
        _("Crea y administra los equipos del club."),
        _("Cada equipo tiene un código de invitación para que los atletas se unan."),
    ],
    ("teams:manage_teams", "ADMIN"): [
        _("Vista de todos los equipos registrados en la plataforma."),
        _("Desde aquí supervisas la estructura de equipos de todos los clubes."),
    ],
    ("teams:athlete_team", "ATHLETE"): [
        _("Tu equipo actual: revisa a tus compañeros de equipo."),
        _("Comparte el código de invitación para que otros atletas se unan."),
    ],
    ("teams:manage_athletes", "HEADCOACH"): [
        _("Lista de todos los atletas del club."),
        _("Puedes asignarles tutores y revisar su estado de onboarding."),
    ],
    ("coach:manage_owned_users", "COACH"): [
        _("Atletas y personal de tu equipo."),
        _("Desde aquí puedes editar sus medidas y ver su información."),
    ],
    ("coach:manage_owned_users", "HEADCOACH"): [
        _("Todos los usuarios bajo tu cargo: atletas y personal técnico."),
        _("Gestiona sus datos y mantén su información de perfil al día."),
    ],

    # ── CATÁLOGO Y PRODUCTOS ───────────────────────────────────────────────
    ("products:catalog", None): [
        _("Catálogo de uniformes disponibles."),
        _("Selecciona un producto para agregarlo a un pedido."),
    ],
    ("products:list_products", "ADMIN"): [
        _("Lista de todos los productos configurados."),
        _("Puedes activar o desactivar productos y editar sus tallas y campos de medida."),
    ],
    ("products:product_detail", "ADMIN"): [
        _("Configuración del producto: tallas estándar y campos de medida requeridos."),
        _("Define su disponibilidad en catálogo y las reglas de medición."),
    ],

    # ── CUENTAS Y ONBOARDING ───────────────────────────────────────────────
    ("accounts:profile_setup", None): [
        _("Completa tu perfil para acceder a la plataforma."),
        _("Elige tu rol: Atleta, HeadCoach o Tutor."),
    ],
    ("accounts:profile_edit", None): [
        _("Edita tu información personal: nombre, foto de perfil y datos de contacto."),
        _("Mantén estos datos actualizados para que tu equipo pueda contactarte."),
    ],
    ("accounts:headcoach_approvals", "ADMIN"): [
        _("Solicitudes de registro de nuevos HeadCoach pendientes de aprobación."),
        _("Aprueba o rechaza cada solicitud para habilitar el acceso del coach."),
    ],
    ("guardian:dashboard", "GUARDIAN"): [
        _("Tu panel como tutor: ve el estado de tu atleta, sus pedidos y datos de perfil."),
        _("Desde aquí das seguimiento a todo lo relacionado con tu atleta a cargo."),
    ],
    ("guardian:headcoach_dashboard", "HEADCOACH"): [
        _("Resumen de tutores asignados y atletas que aún no tienen tutor vinculado."),
        _("Vincula tutores a los atletas menores que lo requieran."),
    ],
    ("measures:manage_measurement_fields", "ADMIN"): [
        _("Define qué medidas se capturan para cada producto (talla de pecho, cintura, etc.)."),
        _("Estos campos determinan qué datos deben ingresar los atletas al medirse."),
    ],
}


def get_help_cards(view_name, user):
    """Return list[str] of help cards for (view_name, user's role).

    Empty list if the user is anonymous, has dismissed help, or there is no
    matching registry entry. Role-specific entries take precedence over the
    None-keyed fallback. Cards are coerced to ``str`` so lazy translations are
    resolved into the active language.
    """
    if not user or not getattr(user, "is_authenticated", False):
        return []
    if getattr(user, "help_dismissed", False):
        return []
    for role in user.roles.values_list("name", flat=True):
        cards = HELP_REGISTRY.get((view_name, role))
        if cards:
            return [str(c) for c in cards]
    return [str(c) for c in HELP_REGISTRY.get((view_name, None), [])]


def get_help_text(view_name, user):
    """Backward-compatible alias: first help card for the view, or empty string."""
    cards = get_help_cards(view_name, user)
    return cards[0] if cards else ""
