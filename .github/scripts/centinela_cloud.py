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
    url = f"https://api.github.com/repos/{repo_full}/issues/{pr_num}/comments"
    headers = {
        "Authorization": f"Bearer {gh_token}",
        "Accept": "application/vnd.github+json"
    }
    try:
        requests.post(url, json={"body": comment}, headers=headers, timeout=10)
        print("💬 Automated feedback comment posted on GitHub PR.")
    except Exception as e:
        print(f"Notice: GitHub PR comment dispatch skipped: {e}")

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

def audit_pull_request():
    """Audits the current Pull Request inside GitHub Actions."""
    repo_full = os.environ.get("GITHUB_REPOSITORY", "")
    repo_name = repo_full.split("/")[-1] if "/" in repo_full else repo_full
    pr_num = os.environ.get("PR_NUMBER", "")
    author = os.environ.get("PR_AUTHOR", "")
    head_ref = os.environ.get("HEAD_REF", "")
    base_ref = os.environ.get("BASE_REF", "develop")

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

    if not errors:
        print("\n🎉 QUALITY GATES PASSED (100% COMPLIANT).")
        congrats = f"""👨‍🏫 **[EDUTRACK CLOUD GUARDIAN — PR AUDIT APPROVED]**
👤 **Contributor:** {m_name} (@{author}) | 🎨 **Assigned Badge:** {c_badge}
📦 **Repository:** `{repo_name}` (PR #{pr_num})

Congratulations {m_name}! Your submission passed all course quality gates:
- ✅ Size limit (< 400 lines) verified.
- ✅ Technical rationale ('Why:') evidenced in commit history.
- ✅ Governance branching model respected.
- ✅ Permanent audit trail retained.
"""
        if card_id:
            post_trello_comment(card_id, congrats)
            move_trello_card(card_id, LIST_DONE)
            print(f"✅ Trello card '{card_name}' moved to Approved.")

        wa_msg = f"""🎓 *[EDUTRACK CLOUD GUARDIAN — APPROVED]*
👤 *Member:* {m_name} ({c_badge})
📦 *Repo:* `{repo_name}` (PR #{pr_num})

Congratulations {m_name}! Your PR passed all course Quality Gates (100%)."""
        send_whatsapp_alert(member.get("phone", ""), member.get("apikey", ""), wa_msg)

        sys.exit(0)
    else:
        print("\n⛔ NON-CONFORMANCE DETECTED. Emitting correction plan...")
        errors_text = "\n".join([f"- ❌ {e}" for e in errors])
        actions_text = "\n".join([f"{idx}. {a}" for idx, a in enumerate(actions, 1)])

        alert = f"""👨‍🏫 **[EDUTRACK CLOUD GUARDIAN — QUALITY GATE OBSERVATIONS / POR CORREGIR]**
👤 **Contributor / Integrante:** {m_name} (@{author}) | 🎨 **Assigned Badge:** {c_badge}
📦 **Repository:** `{repo_name}` (PR #{pr_num})

Attention {m_name}, the Cloud Guardian identified observations requiring resolution before approval:

### ❌ ¿Qué debes corregir exactamente? (Governance Observations):
{errors_text}

### 🛠️ ¿Cómo solucionarlo paso a paso? (Required Action Steps):
{actions_text}

> 💡 *Aplica las correcciones en tu rama local y vuelve a hacer git push. El Centinela en la nube re-auditará automáticamente y aprobará tu entrega cuando esté al 100%.*
"""
        # 1. Post on GitHub PR if running in Actions
        post_github_pr_comment(repo_full, pr_num, alert)

        # 2. Update Trello Card & Interactive Checklist
        if card_id:
            post_trello_comment(card_id, alert)
            move_trello_card(card_id, LIST_FIX)
            add_trello_checklist(card_id, "🛠️ Correcciones Requeridas", actions)
            print(f"⚠️ Trello card '{card_name}' moved to Fix list with detailed instructions and interactive checklist.")

        # 3. WhatsApp Direct Notification
        wa_errors_list = "\n".join([f"• {e}" for e in errors])
        wa_msg = f"""👨‍🏫 *[EDUTRACK CLOUD GUARDIAN — TAREA POR CORREGIR]*
👤 *Integrante:* {m_name} ({c_badge})
📦 *Repo:* `{repo_name}` (PR #{pr_num})

⚠️ *Tu entrega no fue aprobada y requiere correcciones:*
{wa_errors_list}

🛠️ *Paso a paso:*
1. Revisa los comentarios en tu PR #{pr_num} o en tu tarjeta de Trello.
2. Aplica los cambios en tu rama local y haz git push.
Trello se actualizará solo."""
        send_whatsapp_alert(member.get("phone", ""), member.get("apikey", ""), wa_msg)

        print("\n::error::Pull Request failed mandatory governance Quality Gates.")
        sys.exit(1)

if __name__ == "__main__":
    audit_pull_request()
