from __future__ import annotations

import os
import tempfile
from collections import Counter
from datetime import datetime
from pathlib import Path
from typing import Any

import flet as ft
import requests

from backend.config import API_HOST, API_PORT, BASE_DIR, FLET_HOST, FLET_PORT

API_BASE = f"http://{API_HOST}:{API_PORT}/api"
FLET_TEMP_DIR = Path(BASE_DIR) / ".tmp" / "flet"
FLET_TEMP_DIR.mkdir(parents=True, exist_ok=True)
os.environ["TEMP"] = str(FLET_TEMP_DIR)
os.environ["TMP"] = str(FLET_TEMP_DIR)
tempfile.tempdir = str(FLET_TEMP_DIR)

SURFACE = "#111113"
SURFACE_ALT = "#161618"
SURFACE_SOFT = "#1F1F21"
BORDER = "#FFFFFF14"
TEXT = "#F8FAFC"
TEXT_MUTED = "#9CA3AF"
ACCENT = "#F97316"
ACCENT_SOFT = "#FDBA74"
SUCCESS = "#22C55E"
DANGER = "#EF4444"
WARNING = "#F59E0B"
LOGO_BG_START = "#84CC16"
LOGO_BG_END = "#059669"


def as_currency(value: Any) -> str:
    try:
        amount = float(value or 0)
    except (TypeError, ValueError):
        amount = 0.0
    return f"R$ {amount:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")


def as_date(value: Any) -> str:
    if not value:
        return "-"
    raw = str(value)
    try:
        return datetime.fromisoformat(raw.replace("Z", "+00:00")).strftime("%d/%m/%Y")
    except ValueError:
        return raw[:10]


def status_chip(label: str, color: str) -> ft.Control:
    return ft.Container(
        bgcolor=f"{color}22",
        border=ft.border.all(1, f"{color}55"),
        border_radius=999,
        padding=ft.padding.symmetric(horizontal=10, vertical=6),
        content=ft.Text(label, color=color, size=11, weight=ft.FontWeight.W_600),
    )


def metric_card(title: str, value: str, subtitle: str, tone: str = ACCENT) -> ft.Control:
    return ft.Container(
        bgcolor=SURFACE,
        border=ft.border.all(1, BORDER),
        border_radius=22,
        padding=22,
        content=ft.Column(
            [
                ft.Text(title.upper(), size=11, color=TEXT_MUTED, weight=ft.FontWeight.W_600),
                ft.Text(value, size=28, color=TEXT, weight=ft.FontWeight.BOLD),
                ft.Text(subtitle, size=12, color=tone),
            ],
            spacing=8,
        ),
    )


def section_card(title: str, subtitle: str | None = None, content: ft.Control | None = None) -> ft.Control:
    controls: list[ft.Control] = [
        ft.Text(title, size=20, color=TEXT, weight=ft.FontWeight.BOLD),
    ]
    if subtitle:
        controls.append(ft.Text(subtitle, size=12, color=TEXT_MUTED))
    if content:
        controls.append(content)
    return ft.Container(
        bgcolor=SURFACE,
        border=ft.border.all(1, BORDER),
        border_radius=24,
        padding=22,
        content=ft.Column(controls, spacing=16),
    )


def data_table(title: str, rows: list[dict[str, Any]], columns: list[str], limit: int = 12) -> ft.Control:
    header = ft.Row(
        [ft.Text(title, size=18, color=TEXT, weight=ft.FontWeight.BOLD), status_chip(f"{len(rows)} registros", ACCENT)],
        alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
    )
    if not rows:
        body: ft.Control = ft.Container(
            padding=20,
            border_radius=16,
            bgcolor=SURFACE_ALT,
            content=ft.Text("Nenhum dado disponivel.", color=TEXT_MUTED),
        )
    else:
        body = ft.DataTable(
            bgcolor=SURFACE_ALT,
            border=ft.border.all(1, BORDER),
            heading_row_color="#111113",
            divider_thickness=0.3,
            columns=[ft.DataColumn(ft.Text(column.replace("_", " ").title(), color=TEXT)) for column in columns],
            rows=[
                ft.DataRow(
                    cells=[
                        ft.DataCell(
                            ft.Text(
                                str(row.get(column, "-")),
                                color=TEXT,
                                max_lines=2,
                                overflow=ft.TextOverflow.ELLIPSIS,
                            )
                        )
                        for column in columns
                    ]
                )
                for row in rows[:limit]
            ],
        )
    return ft.Column([header, body], spacing=12)


def trend_list(title: str, items: list[tuple[str, int | float]], tone: str = ACCENT) -> ft.Control:
    maximum = max((float(value) for _, value in items), default=1.0) or 1.0
    return section_card(
        title,
        content=ft.Column(
            [
                ft.Column(
                    [
                        ft.Row(
                            [
                                ft.Text(label, color=TEXT, expand=True),
                                ft.Text(str(value), color=ACCENT_SOFT, weight=ft.FontWeight.BOLD),
                            ],
                            alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
                        ),
                        ft.Container(
                            height=8,
                            bgcolor="#172133",
                            border_radius=999,
                            content=ft.Row(
                                [
                                    ft.Container(
                                        width=max(20, int((float(value) / maximum) * 260)),
                                        height=8,
                                        bgcolor=tone,
                                        border_radius=999,
                                    )
                                ]
                            ),
                        ),
                    ],
                    spacing=6,
                )
                for label, value in items
            ],
            spacing=14,
        ),
    )


class ApiClient:
    def __init__(self) -> None:
        self.token: str | None = None
        self.user: dict[str, Any] | None = None

    def _headers(self) -> dict[str, str]:
        if not self.token:
            return {}
        return {"Authorization": f"Bearer {self.token}"}

    def login(self, email: str, password: str) -> dict[str, Any]:
        response = requests.post(
            f"{API_BASE}/auth/login",
            json={"email": email, "password": password},
            timeout=20,
        )
        response.raise_for_status()
        payload = response.json()
        self.token = payload["access_token"]
        self.user = payload["user"]
        return payload

    def get(self, path: str, params: dict[str, Any] | None = None) -> Any:
        response = requests.get(f"{API_BASE}{path}", headers=self._headers(), params=params, timeout=30)
        response.raise_for_status()
        return response.json()

    def post(self, path: str, payload: dict[str, Any] | None = None) -> Any:
        response = requests.post(
            f"{API_BASE}{path}",
            headers=self._headers(),
            json=payload or {},
            timeout=60,
        )
        response.raise_for_status()
        return response.json()


def main(page: ft.Page) -> None:
    page.title = "Dinâmica Platform"
    page.bgcolor = "#101011"
    page.theme_mode = ft.ThemeMode.DARK
    page.padding = 0
    page.window_width = 1440
    page.window_height = 920
    page.scroll = ft.ScrollMode.AUTO
    page.theme = ft.Theme(color_scheme_seed=ACCENT)

    client = ApiClient()
    state: dict[str, Any] = {
        "active_view": "dashboard",
        "summary": {},
        "bootstrap": {},
        "health": {},
        "sync": {},
        "admin_users": [],
        "directory_users": [],
        "locations": [],
        "sprints": [],
    }

    main_content = ft.Column(spacing=18, expand=True)
    nav_column = ft.Column(spacing=10, width=248)
    mobile_nav = ft.Row(scroll=ft.ScrollMode.AUTO, spacing=8)
    shell = ft.Column(spacing=0, expand=True)

    email_field = ft.TextField(
        hint_text="admin@dinamica.com",
        border=ft.InputBorder.UNDERLINE,
        border_color="#FFFFFF4D",
        focused_border_color=ACCENT,
        color=TEXT,
        hint_style=ft.TextStyle(color="#4B5563"),
        content_padding=ft.padding.symmetric(vertical=10),
        text_size=16,
        bgcolor="transparent",
    )
    password_field = ft.TextField(
        hint_text="admin",
        password=True,
        can_reveal_password=True,
        border=ft.InputBorder.UNDERLINE,
        border_color="#FFFFFF4D",
        focused_border_color=ACCENT,
        color=TEXT,
        hint_style=ft.TextStyle(color="#4B5563"),
        content_padding=ft.padding.symmetric(vertical=10),
        text_size=16,
        bgcolor="transparent",
    )
    login_message = ft.Text(color=DANGER, size=12)

    loading_ring = ft.ProgressRing(width=22, height=22, color=ACCENT, visible=False)
    sync_message = ft.Text(color=TEXT_MUTED, size=12)

    building_dropdown = ft.Dropdown(
        label="Obra do sprint",
        border_radius=16,
        bgcolor=SURFACE_ALT,
        border_color=BORDER,
        color=TEXT,
        options=[],
    )
    sprint_name_field = ft.TextField(
        label="Nome do sprint",
        border_radius=16,
        bgcolor=SURFACE_ALT,
        color=TEXT,
        border_color=BORDER,
    )
    sprint_color_field = ft.TextField(
        label="Cor",
        value="blue",
        border_radius=16,
        bgcolor=SURFACE_ALT,
        color=TEXT,
        border_color=BORDER,
    )
    sprint_feedback = ft.Text(color=TEXT_MUTED, size=12)

    card_sprint_dropdown = ft.Dropdown(
        label="Sprint",
        border_radius=16,
        bgcolor=SURFACE_ALT,
        border_color=BORDER,
        color=TEXT,
        options=[],
    )
    card_title_field = ft.TextField(
        label="Titulo do card",
        border_radius=16,
        bgcolor=SURFACE_ALT,
        color=TEXT,
        border_color=BORDER,
    )
    card_status_dropdown = ft.Dropdown(
        label="Status",
        value="todo",
        options=[ft.dropdown.Option(key) for key in ["todo", "doing", "done"]],
        border_radius=16,
        bgcolor=SURFACE_ALT,
        border_color=BORDER,
        color=TEXT,
    )
    card_priority_dropdown = ft.Dropdown(
        label="Prioridade",
        value="medium",
        options=[ft.dropdown.Option(key) for key in ["low", "medium", "high"]],
        border_radius=16,
        bgcolor=SURFACE_ALT,
        border_color=BORDER,
        color=TEXT,
    )
    card_responsible_field = ft.TextField(
        label="Responsavel",
        border_radius=16,
        bgcolor=SURFACE_ALT,
        color=TEXT,
        border_color=BORDER,
    )
    card_feedback = ft.Text(color=TEXT_MUTED, size=12)

    location_code_field = ft.TextField(label="Codigo", border_radius=16, bgcolor=SURFACE_ALT, color=TEXT, border_color=BORDER)
    location_name_field = ft.TextField(label="Nome", border_radius=16, bgcolor=SURFACE_ALT, color=TEXT, border_color=BORDER)
    location_address_field = ft.TextField(label="Endereco", border_radius=16, bgcolor=SURFACE_ALT, color=TEXT, border_color=BORDER)
    location_lat_field = ft.TextField(label="Latitude", border_radius=16, bgcolor=SURFACE_ALT, color=TEXT, border_color=BORDER)
    location_lng_field = ft.TextField(label="Longitude", border_radius=16, bgcolor=SURFACE_ALT, color=TEXT, border_color=BORDER)
    location_type_field = ft.TextField(label="Tipo", value="obra", border_radius=16, bgcolor=SURFACE_ALT, color=TEXT, border_color=BORDER)
    location_feedback = ft.Text(color=TEXT_MUTED, size=12)
    route_origin_dropdown = ft.Dropdown(label="Origem", border_radius=16, bgcolor=SURFACE_ALT, border_color=BORDER, color=TEXT, options=[])
    route_destination_dropdown = ft.Dropdown(label="Destino", border_radius=16, bgcolor=SURFACE_ALT, border_color=BORDER, color=TEXT, options=[])
    route_feedback = ft.Text(color=TEXT_MUTED, size=12)

    def _logo_badge() -> ft.Control:
        return ft.Row(
            [
                ft.Image(
                    src="assets/logo.png",
                    width=52,
                    height=52,
                    fit=ft.ImageFit.CONTAIN,
                ),
                ft.Column(
                    [
                        ft.Text("Dinâmica", size=22, color=TEXT, weight=ft.FontWeight.W_900),
                        ft.Text("EMPREENDIMENTOS", size=9, color=LOGO_BG_START, weight=ft.FontWeight.W_700),
                    ],
                    spacing=0,
                    tight=True,
                ),
            ],
            spacing=12,
        )

    login_panel = ft.Container(
        expand=True,
        bgcolor="#101011",
        content=ft.Row(
            expand=True,
            spacing=0,
            controls=[
                # ── LEFT: form panel ──────────────────────────────────────
                ft.Container(
                    width=440,
                    bgcolor="#111113",
                    border=ft.border.only(right=ft.BorderSide(1, "#FFFFFF0D")),
                    padding=ft.padding.only(left=56, right=56, top=40, bottom=40),
                    content=ft.Column(
                        expand=True,
                        spacing=0,
                        controls=[
                            _logo_badge(),
                            ft.Container(expand=True),
                            ft.Column(
                                [
                                    ft.Text("ACESSO SEGURO", size=11, color=ACCENT, weight=ft.FontWeight.W_700),
                                    ft.Text("Login", size=48, color=TEXT, weight=ft.FontWeight.W_900),
                                    ft.Text(
                                        "Entre com seu usuário administrativo para acessar o painel integrado ao FastAPI.",
                                        color=TEXT_MUTED,
                                        size=13,
                                    ),
                                    ft.Container(height=16),
                                    ft.Column(
                                        [
                                            ft.Text("EMAIL", size=11, color=ACCENT, weight=ft.FontWeight.W_700),
                                            email_field,
                                        ],
                                        spacing=4,
                                    ),
                                    ft.Column(
                                        [
                                            ft.Text("SENHA", size=11, color=ACCENT, weight=ft.FontWeight.W_700),
                                            password_field,
                                        ],
                                        spacing=4,
                                    ),
                                    login_message,
                                    ft.Container(
                                        width=400,
                                        height=52,
                                        border_radius=20,
                                        gradient=ft.LinearGradient(colors=["#EA580C", ACCENT]),
                                        alignment=ft.alignment.center,
                                        ink=True,
                                        on_click=lambda _: handle_login(),
                                        content=ft.Text(
                                            "ENTRAR",
                                            color=TEXT,
                                            size=13,
                                            weight=ft.FontWeight.W_900,
                                        ),
                                    ),
                                ],
                                spacing=16,
                            ),
                            ft.Container(expand=True),
                            ft.Text(
                                "Usuário padrão: admin@dinamica.com",
                                size=11,
                                color="#6B7280",
                            ),
                        ],
                    ),
                ),
                # ── RIGHT: decorative panel ───────────────────────────────
                ft.Container(
                    expand=True,
                    gradient=ft.LinearGradient(
                        colors=["#171719", "#222124", "#1A1A1D"],
                        begin=ft.alignment.center_left,
                        end=ft.alignment.center_right,
                    ),
                    content=ft.Column(
                        [
                            ft.Container(
                                width=112,
                                height=112,
                                border_radius=999,
                                border=ft.border.all(8, f"{ACCENT}F2"),
                                margin=ft.margin.only(left=40, top=40),
                            ),
                            ft.Row(
                                [
                                    ft.Container(
                                        width=48,
                                        height=48,
                                        border_radius=999,
                                        gradient=ft.LinearGradient(colors=[ACCENT_SOFT, ACCENT]),
                                    )
                                ],
                                alignment=ft.MainAxisAlignment.END,
                                tight=True,
                            ),
                            ft.Container(
                                margin=ft.margin.symmetric(horizontal=40, vertical=20),
                                border_radius=28,
                                bgcolor=SURFACE_SOFT,
                                border=ft.border.all(1, f"{ACCENT}33"),
                                padding=28,
                                content=ft.Column(
                                    [
                                        ft.Row(
                                            [
                                                ft.Column(
                                                    [
                                                        ft.Container(width=112, height=12, bgcolor=ACCENT, border_radius=999),
                                                        ft.Container(width=128, height=12, bgcolor=ACCENT, border_radius=999),
                                                        ft.Container(width=80, height=12, bgcolor=ACCENT, border_radius=999),
                                                    ],
                                                    spacing=10,
                                                ),
                                                ft.Container(
                                                    width=80,
                                                    height=80,
                                                    border_radius=999,
                                                    border=ft.border.all(8, ACCENT),
                                                    bgcolor=f"{ACCENT}26",
                                                ),
                                            ],
                                            alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
                                        ),
                                        ft.Container(height=8),
                                        *[
                                            ft.Row(
                                                [
                                                    ft.Container(width=20, height=20, border_radius=999, bgcolor=ACCENT),
                                                    ft.Container(width=int(w * 2.2), height=20, border_radius=999, bgcolor=ACCENT),
                                                    ft.Container(width=40, height=20, border_radius=999, bgcolor=f"{ACCENT_SOFT}CC"),
                                                ],
                                                spacing=10,
                                            )
                                            for w in [62, 74, 58]
                                        ],
                                        ft.Container(height=8),
                                        ft.Row(
                                            [
                                                ft.Container(
                                                    expand=True,
                                                    border_radius=14,
                                                    border=ft.border.all(1, f"{ACCENT}33"),
                                                    bgcolor="#00000040",
                                                    padding=14,
                                                    content=ft.Column(
                                                        [
                                                            ft.Container(width=16, height=16, border_radius=999, bgcolor=ACCENT),
                                                            ft.Container(height=4),
                                                            ft.Container(width=64, height=8, border_radius=999, bgcolor=ACCENT),
                                                            ft.Container(width=48, height=8, border_radius=999, bgcolor=f"{ACCENT_SOFT}CC"),
                                                        ],
                                                        spacing=6,
                                                    ),
                                                )
                                                for _ in range(3)
                                            ],
                                            spacing=12,
                                        ),
                                    ],
                                    spacing=14,
                                ),
                            ),
                        ],
                        spacing=0,
                    ),
                ),
            ],
        ),
    )

    app_shell = ft.Container(expand=True)

    def menu_button(label: str, key: str, icon: str) -> ft.Control:
        selected = state["active_view"] == key
        return ft.Container(
            border_radius=18,
            bgcolor=f"{ACCENT}22" if selected else "transparent",
            border=ft.border.all(1, f"{ACCENT}55" if selected else BORDER),
            padding=ft.padding.symmetric(horizontal=14, vertical=12),
            ink=True,
            on_click=lambda _: switch_view(key),
            content=ft.Row(
                [
                    ft.Icon(icon, color=ACCENT if selected else TEXT_MUTED, size=18),
                    ft.Text(label, color=TEXT if selected else TEXT_MUTED, weight=ft.FontWeight.W_600),
                ],
                spacing=10,
            ),
        )

    def compact_menu_button(label: str, key: str, icon: str) -> ft.Control:
        selected = state["active_view"] == key
        return ft.Container(
            bgcolor=f"{ACCENT}22" if selected else SURFACE,
            border=ft.border.all(1, f"{ACCENT}55" if selected else BORDER),
            border_radius=999,
            padding=ft.padding.symmetric(horizontal=14, vertical=10),
            ink=True,
            on_click=lambda _: switch_view(key),
            content=ft.Row(
                [ft.Icon(icon, size=16, color=ACCENT if selected else TEXT_MUTED), ft.Text(label, color=TEXT, size=12)],
                tight=True,
                spacing=8,
            ),
        )

    def resolve_building_name(building_id: Any) -> str:
        for building in state.get("bootstrap", {}).get("obras", []):
            if str(building.get("id")) == str(building_id) or str(building.get("code")) == str(building_id):
                return str(building.get("name") or building.get("nome") or f"Obra {building_id}")
        return f"Obra {building_id}"

    def resolve_company_name(company_id: Any) -> str:
        for company in state.get("bootstrap", {}).get("companies", []):
            if str(company.get("id")) == str(company_id):
                return str(company.get("tradeName") or company.get("name") or f"Empresa {company_id}")
        return f"Empresa {company_id}" if company_id else "-"

    def top_buildings_by_orders() -> list[tuple[str, int]]:
        counter: Counter[str] = Counter()
        for order in state.get("bootstrap", {}).get("pedidos", []):
            counter[resolve_building_name(order.get("buildingId") or order.get("idObra"))] += 1
        return counter.most_common(5)

    def top_clients_by_city() -> list[tuple[str, int]]:
        items = state.get("summary", {}).get("client_cities", []) or []
        return [(str(item.get("city") or "Sem cidade"), int(item.get("total") or 0)) for item in items[:5]]

    def pending_payable() -> list[dict[str, Any]]:
        return [
            item
            for item in state.get("bootstrap", {}).get("financeiro", [])
            if str(item.get("situacao") or item.get("status") or "").upper() not in {"PAGO", "BAIXADO", "LIQUIDADO"}
        ]

    def open_receivables() -> list[dict[str, Any]]:
        return [
            item
            for item in state.get("bootstrap", {}).get("receber", [])
            if str(item.get("situacao") or item.get("status") or "").upper() not in {"PAGO", "BAIXADO", "LIQUIDADO"}
        ]

    def build_dashboard_view() -> list[ft.Control]:
        summary = state.get("summary", {}) or {}
        sync = state.get("sync", {}) or {}
        cards = summary.get("cards", [])
        latest_sync = sync.get("latestSync") or {}
        return [
            ft.Container(
                padding=32,
                bgcolor="#111113",
                border=ft.border.all(1, BORDER),
                border_radius=28,
                content=ft.Column(
                    [
                        ft.Text("Painel Executivo", size=36, color=TEXT, weight=ft.FontWeight.W_900),
                        ft.Text(
                            "Visão consolidada das operações — Financeiro, Obras, Logística e SIENGE.",
                            color=TEXT_MUTED,
                            size=14,
                        ),
                        ft.Row(
                            [
                                status_chip("FastAPI ativo", SUCCESS),
                                status_chip("Flet UI", ACCENT),
                                status_chip(latest_sync.get("status", "aguardando sync"), WARNING if latest_sync.get("status") != "success" else SUCCESS),
                            ],
                            wrap=True,
                        ),
                    ],
                    spacing=14,
                ),
            ),
            ft.ResponsiveRow(
                controls=[
                    ft.Container(col={"xs": 12, "md": 3}, content=metric_card(card.get("label", "Indicador"), str(card.get("value", 0)), "dados sincronizados"))
                    for card in cards[:4]
                ]
                + [
                    ft.Container(
                        col={"xs": 12, "md": 3},
                        content=metric_card(
                            "Saldo Bancario",
                            as_currency(state.get("bootstrap", {}).get("saldoBancario")),
                            "extrato consolidado",
                            SUCCESS,
                        ),
                    )
                ],
            ),
            ft.ResponsiveRow(
                controls=[
                    ft.Container(
                        col={"xs": 12, "lg": 6},
                        content=trend_list("Top cidades de clientes", top_clients_by_city() or [("Sem dados", 0)], ACCENT),
                    ),
                    ft.Container(
                        col={"xs": 12, "lg": 6},
                        content=trend_list("Obras com mais compras", top_buildings_by_orders() or [("Sem dados", 0)], SUCCESS),
                    ),
                ]
            ),
            ft.ResponsiveRow(
                controls=[
                    ft.Container(
                        col={"xs": 12, "lg": 6},
                        content=section_card(
                            "Status de sincronizacao",
                            "Saude da API e ultimo ciclo de importacao",
                            ft.Column(
                                [
                                    ft.Row([ft.Text("API", color=TEXT), status_chip(state.get("health", {}).get("status", "offline"), SUCCESS if state.get("health", {}).get("status") == "ok" else DANGER)]),
                                    ft.Row([ft.Text("Banco", color=TEXT), status_chip("pronto" if state.get("health", {}).get("database_ready") else "pendente", SUCCESS if state.get("health", {}).get("database_ready") else WARNING)]),
                                    ft.Text(f"Iniciado: {as_date(latest_sync.get('started_at'))}", color=TEXT_MUTED),
                                    ft.Text(f"Finalizado: {as_date(latest_sync.get('finished_at'))}", color=TEXT_MUTED),
                                    ft.Text(latest_sync.get("message", "Sem mensagem"), color=ACCENT_SOFT),
                                ],
                                spacing=10,
                            ),
                        ),
                    ),
                    ft.Container(
                        col={"xs": 12, "lg": 6},
                        content=section_card(
                            "Cobertura funcional",
                            "Substituicoes aplicadas no stack da interface",
                            ft.Column(
                                [
                                    ft.Text("UI: Flet no lugar de React", color=TEXT),
                                    ft.Text("Estilizacao: propriedades Flet no lugar de Tailwind", color=TEXT),
                                    ft.Text("Graficos e dashboards: Flet nativo no lugar de Recharts", color=TEXT),
                                    ft.Text("Icones: Material/Cupertino embutidos no lugar de Lucide", color=TEXT),
                                    ft.Text("Google GenAI continua no fluxo Python", color=TEXT),
                                ],
                                spacing=10,
                            ),
                        ),
                    ),
                ]
            ),
        ]

    def build_finance_view() -> list[ft.Control]:
        payable = pending_payable()
        receivable = open_receivables()
        total_payable = sum(float(item.get("valor") or item.get("amount") or 0) for item in payable)
        total_receivable = sum(float(item.get("valor") or item.get("amount") or 0) for item in receivable)
        return [
            ft.ResponsiveRow(
                controls=[
                    ft.Container(col={"xs": 12, "md": 4}, content=metric_card("Total a pagar", as_currency(total_payable), f"{len(payable)} titulos em aberto", DANGER)),
                    ft.Container(col={"xs": 12, "md": 4}, content=metric_card("Total a receber", as_currency(total_receivable), f"{len(receivable)} titulos em aberto", SUCCESS)),
                    ft.Container(col={"xs": 12, "md": 4}, content=metric_card("Saldo consolidado", as_currency(state.get("bootstrap", {}).get("saldoBancario")), "receitas menos despesas", ACCENT)),
                ]
            ),
            section_card(
                "Titulos a pagar",
                "Financeiro em aberto vindo do bootstrap SIENGE",
                data_table("Pagar", payable, ["id", "nomeCredor", "nomeObra", "dataVencimento", "valor", "situacao"], limit=10),
            ),
            section_card(
                "Titulos a receber",
                "Fluxo de recebiveis e extrato consolidado",
                data_table("Receber", receivable, ["id", "nomeCliente", "nomeObra", "dataVencimento", "valor", "situacao"], limit=10),
            ),
        ]

    def build_orders_view() -> list[ft.Control]:
        orders = state.get("bootstrap", {}).get("pedidos", [])
        items_map = state.get("bootstrap", {}).get("itensPedidos", {}) or {}
        order_rows = []
        for order in orders[:15]:
            order_id = str(order.get("id"))
            order_rows.append(
                {
                    "id": order.get("id"),
                    "obra": order.get("nomeObra") or resolve_building_name(order.get("buildingId")),
                    "fornecedor": order.get("nomeFornecedor"),
                    "data": as_date(order.get("dataEmissao") or order.get("date")),
                    "valor": as_currency(order.get("valorTotal") or order.get("totalAmount")),
                    "itens": len(items_map.get(order_id, [])),
                }
            )
        top_suppliers = Counter(str(order.get("nomeFornecedor") or "Sem fornecedor") for order in orders).most_common(6)
        return [
            ft.ResponsiveRow(
                controls=[
                    ft.Container(col={"xs": 12, "md": 4}, content=metric_card("Pedidos", str(len(orders)), "carregados do cache SIENGE")),
                    ft.Container(col={"xs": 12, "md": 4}, content=metric_card("Itens detalhados", str(len(items_map)), "pedidos com itens em cache", SUCCESS)),
                    ft.Container(col={"xs": 12, "md": 4}, content=metric_card("Empresas ativas", str(len(state.get("bootstrap", {}).get("companies", []))), "relacionadas ao fluxo de compras", ACCENT)),
                ]
            ),
            ft.ResponsiveRow(
                controls=[
                    ft.Container(
                        col={"xs": 12, "lg": 7},
                        content=section_card(
                            "Compras recentes",
                            "Mantem o acompanhamento operacional da versao antiga",
                            data_table("Pedidos", order_rows, ["id", "obra", "fornecedor", "data", "valor", "itens"], limit=15),
                        ),
                    ),
                    ft.Container(
                        col={"xs": 12, "lg": 5},
                        content=trend_list("Fornecedores recorrentes", top_suppliers or [("Sem dados", 0)], ACCENT),
                    ),
                ]
            ),
        ]

    def build_buildings_view() -> list[ft.Control]:
        buildings = state.get("bootstrap", {}).get("obras", [])
        companies = state.get("bootstrap", {}).get("companies", [])
        building_cards = []
        for building in buildings[:18]:
            building_cards.append(
                ft.Container(
                    bgcolor=SURFACE,
                    border=ft.border.all(1, BORDER),
                    border_radius=22,
                    padding=18,
                    content=ft.Column(
                        [
                            ft.Row(
                                [
                                    ft.Text(str(building.get("name") or building.get("nome") or "Obra"), color=TEXT, expand=True, weight=ft.FontWeight.BOLD),
                                    status_chip(str(building.get("codigoVisivel") or building.get("code") or building.get("id")), ACCENT),
                                ],
                                alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
                            ),
                            ft.Text(resolve_company_name(building.get("companyId") or building.get("idCompany")), color=ACCENT_SOFT),
                            ft.Text(str(building.get("address") or building.get("endereco") or "Endereco nao informado"), color=TEXT_MUTED, size=12),
                            ft.Text(f"Responsavel: {building.get('engineer') or 'Aguardando avaliacao'}", color=TEXT, size=12),
                        ],
                        spacing=10,
                    ),
                )
            )
        return [
            ft.ResponsiveRow(
                controls=[
                    ft.Container(col={"xs": 12, "md": 4}, content=metric_card("Obras", str(len(buildings)), "mapeadas para operacao")),
                    ft.Container(col={"xs": 12, "md": 4}, content=metric_card("Empresas", str(len(companies)), "base societaria ativa", SUCCESS)),
                    ft.Container(col={"xs": 12, "md": 4}, content=metric_card("Credores", str(len(state.get('bootstrap', {}).get('credores', []))), "fornecedores sincronizados", ACCENT)),
                ]
            ),
            ft.ResponsiveRow(controls=[ft.Container(col={"xs": 12, "md": 6, "lg": 4}, content=card) for card in building_cards]),
        ]

    def build_access_view() -> list[ft.Control]:
        return [
            ft.ResponsiveRow(
                controls=[
                    ft.Container(col={"xs": 12, "lg": 6}, content=section_card("Usuarios do sistema", content=data_table("App", state.get("admin_users", []), ["id", "full_name", "email", "department", "role"], limit=12))),
                    ft.Container(col={"xs": 12, "lg": 6}, content=section_card("Diretorio", content=data_table("Directory", state.get("directory_users", []), ["id", "name", "email", "active"], limit=12))),
                ]
            )
        ]

    def refresh_location_options() -> None:
        options = [
            ft.dropdown.Option(str(item.get("id")), f"{item.get('code')} - {item.get('name')}")
            for item in state.get("locations", [])
        ]
        route_origin_dropdown.options = options
        route_destination_dropdown.options = options

    def build_logistics_view() -> list[ft.Control]:
        refresh_location_options()
        return [
            ft.ResponsiveRow(
                controls=[
                    ft.Container(
                        col={"xs": 12, "lg": 5},
                        content=section_card(
                            "Nova localizacao",
                            "Cadastro direto no modulo logistico mantido no FastAPI",
                            ft.Column(
                                [
                                    location_code_field,
                                    location_name_field,
                                    location_address_field,
                                    ft.Row([location_lat_field, location_lng_field], wrap=True),
                                    location_type_field,
                                    ft.ElevatedButton(
                                        "Salvar localizacao",
                                        bgcolor=ACCENT,
                                        color=TEXT,
                                        on_click=lambda _: create_location(),
                                    ),
                                    location_feedback,
                                ],
                                spacing=12,
                            ),
                        ),
                    ),
                    ft.Container(
                        col={"xs": 12, "lg": 7},
                        content=section_card(
                            "Calculo de rota",
                            "Distancia aproximada via Haversine",
                            ft.Column(
                                [
                                    route_origin_dropdown,
                                    route_destination_dropdown,
                                    ft.ElevatedButton("Calcular distancia", bgcolor=SURFACE_SOFT, color=TEXT, on_click=lambda _: calculate_route()),
                                    route_feedback,
                                ],
                                spacing=12,
                            ),
                        ),
                    ),
                ]
            ),
            section_card(
                "Pontos logisticos",
                content=data_table("Locations", state.get("locations", []), ["id", "code", "name", "address", "location_type", "source"], limit=16),
            ),
        ]

    def refresh_sprint_options() -> None:
        buildings = state.get("bootstrap", {}).get("obras", [])
        building_dropdown.options = [
            ft.dropdown.Option(str(item.get("id")), str(item.get("name") or item.get("nome") or item.get("id")))
            for item in buildings
        ]
        card_sprint_dropdown.options = [
            ft.dropdown.Option(str(item.get("id")), f"{item.get('name')} ({resolve_building_name(item.get('buildingId'))})")
            for item in state.get("sprints", [])
        ]

    def build_kanban_columns() -> ft.Control:
        columns: list[ft.Control] = []
        status_map = {"todo": "A Fazer", "doing": "Em Progresso", "done": "Concluido"}
        for key, label in status_map.items():
            cards: list[ft.Control] = []
            for sprint in state.get("sprints", []):
                for card in sprint.get("cards", []):
                    if card.get("status") != key:
                        continue
                    cards.append(
                        ft.Container(
                            bgcolor=SURFACE_ALT,
                            border=ft.border.all(1, BORDER),
                            border_radius=18,
                            padding=14,
                            content=ft.Column(
                                [
                                    ft.Text(card.get("title", "Card"), color=TEXT, weight=ft.FontWeight.BOLD),
                                    ft.Text(sprint.get("name", "Sprint"), color=ACCENT_SOFT, size=12),
                                    ft.Text(card.get("description") or "Sem descricao", color=TEXT_MUTED, size=12),
                                    ft.Row(
                                        [
                                            status_chip(card.get("priority", "medium"), WARNING if card.get("priority") == "high" else ACCENT),
                                            status_chip(card.get("responsible") or "sem responsavel", SUCCESS),
                                        ],
                                        wrap=True,
                                    ),
                                ],
                                spacing=10,
                            ),
                        )
                    )
            columns.append(
                ft.Container(
                    expand=True,
                    bgcolor=SURFACE,
                    border=ft.border.all(1, BORDER),
                    border_radius=22,
                    padding=16,
                    content=ft.Column(
                        [ft.Text(label, color=TEXT, size=18, weight=ft.FontWeight.BOLD)] + cards
                        if cards
                        else [ft.Text(label, color=TEXT, size=18, weight=ft.FontWeight.BOLD), ft.Text("Sem cards", color=TEXT_MUTED)],
                        spacing=12,
                    ),
                )
            )
        return ft.ResponsiveRow([ft.Container(col={"xs": 12, "lg": 4}, content=column) for column in columns])

    def build_kanban_view() -> list[ft.Control]:
        refresh_sprint_options()
        return [
            ft.ResponsiveRow(
                controls=[
                    ft.Container(
                        col={"xs": 12, "lg": 4},
                        content=section_card(
                            "Criar sprint",
                            content=ft.Column(
                                [
                                    building_dropdown,
                                    sprint_name_field,
                                    sprint_color_field,
                                    ft.ElevatedButton("Salvar sprint", bgcolor=ACCENT, color=TEXT, on_click=lambda _: create_sprint()),
                                    sprint_feedback,
                                ],
                                spacing=12,
                            ),
                        ),
                    ),
                    ft.Container(
                        col={"xs": 12, "lg": 4},
                        content=section_card(
                            "Criar card",
                            content=ft.Column(
                                [
                                    card_sprint_dropdown,
                                    card_title_field,
                                    card_status_dropdown,
                                    card_priority_dropdown,
                                    card_responsible_field,
                                    ft.ElevatedButton("Salvar card", bgcolor=SURFACE_SOFT, color=TEXT, on_click=lambda _: create_card()),
                                    card_feedback,
                                ],
                                spacing=12,
                            ),
                        ),
                    ),
                    ft.Container(
                        col={"xs": 12, "lg": 4},
                        content=section_card(
                            "Resumo do kanban",
                            content=ft.Column(
                                [
                                    ft.Text(f"Sprints carregados: {len(state.get('sprints', []))}", color=TEXT),
                                    ft.Text(
                                        f"Cards totais: {sum(len(sprint.get('cards', [])) for sprint in state.get('sprints', []))}",
                                        color=TEXT,
                                    ),
                                    ft.Text("Os anexos continuam no backend FastAPI para evolucao futura.", color=TEXT_MUTED, size=12),
                                ],
                                spacing=10,
                            ),
                        ),
                    ),
                ]
            ),
            build_kanban_columns(),
        ]

    def render_active_view() -> None:
        view = state["active_view"]
        builders = {
            "dashboard": build_dashboard_view,
            "financeiro": build_finance_view,
            "compras": build_orders_view,
            "obras": build_buildings_view,
            "logistica": build_logistics_view,
            "acessos": build_access_view,
            "kanban": build_kanban_view,
        }
        main_content.controls = builders.get(view, build_dashboard_view)()
        build_shell()
        page.update()

    def switch_view(view: str) -> None:
        state["active_view"] = view
        render_active_view()

    def build_shell() -> None:
        nav_items = [
            ("DASHBOARD", "dashboard", ft.Icons.SPACE_DASHBOARD_ROUNDED),
            ("FINANCEIRO", "financeiro", ft.Icons.ACCOUNT_BALANCE_WALLET_ROUNDED),
            ("COMPRAS", "compras", ft.Icons.SHOPPING_CART_ROUNDED),
            ("OBRAS", "obras", ft.Icons.APARTMENT_ROUNDED),
            ("LOGÍSTICA", "logistica", ft.Icons.LOCAL_SHIPPING_ROUNDED),
            ("ACESSOS", "acessos", ft.Icons.BADGE_ROUNDED),
            ("KANBAN", "kanban", ft.Icons.VIEW_KANBAN_ROUNDED),
        ]

        def nav_pill(label: str, key: str) -> ft.Control:
            selected = state["active_view"] == key
            return ft.Container(
                border_radius=10,
                bgcolor=f"{ACCENT}DD" if selected else "transparent",
                padding=ft.padding.symmetric(horizontal=16, vertical=8),
                ink=True,
                on_click=lambda _: switch_view(key),
                content=ft.Text(
                    label,
                    color=TEXT if selected else TEXT_MUTED,
                    size=12,
                    weight=ft.FontWeight.W_700,
                ),
            )

        mobile_nav.controls = [nav_pill(label, key) for label, key, _ in nav_items]

        top_header = ft.Container(
            padding=ft.padding.symmetric(horizontal=24, vertical=0),
            bgcolor="#111113",
            border=ft.border.only(bottom=ft.BorderSide(1, "#FFFFFF0D")),
            height=64,
            content=ft.Row(
                [
                    ft.Row(
                        [
                            ft.Image(src="assets/logo.png", width=36, height=36, fit=ft.ImageFit.CONTAIN),
                            ft.Text("DINÂMICA", size=18, color=TEXT, weight=ft.FontWeight.W_900),
                        ],
                        spacing=10,
                    ),
                    ft.Row(
                        [nav_pill(label, key) for label, key, _ in nav_items],
                        spacing=2,
                    ),
                    ft.Row(
                        [
                            loading_ring,
                            ft.Text(
                                f"{client.user.get('full_name', '')}  ·  {client.user.get('role', '')}",
                                color=TEXT_MUTED,
                                size=12,
                            ),
                            ft.Container(
                                border_radius=12,
                                bgcolor=ACCENT,
                                padding=ft.padding.symmetric(horizontal=16, vertical=8),
                                ink=True,
                                on_click=lambda _: sync_sienge(),
                                content=ft.Text("Sincronizar SIENGE", color="#000000", size=12, weight=ft.FontWeight.W_700),
                            ),
                        ],
                        spacing=12,
                    ),
                ],
                alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
                vertical_alignment=ft.CrossAxisAlignment.CENTER,
            ),
        )

        content = ft.Container(
            expand=True,
            padding=24,
            content=ft.Column(
                [mobile_nav, sync_message, main_content],
                spacing=18,
                expand=True,
            ),
        )

        wide_layout = page.width >= 1100 if page.width else True
        mobile_nav.visible = not wide_layout
        shell.controls = [top_header, content]
        app_shell.content = shell

    def load_locations() -> None:
        try:
            state["locations"] = client.get("/sienge/logistics/locations").get("results", [])
        except Exception:
            state["locations"] = []

    def load_sprints() -> None:
        all_sprints: list[dict[str, Any]] = []
        for building in state.get("bootstrap", {}).get("obras", [])[:10]:
            bid = building.get("id")
            if bid is None:
                continue
            try:
                payload = client.get("/kanban", params={"building_id": bid})
                all_sprints.extend(payload.get("buildings", {}).get(str(bid), payload.get("buildings", {}).get(bid, [])))
            except Exception:
                continue
        state["sprints"] = all_sprints

    def load_all_data() -> None:
        loading_ring.visible = True
        sync_message.value = "Atualizando dados da interface em Flet..."
        page.update()
        try:
            state["health"] = client.get("/health")
            state["summary"] = client.get("/dashboard/summary")
            state["bootstrap"] = client.get("/sienge/bootstrap")
            state["sync"] = client.get("/sienge/test")
            state["admin_users"] = client.get("/admin/users")
            state["directory_users"] = client.get("/directory/users")
            load_locations()
            load_sprints()
            refresh_sprint_options()
            sync_message.value = "Dados carregados com sucesso."
        except Exception as exc:
            sync_message.value = f"Falha ao carregar dados: {exc}"
        finally:
            loading_ring.visible = False
            render_active_view()

    def sync_sienge() -> None:
        loading_ring.visible = True
        sync_message.value = "Executando sincronizacao com o SIENGE..."
        page.update()
        try:
            result = client.post("/sienge/sync")
            sync_message.value = result.get("message", "Sincronizacao concluida.")
            load_all_data()
        except Exception as exc:
            loading_ring.visible = False
            sync_message.value = f"Erro no sync: {exc}"
            page.update()

    def create_location() -> None:
        try:
            payload = {
                "code": location_code_field.value.strip(),
                "name": location_name_field.value.strip(),
                "address": location_address_field.value.strip(),
                "latitude": float(location_lat_field.value) if location_lat_field.value else None,
                "longitude": float(location_lng_field.value) if location_lng_field.value else None,
                "location_type": location_type_field.value.strip() or None,
                "source": "flet",
            }
            client.post("/sienge/logistics/locations", payload)
            location_feedback.value = "Localizacao criada com sucesso."
            for field in [location_code_field, location_name_field, location_address_field, location_lat_field, location_lng_field]:
                field.value = ""
            load_locations()
            render_active_view()
        except Exception as exc:
            location_feedback.value = f"Falha ao salvar localizacao: {exc}"
            page.update()

    def calculate_route() -> None:
        try:
            origin = next(item for item in state.get("locations", []) if str(item.get("id")) == route_origin_dropdown.value)
            destination = next(item for item in state.get("locations", []) if str(item.get("id")) == route_destination_dropdown.value)
            payload = {
                "origin": {"address": origin.get("address"), "lat": origin.get("latitude"), "lng": origin.get("longitude")},
                "destination": {"address": destination.get("address"), "lat": destination.get("latitude"), "lng": destination.get("longitude")},
            }
            result = client.post("/sienge/logistics/route-distance", payload)
            route_feedback.value = f"Distancia: {result.get('distanceKm', 0)} km via {result.get('provider', 'desconhecido')}."
            page.update()
        except StopIteration:
            route_feedback.value = "Selecione origem e destino validos."
            page.update()
        except Exception as exc:
            route_feedback.value = f"Falha ao calcular rota: {exc}"
            page.update()

    def create_sprint() -> None:
        try:
            payload = {
                "name": sprint_name_field.value.strip(),
                "building_id": int(building_dropdown.value),
                "color": sprint_color_field.value.strip() or "blue",
                "start_date": None,
                "end_date": None,
            }
            client.post("/kanban/sprint", payload)
            sprint_feedback.value = "Sprint criado com sucesso."
            sprint_name_field.value = ""
            load_sprints()
            render_active_view()
        except Exception as exc:
            sprint_feedback.value = f"Falha ao criar sprint: {exc}"
            page.update()

    def create_card() -> None:
        try:
            sprint_id = int(card_sprint_dropdown.value)
            sprint = next(item for item in state.get("sprints", []) if int(item.get("id")) == sprint_id)
            payload = {
                "title": card_title_field.value.strip(),
                "description": None,
                "status": card_status_dropdown.value,
                "priority": card_priority_dropdown.value,
                "responsible": card_responsible_field.value.strip() or None,
                "due_date": None,
                "tags": None,
                "sprint_id": sprint_id,
                "building_id": int(sprint.get("buildingId")),
            }
            client.post("/kanban/card", payload)
            card_feedback.value = "Card criado com sucesso."
            card_title_field.value = ""
            card_responsible_field.value = ""
            load_sprints()
            render_active_view()
        except StopIteration:
            card_feedback.value = "Sprint selecionado nao foi encontrado."
            page.update()
        except Exception as exc:
            card_feedback.value = f"Falha ao criar card: {exc}"
            page.update()

    def handle_login() -> None:
        login_message.value = ""
        try:
            client.login(email_field.value.strip(), password_field.value)
            page.controls.clear()
            page.add(app_shell)
            load_all_data()
        except Exception as exc:
            login_message.value = f"Falha no login: {exc}"
            page.update()

    def on_resize(_: ft.ControlEvent) -> None:
        if app_shell in page.controls:
            build_shell()
            page.update()

    page.on_resize = on_resize
    page.add(login_panel)


def launch_flet() -> None:
    ft.app(target=main, view=ft.AppView.WEB_BROWSER, host=FLET_HOST, port=FLET_PORT)


if __name__ == "__main__":
    launch_flet()
