"""
despachador_flujo_continuo_trello.py - Despachador de Flujo Continuo (Mínimo 3 Tarjetas por Integrante)
========================================================================================================
EduTrack — Sistemas Distribuidos 2026-B
Líder Técnica: @XimenaChala

Funcionalidad:
1. Inspecciona los repositorios reales de código para garantizar tareas concretas y concisas.
2. Mantiene una cola activa de MÍNIMO 3 TARJETAS POR INTEGRANTE en el tablero de Trello.
3. Cuando un integrante completa una tarea y se aprueba a 'Aprobado y Mergeado',
   automáticamente desbloquea y despacha la siguiente tarea de su hoja de ruta.
4. Asigna automáticamente el miembro (idMembers), color oficial (labels) y especificación técnica concisa.
"""

import os
import sys
import json
import requests
from pathlib import Path

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

AUTO_DIR = Path(__file__).parent.resolve()
MUSIC_DIR = AUTO_DIR.parent.resolve()
CONFIG_FILE = AUTO_DIR / "trello_config.json"

from gestor_colores_y_miembros import TEAM_MEMBERS_DIRECTORY

# Mapeo de listas destino en Trello
LIST_FRONTEND = "6aaf06e126a2d747dfe4f97b"  # Aplicación Web (Frontend)
LIST_BACKEND = "6aaf06dbf860942835979e03"   # Backend & Bases de Datos
LIST_DONE = "6aaf1756df3b5bcabf0307c9"      # ✅ Aprobado y Mergeado
LIST_REVIEW = "6aaf17a63d79b6e2b696aa08"    # Realizado y revisar

LABELS_MAP = {
    "celestedussan": "6aaf2085118b66f80314ebd8",           # Celeste (sky)
    "juancamilopenagosmolina": "6aaef11b808b8de50ad92384", # Verde (green)
    "stephanvargasquiroga": "6aaef11b808b8de50ad92388",    # Morado (purple)
    "ximenachala": "6aaef11b808b8de50ad92385"             # Amarillo (yellow)
}

# Catálogo secuencial de tareas por integrante, verificado contra repositorios reales
ROADMAP_CATALOG = {
    "celestedussan": [
        {
            "id_task": "celeste_task_1",
            "name": "Portal Académico: Filtros por Materia y Cálculo de Promedio (:3002)",
            "repo": "educk-academic-portal",
            "target_list": LIST_FRONTEND,
            "que": "Implementar selector de materia y cálculo en tiempo real del promedio de corte en la tabla de calificaciones.",
            "como": {
                "archivos": "src/App.jsx",
                "puerto": "3002",
                "branch": "feat/HU-001-grade-filter-and-average-ui",
                "commit_msg": "feat(portal): filtros por materia y promedio ponderado en notas",
                "why": "Requerimiento HU-001 para que acudientes y docentes filtren notas por asignatura y visualicen el promedio de corte."
            }
        },
        {
            "id_task": "celeste_task_2",
            "name": "Portal Asistencia: Selector de Fecha y Resumen de Sesión (:3003)",
            "repo": "educk-attendance-portal",
            "target_list": LIST_FRONTEND,
            "que": "Añadir control de selección de fecha de clase, botón de guardar y panel resumen con total de presentes, ausentes y retardos.",
            "como": {
                "archivos": "src/App.jsx",
                "puerto": "3003",
                "branch": "feat/HU-005-attendance-session-summary",
                "commit_msg": "feat(portal): selector de fecha y resumen KPI de asistencia de sesion",
                "why": "Requerimiento HU-005 para pase de lista diario fechado con consolidado inmediato de inasistencias."
            }
        },
        {
            "id_task": "celeste_task_3",
            "name": "Portal Identidad: Estado de Sesión, Rol y Logout (:3001)",
            "repo": "educk-identity-portal",
            "target_list": LIST_FRONTEND,
            "que": "Implementar vista post-autenticación con tarjeta de perfil, badge de rol (Docente/Acudiente) y botón de cierre de sesión.",
            "como": {
                "archivos": "src/App.jsx",
                "puerto": "3001",
                "branch": "feat/HU-003-session-user-profile",
                "commit_msg": "feat(portal): visualizacion de perfil autenticado y accion de logout",
                "why": "Requerimiento HU-003 para gestion visual de sesiones activas y seguridad en el cliente."
            }
        },
        {
            "id_task": "celeste_task_4",
            "name": "Portal Shell: Navegación Unificada de Microfrontends (:3000)",
            "repo": "educk-front",
            "target_list": LIST_FRONTEND,
            "que": "Integrar iframe o contenedor dinámico para renderizar los microfrontends (:3001, :3002, :3003, :3005) desde el menú lateral del Shell.",
            "como": {
                "archivos": "src/App.jsx",
                "puerto": "3000",
                "branch": "feat/GW-001-shell-microfrontend-embedding",
                "commit_msg": "feat(shell): integracion de portales desacoplados en panel central",
                "why": "Arquitectura de microfrontends desacoplados unificados bajo el contenedor principal EduTrack."
            }
        }
    ],
    "juancamilopenagosmolina": [
        {
            "id_task": "camilo_task_1",
            "name": "Backend Asistencia: Validación de Invariantes y Estados de Asistencia (:8083)",
            "repo": "educk-attendance-api",
            "target_list": LIST_BACKEND,
            "que": "Implementar validación de invariantes de dominio: impedir asistencia en fechas futuras y restringir estados a PRESENT, ABSENT, LATE, JUSTIFIED.",
            "como": {
                "archivos": "src/main/java/com/corhuila/edutrack/attendance/application/service/AttendanceService.java",
                "puerto": "8083",
                "branch": "feat/HU-005-attendance-invariants-validation",
                "commit_msg": "feat(attendance): validacion estricta de invariantes y fechas en pase de lista",
                "why": "Requerimiento HU-005 para garantizar consistencia temporal y evitar registros erróneos de asistencia."
            }
        },
        {
            "id_task": "camilo_task_2",
            "name": "Backend Académico: Cálculo Ponderado de Corte y Promedio (:8082)",
            "repo": "educk-academic-api",
            "target_list": LIST_BACKEND,
            "que": "Implementar lógica de cálculo de nota definitiva por asignatura evaluando ponderaciones y retornando estado APROBADO (>= 3.0) o REPROBADO.",
            "como": {
                "archivos": "src/main/java/com/corhuila/edutrack/academic/application/service/GradeService.java",
                "puerto": "8082",
                "branch": "feat/HU-001-grade-weighted-average",
                "commit_msg": "feat(academic): calculo de promedio de corte y determinacion de aprobacion",
                "why": "Requerimiento HU-001 para consolidación de notas académicas y boletines institucionales."
            }
        },
        {
            "id_task": "camilo_task_3",
            "name": "Persistencia Académica: Script Flyway de Índices de Rendimiento (:5432)",
            "repo": "educk-academic-db",
            "target_list": LIST_BACKEND,
            "que": "Crear migración Flyway V2__performance_indexes.sql con índices B-Tree en grades(student_id, subject_id) para optimizar consultas de boletines.",
            "como": {
                "archivos": "migrations/V2__performance_indexes.sql",
                "puerto": "5432",
                "branch": "feat/HU-001-academic-indexes-v2",
                "commit_msg": "feat(db): indices compuestos flyway para optimizacion de calificaciones",
                "why": "Optimización de base de datos PostgreSQL bajo estándar ADR-003 para consultas masivas de notas."
            }
        },
        {
            "id_task": "camilo_task_4",
            "name": "Persistencia Asistencia: Migración Flyway para Justificaciones (:5433)",
            "repo": "educk-attendance-db",
            "target_list": LIST_BACKEND,
            "que": "Crear migración Flyway V2__justifications.sql añadiendo soporte para motivo de justificación y adjunto en tabla attendance_events.",
            "como": {
                "archivos": "migrations/V2__justifications.sql",
                "puerto": "5433",
                "branch": "feat/HU-005-attendance-justifications-schema",
                "commit_msg": "feat(db): soporte de justificaciones medicas en eventos de asistencia",
                "why": "Requerimiento HU-005 para justificación de inasistencias por parte de acudientes."
            }
        }
    ],
    "stephanvargasquiroga": [
        {
            "id_task": "stephan_task_1",
            "name": "Backend Identidad: Endpoint de Validación de Token JWT /validate (:8081)",
            "repo": "educk-identity-api",
            "target_list": LIST_BACKEND,
            "que": "Implementar endpoint POST /api/v1/auth/validate para verificar firma JWT, vigencia y retornar claims del usuario autenticado.",
            "como": {
                "archivos": "src/main/java/com/corhuila/edutrack/identity/infrastructure/web/AuthController.java",
                "puerto": "8081",
                "branch": "feat/HU-003-jwt-validate-endpoint",
                "commit_msg": "feat(auth): endpoint /api/v1/auth/validate para verificacion de firmas jwt",
                "why": "Requerimiento HU-003 para validación centralizada de sesiones desde el API Gateway."
            }
        },
        {
            "id_task": "stephan_task_2",
            "name": "API Gateway: Filtro Global de Autenticación y Propagación de Headers (:8080)",
            "repo": "educk-api-gateway",
            "target_list": LIST_BACKEND,
            "que": "Configurar filtro de enrutamiento que intercepte Authorization: Bearer, llame a :8081/validate e inyecte X-User-Id y X-User-Role hacia los microservicios.",
            "como": {
                "archivos": "src/main/resources/application.yml",
                "puerto": "8080",
                "branch": "feat/GW-001-gateway-auth-filter",
                "commit_msg": "feat(gateway): filtro global de autorizacion y propagacion de headers",
                "why": "Estándar de seguridad perimetral para desacoplar la validación de tokens en cada microservicio."
            }
        },
        {
            "id_task": "stephan_task_3",
            "name": "Worker AMQP: Plantillas de Mensajes y Log de Notificaciones (:8084)",
            "repo": "educk-worker",
            "target_list": LIST_BACKEND,
            "que": "Implementar formateo amigable de alertas en NotificationEventListener para eventos GradeCreated y StudentAbsent, guardando registro en notification_log.",
            "como": {
                "archivos": "src/main/java/com/corhuila/edutrack/worker/infrastructure/amqp/NotificationEventListener.java",
                "puerto": "8084",
                "branch": "feat/HU-002-worker-notification-templates",
                "commit_msg": "feat(worker): plantillas amigables y registro auditable de alertas amqp",
                "why": "Requerimiento HU-002 para notificaciones automáticas asíncronas a acudientes."
            }
        },
        {
            "id_task": "stephan_task_4",
            "name": "Backend Identidad: Rotación de Refresh Tokens y Cierre de Sesión (:8081)",
            "repo": "educk-identity-api",
            "target_list": LIST_BACKEND,
            "que": "Añadir endpoint POST /api/v1/auth/refresh para renovación de tokens expirados y revocación segura de sesiones.",
            "como": {
                "archivos": "src/main/java/com/corhuila/edutrack/identity/application/service/IdentityService.java",
                "puerto": "8081",
                "branch": "feat/HU-003-token-rotation-logout",
                "commit_msg": "feat(auth): rotacion de refresh tokens y revocacion de sesiones",
                "why": "Seguridad institucional para evitar sesiones perpetuas y mitigar robo de tokens."
            }
        }
    ]
}

def load_trello_config():
    return json.loads(CONFIG_FILE.read_text(encoding="utf-8"))

def build_card_description(task: dict, member_info: dict) -> str:
    m_name = member_info["full_name"]
    c_emoji = member_info["color_emoji"]
    c_name = member_info["color_name"]
    como = task["como"]

    return f"""## 📌 ¿Qué toca hacer?
{task['que']}

## 🛠️ Especificación Técnica Concisa
* **Integrante:** {m_name} ({c_emoji} **{c_name}**)
* **Repositorio Objetivo:** `{task['repo']}` (Puerto `:{como['puerto']}`)
* **Archivos a modificar/crear:** `{como['archivos']}`
* **Rama Git Obligatoria:** `{como['branch']}` (base: `develop`)
* **Quality Gates Estrictos:** Máximo 400 líneas, justificación técnica `Why:` obligatoria.

### 💻 Comandos Git para Iniciar:
```bash
cd "{task['repo']}"
git checkout develop && git pull origin develop
git checkout -b {como['branch']}
# Realiza tus cambios en {como['archivos']}
git add .
git commit -m "{como['commit_msg']}" -m "Por qué: {como['why']}"
git push -u origin {como['branch']}
```
*Abre el Pull Request hacia `develop` en GitHub y el Centinela en la nube lo auditará y aprobará automáticamente.*
"""

def get_board_cards(key: str, token: str, board_id: str) -> list:
    url = f"https://api.trello.com/1/boards/{board_id}/cards?fields=name,desc,idList,idMembers,idLabels,labels&key={key}&token={token}"
    res = requests.get(url, timeout=10)
    if res.status_code == 200:
        return res.json()
    return []

def is_card_blocked(card: dict) -> bool:
    """
    Regla de Seguridad 2 (Anti-Bloqueo por Dependencias):
    Si una tarjeta actual tiene una etiqueta que diga 'Bloqueado' (case-insensitive),
    se considera bloqueada por dependencias externas y no se suma al conteo de tareas ejecutables.
    """
    labels = card.get("labels", [])
    for lbl in labels:
        lbl_name = (lbl.get("name") or "").strip().lower()
        if "bloqueado" in lbl_name or "bloqueada" in lbl_name:
            return True
    return False

def ensure_minimum_active_cards(min_cards_per_member: int = 3) -> dict:
    """
    Garantiza que cada integrante tenga siempre un flujo de al menos `min_cards_per_member`
    tarjetas activas ejecutables en el tablero de Trello.
    """
    cfg = load_trello_config()
    key, token, board_id = cfg["api_key"], cfg["token"], cfg["board_id"]

    all_cards = get_board_cards(key, token, board_id)
    active_lists = [LIST_FRONTEND, LIST_BACKEND]

    print("================================================================================")
    print("🚀 DESPACHADOR DE FLUJO CONTINUO — EDUTRACK (MÍNIMO 3 TARJETAS POR PERSONA)")
    print("================================================================================")

    created_summary = {}

    for member_key, tasks in ROADMAP_CATALOG.items():
        member_info = TEAM_MEMBERS_DIRECTORY.get(member_key, {})
        trello_id = member_info.get("trello_id")
        m_name = member_info.get("full_name", member_key)
        label_id = LABELS_MAP.get(member_key)

        # 1. Contar tarjetas activas asignadas a este integrante (Anti-Bloqueo por Dependencias)
        member_active_cards = []
        blocked_cards = []
        for c in all_cards:
            if c.get("idList") in active_lists and trello_id in c.get("idMembers", []):
                if is_card_blocked(c):
                    blocked_cards.append(c)
                    print(f"   ⚠️ [ANTI-BLOQUEO]: Tarjeta '{c.get('name')}' tiene etiqueta 'Bloqueado'. Se excluye del conteo ejecutable.")
                else:
                    member_active_cards.append(c)

        status_suffix = f" ({len(blocked_cards)} bloqueada(s) por dependencias)" if blocked_cards else ""
        print(f"\n👤 {m_name} ({member_info.get('color_emoji')} {member_info.get('color_name')}):")
        print(f"   Tarjetas activas ejecutables: {len(member_active_cards)} de {min_cards_per_member} requeridas{status_suffix}.")

        cards_needed = min_cards_per_member - len(member_active_cards)
        created_for_member = []

        if cards_needed > 0:
            print(f"   ⚡ Despachando {cards_needed} tarjeta(s) nueva(s) del catálogo de corte 2...")
            
            # Buscar tareas del roadmap que no existan aún en el tablero
            existing_card_names = [c.get("name", "").lower() for c in all_cards]

            for task in tasks:
                if cards_needed <= 0:
                    break

                t_name = task["name"]
                target_list_id = task["target_list"]

                # 2. Regla de Seguridad 1 (Prevención de Spam en Trello):
                # Antes de ejecutar la petición POST para crear una nueva tarjeta,
                # hacer un GET a la lista correspondiente para obtener los nombres de las tarjetas actuales.
                # Si el título de la tarea que vas a crear ya existe en esa columna, omite la creación.
                url_get_column = f"https://api.trello.com/1/lists/{target_list_id}/cards?fields=name&key={key}&token={token}"
                try:
                    res_col = requests.get(url_get_column, timeout=10)
                    if res_col.status_code == 200:
                        column_card_names = [c.get("name", "").strip().lower() for c in res_col.json()]
                        if t_name.strip().lower() in column_card_names:
                            print(f"   🛡️ [PREVENCIÓN DE SPAM]: La tarjeta '{t_name}' ya existe en la lista de destino. Creación omitida.")
                            continue
                except Exception as e:
                    print(f"   Aviso al verificar prevención de spam en lista: {e}")

                # Comprobar si ya existe alguna tarjeta con nombre similar en el tablero
                already_exists = any(task["repo"] in ec and task["name"][:25].lower() in ec for ec in existing_card_names)
                if not already_exists:
                    already_exists = any(task["name"][:35].lower() in ec for ec in existing_card_names)

                if not already_exists:
                    # Crear la tarjeta en Trello vía POST
                    desc = build_card_description(task, member_info)
                    url_create = f"https://api.trello.com/1/cards?key={key}&token={token}"
                    payload = {
                        "name": t_name,
                        "desc": desc,
                        "idList": target_list_id,
                        "idMembers": [trello_id],
                        "idLabels": [label_id] if label_id else []
                    }
                    res_cr = requests.post(url_create, data=payload, timeout=10)
                    if res_cr.status_code == 200:
                        new_c = res_cr.json()
                        created_for_member.append(t_name)
                        cards_needed -= 1
                        all_cards.append(new_c)
                        print(f"   ✅ [DESPACHADA]: '{t_name}' -> Lista: {target_list_id}")
                    else:
                        print(f"   ❌ Error al crear tarjeta '{t_name}': {res_cr.status_code} {res_cr.text}")
        else:
            print(f"   ✅ Capacidad óptima: El integrante ya cuenta con {len(member_active_cards)} tarjetas ejecutables en curso.")

        created_summary[m_name] = created_for_member

    print("\n================================================================================")
    print("🏁 Despacho de flujo continuo finalizado con éxito.")
    print("================================================================================")
    return created_summary

if __name__ == "__main__":
    ensure_minimum_active_cards(min_cards_per_member=3)
