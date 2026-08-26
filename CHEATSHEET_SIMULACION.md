# Space Cheer — Cheatsheet de la simulación

> Generado el **2026-08-25** por `python manage.py simulate_platform`.
> Base local PostgreSQL `SPACE`. Todos los usuarios comparten la contraseña **`Test1234!`**.

## Cómo levantar el entorno

```bash
cd C:\Users\Lenovo\Documents\SPACE-CHEER\space_cheer
../venv/Scripts/python.exe manage.py runserver 8000
# → http://127.0.0.1:8000/
```

Para reconstruir la simulación desde cero (borra y recrea la base `SPACE`):

```bash
psql -h localhost -U postgres -c 'DROP DATABASE "SPACE";'
psql -h localhost -U postgres -c 'CREATE DATABASE "SPACE" OWNER postgres;'
../venv/Scripts/python.exe manage.py migrate
../venv/Scripts/python.exe manage.py seed_all
../venv/Scripts/python.exe manage.py seed_products
../venv/Scripts/python.exe manage.py seed_full_data
CELERY_BROKER_URL=memory:// ../venv/Scripts/python.exe manage.py simulate_platform \
    --json-out ../SIMULACION.json
```

> `CELERY_BROKER_URL=memory://` no es opcional: sin Redis vivo, cada notificación espera 3 s reintentando contra `redis:6379` y la corrida pasa de 40 s a ~20 min.

## Qué hay cargado

| Módulo | Contenido |
|---|---|
| Usuarios | 48, todos con perfil completo, CURP y dirección |
| Equipos | 3 con head coach, 2 coaches y 8 atletas cada uno |
| Pedidos | 10 cubriendo los 6 estados del ciclo |
| Jobs de producción | 6 con tareas asignadas por etapa |
| Reportes de error | 3 con las 3 resoluciones de dirección |
| Eventos | 3 (uno abierto, dos cerrados con resultados) |
| Hospedaje | 4 habitaciones de equipo + una de staff |

---

## Usuarios

Contraseña para **todos**: `Test1234!`

Los 48 tienen el correo **verificado y primario** en allauth, así que se entra directo aunque `ACCOUNT_EMAIL_VERIFICATION` esté en `mandatory` (el default del settings; el `.env` local lo baja a `none`).

### Administración

| Correo | Nombre | Equipo | Qué hace en la simulación |
|---|---|---|---|
| `admin@test.com` | Bryan Sánchez | — | Superusuario. Aprueba diseños, manda a producción, entrega, revisa reportes de error. |

### Staff de oficina

| Correo | Nombre | Equipo | Qué hace en la simulación |
|---|---|---|---|
| `staff@test.com` | Renata Galindo | — | Staff de oficina. Captura pedidos offline y da seguimiento. |

### Jueces

| Correo | Nombre | Equipo | Qué hace en la simulación |
|---|---|---|---|
| `juez1@test.com` | Elena Castaño | — | Panel de jueces del Grand Prix. Califica por criterio. |
| `juez2@test.com` | Ricardo Fuentes | — | Panel de jueces del Grand Prix. Califica por criterio. |
| `juez3@test.com` | Mónica Beltrán | — | Panel de jueces del Grand Prix. Califica por criterio. |

### Head coaches

| Correo | Nombre | Equipo | Qué hace en la simulación |
|---|---|---|---|
| `hc.meteors@test.com` | Rodrigo Altair | Meteors | Head coach de Meteors. Crea pedidos del equipo y aprueba el diseño. |
| `hc.supernovas@test.com` | Mariana Polaris | Supernovas | Head coach de Supernovas. Crea pedidos del equipo y aprueba el diseño. |
| `hc.comets@test.com` | Diego Orión | Comets | Head coach de Comets. Crea pedidos del equipo y aprueba el diseño. |

### Coaches auxiliares

| Correo | Nombre | Equipo | Qué hace en la simulación |
|---|---|---|---|
| `coach.meteors2@test.com` | Carlos Arcturus | Meteors | Coach auxiliar de Meteors. Captura medidas de atletas. |
| `coach.meteors1@test.com` | Natalia Vega | Meteors | Coach auxiliar de Meteors. Captura medidas de atletas. |
| `coach.supernovas2@test.com` | Héctor Deneb | Supernovas | Coach auxiliar de Supernovas. Captura medidas de atletas. |
| `coach.supernovas1@test.com` | Paola Capella | Supernovas | Coach auxiliar de Supernovas. Captura medidas de atletas. |
| `coach.comets2@test.com` | Jorge Rigel | Comets | Coach auxiliar de Comets. Captura medidas de atletas. |
| `coach.comets1@test.com` | Laura Sirius | Comets | Coach auxiliar de Comets. Captura medidas de atletas. |

### Atletas

Todos son menores de edad (fuerza el flujo de tutor) y tienen las 8 medidas cargadas en su perfil.

| Equipo | Correos | Nombres |
|---|---|---|
| Comets | `atleta.comets1@test.com` … `atleta.comets8@test.com` | Sofía Cruz, Valeria Torres, Camila Ramírez, Isabella Flores, Daniela Reyes, Fernanda Morales, Lucía Jiménez, Andrea López |
| Meteors | `atleta.meteors1@test.com` … `atleta.meteors8@test.com` | Natalia Salinas, Paulina Aguilar, Stephanie Romero, Mónica Sánchez, Patricia Guerrero, Verónica Delgado, Adriana Vázquez, Claudia Ramos |
| Supernovas | `atleta.supernovas1@test.com` … `atleta.supernovas8@test.com` | Regina Mendoza, Ximena Castro, Renata Guzmán, Alejandra Herrera, Mariana Ríos, Karla Ortega, Diana Vargas, Brenda Peña |

### Tutores / acompañantes

| Correo | Nombre | Equipo | Qué hace en la simulación |
|---|---|---|---|
| `tutor.comets@test.com` | Alicia Cruz | Comets | PADRE — tutor de: Sofía Cruz, Valeria Torres |
| `tutor.supernovas@test.com` | Óscar Mendoza | Supernovas | TUTOR — tutor de: Regina Mendoza, Ximena Castro |
| `tutor.meteors@test.com` | Gabriela Salinas | Meteors | PADRE — tutor de: Natalia Salinas, Paulina Aguilar |

### Operarios de taller

| Correo | Nombre | Equipo | Qué hace en la simulación |
|---|---|---|---|
| `operario.cone@test.com` | Concepción Ibarra | — | Rol de producción CONE → etapas: Selección de Tallas, Sublimación, Calidad Final, Empaque |
| `operario.tino@test.com` | Faustino Ramírez | — | Rol de producción SR. TINO → etapas: Planeación de Materiales, Corte |
| `operario.dani@test.com` | Daniela Ochoa | — | Rol de producción DANI → etapas: Control y Surtido de Materiales, Calidad de Aplicaciones y Cristalería |
| `operario.chino@test.com` | Joaquín Lara | — | Rol de producción CHINO → etapas: Cristalería y Plantillas |
| `operario.chivis@test.com` | Silvia Contreras | — | Rol de producción SRA. CHIVIS → etapas: Costura |
| `operario.tere@test.com` | Teresa Nava | — | Rol de producción TERE → etapas: Calidad de Costura |
| `operario.manuel@test.com` | Manuel Zepeda | — | Rol de producción MANUEL → etapas: Envíos |

---

## Equipos

| Equipo | Ciudad | Código de ingreso | Head coach | Atletas |
|---|---|---|---|---|
| Meteors | Puebla | `09FBBF` | `hc.meteors@test.com` | 8 |
| Supernovas | Monterrey | `83F846` | `hc.supernovas@test.com` | 8 |
| Comets | Guadalajara | `2BE090` | `hc.comets@test.com` | 8 |

---

## Pedidos

Un pedido por cada estado del ciclo de vida, más los tres tipos (`TEAM`, `PERSONAL`, `OFFLINE`).

| # | Tipo | Dueño | Estado | Job | Creado por | Total |
|---|---|---|---|---|---|---|
| **1** | TEAM | Comets — Diego Orión | Entregado | Completado | `hc.comets@test.com` | $18000.00 |
| **2** | TEAM | Supernovas — Mariana Polaris | En producción | En progreso | `hc.supernovas@test.com` | $21200.00 |
| **3** | TEAM | Meteors — Rodrigo Altair | En producción | En progreso | `hc.meteors@test.com` | $17280.00 |
| **4** | TEAM | Comets — Diego Orión | En producción | Pausado | `hc.comets@test.com` | $2560.00 |
| **5** | TEAM | Supernovas — Mariana Polaris | Pendiente | — | `hc.supernovas@test.com` | $14400.00 |
| **6** | TEAM | Meteors — Rodrigo Altair | Diseño aprobado | — | `hc.meteors@test.com` | $27200.00 |
| **7** | TEAM | Comets — Diego Orión | Borrador | — | `hc.comets@test.com` | $1800.00 |
| **8** | TEAM | Supernovas — Mariana Polaris | Cancelado | — | `hc.supernovas@test.com` | $6800.00 |
| **9** | PERSONAL | Sofía Cruz | Entregado | Completado | `atleta.comets1@test.com` | $1300.00 |
| **10** | OFFLINE | Academia Estelar A.C. (3339998877) | En producción | En progreso | `staff@test.com` | $21000.00 |

### Detalle por pedido

#### Pedido #1 — Entregado

- **Dueño:** Comets — Diego Orión · **tipo:** `TEAM` · **creado por:** `hc.comets@test.com`
- **Contenido:** 8× Uniforme Personalizado por Equipo — 8 atletas asignados; 8× Mochila Space Cheer
- **Medidas:** bloqueadas · límite 2026-09-03
- **Entrega comprometida:** 2026-10-08
- **Para qué sirve:** Se entrega al final de la fase 4, cuando su job cierra todas las etapas.
- **Bitácora:** — → DRAFT (hc.comets@test.com) · DRAFT → PENDING (hc.comets@test.com) · PENDING → DESIGN_APPROVED (hc.comets@test.com) · DESIGN_APPROVED → IN_PRODUCTION (admin@test.com) · IN_PRODUCTION → DELIVERED (admin@test.com)

#### Pedido #2 — En producción

- **Dueño:** Supernovas — Mariana Polaris · **tipo:** `TEAM` · **creado por:** `hc.supernovas@test.com`
- **Contenido:** 8× Tenis de Competencia (talla 25); 8× Uniforme Personalizado por Equipo — 8 atletas asignados
- **Medidas:** bloqueadas · límite 2026-09-03
- **Entrega comprometida:** 2026-09-23
- **Para qué sirve:** Job en progreso: avanza hasta costura y ahí se queda.
- **Bitácora:** — → DRAFT (hc.supernovas@test.com) · DRAFT → PENDING (hc.supernovas@test.com) · PENDING → DESIGN_APPROVED (admin@test.com) · DESIGN_APPROVED → IN_PRODUCTION (admin@test.com)

#### Pedido #3 — En producción

- **Dueño:** Meteors — Rodrigo Altair · **tipo:** `TEAM` · **creado por:** `hc.meteors@test.com`
- **Contenido:** 8× Uniforme Personalizado por Equipo — 8 atletas asignados; 16× Accesorio Porrista
- **Medidas:** bloqueadas · límite 2026-09-03
- **Entrega comprometida:** 2026-09-13
- **Para qué sirve:** Job marcado URGENTE. Solo pasó selección de tallas y planeación.
- **Bitácora:** — → DRAFT (hc.meteors@test.com) · DRAFT → PENDING (hc.meteors@test.com) · PENDING → DESIGN_APPROVED (hc.meteors@test.com) · DESIGN_APPROVED → IN_PRODUCTION (admin@test.com)

#### Pedido #4 — En producción

- **Dueño:** Comets — Diego Orión · **tipo:** `TEAM` · **creado por:** `hc.comets@test.com`
- **Contenido:** 8× Shorts de Entrenamiento (talla M)
- **Medidas:** bloqueadas · límite 2026-09-03
- **Entrega comprometida:** 2026-10-23
- **Para qué sirve:** Producto sin diseño: PENDING → IN_PRODUCTION directo. El job se pausa por falta de material.
- **Bitácora:** — → DRAFT (hc.comets@test.com) · DRAFT → PENDING (hc.comets@test.com) · PENDING → IN_PRODUCTION (admin@test.com)

#### Pedido #5 — Pendiente

- **Dueño:** Supernovas — Mariana Polaris · **tipo:** `TEAM` · **creado por:** `hc.supernovas@test.com`
- **Contenido:** 8× Uniforme Personalizado por Equipo — 8 atletas asignados
- **Medidas:** abiertas · límite 2026-09-03
- **Entrega comprometida:** 2026-11-02
- **Para qué sirve:** PENDING sin diseño final subido. Es el pedido para probar la aprobación.
- **Bitácora:** — → DRAFT (hc.supernovas@test.com) · DRAFT → PENDING (hc.supernovas@test.com)

#### Pedido #6 — Diseño aprobado

- **Dueño:** Meteors — Rodrigo Altair · **tipo:** `TEAM` · **creado por:** `hc.meteors@test.com`
- **Contenido:** 8× Uniforme Base (talla M); 2× Playera de Entrenamiento del Equipo (talla S) — 2 atletas asignados; 3× Playera de Entrenamiento del Equipo (talla M) — 3 atletas asignados; 2× Playera de Entrenamiento del Equipo (talla L) — 2 atletas asignados; 1× Playera de Entrenamiento del Equipo (talla XL) — 1 atletas asignados; 8× Uniforme Personalizado por Equipo — 8 atletas asignados
- **Medidas:** cerradas (reabribles) · límite 2026-09-03
- **Entrega comprometida:** 2026-11-12
- **Para qué sirve:** DESIGN_APPROVED con medidas cerradas pero sin bloquear: falta el bloqueo y el primer pago para producción. Trae el reparto de tallas por alumna, así que su hoja imprimible tiene contenido.
- **Bitácora:** — → DRAFT (hc.meteors@test.com) · DRAFT → PENDING (hc.meteors@test.com) · PENDING → DESIGN_APPROVED (hc.meteors@test.com)

#### Pedido #7 — Borrador

- **Dueño:** Comets — Diego Orión · **tipo:** `TEAM` · **creado por:** `hc.comets@test.com`
- **Contenido:** 4× Mochila Space Cheer
- **Medidas:** abiertas
- **Para qué sirve:** DRAFT editable. Sirve para probar agregar/quitar items y tallas.
- **Bitácora:** — → DRAFT (hc.comets@test.com)

#### Pedido #8 — Cancelado

- **Dueño:** Supernovas — Mariana Polaris · **tipo:** `TEAM` · **creado por:** `hc.supernovas@test.com`
- **Contenido:** 8× Tenis de Competencia (talla 24)
- **Medidas:** abiertas · límite 2026-09-03
- **Entrega comprometida:** 2026-10-08
- **Para qué sirve:** CANCELLED desde PENDING con motivo registrado.
- **Bitácora:** — → DRAFT (hc.supernovas@test.com) · DRAFT → PENDING (hc.supernovas@test.com) · PENDING → CANCELLED (hc.supernovas@test.com)

#### Pedido #9 — Entregado

- **Dueño:** Sofía Cruz · **tipo:** `PERSONAL` · **creado por:** `atleta.comets1@test.com`
- **Contenido:** 1× Tenis de Competencia (talla 25); 1× Mochila Space Cheer
- **Medidas:** bloqueadas
- **Entrega comprometida:** 2026-09-18
- **Para qué sirve:** Pedido PERSONAL de catálogo. Job corto (surtido→envíos), se entrega en la fase 4.
- **Bitácora:** — → DRAFT (atleta.comets1@test.com) · DRAFT → PENDING (atleta.comets1@test.com) · PENDING → IN_PRODUCTION (admin@test.com) · IN_PRODUCTION → DELIVERED (admin@test.com)

#### Pedido #10 — En producción

- **Dueño:** Academia Estelar A.C. (3339998877) · **tipo:** `OFFLINE` · **creado por:** `staff@test.com`
- **Contenido:** 6× Chamarra Academia Estelar; 12× Uniforme Taller (captura offline)
- **Medidas:** cerradas (reabribles)
- **Entrega comprometida:** 2026-09-28
- **Pagos:** precio acordado $21000.00 · estado `ANTICIPO`
- **Para qué sirve:** OFFLINE de mostrador. Acordado $21,000, anticipo $8,000, saldo $13000.00. No se puede entregar hasta liquidar.
- **Bitácora:** DRAFT → PENDING (staff@test.com) · PENDING → IN_PRODUCTION (admin@test.com)

---

## Producción

Cada job nace automáticamente al pasar su pedido a `IN_PRODUCTION`. Las tareas se crean por **item × etapa** y se asignan al operario responsable de esa etapa según `StageResponsibility`.

| Job | Pedido | Estado | Urgente | Avance | Qué muestra |
|---|---|---|---|---|---|
| **1** | #1 | Completado | no | 16/16 etapas | Todas las etapas completadas. La orden pasó a DELIVERED y el job cerró en COMPLETED. |
| **2** | #2 | En progreso | no | 7/16 etapas | Frenado después de costura: calidad de costura es la siguiente pendiente (Tere). |
| **3** | #3 | En progreso | 🔴 sí | 2/16 etapas | URGENTE. Solo tallas y planeación; el corte está pendiente con Sr. Tino. |
| **4** | #4 | Pausado | no | 1/12 etapas | PAUSADO por el admin. Ninguna etapa avanza mientras siga en pausa. |
| **5** | #9 | Completado | no | 8/8 etapas | Ruta corta (surtido, calidad final, empaque, envíos) terminada. Orden entregada. |
| **6** | #10 | En progreso | no | 8/24 etapas | Pedido de mostrador en sublimación. No puede entregarse hasta liquidar el saldo. |

### Quién tiene qué asignado

| Operario | Etapas a su cargo | Pendientes | Completadas |
|---|---|---|---|
| Concepción Ibarra | Calidad Final, Empaque, Selección de Tallas, Sublimación | 18 | 16 |
| Daniela Ochoa | Calidad de Aplicaciones y Cristalería, Control y Surtido de Materiales | 8 | 9 |
| Manuel Zepeda | Envíos | 7 | 4 |
| Teresa Nava | Calidad de Costura | 5 | 1 |
| Joaquín Lara | Cristalería y Plantillas | 5 | 1 |
| Silvia Contreras | Costura | 4 | 2 |
| Faustino Ramírez | Corte, Planeación de Materiales | 3 | 9 |

### Tareas pendientes por job

- **Job 1** (pedido #1): sin pendientes, cerrado.
- **Job 2** (pedido #2, En progreso): 9 tareas abiertas. La siguiente es **Calidad de Costura** sobre *Uniforme Personalizado por Equipo*, a cargo de **Teresa Nava**.
- **Job 3** (pedido #3, En progreso): 14 tareas abiertas. La siguiente es **Control y Surtido de Materiales** sobre *Uniforme Personalizado por Equipo*, a cargo de **Daniela Ochoa**.
- **Job 4** (pedido #4, Pausado): 11 tareas abiertas. La siguiente es **Planeación de Materiales** sobre *Shorts de Entrenamiento*, a cargo de **Faustino Ramírez**.
- **Job 5** (pedido #9): sin pendientes, cerrado.
- **Job 6** (pedido #10, En progreso): 16 tareas abiertas. La siguiente es **Sublimación** sobre *Uniforme Taller (captura offline)*, a cargo de **Concepción Ibarra**.

---

## Reportes de error

### Reporte #1 — Reposición requerida

- **Pedido:** #2 · **job:** 2 · **etapa:** Costura
- **Lo reportó:** Teresa Nava · **responsable:** Silvia Contreras
- **Tipo:** DEFECTIVE_SEWING
- **Descripción:** Dos tops salieron con la costura del hombro floja; se detectó en la revisión de calidad.
- **Reposición requerida:** sí · **revisó:** Bryan Sánchez

### Reporte #2 — Excepción otorgada

- **Pedido:** #3 · **job:** 3 · **etapa:** Sublimación
- **Lo reportó:** Daniela Ochoa · **responsable:** Concepción Ibarra
- **Tipo:** WRONG_SUBLIMATION
- **Descripción:** La sublimación del pedido urgente salió con el tono de azul dos puntos abajo del pantone del equipo.
- **Reposición requerida:** no · **revisó:** Bryan Sánchez

### Reporte #3 — Pendiente de revisión

- **Pedido:** #10 · **job:** 6 · **etapa:** Corte
- **Lo reportó:** Faustino Ramírez · **responsable:** Faustino Ramírez
- **Tipo:** WRONG_CUT, WRONG_MATERIAL
- **Descripción:** Se cortaron 10 piezas con el molde de la talla anterior antes de detectar el cambio de medidas.
- **Reposición requerida:** sí

---

## Eventos y concursos

### Copa Galaxia 2026 — SEED

- **Estado:** Completado · **sede:** Arena Nebulosa, Guadalajara · **fechas:** 2026-04-26 → 2026-04-27
- **Equipos inscritos:** 3 · **participantes:** 0
- **Criterios:** Técnica (máx 40.00), Presentación (máx 30.00), Dificultad (máx 30.00)
- **Calificaciones capturadas:** 9
- **Resultados publicados:**
  - 1º **Comets** — 92.50 pts
  - 2º **Supernovas** — 88.00 pts
  - 3º **Meteors** — 84.75 pts

### Copa Nebulosa — SIMULACIÓN

- **Estado:** Completado · **sede:** Domo Nebulosa, Querétaro · **fechas:** 2026-08-03 → 2026-08-04
- **Equipos inscritos:** 3 · **participantes:** 33
- **Panel de jueces:** Mónica Beltrán, Ricardo Fuentes, Elena Castaño
- **Criterios:** Técnica (máx 30.00), Sincronización (máx 25.00), Dificultad (máx 25.00), Presentación (máx 20.00)
- **Calificaciones capturadas:** 36
- **Resultados publicados:**
  - 1º **Comets** — 91.17 pts
  - 2º **Supernovas** — 87.17 pts
  - 3º **Meteors** — 82.17 pts

### Grand Prix Espacial 2026 — SEED

- **Estado:** Inscripciones abiertas · **sede:** Auditorio Galaxia, Ciudad de México · **fechas:** 2026-10-23 → 2026-10-24
- **Equipos inscritos:** 3 · **participantes:** 36
- **Panel de jueces:** Mónica Beltrán, Ricardo Fuentes, Elena Castaño
- **Criterios:** Técnica (máx 30.00), Sincronización (máx 25.00), Dificultad (máx 25.00), Presentación (máx 20.00)
- **Calificaciones capturadas:** 0

---

## Hospedaje

**Hotel Órbita Centro** — check-in 2026-10-22, check-out 2026-10-25.

| Habitación | Tipo | Equipo | Ocupantes |
|---|---|---|---|
| 204 | Familiar (cap. 3) | Comets (familiar) | Alicia Cruz, Sofía Cruz, Valeria Torres |
| 201 | Cuádruple estándar (cap. 4) | Meteors | Natalia Salinas, Paulina Aguilar, Stephanie Romero, Mónica Sánchez |
| 202 | Cuádruple estándar (cap. 4) | Supernovas | Regina Mendoza, Ximena Castro, Renata Guzmán, Alejandra Herrera |
| 203 | Cuádruple estándar (cap. 4) | Comets | Camila Ramírez, Isabella Flores, Daniela Reyes, Fernanda Morales |

Los tres head coaches comparten la habitación **301**.

---

## Pendientes

Dos resueltos el 2026-08-24 con las reglas que definió Bryan; dos abiertos.

### ✅ Resuelto — capacidad real por cama

Antes `BedAssignment` rechazaba cualquier segundo huésped en una cama, sin importar el tipo: una KING valía lo mismo que una individual, y un padre no podía compartir cama con su hijo.

Ahora `Bed` tiene **capacidad con default por tipo y override por cama**:

| Tipo | Capacidad por defecto |
|---|---|
| Individual | 1 |
| Doble / Queen / King / Litera | 2 |

El campo `Bed.capacity` queda vacío para usar el default, o se llena para declarar lo que sea esa cama en particular (una matrimonial angosta para 1, una litera de 3). `Bed.effective_capacity` resuelve cuál manda. No se puede bajar la capacidad por debajo de los huéspedes ya asignados.

Migración: `hospitality/migrations/0003_bed_capacity.py`.

### ✅ Resuelto — un menor ya no se aloja con un adulto ajeno

Regla nueva en `hospitality/policies.py` (`MinorLodgingPolicy`), aplicada tanto en el `clean()` de los modelos como en los servicios de asignación. **La cama es más estricta que el cuarto:**

| Ámbito | Con quién puede estar un menor |
|---|---|
| Habitación | Su tutor asignado, **o** el cuerpo técnico de su equipo (head coach, coach o staff con membresía activa) |
| Cama | **Solo** su tutor asignado |

Entre menores no hay restricción, y entre adultos tampoco. Un coach puede dormir en el mismo cuarto que una atleta menor —eso es acompañamiento normal de equipo— pero no en su misma cama.

La simulación lo muestra en la habitación **204**: la tutora Alicia Cruz comparte la cama matrimonial con su hija Sofía Cruz, y Valeria Torres —la otra atleta a su cargo— duerme en la individual.

Cubierto por 22 tests en `hospitality/tests.py`.

### ✅ Resuelto — fail-open por edad y acreditación por rol inválido

Tres huecos del mismo tipo: la regla existía pero se podía esquivar sin romper nada.

- **`is_minor()` devolvía False sin `birth_date`**, así que un menor sin fecha registrada quedaba fuera de la protección. Ahora un **atleta** sin fecha cuenta como menor; un no-atleta sin fecha sigue contando como adulto, que por ese lado ya era restrictivo.
- **Se acreditaba por un rol que no existe.** El filtro incluía `role_in_team="HEADCOACH"`, valor que `UserTeamMembership.ROLE_CHOICES` no define. Los roles salen ahora de ROLE_CHOICES y el head coach se reconoce por `Team.coach`. El mismo defecto vivía en `orders/permissions.py` decidiendo quién aprueba diseños: también corregido, y el head coach ya no necesita membresía para aprobar.
- **La autorización quedaba congelada en la fila.** Si después le quitaban el tutor al menor, la habitación seguía asignada. `audit_stay()` y `audit_event()` revalidan contra el estado de hoy, y el check-in corta si el alojamiento dejó de cumplir.

Además `assign_guardian()` exige **fecha de nacimiento** y **rol GUARDIAN**; ese filtro vivía solo en el desplegable de la vista, así que el admin de Django o cualquier script lo esquivaban.

### ✅ Resuelto — el pedido ya dice qué falta, y a quién le toca

`next_step_requirements()` reporta de una sola vez todo lo que falta para el siguiente estado, en cualquier punto del ciclo, con el responsable de cada cosa. Antes las validaciones solo hablaban cuando alguien ya había intentado avanzar, y de a un error por vez.

**El cliente no ve el detalle interno.** Admin y staff ven todo; el head coach ve solo lo suyo y del resto sabe que el pedido está en curso. El corte lo hace `can_administer_orders()`.

### ✅ Resuelto — respaldo de la tutela legal

`TUTOR` registra documento, quién verificó y cuándo; solo un ADMIN puede hacerlo, y cambiar la relación invalida la verificación previa. `PADRE` y `ACOMP` siguen declarativos.

**Sin tope de atletas por tutor**: por encima de 4 la pantalla avisa y deja seguir. El riesgo está en que el vínculo sea falso, no en el número, y un error duro ahí solo enseñaría a elegir «Acompañante» para esquivarlo.

### 🔴 Abierto — un menor tiene un solo tutor

`AthleteProfile.guardian` es un FK simple. En la práctica los padres se turnan según el viaje. **Es la limitación que más va a doler** si se sigue trabajando en hospedaje o custodia.

### 🔴 Abierto — STAFF no abre el detalle de un pedido

`/orders/<id>/` admite ADMIN, HEADCOACH, GUARDIAN, COACH y ATHLETE, pero no STAFF, y `visible_for_user` tampoco le da los pedidos offline. A nivel de servicio staff sí ve todos los pendientes con detalle. Es comportamiento previo; ampliar accesos es decisión de producto.

---

## Notas sobre la simulación

- **Las imágenes de diseño son PNG de 1×1.** `OrderDesignImage` exige un mínimo de 35 MB, pero ese validador solo corre en el formulario; el ORM no lo dispara. Si subes un diseño desde la interfaz, el mínimo sí aplica.
- **`seed_full_data` tenía fechas fijas de 2026** que ya caducaron y hacían fallar la validación `registration_close >= registration_open`. Ahora son relativas a la fecha de ejecución.
- **Nada de esto está commiteado.** El comando nuevo es `core/management/commands/simulate_platform.py`.
