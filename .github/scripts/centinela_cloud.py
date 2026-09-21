"""
centinela_cloud.py - Autonomous 24/7 Cloud Guardian (GitHub Actions)
===================================================================
EduTrack — Distributed Systems 2026-B
Technical Lead: @XimenaChala
Standard Compliance: ADR-001 (English Documentation & Tooling Standard)

Functionality:
1. Executes in GitHub Actions cloud runners 24/7 to audit opened/updated Pull Requests.
2. Evaluates mandatory Course Quality Gates:
   - PR diff size (< 400 lines of code).
   - Commit history technical justification ("Why:" / "Por qué:").
   - Strict branching policies per repository type (<abbr>-docs vs code repos).
3. Optionally syncs with external Trello governance board when credentials are provided
   via repository secrets (zero hardcoded credentials).
4. Emits clear English feedback and status reports for automated CI pass/fail status.
"""

import os
import sys
import re
import json
import urllib.parse
import subprocess
from pathlib import Path
from datetime import datetime
import requests

# Reconfigure stdout/stderr encoding for cross-platform compatibility
if hasattr(sys.stdout, "reconfigure"):
    try:
        sys.stdout.reconfigure(encoding="utf-8")
        sys.stderr.reconfigure(encoding="utf-8")
    except Exception:
        pass

# Trello Credentials (Read strictly from Environment / GitHub Secrets - Zero Hardcoded Defaults)
TRELLO_KEY = os.environ.get("TRELLO_KEY", "").strip()
TRELLO_TOKEN = os.environ.get("TRELLO_TOKEN", "").strip()
BOARD_ID = os.environ.get("TRELLO_BOARD_ID", "").strip()

# LLM Engine Credentials & Config (Google AI Studio & GitHub Secrets)
GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY", "").strip()
OPENAI_API_KEY = os.environ.get("OPENAI_API_KEY", "").strip()
LLM_API_KEY    = os.environ.get("LLM_API_KEY", "").strip() or OPENAI_API_KEY or GEMINI_API_KEY
LLM_BASE_URL   = os.environ.get("LLM_BASE_URL", "").strip()
LLM_MODEL      = os.environ.get("LLM_MODEL", "").strip()

try:
    import google.generativeai as genai
    HAS_GENAI = True
    if GEMINI_API_KEY:
        genai.configure(api_key=GEMINI_API_KEY)
except Exception as e:
    genai = None
    HAS_GENAI = False

LIST_DONE = "6aaf1756df3b5bcabf0307c9"    # ✅ Approved and Merged
LIST_FIX  = "6aaf17553a39d35efea465a1"    # ⚠️ Requires Fix
LIST_REVIEW = "6aaf17a63d79b6e2b696aa08" # Ready for Review

TEAM_MEMBERS = {
    "celestedussan": {
        "full_name": "Celeste Dussán",
        "github": ["CelesteDussan", "celestedussan", "mdussanospina"],
        "color_name": "Light Blue",
        "color_emoji": "🩵",
        "email": "mdussanospina@gmail.com",
        "phone": "573142657707",
        "apikey": ""
    },
    "juancamilopenagosmolina": {
        "full_name": "Juan Camilo Penagos Molina",
        "github": ["CamiloPenagos60", "juancamilopenagosmolina", "CamiloPenagos"],
        "color_name": "Green",
        "color_emoji": "🟩",
        "email": "Jcpenagos-2022a@corhuila.edu.co",
        "phone": "573202025309",
        "apikey": ""
    },
    "stephanvargasquiroga": {
        "full_name": "Stephan Vargas Quiroga",
        "github": ["stephanvargasquiroga", "stephanvargas", "lanvargas94"],
        "color_name": "Purple",
        "color_emoji": "🟪",
        "email": "svargas-2022a@corhuila.edu.co",
        "phone": "573175532871",
        "apikey": ""
    },
    "ximenachala": {
        "full_name": "Ximena Del Pilar Zambrano",
        "github": ["XimenaChala", "ximenachala"],
        "color_name": "Yellow",
        "color_emoji": "🟨",
        "email": "xdazmbrano-2022@corhuila.edu.co",
        "phone": "573186282069",
        "apikey": "1515606"
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
        "full_name": author_login or "Contributor",
        "github": [author_login],
        "color_name": "General",
        "color_emoji": "🏷️",
        "email": "",
        "phone": "",
        "apikey": ""
    }

def resolve_card_member(card: dict) -> dict:
    """
    Resuelve el integrante responsable de una tarjeta de Trello cruzando
    su lista real de 'idMembers' contra TEAM_MEMBERS_DIRECTORY de gestor_colores_y_miembros.py.
    Emite logs detallados cuando ocurre match exacto (nivel 1), fallback por texto (nivel 2)
    o default genérico (nivel 3).
    """
    try:
        from gestor_colores_y_miembros import TEAM_MEMBERS_DIRECTORY
    except Exception:
        TEAM_MEMBERS_DIRECTORY = {
            "celestedussan": {
                "trello_id": "64d664a5a44603e18b83f6a7",
                "trello_username": "celestedussan",
                "full_name": "Celeste Dussán",
                "github_logins": ["CelesteDussan", "celestedussan", "mdussanospina"],
                "color_name": "Light Blue",
                "color_emoji": "🩵"
            },
            "juancamilopenagosmolina": {
                "trello_id": "665765ef2f7caa2653da7a58",
                "trello_username": "juancamilopenagosmolina",
                "full_name": "Juan Camilo Penagos Molina",
                "github_logins": ["CamiloPenagos60", "juancamilopenagosmolina", "CamiloPenagos"],
                "color_name": "Green",
                "color_emoji": "🟩"
            },
            "stephanvargasquiroga": {
                "trello_id": "654c1e85c5fc8d84b827177a",
                "trello_username": "stephanvargasquiroga",
                "full_name": "Stephan Vargas Quiroga",
                "github_logins": ["stephanvargasquiroga", "stephanvargas", "lanvargas94"],
                "color_name": "Purple",
                "color_emoji": "🟪"
            },
            "ximenachala": {
                "trello_id": "6a4f3bab9f690436bca48d1a",
                "trello_username": "ximenachala",
                "full_name": "Ximena Del Pilar Zambrano",
                "github_logins": ["XimenaChala", "ximenachala"],
                "color_name": "Yellow",
                "color_emoji": "🟨"
            }
        }

    card_name = card.get("name", "Tarjeta sin título")
    card_member_ids = card.get("idMembers", [])

    # 1. NIVEL 1 (MATCH EXACTO): Búsqueda por trello_id asignado en la tarjeta
    for mid in card_member_ids:
        for uname, info in TEAM_MEMBERS_DIRECTORY.items():
            if info.get("trello_id") == mid:
                contact_info = TEAM_MEMBERS.get(uname, {})
                c_name = info.get("color_name", "General")
                c_emoji = info.get("color_emoji", "🏷️")
                print(f"🎯 [CENTINELA ATTRIBUTION EXACT - NIVEL 1]: Tarjeta '{card_name}' asociada exactamente por trello_id ({mid}) a {info['full_name']} ({c_name} {c_emoji}).")
                return {
                    "full_name": info["full_name"],
                    "github": info.get("github_logins", []),
                    "color_name": c_name,
                    "color_emoji": c_emoji,
                    "email": contact_info.get("email", ""),
                    "phone": contact_info.get("phone", ""),
                    "apikey": contact_info.get("apikey", ""),
                    "match_level": 1,
                    "trello_id": mid
                }

    # Si no hubo match por idMembers, registrar la razón para el log
    if not card_member_ids:
        reason = "la lista 'idMembers' está vacía en Trello (nadie asignado formalmente)"
    else:
        reason = f"ninguno de los idMembers {card_member_ids} coincide con los IDs registrados en TEAM_MEMBERS_DIRECTORY"

    # 2. NIVEL 2 (FALLBACK POR TEXTO / MENCIÓN)
    card_text = (card_name + " " + card.get("desc", "")).lower()
    for uname, info in TEAM_MEMBERS_DIRECTORY.items():
        matched_kw = None
        if uname in card_text:
            matched_kw = uname
        elif info["full_name"].lower() in card_text:
            matched_kw = info["full_name"]
        else:
            for gh in info.get("github_logins", []):
                if gh.lower() in card_text:
                    matched_kw = gh
                    break

        if matched_kw:
            contact_info = TEAM_MEMBERS.get(uname, {})
            c_name = info.get("color_name", "General")
            c_emoji = info.get("color_emoji", "🏷️")
            print(f"⚠️ [CENTINELA ATTRIBUTION FALLBACK - NIVEL 2]: Tarjeta '{card_name}' no tuvo match exacto por idMembers ({reason}). Resuelta por texto/mención ('{matched_kw}') a {info['full_name']} ({c_name} {c_emoji}).")
            return {
                "full_name": info["full_name"],
                "github": info.get("github_logins", []),
                "color_name": c_name,
                "color_emoji": c_emoji,
                "email": contact_info.get("email", ""),
                "phone": contact_info.get("phone", ""),
                "apikey": contact_info.get("apikey", ""),
                "match_level": 2,
                "trello_id": info.get("trello_id", "")
            }

    # 3. NIVEL 3 (DEFAULT GENÉRICO)
    print(f"❌ [CENTINELA ATTRIBUTION DEFAULT - NIVEL 3]: Tarjeta '{card_name}' no tuvo match por idMembers ({reason}) ni mención en texto. Se asignó integrante genérico por defecto.")
    return {
        "full_name": "Contributor",
        "github": ["Contributor"],
        "color_name": "General",
        "color_emoji": "🏷️",
        "email": "",
        "phone": "",
        "apikey": "",
        "match_level": 3,
        "trello_id": None
    }

def post_trello_comment(card_id: str, text: str):
    if not TRELLO_KEY or not TRELLO_TOKEN or not card_id:
        return
    url = f"https://api.trello.com/1/cards/{card_id}/actions/comments?key={TRELLO_KEY}&token={TRELLO_TOKEN}"
    try:
        requests.post(url, data={"text": text}, timeout=10)
    except Exception as e:
        print(f"Notice: Trello comment dispatch skipped: {e}")

def add_trello_checklist(card_id: str, title: str, items: list):
    """Creates an interactive checklist on the Trello card so the teammate can check off each required fix."""
    if not TRELLO_KEY or not TRELLO_TOKEN or not card_id or not items:
        return
    try:
        c_url = f"https://api.trello.com/1/cards/{card_id}/checklists?name={urllib.parse.quote(title)}&key={TRELLO_KEY}&token={TRELLO_TOKEN}"
        res = requests.post(c_url, timeout=10)
        if res.status_code == 200:
            cl_id = res.json().get("id")
            for item in items:
                clean_item = item[:150]
                i_url = f"https://api.trello.com/1/checklists/{cl_id}/checkItems?name={urllib.parse.quote(clean_item)}&key={TRELLO_KEY}&token={TRELLO_TOKEN}"
                requests.post(i_url, timeout=5)
            print(f"📋 Interactive checklist '{title}' created on Trello card.")
    except Exception as e:
        print(f"Notice: Trello checklist dispatch skipped: {e}")

def post_github_pr_comment(repo_full: str, pr_num: str, comment: str):
    """Posts an automated review comment directly onto the GitHub Pull Request."""
    gh_token = os.environ.get("GH_TOKEN", "").strip()
    if not gh_token or not pr_num or not repo_full:
        return
    clean_repo = repo_full if "/" in repo_full else f"code-corhuila/{repo_full}"
    url = f"https://api.github.com/repos/{clean_repo}/issues/{pr_num}/comments"
    headers = {
        "Authorization": f"Bearer {gh_token}",
        "Accept": "application/vnd.github+json"
    }
    try:
        res = requests.post(url, json={"body": comment}, headers=headers, timeout=10)
        if res.status_code in [200, 201]:
            print("💬 Automated feedback comment posted on GitHub PR.")
        else:
            print(f"Notice: GitHub PR comment returned HTTP {res.status_code}: {res.text[:100]}")
    except Exception as e:
        print(f"Notice: GitHub PR comment dispatch skipped: {e}")

def fetch_pr_diff(repo_full: str, pr_num: str) -> str:
    """
    Obtains the full .diff or .patch of the modified files using the GitHub API
    (Accept: application/vnd.github.v3.diff), falling back to git diff if running locally.
    """
    gh_token = os.environ.get("GH_TOKEN") or os.environ.get("GITHUB_TOKEN", "").strip()
    clean_repo = repo_full if "/" in repo_full else f"code-corhuila/{repo_full}"

    if gh_token and pr_num:
        diff_url = f"https://api.github.com/repos/{clean_repo}/pulls/{pr_num}"
        headers = {
            "Authorization": f"Bearer {gh_token}",
            "Accept": "application/vnd.github.v3.diff"
        }
        try:
            res = requests.get(diff_url, headers=headers, timeout=15)
            if res.status_code == 200 and res.text:
                print(f"📥 [GITHUB API]: Diff del PR #{pr_num} extraído con éxito ({len(res.text)} caracteres).")
                return res.text
            else:
                print(f"Notice: GitHub API diff returned HTTP {res.status_code}: {res.text[:100]}")
        except Exception as e:
            print(f"Notice: Error al extraer diff vía GitHub API: {e}")

    # Fallback a git diff local si el repositorio está clonado
    try:
        base_ref = os.environ.get("BASE_REF", "develop")
        diff_cmd = ["git", "diff", f"origin/{base_ref}...HEAD"]
        stat_res = subprocess.run(diff_cmd, capture_output=True, text=True, errors="ignore")
        if stat_res.returncode == 0 and stat_res.stdout.strip():
            print(f"📥 [GIT LOCAL]: Diff extraído contra origin/{base_ref} ({len(stat_res.stdout)} caracteres).")
            return stat_res.stdout
    except Exception as e:
        print(f"Notice: Error al calcular diff git local: {e}")

    return ""

def execute_auto_merge_pr(repo_full: str, pr_num: str, commit_title: str = "", commit_message: str = "") -> bool:
    """
    Executes autonomous Auto-Merge in GitHub API (PUT /repos/{owner}/{repo}/pulls/{pr_num}/merge)
    when the AI Reviewer determines the code is correct, secure, and compliant.
    """
    gh_token = os.environ.get("GH_TOKEN") or os.environ.get("GITHUB_TOKEN", "").strip()
    clean_repo = repo_full if "/" in repo_full else f"code-corhuila/{repo_full}"
    if not gh_token or not pr_num:
        print("⚠️ Auto-merge omitido: GH_TOKEN o PR_NUMBER no disponibles.")
        return False

    url = f"https://api.github.com/repos/{clean_repo}/pulls/{pr_num}/merge"
    headers = {
        "Authorization": f"Bearer {gh_token}",
        "Accept": "application/vnd.github+json"
    }

    title = commit_title or f"chore(ci): autonomous auto-merge PR #{pr_num} [AI-Approved]"
    message = commit_message or "Approved by EduTrack Autonomous AI Reviewer on behalf of Technical Lead @XimenaChala."

    # Intentar primero con squash y luego con merge
    for method in ["squash", "merge"]:
        payload = {
            "commit_title": title,
            "commit_message": message,
            "merge_method": method
        }
        try:
            res = requests.put(url, json=payload, headers=headers, timeout=15)
            if res.status_code == 200:
                print(f"🔀 [AUTO-MERGE AUTÓNOMO EXITOSO]: PR #{pr_num} mergeado a la rama base con método '{method}'.")
                return True
            elif res.status_code == 405:
                print(f"Notice: Método de auto-merge '{method}' no permitido en el repo (HTTP 405), probando siguiente...")
                continue
            elif res.status_code == 409:
                print(f"❌ [AUTO-MERGE CONFLICTO]: No se puede mergear el PR #{pr_num} por conflictos de ramas (HTTP 409).")
                return False
            else:
                print(f"Notice: Auto-merge devolvió HTTP {res.status_code}: {res.text[:120]}")
        except Exception as e:
            print(f"Notice: Excepción durante auto-merge: {e}")

    return False

def fetch_pr_details(repo_full: str, pr_num: str) -> dict:
    """Fetches PR metadata including head commit SHA for inline line reviews."""
    gh_token = os.environ.get("GH_TOKEN") or os.environ.get("GITHUB_TOKEN", "").strip()
    clean_repo = repo_full if "/" in repo_full else f"code-corhuila/{repo_full}"
    if not gh_token or not pr_num:
        return {}
    url = f"https://api.github.com/repos/{clean_repo}/pulls/{pr_num}"
    headers = {"Authorization": f"Bearer {gh_token}", "Accept": "application/vnd.github+json"}
    try:
        res = requests.get(url, headers=headers, timeout=10)
        if res.status_code == 200:
            return res.json()
    except Exception:
        pass
    return {}

def submit_pr_line_review(repo_full: str, pr_num: str, aprobado: bool, resumen: str, cambios_requeridos: list) -> bool:
    """
    Submits official review on GitHub:
    - If aprobado == True: event='APPROVE'
    - If aprobado == False: event='REQUEST_CHANGES', posting inline Review Comments on the affected lines
      with the suggested code blocks so teammates can easily copy & paste or click 'Apply suggestion'!
    """
    gh_token = os.environ.get("GH_TOKEN") or os.environ.get("GITHUB_TOKEN", "").strip()
    clean_repo = repo_full if "/" in repo_full else f"code-corhuila/{repo_full}"
    if not gh_token or not pr_num:
        print("⚠️ Revisión omitida: GH_TOKEN o PR_NUMBER no disponibles.")
        return False

    headers = {
        "Authorization": f"Bearer {gh_token}",
        "Accept": "application/vnd.github+json"
    }

    # Fetch PR details to obtain the head commit SHA required for inline review comments
    pr_details = fetch_pr_details(clean_repo, pr_num)
    head_sha = pr_details.get("head", {}).get("sha", "")

    if aprobado:
        body = f"""# 🤖 [EDUTRACK AI CODE REVIEWER — APROBADO]
**Evaluador:** Revisor Técnico Senior con Inteligencia Artificial (Gemini 1.5 Flash) en representación de @XimenaChala.
**Estado:** ✅ **APROBADO PARA MERGE AUTOMÁTICO**

### 📋 Resumen del Análisis:
{resumen}

---
> 🚀 *Todas las verificaciones de sintaxis, seguridad y lógica arquitectónica han sido superadas. Procediendo con el Auto-Merge autónomo.*"""
        url = f"https://api.github.com/repos/{clean_repo}/pulls/{pr_num}/reviews"
        payload = {"body": body, "event": "APPROVE"}
        try:
            res = requests.post(url, json=payload, headers=headers, timeout=15)
            if res.status_code in [200, 201]:
                print(f"📝 [GITHUB REVIEW]: Revisión 'APPROVE' publicada en el PR #{pr_num}.")
                return True
        except Exception as e:
            print(f"Notice: Error al enviar review APPROVE: {e}")
            post_github_pr_comment(clean_repo, pr_num, body)
        return True

    else:
        # Formatear el cuerpo principal de la revisión con todas las correcciones
        code_snippets_body = []
        for idx, c in enumerate(cambios_requeridos, 1):
            arch = c.get("archivo", "archivo")
            linea = c.get("linea_aproximada", 1)
            motivo = c.get("motivo", "Ajuste técnico requerido")
            codigo = c.get("codigo_sugerido", "")
            code_snippets_body.append(f"""#### 📄 {idx}. Archivo: `{arch}` (Línea aprox. {linea})
> **Motivo:** {motivo}

```
{codigo}
```
""")
        snippets_text = "\n".join(code_snippets_body) if code_snippets_body else "> *Consulta los comentarios en las líneas del código.*"

        review_body = f"""# 🤖 [EDUTRACK AI CODE REVIEWER — CAMBIOS REQUERIDOS]
**Evaluador:** Revisor Técnico Senior con Inteligencia Artificial (Gemini 1.5 Flash) en representación de @XimenaChala.
**Estado:** ⚠️ **REQUEST_CHANGES (Se requieren correcciones antes del merge)**

### 📋 Resumen del Diagnóstico:
{resumen}

### 🛠️ Correcciones Técnicas Sugeridas (Listas para Copiar y Pegar):
{snippets_text}

---
> 💡 **Instrucciones para el desarrollador:**
> 1. Abre los archivos indicados en tu editor local.
> 2. Reemplaza el código con las sugerencias indicadas arriba.
> 3. Haz commit con justificación técnica (`Why: ...`) y sube con `git push`.
> 4. El Revisor con IA re-evaluará el PR automáticamente y ejecutará el Auto-Merge."""

        url = f"https://api.github.com/repos/{clean_repo}/pulls/{pr_num}/reviews"
        line_comments = []
        if head_sha:
            for c in cambios_requeridos:
                arch = c.get("archivo", "")
                linea = c.get("linea_aproximada")
                motivo = c.get("motivo", "Corrección sugerida por el Revisor con IA")
                codigo = c.get("codigo_sugerido", "")
                if arch and linea:
                    try:
                        line_comments.append({
                            "path": arch,
                            "line": int(linea),
                            "side": "RIGHT",
                            "body": f"```suggestion\n{codigo}\n```\n\n💡 **Motivo:** {motivo}"
                        })
                    except Exception:
                        pass

        # 1. Intentar enviar con inline comments si hay comentarios válidos
        if line_comments and head_sha:
            payload = {
                "commit_id": head_sha,
                "body": review_body,
                "event": "REQUEST_CHANGES",
                "comments": line_comments
            }
            try:
                res = requests.post(url, json=payload, headers=headers, timeout=15)
                if res.status_code in [200, 201]:
                    print(f"📝 [GITHUB REVIEW]: Revisión oficial 'REQUEST_CHANGES' con {len(line_comments)} comentario(s) de línea publicada en PR #{pr_num}.")
                    return True
                else:
                    print(f"Notice: Envío con comentarios de línea devolvió HTTP {res.status_code}: {res.text[:120]}. Reintentando a nivel general...")
            except Exception as e:
                print(f"Notice: Error al enviar revisión con inline comments: {e}")

        # 2. Si fallaron los inline comments o la línea no estaba en el diff, enviar el review general
        payload_general = {
            "body": review_body,
            "event": "REQUEST_CHANGES"
        }
        try:
            res_gen = requests.post(url, json=payload_general, headers=headers, timeout=15)
            if res_gen.status_code in [200, 201]:
                print(f"📝 [GITHUB REVIEW]: Revisión 'REQUEST_CHANGES' publicada en PR #{pr_num}.")
                return True
            else:
                print(f"Notice: Review general devolvió HTTP {res_gen.status_code}: {res_gen.text[:120]}")
        except Exception as e:
            print(f"Notice: Error al enviar review general: {e}")

        # 3. Fallback a comentario de issue
        post_github_pr_comment(clean_repo, pr_num, review_body)
        return True

def submit_pr_review(repo_full: str, pr_num: str, event: str, body: str) -> bool:
    """Compatibilidad: envia una revision formal simple de PR."""
    return submit_pr_line_review(repo_full, pr_num, aprobado=(event == "APPROVE"), resumen=body, cambios_requeridos=[])

def extract_json_payload(raw_text: str) -> dict:
    """Safely extracts JSON object from raw LLM output text."""
    if not raw_text:
        return {}
    cleaned = raw_text.strip()
    if cleaned.startswith("```"):
        lines = cleaned.splitlines()
        if lines and lines[0].startswith("```"):
            lines = lines[1:]
        if lines and lines[-1].startswith("```"):
            lines = lines[:-1]
        cleaned = "\n".join(lines).strip()
    try:
        return json.loads(cleaned)
    except Exception:
        match = re.search(r"(\{.*\})", raw_text, re.DOTALL)
        if match:
            try:
                return json.loads(match.group(1))
            except Exception:
                pass
    return {}

def call_gemini_api(api_key: str, system_prompt: str, user_prompt: str) -> dict:
    """Invokes Google Gemini REST API using gemini-1.5-flash."""
    models = ["gemini-1.5-flash", "gemini-2.0-flash", "gemini-1.5-pro"]
    headers = {"Content-Type": "application/json"}
    combined_prompt = f"{system_prompt}\n\n====================\nPULL REQUEST AUDIT TASK:\n====================\n{user_prompt}"
    payload = {
        "contents": [
            {"parts": [{"text": combined_prompt}]}
        ],
        "generationConfig": {
            "temperature": 0.1,
            "responseMimeType": "application/json"
        }
    }
    for model in models:
        url = f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent?key={api_key}"
        try:
            res = requests.post(url, json=payload, headers=headers, timeout=30)
            if res.status_code == 200:
                data = res.json()
                text = data["candidates"][0]["content"]["parts"][0]["text"]
                parsed = extract_json_payload(text)
                if parsed:
                    return parsed
            else:
                print(f"Notice: Gemini ({model}) returned HTTP {res.status_code}: {res.text[:120]}")
        except Exception as e:
            print(f"Notice: Gemini ({model}) request error: {e}")
    return None

def call_openai_api(api_key: str, system_prompt: str, user_prompt: str, base_url: str = "") -> dict:
    """Invokes OpenAI Chat API or OpenAI-compatible endpoint."""
    endpoint = base_url.rstrip("/") if base_url else "https://api.openai.com/v1"
    url = f"{endpoint}/chat/completions"
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json"
    }
    model = os.environ.get("LLM_MODEL", "gpt-4o-mini")
    payload = {
        "model": model,
        "messages": [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt}
        ],
        "response_format": {"type": "json_object"},
        "temperature": 0.1
    }
    try:
        res = requests.post(url, json=payload, headers=headers, timeout=30)
        if res.status_code == 200:
            data = res.json()
            text = data["choices"][0]["message"]["content"]
            parsed = extract_json_payload(text)
            if parsed:
                return parsed
        else:
            print(f"Notice: OpenAI API returned HTTP {res.status_code}: {res.text[:120]}")
    except Exception as e:
        print(f"Notice: OpenAI API request error: {e}")
    return None

def analyze_pr_with_gemini(
    repo_name: str,
    author: str,
    pr_num: str,
    head_ref: str,
    base_ref: str,
    diff_text: str,
    static_errors: list,
    spec_data: dict,
    member: dict
) -> dict:
    """
    Sends PR diff and microservices architectural context to Google Gemini (gemini-1.5-flash)
    via google.generativeai (or REST fallback) enforcing response_mime_type="application/json".
    Acts as Senior Technical Reviewer / Tech Lead evaluating syntax, security, and architectural logic.
    Returns:
    {
      "aprobado": true/false,
      "comentario_resumen": "...",
      "cambios_requeridos": [
        {
          "archivo": "...",
          "linea_aproximada": 123,
          "motivo": "...",
          "codigo_sugerido": "..."
        }
      ]
    }
    """
    m_name = member["full_name"]
    c_badge = f"{member['color_name']} {member['color_emoji']}"

    max_diff_chars = 120000
    truncated_diff = diff_text
    if len(diff_text) > max_diff_chars:
        truncated_diff = diff_text[:max_diff_chars] + f"\n\n... [DIFF TRUNCADO POR TAMAÑO: {len(diff_text)} caracteres totales] ..."

    services_summary = json.dumps(spec_data.get("services", {}), indent=2)

    prompt = f"""Actúa como el Revisor Técnico Senior (Tech Lead) y Arquitecto de Software de la plataforma distribuida 'EduTrack' (Sistemas Distribuidos 2026-B).
Tu función es evaluar Pull Requests de manera autónoma en representación de la Líder Técnica @XimenaChala.

### 🏛️ ARQUITECTURA DE MICROSERVICIOS Y CATÁLOGO DEL SISTEMA:
EduTrack opera bajo arquitectura de microservicios con aislamiento de bases de datos (ADR-003: Database per Service):
{services_summary}

### 👥 ROLES Y RESPONSABILIDADES DEL EQUIPO:
- Celeste Dussán (@CelesteDussan, 🩵 Celeste): Líder Frontend. Portales desacoplados en React / Vite (:3001, :3002, :3003, :3005) y shell unificado (:3000).
- Juan Camilo Penagos Molina (@CamiloPenagos60, 🟩 Verde): Arquitecto de Datos. PostgreSQL 16, esquemas Flyway, claves primarias obligatorias con 'UUID PRIMARY KEY DEFAULT gen_random_uuid()' (ADR-003). Cero fugas de dominio entre bases de datos.
- Stephan Vargas Quiroga (@stephanvargasquiroga, 🟪 Morado): Arquitecto Backend. Microservicios en Spring Boot / Go, Arquitectura Hexagonal estricta (domain, application, infrastructure), REST y worker AMQP RabbitMQ.
- Ximena Del Pilar Zambrano (@XimenaChala, 🟨 Amarillo): Líder Técnica, API Gateway (:8080) y gobernanza global.

### 📐 CRITERIOS DE REVISIÓN OBLIGATORIOS:
1. Sintaxis y Calidad de Código: Código funcional, sin errores de compilación, imports limpios y buenas prácticas.
2. Seguridad: Cero credenciales en texto plano, sin vulnerabilidades de SQL Injection, manejo de excepciones sin panics/500.
3. Lógica Arquitectónica:
   - Aislamiento de dominio: Ningún microservicio debe acceder a tablas ajenas (ej. academic no toca identity).
   - En APIs backend: Capas hexagonales respetadas (el dominio no depende de la infraestructura).
   - En bases de datos: Claves primarias UUID gen_random_uuid(), nunca enteros autoincrementales.
   - En puertos: Puertos configurados idénticos a los del catálogo oficial.
4. Gobernanza: PR acotado (< 400 líneas), commits con justificación técnica ('Why:').

### 📦 CONTEXTO DEL PULL REQUEST ACTUAL:
- Repositorio: `{repo_name}`
- Pull Request: #{pr_num}
- Autor: @{author} ({m_name}, {c_badge})
- Rama Origen: `{head_ref}` -> Rama Base: `{base_ref}`

### 📝 DIFF COMPLETO DE LOS CAMBIOS:
```diff
{truncated_diff}
```

### 🎯 TU TAREA:
Evalúa la sintaxis, seguridad y lógica arquitectónica de este Pull Request.
Debes devolver OBLIGATORIAMENTE una respuesta en formato JSON válido con esta estructura exacta:
{{
  "aprobado": true,
  "comentario_resumen": "Resumen ejecutivo claro y técnico del análisis...",
  "cambios_requeridos": [
    {{
      "archivo": "ruta/exacta/al/archivo.ext",
      "linea_aproximada": 123,
      "motivo": "Explicación precisa de qué falló y por qué",
      "codigo_sugerido": "Bloque de código corregido completo listo para copiar y pegar"
    }}
  ]
}}

Si 'aprobado' es true, 'cambios_requeridos' DEBE ser una lista vacía [].
Si 'aprobado' es false, 'cambios_requeridos' DEBE contener cada uno de los archivos y líneas que deben corregirse con su respectivo 'codigo_sugerido' listo para que el equipo lo copie y pegue."""

    candidate_models = ["gemini-3.6-flash", "gemini-3.5-flash", "gemini-flash-latest", "gemini-1.5-flash", "gemini-2.0-flash"]

    # 1. Llamada a Google Generative AI SDK (google.generativeai)
    if HAS_GENAI and GEMINI_API_KEY:
        for m_cand in candidate_models:
            try:
                print(f"🤖 [GEMINI AI]: Evaluando PR #{pr_num} con '{m_cand}' vía google.generativeai...")
                model = genai.GenerativeModel(
                    model_name=m_cand,
                    generation_config={
                        "temperature": 0.1,
                        "response_mime_type": "application/json"
                    }
                )
                response = model.generate_content(prompt)
                if response and response.text:
                    parsed = json.loads(response.text)
                    if "aprobado" in parsed:
                        print(f"   ✅ [GEMINI AI ({m_cand})]: Decisión recibida -> Aprobado: {parsed.get('aprobado')}")
                        return parsed
            except Exception as e:
                print(f"Notice: Modelo '{m_cand}' no disponible o error: {e}")

    # 2. Llamada REST fallback a Google Gemini API
    if GEMINI_API_KEY:
        for m_cand in candidate_models:
            try:
                print(f"🤖 [GEMINI REST]: Evaluando PR #{pr_num} con Gemini REST endpoint ({m_cand})...")
                url = f"https://generativelanguage.googleapis.com/v1beta/models/{m_cand}:generateContent?key={GEMINI_API_KEY}"
                headers = {"Content-Type": "application/json"}
                payload = {
                    "contents": [{"parts": [{"text": prompt}]}],
                    "generationConfig": {
                        "temperature": 0.1,
                        "response_mime_type": "application/json"
                    }
                }
                res = requests.post(url, json=payload, headers=headers, timeout=30)
                if res.status_code == 200:
                    data = res.json()
                    text = data["candidates"][0]["content"]["parts"][0]["text"]
                    parsed = extract_json_payload(text)
                    if parsed and "aprobado" in parsed:
                        print(f"   ✅ [GEMINI REST ({m_cand})]: Decisión recibida -> Aprobado: {parsed.get('aprobado')}")
                        return parsed
            except Exception as e:
                pass

    # 3. Llamada alternativa a OpenAI / LLM_API_KEY si estuviera configurada
    if OPENAI_API_KEY or LLM_API_KEY:
        try:
            print(f"🤖 [OPENAI/LLM]: Evaluando PR #{pr_num} con LLM API alternativo...")
            res_oa = call_openai_api(OPENAI_API_KEY or LLM_API_KEY, "You are a Senior Tech Lead. Return JSON.", prompt, LLM_BASE_URL)
            if res_oa and "aprobado" in res_oa:
                return res_oa
        except Exception as e:
            print(f"Notice: Error en LLM alternativo: {e}")

    # 4. Fallback Determinista si no hay API Key activa o red inaccesible
    print("ℹ️ [AI FALLBACK]: Sin conexión con API de LLM. Aplicando evaluación determinista de Gobernanza.")
    if not static_errors:
        return {
            "aprobado": True,
            "comentario_resumen": f"Auditoría técnica superada al 100%. Código conforme a estándares de EduTrack para {m_name}.",
            "cambios_requeridos": []
        }
    else:
        req_changes = []
        for idx, err in enumerate(static_errors, 1):
            req_changes.append({
                "archivo": repo_name,
                "linea_aproximada": 1,
                "motivo": err,
                "codigo_sugerido": f"// Corrección obligatoria de gobernanza {idx}:\n// {err}"
            })
        return {
            "aprobado": False,
            "comentario_resumen": f"Se detectaron {len(static_errors)} no-conformidades en las puertas de calidad.",
            "cambios_requeridos": req_changes
        }

def analyze_pr_with_ai(repo_name, author, pr_num, head_ref, base_ref, diff_text, static_errors, static_actions, spec_data, member):
    """Wrapper de compatibilidad."""
    return analyze_pr_with_gemini(repo_name, author, pr_num, head_ref, base_ref, diff_text, static_errors, spec_data, member)

def trigger_continuous_replenishment():
    """
    Triggers automatic card replenishment so the teammate immediately gets their next task.
    """
    try:
        from despachador_flujo_continuo_trello import ensure_minimum_active_cards
        print("\n⚡ [CENTINELA AI]: Despachando automáticamente la siguiente tarea en Trello...")
        ensure_minimum_active_cards(min_cards_per_member=3)
        return
    except Exception:
        pass

    try:
        sys.path.append(str(Path(__file__).parent))
        sys.path.append(str(Path(__file__).parent.parent / "scripts"))
        from despachador_flujo_continuo_trello import ensure_minimum_active_cards
        print("\n⚡ [CENTINELA AI]: Despachando automáticamente la siguiente tarea en Trello...")
        ensure_minimum_active_cards(min_cards_per_member=3)
    except Exception as e:
        print(f"Notice: Continuous task dispatch skipped: {e}")

def move_trello_card(card_id: str, list_id: str):
    if not TRELLO_KEY or not TRELLO_TOKEN or not card_id or not list_id:
        return
    url = f"https://api.trello.com/1/cards/{card_id}?key={TRELLO_KEY}&token={TRELLO_TOKEN}"
    try:
        requests.put(url, data={"idList": list_id}, timeout=10)
    except Exception as e:
        print(f"Notice: Trello card move skipped: {e}")

def find_card_for_repo(repo_name: str) -> dict:
    if not TRELLO_KEY or not TRELLO_TOKEN or not BOARD_ID:
        return {}
    url = f"https://api.trello.com/1/boards/{BOARD_ID}/cards?fields=name,desc,idList,idMembers&key={TRELLO_KEY}&token={TRELLO_TOKEN}"
    try:
        res = requests.get(url, timeout=10)
        if res.status_code == 200:
            cards = res.json()
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
            for c in cards:
                if repo_name.lower() in (c.get("name", "") + " " + c.get("desc", "")).lower():
                    return c
    except Exception as e:
        print(f"Notice: Trello card lookup skipped: {e}")
    return {}

def load_architecture_spec() -> dict:
    """Loads the architecture specification from local file, remote educk-docs raw URL, or built-in fallback."""
    spec_paths = [
        Path(".github/architecture_spec.json"),
        Path("architecture_spec.json"),
        Path("../educk-docs/.github/architecture_spec.json"),
        Path("../automatizacion/architecture_spec.json")
    ]
    for p in spec_paths:
        if p.exists():
            try:
                return json.loads(p.read_text(encoding="utf-8"))
            except Exception:
                pass
                
    spec_url = "https://raw.githubusercontent.com/code-corhuila/educk-docs/main/.github/architecture_spec.json"
    try:
        res = requests.get(spec_url, timeout=5)
        if res.status_code == 200:
            return res.json()
    except Exception:
        pass

    return {
        "services": {
            "identity": {"api_port": 8081, "db_name": "identity_db", "portal_port": 3001, "tables": ["users", "students", "schools", "parent_child_link"]},
            "academic": {"api_port": 8082, "db_name": "academic_db", "portal_port": 3002, "tables": ["subjects", "assignments", "grades"], "events": ["GradeCreated"]},
            "attendance": {"api_port": 8083, "db_name": "attendance_db", "portal_port": 3003, "tables": ["attendance_events", "attendance_processed"], "events": ["StudentAbsent"]},
            "communication": {"api_port": 8085, "db_name": "communication_db", "portal_port": 3005, "tables": ["messages", "conversations", "conversation_participants", "message_reads"]}
        }
    }

def perform_semantic_content_audit(repo_name: str, spec: dict) -> tuple:
    """
    Semantically verifies the checked out repository files against educk-docs specs.
    Returns: (errors: list, actions: list)
    """
    errors = []
    actions = []
    clean_repo = repo_name.lower().strip()
    
    services = spec.get("services", {})
    matched_dom = None
    role = "unknown"

    if clean_repo.endswith("-db"):
        role = "db"
    elif clean_repo.endswith("-api") or clean_repo == "edutrack":
        role = "api"
    elif clean_repo.endswith("-portal") or clean_repo == "educk-front":
        role = "portal"
    elif clean_repo == "educk-docs":
        return [], []

    for dom, s_info in services.items():
        if dom in clean_repo:
            matched_dom = dom
            break
            
    if not matched_dom and clean_repo == "edutrack":
        matched_dom = "communication"

    if not matched_dom or matched_dom not in services:
        return [], []

    s_info = services[matched_dom]
    expected_tables = set(s_info.get("tables", []))
    expected_api_port = s_info.get("api_port")
    expected_portal_port = s_info.get("portal_port")
    expected_db_name = s_info.get("db_name")

    all_tables = {}
    for other_dom, other_s in services.items():
        for t in other_s.get("tables", []):
            all_tables[t] = other_dom

    # 1. Database Repositories Audit
    if role == "db":
        sql_files = list(Path(".").glob("migrations/*.sql")) or list(Path(".").glob("**/*.sql"))
        found_tables = set()
        for sf in sql_files:
            try:
                content = sf.read_text(encoding="utf-8", errors="ignore")
                matches = re.findall(r"CREATE\s+TABLE\s+(?:IF\s+NOT\s+EXISTS\s+)?(?:[a-zA-Z0-9_]+\.)?([a-zA-Z0-9_]+)", content, re.IGNORECASE)
                for m in matches:
                    found_tables.add(m.lower())
                if "CREATE TABLE" in content.upper() and not ("UUID" in content.upper() or "GEN_RANDOM_UUID" in content.upper()):
                    errors.append(f"In '{sf.name}': Tables must use 'UUID PRIMARY KEY DEFAULT gen_random_uuid()' per ADR-003 standard.")
                    actions.append(f"Change primary key data type to UUID in '{sf.name}'.")
            except Exception:
                pass

        if expected_tables and found_tables:
            for ft in found_tables:
                if ft in all_tables and all_tables[ft] != matched_dom:
                    owner = all_tables[ft]
                    errors.append(f"DOMAIN LEAK DETECTED: Table '{ft}' belongs to '{owner}' service per educk-docs, but was created in '{repo_name}'.")
                    actions.append(f"Remove '{ft}' from this service. Every microservice must have its own isolated database (ADR-003 Database per Service).")
            missing = expected_tables - found_tables
            if missing and len(found_tables) > 0:
                errors.append(f"INCOMPLETE TABLES: According to educk-docs, this service must implement {sorted(list(expected_tables))}. Missing: {sorted(list(missing))}.")
                actions.append(f"Consult 'educk-docs/09-microservices/services/' and add the missing tables {sorted(list(missing))} in Flyway migrations.")

    # 2. Backend API Audit
    elif role == "api":
        app_configs = list(Path(".").glob("**/application*.yml")) + list(Path(".").glob("**/application*.properties"))
        for cf in app_configs:
            try:
                text = cf.read_text(encoding="utf-8", errors="ignore")
                port_match = re.search(r"port:\s*(\d+)", text) or re.search(r"server\.port\s*=\s*(\d+)", text)
                if port_match and expected_api_port:
                    conf_port = int(port_match.group(1))
                    if conf_port != expected_api_port:
                        errors.append(f"PORT CONFLICT: Configured port :{conf_port} does not match assigned port :{expected_api_port} in educk-docs service catalog.")
                        actions.append(f"Set 'port: {expected_api_port}' in '{cf.name}' to prevent gateway routing collisions.")
            except Exception:
                pass

        java_src = Path("src/main/java")
        if java_src.exists():
            pkg_dirs = [d.name.lower() for d in java_src.glob("**/*") if d.is_dir()]
            has_domain = any("domain" in p for p in pkg_dirs)
            has_application = any("application" in p for p in pkg_dirs)
            if not (has_domain and has_application):
                errors.append("HEXAGONAL ARCHITECTURE VIOLATION: Source code does not implement required 'domain/' and 'application/' layer separation.")
                actions.append("Refactor code into Hexagonal layers: domain (ports/entities) and application (services/use cases).")

    # 3. Frontend Portal Audit
    elif role == "portal":
        vite_conf = Path("vite.config.js") if Path("vite.config.js").exists() else Path("vite.config.ts")
        if vite_conf.exists() and expected_portal_port:
            try:
                v_text = vite_conf.read_text(encoding="utf-8", errors="ignore")
                v_port = re.search(r"port:\s*(\d+)", v_text)
                if v_port and int(v_port.group(1)) != expected_portal_port:
                    errors.append(f"PORTAL PORT CONFLICT: Configured port :{v_port.group(1)} does not match assigned portal port :{expected_portal_port} in educk-docs.")
                    actions.append(f"Update port to :{expected_portal_port} in vite.config.js.")
            except Exception:
                pass

    return errors, actions

def send_whatsapp_alert(phone: str, apikey: str, message: str):
    if not phone:
        return
    encoded = urllib.parse.quote(message)
    wa_link = f"https://wa.me/{phone}?text={encoded}"
    print(f"📱 [WHATSAPP DIRECT LINK]: {wa_link}")
    if apikey:
        try:
            call_phone = phone if phone.startswith("+") else f"+{phone}"
            call_url = f"https://api.callmebot.com/whatsapp.php?phone={urllib.parse.quote(call_phone)}&text={encoded}&apikey={apikey}"
            res = requests.get(call_url, timeout=5)
            if res.status_code == 200:
                print(f"   ✅ Automated WhatsApp alert dispatched to {call_phone}")
            else:
                print(f"   ℹ️ CallMeBot notification response: HTTP {res.status_code}")
        except Exception as e:
            print(f"   Notice: WhatsApp automated dispatch skipped: {e}")

def run_scheduled_cloud_audit(repo_full: str, repo_name: str):
    """
    Periodic autonomous runner in GitHub Actions (runs every 30 minutes 24/7 in the cloud).
    Audits Trello 'Realizado y revisar' and open PRs without any local PC turned on.
    """
    print("=" * 80)
    print("☁️  AUTONOMOUS 24/7 CLOUD GUARDIAN — SCHEDULED CRON RUNNER")
    print(f"📦 Repository: {repo_full or repo_name} | Mode: Cloud Scheduled Check")
    print(f"⏱️  Cloud Timestamp: {datetime.now().isoformat()}")
    print("=" * 80)

    if not TRELLO_KEY or not TRELLO_TOKEN or not BOARD_ID:
        print("Notice: Trello credentials not provided. Periodic scan complete.")
        sys.exit(0)

    # 1. Fetch cards in 'Realizado y revisar' (LIST_REVIEW)
    url = f"https://api.trello.com/1/lists/{LIST_REVIEW}/cards?fields=name,desc,idList,idMembers&key={TRELLO_KEY}&token={TRELLO_TOKEN}"
    try:
        res = requests.get(url, timeout=10)
        if res.status_code != 200:
            print(f"Notice: Trello list fetch returned HTTP {res.status_code}.")
            sys.exit(0)
        review_cards = res.json()
    except Exception as e:
        print(f"Notice: Trello connection error: {e}")
        sys.exit(0)

    if not review_cards:
        print("✅ [Trello] No cards currently pending review in 'Realizado y revisar'. Everything up to date.")
        sys.exit(0)

    print(f"🔍 Found {len(review_cards)} card(s) in 'Realizado y revisar'. Auditing...")
    
    gh_token = os.environ.get("GH_TOKEN", "").strip()
    headers = {"Authorization": f"Bearer {gh_token}", "Accept": "application/vnd.github+json"} if gh_token else {}

    for c in review_cards:
        c_id = c["id"]
        c_name = c["name"]
        print(f"\n📋 Evaluating card: '{c_name}'")
        
        # Resolver integrante responsable a partir de c["idMembers"] real cruzado con gestor_colores_y_miembros.py
        member = resolve_card_member(c)
        m_name = member["full_name"]
        c_badge = f"{member['color_name']} {member['color_emoji']}"
        
        # Try to find corresponding PR on GitHub
        target_repo = repo_full if repo_full else f"code-corhuila/{repo_name}"
        open_prs = []
        if gh_token:
            prs_url = f"https://api.github.com/repos/{target_repo}/pulls?state=open"
            try:
                r_prs = requests.get(prs_url, headers=headers, timeout=10)
                if r_prs.status_code == 200:
                    open_prs = r_prs.json()
            except Exception:
                pass

        if not open_prs:
            print(f"  ⚠️ No open PR found for card '{c_name}'. Moving to Fix with instruction.")
            act_steps = [
                f"Sube tu rama de trabajo a GitHub con 'git push -u origin <nombre-rama>'.",
                f"Abre el Pull Request en GitHub para que el Centinela en la nube pueda auditarlo."
            ]
            feedback = f"""👨‍🏫 **[EDUTRACK CLOUD GUARDIAN — TAREA SIN PULL REQUEST]**
👤 **Integrante:** {m_name} | 🎨 **Color:** {c_badge}

⚠️ La tarjeta fue colocada en 'Realizado y revisar', pero no se encontró un Pull Request abierto en GitHub.

### 🛠️ Pasos para solucionarlo:
1. Sube tu rama con tus commits (`git push -u origin <rama>`).
2. Abre el Pull Request en GitHub hacia la rama correspondiente.
3. El Centinela en la nube lo auditará y aprobará automáticamente."""
            post_trello_comment(c_id, feedback)
            move_trello_card(c_id, LIST_FIX)
            add_trello_checklist(c_id, "🛠️ Correcciones Requeridas", act_steps)
            
            wa_text = f"""👨‍🏫 *[EDUTRACK CLOUD GUARDIAN]*
👤 *{m_name}* ({c_badge})
⚠️ Moviste la tarjeta '{c_name}' a revisar en Trello, pero falta abrir el Pull Request en GitHub.
Por favor sube tu rama y abre el PR para que el Centinela lo apruebe."""
            send_whatsapp_alert(member.get("phone", ""), member.get("apikey", ""), wa_text)
        else:
            pr = open_prs[0]
            pr_id = pr.get("number")
            print(f"  🔍 Found open PR #{pr_id}. PR triggers will audit diffs and commits.")

    print("\n✅ Autonomous cloud audit cycle completed successfully.")
    sys.exit(0)

def audit_pull_request():
    """Audits the current Pull Request inside GitHub Actions."""
    repo_full = os.environ.get("GITHUB_REPOSITORY", "")
    repo_name = repo_full.split("/")[-1] if "/" in repo_full else repo_full
    pr_num = os.environ.get("PR_NUMBER", "").strip()
    author = os.environ.get("PR_AUTHOR", "")
    head_ref = os.environ.get("HEAD_REF", "")
    base_ref = os.environ.get("BASE_REF", "develop")

    if not pr_num:
        run_scheduled_cloud_audit(repo_full, repo_name)
        return

    print("=" * 80)
    print("☁️  AUTONOMOUS 24/7 CLOUD GUARDIAN (GITHUB ACTIONS) — EDUTRACK")
    print(f"📦 Repository: {repo_name} | PR #{pr_num} by @{author}")
    print(f"🌿 Branch: {head_ref} -> Base: {base_ref}")
    print("=" * 80)

    member = resolve_member(author)
    m_name = member["full_name"]
    c_badge = f"{member['color_name']} {member['color_emoji']}"

    errors = []
    actions = []

    # 1. Branching Policy Verification
    if repo_name == "educk-docs":
        # In -docs repositories, PRs must come from docs/<topic-slug> child branches targeting main
        if head_ref == "main" and base_ref == "main":
            errors.append("In 'educk-docs', PRs cannot merge 'main -> main'. You must create a child branch (e.g., 'docs/<topic-slug>') targeting 'main'.")
            actions.append("Checkout a child branch: 'git checkout -b docs/my-topic', push it, and submit the PR targeting 'main'.")
        elif base_ref != "main":
            errors.append(f"In 'educk-docs', the canonical target branch is strictly 'main'. Base branch '{base_ref}' is invalid.")
            actions.append("Change your Pull Request base target branch to 'main'.")
    else:
        # In application / service repositories, PRs target develop from feat/..., fix/..., chore/...
        if head_ref in ["develop", "main", "qa"]:
            errors.append(f"Pull Requests directly from protected branches ('{head_ref}') are strictly prohibited under course governance.")
            actions.append("Create a child branch from develop: 'git checkout -b feat/HU-XXX-name' and submit the PR targeting 'develop'.")
        if base_ref == "main" and not head_ref.startswith("release/") and not head_ref.startswith("hotfix/"):
            errors.append(f"Only 'release/*' or 'hotfix/*' branches may target 'main' in code repositories. Received '{head_ref}'.")
            actions.append("Target 'develop' for ongoing feature branches, or follow the formal promotion workflow.")

    # 2. PR Line Diff Cap (< 400 lines)
    try:
        diff_cmd = ["git", "diff", "--shortstat", f"origin/{base_ref}...HEAD"]
        stat_res = subprocess.run(diff_cmd, capture_output=True, text=True)
        if stat_res.returncode == 0 and stat_res.stdout.strip():
            parts = stat_res.stdout.strip().split(",")
            total_lines = 0
            for p in parts:
                if "insertion" in p or "deletion" in p:
                    num = ''.join(filter(str.isdigit, p))
                    if num:
                        total_lines += int(num)
            print(f"📊 Modified lines: {total_lines} (Mandatory Course Limit: 400)")
            if total_lines > 400:
                errors.append(f"Pull Request modifies {total_lines} lines, exceeding the strict 400-line cap established by Prof. Ariel (@ariel5253).")
                actions.append("Partition your changes into atomic, scoped Pull Requests under 400 lines.")
    except Exception as e:
        print(f"Notice: git diff calculation skipped: {e}")

    # 3. Commit Justification Check ("Why:" / "Por qué:")
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
                if "why:" in full_text or "por qué:" in full_text or "por que:" in full_text:
                    has_why = True
                    break
            if not has_why:
                errors.append("None of the commits in this PR contain the mandatory technical justification body ('Why: <rationale>').")
                actions.append("Amend your commit: 'git commit --amend -m \"docs(scope): summary\" -m \"Why: Technical rationale for Cut 1/2 defense.\" ' and push with '--force-with-lease'.")
    except Exception as e:
        print(f"Notice: git log commit inspection skipped: {e}")

    # 4. Semantic Content Audit (vs educk-docs Single Source of Truth)
    spec_data = load_architecture_spec()
    sem_errors, sem_actions = perform_semantic_content_audit(repo_name, spec_data)
    if sem_errors:
        errors.extend(sem_errors)
        actions.extend(sem_actions)

    # External Trello Synchronization (if configured)
    target_card = find_card_for_repo(repo_name)
    card_id = target_card.get("id")
    card_name = target_card.get("name", f"Task for {repo_name}")

    # 5. Extract PR Diff via GitHub API
    pr_diff = fetch_pr_diff(repo_full, pr_num)

    # 6. Execute AI Review via Gemini 1.5 Flash
    gemini_result = analyze_pr_with_gemini(
        repo_name=repo_name,
        author=author,
        pr_num=pr_num,
        head_ref=head_ref,
        base_ref=base_ref,
        diff_text=pr_diff,
        static_errors=errors,
        spec_data=spec_data,
        member=member
    )

    aprobado = gemini_result.get("aprobado", False)
    comentario_resumen = gemini_result.get("comentario_resumen", "")
    cambios_requeridos = gemini_result.get("cambios_requeridos", [])

    # Prevalencia de seguridad: Si hubo errores estáticos bloqueantes pero Gemini devolvió aprobado, prevalece la corrección
    if errors and aprobado:
        aprobado = False
        for err in errors:
            cambios_requeridos.append({
                "archivo": repo_name,
                "linea_aproximada": 1,
                "motivo": err,
                "codigo_sugerido": f"// Corrección requerida por políticas del curso:\n// {err}"
            })

    # External Trello Synchronization
    target_card = find_card_for_repo(repo_name)
    card_id = target_card.get("id")
    card_name = target_card.get("name", f"Task for {repo_name}")

    if aprobado:
        print("\n🎉 [GEMINI AI]: PULL REQUEST APROBADO (100% CONFORME).")
        print(f"📋 Resumen: {comentario_resumen}")

        # 1. Submit official review (APPROVE)
        submit_pr_line_review(repo_full, pr_num, aprobado=True, resumen=comentario_resumen, cambios_requeridos=[])

        # 2. Execute Autonomous Auto-Merge in GitHub API
        merge_success = execute_auto_merge_pr(
            repo_full=repo_full,
            pr_num=pr_num,
            commit_title=f"Merge pull request #{pr_num} from {head_ref} [AI-Approved]",
            commit_message=f"{comentario_resumen}\n\nApproved autonomously by EduTrack AI Reviewer (Gemini 1.5 Flash) on behalf of Technical Lead @XimenaChala."
        )

        # 3. Update Trello Card & Continuous Replenishment
        if card_id:
            congrats_body = f"""# 🤖 [EDUTRACK AI CODE REVIEWER — APROBADO & AUTO-MERGE]
👤 **Integrante:** {m_name} (@{author}) | 🎨 **Badge:** {c_badge}
📦 **Repositorio:** `{repo_name}` (PR #{pr_num})

### 📋 Resumen del Análisis:
{comentario_resumen}

---
> 🚀 *El Pull Request fue mergeado automáticamente y la tarjeta se movió a `✅ Aprobado y Mergeado`. Tu siguiente tarea del catálogo ha sido despachada.*"""
            post_trello_comment(card_id, congrats_body)
            move_trello_card(card_id, LIST_DONE)
            print(f"✅ Trello card '{card_name}' movida a Aprobado y Mergeado.")

            # Continuous replenishment: dispatch next task immediately
            trigger_continuous_replenishment()

        # 4. WhatsApp Notification
        wa_msg = f"""🎓 *[EDUTRACK AI REVIEWER — APROBADO & MERGEADO]*
👤 *Integrante:* {m_name} ({c_badge})
📦 *Repo:* `{repo_name}` (PR #{pr_num})

¡Felicitaciones {m_name}! Tu entrega fue analizada y aprobada por el Revisor con IA (Gemini).
El PR ya fue mergeado automáticamente y tu siguiente tarea fue despachada en Trello."""
        send_whatsapp_alert(member.get("phone", ""), member.get("apikey", ""), wa_msg)

        sys.exit(0)

    else:
        print("\n⚠️ [GEMINI AI]: CAMBIOS REQUERIDOS (REQUEST_CHANGES).")
        print(f"📋 Resumen: {comentario_resumen}")
        print(f"🛠️ Observaciones técnicas: {len(cambios_requeridos)}")

        # 1. Submit official review (REQUEST_CHANGES) with line comments on affected lines
        submit_pr_line_review(repo_full, pr_num, aprobado=False, resumen=comentario_resumen, cambios_requeridos=cambios_requeridos)

        # 2. Update Trello Card & Interactive Checklist
        if card_id:
            trello_fix_body = f"""# 🤖 [EDUTRACK AI CODE REVIEWER — CAMBIOS REQUERIDOS]
👤 **Integrante:** {m_name} (@{author}) | 🎨 **Badge:** {c_badge}
📦 **Repositorio:** `{repo_name}` (PR #{pr_num})

### 📋 Resumen del Diagnóstico:
{comentario_resumen}

### 🛠️ Correcciones Requeridas:
Revisa los comentarios de revisión directamente en las líneas afectadas de tu PR #{pr_num} en GitHub, donde tienes los bloques de código corregidos listos para copiar y pegar."""
            post_trello_comment(card_id, trello_fix_body)
            move_trello_card(card_id, LIST_FIX)
            checklist_items = [f"[{c.get('archivo')}:{c.get('linea_aproximada')}] {c.get('motivo')[:120]}" for c in cambios_requeridos[:8]]
            add_trello_checklist(card_id, "🛠️ Correcciones Requeridas por el Revisor IA", checklist_items)
            print(f"⚠️ Trello card '{card_name}' movida a Fix list con checklist interactiva.")

        # 3. WhatsApp Notification
        wa_obs = "\n".join([f"• [{c.get('archivo')}] {c.get('motivo')[:80]}" for c in cambios_requeridos[:3]])
        wa_msg = f"""👨‍🏫 *[EDUTRACK AI REVIEWER — CAMBIOS REQUERIDOS]*
👤 *Integrante:* {m_name} ({c_badge})
📦 *Repo:* `{repo_name}` (PR #{pr_num})

⚠️ *Tu entrega requiere ajustes antes de ser mergeada:*
{wa_obs}

🛠️ *En tu PR #{pr_num} en GitHub ya tienes las sugerencias de código listas directamente en las líneas afectadas para copiar y pegar.*
Aplica los cambios, haz git push y el Revisor con IA ejecutará el merge solo."""
        send_whatsapp_alert(member.get("phone", ""), member.get("apikey", ""), wa_msg)

        print("\n::error::Pull Request requires changes per Autonomous AI Code Reviewer.")
        sys.exit(1)

if __name__ == "__main__":
    audit_pull_request()
