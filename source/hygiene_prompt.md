# Fas 4: Repo Hygien för Rocket

## Mål
Förbättra kodhygien i Rocket-repon:
1. **Code style/lint** — flake8/ruff konfiguration och körning
2. **Dokumentation** — README.md, konventioner
3. **Kodstruktur** — identifiera och fixa uppenbara hygienproblem
4. **Dependencies** — se till requirements.txt är ren och uppdaterad
5. **Git hygiene** — .gitignore, commit-praktiker

## Steg
1. Kör flake8/ruff över `rocket/` katalogen och rapportera resultat
2. Skapa `.flake8` eller `ruff.toml` med projekt-specifika konfigurationer
3. Kontrollera README.md — skapa om saknas
4. Kontrollera kodstruktur — identifiera stora filer (>200 lines) och uppenbara problem
5. Commit alla ändringar till `security-hardening`-branchen

## Betydelse
- Gör koden lättare att underhålla
- Säkerställer att nya bidrag håller samma standard
- Bygger grund för framtida fas 5-7
