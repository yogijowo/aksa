# Contributing to AKSA (`CONTRIBUTING.md`)

Thank you for contributing to **AKSA** (*Asisten Kerja & Sistem Automasi*).

## 1. Golden Engineering Rules

1. **Language Split Rule:**
   - **Code, Identifiers, Comments, Commit Messages, and Technical Docs:** Must be written in **English**.
   - **User-Facing Application UI, Error Messages, Toast Notifications, and Prompts:** Must be written in **natural, polite, modern Bahasa Indonesia**.
2. **Security & Deny-by-Default:**
   - All tools and actions must pass through `ExecutionPolicyGateway`.
   - Never add public override flags (`execution_policy_override`, `skip_approval`, `is_admin`).
   - Never store plaintext API keys or tokens in SQLite, logs, or frontend localStorage; always use `CredentialVault`.
   - Never implement silent fallback from local models (`Ollama` / `LM Studio`) to cloud providers.
3. **No Static / Emoji Icons in UI:**
   - Never use static Unicode emojis in React components; always use vector icons from `lucide-react`.

## 2. Change Management Workflow (Section 23)

1. Open an issue with a narrow, well-defined scope.
2. Write reproduction or acceptance tests first.
3. Implement one domain at a time.
4. Review security impact and database schema migrations (`schema_migrations`).
5. Run local backend and frontend verification:
   ```bash
   npm run test:backend
   npm run test:frontend
   ```
6. Update `PROGRESS.md` using disciplined status values (`NOT_STARTED`, `IN_PROGRESS`, `IMPLEMENTED`, `TESTED`, `VERIFIED_WINDOWS`, `VERIFIED_MACOS`, `RELEASED`).
7. Submit a Pull Request using `.github/PULL_REQUEST_TEMPLATE.md`.
