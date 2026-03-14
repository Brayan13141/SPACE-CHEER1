# product_templates.py
# Plantillas oficiales para crear productos dentro del sistema.
# Cada plantilla define:
# defaults: configuración del modelo Product
# flags: comportamiento esperado en UI y flujos de orden
# example: ejemplo real del producto que se generará


PRODUCT_TEMPLATES = {
    # =========================================================
    # 1 PRODUCTO ESTANDAR SIMPLE
    #
    # GLOBAL
    # └── NONE
    #
    # No personalización
    # No tallas
    # No medidas
    # No atleta
    # No equipo
    # =========================================================
    "CATALOG_STANDARD": {
        "label": "Producto estándar",
        "description": "Producto simple sin tallas ni personalización",
        "example": {
            "name": "Mochila deportiva",
            "usage": "Producto genérico que cualquier usuario puede comprar",
        },
        "flags": {
            "requires_team": False,
            "requires_athlete": False,
            "requires_sizes": False,
            "requires_measurements": False,
        },
        "defaults": {
            "product_type": "OTHER",
            "usage_type": "GLOBAL",
            "size_strategy": "NONE",
            "scope": "CATALOG",
        },
    },
    # =========================================================
    # 2 PRODUCTO CON TALLAS
    #
    # GLOBAL
    # └── STANDARD
    #
    # No personalización
    # Usa tallas
    # =========================================================
    "CATALOG_WITH_SIZES": {
        "label": "Producto con tallas",
        "description": "Producto estándar con tallas como CH, M, G",
        "example": {
            "name": "Playera deportiva básica",
            "usage": "Playera estándar vendida por talla(CH,M,G)",
        },
        "flags": {
            "requires_team": False,
            "requires_athlete": False,
            "requires_sizes": True,
            "requires_measurements": False,
        },
        "defaults": {
            "product_type": "UNIFORM",
            "usage_type": "GLOBAL",
            "size_strategy": "STANDARD",
            "scope": "CATALOG",
        },
    },
    # =========================================================
    # 3 UNIFORME PERSONALIZADO POR EQUIPO
    #
    # TEAM_CUSTOM
    # └── STANDARD
    #
    # Cada equipo tiene su uniforme
    # Se selecciona talla
    # =========================================================
    "TEAM_UNIFORM_STANDARD": {
        "label": "Uniforme de equipo con tallas",
        "description": "Uniforme personalizado por equipo usando tallas estándar(CH,M,G)",
        "example": {
            "name": "Uniforme oficial del club",
            "usage": "El equipo compra uniformes para sus atletas",
        },
        "flags": {
            "requires_team": True,
            "requires_athlete": False,
            "requires_sizes": True,
            "requires_measurements": False,
        },
        "defaults": {
            "product_type": "UNIFORM",
            "usage_type": "TEAM_CUSTOM",
            "size_strategy": "STANDARD",
            "scope": "CATALOG",
        },
    },
    # =========================================================
    # 4 UNIFORME POR EQUIPO CON MEDIDAS
    #
    # TEAM_CUSTOM
    # └── MEASUREMENTSa
    #
    # Cada atleta registra medidas
    # =========================================================
    "TEAM_UNIFORM_MEASUREMENTS": {
        "label": "Uniforme del equipo con medidas",
        "description": "Uniforme donde cada atleta registra sus medidas",
        "example": {
            "name": "Traje de competencia del equipo",
            "usage": "Uniforme hecho a medida para cada atleta",
        },
        "flags": {
            "requires_team": True,
            "requires_athlete": True,
            "requires_sizes": False,
            "requires_measurements": True,
        },
        "defaults": {
            "product_type": "UNIFORM",
            "usage_type": "TEAM_CUSTOM",
            "size_strategy": "MEASUREMENTS",
            "scope": "CATALOG",
        },
    },
    # =========================================================
    # 5 UNIFORME PERSONALIZADO POR ATLETA
    #
    # ATHLETE_CUSTOM
    # └── MEASUREMENTS
    #
    # Cada atleta tiene nombre
    # número
    # medidas
    # =========================================================
    "ATHLETE_UNIFORM": {
        "label": "Uniforme personalizado por atleta",
        "description": "Cada atleta tiene nombre, número y medidas",
        "example": {
            "name": "Jersey personalizado",
            "usage": "Uniforme con nombre y número del atleta",
        },
        "flags": {
            "requires_team": False,
            "requires_athlete": True,
            "requires_sizes": False,
            "requires_measurements": True,
        },
        "defaults": {
            "product_type": "UNIFORM",
            "usage_type": "ATHLETE_CUSTOM",
            "size_strategy": "MEASUREMENTS",
            "scope": "CATALOG",
        },
    },
    # =========================================================
    # 6 PRODUCTO EXCLUSIVO DE EQUIPO
    #
    # TEAM_CUSTOM
    # └── STANDARD
    # scope TEAM_ONLY
    # =========================================================
    "TEAM_EXCLUSIVE_UNIFORM": {
        "label": "Uniforme exclusivo de equipo",
        "description": "Producto disponible únicamente para un equipo con tallas estandar (CH,M,G)",
        "example": {
            "name": "Uniforme oficial del club Tigres",
            "usage": "Solo el equipo Tigres puede comprarlo (CH,M,G)",
        },
        "flags": {
            "requires_team": True,
            "requires_athlete": False,
            "requires_sizes": True,
            "requires_measurements": False,
        },
        "defaults": {
            "product_type": "UNIFORM",
            "usage_type": "TEAM_CUSTOM",
            "size_strategy": "STANDARD",
            "scope": "TEAM_ONLY",
        },
    },
    # =========================================================
    # 7 UNIFORME EXCLUSIVO CON MEDIDAS
    #
    # TEAM_CUSTOM
    # └── MEASUREMENTS
    # scope TEAM_ONLY
    # =========================================================
    "TEAM_EXCLUSIVE_MEASURED_UNIFORM": {
        "label": "Uniforme exclusivo con medidas",
        "description": "Uniforme exclusivo de un equipo con medidas personalizadas",
        "example": {
            "name": "Uniforme profesional del club",
            "usage": "Cada atleta registra medidas para su uniforme",
        },
        "flags": {
            "requires_team": True,
            "requires_athlete": True,
            "requires_sizes": False,
            "requires_measurements": True,
        },
        "defaults": {
            "product_type": "UNIFORM",
            "usage_type": "TEAM_CUSTOM",
            "size_strategy": "MEASUREMENTS",
            "scope": "TEAM_ONLY",
        },
    },
}
