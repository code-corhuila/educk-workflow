## Pull Request — Team G1 (EduTrack / educk)

> **Regla de oro del curso:** Todo PR debe tener un diff menor a **400 líneas**, respetar la convención `<abbr>-<domain>-<piece>` y tener pruebas verdes.

### 1. Información General
- **Historia de Usuario / Tarea:** HU-___
- **Tipo de Cambio:**
  - [ ] `feat`: Nueva funcionalidad
  - [ ] `fix`: Corrección de error / bugfix
  - [ ] `test`: Nuevas pruebas unitarias o de integración
  - [ ] `refactor`: Refactorización de código sin cambio de comportamiento
  - [ ] `docs`: Actualización de documentación o contratos
  - [ ] `chore`: Configuración, Docker, dependencias

### 2. Resumen del Cambio
<!-- Explica brevemente qué hiciste y por qué -->

---

### 3. Lista de Verificación Obligatoria (Quality Gates)
*Marca cada casilla con [x]. Todos los puntos son obligatorios para que tu PR sea aprobado:*

- [ ] **Límite de Tamaño:** El diff del PR es estrictamente menor a **400 líneas de código**.
- [ ] **Ramas Correctas:** El PR viene de una rama hija (`feat/HU-XXX-...`, `fix/...`, `docs/...`) hacia `develop`. (Prohibido hacer push directo).
- [ ] **Conventional Commits:** Todos los mensajes de commit están en inglés y siguen el formato `type(scope): description`.
- [ ] **Cero Secretos:** No se subieron contraseñas, tokens ni archivos `.env` con credenciales reales.
- [ ] **Pruebas Automatizadas:** El código compila y las pruebas unitarias pasan 100% en verde (`mvn test` / `npm test`).
- [ ] **Arquitectura Hexagonal (Backend):** La capa `domain/` es Java puro (cero `import` de Spring, JPA o SQL).
- [ ] **Soberanía de Base de Datos (ADR-003):** Ningún script DDL ni migración está dentro del backend. Cero claves foráneas físicas cross-database.
- [ ] **Docker & Nombres:** Contenedores usan `<abbr>-<domain>-<piece>` y la API espera salud real (`condition: service_healthy` con `pg_isready`).
- [ ] **Documentación en Inglés (ADR-001):** Comentarios, nombres y documentación técnica están en inglés.

