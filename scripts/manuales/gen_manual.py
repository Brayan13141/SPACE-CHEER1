"""
Generador del Manual Técnico de Space Cheer.
Ejecutar: PYTHONUTF8=1 python gen_manual.py
desde C:/Users/Lenovo/Documents/SPACE-CHEER/
"""

import sys
from playwright.sync_api import sync_playwright

# ─── CONTENIDO HTML ────────────────────────────────────────────────────────────

HTML = r"""<!DOCTYPE html>
<html lang="es">
<head>
<meta charset="UTF-8"/>
<title>Manual Técnico — Space Cheer</title>
<style>
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;600;700&display=swap');
@page { size: A4; margin: 18mm 16mm; }
body { font-family: 'Segoe UI', Arial, sans-serif; color: #0f172a; font-size: 10pt; line-height: 1.65; margin: 0; }
h1 { font-size: 22pt; color: #0f172a; font-weight: 700; margin-bottom: 6px; }
h2 { font-size: 13.5pt; color: #1e3a5f; border-bottom: 2.5px solid #0ea5e9; padding-bottom: 5px; margin: 28px 0 12px; font-weight: 700; }
h3 { font-size: 11pt; color: #1e40af; margin: 18px 0 7px; font-weight: 600; }
h4 { font-size: 10pt; color: #334155; margin: 12px 0 4px; font-weight: 600; }
p { margin: 6px 0; }
ul, ol { margin: 6px 0 8px 20px; }
li { margin-bottom: 3px; }
code { font-family: 'Consolas', 'Courier New', monospace; background: #f1f5f9; border-radius: 3px; padding: 1px 4px; font-size: 9pt; color: #0369a1; }
pre { font-family: 'Consolas', 'Courier New', monospace; background: #f8fafc; border: 1px solid #e2e8f0; border-radius: 5px; padding: 10px 13px; font-size: 8.5pt; overflow-wrap: break-word; white-space: pre-wrap; color: #1e293b; margin: 8px 0; }
.model { background: #f8fafc; border: 1px solid #e2e8f0; border-radius: 8px; padding: 12px 15px; margin: 10px 0; }
.field { font-family: 'Consolas', monospace; font-size: 9pt; color: #0369a1; }
.info { background: #eff6ff; border-left: 4px solid #3b82f6; padding: 9px 13px; margin: 10px 0; border-radius: 0 5px 5px 0; }
.warn { background: #fefce8; border-left: 4px solid #eab308; padding: 9px 13px; margin: 10px 0; border-radius: 0 5px 5px 0; }
.danger { background: #fff1f2; border-left: 4px solid #ef4444; padding: 9px 13px; margin: 10px 0; border-radius: 0 5px 5px 0; }
.success { background: #f0fdf4; border-left: 4px solid #22c55e; padding: 9px 13px; margin: 10px 0; border-radius: 0 5px 5px 0; }
table { width: 100%; border-collapse: collapse; font-size: 9pt; margin: 10px 0; }
th { background: #1e293b; color: #fff; padding: 7px 9px; text-align: left; font-size: 9pt; font-weight: 600; }
td { padding: 6px 9px; border-bottom: 1px solid #e2e8f0; vertical-align: top; }
tr:nth-child(even) td { background: #f8fafc; }
.cover { text-align: center; padding: 80px 0 60px; }
.cover h1 { font-size: 30pt; color: #0f172a; margin-bottom: 10px; }
.cover .subtitle { font-size: 14pt; color: #64748b; margin-bottom: 40px; }
.cover .meta { font-size: 10pt; color: #94a3b8; }
.page-break { page-break-before: always; }
.toc-entry { display: flex; justify-content: space-between; padding: 3px 0; border-bottom: 1px dotted #cbd5e1; }
.diagram { font-family: 'Consolas', monospace; background: #0f172a; color: #7dd3fc; border-radius: 6px; padding: 14px; font-size: 8.5pt; margin: 10px 0; white-space: pre; }
.badge { display: inline-block; padding: 2px 7px; border-radius: 4px; font-size: 8pt; font-weight: 600; margin: 0 2px; }
.badge-blue { background: #dbeafe; color: #1d4ed8; }
.badge-green { background: #dcfce7; color: #166534; }
.badge-orange { background: #ffedd5; color: #c2410c; }
.badge-red { background: #fee2e2; color: #dc2626; }
.badge-purple { background: #f3e8ff; color: #7c3aed; }
.section-label { font-size: 8pt; color: #94a3b8; text-transform: uppercase; letter-spacing: 0.08em; font-weight: 600; margin-bottom: 4px; }
hr { border: none; border-top: 1px solid #e2e8f0; margin: 16px 0; }
</style>
</head>
<body>

<!-- ═══════════════════════════════ PORTADA ═══════════════════════════════ -->
<div class="cover">
  <div class="section-label">Documento Técnico Interno</div>
  <h1>Space Cheer</h1>
  <div class="subtitle">Manual Técnico del Sistema</div>
  <p style="font-size:11pt; color:#475569; max-width:480px; margin:0 auto 30px;">
    Guía exhaustiva de arquitectura, modelos, servicios, despliegue y seguridad
    de la plataforma Django 5.2 para gestión de equipos de cheerleading.
  </p>
  <div class="meta">
    <p><strong>Versión:</strong> 1.0 &nbsp;|&nbsp; <strong>Fecha:</strong> 2026-06-22</p>
    <p><strong>Dominio en producción:</strong> <code>spacecheer.com</code></p>
    <p><strong>Servidor:</strong> Hetzner 167.233.125.145 &nbsp;|&nbsp; Ubuntu 26.04 &nbsp;|&nbsp; Python 3.14</p>
  </div>
</div>

<!-- ═══════════════════════════ TABLA DE CONTENIDOS ══════════════════════ -->
<div class="page-break"></div>
<h2 style="border-bottom:none; font-size:16pt; color:#0f172a;">Tabla de Contenidos</h2>
<div class="toc-entry"><span>1. Descripción General del Sistema</span><span>3</span></div>
<div class="toc-entry"><span>2. Arquitectura de Apps Django</span><span>4</span></div>
<div class="toc-entry"><span>3. Modelos de Datos Clave</span><span>6</span></div>
<div class="toc-entry"><span>4. Servicio de Estado de Pedidos (State Machine)</span><span>12</span></div>
<div class="toc-entry"><span>5. Capa de Servicios</span><span>14</span></div>
<div class="toc-entry"><span>6. Sistema de Autenticación y Roles</span><span>16</span></div>
<div class="toc-entry"><span>7. URLs del Sistema</span><span>18</span></div>
<div class="toc-entry"><span>8. Sistema de Notificaciones y Celery</span><span>20</span></div>
<div class="toc-entry"><span>9. Configuración de Producción</span><span>21</span></div>
<div class="toc-entry"><span>10. Guía de Desarrollo</span><span>24</span></div>
<div class="toc-entry"><span>11. Seguridad</span><span>25</span></div>

<!-- ══════════════════════════ 1. DESCRIPCIÓN GENERAL ═══════════════════ -->
<div class="page-break"></div>
<h2>1. Descripción General del Sistema</h2>

<p><strong>Space Cheer</strong> es una plataforma web Django diseñada para la gestión integral de equipos de cheerleading. Centraliza en un solo sistema: pedidos de uniformes, toma de medidas corporales por atleta, membresías de equipo, flujo de producción de prendas y funcionalidades sociales.</p>

<h3>1.1 Funcionalidades Principales</h3>
<ul>
  <li><strong>Gestión de equipos y membresías:</strong> Coaches crean equipos, atletas se unen por código. Sistema de roles dentro del equipo (ATHLETE, COACH, STAFF).</li>
  <li><strong>Catálogo de productos:</strong> Productos con tres ejes ortogonales: tipo de uso (GLOBAL/TEAM_CUSTOM/ATHLETE_CUSTOM), estrategia de talla (NONE/STANDARD/MEASUREMENTS) y alcance (CATALOG/TEAM_ONLY).</li>
  <li><strong>Pedidos con máquina de estados:</strong> DRAFT → PENDING → DESIGN_APPROVED → IN_PRODUCTION → DELIVERED, con cancelación posible desde los primeros tres estados.</li>
  <li><strong>Medidas corporales por atleta:</strong> Campos configurables (pecho, cintura, etc.) vinculados al perfil del atleta y snapshotteados en la orden.</li>
  <li><strong>Producción:</strong> Al ingresar al estado IN_PRODUCTION, se crea automáticamente un <code>ProductionJob</code> con <code>ProductionTask</code> por etapa y por ítem. Los operarios completan tareas secuencialmente.</li>
  <li><strong>Auditoría PII:</strong> Acceso a datos sensibles (CURP, medidas de menores) queda registrado en <code>PiiAccessLog</code>.</li>
  <li><strong>Funciones sociales:</strong> Feed de publicaciones, likes y comentarios (app <code>social</code>).</li>
</ul>

<h3>1.2 Stack Tecnológico</h3>
<table>
  <tr><th>Componente</th><th>Versión</th><th>Rol</th></tr>
  <tr><td>Django</td><td>5.2.14</td><td>Framework web principal</td></tr>
  <tr><td>PostgreSQL</td><td>18.4</td><td>Base de datos relacional</td></tr>
  <tr><td>Celery</td><td>5.6.2</td><td>Cola de tareas asíncronas</td></tr>
  <tr><td>Redis</td><td>5.0.1</td><td>Broker de Celery + backend de resultados</td></tr>
  <tr><td>django-allauth</td><td>65.13.1</td><td>Autenticación (email + username + OAuth)</td></tr>
  <tr><td>django-celery-beat</td><td>2.9.0</td><td>Tareas periódicas en base de datos</td></tr>
  <tr><td>django-csp</td><td>4.0</td><td>Content Security Policy (nonce-based)</td></tr>
  <tr><td>whitenoise</td><td>6.12.0</td><td>Servicio de archivos estáticos sin Nginx extra</td></tr>
  <tr><td>cryptography (Fernet)</td><td>46.0.3</td><td>Cifrado de campos PII (CURP, dirección)</td></tr>
  <tr><td>Gunicorn</td><td>25.1.0</td><td>Servidor WSGI (3 workers, puerto 8002)</td></tr>
  <tr><td>Nginx</td><td>1.28.3</td><td>Reverse proxy + SSL termination</td></tr>
  <tr><td>Bootstrap</td><td>5.x</td><td>Framework CSS frontend (dark mode, mobile-first)</td></tr>
  <tr><td>psycopg2-binary</td><td>2.9.11</td><td>Driver PostgreSQL</td></tr>
  <tr><td>python-decouple</td><td>3.8</td><td>Gestión de variables de entorno (.env)</td></tr>
  <tr><td>pytest + pytest-django</td><td>9.0.2 / 4.12.0</td><td>Suite de tests</td></tr>
</table>

<h3>1.3 Infraestructura de Producción</h3>
<table>
  <tr><th>Dato</th><th>Valor</th></tr>
  <tr><td>Proveedor</td><td>Hetzner Cloud</td></tr>
  <tr><td>IP</td><td>167.233.125.145</td></tr>
  <tr><td>Sistema Operativo</td><td>Ubuntu 26.04 LTS (resolute)</td></tr>
  <tr><td>Python</td><td>3.14.4</td></tr>
  <tr><td>PostgreSQL</td><td>18.4</td></tr>
  <tr><td>Dominio</td><td>spacecheer.com</td></tr>
  <tr><td>SSL</td><td>Let's Encrypt (certbot) — expira 2026-09-08, auto-renueva</td></tr>
  <tr><td>Repositorio</td><td>github.com/Brayan13141/SPACE-CHEER1.git (rama: main)</td></tr>
  <tr><td>Ruta en servidor</td><td>/home/space/SERVER/SPACE-CHEER1/space_cheer/</td></tr>
</table>

<h3>1.4 Servicios Systemd</h3>
<table>
  <tr><th>Servicio</th><th>Descripción</th><th>Comando</th></tr>
  <tr><td><code>space-cheer</code></td><td>Gunicorn (3 workers, puerto 8002)</td><td><code>systemctl restart space-cheer</code></td></tr>
  <tr><td><code>space-cheer-worker</code></td><td>Celery Worker (concurrency=2)</td><td><code>systemctl restart space-cheer-worker</code></td></tr>
  <tr><td><code>space-cheer-beat</code></td><td>Celery Beat con DatabaseScheduler</td><td><code>systemctl restart space-cheer-beat</code></td></tr>
</table>

<div class="info"><strong>Logs en tiempo real:</strong> <code>journalctl -u space-cheer -f</code> &nbsp;|&nbsp; <code>tail -f logs/gunicorn_error.log</code></div>


<!-- ═══════════════════════════ 2. ARQUITECTURA APPS ════════════════════ -->
<div class="page-break"></div>
<h2>2. Arquitectura de Apps Django</h2>

<p>El proyecto Django está en <code>space_cheer/</code> (donde vive <code>manage.py</code>). El módulo de configuración es <code>space_cheer.space_cheer.settings</code>.</p>

<h3>2.1 Listado de Apps Instaladas</h3>
<table>
  <tr><th>App</th><th>Responsabilidad Principal</th><th>Estado</th></tr>
  <tr><td><code>accounts</code></td><td>User personalizado, roles M2M, perfiles (Athlete/Coach/Staff), CURP cifrada, PII audit, guardián de menores, middleware IP whitelist</td><td><span class="badge badge-green">Producción</span></td></tr>
  <tr><td><code>teams</code></td><td>Team, UserTeamMembership (con estados), TeamCategory, TeamSong, join_code</td><td><span class="badge badge-green">Producción</span></td></tr>
  <tr><td><code>measures</code></td><td>MeasurementField (campos configurables), MeasurementValue (valores por usuario)</td><td><span class="badge badge-green">Producción</span></td></tr>
  <tr><td><code>products</code></td><td>Season, Product (3 ejes ortogonales), ProductSizeVariant, ProductMeasurementField</td><td><span class="badge badge-green">Producción</span></td></tr>
  <tr><td><code>orders</code></td><td>Order (state machine), OrderItem, OrderItemAthlete, OrderItemMeasurement, OrderLog, OrderContactInfo, OrderDesignImage</td><td><span class="badge badge-green">Producción</span></td></tr>
  <tr><td><code>production</code></td><td>ProductionJob, ProductionTask, ProductionStage, ProductionRole, ErrorReport, StageResponsibility, templates de producción</td><td><span class="badge badge-green">Producción</span></td></tr>
  <tr><td><code>custody</code></td><td>Relación guardián-menor, acceso controlado para menores (MinorAccessService)</td><td><span class="badge badge-green">Producción</span></td></tr>
  <tr><td><code>core</code></td><td>Home/landing, utilidades de archivos, contexto de ayuda contextual, servicio de media protegida</td><td><span class="badge badge-green">Producción</span></td></tr>
  <tr><td><code>coach</code></td><td>Vistas específicas del rol COACH (panel, atletas, órdenes)</td><td><span class="badge badge-green">Producción</span></td></tr>
  <tr><td><code>social</code></td><td>Feed, publicaciones, likes, comentarios</td><td><span class="badge badge-blue">Básico</span></td></tr>
  <tr><td><code>commerce</code></td><td>Tienda / comercio (etapa temprana)</td><td><span class="badge badge-orange">En desarrollo</span></td></tr>
  <tr><td><code>events</code></td><td>Competencias/eventos (no desarrollado aún)</td><td><span class="badge badge-orange">Placeholder</span></td></tr>
  <tr><td><code>hospitality</code></td><td>Hospitalidad/alojamiento para eventos</td><td><span class="badge badge-orange">En desarrollo</span></td></tr>
</table>

<h3>2.2 Flujo de Request</h3>
<pre class="diagram">Request HTTPS
     │
     ▼
  Nginx (443→8002)
  └─ X-Forwarded-Proto: https
  └─ X-Real-IP, X-Forwarded-For
     │
     ▼
  Gunicorn (127.0.0.1:8002, 3 workers)
     │
     ▼
  Django WSGI Middleware Stack:
  1. SecurityMiddleware (HSTS, SSL-redirect)
  2. AdminIPWhitelistMiddleware  ← bloquea /admin/ y /orders/admin/ por IP
  3. WhiteNoiseMiddleware        ← sirve /static/ directamente
  4. CSPMiddleware               ← inyecta Content-Security-Policy con nonce
  5. PermissionsPolicyMiddleware ← agrega header Permissions-Policy
  6. SessionMiddleware
  7. LocaleMiddleware
  8. CommonMiddleware
  9. CsrfViewMiddleware
  10. AuthenticationMiddleware
  11. MessageMiddleware
  12. XFrameOptionsMiddleware
  13. AccountMiddleware (allauth)
     │
     ▼
  URL Router (space_cheer/urls.py)
     │
     ▼
  View function / class-based view
     │
     ├─► Service Layer (orders/services/, production/services.py, accounts/services/)
     │        │
     │        └─► Django ORM → PostgreSQL 18
     │
     └─► Template → Response HTML
</pre>

<h3>2.3 Estructura de Templates</h3>
<p>Templates globales en <code>space_cheer/templates/</code>. Cada app tiene sus templates en <code>app/templates/app/</code>. Bootstrap 5 con dark mode siempre activo, paleta espacial (azules oscuros / cian). Scripts inline usan <code>nonce="{{ request.csp_nonce }}"</code>.</p>

<h3>2.4 Archivos Estáticos</h3>
<ul>
  <li>Fuente: <code>space_cheer/static/</code></li>
  <li>En producción: <code>python manage.py collectstatic</code> →  <code>space_cheer/staticfiles/</code></li>
  <li>Servidos por <strong>WhiteNoise</strong> desde Django (sin bloque Nginx separado)</li>
</ul>

<h3>2.5 Media (archivos subidos)</h3>
<ul>
  <li>Path: <code>space_cheer/media/</code></li>
  <li>Rutas configurables por modelo: <code>user_profile_photo_path</code>, <code>design_upload_path</code>, <code>product_image_path</code>, <code>team_photo_path</code>, <code>team_song_path</code></li>
  <li><strong>Media protegida:</strong> <code>core/views_media.py → serve_protected_media</code> — no acceso público directo</li>
  <li>Validación con <strong>python-magic</strong> (magic bytes) en todos los campos <code>ImageField</code>/<code>FileField</code></li>
  <li>Tamaño máximo: 5 MB (<code>DATA_UPLOAD_MAX_MEMORY_SIZE</code>). Diseños de orden: mínimo 3.5 MB</li>
</ul>


<!-- ═══════════════════════════ 3. MODELOS DE DATOS ═════════════════════ -->
<div class="page-break"></div>
<h2>3. Modelos de Datos Clave</h2>

<h3>3.1 accounts.User</h3>
<div class="model">
  <p>Extiende <code>AbstractUser</code>. Modelo: <code>AUTH_USER_MODEL = "accounts.User"</code></p>
  <table>
    <tr><th>Campo</th><th>Tipo</th><th>Descripción</th></tr>
    <tr><td><code>roles</code></td><td>M2M → Role</td><td>Roles del usuario (ADMIN, HEADCOACH, COACH, STAFF, ATLETA, ACOMPANANTE, OPERARIO)</td></tr>
    <tr><td><code>email</code></td><td>EmailField (unique)</td><td>Email único, normalizado a minúsculas</td></tr>
    <tr><td><code>phone</code></td><td>CharField(15, unique, nullable)</td><td>10 dígitos México, unique solo si tiene valor</td></tr>
    <tr><td><code>curp</code></td><td>EncryptedCharField(18)</td><td>CURP cifrada con Fernet. Validación regex + unicidad por hash HMAC</td></tr>
    <tr><td><code>curp_hash</code></td><td>CharField(64, unique, editable=False)</td><td>HMAC determinístico para unicidad del CURP cifrado</td></tr>
    <tr><td><code>birth_date</code></td><td>DateField nullable</td><td>Para calcular minoría de edad (<code>is_minor</code> property)</td></tr>
    <tr><td><code>gender</code></td><td>CharField choices: H/M</td><td>Género</td></tr>
    <tr><td><code>profile_completed</code></td><td>BooleanField (default=False)</td><td>Flag de onboarding. Requerido para acceder a vistas protegidas</td></tr>
    <tr><td><code>privacy_accepted</code></td><td>BooleanField</td><td>Aceptación aviso de privacidad</td></tr>
    <tr><td><code>terms_accepted</code></td><td>BooleanField</td><td>Aceptación términos y condiciones</td></tr>
    <tr><td><code>help_dismissed</code></td><td>BooleanField</td><td>Usuario ocultó los tooltips de ayuda contextual</td></tr>
    <tr><td><code>foto_perfil</code></td><td>ImageField (opcional)</td><td>Validada con python-magic (magic bytes)</td></tr>
  </table>
  <p><strong>Propiedades:</strong> <code>is_headcoach</code>, <code>is_minor</code> (calcula edad contra birth_date)</p>
</div>

<h3>3.2 accounts.Role</h3>
<div class="model">
  <table>
    <tr><th>Campo</th><th>Tipo</th><th>Descripción</th></tr>
    <tr><td><code>name</code></td><td>CharField(50, unique)</td><td>Nombre: ADMIN, HEADCOACH, COACH, STAFF, ATLETA, ACOMPANANTE, OPERARIO</td></tr>
    <tr><td><code>requires_curp</code></td><td>BooleanField</td><td>Si True, el usuario debe tener CURP registrada</td></tr>
    <tr><td><code>is_staff_type</code></td><td>BooleanField</td><td>Rol de tipo staff</td></tr>
    <tr><td><code>is_athlete_type</code></td><td>BooleanField</td><td>Rol de tipo atleta</td></tr>
    <tr><td><code>is_coach_type</code></td><td>BooleanField</td><td>Rol de tipo coach</td></tr>
    <tr><td><code>is_production_type</code></td><td>BooleanField</td><td>Rol de producción (OPERARIO)</td></tr>
    <tr><td><code>allow_dashboard_access</code></td><td>BooleanField</td><td>Si puede acceder al dashboard</td></tr>
  </table>
  <p>Poblar con: <code>python manage.py seed_roles</code></p>
</div>

<h3>3.3 accounts.PiiAccessLog</h3>
<div class="model">
  <p>Registro de auditoría para accesos a datos sensibles. Obligatorio por LGDNNA / LFPDPPP (mínimo 5 años de retención).</p>
  <table>
    <tr><th>Campo</th><th>Tipo</th><th>Descripción</th></tr>
    <tr><td><code>accessed_by</code></td><td>FK → User (SET_NULL)</td><td>Quién accedió al dato</td></tr>
    <tr><td><code>target_user</code></td><td>FK → User (SET_NULL)</td><td>A quién pertenece el dato accedido</td></tr>
    <tr><td><code>access_type</code></td><td>CharField choices</td><td>VIEW_CURP, VIEW_MEDICAL, VIEW_MEASUREMENTS, VIEW_ADDRESS, EXPORT_DATA, EDIT_PROFILE, BULK_IMPORT</td></tr>
    <tr><td><code>field_accessed</code></td><td>CharField(100)</td><td>Campo específico (ej: "curp", "measurements")</td></tr>
    <tr><td><code>ip_address</code></td><td>GenericIPAddressField</td><td>IP del cliente</td></tr>
    <tr><td><code>notes</code></td><td>TextField</td><td>Contexto adicional</td></tr>
    <tr><td><code>timestamp</code></td><td>DateTimeField (db_index)</td><td>Momento del acceso</td></tr>
  </table>
  <div class="warn">Nunca escribir directamente a PiiAccessLog. Siempre usar <code>PiiAuditService.log()</code>.</div>
</div>

<h3>3.4 teams.Team</h3>
<div class="model">
  <table>
    <tr><th>Campo</th><th>Tipo</th><th>Descripción</th></tr>
    <tr><td><code>name</code></td><td>CharField(100)</td><td>Nombre del equipo</td></tr>
    <tr><td><code>coach</code></td><td>FK → User (CASCADE)</td><td>Entrenador principal</td></tr>
    <tr><td><code>city</code></td><td>CharField(100)</td><td>Ciudad</td></tr>
    <tr><td><code>phone</code></td><td>CharField(20)</td><td>Teléfono de contacto</td></tr>
    <tr><td><code>logo</code></td><td>ImageField (opcional)</td><td>Logo, validado magic bytes</td></tr>
    <tr><td><code>category</code></td><td>FK → TeamCategory (nullable)</td><td>Categoría/nivel del equipo</td></tr>
    <tr><td><code>join_code</code></td><td>CharField(12, unique, editable=False)</td><td>Código de 6 hex chars generado con <code>secrets.token_hex(3)</code></td></tr>
    <tr><td><code>is_active</code></td><td>BooleanField</td><td>Activo/inactivo</td></tr>
  </table>
</div>

<h3>3.5 teams.UserTeamMembership</h3>
<div class="model">
  <table>
    <tr><th>Campo</th><th>Descripción</th></tr>
    <tr><td><code>user</code>, <code>team</code></td><td>FK. unique_together: un usuario solo puede estar una vez por equipo</td></tr>
    <tr><td><code>role_in_team</code></td><td>ATHLETE | COACH | STAFF</td></tr>
    <tr><td><code>status</code></td><td>pending → accepted | rejected | inactive</td></tr>
    <tr><td><code>is_active</code></td><td>BooleanField. True solo cuando status=accepted</td></tr>
    <tr><td><code>start_date</code>, <code>end_date</code></td><td>Fechas de vigencia de membresía</td></tr>
  </table>
  <p>Métodos: <code>.accept()</code>, <code>.reject()</code>, <code>.activate(role=None)</code>, <code>.deactivate()</code></p>
</div>

<h3>3.6 products.Product</h3>
<div class="model">
  <p>Tres ejes ortogonales de clasificación:</p>
  <table>
    <tr><th>Eje</th><th>Valores</th><th>Descripción</th></tr>
    <tr><td><code>usage_type</code></td><td>GLOBAL | TEAM_CUSTOM | ATHLETE_CUSTOM</td><td>Nivel de personalización del producto</td></tr>
    <tr><td><code>size_strategy</code></td><td>NONE | STANDARD | MEASUREMENTS</td><td>Cómo se maneja el tamaño</td></tr>
    <tr><td><code>scope</code></td><td>CATALOG | TEAM_ONLY</td><td>Disponibilidad del producto</td></tr>
  </table>
  <p><strong>Reglas de negocio clave (validadas en <code>Product.clean()</code>):</strong></p>
  <ul>
    <li>ATHLETE_CUSTOM → requiere <code>size_strategy=MEASUREMENTS</code></li>
    <li>GLOBAL → no puede ser TEAM_ONLY ni usar MEASUREMENTS</li>
    <li>TEAM_ONLY → requiere <code>owner_team</code></li>
    <li>CATALOG → no puede tener <code>owner_team</code></li>
    <li>Campos <code>scope</code>, <code>owner_team</code>, <code>size_strategy</code>, <code>usage_type</code> son <strong>inmutables</strong> una vez que el producto aparece en una orden</li>
  </ul>
  <p><strong>Propiedades:</strong> <code>requires_design</code>, <code>requires_measurements</code>, <code>requires_athletes</code>, <code>requires_sizes</code>, <code>is_simple</code>, <code>requires_team</code></p>
</div>

<h3>3.7 orders.Order</h3>
<div class="model">
  <table>
    <tr><th>Campo</th><th>Tipo</th><th>Descripción</th></tr>
    <tr><td><code>status</code></td><td>CharField choices</td><td>DRAFT|PENDING|DESIGN_APPROVED|IN_PRODUCTION|DELIVERED|CANCELLED</td></tr>
    <tr><td><code>order_type</code></td><td>PERSONAL | TEAM</td><td>Determina qué FK de propietario es válida</td></tr>
    <tr><td><code>owner_user</code></td><td>FK → User (nullable)</td><td>Propietario si PERSONAL</td></tr>
    <tr><td><code>owner_team</code></td><td>FK → Team (nullable)</td><td>Propietario si TEAM</td></tr>
    <tr><td><code>created_by</code></td><td>FK → User (PROTECT)</td><td>Quién creó la orden</td></tr>
    <tr><td><code>measurements_open</code></td><td>BooleanField (default=True)</td><td>Permite editar medidas (togglable)</td></tr>
    <tr><td><code>measurements_locked</code></td><td>BooleanField (default=False)</td><td>Bloqueo definitivo de medidas (irreversible)</td></tr>
    <tr><td><code>locked_at</code></td><td>DateTimeField nullable</td><td>Timestamp del bloqueo</td></tr>
    <tr><td><code>design_approved_by</code></td><td>FK → User nullable</td><td>Quién aprobó el diseño</td></tr>
    <tr><td><code>design_approved_at</code></td><td>DateTimeField nullable</td><td>Timestamp aprobación diseño</td></tr>
    <tr><td><code>production_started_at</code></td><td>DateTimeField nullable</td><td>Timestamp inicio producción</td></tr>
    <tr><td><code>delivered_at</code></td><td>DateTimeField nullable</td><td>Timestamp entrega</td></tr>
    <tr><td><code>cancelled_at</code></td><td>DateTimeField nullable</td><td>Timestamp cancelación</td></tr>
    <tr><td><code>cancelled_by</code></td><td>FK → User nullable</td><td>Quién canceló</td></tr>
    <tr><td><code>freeze_payment_date</code></td><td>DateTimeField nullable</td><td>Pago de congelación (requerido antes de PENDING si hay diseño)</td></tr>
    <tr><td><code>first_payment_date</code></td><td>DateTimeField nullable</td><td>Primer pago (requerido antes de IN_PRODUCTION)</td></tr>
    <tr><td><code>final_payment_date</code></td><td>DateTimeField nullable</td><td>Pago final (requerido antes de DELIVERED si hay diseño)</td></tr>
    <tr><td><code>measurements_due_date</code></td><td>DateField nullable</td><td>Fecha límite de medidas</td></tr>
    <tr><td><code>uniform_delivery_date</code></td><td>DateField nullable</td><td>Fecha de entrega del uniforme</td></tr>
    <tr><td><code>closed</code></td><td>BooleanField (default=False)</td><td>True cuando DELIVERED o CANCELLED</td></tr>
  </table>
  <div class="info">
    <strong>Invariante crítica:</strong> Nunca cambiar <code>order.status</code> directamente. El <code>save()</code> del modelo bloquea cambios de estado sin el flag <code>_allow_status_change</code>. Siempre usar <code>OrderStateService.transition()</code>.
  </div>
  <p><strong>Estado de medidas:</strong></p>
  <table>
    <tr><th>measurements_open</th><th>measurements_locked</th><th>Resultado</th></tr>
    <tr><td>True</td><td>False</td><td>Editable</td></tr>
    <tr><td>False</td><td>False</td><td>Cerrado temporal (reabreable)</td></tr>
    <tr><td>False</td><td>True</td><td>Bloqueado definitivo (irreversible)</td></tr>
  </table>
</div>

<h3>3.8 orders.OrderItem</h3>
<div class="model">
  <table>
    <tr><th>Campo</th><th>Descripción</th></tr>
    <tr><td><code>order</code></td><td>FK → Order (CASCADE)</td></tr>
    <tr><td><code>product</code></td><td>FK → Product (PROTECT)</td></tr>
    <tr><td><code>quantity</code></td><td>PositiveIntegerField</td></tr>
    <tr><td><code>unit_price</code></td><td>DecimalField — calculado: base_price + additional_price de variante</td></tr>
    <tr><td><code>subtotal</code></td><td>DecimalField — unit_price × quantity</td></tr>
    <tr><td><code>size_variant</code></td><td>FK → ProductSizeVariant (nullable). Inmutable después de creado el item.</td></tr>
  </table>
  <p><strong>Propiedades:</strong> <code>needs_athletes</code>, <code>needs_size</code>, <code>missing_configuration</code>, <code>configuration_state</code> (READY | INCOMPLETE)</p>
</div>

<h3>3.9 orders.OrderItemAthlete</h3>
<div class="model">
  <p>Asocia un atleta a un OrderItem. Requerido cuando el producto usa <code>ATHLETE_CUSTOM</code> o <code>TEAM_CUSTOM + MEASUREMENTS</code>.</p>
  <ul>
    <li>unique: (order_item, athlete)</li>
    <li>Valida que el atleta sea miembro activo del equipo (TEAM) o el propietario (PERSONAL)</li>
    <li>Método: <code>has_complete_measurements()</code> — verifica que todos los campos requeridos tengan valor</li>
  </ul>
</div>

<h3>3.10 orders.OrderItemMeasurement</h3>
<div class="model">
  <p>Snapshot de medidas por atleta dentro de un item. Arquitectura híbrida:</p>
  <table>
    <tr><th>Campo</th><th>Descripción</th></tr>
    <tr><td><code>athlete_item</code></td><td>FK → OrderItemAthlete</td></tr>
    <tr><td><code>field</code></td><td>FK → MeasurementField (PROTECT)</td></tr>
    <tr><td><code>field_name</code></td><td>CharField — copia del nombre del campo (snapshot)</td></tr>
    <tr><td><code>field_unit</code></td><td>CharField — copia de la unidad (snapshot)</td></tr>
    <tr><td><code>value_original</code></td><td>CharField — valor copiado del perfil del atleta al importar</td></tr>
    <tr><td><code>value</code></td><td>CharField — valor editable dentro de la orden</td></tr>
    <tr><td><code>is_modified</code></td><td>BooleanField — True si el coach editó manualmente</td></tr>
  </table>
  <p><strong>Propiedades:</strong> <code>has_value</code>, <code>display_value</code> (nunca muestra "None")</p>
</div>

<h3>3.11 production.ProductionJob</h3>
<div class="model">
  <table>
    <tr><th>Campo</th><th>Descripción</th></tr>
    <tr><td><code>order</code></td><td>OneToOneField → Order (CASCADE). Una orden = un Job.</td></tr>
    <tr><td><code>is_urgent</code></td><td>BooleanField. Toggleable por admin.</td></tr>
    <tr><td><code>created_at</code></td><td>DateTimeField auto</td></tr>
    <tr><td><code>completed_at</code></td><td>DateTimeField nullable</td></tr>
  </table>
</div>

<h3>3.12 production.ProductionTask</h3>
<div class="model">
  <table>
    <tr><th>Campo</th><th>Descripción</th></tr>
    <tr><td><code>job</code></td><td>FK → ProductionJob (CASCADE)</td></tr>
    <tr><td><code>order_item</code></td><td>FK → OrderItem (CASCADE)</td></tr>
    <tr><td><code>stage</code></td><td>FK → ProductionStage (PROTECT)</td></tr>
    <tr><td><code>status</code></td><td>PENDING | COMPLETED</td></tr>
    <tr><td><code>assigned_to</code></td><td>FK → User nullable — operario asignado</td></tr>
    <tr><td><code>completed_by</code></td><td>FK → User nullable</td></tr>
    <tr><td><code>started_at</code>, <code>completed_at</code></td><td>DateTimeField nullable</td></tr>
    <tr><td><code>notes</code></td><td>TextField — notas de ejecución</td></tr>
  </table>
  <p>unique: (job, order_item, stage). Las etapas deben completarse en orden (<code>display_order</code> ascendente).</p>
</div>

<h3>3.13 production.ErrorReport</h3>
<div class="model">
  <p>Registro estructurado de errores de producción con 7 secciones y sistema de revisión.</p>
  <table>
    <tr><th>Sección</th><th>Campos clave</th></tr>
    <tr><td>Info general</td><td><code>order</code>, <code>job</code>, <code>stage</code>, <code>area</code>, <code>reported_by</code></td></tr>
    <tr><td>Tipo de error (JSONField)</td><td>WRONG_SIZES, WRONG_CUT, WRONG_SUBLIMATION, WRONG_APPLICATION, DEFECTIVE_SEWING, WRONG_MATERIAL, WRONG_QUANTITY, INCOMPLETE_ORDER, PROCESS_DELAY, OTHER</td></tr>
    <tr><td>Descripción</td><td><code>description</code> (TextField)</td></tr>
    <tr><td>Responsable</td><td><code>responsible</code>, <code>responsible_area</code>, <code>error_causes</code> (JSONField)</td></tr>
    <tr><td>Impacto (JSONField)</td><td>DELIVERY_DELAY, REDO_GARMENT, WASTED_MATERIAL, ADDITIONAL_COST, UNHAPPY_CLIENT, AFFECTS_QUALITY</td></tr>
    <tr><td>Acciones correctivas</td><td><code>corrective_actions</code>, <code>prevention_actions</code></td></tr>
    <tr><td>Revisión por dirección</td><td><code>review_status</code> (PENDING|REVIEWED|EXCEPTION_GRANTED|REPOSITION_REQUIRED), <code>reviewed_by</code>, <code>reviewed_at</code></td></tr>
  </table>
  <p>Propiedad <code>is_reposition_type</code>: auto-flag si el tipo de error implica reposición (WRONG_SIZES, WRONG_CUT, WRONG_SUBLIMATION, WRONG_APPLICATION, DEFECTIVE_SEWING, INCOMPLETE_ORDER).</p>
</div>

<h3>3.14 Diagrama de Relaciones (ASCII)</h3>
<pre class="diagram">
   User ─────────────── M2M ─────────── Role
    │
    ├── [coach] ────────────────────── Team ──── TeamCategory
    │                                   │
    │                          UserTeamMembership (status, role_in_team)
    │
    ├── [owner_user / created_by] ──── Order ─────────── OrderContactInfo
    │                                   │                 OrderDesignImage
    │                                   │                 OrderLog
    │                                   │
    │                              OrderItem ────────── Product ─── Season
    │                                   │                 │           │
    │                                   │             ProductSizeVariant
    │                                   │             ProductMeasurementField
    │                                   │                 │
    │                         OrderItemAthlete            MeasurementField
    │                                   │                      │
    │                         OrderItemMeasurement ────────────┘
    │
    └── [measurements] ─────────── MeasurementValue ──── MeasurementField
    └── [team_memberships] ──────── UserTeamMembership
    └── [pii_accesses_made] ──────── PiiAccessLog

   Order (1:1) ──── ProductionJob ──── ProductionTask ──── ProductionStage
                                            │                    │
                                         [assigned_to/         StageResponsibility
                                          completed_by]              │
                                             │                 ProductionRole
                                           User           OperarioRoleAssignment

   ProductionTemplate ─── M2M (ProductionTemplateStage) ─── ProductionStage
   Product ─── M2M (ProductStageConfig) ─── ProductionStage

   ErrorReport ──── Order, ProductionJob, ProductionStage, User
</pre>


<!-- ══════════════════════ 4. STATE MACHINE ══════════════════════════════ -->
<div class="page-break"></div>
<h2>4. Servicio de Estado de Pedidos (State Machine)</h2>

<h3>4.1 Estados y Transiciones</h3>
<pre class="diagram">
  DRAFT ────────────────────────── PENDING
    │                                  │
    │                                  ├─── DESIGN_APPROVED ──── IN_PRODUCTION ──── DELIVERED
    │                                  │           │                    (final)
    │                                  │           └─── CANCELLED (final)
    └─── CANCELLED (final)             └─── CANCELLED (final)
                                       └─── IN_PRODUCTION (si no requiere diseño)
</pre>

<div class="info">
  <strong>ALLOWED_TRANSITIONS (definido en Order):</strong>
  <ul>
    <li>DRAFT → [PENDING, CANCELLED]</li>
    <li>PENDING → [DESIGN_APPROVED, CANCELLED, IN_PRODUCTION]</li>
    <li>DESIGN_APPROVED → [IN_PRODUCTION, CANCELLED]</li>
    <li>IN_PRODUCTION → [DELIVERED]</li>
    <li>DELIVERED → [] (terminal)</li>
    <li>CANCELLED → [] (terminal)</li>
  </ul>
</div>

<h3>4.2 Uso de OrderStateService.transition()</h3>
<pre>from orders.services.state import OrderStateService

# Patrón estándar
order = OrderStateService.transition(
    order=order,
    to_status="PENDING",
    user=request.user,
    notes="Enviado para revisión",
)

# La función:
# 1. Adquiere SELECT FOR UPDATE (lock de fila)
# 2. Llama validate_transition() — lanza ValidationError/PermissionDenied
# 3. Aplica STATE_EFFECTS (timestamps, flags)
# 4. Persiste con update_fields mínimos
# 5. Crea OrderLog (auditoría)
# 6. Llama _post_transition_hooks (notificaciones, ProductionJobService)</pre>

<h3>4.3 Precondiciones por Transición</h3>
<table>
  <tr><th>Destino</th><th>Precondiciones Obligatorias</th></tr>
  <tr>
    <td>PENDING</td>
    <td>
      • Tiene OrderContactInfo completa (nombre, teléfono, email, dirección, ciudad, CP)<br>
      • Al menos un OrderItem<br>
      • Todos los items en estado READY (tallas/atletas/medidas completas)<br>
      • Si orden TEAM: todos los atletas del equipo asignados a cada item que lo requiere<br>
      • Total &gt; 0<br>
      • Si requiere diseño: <code>freeze_payment_date</code> registrado
    </td>
  </tr>
  <tr>
    <td>DESIGN_APPROVED</td>
    <td>
      • Si requiere diseño: imagen con <code>is_final=True</code><br>
      • Si requiere atletas: todos los atletas del equipo asignados y consistentes<br>
      • Si requiere medidas: <code>OrderMeasurementsValidator.validate_complete()</code> OK<br>
      • Cierra medidas automáticamente (<code>MeasurementLifecycleService.close()</code>)
    </td>
  </tr>
  <tr>
    <td>IN_PRODUCTION</td>
    <td>
      • Si requiere diseño: imagen final presente<br>
      • Si requiere medidas: <code>measurements_locked=True</code> + <code>measurements_due_date</code> definida<br>
      • Si tiene uniformes: <code>uniform_delivery_date</code> definida<br>
      • <code>first_payment_date</code> registrado (sin excepción)<br>
      • Bloquea medidas definitivamente (<code>MeasurementLifecycleService.lock()</code>)
    </td>
  </tr>
  <tr>
    <td>DELIVERED</td>
    <td>
      • Si requiere diseño: <code>final_payment_date</code> registrado<br>
      • Si tiene uniformes: <code>uniform_delivery_date</code> definida<br>
      • Marca <code>closed=True</code>, registra <code>delivered_at</code>
    </td>
  </tr>
  <tr>
    <td>CANCELLED</td>
    <td>
      • No requiere precondiciones adicionales<br>
      • Guarda <code>cancelled_reason</code>, <code>cancelled_at</code>, <code>cancelled_by</code><br>
      • Marca <code>closed=True</code> y cierra <code>contact_info</code>
    </td>
  </tr>
</table>

<h3>4.4 Efectos Secundarios al entrar a IN_PRODUCTION</h3>
<div class="model">
  <p>Al transicionar a <strong>IN_PRODUCTION</strong>, <code>_post_transition_hooks()</code> invoca automáticamente:</p>
  <ol>
    <li><code>ProductionJobService.create_for_order(order)</code> — crea el <code>ProductionJob</code> con todas las <code>ProductionTask</code> necesarias</li>
    <li><code>OrderNotificationService.notify_production_started(order, user)</code> — notifica por email</li>
    <li><code>MeasurementLifecycleService.lock(order)</code> — bloqueo definitivo de medidas</li>
  </ol>
  <p>La creación de tasks funciona así:</p>
  <ol>
    <li>Se crea un <code>ProductionJob</code> vinculado a la orden</li>
    <li>Para cada <code>OrderItem</code>, se leen los <code>ProductStageConfig</code> del producto</li>
    <li>Por cada configuración de etapa, se crea una <code>ProductionTask</code> en estado PENDING</li>
    <li>Se usa <code>bulk_create()</code> para eficiencia</li>
    <li>Productos sin etapas configuradas generan warning en logs pero no error</li>
  </ol>
</div>

<h3>4.5 Permisos por Transición</h3>
<table>
  <tr><th>Transición</th><th>Quién puede</th></tr>
  <tr><td>→ PENDING</td><td>Superuser, Staff, o creator/coach de la orden (<code>can_manage_order</code>)</td></tr>
  <tr><td>→ CANCELLED (desde DRAFT/PENDING)</td><td>Superuser, Staff, o creator/coach de la orden</td></tr>
  <tr><td>→ DESIGN_APPROVED</td><td>Superuser, Staff, o quien tenga permiso <code>can_approve_design</code></td></tr>
  <tr><td>→ IN_PRODUCTION</td><td>Solo Superuser o Staff</td></tr>
  <tr><td>→ DELIVERED</td><td>Solo Superuser o Staff</td></tr>
</table>


<!-- ═══════════════════════════ 5. SERVICIOS ═════════════════════════════ -->
<div class="page-break"></div>
<h2>5. Capa de Servicios</h2>

<div class="info">Toda la lógica de negocio vive en servicios. Las vistas delegan en servicios; los servicios no deben importar de vistas.</div>

<h3>5.1 orders/services/state.py — OrderStateService y OrderCreationService</h3>
<div class="model">
  <p><strong>OrderStateService</strong></p>
  <ul>
    <li><code>transition(order, to_status, user, notes="")</code> — método principal, atómico con SELECT FOR UPDATE</li>
    <li><code>can_transition(order, to_status)</code> — verifica transición en ALLOWED_TRANSITIONS</li>
    <li><code>validate_transition(order, to_status, user)</code> — valida permiso + precondiciones</li>
    <li><code>get_available_transitions(order, user)</code> — lista de transiciones disponibles para UI</li>
    <li><code>can_user_attempt_transition(order, to_status, user)</code> — verificación ligera para UI</li>
    <li><code>_apply_state_effects()</code> — aplica timestamps y flags según STATE_EFFECTS</li>
    <li><code>_persist_transition()</code> — save con update_fields mínimos + flag _allow_status_change</li>
    <li><code>_create_transition_log()</code> — crea OrderLog con metadata</li>
    <li><code>_post_transition_hooks()</code> — notificaciones + creación de ProductionJob</li>
  </ul>
  <p><strong>OrderCreationService</strong></p>
  <ul>
    <li><code>create_order(order_type, created_by, owner_user=None, owner_team=None)</code> — crea Order en DRAFT + OrderLog inicial</li>
  </ul>
</div>

<h3>5.2 orders/services/measurements/MeasurementLifecycleService.py</h3>
<div class="model">
  <ul>
    <li><code>open(order, user=None)</code> — abre edición (idempotente). Falla si bloqueado.</li>
    <li><code>close(order, user=None)</code> — cierre temporal (idempotente)</li>
    <li><code>reopen(order, user=None)</code> — reabrir (solo en DRAFT/PENDING/DESIGN_APPROVED y no bloqueado)</li>
    <li><code>lock(order, user=None)</code> — bloqueo definitivo: <code>measurements_locked=True</code>, <code>measurements_open=False</code>, guarda <code>locked_at</code></li>
    <li><code>auto_close_if_due(order)</code> — cierra si llegó la fecha límite. Ideal para Celery Beat.</li>
  </ul>
</div>

<h3>5.3 orders/services/notifications/order_notifications.py — OrderNotificationService</h3>
<div class="model">
  <p>Notificaciones por email vía <code>EmailMultiAlternatives</code> (text + HTML).</p>
  <ul>
    <li><code>notify_design_approved(order, triggered_by)</code></li>
    <li><code>notify_production_started(order, triggered_by)</code></li>
    <li><code>notify_order_delivered(order, triggered_by)</code></li>
    <li><code>notify_production_task_completed(task, recipients)</code> — notifica a ADMIN+STAFF</li>
    <li><code>notify_task_assigned(task)</code> — notifica al operario asignado</li>
    <li><code>_get_recipients(order)</code> — extrae emails del owner_user o todos los miembros del equipo</li>
  </ul>
</div>

<h3>5.4 production/services.py — ProductionJobService</h3>
<div class="model">
  <ul>
    <li><code>create_for_order(order)</code> — crea ProductionJob + ProductionTasks para todos los items y sus etapas configuradas</li>
    <li><code>complete_task(task, user, started_at, notes="")</code>:
      <ul>
        <li>Verifica que no haya etapas previas PENDING (bloqueo por orden)</li>
        <li>SELECT FOR UPDATE en la tarea</li>
        <li>Marca COMPLETED con timestamps</li>
        <li>Dispara <code>notify_production_stage_complete.delay(task.pk)</code></li>
      </ul>
    </li>
    <li><code>assign_task(task, operario)</code> — asigna operario + dispara <code>notify_task_assigned.delay(task.pk)</code></li>
    <li><code>toggle_urgent(job)</code> — toggle de flag is_urgent</li>
  </ul>
</div>

<h3>5.5 production/services.py — OperarioService</h3>
<div class="model">
  <ul>
    <li><code>create(username, password, first_name, last_name, email)</code> — crea usuario nuevo con rol OPERARIO</li>
    <li><code>assign_existing(user)</code> — agrega rol OPERARIO a usuario ya registrado</li>
    <li><code>assign_role(operario, prod_role, assigned_by)</code> — crea OperarioRoleAssignment (get_or_create)</li>
    <li><code>remove_role(operario, prod_role)</code> — elimina asignación de rol de producción</li>
  </ul>
</div>

<h3>5.6 production/services.py — ErrorReportService</h3>
<div class="model">
  <ul>
    <li><code>create(...)</code> — crea ErrorReport con todos los campos. Auto-flag <code>requires_reposition=True</code> si el tipo lo implica.</li>
    <li><code>review(report, reviewed_by, review_status, review_notes, is_exception, exception_reason)</code> — registra la revisión. Si <code>EXCEPTION_GRANTED</code>: cancela reposición.</li>
  </ul>
</div>

<h3>5.7 Otros Servicios Relevantes</h3>
<table>
  <tr><th>Módulo</th><th>Descripción</th></tr>
  <tr><td><code>orders/services/cart.py</code></td><td>Lógica del carrito de compras</td></tr>
  <tr><td><code>orders/services/contactinfo.py</code></td><td>Validación de información de contacto</td></tr>
  <tr><td><code>orders/services/factories.py</code></td><td><code>OrderContactInfoFactory.from_user(order, user)</code></td></tr>
  <tr><td><code>orders/services/preconditions.py</code></td><td><code>can_submit_order(order)</code> — lista de issues bloqueantes</td></tr>
  <tr><td><code>orders/services/validators.py</code></td><td>OrderBaseValidator, OrderDesignValidator, OrderMeasurementsValidator</td></tr>
  <tr><td><code>orders/services/product_filter_service.py</code></td><td>Filtros de productos disponibles para una orden</td></tr>
  <tr><td><code>accounts/services/</code></td><td>PiiAuditService, UserSearchService, BulkImportService, OwnershipService</td></tr>
</table>


<!-- ══════════════════════ 6. AUTENTICACIÓN Y ROLES ═════════════════════ -->
<div class="page-break"></div>
<h2>6. Sistema de Autenticación y Roles</h2>

<h3>6.1 Roles del Sistema</h3>
<table>
  <tr><th>Rol</th><th>Flag en Role model</th><th>Acceso</th></tr>
  <tr><td>ADMIN</td><td>—</td><td>Acceso total, gestión del sistema</td></tr>
  <tr><td>HEADCOACH</td><td><code>is_coach_type=True</code></td><td>Coach principal, puede gestionar coaches secundarios</td></tr>
  <tr><td>COACH</td><td><code>is_coach_type=True</code></td><td>Gestión de equipos y órdenes</td></tr>
  <tr><td>STAFF</td><td><code>is_staff_type=True</code></td><td>Acceso a panel admin de órdenes, transiciones IN_PRODUCTION/DELIVERED</td></tr>
  <tr><td>ATLETA</td><td><code>is_athlete_type=True</code></td><td>Ver su equipo, sus medidas, sus órdenes</td></tr>
  <tr><td>ACOMPANANTE</td><td><code>is_athlete_type=True</code></td><td>Acompañante de atleta menor</td></tr>
  <tr><td>OPERARIO</td><td><code>is_production_type=True</code></td><td>Panel de producción, completar tareas asignadas</td></tr>
</table>

<p><strong>Jerarquía global (teams/models.py — GLOBAL_ROLE_HIERARCHY):</strong></p>
<pre>ADMIN       → ve a: ADMIN, HEADCOACH, COACH, STAFF, ATHLETE, ACOMPANANTE
HEADCOACH   → ve a: HEADCOACH, COACH, STAFF, ATHLETE, ACOMPANANTE
COACH       → ve a: COACH, STAFF, ATHLETE, ACOMPANANTE
STAFF       → ve a: STAFF, ACOMPANANTE
ATHLETE     → ve a: ATHLETE, ACOMPANANTE
ACOMPANANTE → ve a: ACOMPANANTE</pre>

<h3>6.2 Decorator @role_required()</h3>
<div class="model">
  <pre>from accounts.decorators import role_required

@role_required("HEADCOACH", "COACH")
def my_view(request):
    ...

@role_required("ADMIN", "STAFF")
def admin_view(request):
    ...</pre>
  <p><strong>Flujo del decorator:</strong></p>
  <ol>
    <li>Verifica autenticación → redirect a <code>account_login</code> si no autenticado</li>
    <li>Verifica <code>profile_completed</code> → redirect a <code>get_user_redirect_flow(user)</code></li>
    <li>Superuser bypass (sin verificar roles)</li>
    <li>Intersección de roles del usuario con roles permitidos → accede si hay match</li>
    <li>Si no hay match → log warning + redirect al flujo del usuario</li>
  </ol>
  <p>Para CBVs se usan mixins en <code>accounts/mixins.py</code>.</p>
</div>

<h3>6.3 @minor_access_required()</h3>
<div class="model">
  <pre>from accounts.decorators import minor_access_required

@minor_access_required(min_level="ACTIVE")
def view_for_minors_with_active_access(request):
    ...</pre>
  <p>Niveles: BLOCKED (0) &lt; READ_ONLY (1) &lt; ACTIVE (2). Si el usuario no es menor, pasa sin restricción. Delegado a <code>MinorAccessService.get_access_level(user)</code>.</p>
</div>

<h3>6.4 AdminIPWhitelistMiddleware</h3>
<div class="model">
  <p>Archivo: <code>accounts/middleware.py</code>. Activado en posición 2 del stack (tras SecurityMiddleware).</p>
  <p><strong>Rutas protegidas:</strong></p>
  <ul>
    <li><code>/{ADMIN_URL}</code> — panel Django admin (URL configurable via <code>.env</code>)</li>
    <li><code>/orders/admin/</code> — panel de administración de órdenes</li>
  </ul>
  <p>Si la variable <code>ADMIN_ALLOWED_IPS</code> tiene IPs configuradas y la IP del cliente no está en la lista → retorna <code>403 Forbidden</code> inmediatamente.</p>
  <p>Usa <code>django-ipware</code> para extraer la IP real (considera proxies / X-Forwarded-For).</p>
  <div class="warn">En producción: configurar <code>ADMIN_ALLOWED_IPS=tu.ip.aqui</code> en el <code>.env</code> para proteger el panel.</div>
</div>

<h3>6.5 Onboarding (profile_completed)</h3>
<div class="model">
  <p>Flujo de onboarding: <code>accounts/utils/redirect_flow.py → get_user_redirect_flow(user)</code></p>
  <p>Al registrarse, <code>profile_completed=False</code>. El usuario debe completar su perfil antes de acceder a cualquier vista protegida con <code>@role_required</code>.</p>
  <p>Para coaches: aprobación de admin requerida (<code>CoachProfile.approval_status = APPROVED</code>).</p>
  <p>Para roles que requieren CURP: verificación adicional en onboarding.</p>
</div>

<h3>6.6 Allauth — Configuración</h3>
<div class="model">
  <table>
    <tr><th>Setting</th><th>Valor</th></tr>
    <tr><td><code>ACCOUNT_LOGIN_METHODS</code></td><td>email, username (ambos permitidos)</td></tr>
    <tr><td><code>ACCOUNT_EMAIL_VERIFICATION</code></td><td>mandatory (confirmar email antes de acceder)</td></tr>
    <tr><td><code>ACCOUNT_RATE_LIMITS</code></td><td>login_failed: 5 intentos / 300 segundos</td></tr>
    <tr><td><code>ACCOUNT_LOGOUT_ON_PASSWORD_CHANGE</code></td><td>True (invalida otras sesiones)</td></tr>
    <tr><td>OAuth providers</td><td>Google, Facebook, Apple (configurados)</td></tr>
    <tr><td>Custom adapters</td><td>CustomAccountAdapter, CustomSocialAccountAdapter, CustomInvitationsAdapter</td></tr>
    <tr><td>SITE_ID</td><td>2</td></tr>
  </table>
</div>

<h3>6.7 Cifrado PII</h3>
<div class="model">
  <p>Campos sensibles usan <code>EncryptedCharField</code> (Fernet + cryptography):</p>
  <ul>
    <li><code>User.curp</code> — CURP cifrada. Unicidad por <code>User.curp_hash</code> (HMAC determinístico)</li>
    <li><code>UserAddress.address</code>, <code>UserAddress.city</code>, <code>UserAddress.zip_code</code></li>
  </ul>
  <p><strong>Rotación de claves Fernet:</strong> <code>FERNET_KEYS</code> soporta múltiples claves (MultiFernet). Agregar nueva clave al inicio, dejar la anterior al final. Generar con:</p>
  <pre>python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"</pre>
</div>


<!-- ══════════════════════════ 7. URLs DEL SISTEMA ══════════════════════ -->
<div class="page-break"></div>
<h2>7. URLs del Sistema</h2>

<h3>7.1 URL Root (space_cheer/urls.py)</h3>
<table>
  <tr><th>Prefijo</th><th>Include</th></tr>
  <tr><td><code>/{ADMIN_URL}</code></td><td>Django admin (URL configurable via .env)</td></tr>
  <tr><td><code>/i18n/</code></td><td>Cambio de idioma (es/en)</td></tr>
  <tr><td><code>/</code></td><td>core.urls — Home/landing</td></tr>
  <tr><td><code>/accounts/</code></td><td>allauth.urls + accounts.urls.views_accounts_urls</td></tr>
  <tr><td><code>/guardian/</code></td><td>custody.urls — Relación guardián-menor</td></tr>
  <tr><td><code>/teams/</code></td><td>teams.urls</td></tr>
  <tr><td><code>/measures/</code></td><td>measures.urls</td></tr>
  <tr><td><code>/coach/</code></td><td>coach.urls</td></tr>
  <tr><td><code>/orders/</code></td><td>orders.urls</td></tr>
  <tr><td><code>/products/</code></td><td>products.urls</td></tr>
  <tr><td><code>/events/</code></td><td>events.urls (namespace: events)</td></tr>
  <tr><td><code>/hospitality/</code></td><td>hospitality.urls (namespace: hospitality)</td></tr>
  <tr><td><code>/social/</code></td><td>social.urls (namespace: social)</td></tr>
  <tr><td><code>/production/</code></td><td>production.urls (namespace: production)</td></tr>
  <tr><td><code>/invitations/</code></td><td>invitations.urls (namespace: invitations)</td></tr>
  <tr><td><code>/media/&lt;path&gt;</code></td><td>serve_protected_media — media protegida</td></tr>
</table>

<h3>7.2 Accounts URLs (namespace: accounts)</h3>
<table>
  <tr><th>URL</th><th>Nombre</th><th>Descripción</th></tr>
  <tr><td><code>/accounts/complete-profile/</code></td><td>profile_setup</td><td>Onboarding inicial</td></tr>
  <tr><td><code>/accounts/complete-profile/curp/</code></td><td>curp_verification</td><td>Verificación CURP</td></tr>
  <tr><td><code>/accounts/coach/pending/</code></td><td>coach_pending_approval</td><td>Pantalla de espera coach</td></tr>
  <tr><td><code>/accounts/coach/rejected/</code></td><td>coach_rejected</td><td>Pantalla coach rechazado</td></tr>
  <tr><td><code>/accounts/admin/headcoach-approvals/</code></td><td>headcoach_approvals</td><td>Aprobación headcoach</td></tr>
  <tr><td><code>/accounts/profile/edit/</code></td><td>profile_edit</td><td>Editar perfil</td></tr>
  <tr><td><code>/accounts/profile/photo/upload/</code></td><td>profile_photo_upload</td><td>Subir foto de perfil</td></tr>
  <tr><td><code>/accounts/profile/settings/</code></td><td>profile_settings</td><td>Configuraciones de perfil</td></tr>
  <tr><td><code>/accounts/search/</code></td><td>user_search</td><td>API búsqueda de usuarios</td></tr>
  <tr><td><code>/accounts/athletes/import/</code></td><td>bulk_import_athletes</td><td>Importación masiva de atletas</td></tr>
  <tr><td><code>/accounts/</code></td><td>list_address</td><td>Lista de direcciones</td></tr>
</table>

<h3>7.3 Orders URLs (namespace: orders)</h3>
<table>
  <tr><th>URL</th><th>Nombre</th><th>Descripción</th></tr>
  <tr><td><code>/orders/</code></td><td>manage_orders</td><td>Lista de órdenes</td></tr>
  <tr><td><code>/orders/create/</code></td><td>create_order</td><td>Crear nueva orden</td></tr>
  <tr><td><code>/orders/&lt;id&gt;/</code></td><td>detail_order</td><td>Detalle de orden</td></tr>
  <tr><td><code>/orders/&lt;id&gt;/edit/</code></td><td>edit_order</td><td>Editar orden</td></tr>
  <tr><td><code>/orders/&lt;id&gt;/contact/</code></td><td>contact_info_order</td><td>Info de contacto</td></tr>
  <tr><td><code>/orders/&lt;id&gt;/items/add/</code></td><td>add_item_product_order</td><td>Agregar producto a orden</td></tr>
  <tr><td><code>/orders/items/&lt;id&gt;/</code></td><td>order_item_detail</td><td>Detalle de item</td></tr>
  <tr><td><code>/orders/items/&lt;id&gt;/import-team/</code></td><td>item_import_team_athletes</td><td>Importar atletas del equipo</td></tr>
  <tr><td><code>/orders/items/athlete/&lt;id&gt;/measurements/</code></td><td>order_item_measurements</td><td>Ver medidas del atleta</td></tr>
  <tr><td><code>/orders/&lt;id&gt;/transition/&lt;status&gt;/</code></td><td>transition</td><td>Transicionar estado</td></tr>
  <tr><td><code>/orders/cart/</code></td><td>cart</td><td>Ver carrito</td></tr>
  <tr><td><code>/orders/admin/orders/</code></td><td>admin_order_list</td><td>Lista admin (IP whitelist)</td></tr>
  <tr><td><code>/orders/admin/orders/&lt;id&gt;/</code></td><td>admin_order_detail</td><td>Detalle admin</td></tr>
  <tr><td><code>/orders/admin/orders/&lt;id&gt;/upload-design/</code></td><td>admin_upload_design</td><td>Subir diseño final</td></tr>
  <tr><td><code>/orders/admin/orders/&lt;id&gt;/update-dates/</code></td><td>admin_update_order_dates</td><td>Actualizar fechas operativas</td></tr>
  <tr><td><code>/orders/admin/orders/&lt;id&gt;/close-measurements/</code></td><td>close_measurements</td><td>Cerrar medidas</td></tr>
  <tr><td><code>/orders/admin/orders/&lt;id&gt;/reopen-measurements/</code></td><td>reopen_measurements</td><td>Reabrir medidas</td></tr>
  <tr><td><code>/orders/admin/orders/&lt;id&gt;/lock-measurements/</code></td><td>lock_measurements</td><td>Bloquear medidas definitivamente</td></tr>
</table>

<h3>7.4 Production URLs (namespace: production)</h3>
<table>
  <tr><th>URL</th><th>Nombre</th><th>Rol requerido</th></tr>
  <tr><td><code>/production/</code></td><td>dashboard</td><td>OPERARIO — panel de tareas</td></tr>
  <tr><td><code>/production/mi-area/</code></td><td>mi_area</td><td>OPERARIO — mis tareas asignadas</td></tr>
  <tr><td><code>/production/task/&lt;pk&gt;/complete/</code></td><td>task_complete</td><td>OPERARIO — completar tarea</td></tr>
  <tr><td><code>/production/admin/</code></td><td>admin_overview</td><td>ADMIN/STAFF — resumen de producción</td></tr>
  <tr><td><code>/production/reglamento/</code></td><td>reglamento</td><td>Reglamento de producción</td></tr>
  <tr><td><code>/production/admin/job/&lt;pk&gt;/</code></td><td>admin_job_detail</td><td>ADMIN/STAFF — detalle de job</td></tr>
  <tr><td><code>/production/admin/task/&lt;pk&gt;/assign/</code></td><td>assign_task</td><td>ADMIN/STAFF — asignar operario</td></tr>
  <tr><td><code>/production/errores/</code></td><td>error_report_list</td><td>Lista de reportes de error</td></tr>
  <tr><td><code>/production/errores/nuevo/</code></td><td>create_error_report</td><td>Crear reporte de error</td></tr>
  <tr><td><code>/production/errores/&lt;pk&gt;/revisar/</code></td><td>review_error_report</td><td>ADMIN — revisar reporte</td></tr>
  <tr><td><code>/production/config/stages/</code></td><td>manage_stages</td><td>ADMIN — gestionar etapas</td></tr>
  <tr><td><code>/production/config/roles/</code></td><td>manage_roles</td><td>ADMIN — gestionar roles</td></tr>
  <tr><td><code>/production/config/operarios/</code></td><td>manage_operarios</td><td>ADMIN — gestionar operarios</td></tr>
  <tr><td><code>/production/config/plantillas/</code></td><td>manage_templates</td><td>ADMIN — plantillas de producción</td></tr>
  <tr><td><code>/production/config/product-stages/</code></td><td>product_stages_matrix</td><td>ADMIN — matriz producto/etapa</td></tr>
</table>

<h3>7.5 Teams URLs (namespace: teams)</h3>
<table>
  <tr><th>URL</th><th>Descripción</th></tr>
  <tr><td><code>/teams/my-team/</code></td><td>Ver mi equipo (atleta)</td></tr>
  <tr><td><code>/teams/join/</code></td><td>Unirse por código join_code</td></tr>
  <tr><td><code>/teams/coach/</code></td><td>Panel coach — mis equipos</td></tr>
  <tr><td><code>/teams/teams/</code></td><td>Gestionar equipos (admin/headcoach)</td></tr>
  <tr><td><code>/teams/manage_athletes/</code></td><td>Gestionar atletas</td></tr>
  <tr><td><code>/teams/&lt;id&gt;/members/</code></td><td>Miembros del equipo</td></tr>
  <tr><td><code>/teams/requests/&lt;id&gt;/accept/</code></td><td>Aceptar solicitud de membresía</td></tr>
</table>

<h3>7.6 Products URLs (namespace: products)</h3>
<table>
  <tr><th>URL</th><th>Descripción</th></tr>
  <tr><td><code>/products/catalog/</code></td><td>Catálogo público de productos</td></tr>
  <tr><td><code>/products/</code></td><td>Lista de productos (admin)</td></tr>
  <tr><td><code>/products/create/</code></td><td>Paso 1: elegir plantilla de producto</td></tr>
  <tr><td><code>/products/create/new/</code></td><td>Paso 2: formulario de creación</td></tr>
  <tr><td><code>/products/&lt;id&gt;/</code></td><td>Detalle/edición (tallas, medidas, toggle activo)</td></tr>
</table>


<!-- ═══════════════════════ 8. CELERY Y NOTIFICACIONES ══════════════════ -->
<div class="page-break"></div>
<h2>8. Sistema de Notificaciones y Celery</h2>

<h3>8.1 Configuración de Celery</h3>
<div class="model">
  <table>
    <tr><th>Setting</th><th>Valor en producción</th></tr>
    <tr><td><code>CELERY_BROKER_URL</code></td><td>redis://127.0.0.1:6379/0</td></tr>
    <tr><td><code>CELERY_RESULT_BACKEND</code></td><td>redis://127.0.0.1:6379/0</td></tr>
    <tr><td><code>CELERY_ACCEPT_CONTENT</code></td><td>["json"]</td></tr>
    <tr><td><code>CELERY_TASK_SERIALIZER</code></td><td>"json"</td></tr>
    <tr><td><code>CELERY_TIMEZONE</code></td><td>America/Mexico_City</td></tr>
    <tr><td><code>CELERY_TASK_ACKS_LATE</code></td><td>True (task confirmada solo tras completarse)</td></tr>
    <tr><td><code>CELERY_WORKER_PREFETCH_MULTIPLIER</code></td><td>1 (no pre-fetch de tareas)</td></tr>
    <tr><td>Concurrency worker</td><td>2 procesos</td></tr>
    <tr><td>Scheduler de Beat</td><td><code>django_celery_beat.schedulers:DatabaseScheduler</code></td></tr>
  </table>
  <p>Scheduler de tareas periódicas en base de datos → se gestiona desde el admin de Django o vía modelo <code>PeriodicTask</code>.</p>
</div>

<h3>8.2 Tareas Celery Definidas</h3>

<h4>production/tasks.py</h4>
<div class="model">
  <p><strong><code>notify_production_stage_complete(task_id)</code></strong></p>
  <ul>
    <li>Disparada por: <code>ProductionJobService.complete_task()</code> → <code>.delay(task.pk)</code></li>
    <li>Busca la <code>ProductionTask</code> por ID con select_related</li>
    <li>Obtiene todos los usuarios ADMIN+STAFF activos</li>
    <li>Llama <code>OrderNotificationService.notify_production_task_completed(task, admins_and_staff)</code></li>
    <li>Configuración: <code>max_retries=3</code>, <code>acks_late=True</code></li>
  </ul>

  <p><strong><code>notify_task_assigned(task_id)</code></strong></p>
  <ul>
    <li>Disparada por: <code>ProductionJobService.assign_task()</code> cuando se asigna un operario → <code>.delay(task.pk)</code></li>
    <li>Verifica que la tarea tenga <code>assigned_to</code> (si no, omite)</li>
    <li>Llama <code>OrderNotificationService.notify_task_assigned(task)</code></li>
    <li>En caso de error: retry con <code>countdown=60</code> segundos</li>
    <li>Configuración: <code>max_retries=3</code>, <code>acks_late=True</code></li>
  </ul>
</div>

<h4>accounts/tasks.py</h4>
<div class="model">
  <p>Tareas relacionadas con cuentas de usuario (no leídas en detalle, típicamente: limpieza de sesiones, expiración de invitaciones).</p>
</div>

<h4>orders/tasks.py</h4>
<div class="model">
  <p>Tareas relacionadas con órdenes. El management command <code>close_expired_measurements</code> también se puede ejecutar como tarea periódica.</p>
</div>

<h3>8.3 Flujo Completo de Notificación al Asignar Tarea</h3>
<pre class="diagram">
Admin → POST /production/admin/task/{pk}/assign/
     │
     ▼
ProductionJobService.assign_task(task, operario)
     │
     ├─ task.assigned_to = operario
     ├─ task.save(update_fields=["assigned_to"])
     └─ notify_task_assigned.delay(task.pk)
                    │
                    ▼ (asíncrono, en Celery Worker)
        notify_task_assigned(task_id)
                    │
                    ▼
        OrderNotificationService.notify_task_assigned(task)
                    │
                    ▼
        EmailMultiAlternatives → operario.email
        (Asunto: "Nueva tarea asignada: {stage.name} — Pedido #{id}")
</pre>

<h3>8.4 Archivos de Log de Celery</h3>
<ul>
  <li><code>logs/celery_worker.log</code> — log del worker</li>
  <li><code>logs/celery_beat.log</code> — log del beat scheduler</li>
</ul>
<pre>tail -f /home/space/SERVER/SPACE-CHEER1/space_cheer/logs/celery_worker.log</pre>


<!-- ═══════════════════════ 9. CONFIGURACIÓN DE PRODUCCIÓN ══════════════ -->
<div class="page-break"></div>
<h2>9. Configuración de Producción (Servidor)</h2>

<h3>9.1 Variables de Entorno Requeridas (.env)</h3>
<p>El archivo <code>.env</code> se ubica en <code>space_cheer/space_cheer/.env</code>. Nunca debe commitearse al repositorio.</p>
<table>
  <tr><th>Variable</th><th>Descripción</th><th>Ejemplo</th></tr>
  <tr><td><code>SECRET_KEY</code></td><td>Django secret key (50 hex chars)</td><td><code>secrets.token_hex(50)</code></td></tr>
  <tr><td><code>DEBUG</code></td><td>Modo debug (False en producción)</td><td><code>False</code></td></tr>
  <tr><td><code>ALLOWED_HOSTS</code></td><td>Hosts permitidos (CSV)</td><td><code>spacecheer.com,www.spacecheer.com</code></td></tr>
  <tr><td><code>CSRF_TRUSTED_ORIGINS</code></td><td>Orígenes CSRF confiables</td><td><code>https://spacecheer.com,https://www.spacecheer.com</code></td></tr>
  <tr><td><code>DB_NAME</code></td><td>Nombre de la base de datos</td><td><code>space_cheer_db</code></td></tr>
  <tr><td><code>DB_USER</code></td><td>Usuario de PostgreSQL</td><td><code>space_cheer_user</code></td></tr>
  <tr><td><code>DB_PASSWORD</code></td><td>Contraseña de PostgreSQL</td><td>(secreto)</td></tr>
  <tr><td><code>DB_HOST</code></td><td>Host de PostgreSQL</td><td><code>localhost</code></td></tr>
  <tr><td><code>DB_PORT</code></td><td>Puerto de PostgreSQL</td><td><code>5432</code></td></tr>
  <tr><td><code>CELERY_BROKER_URL</code></td><td>URL del broker Redis</td><td><code>redis://127.0.0.1:6379/0</code></td></tr>
  <tr><td><code>CELERY_RESULT_BACKEND</code></td><td>Backend de resultados Redis</td><td><code>redis://127.0.0.1:6379/0</code></td></tr>
  <tr><td><code>CELERY_TIMEZONE</code></td><td>Zona horaria de Celery</td><td><code>America/Mexico_City</code></td></tr>
  <tr><td><code>EMAIL_BACKEND</code></td><td>Backend de email</td><td><code>django.core.mail.backends.smtp.EmailBackend</code></td></tr>
  <tr><td><code>EMAIL_HOST</code></td><td>Servidor SMTP</td><td><code>smtp.gmail.com</code></td></tr>
  <tr><td><code>EMAIL_PORT</code></td><td>Puerto SMTP</td><td><code>587</code></td></tr>
  <tr><td><code>EMAIL_USE_TLS</code></td><td>TLS para SMTP</td><td><code>True</code></td></tr>
  <tr><td><code>EMAIL_HOST_USER</code></td><td>Usuario SMTP</td><td>(correo)</td></tr>
  <tr><td><code>EMAIL_HOST_PASSWORD</code></td><td>Contraseña SMTP (App Password)</td><td>(secreto)</td></tr>
  <tr><td><code>DEFAULT_FROM_EMAIL</code></td><td>Remitente por defecto</td><td><code>Space Cheer &lt;correo&gt;</code></td></tr>
  <tr><td><code>SESSION_COOKIE_SECURE</code></td><td>Cookie de sesión solo HTTPS</td><td><code>True</code></td></tr>
  <tr><td><code>CSRF_COOKIE_SECURE</code></td><td>Cookie CSRF solo HTTPS</td><td><code>True</code></td></tr>
  <tr><td><code>SECURE_SSL_REDIRECT</code></td><td>Fuerza HTTPS</td><td><code>True</code></td></tr>
  <tr><td><code>SECURE_HSTS_SECONDS</code></td><td>Duración HSTS (1 año)</td><td><code>31536000</code></td></tr>
  <tr><td><code>ADMIN_URL</code></td><td>URL del panel admin (ofuscar)</td><td><code>mi-panel-sc-2026/</code></td></tr>
  <tr><td><code>ADMIN_ALLOWED_IPS</code></td><td>IPs permitidas para admin (CSV)</td><td><code>1.2.3.4,5.6.7.8</code></td></tr>
  <tr><td><code>FERNET_KEYS</code></td><td>Claves Fernet para cifrado PII (CSV)</td><td><code>Fernet.generate_key()</code></td></tr>
</table>

<h3>9.2 Proceso de Re-deploy</h3>
<pre>cd /home/space/SERVER/SPACE-CHEER1
source venv/bin/activate

# 1. Obtener cambios
git pull origin main

# 2. Actualizar dependencias (solo si cambió requirements.txt)
pip install -r space_cheer/requirements.txt

# 3. Aplicar migraciones
cd space_cheer
python manage.py migrate

# 4. Recolectar archivos estáticos
python manage.py collectstatic --noinput

# 5. Reiniciar todos los servicios
systemctl restart space-cheer space-cheer-worker space-cheer-beat</pre>

<div class="warn"><strong>Migraciones en producción:</strong> Ejecutar siempre <code>python manage.py check --deploy</code> antes de migrate en producción para detectar configuraciones inseguras.</div>

<h3>9.3 Gunicorn — Configuración</h3>
<div class="model">
  <table>
    <tr><th>Parámetro</th><th>Valor</th></tr>
    <tr><td>Workers</td><td>3 (recomendado: 2×CPU + 1)</td></tr>
    <tr><td>Bind</td><td>127.0.0.1:8002</td></tr>
    <tr><td>Access log</td><td><code>logs/gunicorn_access.log</code></td></tr>
    <tr><td>Error log</td><td><code>logs/gunicorn_error.log</code></td></tr>
    <tr><td>Restart</td><td>on-failure (systemd)</td></tr>
  </table>
</div>

<h3>9.4 Nginx — Configuración Clave</h3>
<div class="model">
  <ul>
    <li><code>client_max_body_size 40M</code> — para uploads de diseño de alta resolución</li>
    <li><code>proxy_set_header X-Forwarded-Proto $scheme</code> — CRÍTICO para allauth 65.x (sin esto: login 403)</li>
    <li>WhiteNoise sirve <code>/static/</code> desde Django directamente (no requiere bloque en Nginx)</li>
    <li>SSL gestionado por certbot con auto-renovación via systemd timer</li>
    <li>Firewall Hetzner: puertos 22, 80, 443 permitidos</li>
  </ul>
</div>

<h3>9.5 Logs y Monitoreo</h3>
<table>
  <tr><th>Log</th><th>Ruta</th></tr>
  <tr><td>Django (INFO+)</td><td><code>logs/django.log</code></td></tr>
  <tr><td>Django errores críticos</td><td><code>logs/errors.log</code></td></tr>
  <tr><td>Gunicorn access</td><td><code>logs/gunicorn_access.log</code></td></tr>
  <tr><td>Gunicorn errores</td><td><code>logs/gunicorn_error.log</code></td></tr>
  <tr><td>Celery worker</td><td><code>logs/celery_worker.log</code></td></tr>
  <tr><td>Celery beat</td><td><code>logs/celery_beat.log</code></td></tr>
  <tr><td>Nginx errores</td><td><code>/var/log/nginx/error.log</code></td></tr>
</table>
<pre>journalctl -u space-cheer -f           # Gunicorn en tiempo real
journalctl -u space-cheer-worker -f    # Celery worker en tiempo real
tail -f logs/errors.log                # Solo errores críticos Django</pre>

<h3>9.6 SSL / Certbot</h3>
<pre>certbot certificates                                   # Ver estado del cert
certbot renew --dry-run                                # Probar renovación
# Renovación automática: systemd timer activo</pre>
<div class="success">SSL activo. Certificado expira 2026-09-08. Renovación automática configurada.</div>


<!-- ═══════════════════════════ 10. GUÍA DE DESARROLLO ══════════════════ -->
<div class="page-break"></div>
<h2>10. Guía de Desarrollo</h2>

<h3>10.1 Setup del Entorno Local</h3>
<pre>cd C:/Users/Lenovo/Documents/SPACE-CHEER/
python -m venv venv
venv/Scripts/activate            # Windows (PowerShell: venv\Scripts\Activate.ps1)
pip install -r space_cheer/requirements.txt

# Crear .env en space_cheer/space_cheer/.env
# Copiar variables con DEBUG=True y SECURE_SSL_REDIRECT=False

cd space_cheer
python manage.py migrate
PYTHONUTF8=1 python manage.py seed_all --verbose   # Roles + staff roles + room features
python manage.py createsuperuser

# Iniciar servidor
python manage.py runserver

# Celery (en terminal separada, requiere Redis)
celery -A space_cheer worker -l info
celery -A space_cheer beat -l info</pre>

<h3>10.2 Comandos manage.py Útiles</h3>
<table>
  <tr><th>Comando</th><th>Descripción</th></tr>
  <tr><td><code>python manage.py seed_all --verbose</code></td><td>Ejecuta todos los seeds (roles, staff_roles, room_features)</td></tr>
  <tr><td><code>python manage.py seed_roles --verbose</code></td><td>Crea roles: ADMIN, HEADCOACH, COACH, STAFF, ATLETA, ACOMPANANTE, OPERARIO</td></tr>
  <tr><td><code>python manage.py seed_staff_roles --verbose</code></td><td>Roles específicos de staff</td></tr>
  <tr><td><code>python manage.py seed_room_features --verbose</code></td><td>Features de habitaciones (hospitality)</td></tr>
  <tr><td><code>python manage.py close_expired_measurements</code></td><td>Cierra medidas de órdenes con fecha límite vencida</td></tr>
  <tr><td><code>python manage.py close_expired_measurements --dry-run</code></td><td>Simula sin cambios</td></tr>
  <tr><td><code>python manage.py close_expired_measurements --order-id=123</code></td><td>Aplica a una orden específica</td></tr>
  <tr><td><code>python manage.py migrate</code></td><td>Aplicar migraciones</td></tr>
  <tr><td><code>python manage.py makemigrations</code></td><td>Crear migraciones</td></tr>
  <tr><td><code>python manage.py collectstatic --noinput</code></td><td>Recolectar estáticos</td></tr>
  <tr><td><code>python manage.py check --deploy</code></td><td>Verificar configuración de producción</td></tr>
  <tr><td><code>python manage.py createsuperuser</code></td><td>Crear superusuario</td></tr>
  <tr><td><code>python manage.py shell</code></td><td>Shell interactivo Django</td></tr>
</table>

<div class="warn"><strong>Queries en producción:</strong> Usar <code>psql -h 127.0.0.1 -U space_cheer_user -d space_cheer_db</code> directamente. No usar <code>manage.py shell -c</code> en producción (problema con wrap del terminal).</div>

<h3>10.3 Cómo Correr Tests</h3>
<pre>cd space_cheer

# Todos los tests configurados (pytest.ini define testpaths)
pytest

# Un archivo específico
pytest orders/tests/test_models.py

# Un test específico
pytest orders/tests/test_models.py::ClassName::test_method

# Con coverage report
pytest --cov=orders</pre>

<p><strong>Configuración pytest.ini:</strong></p>
<ul>
  <li>Reutiliza la base de datos de tests (<code>--reuse-db</code>)</li>
  <li>Omite migraciones (<code>--nomigrations</code>) — más rápido</li>
  <li>Cobertura medida sobre la app <code>orders</code></li>
  <li>Para en el primer fallo (<code>--maxfail=1</code>)</li>
</ul>

<p><strong>Ubicación de tests:</strong></p>
<table>
  <tr><th>App</th><th>Tests</th></tr>
  <tr><td>orders</td><td><code>orders/tests/</code> (directorio con múltiples archivos)</td></tr>
  <tr><td>accounts</td><td><code>accounts/tests.py</code>, <code>test_admin_approvals.py</code>, <code>test_coach_approval.py</code></td></tr>
  <tr><td>teams</td><td><code>teams/tests.py</code>, <code>test_join_code.py</code>, <code>test_membership_flow.py</code>, <code>test_permissions.py</code></td></tr>
  <tr><td>measures</td><td><code>measures/tests.py</code></td></tr>
  <tr><td>products</td><td><code>products/tests.py</code></td></tr>
  <tr><td>production</td><td><code>production/tests.py</code>, <code>test_product_stages.py</code>, <code>test_views.py</code></td></tr>
</table>

<h3>10.4 Variables de Entorno para Desarrollo Local</h3>
<pre>SECRET_KEY=dev-key-no-usar-en-produccion
DEBUG=True
ALLOWED_HOSTS=localhost,127.0.0.1
CSRF_TRUSTED_ORIGINS=http://localhost:8000

DB_NAME=space_cheer_dev
DB_USER=postgres
DB_PASSWORD=tu_password
DB_HOST=localhost
DB_PORT=5432

CELERY_BROKER_URL=redis://127.0.0.1:6379/0
CELERY_RESULT_BACKEND=redis://127.0.0.1:6379/0
CELERY_TIMEZONE=America/Mexico_City

EMAIL_BACKEND=django.core.mail.backends.console.EmailBackend
EMAIL_HOST=smtp.gmail.com
EMAIL_PORT=587
EMAIL_USE_TLS=True
EMAIL_HOST_USER=test@example.com
EMAIL_HOST_PASSWORD=test
DEFAULT_FROM_EMAIL=test@example.com

SESSION_COOKIE_SECURE=False
CSRF_COOKIE_SECURE=False
SECURE_SSL_REDIRECT=False
SECURE_HSTS_SECONDS=0

ADMIN_URL=admin/
ADMIN_ALLOWED_IPS=

FERNET_KEYS=tu_clave_fernet_aqui</pre>

<h3>10.5 Estructura de Templates</h3>
<pre>space_cheer/
├── templates/              ← Templates globales (base.html, navbar, footer)
├── accounts/
│   └── templates/accounts/ ← Templates de cuentas
├── orders/
│   └── templates/orders/   ← Templates de órdenes
├── production/
│   └── templates/production/ ← Templates de producción
└── ...</pre>


<!-- ══════════════════════════ 11. SEGURIDAD ════════════════════════════ -->
<div class="page-break"></div>
<h2>11. Seguridad</h2>

<h3>11.1 Headers de Seguridad</h3>
<table>
  <tr><th>Header</th><th>Valor / Configuración</th></tr>
  <tr><td>HSTS</td><td>Strict-Transport-Security: max-age=31536000; includeSubDomains; preload</td></tr>
  <tr><td>Content-Security-Policy</td><td>default-src 'self'; script-src 'self' CDNs + nonce; style-src 'self' + nonce; frame-ancestors 'none'</td></tr>
  <tr><td>X-Frame-Options</td><td>DENY (clickjacking)</td></tr>
  <tr><td>X-Content-Type-Options</td><td>nosniff</td></tr>
  <tr><td>Referrer-Policy</td><td>strict-origin-when-cross-origin</td></tr>
  <tr><td>Permissions-Policy</td><td>camera=(), microphone=(), geolocation=()</td></tr>
</table>

<h3>11.2 Content Security Policy (CSP) con Nonce</h3>
<div class="model">
  <p>Implementado con <code>django-csp 4.0</code>. <strong>Sin 'unsafe-inline'</strong>. Todos los scripts y estilos inline usan nonce:</p>
  <pre>&lt;script nonce="{{ request.csp_nonce }}"&gt;
  // código JS inline seguro
&lt;/script&gt;

&lt;style nonce="{{ request.csp_nonce }}"&gt;
  /* estilos inline seguros */
&lt;/style&gt;</pre>
  <p>CDNs permitidos: jQuery, DataTables, jsDelivr, Fonts Google (solo en style-src).</p>
</div>

<h3>11.3 Protección contra XSS</h3>
<div class="model">
  <ul>
    <li>Templates Django auto-escapan por defecto</li>
    <li>En código JS: siempre <code>element.textContent = value</code> (nunca <code>innerHTML</code>)</li>
    <li>CSP nonce previene inyección de scripts no autorizados</li>
    <li>Datos de API devueltos como JSON parseado, no como HTML</li>
  </ul>
</div>

<h3>11.4 CSRF</h3>
<div class="model">
  <ul>
    <li><code>CsrfViewMiddleware</code> activo en todas las vistas POST</li>
    <li><code>CSRF_COOKIE_SAMESITE = "Strict"</code></li>
    <li><code>CSRF_COOKIE_SECURE = True</code> en producción (solo HTTPS)</li>
    <li>Vistas con efectos de escritura usan siempre <code>{% csrf_token %}</code></li>
    <li>APIs internas: CSRF token en header <code>X-CSRFToken</code></li>
  </ul>
</div>

<h3>11.5 IP Whitelist para Admin</h3>
<div class="model">
  <p><code>AdminIPWhitelistMiddleware</code> (accounts/middleware.py) protege:</p>
  <ul>
    <li><code>/{ADMIN_URL}</code> — panel Django admin</li>
    <li><code>/orders/admin/</code> — panel de administración de órdenes</li>
  </ul>
  <pre>ADMIN_URL=mi-panel-sc-2026/     # URL admin ofuscada
ADMIN_ALLOWED_IPS=1.2.3.4,5.6.7.8   # Solo estas IPs</pre>
  <p>Si ADMIN_ALLOWED_IPS está vacío → no hay restricción por IP (desactivado).</p>
</div>

<h3>11.6 Protección de Contraseñas</h3>
<div class="model">
  <ul>
    <li>Mínimo 12 caracteres (plataforma maneja datos de menores — LGDNNA)</li>
    <li>UserAttributeSimilarityValidator, CommonPasswordValidator, NumericPasswordValidator</li>
    <li>Sesión invalidada al cambiar contraseña (<code>ACCOUNT_LOGOUT_ON_PASSWORD_CHANGE=True</code>)</li>
    <li>Rate limiting en login: 5 intentos fallidos / 300 segundos</li>
  </ul>
</div>

<h3>11.7 PII Audit Log</h3>
<div class="model">
  <p>Registro de auditoría para datos sensibles (CURP, medidas, dirección de menores):</p>
  <ul>
    <li>Modelo: <code>PiiAccessLog</code></li>
    <li>Escritura: solo vía <code>PiiAuditService.log()</code></li>
    <li>Retención mínima: 5 años (LFPDPPP)</li>
    <li>Índices en: <code>(accessed_by, timestamp)</code>, <code>(target_user, timestamp)</code>, <code>(access_type, timestamp)</code></li>
  </ul>
  <p>Tipos de acceso: VIEW_CURP, VIEW_MEDICAL, VIEW_MEASUREMENTS, VIEW_ADDRESS, EXPORT_DATA, EDIT_PROFILE, BULK_IMPORT</p>
</div>

<h3>11.8 Cifrado de Campos PII</h3>
<div class="model">
  <ul>
    <li>CURP: <code>EncryptedCharField</code> con Fernet (AES-128-CBC + HMAC-SHA256)</li>
    <li>Dirección (calle, ciudad, CP): <code>EncryptedCharField</code></li>
    <li>Unicidad del CURP cifrado: HMAC determinístico en <code>curp_hash</code></li>
    <li>Rotación de claves: MultiFernet (agregar nueva al inicio, dejar antigua al final)</li>
  </ul>
</div>

<h3>11.9 Validación de Archivos</h3>
<div class="model">
  <ul>
    <li>Magic bytes (python-magic): verifica que el archivo sea realmente una imagen/audio</li>
    <li>Extensión válida no es suficiente — se valida el header binario</li>
    <li>Tamaño máximo upload: 5 MB (<code>DATA_UPLOAD_MAX_MEMORY_SIZE</code>)</li>
    <li>Diseños de orden: mínimo 3.5 MB (<code>validate_min_size_35mb</code>)</li>
    <li>Aplicado en: <code>User.foto_perfil</code>, <code>Team.logo</code>, <code>Product.image</code>, <code>OrderDesignImage.image</code>, <code>TeamSong.audio</code></li>
  </ul>
</div>

<h3>11.10 Sesiones</h3>
<div class="model">
  <table>
    <tr><th>Setting</th><th>Valor</th></tr>
    <tr><td>SESSION_COOKIE_HTTPONLY</td><td>True (JS no puede leer la cookie)</td></tr>
    <tr><td>SESSION_COOKIE_SECURE</td><td>True en producción</td></tr>
    <tr><td>SESSION_COOKIE_AGE</td><td>8 horas (28800 segundos)</td></tr>
    <tr><td>SESSION_COOKIE_SAMESITE</td><td>Lax</td></tr>
  </table>
</div>

<h3>11.11 Límite de Upload (Anti-DoS)</h3>
<div class="model">
  <ul>
    <li><code>DATA_UPLOAD_MAX_MEMORY_SIZE = 5 MB</code></li>
    <li><code>FILE_UPLOAD_MAX_MEMORY_SIZE = 5 MB</code></li>
    <li>Nginx: <code>client_max_body_size 40M</code> (para diseños de alta resolución)</li>
  </ul>
</div>

<h3>11.12 Invitaciones</h3>
<div class="model">
  <ul>
    <li><code>django-invitations 2.1.0</code> — sistema de invitaciones por email</li>
    <li>Expiración: 7 días (<code>INVITATIONS_INVITATION_EXPIRY</code>)</li>
    <li>Registro primero, luego activar invitación (<code>INVITATIONS_ACCEPT_INVITE_AFTER_SIGNUP=True</code>)</li>
  </ul>
</div>

<hr>
<p style="text-align:center; color:#94a3b8; font-size:8.5pt; margin-top:30px;">
  Manual Técnico Space Cheer v1.0 &mdash; Generado automáticamente desde el código fuente &mdash; 2026-06-22<br>
  Para uso interno del equipo de desarrollo. No distribuir externamente.
</p>

</body>
</html>"""

# ─── GENERACIÓN DEL PDF ────────────────────────────────────────────────────────

OUTPUT_PATH = "C:/Users/Lenovo/Documents/SPACE-CHEER/manual_tecnico.pdf"

def main():
    print("Generando manual tecnico PDF...", flush=True)
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page()
        page.set_content(HTML, wait_until="domcontentloaded")
        page.pdf(
            path=OUTPUT_PATH,
            format="A4",
            print_background=True,
            margin={"top": "15mm", "bottom": "15mm", "left": "15mm", "right": "15mm"},
        )
        browser.close()
    import os
    size = os.path.getsize(OUTPUT_PATH)
    print(f"PDF generado exitosamente: {OUTPUT_PATH}")
    print(f"Tamanio: {size:,} bytes ({size / 1024 / 1024:.2f} MB)")

if __name__ == "__main__":
    main()
