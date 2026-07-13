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

    # ── CORE (landing / contacto) ──────────────────────────────────────────
    ("core:landing", None): [
        _("Página pública de Space Cheer: conoce nuestros servicios, competencias y uniformes."),
        _("Usa el menú superior para volver a tu panel o navegar a la tienda y competencias."),
    ],
    ("core:manage_landing", "ADMIN"): [
        _("Edita el contenido de la página pública: textos e imágenes que ven los visitantes."),
        _("Los cambios se publican de inmediato — revisa la landing después de guardar."),
    ],
    ("core:contact", None): [
        _("¿Tienes dudas o problemas? Escríbenos con este formulario y te responderemos por correo."),
        _("Incluye todos los detalles posibles (pedido, equipo, pantalla) para ayudarte más rápido."),
    ],

    # ── CUENTA: CONFIGURACIÓN Y DIRECCIONES ────────────────────────────────
    ("accounts:profile_settings", None): [
        _("Configura las preferencias de tu cuenta desde esta pantalla."),
        _("Si desactivaste los consejos de ayuda (el botón ? flotante), aquí puedes reactivarlos."),
    ],
    ("accounts:list_address", None): [
        _("Tus direcciones guardadas. Se usan como datos de contacto y entrega en tus pedidos."),
        _("Mantén al menos una dirección completa y actualizada para evitar retrasos en envíos."),
    ],
    ("accounts:create_address", None): [
        _("Captura tu dirección completa: calle, número, colonia, ciudad y código postal."),
        _("Verifica bien los datos — esta dirección puede usarse para la entrega de pedidos."),
    ],
    ("accounts:update_address", None): [
        _("Corrige o actualiza los datos de esta dirección."),
        _("Los pedidos nuevos usarán la información actualizada."),
    ],
    ("accounts:curp_verification", None): [
        _("La CURP se solicita por requisito legal para atletas. Verifica que coincida con tu documento oficial."),
        _("Tus datos están protegidos: el acceso a esta información queda registrado y auditado."),
    ],
    ("accounts:bulk_import_athletes", None): [
        _("Importa varios atletas a la vez: descarga la plantilla, llénala y súbela aquí."),
        _("Al terminar verás un resumen con las filas aceptadas y los errores a corregir."),
    ],
    ("accounts:coach_pending_approval", None): [
        _("Tu solicitud de HeadCoach está en revisión por el administrador."),
        _("Recibirás un correo cuando sea aprobada y podrás acceder a todas las funciones."),
    ],
    ("accounts:coach_rejected", None): [
        _("Tu solicitud de HeadCoach fue rechazada."),
        _("Si crees que es un error, contáctanos desde la página de contacto para revisarlo."),
    ],
    ("accounts:account_deactivate", None): [
        _("Al desactivar tu cuenta perderás acceso a tus pedidos, equipos y datos de la plataforma."),
        _("Si solo quieres dejar de recibir avisos, mejor ajusta tu configuración de perfil."),
    ],

    # ── CUSTODIA / TUTORES ─────────────────────────────────────────────────
    ("guardian:assign_guardian", None): [
        _("Vincula un tutor al atleta menor de edad. Es requisito para que el menor use la plataforma."),
        _("El tutor podrá ver los pedidos y datos del atleta, y autorizar su información."),
    ],
    ("guardian:minor_blocked", None): [
        _("Tu cuenta está bloqueada porque aún no tienes un tutor vinculado."),
        _("Pide a tu coach o headcoach que vincule a tu papá, mamá o tutor para continuar."),
    ],
    ("guardian:create_order_for_minor", "GUARDIAN"): [
        _("Crea un pedido en nombre de tu atleta a cargo, eligiendo productos del catálogo."),
        _("Después podrás capturar sus medidas y dar seguimiento al pedido desde tu panel."),
    ],

    # ── COACH: GESTIÓN DE ATLETAS Y CREW ───────────────────────────────────
    ("coach:edit_athlete_measures", None): [
        _("Edita las medidas corporales del atleta. Se usan en productos con tallas por medidas."),
        _("Captura con cinta métrica y verifica dos veces — de esto depende que el uniforme quede bien."),
    ],
    ("coach:edit_owned_user", None): [
        _("Edita los datos del miembro de tu crew: información personal y de contacto."),
        _("Mantén estos datos al día para pedidos y competencias."),
    ],
    ("coach:create_team_crew_member", None): [
        _("Agrega personal de apoyo (crew) a tu equipo con su información básica."),
        _("El crew participa en la operación del equipo pero no captura medidas de atleta."),
    ],

    # ── EQUIPOS (páginas faltantes) ────────────────────────────────────────
    ("teams:coach_teams", None): [
        _("Los equipos donde participas como coach."),
        _("Entra a un equipo para ver a sus miembros y gestionar solicitudes."),
    ],
    ("teams:join_by_code", None): [
        _("Ingresa el código de invitación que te dio tu coach para unirte a su equipo."),
        _("Tu solicitud quedará pendiente hasta que el coach la acepte."),
    ],
    ("teams:manage_categories", "ADMIN"): [
        _("Categorías para clasificar los equipos (nivel, edad, modalidad)."),
        _("Las categorías se usan también al registrar equipos en competencias."),
    ],
    ("teams:manage_team_members", None): [
        _("Miembros del equipo: acepta o rechaza solicitudes, cambia roles o retira miembros."),
        _("Si el código de invitación se filtró, puedes regenerarlo — el anterior deja de funcionar."),
    ],

    # ── PEDIDOS (páginas de usuario faltantes) ─────────────────────────────
    ("orders:edit_order", None): [
        _("Edita los datos generales del pedido mientras siga siendo editable."),
        _("Una vez enviado a revisión, los cambios mayores los gestiona el administrador."),
    ],
    ("orders:contact_info_order", None): [
        _("Captura los datos de contacto y entrega del pedido."),
        _("Con esta información te avisamos de avances y coordinamos la entrega final."),
    ],
    ("orders:order_item_detail", None): [
        _("Detalle del artículo: los atletas asignados y el estado de sus medidas."),
        _("Puedes importar de golpe a los atletas del equipo en lugar de agregarlos uno por uno."),
    ],
    ("orders:cart_team_select", None): [
        _("Este producto es personalizado por equipo: elige a qué equipo pertenece antes de agregarlo."),
        _("Así el pedido queda ligado al equipo correcto y sus atletas podrán capturar medidas."),
    ],

    # ── PEDIDOS (admin / mostrador) ────────────────────────────────────────
    ("orders:customer_list", "ADMIN"): [
        _("Clientes de mostrador para pedidos offline (fuera de la plataforma)."),
        _("Crea aquí al cliente antes de levantar su pedido offline."),
    ],
    ("orders:offline_order_create", "ADMIN"): [
        _("Levanta un pedido de mostrador: elige cliente, productos internos y plantilla de producción."),
        _("Los abonos y anticipos se registran después, desde el detalle del pedido."),
    ],

    # ── PRODUCCIÓN (páginas faltantes) ─────────────────────────────────────
    ("production:mi_area", "OPERARIO"): [
        _("Tu área de trabajo: los roles que tienes asignados y las etapas donde eres responsable o auxiliar."),
        _("También ves aquí los reportes de error que has generado y su estado."),
    ],
    ("production:reglamento", None): [
        _("El reglamento de producción: quién es responsable de cada etapa y quiénes son auxiliares."),
        _("Regla de Oro: ninguna etapa puede iniciarse sin haber completado la anterior."),
    ],
    ("production:admin_job_detail", "ADMIN"): [
        _("Trabajo de producción de la orden: todas sus tareas por artículo y etapa."),
        _("Asigna operarios a cada tarea, márcala urgente o reasigna en bloque si hace falta."),
    ],
    ("production:error_report_detail", None): [
        _("Detalle del reporte de error: qué pasó, en qué etapa y las acciones correctivas."),
        _("El administrador lo revisa y decide si la prenda requiere reposición."),
    ],
    ("production:item_measurements", None): [
        _("Las medidas capturadas de este artículo, tal como las verá el piso de producción."),
        _("Si algo no cuadra con la prenda física, genera un reporte de error."),
    ],
    ("production:order_design", None): [
        _("El diseño aprobado de la orden, para consulta durante la producción."),
        _("Produce siempre contra este diseño — es el que autorizó el administrador."),
    ],
    ("production:manage_responsibilities", "ADMIN"): [
        _("Define el responsable primario y los auxiliares de cada etapa — esto es el reglamento."),
        _("Los cambios se reflejan de inmediato en la vista de reglamento y en Mi Área de los operarios."),
    ],
    ("production:manage_templates", "ADMIN"): [
        _("Plantillas de producción: conjuntos de etapas predefinidos para crear pedidos más rápido."),
        _("Se usan al levantar pedidos offline para no configurar las etapas una por una."),
    ],
    ("production:product_stages_matrix", "ADMIN"): [
        _("Matriz producto × etapa: marca qué etapas aplican a cada producto."),
        _("Al enviar un pedido a producción, esta matriz define qué tareas se generan."),
    ],
    ("production:operario_detail", "ADMIN"): [
        _("Detalle del operario: sus roles de producción y las tareas que tiene asignadas."),
        _("Desde aquí controlas su carga de trabajo y sus responsabilidades."),
    ],
    ("production:manage_role_operarios", "ADMIN"): [
        _("Agrega o quita operarios de este rol de producción."),
        _("Las tareas ya asignadas no cambian solas: reasígnalas desde el detalle del trabajo."),
    ],

    # ── PRODUCTOS (admin, faltantes) ───────────────────────────────────────
    ("products:create_product", "ADMIN"): [
        _("Configura el producto: tipo de uso (global, por equipo o por atleta), tallas y alcance."),
        _("Ojo: una vez usado en un pedido, el tipo de uso y la estrategia de tallas quedan fijos."),
    ],
    ("products:select_template", "ADMIN"): [
        _("Elige una plantilla base para crear el producto con su configuración precargada."),
        _("Después podrás ajustar nombre, precio, tallas y campos de medida."),
    ],

    # ── COMPETENCIAS (páginas faltantes) ───────────────────────────────────
    ("events:event_edit", "ADMIN"): [
        _("Edita los datos del evento: fechas, sede y categorías disponibles."),
        _("Si el evento ya tiene registros, avisa a los equipos de cualquier cambio importante."),
    ],
    ("events:my_registrations", None): [
        _("Los registros de tus equipos en competencias y su estado (pendiente, aceptado, rechazado)."),
        _("Puedes retirar un registro si tu equipo ya no participará."),
    ],
    ("events:team_register", None): [
        _("Registra a tu equipo en este evento eligiendo la categoría adecuada."),
        _("Hazlo antes del cierre de inscripciones — el organizador aceptará o rechazará el registro."),
    ],
    ("events:registrations_list", "ADMIN"): [
        _("Los equipos registrados en el evento. Acepta o rechaza cada solicitud."),
        _("Solo los registros aceptados participan y aparecen en el panel de jueces."),
    ],
    ("events:staff_manage", "ADMIN"): [
        _("Asigna jueces y staff al evento con su función específica."),
        _("Los jueces asignados tendrán acceso a su panel de calificación."),
    ],
    ("events:criteria_manage", "ADMIN"): [
        _("Define los criterios de calificación del evento y su ponderación."),
        _("Los jueces calificarán cada rutina criterio por criterio según esta configuración."),
    ],
    ("events:score_entry", "ADMIN"): [
        _("Captura o corrige calificaciones de los equipos participantes."),
        _("Úsalo para ajustes administrativos; los jueces capturan desde su propio panel."),
    ],
    ("events:results_manage", "ADMIN"): [
        _("Revisa y publica los resultados finales del evento."),
        _("Una vez publicados, los equipos podrán consultarlos en la página del evento."),
    ],
    ("events:judge_panel", None): [
        _("Tu panel de juez: califica cada rutina según los criterios configurados."),
        _("Las calificaciones se guardan por criterio — revisa antes de enviar cada puntuación."),
    ],

    # ── HOSPEDAJE (páginas faltantes) ──────────────────────────────────────
    ("hospitality:hotel_detail", "ADMIN"): [
        _("Detalle del hotel: sus tipos de habitación, habitaciones y camas."),
        _("Configura primero tipos y habitaciones para poder asignar estancias después."),
    ],
    ("hospitality:hotel_create", "ADMIN"): [
        _("Registra un hotel para el evento con sus datos generales."),
        _("Después agrégale tipos de habitación, habitaciones y camas."),
    ],
    ("hospitality:hotel_edit", "ADMIN"): [
        _("Edita los datos del hotel."),
        _("Los cambios no afectan las estancias ya asignadas."),
    ],
    ("hospitality:room_type_create", "ADMIN"): [
        _("Crea un tipo de habitación: capacidad y características (amenidades)."),
        _("También puedes aplicar presets para crear varios tipos comunes de una vez."),
    ],
    ("hospitality:room_type_edit", "ADMIN"): [
        _("Edita el tipo de habitación: capacidad y características."),
        _("Las habitaciones existentes conservan su tipo con los datos actualizados."),
    ],
    ("hospitality:room_create", "ADMIN"): [
        _("Agrega una habitación al hotel indicando su tipo y número."),
        _("Después crea sus camas para poder asignar huéspedes."),
    ],
    ("hospitality:room_edit", "ADMIN"): [
        _("Edita los datos de la habitación."),
        _("Revisa las asignaciones existentes si cambias su capacidad o tipo."),
    ],
    ("hospitality:bed_create", "ADMIN"): [
        _("Agrega camas a la habitación indicando su tipo."),
        _("Cada cama puede asignarse a un huésped específico."),
    ],
    ("hospitality:stay_list", "ADMIN"): [
        _("Las estancias de los participantes del evento y su estado."),
        _("Flujo: crear → confirmar → asignar habitación y cama → check-in → check-out."),
    ],
    ("hospitality:stay_create", "ADMIN"): [
        _("Crea la estancia de un participante con sus fechas de entrada y salida."),
        _("Después confírmala y asígnale habitación y cama."),
    ],
    ("hospitality:stay_detail", "ADMIN"): [
        _("Detalle de la estancia: huésped, fechas, habitación y cama asignadas."),
        _("Desde aquí confirmas, asignas habitación/cama y registras check-in y check-out."),
    ],
    ("hospitality:stay_confirm", "ADMIN"): [
        _("Confirma la estancia para apartar el lugar del huésped."),
        _("Una vez confirmada podrás asignarle habitación y cama."),
    ],
    ("hospitality:room_assign", "ADMIN"): [
        _("Asigna una habitación a esta estancia según disponibilidad."),
        _("También puedes usar la auto-asignación para que el sistema elija por ti."),
    ],
    ("hospitality:bed_assign", "ADMIN"): [
        _("Asigna la cama específica dentro de la habitación."),
        _("Considera las preferencias registradas por el huésped."),
    ],
    ("hospitality:preference_form", None): [
        _("Registra tus preferencias de hospedaje: con quién compartir y qué características necesitas."),
        _("El organizador las toma en cuenta al asignarte habitación y cama."),
    ],
    ("hospitality:room_feature_list", "ADMIN"): [
        _("Características de habitación (amenidades) reutilizables en todos los hoteles."),
        _("Crea aquí las características antes de usarlas en los tipos de habitación."),
    ],
    ("hospitality:room_feature_create", "ADMIN"): [
        _("Crea una característica de habitación (ej. aire acondicionado, vista al mar)."),
        _("Estará disponible para todos los tipos de habitación de todos los hoteles."),
    ],
    ("hospitality:room_feature_edit", "ADMIN"): [
        _("Edita el nombre o descripción de la característica."),
        _("El cambio se refleja en todos los tipos de habitación que la usan."),
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
