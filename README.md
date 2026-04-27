# Dinamica

Projeto consolidado em stack Python:

- `Flet` para a interface Web, Desktop e Mobile
- `FastAPI` para API e integracoes externas
- `SQLAlchemy + PostgreSQL` para persistencia
- `Pandas` para analytics
- `Google GenAI (Python SDK)` para IA no fluxo Python

## O que mudou

- A interface antiga em `React + Tailwind + Recharts + Lucide` foi removida da raiz.
- O stack legado foi removido para evitar conflito de watchers e processos locais.
- O layout operacional foi recriado no [flet_app.py](/c:/Users/dinam/OneDrive/Documentos/GitHub/Dinamica/flet_app.py).

## Rodar localmente

Pre-requisitos:

- Python 3.11+
- PostgreSQL ativo em `localhost`

Passos:

1. Instale as dependencias:
   `pip install -r requirements.txt`
2. Crie um `.env` a partir de `.env.example`
3. Ajuste `DATABASE_URL` para sua instancia Postgres local
4. Inicie o projeto:
   `python app.py`

Endpoints locais:

- API FastAPI: `http://127.0.0.1:8000`
- App Flet: `http://127.0.0.1:8550`

Credencial inicial:

- Email: `admin@dinamica.com`
- Senha: `admin`
