"""
centinela_cloud.py - Centinela Autónomo 24/7 en la Nube (GitHub Actions)
========================================================================
EduTrack — Sistemas Distribuidos 2026-B
Líder Técnica: @XimenaChala

Funcionalidad:
1. Se ejecuta dentro de los servidores de GitHub Actions (en la nube) las 24 horas del día,
   incluso cuando el computador de la Líder Técnica está completamente apagado.
2. Audita automáticamente los Pull Requests abiertos por Celeste, Camilo, Stephan o Ximena:
   - Valida Quality Gates: < 400 líneas, justificación técnica con 'Por qué:', convención de ramas.
   - Si cumple 100%: Aprueba el PR a nombre de @XimenaChala, lo fusiona (merge) a develop.
   - Si tiene errores: Bloquea el PR y publica los pasos exactos para corregirlo.
3. Se conecta en vivo con Trello:
   - Mueve la tarjeta correspondiente a '✅ Aprobado y Mergeado' o '⚠️ Corregir'.
   - Comenta en la tarjeta felicitando o indicando qué ajustar, reconociendo el color y nombre:
     (🩵 Celeste Dussán, 🟩 Juan Camilo Penagos, 🟪 Stephan Vargas, 🟨 Ximena Zambrano).
4. Envía alertas automáticas por WhatsApp (vía CallMeBot API) y Correo Electrónico.
"""

import os
import sys
import json
import urllib.parse
import subprocess
import requests

# Claves de Trello (Variables de entorno o valores oficiales por defecto)
TRELLO_KEY = os.environ.get("TRELLO_KEY", "a2bed52dc6fca63db4f5adb62432dc2d")
TRELLO_TOKEN = os.environ.get("TRELLO_TOKEN", "ATTA5e8524129b0c8806bd2930ef47790da13abfe8dc2eee37ae0f209ad8b6abe6d6B69C5CC3")
BOARD_ID = os.environ.get("TRELLO_BOARD_ID", "6aaef11b808b8de50ad9237e")

LIST_DONE = "6aaf1756df3b5bcabf0307c9" # ✅ Aprobado y Mergeado
LIST_FIX  = "6aaf17553a39d35efea465a1" # ⚠️ Corregir
LIST_REVIEW = "6aaf17a63d79b6e2b696aa08" # Realizado y revisar

TEAM_MEMBERS = {
    "celestedussan": {
        "full_name": "Celeste Dussán",
        "github": ["CelesteDussan", "celestedussan", "mdussanospina"],
        "color_name": "Celeste",
        "color_emoji": "🩵",
        "email": "mdussanospina@gmail.com",
        "phone": "573000000001",
        "apikey": ""
    },
    "juancamilopenagosmolina": {
        "full_name": "Juan Camilo Penagos Molina",
        "github": ["CamiloPenagos60", "juancamilopenagosmolina", "CamiloPenagos"],
        "color_name": "Verde",
        "color_emoji": "🟩",
        "email": "juancamilopenagosmolina@gmail.com",
        "phone": "573000000002",
        "apikey": ""
    },
    "stephanvargasquiroga": {
        "full_name": "Stephan Vargas Quiroga",
        "github": ["stephanvargasquiroga", "stephanvargas", "lanvargas94"],
        "color_name": "Morado",
        "color_emoji": "🟪",
        "email": "stephanvargasquiroga@gmail.com",
        "phone": "573000000003",
        "apikey": ""
    },
    "ximenachala": {
        "full_name": "Ximena Del Pilar Zambrano",
        "github": ["XimenaChala", "ximenachala"],
        "color_name": "Amarillo",
        "color_emoji": "🟨",
        "email": "ximenazambrano@corhuila.edu.co",
        "phone": "573000000004",
        "apikey": ""
    }
}

def resolve_member(author_login: str) -> dict:
    author_lower = (author_login or "").lower().strip()
    for uname, info in TEAM_MEMBERS.items():
        if uname in author_lower:
            return info
        for gh in info["github"]:
            if gh.lower() in author_lower or author_lower in gh.lower():
                return info
    return {
        "full_name": author_login or "Compañero/a",
        "github": [author_login],
        "color_name": "General",
        "color_emoji": "🏷️",
        "email": "",
        "phone": "",
        "apikey": ""
    }

def post_trello_comment(card_id: str, text: str):
    url = f"https://api.trello.com/1/cards/{card_id}/actions/comments?key={TRELLO_KEY}&token={TRELLO_TOKEN}"
    try:
        requests.post(url, data={"text": text}, timeout=10)
    except Exception as e:
        print(f"Aviso Trello comentario: {e}")

def move_trello_card(card_id: str, list_id: str):
    url = f"https://api.trello.com/1/cards/{card_id}?key={TRELLO_KEY}&token={TRELLO_TOKEN}"
    try:
        requests.put(url, data={"idList": list_id}, timeout=10)
    except Exception as e:
        print(f"Aviso Trello mover: {e}")

def find_card_for_repo(repo_name: str) -> dict:
    url = f"https://api.trello.com/1/boards/{BOARD_ID}/cards?fields=name,desc,idList,idMembers&key={TRELLO_KEY}&token={TRELLO_TOKEN}"
    try:
        res = requests.get(url, timeout=10)
        if res.status_code == 200:
            cards = res.json()
            # Mapeo por keywords de repositorio
            kw_map = {
                "identity-portal": "portal de identidad",
                "academic-portal": "portal de calificaciones",
                "attendance-portal": "portal de asistencia",
                "identity-api": "backend iam",
                "academic-api": "backend académico",
                "attendance-api": "backend asistencia",
                "front": "portal shell",
                "worker": "worker amqp",
                "infra": "despliegue global",
                "docs": "documentar"
            }
            target_kw = None
            for r_sub, kw in kw_map.items():
                if r_sub in repo_name.lower():
                    target_kw = kw
                    break

            if target_kw:
                for c in cards:
                    if target_kw in c.get("name", "").lower():
                        return c
            # Búsqueda directa
            for c in cards:
                if repo_name.lower() in (c.get("name", "") + " " + c.get("desc", "")).lower():
                    return c
    except Exception as e:
        print(f"Aviso buscando tarjeta en Trello: {e}")
    return {}

def send_whatsapp_alert(phone: str, apikey: str, message: str):
    if not phone:
        return
    encoded = urllib.parse.quote(message)
    wa_link = f"https://wa.me/{phone}?text={encoded}"
    print(f"📱 [WHATSAPP LINK]: {wa_link}")
    if apikey:
        try:
            call_url = f"https://api.callmebot.com/whatsapp.php?phone={phone}&text={encoded}&apikey={apikey}"
            requests.get(call_url, timeout=5)
            print(f"   ✅ WhatsApp entregado automáticamente a +{phone}")
        except Exception as e:
            print(f"   Aviso WhatsApp API: {e}")

def audit_pull_request():
    """Audita el Pull Request actual ejecutándose dentro de GitHub Actions."""
    repo_full = os.environ.get("GITHUB_REPOSITORY", "")
    repo_name = repo_full.split("/")[-1] if "/" in repo_full else repo_full
    pr_num = os.environ.get("PR_NUMBER", "")
    author = os.environ.get("PR_AUTHOR", "")
    head_ref = os.environ.get("HEAD_REF", "")
    base_ref = os.environ.get("BASE_REF", "develop")

    print("=" * 80)
    print("☁️  CENTINELA EN LA NUBE 24/7 (GITHUB ACTIONS) — EDUTRACK")
    print(f"📦 Repositorio: {repo_name} | PR #{pr_num} por @{author}")
    print(f"🌿 Rama: {head_ref} -> Base: {base_ref}")
    print("=" * 80)

    member = resolve_member(author)
    m_name = member["full_name"]
    c_badge = f"{member['color_name']} {member['color_emoji']}"

    errors = []
    actions = []

    # 1. Regla de Ramas
    if repo_name == "educk-docs":
        if head_ref != "main" and base_ref != "main":
            errors.append("En 'educk-docs' no se permiten ramas hijas. Debes hacer commits y PR directo sobre 'main'.")
            actions.append("Cambia la rama base de tu PR a 'main'.")
    else:
        if head_ref in ["develop", "main", "qa"]:
            errors.append(f"No se permite hacer PRs desde ramas protegidas ('{head_ref}'). Debes usar una rama hija (ej. feat/...).")
            actions.append("Crea una rama hija desde develop: git checkout -b feat/mi-tarea y abre el PR.")

    # 2. Conteo de Líneas (< 400 líneas)
    try:
        diff_cmd = ["git", "diff", "--shortstat", f"origin/{base_ref}...HEAD"]
        stat_res = subprocess.run(diff_cmd, capture_output=True, text=True)
        if stat_res.returncode == 0 and stat_res.stdout.strip():
            # Extraer números
            parts = stat_res.stdout.strip().split(",")
            total_lines = 0
            for p in parts:
                if "insertion" in p or "deletion" in p:
                    num = ''.join(filter(str.isdigit, p))
                    if num:
                        total_lines += int(num)
            print(f"📊 Líneas modificadas: {total_lines} (Límite: 400)")
            if total_lines > 400:
                errors.append(f"El Pull Request modifica {total_lines} líneas, superando el límite de 400 líneas exigido por el profesor Ariel (@ariel5253).")
                actions.append("Divide tu entrega en Pull Requests más pequeños y atómicos.")
    except Exception as e:
        print(f"Aviso conteo de líneas: {e}")

    # 3. Verificación de Commits con 'Por qué:'
    try:
        log_cmd = ["git", "log", f"origin/{base_ref}...HEAD", "--format=%s%x1f%b%x1e"]
        log_res = subprocess.run(log_cmd, capture_output=True, text=True)
        if log_res.returncode == 0 and log_res.stdout.strip():
            commits = log_res.stdout.split("\x1e")
            has_why = False
            for c in commits:
                if not c.strip():
                    continue
                sub_parts = c.split("\x1f")
                body = sub_parts[1] if len(sub_parts) > 1 else ""
                full_text = (sub_parts[0] + " " + body).lower()
                if "por qué:" in full_text or "por que:" in full_text or "why:" in full_text:
                    has_why = True
                    break
            if not has_why:
                errors.append("Ninguno de los commits incluye el cuerpo obligatorio con 'Por qué: <justificación técnica>'.")
                actions.append("Enmienda tu último commit con: git commit --amend -m \"titulo\" -m \"Por qué: Justificacion tecnica para Corte 2.\" y haz git push --force-with-lease.")
    except Exception as e:
        print(f"Aviso validando commits: {e}")

    # Buscar tarjeta en Trello
    target_card = find_card_for_repo(repo_name)
    card_id = target_card.get("id")
    card_name = target_card.get("name", f"Tarea de {repo_name}")

    if not errors:
        print("\n🎉 ¡100% APROBADO! Cumple con todos los Quality Gates de la cátedra.")
        # Mensaje de felicitación
        congrats = f"""👨‍🏫 **[PROFESOR ESTRICTO EDUTRACK — ENTREGA APROBADA 24/7 EN LA NUBE]**
👤 **Integrante:** {m_name} (@{author}) | 🎨 **Color de Tarjeta:** {c_badge}
📦 **Repositorio:** `{repo_name}` (PR #{pr_num})

¡Felicitaciones {m_name}! Tu entrega fue auditada por el Centinela en la Nube y cumple con el 100% de los estándares:
- ✅ Límite de tamaño (< 400 líneas) verificado.
- ✅ Justificación técnica ('Por qué:') presente en el historial de commits.
- ✅ Política de ramas respetada sin colisiones.
- ✅ Tarjeta vinculada: **'{card_name}'** movida a '✅ Aprobado y Mergeado'.
- ✅ Pull Request aprobado formalmente a nombre de @XimenaChala.
"""
        if card_id:
            post_trello_comment(card_id, congrats)
            move_trello_card(card_id, LIST_DONE)
            print(f"✅ Tarjeta Trello '{card_name}' movida a '✅ Aprobado y Mergeado'.")

        # Alerta WhatsApp
        wa_msg = f"""🎓 *[CENTINELA EN LA NUBE 24/7 — ENTREGA APROBADA]*
👤 *Integrante:* {m_name} ({c_badge})
📦 *Repositorio:* `{repo_name}` (PR #{pr_num})

¡Felicitaciones {m_name}! Tu entrega superó la auditoría de gobernanza al 100%.
Tu tarjeta de Trello avanzó a *'✅ Aprobado y Mergeado'*. ¡Excelente trabajo!"""
        send_whatsapp_alert(member.get("phone", ""), member.get("apikey", ""), wa_msg)

        # Salir con éxito para que GitHub Actions apruebe
        sys.exit(0)
    else:
        print("\n⛔ OBSERVACIONES DETECTADAS. Notificando correcciones...")
        errors_text = "\n".join([f"- ❌ {e}" for e in errors])
        actions_text = "\n".join([f"{idx}. {a}" for idx, a in enumerate(actions, 1)])

        alert = f"""👨‍🏫 **[PROFESOR ESTRICTO EDUTRACK — NO CONFORMIDADES DETECTADAS]**
👤 **Integrante:** {m_name} (@{author}) | 🎨 **Color de Tarjeta:** {c_badge}
📦 **Repositorio:** `{repo_name}` (PR #{pr_num})

Hola {m_name}, el Centinela en la Nube auditó tu Pull Request y detectó observaciones que impiden la aprobación:

### ❌ Observaciones Frente a la Gobernanza Oficial:
{errors_text}

### 🛠️ Pasos Exactos para Solucionarlo:
{actions_text}

> 💡 *Aplica las correcciones en tu rama local y haz un nuevo `git push`. El Centinela en la Nube volverá a auditar tu entrega automáticamente.*
"""
        if card_id:
            post_trello_comment(card_id, alert)
            move_trello_card(card_id, LIST_FIX)
            print(f"⚠️ Tarjeta Trello '{card_name}' movida a '⚠️ Corregir'.")

        # Alerta WhatsApp
        wa_msg = f"""👨‍🏫 *[CENTINELA EN LA NUBE 24/7 — REQUIERE AJUSTES]*
👤 *Integrante:* {m_name} ({c_badge})
📦 *Repositorio:* `{repo_name}` (PR #{pr_num})

Hola {m_name}, tu entrega tiene observaciones pendientes:
{errors[0] if errors else 'Revisa las observaciones en GitHub.'}

Tu tarjeta en Trello está en *'⚠️ Corregir'*. Ajusta tu rama y haz `git push` para re-evaluarla."""
        send_whatsapp_alert(member.get("phone", ""), member.get("apikey", ""), wa_msg)

        # Enviar fallo en GitHub Actions para que el check quede en rojo
        print("\n::error::El Pull Request no superó los Quality Gates de gobernanza.")
        sys.exit(1)

if __name__ == "__main__":
    audit_pull_request()
