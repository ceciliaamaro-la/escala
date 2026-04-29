# Sistema de Escala Militar (Django)

Django 6.0 application for managing military duty rosters ("escalas") across multiple military organizations (OMs). Includes models for users, military personnel, organizational units, ranks, specialties, calendars, schedules and a "Quadrinho" balancing system that distributes services fairly.

## Stack

- Python 3.12 + Django 6.0 (`.pythonlibs/` virtualenv managed by `uv`)
- SQLite database (`db.sqlite3`)
- Gunicorn for production
- Single Django app: `escalas`
- Project package: `core` (settings, urls, wsgi)

## Layout

- `core/` — Django project (settings, urls, wsgi, asgi)
- `escalas/` — main app (models, admin, views, forms, signals, migrations)
- `files/` — original delivery docs (PT-BR README, usage examples)
- `manage.py` — Django entry point
- `db.sqlite3` — SQLite database (committed; contains seeded admin user)

## Routes

- `/` → redirects to `/admin/`
- `/admin/` → Django admin (only configured UI). The PT-BR views in `escalas/views.py` exist but are not wired into URLs and reference templates that aren't included.

## Replit configuration

- Workflow `Start application`: `python manage.py runserver 0.0.0.0:5000` (port 5000, webview).
- `core/settings.py`:
  - `ALLOWED_HOSTS = ['*']` (required so the proxied Replit preview can reach the dev server).
  - `CSRF_TRUSTED_ORIGINS` includes `*.replit.dev`, `*.replit.app`, `*.repl.co` and the kirk/picard subdomains.
- Deployment: VM target running migrations then gunicorn on port 5000.

## Notes / known issues

- `AUTH_USER_MODEL` is **not** set even though `escalas.UsuarioCustomizado` extends `AbstractUser`. The initial migration uses a hard FK to `escalas.usuariocustomizado` instead of the swappable user reference, so changing `AUTH_USER_MODEL` later would require a fresh migration. For now `auth.User` remains the active auth model and the custom user table coexists.
- The non-admin views (`escalas/views.py`) call methods like `request.user.pode_administrar()` that only exist on `UsuarioCustomizado`. They will not work until `AUTH_USER_MODEL` is wired up and matching templates are added.
- SQLite is fine for the dev workflow but in a VM deployment writes live on the deployment disk; consider migrating to Postgres for multi-instance/long-term use.
