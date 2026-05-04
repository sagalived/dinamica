from typing import Any
from datetime import datetime, timedelta
import hashlib
import threading
import asyncio

import httpx

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select
from sqlalchemy.orm import Session

from backend.database import get_db
from backend.dependencies import get_current_user
from backend.models import AppUser, Building, Company, Creditor, DirectoryUser
from backend.schemas import BootstrapResponse, FetchItemsRequest, FetchQuotationsRequest
from backend.services.sienge_cache import utc_now_iso
from backend.services.sienge_client import sienge_client
from backend.services.mc_by_building_service import compute_mc_by_building
from backend.services.sienge_storage import (
    read_snapshot,
    read_sync_metadata,
    write_snapshot,
    write_sync_metadata,
)

router = APIRouter(prefix="/api/sienge", tags=["sienge"])
_SYNC_LOCK = threading.Lock()
_SYNC_STATE: dict[str, Any] = {
    "running": False,
    "source": None,
    "started_at": None,
}


def _validate_iso_date(value: str, label: str) -> None:
    try:
        datetime.strptime(value, "%Y-%m-%d")
    except ValueError:
        raise HTTPException(
            status_code=422,
            detail=f"{label} deve estar no formato yyyy-MM-dd (ex: 2017-08-13)",
        )


def _add_days_iso(value: str, days: int) -> str:
    dt = datetime.strptime(value, "%Y-%m-%d") + timedelta(days=days)
    return dt.strftime("%Y-%m-%d")


def _infer_cached_range(items: list[dict[str, Any]], date_fields: list[str]) -> tuple[str | None, str | None]:
    min_ms: int | None = None
    max_ms: int | None = None
    for item in items:
        if not isinstance(item, dict):
            continue
        raw = None
        for key in date_fields:
            if item.get(key):
                raw = item.get(key)
                break
        ms = _to_date_number(raw)
        if not ms:
            continue
        if min_ms is None or ms < min_ms:
            min_ms = ms
        if max_ms is None or ms > max_ms:
            max_ms = ms
    if min_ms is None or max_ms is None:
        return None, None
    start = datetime.fromtimestamp(min_ms / 1000).strftime("%Y-%m-%d")
    end = datetime.fromtimestamp(max_ms / 1000).strftime("%Y-%m-%d")
    return start, end


async def _ensure_cached_dataset_range(
    *,
    db: Session,
    dataset_key: str,
    start_date: str,
    end_date: str,
    fetcher,
    date_fields_for_infer: list[str],
) -> None:
    """Garante que o snapshot de um dataset cubra o range solicitado.

    Estratégia: mantém um metadata de cobertura e busca apenas o delta.
    """
    if not start_date or not end_date:
        return

    meta = read_snapshot(db, "sienge_ranges", default={})
    if not isinstance(meta, dict):
        meta = {}

    dataset_meta = meta.get(dataset_key)
    if not isinstance(dataset_meta, dict):
        dataset_meta = {}

    cached_start = dataset_meta.get("start")
    cached_end = dataset_meta.get("end")

    existing = _to_array(read_snapshot(db, f"{dataset_key}.json", default=[]))

    # Sempre tenta inferir o range REAL do cache. Isso evita meta "mentindo"
    # (ex.: meta diz 2026, mas o snapshot foi sobrescrito e só tem 2025).
    inferred_start: str | None = None
    inferred_end: str | None = None
    if existing:
        inferred_start, inferred_end = _infer_cached_range(existing, date_fields_for_infer)

    if inferred_start and inferred_end:
        if not cached_start or not cached_end:
            cached_start, cached_end = inferred_start, inferred_end
        else:
            # Se o meta está maior do que o conteúdo real, corrige para o range inferido.
            # (Isso força o delta a ser buscado e evita respostas vazias/erradas.)
            if inferred_start > cached_start or inferred_end < cached_end:
                cached_start, cached_end = inferred_start, inferred_end
                meta[dataset_key] = {"start": cached_start, "end": cached_end}
                write_snapshot(db, "sienge_ranges", meta)

    # Se não tem cache, baixa tudo do range solicitado.
    if not existing or not cached_start or not cached_end:
        fresh = await fetcher(start_date, end_date)
        if fresh:
            write_snapshot(db, f"{dataset_key}.json", fresh)
            final_start, final_end = _infer_cached_range(fresh, date_fields_for_infer)
            meta[dataset_key] = {
                "start": final_start or start_date,
                "end": final_end or end_date,
            }
            write_snapshot(db, "sienge_ranges", meta)
        return

    missing_ranges: list[tuple[str, str]] = []
    if start_date < cached_start:
        missing_ranges.append((start_date, _add_days_iso(cached_start, -1)))
    if end_date > cached_end:
        missing_ranges.append((_add_days_iso(cached_end, 1), end_date))

    if not missing_ranges:
        # mantém meta consistente
        if dataset_key not in meta:
            meta[dataset_key] = {"start": cached_start, "end": cached_end}
            write_snapshot(db, "sienge_ranges", meta)
        return

    merged: list[dict[str, Any]] = list(existing)
    seen: set[str] = set()
    for it in merged:
        if isinstance(it, dict) and it.get("id") is not None:
            seen.add(str(it.get("id")))

    changed = False
    for m_start, m_end in missing_ranges:
        if m_start > m_end:
            continue
        fresh = await fetcher(m_start, m_end)
        if not fresh:
            continue
        for it in fresh:
            if not isinstance(it, dict):
                continue
            iid = it.get("id")
            key = str(iid) if iid is not None else None
            if key and key in seen:
                continue
            if key:
                seen.add(key)
            merged.append(it)
            changed = True

    if changed:
        write_snapshot(db, f"{dataset_key}.json", merged)
        final_start, final_end = _infer_cached_range(merged, date_fields_for_infer)
        meta[dataset_key] = {
            "start": final_start or min(cached_start, start_date),
            "end": final_end or max(cached_end, end_date),
        }
        write_snapshot(db, "sienge_ranges", meta)


@router.get("/nfe/documents")
async def list_nfe_documents(
    startDate: str = Query(..., description="Data inicial da busca (data de emissão) - yyyy-MM-dd"),
    endDate: str = Query(..., description="Data final da busca (data de emissão) - yyyy-MM-dd"),
    limit: int = Query(100, ge=1, le=200, description="Quantidade máxima de resultados (max 200)"),
    offset: int = Query(0, ge=0, description="Deslocamento na lista"),
    companyId: int | None = Query(None, description="ID da empresa"),
    supplierId: int | None = Query(None, description="ID do fornecedor"),
    documentId: str | None = Query(None, description="ID do documento"),
    series: str | None = Query(None, description="Série da nota fiscal"),
    number: str | None = Query(None, description="Número da nota fiscal"),
    current_user: AppUser = Depends(get_current_user),
) -> Any:
    _validate_iso_date(startDate, "startDate")
    _validate_iso_date(endDate, "endDate")

    payload = await sienge_client.fetch_nfe_documents(
        startDate=startDate,
        endDate=endDate,
        limit=limit,
        offset=offset,
        companyId=companyId,
        supplierId=supplierId,
        documentId=documentId,
        series=series,
        number=number,
    )

    if payload is None:
        return {
            "resultSetMetadata": {"count": 0, "offset": offset, "limit": limit},
            "results": [],
            "source": "fallback",
            "diagnostic": sienge_client.last_error,
        }

    if isinstance(payload, list):
        return {
            "resultSetMetadata": {"count": len(payload), "offset": offset, "limit": limit},
            "results": payload,
            "source": "sienge_live",
        }

    if isinstance(payload, dict):
        payload.setdefault("source", "sienge_live")
        return payload

    return {
        "resultSetMetadata": {"count": 0, "offset": offset, "limit": limit},
        "results": [],
        "source": "fallback",
        "diagnostic": sienge_client.last_error,
    }


def _to_array(payload: Any) -> list[dict]:
    if isinstance(payload, dict):
        data = payload.get("data")
        if isinstance(data, dict) and isinstance(data.get("results"), list):
            return data["results"]
        if isinstance(payload.get("results"), list):
            return payload["results"]
    if isinstance(payload, list):
        return payload
    return []


def _safe_float(value: Any, default: float = 0.0) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def _read_cached_dataset(db: Session, filename: str, default: Any) -> Any:
    return read_snapshot(db, filename, default=default)


def _write_cached_dataset(db: Session, filename: str, payload: Any) -> None:
    write_snapshot(db, filename, payload)


def _bill_buildings_cost_cache_key(bill_id: str) -> str:
    safe = "".join(ch for ch in str(bill_id) if ch.isdigit()) or str(bill_id)
    return f"bills_buildings_cost/{safe}.json"


def _extract_buildings_cost_rows(payload: Any) -> list[dict[str, Any]]:
    """Normaliza payloads variados do Sienge para uma lista de linhas."""
    if payload is None:
        return []
    if isinstance(payload, dict):
        data = payload.get("data")
        if isinstance(data, dict) and isinstance(data.get("results"), list):
            return [x for x in data["results"] if isinstance(x, dict)]
        if isinstance(payload.get("results"), list):
            return [x for x in payload["results"] if isinstance(x, dict)]
        if isinstance(payload.get("buildingsCost"), list):
            return [x for x in payload["buildingsCost"] if isinstance(x, dict)]
        if isinstance(payload.get("data"), list):
            return [x for x in payload["data"] if isinstance(x, dict)]
    if isinstance(payload, list):
        return [x for x in payload if isinstance(x, dict)]
    return []


def _weights_from_buildings_cost(rows: list[dict[str, Any]]) -> list[tuple[str, float]]:
    """Extrai pesos de rateio por obra.

    Retorna lista de (building_id, weight). O weight pode vir de % ou valor.
    """
    out: list[tuple[str, float]] = []
    for r in rows:
        bid = r.get("buildingId") or r.get("enterpriseId") or r.get("idObra") or r.get("building")
        bid_str = str(bid or "").strip()
        if not bid_str or bid_str in {"None", "undefined", "null"}:
            continue

        pct = r.get("percentage") or r.get("costPercentage") or r.get("percent") or r.get("rate")
        val = r.get("value") or r.get("costValue") or r.get("amount") or r.get("valor")
        pct_f = _safe_float(pct, 0.0)
        if pct_f:
            out.append((bid_str, pct_f))
            continue

        val_f = _safe_float(val, 0.0)
        if val_f:
            out.append((bid_str, val_f))
            continue

        out.append((bid_str, 1.0))
    return out


def _cache_counts(db: Session) -> dict[str, int]:
    return {
        "obras": len(_to_array(_read_cached_dataset(db, "obras.json", []))),
        "usuarios": len(_to_array(_read_cached_dataset(db, "usuarios.json", []))),
        "credores": len(_to_array(_read_cached_dataset(db, "credores.json", []))),
        "empresas": len(_to_array(_read_cached_dataset(db, "empresas.json", []))),
        "pedidos": len(_to_array(_read_cached_dataset(db, "pedidos.json", []))),
        "financeiro": len(_to_array(_read_cached_dataset(db, "financeiro.json", []))),
        "receber": len(_to_array(_read_cached_dataset(db, "receber.json", []))),
    }


def _normalize_company(item: dict[str, Any]) -> dict[str, Any]:
    return {
        "id": item.get("id"),
        "name": item.get("name") or item.get("nome") or item.get("companyName") or f"Empresa {item.get('id')}",
        "tradeName": item.get("tradeName") or item.get("nomeFantasia"),
        "companyName": item.get("companyName") or item.get("name") or item.get("nome") or f"Empresa {item.get('id')}",
        "cnpj": item.get("cnpj") or item.get("cpfCnpj") or "",
    }


def _normalize_building(item: dict[str, Any]) -> dict[str, Any]:
    company_id = item.get("companyId") or item.get("idCompany") or item.get("empresaId")
    code = item.get("code") or item.get("codigoVisivel") or item.get("codigo") or item.get("id")
    name = item.get("name") or item.get("nome") or item.get("enterpriseName") or f"Obra {code}"
    address = item.get("address") or item.get("endereco") or item.get("adress") or ""
    engineer = item.get("engineer") or item.get("responsavelTecnico") or item.get("responsavel") or ""
    return {
        "id": item.get("id") or code,
        "code": str(code or ""),
        "codigoVisivel": str(code or ""),
        "name": name,
        "nome": name,
        "address": address,
        "endereco": address,
        "latitude": item.get("latitude"),
        "longitude": item.get("longitude"),
        "companyId": company_id,
        "idCompany": company_id,
        "cnpj": item.get("cnpj"),
        "engineer": engineer or "Aguardando Avaliação",
    }


def _normalize_creditor(item: dict[str, Any]) -> dict[str, Any]:
    address = item.get("address") if isinstance(item.get("address"), dict) else {}
    name = item.get("name") or item.get("nome") or item.get("tradeName") or f"Credor {item.get('id')}"
    return {
        "id": item.get("id"),
        "name": name,
        "nome": name,
        "nomeFantasia": item.get("tradeName") or item.get("nomeFantasia"),
        "cnpj": item.get("cnpj") or item.get("cpfCnpj") or "",
        "city": item.get("city") or item.get("cidade") or address.get("cityName"),
        "state": item.get("state") or item.get("estado") or address.get("state"),
        "active": item.get("ativo") is not False if "ativo" in item else item.get("active", True),
    }


def _normalize_user(item: dict[str, Any]) -> dict[str, Any]:
    name = item.get("name") or item.get("nome") or "Usuário sem nome"
    return {
        "id": str(item.get("id") or item.get("userId") or item.get("username") or ""),
        "name": name,
        "nome": name,
        "email": item.get("email"),
        "active": item.get("active", True),
    }


def _extract_company_id_from_links(links: list[dict[str, Any]]) -> int | None:
    for link in links:
        if link.get("rel") == "company" and link.get("href"):
            tail = link["href"].rstrip("/").split("/")[-1]
            if str(tail).isdigit():
                return int(tail)
    return None


def _to_date_number(value: Any) -> int:
    raw = str(value or "").strip()
    if not raw:
        return 0
    try:
        return int(datetime.fromisoformat(raw.replace("Z", "+00:00")).timestamp() * 1000)
    except ValueError:
        pass
    for fmt in ("%Y-%m-%d", "%Y-%m-%d %H:%M:%S", "%d/%m/%Y"):
        try:
            return int(datetime.strptime(raw[:19], fmt).timestamp() * 1000)
        except ValueError:
            continue
    return 0


def _in_range(date_number: int, start_ms: int | None, end_exclusive_ms: int | None) -> bool:
    if start_ms is None and end_exclusive_ms is None:
        return True
    if not date_number:
        return False
    if start_ms is not None and date_number < start_ms:
        return False
    if end_exclusive_ms is not None and date_number >= end_exclusive_ms:
        return False
    return True


def _date_start_ms(value: str | None) -> int | None:
    if not value:
        return None
    return _to_date_number(value)


def _date_end_exclusive_ms(value: str | None) -> int | None:
    if not value:
        return None
    base = _to_date_number(value)
    if base == 0:
        return None
    return base + 24 * 60 * 60 * 1000


def _legacy_bootstrap_payload(db: Session, include_transactions: bool = True) -> dict[str, Any]:
    obras = _to_array(_read_cached_dataset(db, "obras.json", []))
    usuarios = _to_array(_read_cached_dataset(db, "usuarios.json", []))
    credores = _to_array(_read_cached_dataset(db, "credores.json", []))
    companies = _to_array(_read_cached_dataset(db, "empresas.json", []))
    if include_transactions:
        pedidos = _to_array(_read_cached_dataset(db, "pedidos.json", []))
        financeiro = _to_array(_read_cached_dataset(db, "financeiro.json", []))
        receber = _to_array(_read_cached_dataset(db, "receber.json", []))
        itens_pedidos = _read_cached_dataset(db, "itens_pedidos.json", {}) or {}
    else:
        pedidos = []
        financeiro = []
        receber = []
        itens_pedidos = {}

    if not obras:
        obras = [
            {
                "id": b.id,
                "name": b.name,
                "code": b.id,
                "address": b.address,
                "companyId": b.company_id,
                "cnpj": b.cnpj,
            }
            for b in db.scalars(select(Building)).all()
        ]
    if not companies:
        companies = [
            {
                "id": c.id,
                "name": c.name,
                "tradeName": c.trade_name,
                "companyName": c.name,
                "cnpj": c.cnpj,
            }
            for c in db.scalars(select(Company)).all()
        ]
    if not credores:
        credores = [
            {
                "id": c.id,
                "name": c.name,
                "tradeName": c.trade_name,
                "cnpj": c.cnpj,
                "city": c.city,
                "state": c.state,
                "active": c.active,
            }
            for c in db.scalars(select(Creditor)).all()
        ]
    if not usuarios:
        usuarios = [
            {
                "id": row.id,
                "name": row.name,
                "nome": row.name,
                "email": row.email,
                "active": row.active,
            }
            for row in db.scalars(select(DirectoryUser).order_by(DirectoryUser.name)).all()
        ]

    building_map: dict[str, dict[str, Any]] = {}
    for obra in obras:
        normalized = _normalize_building(obra)
        for bid in {
            str(normalized.get("code") or ""),
            str(normalized.get("id") or ""),
        }:
            if bid and bid not in {"None", "undefined"}:
                building_map[bid] = normalized

    creditor_map: dict[str, str] = {}
    for credor in credores:
        normalized = _normalize_creditor(credor)
        cid = str(normalized.get("id") or "")
        if cid:
            creditor_map[cid] = normalized["name"]

    user_map: dict[str, str] = {}
    for user in usuarios:
        normalized = _normalize_user(user)
        uid = str(normalized["id"])
        if uid:
            user_map[uid] = normalized["name"]

    normalized_orders: list[dict[str, Any]] = []
    for pedido in pedidos:
        building_id = str(pedido.get("codigoVisivelObra") or pedido.get("idObra") or pedido.get("buildingId") or "")
        supplier_id = str(pedido.get("codigoFornecedor") or pedido.get("idCredor") or pedido.get("supplierId") or "")
        buyer_id = str(pedido.get("idComprador") or pedido.get("codigoComprador") or pedido.get("buyerId") or "")
        building_info = building_map.get(building_id, {})
        normalized_orders.append(
            {
                "id": pedido.get("id") or pedido.get("numero") or 0,
                "buildingId": int(building_id) if building_id.isdigit() else 0,
                "idObra": int(building_id) if building_id.isdigit() else 0,
                "codigoVisivelObra": building_id,
                "companyId": pedido.get("companyId") or building_info.get("companyId"),
                "buyerId": buyer_id,
                "idComprador": buyer_id,
                "codigoComprador": buyer_id,
                "supplierId": int(supplier_id) if supplier_id.isdigit() else 0,
                "codigoFornecedor": int(supplier_id) if supplier_id.isdigit() else 0,
                "date": pedido.get("data") or pedido.get("dataEmissao") or pedido.get("date") or "",
                "dataEmissao": pedido.get("data") or pedido.get("dataEmissao") or pedido.get("date") or "",
                "totalAmount": _safe_float(pedido.get("totalAmount") or pedido.get("valorTotal")),
                "valorTotal": _safe_float(pedido.get("totalAmount") or pedido.get("valorTotal")),
                "status": pedido.get("status") or pedido.get("situacao") or "N/A",
                "situacao": pedido.get("status") or pedido.get("situacao") or "N/A",
                "paymentCondition": pedido.get("condicaoPagamento") or pedido.get("paymentMethod") or "A Prazo",
                "condicaoPagamento": pedido.get("condicaoPagamento") or pedido.get("paymentMethod") or "A Prazo",
                "deliveryDate": pedido.get("dataEntrega") or pedido.get("prazoEntrega") or "",
                "dataEntrega": pedido.get("dataEntrega") or pedido.get("prazoEntrega") or "",
                "internalNotes": pedido.get("internalNotes") or pedido.get("observacao") or "",
                "observacao": pedido.get("internalNotes") or pedido.get("observacao") or "",
                "nomeObra": pedido.get("nomeObra") or building_info.get("name") or (f"Obra {building_id}" if building_id else "Obra sem nome"),
                "nomeFornecedor": pedido.get("nomeFornecedor") or creditor_map.get(supplier_id) or (f"Credor {supplier_id}" if supplier_id else "Credor sem nome"),
                "nomeComprador": pedido.get("nomeComprador") or pedido.get("buyerName") or user_map.get(buyer_id) or buyer_id,
                "solicitante": pedido.get("solicitante") or pedido.get("requesterId") or pedido.get("createdBy") or user_map.get(buyer_id) or buyer_id,
                "requesterId": pedido.get("requesterId") or pedido.get("solicitante") or pedido.get("createdBy") or user_map.get(buyer_id) or buyer_id,
                "createdBy": pedido.get("createdBy") or pedido.get("nomeComprador") or user_map.get(buyer_id) or buyer_id,
            }
        )

    normalized_financial: list[dict[str, Any]] = []
    for item in financeiro:
        creditor_id = str(item.get("creditorId") or item.get("idCredor") or item.get("codigoFornecedor") or item.get("debtorId") or "")
        building_id = str(item.get("idObra") or item.get("codigoObra") or item.get("enterpriseId") or item.get("buildingId") or "")
        building_info = building_map.get(building_id, {})
        company_id = (
            item.get("companyId")
            or next(
                (
                    lnk["href"].rstrip("/").split("/")[-1]
                    for lnk in (item.get("links") or [])
                    if lnk.get("rel") == "company" and lnk.get("href")
                ),
                None,
            )
            or building_info.get("companyId")
        )
        name = item.get("nomeCredor") or item.get("creditorName") or item.get("nomeFantasiaCredor") or item.get("fornecedor") or item.get("credor") or creditor_map.get(creditor_id) or "Credor sem nome"
        normalized_financial.append(
            {
                "id": item.get("id") or item.get("numero") or item.get("codigoTitulo") or item.get("documentNumber") or 0,
                "companyId": int(company_id) if str(company_id).isdigit() else company_id,
                "creditorId": creditor_id,
                "buildingId": int(building_id) if building_id.isdigit() else 0,
                "idObra": int(building_id) if building_id.isdigit() else 0,
                "codigoObra": building_id,
                "dataVencimento": item.get("dataVencimento") or item.get("issueDate") or item.get("dueDate") or item.get("dataVencimentoProjetado") or item.get("dataEmissao") or item.get("dataContabil") or "",
                "descricao": item.get("descricao") or item.get("historico") or item.get("tipoDocumento") or item.get("notes") or item.get("observacao") or "Título a Pagar",
                "valor": _safe_float(item.get("totalInvoiceAmount") or item.get("valor") or item.get("amount") or item.get("valorTotal") or item.get("valorLiquido") or item.get("valorBruto")),
                "situacao": item.get("situacao") or item.get("status") or "Pendente",
                "creditorName": name,
                "nomeCredor": name,
                "nomeObra": item.get("nomeObra") or building_info.get("name") or (f"Obra {building_id}" if building_id else "Obra sem nome"),
                "documentNumber": item.get("documentNumber") or item.get("numeroDocumento") or item.get("numero") or item.get("codigoTitulo") or "",
                "links": item.get("links") or [],
            }
        )

    normalized_receivable: list[dict[str, Any]] = []
    for item in receber:
        building_id = str(item.get("idObra") or item.get("codigoObra") or item.get("enterpriseId") or item.get("buildingId") or "")
        building_info = building_map.get(building_id, {})
        links = item.get("links") or []
        raw_value = _safe_float(
            item.get("rawValue")
            if item.get("rawValue") is not None
            else item.get("value")
            or item.get("valor")
            or item.get("valorSaldo")
            or item.get("totalInvoiceAmount")
            or item.get("valorTotal")
            or item.get("amount")
        )
        company_id = item.get("companyId") or building_info.get("companyId") or _extract_company_id_from_links(links)
        normalized_receivable.append(
            {
                "id": item.get("id") or item.get("numero") or item.get("numeroTitulo") or item.get("codigoTitulo") or item.get("documentNumber") or 0,
                "companyId": int(company_id) if str(company_id).isdigit() else company_id,
                "buildingId": int(building_id) if building_id.isdigit() else 0,
                "idObra": int(building_id) if building_id.isdigit() else 0,
                "codigoObra": building_id,
                "dataVencimento": item.get("data") or item.get("date") or item.get("dataVencimento") or item.get("dataEmissao") or item.get("issueDate") or item.get("dataVencimentoProjetado") or "",
                "descricao": item.get("descricao") or item.get("historico") or item.get("observacao") or item.get("notes") or item.get("description") or "Título a Receber",
                "nomeCliente": item.get("nomeCliente") or item.get("nomeFantasiaCliente") or item.get("cliente") or item.get("clientName") or "Extrato/Cliente",
                "valor": abs(raw_value),
                "rawValue": raw_value,
                "situacao": str(item.get("situacao") or item.get("status") or "ABERTO").upper(),
                "nomeObra": item.get("nomeObra") or building_info.get("name") or (f"Obra {building_id}" if building_id else "Obra sem nome"),
                "documentId": item.get("documentId") or "",
                "documentNumber": item.get("documentNumber") or "",
                "installmentNumber": item.get("installmentNumber"),
                "statementOrigin": item.get("statementOrigin") or "",
                "statementType": item.get("statementType") or "",
                "billId": item.get("billId"),
                "type": item.get("type") or "Income",
                # bankAccountCode extraído do link rel="bank-account" (ex: ...bank-account/SANTANDER)
                "bankAccountCode": (
                    item.get("bankAccountCode")
                    or next(
                        (lnk["href"].rstrip("/").split("/")[-1]
                         for lnk in links
                         if lnk.get("rel") == "bank-account" and lnk.get("href")),
                        "",
                    )
                ),
                "links": links,
            }
        )

    saldo_bancario = sum(
        _safe_float(item.get("rawValue"))
        for item in normalized_receivable
        if str(item.get("type") or "").strip().lower() != "expense"
    ) - sum(
        _safe_float(item.get("rawValue"))
        for item in normalized_receivable
        if str(item.get("type") or "").strip().lower() == "expense"
    )

    return {
        "obras": list(building_map.values()),
        "usuarios": [_normalize_user(user) for user in usuarios],
        "credores": [_normalize_creditor(credor) for credor in credores],
        "companies": [_normalize_company(company) for company in companies],
        "pedidos": normalized_orders,
        "financeiro": normalized_financial,
        "receber": normalized_receivable,
        "itensPedidos": {str(key): value for key, value in itens_pedidos.items()},
        "saldoBancario": saldo_bancario,
        "latestSync": read_sync_metadata(db),
    }


def _normalize_response_payload(payload: dict[str, Any], db: Session, include_transactions: bool = False) -> BootstrapResponse:
    normalized = _legacy_bootstrap_payload(db, include_transactions=include_transactions)
    if payload.get("latestSync"):
        normalized["latestSync"] = payload["latestSync"]
    if payload.get("itensPedidos"):
        normalized["itensPedidos"] = payload["itensPedidos"]
    return BootstrapResponse(**normalized)


def get_sync_state() -> dict[str, Any]:
    return {
        "running": bool(_SYNC_STATE.get("running")),
        "source": _SYNC_STATE.get("source"),
        "started_at": _SYNC_STATE.get("started_at"),
    }


async def run_sync_once(db: Session, source: str = "manual") -> dict[str, Any]:
    acquired = _SYNC_LOCK.acquire(blocking=False)
    if not acquired:
        latest_sync = read_sync_metadata(db) or {}
        return {
            "latestSync": latest_sync,
            "itensPedidos": _read_cached_dataset(db, "itens_pedidos.json", {}) or {},
            "synced": False,
            "source": latest_sync.get("source") or "cache",
            "in_progress": True,
            "message": "Sincronizacao ja em andamento.",
        }

    _SYNC_STATE["running"] = True
    _SYNC_STATE["source"] = source
    _SYNC_STATE["started_at"] = utc_now_iso()

    try:
        payload = await _perform_sync(db)
        payload["in_progress"] = False
        payload["message"] = (payload.get("latestSync") or {}).get("message")
        return payload
    finally:
        _SYNC_STATE["running"] = False
        _SYNC_STATE["source"] = None
        _SYNC_STATE["started_at"] = None
        _SYNC_LOCK.release()


async def _perform_sync(db: Session) -> dict[str, Any]:
    started_at = utc_now_iso()

    obras = await sienge_client.fetch_obras()
    if obras:
        _write_cached_dataset(db, "obras.json", obras)

    usuarios = await sienge_client.fetch_users()
    if usuarios:
        _write_cached_dataset(db, "usuarios.json", usuarios)

    empresas = await sienge_client.fetch_empresas()
    if empresas:
        _write_cached_dataset(db, "empresas.json", empresas)

    credores = await sienge_client.fetch_credores()
    if credores:
        _write_cached_dataset(db, "credores.json", credores)

    pedidos = await sienge_client.fetch_pedidos()
    if pedidos:
        _write_cached_dataset(db, "pedidos.json", pedidos)

    financeiro = await sienge_client.fetch_financeiro()
    if financeiro:
        _write_cached_dataset(db, "financeiro.json", financeiro)

    receber = await sienge_client.fetch_receber()
    if receber:
        _write_cached_dataset(db, "receber.json", receber)

    itens_pedidos = _read_cached_dataset(db, "itens_pedidos.json", {}) or {}

    if not any([obras, usuarios, empresas, credores, pedidos, financeiro, receber, itens_pedidos]):
        cached_counts = _cache_counts(db)
        has_cache = any(cached_counts.values())
        diagnostic = sienge_client.last_error or {}
        status_code = diagnostic.get("status_code")
        reason = "SIENGE indisponível"
        if status_code == 401:
            reason = "SIENGE retornou 401 (credenciais inválidas/expiradas)"

        metadata = {
            "status": "degraded" if has_cache else "error",
            "started_at": started_at,
            "finished_at": utc_now_iso(),
            "message": (
                f"{reason}. Usando cache local." if has_cache else f"{reason}. Cache local vazio."
            ),
            "counts": cached_counts,
            "source": "cache" if has_cache else "none",
        }
        write_sync_metadata(db, metadata)
        return {
            "latestSync": metadata,
            "itensPedidos": _read_cached_dataset(db, "itens_pedidos.json", {}) or {},
            "synced": False,
            "source": metadata["source"],
        }

    metadata = {
        "status": "success",
        "started_at": started_at,
        "finished_at": utc_now_iso(),
        "message": "Sincronizado com sucesso no Sienge",
        "counts": {
            "obras": len(obras),
            "usuarios": len(usuarios),
            "empresas": len(empresas),
            "credores": len(credores),
            "pedidos": len(pedidos),
            "financeiro": len(financeiro),
            "receber": len(receber),
            "itensPedidos": len(itens_pedidos),
        },
    }
    write_sync_metadata(db, metadata)

    return {
        "latestSync": metadata,
        "itensPedidos": {str(key): value for key, value in itens_pedidos.items()},
        "synced": True,
        "source": "sienge_live",
    }


@router.get("/test")
async def test_connection(db: Session = Depends(get_db)) -> dict[str, Any]:
    try:
        _ = db.scalar(select(Company).limit(1))
        counts = _cache_counts(db)
        has_cache = any(counts.values())
        live_result = await sienge_client.test_connection()
        live = live_result.get("live", {})
        latest_sync = read_sync_metadata(db) or {}
        live_ok = bool(live.get("ok"))
        return {
            "ok": live_ok or has_cache,
            "live": live,
            "cache": counts,
            "latestSync": latest_sync,
            "syncState": get_sync_state(),
            "database": {"ok": True},
        }
    except Exception as e:
        return {
            "ok": False,
            "live": {"ok": False, "error": str(e)},
            "cache": _cache_counts(db),
            "latestSync": read_sync_metadata(db),
            "syncState": get_sync_state(),
            "database": {"ok": False, "error": str(e)},
        }


@router.get("/bootstrap", response_model=BootstrapResponse)
async def bootstrap(
    current_user: AppUser = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> BootstrapResponse:
    # Bootstrap leve: retorna apenas metadados (obras/usuarios/credores).
    # Pedidos/financeiro/receber chegam via /filtered (filtrado, pequeno).
    result = _normalize_response_payload({}, db)
    counts = _cache_counts(db)
    result.cacheReady = counts.get("pedidos", 0) > 0 or counts.get("financeiro", 0) > 0
    result.cacheCounts = counts
    return result


@router.post("/sync")
async def sync(
    current_user: AppUser = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    payload = await run_sync_once(db, source="manual")
    latest_sync = payload.get("latestSync", {})
    synced = bool(payload.get("synced", False))
    in_progress = bool(payload.get("in_progress", False))
    degraded = latest_sync.get("status") == "degraded"
    return {
        "status": "in_progress" if in_progress else ("ok" if synced else ("degraded" if degraded else "error")),
        "message": (
            payload.get("message")
            or latest_sync.get("message")
            or ("Sync completed from Sienge API" if synced else "Sync executado com fallback")
        ),
        "synced": synced,
        "in_progress": in_progress,
        "syncState": get_sync_state(),
        "source": payload.get("source", "unknown"),
        "latestSync": latest_sync,
        "data": latest_sync.get("counts", {}),
    }


@router.get("/filtered")
async def filtered_data(
    start_date: str | None = None,
    end_date: str | None = None,
    company_id: str = "all",
    building_id: str = "all",
    user_id: str = "all",
    requester_id: str = "all",
    current_user: AppUser = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    if start_date:
        _validate_iso_date(start_date, "start_date")
    if end_date:
        _validate_iso_date(end_date, "end_date")
    if start_date and end_date and end_date < start_date:
        raise HTTPException(status_code=422, detail="end_date deve ser >= start_date")

    # Cache incremental: se pedirem um range fora do cache, baixa só o delta.
    if start_date and end_date and sienge_client.is_configured:
        await _ensure_cached_dataset_range(
            db=db,
            dataset_key="pedidos",
            start_date=start_date,
            end_date=end_date,
            fetcher=sienge_client.fetch_pedidos_range,
            date_fields_for_infer=["data", "dataEmissao", "date"],
        )
        await _ensure_cached_dataset_range(
            db=db,
            dataset_key="financeiro",
            start_date=start_date,
            end_date=end_date,
            fetcher=sienge_client.fetch_financeiro_range,
            date_fields_for_infer=[
                "dataVencimento",
                "dueDate",
                "issueDate",
                "dataEmissao",
                "dataContabil",
            ],
        )
        await _ensure_cached_dataset_range(
            db=db,
            dataset_key="receber",
            start_date=start_date,
            end_date=end_date,
            fetcher=sienge_client.fetch_receber_range,
            date_fields_for_infer=[
                "dataVencimento",
                "dueDate",
                "data",
                "date",
                "issueDate",
                "dataEmissao",
            ],
        )

    payload = _legacy_bootstrap_payload(db)

    obras = _to_array(payload.get("obras", []))
    pedidos = _to_array(payload.get("pedidos", []))
    financeiro = _to_array(payload.get("financeiro", []))
    receber = _to_array(payload.get("receber", []))

    building_company_map: dict[str, str] = {}
    for obra in obras:
        cid = str(obra.get("companyId") or obra.get("idCompany") or "")
        if not cid:
            continue
        id_candidates = {
            str(obra.get("id") or ""),
            str(obra.get("code") or ""),
            str(obra.get("codigoVisivel") or ""),
            str(obra.get("codigo") or ""),
        }
        for bid in id_candidates:
            if bid and bid not in {"None", "undefined"}:
                building_company_map[bid] = cid

    start_ms = _date_start_ms(start_date)
    end_exclusive_ms = _date_end_exclusive_ms(end_date)

    building_aliases: set[str] | None = None
    if building_id != "all":
        normalized_buildings = [_normalize_building(obra) for obra in obras]
        selected = next(
            (
                b
                for b in normalized_buildings
                if str(b.get("id") or "") == building_id
                or str(b.get("code") or "") == building_id
                or str(b.get("codigoVisivel") or "") == building_id
            ),
            None,
        )
        if selected:
            building_aliases = {
                str(selected.get("id") or ""),
                str(selected.get("code") or ""),
                str(selected.get("codigoVisivel") or ""),
            }
            building_aliases = {bid for bid in building_aliases if bid and bid not in {"None", "undefined"}}
        else:
            building_aliases = {building_id}

    def matches_building(item: dict[str, Any]) -> bool:
        if building_aliases is None:
            return True
        bid = str(
            item.get("buildingId")
            or item.get("idObra")
            or item.get("codigoVisivelObra")
            or item.get("codigoObra")
            or item.get("enterpriseId")
            or ""
        )
        return bid in building_aliases

    def _auth_fingerprint() -> str:
        raw = f"{getattr(sienge_client, 'access_name', '')}:{getattr(sienge_client, 'token', '')}"
        return hashlib.sha1(raw.encode("utf-8")).hexdigest()[:10]

    async def _ensure_buildings_cost_cached(
        bill_ids: list[str],
        *,
        max_concurrency: int = 8,
        time_budget_s: int = 12,
        max_fetch: int = 200,
    ) -> None:
        """Busca rateios faltantes e cacheia em snapshots.

        Mantém hard cap de tempo para evitar travar a UI.
        """
        if not bill_ids or not sienge_client.is_configured:
            return

        cursor_key = "bills_buildings_cost_cursor.json"
        cursor_payload = read_snapshot(db, cursor_key, default={}) or {}
        try:
            cursor = int(cursor_payload.get("cursor") or 0)
        except (TypeError, ValueError):
            cursor = 0

        negative_404_ttl_s = 24 * 60 * 60
        auth_fp = _auth_fingerprint()

        to_fetch: list[str] = []
        seen_local: set[str] = set()
        for bid in bill_ids:
            if not bid or bid in {"None", "undefined", "null", "0"}:
                continue
            if bid in seen_local:
                continue
            seen_local.add(bid)
            key = _bill_buildings_cost_cache_key(bid)
            cached = read_snapshot(db, key, default=None)
            if cached is None:
                to_fetch.append(bid)
                continue

            # Negative cache para 404 (evita refetch infinito).
            if isinstance(cached, dict) and cached.get("_status") == 404:
                cached_at = str(cached.get("_cached_at") or "")
                cached_fp = str(cached.get("_auth_fp") or "")
                try:
                    age_s = (datetime.now() - datetime.fromisoformat(cached_at.replace("Z", "+00:00"))).total_seconds()
                except Exception:
                    age_s = None
                if cached_fp != auth_fp or age_s is None or age_s > negative_404_ttl_s:
                    to_fetch.append(bid)

        if not to_fetch:
            return

        # Cursor para varrer progressivamente a lista (se a UI repetir o filtro,
        # seguimos de onde parou, em vez de sempre pegar os mesmos billIds).
        if to_fetch:
            start = cursor % len(to_fetch)
            to_fetch = to_fetch[start:] + to_fetch[:start]

        to_fetch = to_fetch[: max_fetch if max_fetch > 0 else 0]
        if not to_fetch:
            return

        started = datetime.now()
        processed_fetch = 0

        async def _fetch_one(bid: str, client: httpx.AsyncClient) -> None:
            payload, err = await sienge_client.fetch_bill_buildings_cost_with_client_detailed(client, bid)
            nonlocal processed_fetch
            processed_fetch += 1
            if payload is not None and err is None:
                write_snapshot(db, _bill_buildings_cost_cache_key(bid), payload)
                return
            if isinstance(err, dict) and err.get("status_code") == 404:
                write_snapshot(
                    db,
                    _bill_buildings_cost_cache_key(bid),
                    {
                        "_status": 404,
                        "_cached_at": utc_now_iso(),
                        "_endpoint": err.get("endpoint"),
                        "_auth_fp": auth_fp,
                    },
                )

        async with httpx.AsyncClient(timeout=sienge_client.timeout) as client:
            idx = 0
            while idx < len(to_fetch):
                if (datetime.now() - started).total_seconds() >= time_budget_s:
                    break
                batch = to_fetch[idx : idx + max_concurrency]
                idx += len(batch)
                await asyncio.gather(*[asyncio.create_task(_fetch_one(bid, client)) for bid in batch], return_exceptions=True)

        if processed_fetch:
            write_snapshot(db, cursor_key, {"cursor": cursor + processed_fetch, "updated_at": utc_now_iso()})

    def _bill_weights(bill_id: str) -> list[tuple[str, float]]:
        if not bill_id:
            return []
        cached = read_snapshot(db, _bill_buildings_cost_cache_key(bill_id), default=None)
        rows = _extract_buildings_cost_rows(cached)
        return _weights_from_buildings_cost(rows)

    def _select_allocations(bill_id: str, amount: float) -> list[tuple[str, float]]:
        weights = _bill_weights(bill_id)
        if not weights:
            return []
        total = sum(abs(w) for _, w in weights) or 0.0
        if total <= 0:
            return []
        out: list[tuple[str, float]] = []
        for bid, w in weights:
            frac = abs(w) / total
            out.append((bid, amount * frac))
        return out

    def order_company(order: dict[str, Any]) -> str:
        direct = order.get("companyId")
        if direct is not None and str(direct) not in {"", "None", "undefined"}:
            return str(direct)

        # Fallback: alguns payloads carregam company apenas via links
        links = order.get("links") or []
        if isinstance(links, list):
            linked = _extract_company_id_from_links(links)
            if linked is not None:
                return str(linked)

        bid = str(
            order.get("buildingId")
            or order.get("buildingCode")
            or order.get("idObra")
            or order.get("codigoVisivelObra")
            or order.get("codigoObra")
            or order.get("enterpriseId")
            or ""
        )
        return building_company_map.get(bid, "")

    filtered_orders = []
    for order in pedidos:
        date_numeric = _to_date_number(order.get("date") or order.get("dataEmissao"))
        if not _in_range(date_numeric, start_ms, end_exclusive_ms):
            continue
        if company_id != "all" and order_company(order) != company_id:
            continue
        if not matches_building(order):
            continue
        if user_id != "all" and str(order.get("buyerId") or order.get("idComprador") or "") != user_id:
            continue
        if requester_id != "all" and str(order.get("requesterId") or order.get("solicitante") or "") != requester_id:
            continue
        filtered_orders.append(order)

    def financial_company(item: dict[str, Any]) -> str:
        direct = item.get("companyId")
        if direct is None:
            direct = item.get("company_id")
        if direct is not None and str(direct) not in {"", "None", "undefined"}:
            return str(direct)

        # Fallback: alguns títulos retornam companyId apenas no links rel=company
        links = item.get("links") or []
        if isinstance(links, list):
            linked = _extract_company_id_from_links(links)
            if linked is not None:
                return str(linked)

        bid = str(
            item.get("buildingId")
            or item.get("buildingCode")
            or item.get("idObra")
            or item.get("codigoVisivelObra")
            or item.get("codigoObra")
            or item.get("enterpriseId")
            or ""
        )
        return building_company_map.get(bid, "")

    filtered_financial = []
    if building_aliases is None:
        for item in financeiro:
            date_numeric = _to_date_number(
                item.get("dataVencimento")
                or item.get("dueDate")
                or item.get("issueDate")
                or item.get("dataVencimentoProjetado")
                or item.get("dataEmissao")
                or item.get("dataContabil")
            )
            if not _in_range(date_numeric, start_ms, end_exclusive_ms):
                continue
            if company_id != "all" and financial_company(item) != company_id:
                continue
            filtered_financial.append(item)
    else:
        # Rateio por obra via buildings-cost (bills geralmente não têm obra direta).
        bill_ids: list[str] = []
        seen_bill_ids: set[str] = set()
        for item in financeiro:
            date_numeric = _to_date_number(
                item.get("dataVencimento")
                or item.get("dueDate")
                or item.get("issueDate")
                or item.get("dataVencimentoProjetado")
                or item.get("dataEmissao")
                or item.get("dataContabil")
            )
            if not _in_range(date_numeric, start_ms, end_exclusive_ms):
                continue
            if company_id != "all" and financial_company(item) != company_id:
                continue
            bid = str(item.get("id") or item.get("billId") or item.get("bill_id") or "").strip()
            if bid and bid not in seen_bill_ids:
                seen_bill_ids.add(bid)
                bill_ids.append(bid)

        await _ensure_buildings_cost_cached(bill_ids)

        for item in financeiro:
            date_numeric = _to_date_number(
                item.get("dataVencimento")
                or item.get("dueDate")
                or item.get("issueDate")
                or item.get("dataVencimentoProjetado")
                or item.get("dataEmissao")
                or item.get("dataContabil")
            )
            if not _in_range(date_numeric, start_ms, end_exclusive_ms):
                continue
            if company_id != "all" and financial_company(item) != company_id:
                continue
            bill_id = str(item.get("id") or item.get("billId") or item.get("bill_id") or "").strip()
            amount = _safe_float(item.get("valor") or item.get("amount") or item.get("value") or 0)
            for alloc_building, alloc_amount in _select_allocations(bill_id, amount):
                if alloc_building not in building_aliases:
                    continue
                cloned = dict(item)
                cloned["buildingId"] = int(alloc_building) if alloc_building.isdigit() else 0
                cloned["idObra"] = int(alloc_building) if alloc_building.isdigit() else 0
                cloned["codigoObra"] = alloc_building
                cloned["valor"] = alloc_amount
                filtered_financial.append(cloned)

    filtered_receber = []
    if building_aliases is None:
        for item in receber:
            date_numeric = _to_date_number(
                item.get("dataVencimento")
                or item.get("dueDate")
                or item.get("data")
                or item.get("date")
                or item.get("dataEmissao")
                or item.get("issueDate")
                or item.get("dataVencimentoProjetado")
            )
            if not _in_range(date_numeric, start_ms, end_exclusive_ms):
                continue
            if company_id != "all" and financial_company(item) != company_id:
                continue
            filtered_receber.append(item)
    else:
        bill_ids: list[str] = []
        seen_bill_ids: set[str] = set()
        for item in receber:
            date_numeric = _to_date_number(
                item.get("dataVencimento")
                or item.get("dueDate")
                or item.get("data")
                or item.get("date")
                or item.get("dataEmissao")
                or item.get("issueDate")
                or item.get("dataVencimentoProjetado")
            )
            if not _in_range(date_numeric, start_ms, end_exclusive_ms):
                continue
            if company_id != "all" and financial_company(item) != company_id:
                continue
            bid = str(item.get("billId") or item.get("bill_id") or "").strip()
            if bid and bid not in seen_bill_ids:
                seen_bill_ids.add(bid)
                bill_ids.append(bid)

        await _ensure_buildings_cost_cached(bill_ids)

        for item in receber:
            date_numeric = _to_date_number(
                item.get("dataVencimento")
                or item.get("dueDate")
                or item.get("data")
                or item.get("date")
                or item.get("dataEmissao")
                or item.get("issueDate")
                or item.get("dataVencimentoProjetado")
            )
            if not _in_range(date_numeric, start_ms, end_exclusive_ms):
                continue
            if company_id != "all" and financial_company(item) != company_id:
                continue
            bill_id = str(item.get("billId") or item.get("bill_id") or "").strip()
            raw_value = _safe_float(item.get("rawValue") if item.get("rawValue") is not None else item.get("valor") or item.get("amount") or 0)
            for alloc_building, alloc_amount in _select_allocations(bill_id, raw_value):
                if alloc_building not in building_aliases:
                    continue
                cloned = dict(item)
                cloned["buildingId"] = int(alloc_building) if alloc_building.isdigit() else 0
                cloned["idObra"] = int(alloc_building) if alloc_building.isdigit() else 0
                cloned["codigoObra"] = alloc_building
                cloned["rawValue"] = alloc_amount
                cloned["valor"] = abs(alloc_amount)
                filtered_receber.append(cloned)

    return {
        "pedidos": filtered_orders,
        "financeiro": filtered_financial,
        "receber": filtered_receber,
        "latestSync": payload.get("latestSync"),
        "filters": {
            "start_date": start_date,
            "end_date": end_date,
            "company_id": company_id,
            "user_id": user_id,
            "requester_id": requester_id,
        },
        "counts": {
            "pedidos": len(filtered_orders),
            "financeiro": len(filtered_financial),
            "receber": len(filtered_receber),
        },
    }


@router.get("/mc-by-building")
async def mc_by_building(
    start_date: str | None = None,
    end_date: str | None = None,
    company_id: str = "all",
    building_id: str = "all",
    user_id: str = "all",
    requester_id: str = "all",
    top: int = Query(5, ge=1, le=50),
    debug: bool = Query(False, description="Quando true, inclui diagnóstico detalhado do rateio por obra"),
    time_budget_seconds: int = Query(90, ge=10, le=240, description="Tempo máximo (s) para buscar rateios faltantes antes de responder"),
    max_concurrency: int = Query(10, ge=2, le=50, description="Concorrência máxima de chamadas ao Sienge (valores altos tendem a gerar 429)"),
    current_user: AppUser = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    """TOP obras por Receita Operacional, com MC e %MC.

    Receita Operacional: soma de títulos a receber que parecem NF (heurística do front).
    Custos: despesas do extrato bancário (accounts-statements) com type=Expense.
    Rateio por obra: via GET /bills/{billId}/buildings-cost (cacheado em snapshot).
    """

    # IMPORTANTE:
    # Os títulos a pagar (bills) frequentemente NÃO trazem vínculo direto com obra.
    # Se aplicarmos company_id/building_id aqui, podemos zerar o financeiro e quebrar
    # o rateio por obra (buildings-cost). Portanto, buscamos o dataset base SEM esses
    # filtros e deixamos o serviço aplicar a filtragem no nível da OBRA após o rateio.
    filtered = await filtered_data(
        start_date=start_date,
        end_date=end_date,
        company_id="all",
        building_id="all",
        user_id=user_id,
        requester_id=requester_id,
        current_user=current_user,
        db=db,
    )
    filtered.setdefault("filters", {})
    filtered["filters"].update(
        {
            "company_id": company_id,
            "building_id": building_id,
            "user_id": user_id,
            "requester_id": requester_id,
        }
    )

    return await compute_mc_by_building(
        filtered=filtered,
        db=db,
        top=top,
        debug=debug,
        time_budget_seconds=time_budget_seconds,
        max_concurrency=max_concurrency,
    )


@router.post("/fetch-items")
async def fetch_items(
    payload: FetchItemsRequest,
    current_user: AppUser = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> dict[str, list[dict]]:
    try:
        items_map = _read_cached_dataset(db, "itens_pedidos.json", {}) or {}
        changed = False
        requested_ids = {str(order_id) for order_id in payload.ids}

        for order_id in payload.ids:
            key = str(order_id)
            if items_map.get(key):
                continue
            items = await sienge_client.fetch_purchase_order_items(order_id)
            if items:
                items_map[key] = items
                changed = True

        if changed:
            _write_cached_dataset(db, "itens_pedidos.json", items_map)

        return {str(key): value for key, value in items_map.items() if str(key) in requested_ids}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e)) from e


@router.post("/fetch-quotations")
async def fetch_quotations(
    payload: FetchQuotationsRequest,
    current_user: AppUser = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    try:
        target_ids = {str(order_id) for order_id in payload.ids}
        quotations_map = _read_cached_dataset(db, "cotacoes_pedidos.json", {}) or {}
        items_map = _read_cached_dataset(db, "itens_pedidos.json", {}) or {}
        pedidos = _to_array(_read_cached_dataset(db, "pedidos.json", []))
        pedido_lookup = {
            str(item.get("id") or item.get("numero")): item
            for item in pedidos
            if item.get("id") or item.get("numero")
        }
        changed = False

        def build_quote(oid: str, order_info: dict[str, Any], order_items: list[dict]) -> dict[str, Any]:
            supplier_id = order_info.get("supplierId") or order_info.get("codigoFornecedor")
            return {
                "orderId": int(oid) if oid.isdigit() else 0,
                "supplierId": supplier_id,
                "creditorId": supplier_id,
                "supplierName": order_info.get("nomeFornecedor"),
                "date": order_info.get("date") or order_info.get("dataEmissao") or "",
                "totalAmount": _safe_float(order_info.get("totalAmount") or order_info.get("valorTotal")),
                "items": [
                    {
                        "description": item.get("resourceDescription") or item.get("descricao") or "",
                        "resourceId": item.get("resourceId"),
                        "unitPrice": _safe_float(item.get("netPrice") or item.get("unitPrice") or item.get("valorUnitario")),
                        "quantity": _safe_float(item.get("quantity") or item.get("quantidade")),
                        "unitOfMeasure": item.get("unitOfMeasure") or item.get("unidadeMedidaSigla") or "",
                        "quotationIds": [pq.get("purchaseQuotationId") for pq in (item.get("purchaseQuotations") or [])],
                    }
                    for item in order_items
                ],
            }

        quotation_index: dict[int, list[str]] = {}
        for oid, order_items in items_map.items():
            if not isinstance(order_items, list):
                continue
            for item in order_items:
                for quotation in item.get("purchaseQuotations") or []:
                    quotation_id = quotation.get("purchaseQuotationId")
                    if quotation_id:
                        quotation_index.setdefault(int(quotation_id), [])
                        if oid not in quotation_index[int(quotation_id)]:
                            quotation_index[int(quotation_id)].append(oid)

        for order_id in payload.ids:
            key = str(order_id)
            if quotations_map.get(key):
                continue

            order_items = items_map.get(key)
            if not order_items:
                order_items = await sienge_client.fetch_purchase_order_items(order_id)
                if order_items:
                    items_map[key] = order_items
                    changed = True

            if not isinstance(order_items, list) or not order_items:
                quotations_map[key] = []
                changed = True
                continue

            quotation_ids: set[int] = set()
            for item in order_items:
                for quotation in item.get("purchaseQuotations") or []:
                    quotation_id = quotation.get("purchaseQuotationId")
                    if quotation_id:
                        quotation_ids.add(int(quotation_id))

            if not quotation_ids:
                quotations_map[key] = []
                changed = True
                continue

            competitor_ids: set[str] = set()
            for quotation_id in quotation_ids:
                for candidate_order_id in quotation_index.get(quotation_id, []):
                    if candidate_order_id != key:
                        competitor_ids.add(candidate_order_id)

            competitor_quotes: list[dict[str, Any]] = []
            for competitor_id in competitor_ids:
                competitor_items = items_map.get(competitor_id)
                if not competitor_items and competitor_id.isdigit():
                    fetched_items = await sienge_client.fetch_purchase_order_items(int(competitor_id))
                    if fetched_items:
                        competitor_items = fetched_items
                        items_map[competitor_id] = fetched_items
                        changed = True
                if competitor_items:
                    competitor_quotes.append(build_quote(competitor_id, pedido_lookup.get(competitor_id, {}), competitor_items))

            quotation_meta = await sienge_client.fetch_purchase_quotation(next(iter(quotation_ids)))
            winning_order = pedido_lookup.get(key, {})
            competitor_quotes.append(build_quote(key, winning_order, order_items))
            competitor_quotes.sort(key=lambda item: item.get("orderId") or 0)

            quotations_map[key] = {
                "quotes": competitor_quotes,
                "quotationIds": sorted(quotation_ids),
                "quotationMeta": quotation_meta,
                "winningSupplier": winning_order.get("supplierId") or winning_order.get("codigoFornecedor"),
            }
            changed = True

        if changed:
            _write_cached_dataset(db, "itens_pedidos.json", items_map)
            _write_cached_dataset(db, "cotacoes_pedidos.json", quotations_map)

        return {key: value for key, value in quotations_map.items() if key in target_ids}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e)) from e
