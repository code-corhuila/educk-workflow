"""
gestor_colores_y_miembros.py - Gestor Inteligente de Asignaciones, Colores y Miembros
======================================================================================
EduTrack — Sistemas Distribuidos 2026-B
Líder Técnica: @XimenaChala

Funcionalidad:
1. Inspecciona el tablero de Trello en tiempo real y detecta:
   - Quién eligió cada tarjeta (miembros asignados en idMembers).
   - Qué color tiene cada tarjeta (labels / etiquetas de color).
2. Mapea la correlación en vivo entre Git (autores de commits/PRs) y Trello (tarjetas y colores).
3. Cuando un integrante sube algo a Git (ej. Celeste sube algo de frontend):
   - El agente detecta quién subió el código y busca su tarjeta en Trello con su color distintivo.
   - Personaliza las alertas y especificaciones con su nombre, usuario de GitHub, usuario de Trello
     y color identificador (ej. Celeste 🩵, Amarillo 🟨, Verde 🟩, Morado 🟪).
4. Cuando se genera una nueva tarjeta con especificaciones:
   - Le aplica automáticamente la etiqueta de color y el miembro asignado en Trello.
   - Coloca un encabezado claro para que la persona sepa inmediatamente que es para ella.
"""

import os
import sys
import json
import requests
from pathlib import Path

# Asegurar codificación UTF-8
if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding="utf-8")
        sys.stderr.reconfigure(encoding="utf-8")
    except Exception:
        pass

AUTO_DIR = Path(__file__).parent.resolve()
MUSIC_DIR = AUTO_DIR.parent.resolve()
TRELLO_CONFIG_FILE = AUTO_DIR / "trello_config.json"
MEMBER_REGISTRY_FILE = AUTO_DIR / "team_members_registry.json"

# Directorio Maestro de Integrantes
TEAM_MEMBERS_DIRECTORY = {
    "celestedussan": {
        "trello_id": "64d664a5a44603e18b83f6a7",
        "trello_username": "celestedussan",
        "full_name": "Celeste Dussán",
        "github_logins": ["CelesteDussan", "celestedussan", "mdussanospina", "Maria Celeste Dussan Ospina"],
        "color_code": "sky",
        "color_name": "Celeste",
        "color_emoji": "🩵",
        "default_role": "Especialista en Frontend & Portales Web"
    },
    "juancamilopenagosmolina": {
        "trello_id": "665765ef2f7caa2653da7a58",
        "trello_username": "juancamilopenagosmolina",
        "full_name": "Juan Camilo Penagos Molina",
        "github_logins": ["CamiloPenagos60", "juancamilopenagosmolina", "juancamilopenagos", "CamiloPenagos"],
        "color_code": "green",
        "color_name": "Verde",
        "color_emoji": "🟩",
        "default_role": "Especialista en Backend & Persistencia"
    },
    "stephanvargasquiroga": {
        "trello_id": "654c1e85c5fc8d84b827177a",
        "trello_username": "stephanvargasquiroga",
        "full_name": "Stephan Vargas Quiroga",
        "github_logins": ["stephanvargasquiroga", "stephanvargas", "lanvargas94", "stephanvq"],
        "color_code": "purple",
        "color_name": "Morado",
        "color_emoji": "🟪",
        "default_role": "Especialista en Microservicios & Integración"
    },
    "ximenachala": {
        "trello_id": "6a4f3bab9f690436bca48d1a",
        "trello_username": "ximenachala",
        "full_name": "Ximena Del Pilar Zambrano",
        "github_logins": ["XimenaChala", "ximenachala"],
        "color_code": "yellow",
        "color_name": "Amarillo",
        "color_emoji": "🟨",
        "default_role": "Líder Técnica, Frontend Shell & Infraestructura"
    }
}

# Diccionario de nombres de color amigables
COLOR_NAMES_ES = {
    "yellow": ("Amarillo", "🟨"),
    "sky": ("Celeste", "🩵"),
    "blue": ("Azul", "🟦"),
    "green": ("Verde", "🟩"),
    "purple": ("Morado", "🟪"),
    "orange": ("Naranja", "🟧"),
    "red": ("Rojo", "🟥"),
    "pink": ("Rosado", "🌸"),
    "black": ("Negro", "⬛"),
    "lime": ("Lima", "🍋")
}

def load_trello_config() -> dict:
    if TRELLO_CONFIG_FILE.exists():
        try:
            return json.loads(TRELLO_CONFIG_FILE.read_text(encoding="utf-8"))
        except Exception:
            pass
    return {}

class ColorMemberManager:
    def __init__(self):
        self.cfg = load_trello_config()
        self.key = self.cfg.get("api_key", "")
        self.token = self.cfg.get("token", "")
        self.board_id = self.cfg.get("board_id", "")
        self.base_url = "https://api.trello.com/1"
        self.labels_cache = {}
        self.members_cache = {}
        self.card_assignments = {}

    def is_ready(self) -> bool:
        return bool(self.key and self.token and self.board_id)

    def fetch_board_labels(self) -> dict:
        """Obtiene todas las etiquetas del tablero y las guarda por color/nombre."""
        if not self.is_ready():
            return {}
        url = f"{self.base_url}/boards/{self.board_id}/labels?key={self.key}&token={self.token}"
        res = requests.get(url)
        if res.status_code == 200:
            labels = res.json()
            # Mapear por color e ID
            for l in labels:
                self.labels_cache[l["id"]] = l
                # también indexar por color
                color = l.get("color")
                if color:
                    self.labels_cache[color] = l
            return self.labels_cache
        return {}

    def fetch_board_members(self) -> dict:
        """Obtiene los miembros registrados en el tablero de Trello."""
        if not self.is_ready():
            return {}
        url = f"{self.base_url}/boards/{self.board_id}/members?key={self.key}&token={self.token}"
        res = requests.get(url)
        if res.status_code == 200:
            for m in res.json():
                self.members_cache[m["id"]] = m
                self.members_cache[m["username"].lower()] = m
            return self.members_cache
        return {}

    def ensure_team_labels_on_board(self):
        """Asegura que existan etiquetas personalizadas para cada integrante en Trello."""
        if not self.is_ready():
            return
        
        self.fetch_board_labels()

        for uname, info in TEAM_MEMBERS_DIRECTORY.items():
            color = info["color_code"]
            name = info["full_name"]
            label_name = f"{name} ({info['color_name']})"

            # Buscar si ya existe una etiqueta con ese color o nombre
            found = None
            for lid, l in self.labels_cache.items():
                if isinstance(l, dict) and l.get("color") == color:
                    found = l
                    break

            if found:
                # Si existe pero no tiene nombre descriptivo, actualizar su nombre
                if not found.get("name") or found.get("name") != label_name:
                    update_url = f"{self.base_url}/labels/{found['id']}?name={label_name}&key={self.key}&token={self.token}"
                    requests.put(update_url)
                    found["name"] = label_name
            else:
                # Crear la etiqueta en el tablero
                create_url = f"{self.base_url}/boards/{self.board_id}/labels?name={label_name}&color={color}&key={self.key}&token={self.token}"
                res = requests.post(create_url)
                if res.status_code == 200:
                    created_label = res.json()
                    self.labels_cache[created_label["id"]] = created_label
                    self.labels_cache[color] = created_label

    def scan_board_assignments(self) -> dict:
        """
        Escanea exhaustivamente todas las tarjetas del tablero de Trello.
        Determina quién eligió cada tarjeta y qué color tiene asignado.
        Retorna un diccionario estructurado de asignaciones activas.
        """
        if not self.is_ready():
            return {}

        self.fetch_board_labels()
        self.fetch_board_members()

        url = f"{self.base_url}/boards/{self.board_id}/cards?fields=name,desc,idList,labels,idLabels,idMembers&key={self.key}&token={self.token}"
        res = requests.get(url)
        if res.status_code != 200:
            return {}

        cards = res.json()
        assignments = {}

        for card in cards:
            c_id = card["id"]
            c_name = card["name"]
            c_desc = card.get("desc", "")
            id_members = card.get("idMembers", [])
            labels = card.get("labels", [])
            id_labels = card.get("idLabels", [])

            # Detectar miembros
            assigned_members = []
            for mid in id_members:
                m_info = self.members_cache.get(mid)
                if m_info:
                    username = m_info["username"].lower()
                    dir_entry = TEAM_MEMBERS_DIRECTORY.get(username)
                    if dir_entry:
                        assigned_members.append(dir_entry)
                    else:
                        assigned_members.append({
                            "trello_id": mid,
                            "trello_username": m_info["username"],
                            "full_name": m_info.get("fullName", m_info["username"]),
                            "github_logins": [m_info["username"]],
                            "color_code": "blue",
                            "color_name": "Azul",
                            "color_emoji": "🟦",
                            "default_role": "Desarrollador"
                        })

            # Detectar colores
            card_colors = []
            for l in labels:
                color = l.get("color")
                if color:
                    name_es, emoji = COLOR_NAMES_ES.get(color, (color.capitalize(), "🏷️"))
                    card_colors.append({
                        "id": l.get("id"),
                        "color": color,
                        "name": l.get("name") or name_es,
                        "name_es": name_es,
                        "emoji": emoji
                    })

            # Si no tiene miembro explícito pero tiene un color que pertenece a alguien (ej. yellow -> Ximena, sky -> Celeste)
            if not assigned_members and card_colors:
                for c_col in card_colors:
                    for uname, info in TEAM_MEMBERS_DIRECTORY.items():
                        if info["color_code"] == c_col["color"]:
                            assigned_members.append(info)
                            break

            assignments[c_id] = {
                "id": c_id,
                "name": c_name,
                "desc": c_desc,
                "idList": card["idList"],
                "assigned_members": assigned_members,
                "card_colors": card_colors,
                "primary_member": assigned_members[0] if assigned_members else None,
                "primary_color": card_colors[0] if card_colors else (assigned_members[0] if assigned_members else None)
            }

        self.card_assignments = assignments
        return assignments

    def find_assignment_for_repo_or_task(self, repo_name: str, task_text: str = "") -> dict:
        """Encuentra la tarjeta en Trello asociada a un repositorio o tarea y quién la tiene."""
        if not self.card_assignments:
            self.scan_board_assignments()

        query = (repo_name + " " + task_text).lower()

        # Palabras clave por repositorio
        repo_keywords = {
            "identity-api": ["iam", "identidad", "login", "auth", "8081"],
            "identity-db": ["identity", "iam", "5431", "usuarios", "roles"],
            "identity-portal": ["portal de identidad", "login (:3001)", "3001"],
            "api-gateway": ["gateway", "8080", "perimetral"],
            "academic-api": ["académico", "calificaciones", "notas", "8082"],
            "academic-db": ["academic", "5432", "cursos", "evaluaciones"],
            "academic-portal": ["portal de calificaciones", "boletín", "3002"],
            "attendance-api": ["asistencia", "pase de lista", "8083"],
            "attendance-db": ["attendance", "5433", "sesiones"],
            "attendance-portal": ["portal de asistencia", "3003"],
            "educk-front": ["shell", "portal shell", "3000"],
            "educk-infra": ["infraestructura", "compose", "rabbitmq", "worker"],
            "educk-worker": ["worker", "amqp", "deduplicación", "alertas"],
            "edutrack": ["walking skeleton", "mensajería", "comunicación"],
            "educk-communication": ["comunicación", "padre-profesor", "8085"],
            "educk-docs": ["documentar", "gobernanza", "despliegue global", "specs"]
        }

        matched_card = None
        for cid, card_info in self.card_assignments.items():
            c_text = (card_info["name"] + " " + card_info["desc"]).lower()
            
            # 1. Coincidencia directa con nombre de repo
            if repo_name.lower() in c_text:
                matched_card = card_info
                break

            # 2. Coincidencia con palabras clave
            for repo_key, keywords in repo_keywords.items():
                if repo_key in repo_name.lower():
                    if any(k in c_text for k in keywords):
                        matched_card = card_info
                        break
            if matched_card:
                break

        return matched_card

    def get_member_by_git_author(self, author_login_or_name: str) -> dict:
        """Resuelve el integrante a partir del login o nombre de commit en GitHub."""
        clean_author = (author_login_or_name or "").lower().strip()

        for uname, info in TEAM_MEMBERS_DIRECTORY.items():
            if uname in clean_author:
                return info
            for gh in info["github_logins"]:
                if gh.lower() in clean_author or clean_author in gh.lower():
                    return info

        return None

    def tag_card_with_member_and_color(self, card_id: str, member_username: str):
        """Asigna en Trello el miembro (idMembers) y la etiqueta de color (idLabels) a una tarjeta."""
        if not self.is_ready():
            return False

        member_info = TEAM_MEMBERS_DIRECTORY.get(member_username.lower())
        if not member_info:
            return False

        self.fetch_board_labels()

        # 1. Asignar miembro a la tarjeta si no lo tiene
        mid = member_info["trello_id"]
        url_member = f"{self.base_url}/cards/{card_id}/idMembers?value={mid}&key={self.key}&token={self.token}"
        requests.post(url_member)

        # 2. Asignar etiqueta de color a la tarjeta
        target_color = member_info["color_code"]
        label_id = None
        for lid, l in self.labels_cache.items():
            if isinstance(l, dict) and l.get("color") == target_color:
                label_id = l.get("id")
                break

        if label_id:
            url_label = f"{self.base_url}/cards/{card_id}/idLabels?value={label_id}&key={self.key}&token={self.token}"
            requests.post(url_label)
            return True

        return False

    def reassign_card(self, card_id: str, member_username: str, clear_others: bool = True) -> bool:
        """
        Asigna exclusivamente una tarjeta a un integrante, aplicando su color oficial
        y eliminando las etiquetas o miembros anteriores para no causar confusión.
        """
        if not self.is_ready():
            return False

        member_info = TEAM_MEMBERS_DIRECTORY.get(member_username.lower())
        if not member_info:
            return False

        self.fetch_board_labels()

        if clear_others:
            card_res = requests.get(f"{self.base_url}/cards/{card_id}?fields=idMembers,idLabels&key={self.key}&token={self.token}")
            if card_res.status_code == 200:
                card_data = card_res.json()
                # Remover otros miembros
                for mid in card_data.get("idMembers", []):
                    if mid != member_info["trello_id"]:
                        requests.delete(f"{self.base_url}/cards/{card_id}/idMembers/{mid}?key={self.key}&token={self.token}")
                
                # Remover etiquetas de otros integrantes
                target_color = member_info["color_code"]
                for lid in card_data.get("idLabels", []):
                    l_info = self.labels_cache.get(lid)
                    if l_info and l_info.get("color") != target_color:
                        if l_info.get("color") in ["yellow", "sky", "green", "purple"]:
                            requests.delete(f"{self.base_url}/cards/{card_id}/idLabels/{lid}?key={self.key}&token={self.token}")

        return self.tag_card_with_member_and_color(card_id, member_username)

    def post_comment(self, card_id: str, text: str):
        """Publica un comentario en la tarjeta de Trello."""
        if not self.is_ready():
            return False
        url = f"{self.base_url}/cards/{card_id}/actions/comments?key={self.key}&token={self.token}"
        res = requests.post(url, data={"text": text})
        return res.status_code == 200

    def update_card_banner(self, card_id: str, member_username: str, repo_name: str, spec_desc: str = ""):
        """Actualiza la descripción de una tarjeta con el formato limpio: ¿Qué toca hacer? y Especificación."""
        clean_desc = f"""## 📌 ¿Qué toca hacer?
{spec_desc if spec_desc else 'Desarrollo del componente conforme a la arquitectura oficial de EduTrack.'}

---

## 🛠️ Especificación Técnica (¿Cómo hacerlo?)
### 1. Componentes y Tecnologías:
- **Repositorio:** `{repo_name}`
- **Arquitectura:** Modular y desacoplada conforme a la Documentación Maestra.

### 2. Criterios de Aceptación (Quality Gates):
- [ ] Pull Request con menos de 400 líneas modificadas.
- [ ] Commits con cuerpo explicativo (`Por qué: ...`).
- [ ] Al subir tus cambios a GitHub, mueve esta tarjeta a **'Realizado y revisar'**.
"""
        url = f"{self.base_url}/cards/{card_id}?key={self.key}&token={self.token}"
        res = requests.put(url, data={"desc": clean_desc})
        return res.status_code == 200

    def create_personalized_card(self, list_id: str, title: str, member_username: str, repo_name: str, spec_dict: dict = None) -> dict:
        """
        Crea una nueva tarjeta en Trello y le aplica automáticamente:
        - El miembro asignado (idMembers)
        - La etiqueta con su color identificador (idLabels)
        - Descripción limpia con ¿Qué toca hacer? y Especificación
        - Comentario inicial con checklist y comandos Git
        """
        if not self.is_ready():
            return {}

        member_info = TEAM_MEMBERS_DIRECTORY.get(member_username.lower())
        if not member_info:
            return {}

        spec = spec_dict or {}
        is_docs = (repo_name == "educk-docs")
        branch_line = "**Rama Oficial:** `main` *(En educk-docs se trabaja directo en main, sin ramas hijas)*" if is_docs else f"- **Rama Base:** `{spec.get('base_branch', 'develop')}`\n- **Tu Rama Hija Obligatoria:** `{spec.get('expected_branch', 'feat/...')}`"

        git_cmds = f"""cd "{repo_name}"
git checkout main && git pull origin main
# Edita tus archivos de documentacion
git add .
git commit -m "docs(...): descripcion" -m "Por qué: Justificacion tecnica para Corte 2."
git push origin main""" if is_docs else f"""cd "{repo_name}"
git checkout {spec.get('base_branch', 'develop')} && git pull origin {spec.get('base_branch', 'develop')}
git checkout -b {spec.get('expected_branch', 'feat/...')}
# Desarrolla tu componente
git add .
git commit -m "feat(...): descripcion" -m "Por qué: Justificacion tecnica para Corte 2."
git push -u origin {spec.get('expected_branch', 'feat/...')}"""

        desc = f"""## 📌 ¿Qué toca hacer?
{spec.get('desc', 'Desarrollo del componente conforme a la arquitectura oficial de EduTrack.')}

---

## 🛠️ Especificación Técnica (¿Cómo hacerlo?)

### 1. Componentes y Tecnologías:
- **Tecnología:** {spec.get('tech', 'Spring Boot 3 / React 18')}
- **Puerto Oficial:** {spec.get('port', 'Puerto asignado')}
- **Arquitectura:** Hexagonal / Microservicios

### 2. Política de Ramas Git:
- **Repositorio:** `{repo_name}`
{branch_line}

### 3. Comandos Git Paso a Paso para tu Computador:
```bash
{git_cmds}
```

### 4. Criterios de Aceptación (Quality Gates):
- [ ] Menos de 400 líneas modificadas en el PR.
- [ ] Cada commit debe incluir cuerpo con `Por qué: <justificación técnica>`.
- [ ] Respetar puertos oficiales y arquitectura hexagonal.
- [ ] Al subir tus cambios a Git, **mueve esta tarjeta a 'Realizado y revisar'**.
"""
        create_url = f"{self.base_url}/cards?name={requests.utils.quote(title)}&desc={requests.utils.quote(desc)}&idList={list_id}&key={self.key}&token={self.token}"
        res = requests.post(create_url)
        if res.status_code != 200:
            return {}

        card = res.json()
        card_id = card["id"]

        # Asignar miembro y color
        self.tag_card_with_member_and_color(card_id, member_username)

        # Publicar comentario con guía personalizada
        comment = self.build_personalized_guidance(title, repo_name, member_info, spec)
        self.post_comment(card_id, comment)

        return card

    def build_personalized_guidance(self, card_name: str, repo_name: str, member_info: dict, spec: dict, color_info: dict = None) -> str:
        """
        Construye la guía de especificaciones personalizada con el nombre,
        usuario y color distintivo de la persona para que sepa exactamente que es para ella.
        """
        m_name = member_info["full_name"] if member_info else "Compañero/a"
        m_gh = member_info["github_logins"][0] if member_info else "developer"
        m_trello = member_info["trello_username"] if member_info else "trello"
        
        c_name = color_info["name_es"] if color_info else (member_info["color_name"] if member_info else "Azul")
        c_emoji = color_info["emoji"] if color_info else (member_info["color_emoji"] if member_info else "🏷️")

        is_docs = (repo_name == "educk-docs")
        branch_line = "**Rama Oficial:** `main` (Directo sin ramas hijas)" if is_docs else f"**Rama Hija Obligatoria:** `{spec.get('expected_branch', 'feat/...')}` (creada desde `{spec.get('base_branch', 'develop')}`)"

        git_cmds = f"""```bash
cd "{repo_name}"
git checkout main && git pull origin main
# Realiza tus modificaciones en los archivos markdown
git add .
git commit -m "docs(...): descripcion del cambio" -m "Por qué: Justificacion tecnica para Corte 2."
git push origin main
```""" if is_docs else f"""```bash
cd "{repo_name}"
git checkout {spec.get('base_branch', 'develop')} && git pull origin {spec.get('base_branch', 'develop')}
git checkout -b {spec.get('expected_branch', 'feat/...')}
# Desarrolla tu código respetando puertos oficiales y arquitectura hexagonal
git add .
git commit -m "feat(...): descripcion" -m "Por qué: Justificacion tecnica."
git push -u origin {spec.get('expected_branch', 'feat/...')}
```"""

        comment = f"""👋 ¡Hola **{m_name}** (@{m_gh} en GitHub / @{m_trello} en Trello)!

🎨 **TARJETA ASIGNADA PERSONALMENTE:**
- **Actividad:** `{card_name}`
- **Color Distintivo en el Tablero:** {c_emoji} **{c_name}**
- **Repositorio Oficial:** `{repo_name}`
- {branch_line}

---

### 📋 Misión y Especificaciones Técnicas:
{spec.get('desc', 'Desarrollo del componente conforme a la arquitectura oficial de EduTrack.')}

### 💻 Comandos Git para tu Computador:
{git_cmds}

### ⚖️ Checklist de Aprobación Inmediata:
- [ ] Tarjeta identificada con tu color {c_emoji} **{c_name}**.
- [ ] {"Commits y PR directos en rama main (sin ramas hijas)." if is_docs else "No hacer commits directos a develop, main o qa (usar tu rama hija)."}
- [ ] Todo commit debe incluir el cuerpo con `Por qué: <justificación técnica>`.
- [ ] Tamaño de Pull Request menor a 400 líneas.
- [ ] Al subir tus cambios a Git, **mueve esta tarjeta a 'Realizado y revisar'**.

> *¡Muchos éxitos {m_name}! El Asistente Automático auditará tu entrega en cuanto la coloques en 'Realizado y revisar'.*
"""
        return comment

    def build_personalized_feedback(self, repo_name: str, pr_num: int, author: str, passed: bool, feedback_text: str, next_step: str = "") -> str:
        """
        Construye la retroalimentación personalizada dirigida a la persona
        que subió el código al Git, reconociendo su tarjeta y su color en Trello.
        """
        member = self.get_member_by_git_author(author)
        m_name = member["full_name"] if member else author
        c_emoji = member["color_emoji"] if member else "🏷️"
        c_name = member["color_name"] if member else "Identificador"

        card = self.find_assignment_for_repo_or_task(repo_name)
        card_name = card["name"] if card else f"Tarea de {repo_name}"

        if passed:
            msg = f"""🎉 **¡EXCELENTE TRABAJO {m_name.upper()}!** ({c_emoji} Tarjeta Color: **{c_name}**)

Tu entrega en `{repo_name}` (Pull Request #{pr_num}) ha superado la auditoría rigurosa frente a la **DOCUMENTACION_MAESTRA_EDUTRACK.md**:
- ✅ Cumple con el 100% de los Quality Gates (< 400 líneas, justificación técnica y convención de ramas).
- ✅ Tarjeta Trello vinculada: **'{card_name}'** (movida automáticamente a '✅ Aprobado y Mergeado').
- ✅ Pull Request aprobado y fusionado formalmente a nombre de @XimenaChala (Tech Lead).

---

{next_step}
"""
        else:
            msg = f"""👋 **Hola {m_name}** ({c_emoji} Tarjeta Color: **{c_name}** | Tarea: '{card_name}'):

Revisé minuciosamente tu Pull Request #{pr_num} en `{repo_name}` y detecté las siguientes observaciones que debes ajustar para que tu código sea compatible con el resto del equipo:

{feedback_text}

> 💡 *Realiza los ajustes en tu rama local y haz un nuevo `git push`. En cuanto lo hagas, volveré a revisar y aprobaré tu tarjeta en Trello de inmediato.*
"""
        return msg

if __name__ == "__main__":
    mgr = ColorMemberManager()
    print("🚀 Sincronizando etiquetas y colores oficiales del equipo en Trello...")
    mgr.ensure_team_labels_on_board()
    print("\n🔍 Analizando asignaciones de tarjetas y colores en tiempo real...")
    assignments = mgr.scan_board_assignments()
    print(f"Total tarjetas analizadas: {len(assignments)}")
    for cid, info in assignments.items():
        m = info["primary_member"]
        c = info["primary_color"]
        m_str = m["full_name"] if m else "Sin Miembro"
        c_str = f"{c['name_es']} {c['emoji']}" if c and "name_es" in c else (m["color_name"] if m else "Sin Color")
        print(f"  • '{info['name']}': [{c_str}] -> {m_str}")
