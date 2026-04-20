# Project Commands, Rules & Preferences

CCE lets you define per-project rules, preferences, and commands that Claude follows automatically every session. These are stored in `.cce/commands.yaml` and loaded into Claude's context at session start.

---

## Quick Start

```bash
cd ~/my-project
cce commands add-rule 'Never generate down() in migrations'
cce commands set-pref database PostgreSQL
cce commands add before_push 'composer test'
cce commands list
```

---

## File Format

`.cce/commands.yaml`:

```yaml
rules:
  - NEVER generate down() in migrations — forward-only
  - Use UUID for primary keys
  - All API responses must use JsonResource classes

preferences:
  database: PostgreSQL
  auth: Sanctum
  queue: Redis
  style: Clean architecture, no god classes

before_push:
  - php artisan test --parallel
  - phpstan analyse --level=8

before_commit:
  - php-cs-fixer fix --dry-run

on_start:
  - echo "Deploy window: Tue/Thu only"

custom:
  deploy: kubectl apply -f k8s/production/
  seed: php artisan db:seed --class=TestDataSeeder
  migrate: php artisan migrate --force
```

---

## Sections Explained

### rules

Hard rules Claude **must** follow. These appear prominently in the init prompt.

```yaml
rules:
  - Never use raw SQL queries — always use Eloquent
  - All new endpoints must have request validation
  - Use strict_types in every PHP file
```

### preferences

Key-value pairs describing how Claude should approach the project.

```yaml
preferences:
  language: PHP
  framework: Laravel
  database: PostgreSQL
  auth: Sanctum
  frontend: Livewire
  naming: Models singular, tables plural
  style: Clean architecture, no god classes
```

### before_push

Commands Claude runs before any `git push`. Use for tests, linting, static analysis.

```yaml
before_push:
  - composer test
  - phpstan analyse --level=8
  - npm run build
```

### before_commit

Commands Claude runs before any `git commit`. Use for formatting, quick checks.

```yaml
before_commit:
  - php-cs-fixer fix --dry-run
  - npm run lint
```

### on_start

Messages shown at the beginning of every Claude session. Use for reminders.

```yaml
on_start:
  - echo "Deploy freeze until Friday"
  - echo "PR required for staging branch"
```

### custom

Named commands Claude can run when you ask for them by name.

```yaml
custom:
  deploy: kubectl apply -f k8s/production/
  seed: php artisan db:seed --class=TestDataSeeder
  migrate: php artisan migrate --force
  logs: kubectl logs -f deployment/api --tail=100
```

---

## Workspace Support

For multi-project workspaces (e.g. `~/sonin` with many projects inside), you can define shared rules at the workspace level.

### Directory structure

```
~/sonin/
  ├── .cce/commands.yaml           ← Workspace config (shared)
  ├── project-a/.cce/commands.yaml ← Project A config
  └── project-b/.cce/commands.yaml ← Project B config
```

### Workspace config (optional)

`~/sonin/.cce/commands.yaml`:

```yaml
rules:
  - Follow PSR-12 coding standard
  - Always use strict types in PHP files

preferences:
  language: PHP
  framework: Laravel
  testing: PHPUnit

before_push:
  - echo "Global: run tests first"
```

### Project config

`~/sonin/project-a/.cce/commands.yaml`:

```yaml
rules:
  - NEVER generate down() in migrations — forward-only
  - Use UUID for primary keys

preferences:
  database: PostgreSQL
  auth: Sanctum

before_push:
  - php artisan test --parallel
  - phpstan analyse --level=8
```

`~/sonin/project-b/.cce/commands.yaml`:

```yaml
rules:
  - Always include down() in migrations for rollback

preferences:
  database: MySQL
  frontend: Livewire

before_push:
  - npm test
```

### Merge behavior

When Claude starts a session in `~/sonin/project-a`, CCE merges workspace + project configs:

| Section | Merge strategy |
|---------|---------------|
| `rules` | Workspace + project appended, duplicates removed |
| `preferences` | Merged — project values override workspace on conflict |
| `before_push` | Workspace + project appended, duplicates removed |
| `before_commit` | Same as above |
| `on_start` | Same as above |
| `custom` | Merged — project commands override workspace on conflict |

**Example merged result for project-a:**

```
Rules:
  → Follow PSR-12 coding standard          ← workspace
  → Always use strict types in PHP files    ← workspace
  → NEVER generate down() in migrations     ← project
  → Use UUID for primary keys               ← project

Preferences:
  language: PHP            ← workspace
  framework: Laravel       ← workspace
  testing: PHPUnit         ← workspace
  database: PostgreSQL     ← project (added)
  auth: Sanctum            ← project (added)

Before push:
  $ echo "Global: run tests first"      ← workspace
  $ php artisan test --parallel          ← project
  $ phpstan analyse --level=8            ← project
```

**Workspace config is optional.** Projects work standalone without it.

---

## CLI Commands

### Add rules and preferences

```bash
cce commands add-rule 'Never use raw SQL'
cce commands set-pref database PostgreSQL
cce commands set-pref auth Sanctum
```

### Add commands to hooks

```bash
cce commands add before_push 'composer test'
cce commands add before_commit 'php-cs-fixer fix --dry-run'
cce commands add on_start 'echo Deploy freeze until Friday'
```

### Add custom named commands

```bash
cce commands add-custom deploy 'kubectl apply -f k8s/'
cce commands add-custom migrate 'php artisan migrate --force'
```

### List all (merged with workspace)

```bash
cce commands list
```

### Remove

```bash
cce commands remove before_push 'composer test'
cce commands remove-rule 'Never use raw SQL'
cce commands remove-pref database
cce commands remove custom deploy
```

---

## What Claude Sees

At session start, CCE injects the merged config into Claude's context:

```
### Project Rules
- Follow PSR-12 coding standard
- NEVER generate down() in migrations — forward-only
- Use UUID for primary keys

### Project Preferences
- database: PostgreSQL
- auth: Sanctum
- style: Clean architecture

### Project Commands
- Before push: `php artisan test --parallel`, `phpstan analyse --level=8`
- Before commit: `php-cs-fixer fix --dry-run`
- Custom commands:
  - deploy: `kubectl apply -f k8s/production/`
```

Claude follows these automatically — no need to remind it each session.

---

## Gitignore

`cce init` automatically adds `.cce/` to `.gitignore`. Project commands are local configuration and should not be committed to the repository (different team members may have different preferences).

If you want to share commands across the team, commit the workspace-level `.cce/commands.yaml` instead.
