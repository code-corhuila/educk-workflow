# educk-workflow — Governance & Autonomous CI/CD Suite

> Core business workflow orchestration, governance quality gates, continuous Trello dispatcher, and AI-powered code review for EduTrack.

Part of the **EduTrack** distributed system — Team G1, Sistemas Distribuidos 2026-B.  
Technical Lead: **@XimenaChala**  
Standard Compliance: **ADR-001** (English Documentation & Tooling), **ADR-003** (Database per Service).

---

## 🚀 Key Modules & Autonomous Systems

### 1. Autonomous AI Code Reviewer (`centinela_cloud.py`)
- **Engine:** Google Gemini (`gemini-3.6-flash` with resilient multi-tier fallback).
- **Quality Gates:**
  - Evaluates architectural integrity (Database per Service isolation, Hexagonal layers).
  - Validates PR line boundaries (< 400 lines) and Conventional Commit compliance (`Why:` rationale).
  - Inspects code syntax, potential unhandled runtime exceptions, and security vulnerabilities.
- **Autonomous Decisions:**
  - **Approval:** Triggers automated squash merge via GitHub REST API, submits `APPROVE` review, advances Trello card to Done, and notifies developer.
  - **Change Requests:** Blocks merge, emits formal `REQUEST_CHANGES` review with actionable inline diff suggestions (` ```suggestion `), moves Trello card to Revision, and generates corrective checklist.

### 2. Continuous Flow Dispatcher & Safety Locks (`despachador_flujo_continuo_trello.py`)
- **Anti-Spam Guard:** Performs pre-flight `GET` requests against target list cards to eliminate duplicate task creation.
- **Anti-Block Dependency Bypass:** Automatically ignores cards tagged with `'Bloqueado'` / `'Blocked'` from active WIP counting, ensuring developers receive executable work without blocking queues.
- **Continuous Card Replenishment:** Maintains a minimum buffer of active tasks per team member as previous work completes.

### 3. Multi-Repository 24/7 CI/CD (`centinela-cloud.yml`)
- Scheduled and event-driven workflow executing on GitHub-hosted runners 24/7.
- Operates independently even when local workstations are offline.

---

## 🔐 GitHub Secrets & Permissions Configuration

To enable the autonomous cloud guardian across repositories:

### Required Secrets (`Settings -> Secrets and variables -> Actions`):
- `GEMINI_API_KEY`: Google AI Studio API key for PR diff analysis.
- `TRELLO_KEY`: Developer API Key for Trello integration.
- `TRELLO_TOKEN`: Server Token for Trello card synchronization.
- `TRELLO_BOARD_ID`: Unique board identifier (`6aaef11b808b8de50ad9237e`).

### Workflow Permissions (`Settings -> Actions -> General`):
- **Workflow permissions:** `Read and write permissions`.
- **PR Approvals:** Check *Allow GitHub Actions to create and approve pull requests*.

---

## 🌿 Branching Policy

Permanent branches: `develop`, `qa`, `main`.  
**Direct commits are strictly prohibited.** All changes must enter through a child branch and merge via Pull Request.

```text
develop  <--PR--  feat/... fix/... chore/...
qa       <--PR--  qa/... (cherry-pick -x)
main     <--PR--  release/... hotfix/...
```
