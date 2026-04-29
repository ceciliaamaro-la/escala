# Sistema de Escala Militar (Django)

Aplicação Django 6.0 para gestão de escalas militares da **FAB (Força Aérea Brasileira)**. Opera em modo **multi-OM**: o usuário escolhe a OM ativa via dropdown na navbar (`/om/trocar/`) e todas as listagens/cadastros ficam escopadas àquela OM (lida da sessão em `escalas/context_processors.py::om_context`). Inclui modelos para usuários, militares, divisões, postos, especialidades, calendário, escalas e o sistema "Quadrinho" de balanceamento.

## Stack

- Python 3.12 + Django 6.0 (`.pythonlibs/` gerenciado por `uv`)
- SQLite (`db.sqlite3`)
- Bootstrap 5.3 + Bootstrap Icons + fonte Cinzel (CDN)
- Gunicorn em produção
- App único: `escalas` ; pacote do projeto: `core`

## Layout

- `core/` — projeto Django (settings, urls, wsgi, asgi)
- `escalas/`
  - `models.py` — domínio completo
  - `views.py` — dashboard + cadastros (atual)
  - `views_escala_legado.py` — views antigas de escala (a integrar)
  - `forms_cadastro.py` — ModelForms com BootstrapFormMixin
  - `urls.py` — rotas dos cadastros
  - `management/commands/seed_dados.py` — popula dados de exemplo
- `templates/`
  - `base.html` — layout principal (navbar, footer, mensagens)
  - `registration/login.html`
  - `dashboard.html`
  - `cadastro/` — telas de OM, postos, especialidades, divisões e militares
- `escalas/context_processors.py` — `om_context` injeta `om_ativa` e `oms_disponiveis` em todos os templates
- `static/css/militar.css` — tema visual FAB (azul #003a78, amarelo #ffd200)
- `db.sqlite3` — SQLite versionado
- `media/oms/logos/` — uploads dos brasões/logos das OMs (servido em `/media/` no DEBUG; ignorado pelo git)

## Rotas

Públicas:
- `/login/`, `/logout/`

Autenticadas (login obrigatório):
- `/` — Painel
- `/organizacao/` e `/organizacao/editar/`
- `/postos/`, `/postos/novo/`, `/postos/<id>/editar|excluir/`
- `/especialidades/`, idem
- `/divisoes/`, idem
- `/militares/` (com filtros `q`, `divisao`, `posto`), `/militares/novo/`, `/militares/<id>/`, `/militares/<id>/editar|excluir/`
- `/admin/` — Django admin

## Configuração Replit

- Workflow `Start application`: `.pythonlibs/bin/python manage.py runserver 0.0.0.0:5000`
- `core/settings.py`:
  - `AUTH_USER_MODEL = 'escalas.UsuarioCustomizado'`
  - `ALLOWED_HOSTS = ['*']` e `CSRF_TRUSTED_ORIGINS` para domínios `*.replit.dev`, `*.replit.app`, `*.repl.co`, `*.kirk.replit.dev`, `*.picard.replit.dev`
  - `LANGUAGE_CODE='pt-br'`, `TIME_ZONE='America/Sao_Paulo'`
  - `LOGIN_URL='/login/'`, `LOGIN_REDIRECT_URL='/'`, `LOGOUT_REDIRECT_URL='/login/'`
  - `TEMPLATES['DIRS'] = [BASE_DIR/'templates']`
  - `STATICFILES_DIRS = [BASE_DIR/'static']`
- Deployment alvo: VM (migrações + gunicorn na porta 5000)

## Acesso de testes

- Superusuário: `admin` / `admin123` (perfil `admin_om`, vinculado à OM `1ºBI`)
- Dados de exemplo populados via `python manage.py seed_dados`:
  - 1 OM (`1ºBI — 1º Batalhão de Infantaria`)
  - 13 postos (Sd → Cel)
  - 6 especialidades
  - 4 divisões (DPE, DOP, DLG, DAD)
  - 8 militares
  - 3 tipos de serviço (Preto/Vermelho/Roxo)
  - 365 dias do calendário 2026 (auto)
  - tipos de escala e indisponibilidade

Para repopular do zero: `python manage.py seed_dados --reset`

## Padrões adotados

- **Single-OM**: helper `obter_om_ativa()` em `views.py` retorna a primeira OM ativa; forms ocultam o campo `organizacao_militar` e a view o atribui automaticamente.
- **Soft-delete**: views de exclusão setam `ativo=False` em vez de DELETE, preservando histórico.
- **Busca em militares**: filtros combináveis por nome/matrícula/CPF + divisão + posto.
- **Bootstrap via mixin**: `BootstrapFormMixin` aplica `form-control`/`form-select`/`form-check-input` automaticamente.

## Próximos passos sugeridos

- Reaproveitar `views_escala_legado.py` para reativar geração/visualização de escalas com novo visual.
- Telas de indisponibilidades por militar.
- Tela de calendário (cores Preto/Vermelho/Roxo) com edição manual de feriados.
