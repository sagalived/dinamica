import React, { useEffect, useMemo, useState } from 'react';
import { motion } from 'framer-motion';
import { TrendingUp, DollarSign, Building2, Package, Percent } from 'lucide-react';
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from '../../components/ui/card';
import { Table, TableBody, TableCell, TableFooter, TableHead, TableHeader, TableRow } from '../../components/ui/table';
import { cn } from '../../lib/utils';
import { sienge as siengeApi } from '../../lib/api';
import {
  ResponsiveContainer, AreaChart, Area, XAxis, YAxis, Tooltip, Legend,
  PieChart, Pie, Cell
} from 'recharts';
import { useSienge } from '../../contexts/SiengeContext';
import { addMonths, format, parseISO } from 'date-fns';
import { toMoney, translateStatusLabel } from '../financeiro/logic';

import type { McByBuildingResponse } from './types';

export function DashboardGeral() {
  const {
    orders,
    financialTitles,
    receivableTitles,
    nfeDocuments,
    fcSelectedBuilding,
    selectedCompany,
    selectedUser,
    selectedRequester,
    companies,
    dataRevision,
    activeBuildingCount,
    startDate,
    endDate,
  } = useSienge();

  const toNumberSafe = (value: any): number => {
    if (typeof value === 'number') return Number.isFinite(value) ? value : NaN;
    if (typeof value !== 'string') return Number(value);
    const raw = value.trim();
    if (!raw) return NaN;
    // aceita: "1234.56", "1.234,56", "1,234.56", "1234,56"
    const cleaned = raw
      .replace(/\s/g, '')
      .replace(/R\$/gi, '')
      .replace(/%/g, '');

    const hasComma = cleaned.includes(',');
    const hasDot = cleaned.includes('.');
    if (hasComma && hasDot) {
      // assume o separador decimal é o ÚLTIMO entre '.' e ','
      const lastComma = cleaned.lastIndexOf(',');
      const lastDot = cleaned.lastIndexOf('.');
      const decimalSep = lastComma > lastDot ? ',' : '.';
      const thousandsSep = decimalSep === ',' ? '.' : ',';
      const normalized = cleaned
        .split(thousandsSep).join('')
        .replace(decimalSep, '.');
      return Number(normalized);
    }
    if (hasComma && !hasDot) {
      return Number(cleaned.replace(',', '.'));
    }
    // só ponto, ou nenhum
    return Number(cleaned);
  };

  const [mcByBuildingResp, setMcByBuildingResp] = useState<McByBuildingResponse>({
    rows: [],
    total: { receita_operacional: 0, mc: 0, mc_percent: 0 },
  });
  const [mcByBuildingLoading, setMcByBuildingLoading] = useState(false);

  useEffect(() => {
    let cancelled = false;

    const normalizeFilter = (value: any): string => {
      const str = String(value ?? '').trim();
      if (!str) return 'all';
      const lowered = str.toLowerCase();
      if (lowered === 'undefined' || lowered === 'null') return 'all';
      return str;
    };

    const run = async () => {
      setMcByBuildingLoading(true);
      try {
        const now = new Date();
        const defaultEnd = new Date(now.getFullYear(), now.getMonth(), now.getDate());
        const defaultStart = addMonths(defaultEnd, -6);
        const effectiveStart = startDate || defaultStart;
        const effectiveEnd = endDate || startDate || defaultEnd;

        // Rows (Top 5) não sofrem influência de filtro.
        const rowsParams: any = {
          company_id: 'all',
          building_id: 'all',
          user_id: 'all',
          requester_id: 'all',
          start_date: format(effectiveStart, 'yyyy-MM-dd'),
          end_date: format(effectiveEnd, 'yyyy-MM-dd'),
          top: 5,
          time_budget_seconds: 15,
          max_concurrency: 4,
        };
        // Total respeita filtros (empresa/obra/usuário/solicitante), mas sem data.
        const totalParams: any = {
          company_id: normalizeFilter(selectedCompany),
          building_id: normalizeFilter(fcSelectedBuilding),
          user_id: normalizeFilter(selectedUser),
          requester_id: normalizeFilter(selectedRequester),
          start_date: format(effectiveStart, 'yyyy-MM-dd'),
          end_date: format(effectiveEnd, 'yyyy-MM-dd'),
          top: 5,
          time_budget_seconds: 15,
          max_concurrency: 4,
        };

        const [{ data: rowsData }, { data: totalData }] = await Promise.all([
          siengeApi.get('/mc-by-building', { params: rowsParams }),
          siengeApi.get('/mc-by-building', { params: totalParams }),
        ]);
        if (cancelled) return;
        setMcByBuildingResp({
          rows: Array.isArray(rowsData?.rows) ? rowsData.rows : [],
          total: totalData?.total || { receita_operacional: 0, mc: 0, mc_percent: 0 },
          diagnostic: {
            rows: rowsData?.diagnostic,
            total: totalData?.diagnostic,
          },
        });
      } catch {
        if (cancelled) return;
        setMcByBuildingResp({ rows: [], total: { receita_operacional: 0, mc: 0, mc_percent: 0 } });
      } finally {
        if (!cancelled) setMcByBuildingLoading(false);
      }
    };

    run();
    return () => {
      cancelled = true;
    };
  }, [dataRevision, endDate, fcSelectedBuilding, selectedCompany, selectedRequester, selectedUser, startDate]);

  const stats = useMemo(() => {
    const ordersArray = Array.isArray(orders) ? orders : [];
    const total = ordersArray.reduce((acc: number, curr: any) => acc + toMoney(curr.totalAmount), 0);
    const avg = ordersArray.length > 0 ? total / ordersArray.length : 0;

    const receivableArray = Array.isArray(receivableTitles) ? receivableTitles : [];

    const isExpense = (t: any): boolean => {
      const type = String(t?.type || '').trim().toLowerCase();
      if (type === 'expense') return true;
      const rv = Number(t?.rawValue);
      return Number.isFinite(rv) && rv < 0;
    };

    const isNotaFiscalIncome = (t: any): boolean => {
      const type = String(t?.type || '').trim().toLowerCase();
      if (!type) return false;
      if (type === 'expense') return false;
      const documentId = String(t?.documentId || '').trim().toUpperCase();
      const documentNumber = String(t?.documentNumber || '').trim().toUpperCase();
      return documentId.includes('NF') || documentNumber.includes('NF');
    };

    const receitaOperacionalReceber = receivableArray
      .filter(isNotaFiscalIncome)
      .reduce((acc: number, curr: any) => acc + Math.abs(toMoney(curr.rawValue ?? curr.amount ?? curr.valor)), 0);

    const nfeArray = Array.isArray(nfeDocuments) ? nfeDocuments : [];
    const receitaOperacionalNfe = nfeArray.reduce((acc: number, doc: any) => {
      // O payload do Sienge pode variar; tentamos os campos mais comuns.
      const raw =
        doc?.totalInvoiceAmount ??
        doc?.totalAmount ??
        doc?.amount ??
        doc?.valorTotal ??
        doc?.valor ??
        doc?.valorTotalNota ??
        doc?.valorTotalNfe ??
        doc?.valorTotalNFe ??
        doc?.valorTotalDocumentoFiscal ??
        doc?.valorDocumentoFiscal;
      return acc + toMoney(raw);
    }, 0);

    // Regra prática para garantir filtro por OBRA:
    // - Se há obra selecionada, usamos `receber` (já vem filtrado por obra/datas via /filtered).
    // - Se não há obra selecionada, preferimos NF-e; se não vier valor, cai no `receber`.
    const receitaOperacional = fcSelectedBuilding !== 'all'
      ? receitaOperacionalReceber
      : (receitaOperacionalNfe > 0 ? receitaOperacionalNfe : receitaOperacionalReceber);
    
    const fTotal = financialTitles.reduce((acc: number, curr: any) => acc + toMoney(curr.amount), 0);
    const rTotal = receivableTitles.reduce((acc: number, curr: any) => acc + toMoney(curr.amount), 0);
    const balance = rTotal - fTotal;

    // Margem de Contribuição (aproximação operacional):
    // Receita (NF) - Custos (despesas do extrato: type=Expense).
    // Usar extrato evita distorções quando /bills não cobre o período/filtros.
    const cpv = receivableArray
      .filter(isExpense)
      .reduce((acc: number, curr: any) => acc + Math.abs(toMoney(curr.rawValue ?? curr.amount ?? curr.valor)), 0);
    const margemContribuicao = receitaOperacional - cpv;

    return { total, avg, receitaOperacional, fTotal, rTotal, balance, cpv, margemContribuicao };
  }, [orders, financialTitles, receivableTitles, nfeDocuments, fcSelectedBuilding]);

  const receitaMargemSeries = useMemo(() => {
    const receivableArray = Array.isArray(receivableTitles) ? receivableTitles : [];
    // Para o dashboard, custos vêm do extrato (Expense), não de /bills.

    const monthKey = (d: Date) => `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, '0')}`;
    const monthLabel = (d: Date) => d.toLocaleDateString('pt-BR', { month: 'short' }).replace('.', '');

    const parseDateSafe = (raw: any): Date | null => {
      const str = String(raw || '').trim();
      if (!str || str === '---') return null;
      try {
        const d = parseISO(str);
        return Number.isNaN(d.getTime()) ? null : d;
      } catch {
        return null;
      }
    };

    const isNotaFiscalIncome = (t: any): boolean => {
      const type = String(t?.type || '').trim().toLowerCase();
      if (!type) return false;
      if (type === 'expense') return false;
      const documentId = String(t?.documentId || '').trim().toUpperCase();
      const documentNumber = String(t?.documentNumber || '').trim().toUpperCase();
      return documentId.includes('NF') || documentNumber.includes('NF');
    };

    const isExpense = (t: any): boolean => {
      const type = String(t?.type || '').trim().toLowerCase();
      if (type === 'expense') return true;
      const rv = Number(t?.rawValue);
      return Number.isFinite(rv) && rv < 0;
    };

    const getDate = (t: any): Date | null => {
      const numeric = Number(t?.dueDateNumeric) || 0;
      if (numeric) {
        const d = new Date(numeric);
        return Number.isNaN(d.getTime()) ? null : d;
      }
      return parseDateSafe(t?.dueDate);
    };

    // Janela temporal: usa o mesmo range efetivo do contexto
    // (manual quando selecionado; senão últimos 6 meses).
    const now = new Date();
    const defaultEnd = new Date(now.getFullYear(), now.getMonth(), now.getDate());
    const defaultStart = addMonths(defaultEnd, -6);
    const effectiveStart = startDate || defaultStart;
    const effectiveEnd = endDate || startDate || defaultEnd;

    const startMonth = new Date(effectiveStart.getFullYear(), effectiveStart.getMonth(), 1);
    const endMonth = new Date(effectiveEnd.getFullYear(), effectiveEnd.getMonth(), 1);
    const months: { key: string; label: string }[] = [];
    for (let d = new Date(startMonth); d.getTime() <= endMonth.getTime(); d = new Date(d.getFullYear(), d.getMonth() + 1, 1)) {
      months.push({ key: monthKey(d), label: monthLabel(d) });
      // segurança: evita loop infinito em caso de data inválida
      if (months.length > 48) break;
    }

    const receitaByMonth: Record<string, number> = {};
    receivableArray.filter(isNotaFiscalIncome).forEach((t: any) => {
      const d = getDate(t);
      if (!d) return;
      const key = monthKey(d);
      receitaByMonth[key] = (receitaByMonth[key] || 0) + Math.abs(toMoney(t?.rawValue ?? t?.amount ?? 0));
    });

    const cpvByMonth: Record<string, number> = {};
    receivableArray.filter(isExpense).forEach((t: any) => {
      const d = getDate(t);
      if (!d) return;
      const key = monthKey(d);
      cpvByMonth[key] = (cpvByMonth[key] || 0) + Math.abs(toMoney(t?.rawValue ?? t?.amount ?? 0));
    });

    const receitaChart = months.map((m) => ({ name: m.label, valor: receitaByMonth[m.key] || 0 }));
    const margemChart = months.map((m) => ({
      name: m.label,
      valor: (receitaByMonth[m.key] || 0) - (cpvByMonth[m.key] || 0),
    }));

    const mcPercentChart = months.map((m) => {
      const receita = receitaByMonth[m.key] || 0;
      const margem = receita - (cpvByMonth[m.key] || 0);
      const pct = receita > 0 ? (margem / receita) * 100 : 0;
      return { name: m.label, valor: pct };
    });

    const bestMonth = (series: { name: string; valor: number }[]) => {
      let best = { name: '-', valor: 0 };
      series.forEach((p) => {
        if (p.valor > best.valor) best = p;
      });
      return best;
    };

    return {
      receitaChart,
      margemChart,
      mcPercentChart,
      bestReceita: bestMonth(receitaChart),
      bestMargem: bestMonth(margemChart),
      bestMcPercent: bestMonth(mcPercentChart),
    };
  }, [endDate, financialTitles, receivableTitles, startDate]);

  const mcGeralPercent = useMemo(() => {
    const total = mcByBuildingResp.total || { receita_operacional: 0, mc: 0, mc_percent: 0 };
    if (total?.mc_percent != null) {
      const v = toNumberSafe(total.mc_percent);
      return Number.isFinite(v) ? v : 0;
    }
    const receita = toNumberSafe(total?.receita_operacional || 0);
    const mc = toNumberSafe(total?.mc || 0);
    return receita > 0 ? (mc / receita) * 100 : 0;
  }, [mcByBuildingResp.total]);

  const resumoPorObra = useMemo(() => {
    const rows = (mcByBuildingResp.rows || []).map((r) => {
      const receita = toNumberSafe(r?.receita_operacional || 0);
      const mc = toNumberSafe(r?.mc || 0);
      const pct = toNumberSafe(r?.mc_percent || 0);
      const name = String(r?.building_name || r?.building_id || 'Obra');
      return { id: String(r?.building_id || name), name, receita, mc, pct };
    });

    const total = mcByBuildingResp.total || { receita_operacional: 0, mc: 0, mc_percent: 0 };
    const maxReceita = Math.max(1, ...rows.map((r) => r.receita));
    const maxMcAbs = Math.max(1, ...rows.map((r) => Math.abs(r.mc)));

    return {
      rows,
      total: {
        receita: toNumberSafe(total.receita_operacional || 0),
        mc: toNumberSafe(total.mc || 0),
        pct: toNumberSafe(total.mc_percent || 0),
      },
      maxReceita,
      maxMcAbs,
    };
  }, [mcByBuildingResp.rows, mcByBuildingResp.total]);

  const orderStatusData = useMemo(() => {
    const map: Record<string, number> = {};
    const ordersArray = Array.isArray(orders) ? orders : [];
    ordersArray.forEach((o: any) => {
      const status = translateStatusLabel(o.status) || 'N/D';
      map[status] = (map[status] || 0) + 1;
    });
    return Object.entries(map).map(([name, value]) => ({ name, value })).sort((a,b) => b.value - a.value);
  }, [orders]);

  const kpiReceitaOperacional = useMemo(() => {
    const total = mcByBuildingResp.total;
    const v = toNumberSafe(total?.receita_operacional);
    if (Number.isFinite(v)) return v;
    return Number(stats.receitaOperacional || 0);
  }, [mcByBuildingResp.total, stats.receitaOperacional]);

  const kpiMargemContribuicao = useMemo(() => {
    const total = mcByBuildingResp.total;
    const v = toNumberSafe(total?.mc);
    if (Number.isFinite(v)) return v;
    return Number(stats.margemContribuicao || 0);
  }, [mcByBuildingResp.total, stats.margemContribuicao]);

  return (
    <motion.div key="db-geral" initial={{ opacity: 0, y: 20 }} animate={{ opacity: 1, y: 0 }} exit={{ opacity: 0, y: -20 }} className="space-y-8">
      <div className="grid grid-cols-2 lg:grid-cols-4 gap-3 sm:gap-6">
        {[
          {
            label: selectedCompany !== 'all'
              ? `RECEITA — ${companies.find((c: any) => String(c.id) === selectedCompany)?.name || 'Empresa'}`
              : 'RECEITA OPERACIONAL',
            value: `R$ ${kpiReceitaOperacional.toLocaleString('pt-BR', { maximumFractionDigits: 0 })}`,
            icon: TrendingUp,
            color: 'orange',
            tooltip: 'Receita Operacional (base NF via rateio /mc-by-building; respeita filtros e período)',
          },
          {
            label: selectedCompany !== 'all'
              ? `MARGEM — ${companies.find((c: any) => String(c.id) === selectedCompany)?.name || 'Empresa'}`
              : 'Margem de Contribuição',
            value: `R$ ${kpiMargemContribuicao.toLocaleString('pt-BR', { maximumFractionDigits: 0 })}`,
            icon: DollarSign,
            color: kpiMargemContribuicao >= 0 ? 'green' : 'red',
            tooltip: 'Margem de Contribuição (MC): Receita Operacional − Custos (rateado por obra).',
          },
          { label: 'Obras Ativas', value: activeBuildingCount, icon: Building2, color: 'orange' },
          { label: 'Total de Pedidos', value: orders.length, icon: Package, color: 'orange' }
        ].map((kpi, i) => (
          <Card key={i} className="bg-[#161618] border-white/5 shadow-2xl overflow-hidden relative group" title={(kpi as any).tooltip || ''}>
            <div className="absolute top-0 right-0 p-3 opacity-10 group-hover:opacity-20 transition-opacity"><kpi.icon size={40} className="text-orange-500" /></div>
            <CardHeader className="pb-2 p-4 sm:p-6">
              <CardDescription className="text-[9px] sm:text-[10px] font-black uppercase tracking-widest text-orange-500/70 leading-tight">{kpi.label}</CardDescription>
              <CardTitle className={cn("text-xl sm:text-3xl font-black tracking-tighter mt-1", kpi.color === 'red' ? 'text-red-500' : kpi.color === 'green' ? 'text-green-500' : 'text-white')}>{kpi.value}</CardTitle>
            </CardHeader>
            <div className="h-1 w-full bg-orange-600/20"><div className="h-full bg-orange-600 w-1/3" /></div>
          </Card>
        ))}
      </div>

      {/* Mini gráficos (estilo referência) */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-4 sm:gap-8">
        <Card
          className="bg-[#161618] border-white/5 shadow-2xl overflow-hidden relative"
          title="Receita Operacional (base NF). Fórmula: Receita = Σ(NF) no período filtrado. Melhor mês = maior valor mensal de receita."
        >
          <div className="absolute top-0 right-0 p-4 opacity-10"><TrendingUp size={52} className="text-orange-500" /></div>
          <CardHeader className="pb-2 p-4 sm:p-6">
            <CardTitle className="text-lg font-black uppercase tracking-tight text-white">Receita Operacional</CardTitle>
            <div className="flex items-center justify-between text-[11px] text-gray-400">
              <span>Melhor mês: {receitaMargemSeries.bestReceita.name}</span>
              <span className="font-black text-orange-500">R$ {receitaMargemSeries.bestReceita.valor.toLocaleString('pt-BR', { maximumFractionDigits: 0 })}</span>
            </div>
            <div className="text-2xl sm:text-4xl font-black tracking-tighter text-white">R$ {kpiReceitaOperacional.toLocaleString('pt-BR', { maximumFractionDigits: 0 })}</div>
          </CardHeader>
          <CardContent className="h-[150px] sm:h-[180px] pt-2 pb-4">
            <ResponsiveContainer width="100%" height="100%">
              <AreaChart data={receitaMargemSeries.receitaChart} margin={{ top: 8, right: 8, left: 0, bottom: 0 }}>
                <defs>
                  <linearGradient id="miniReceita" x1="0" y1="0" x2="0" y2="1">
                    <stop offset="5%" stopColor="#f97316" stopOpacity={0.35} />
                    <stop offset="95%" stopColor="#f97316" stopOpacity={0} />
                  </linearGradient>
                </defs>
                <XAxis dataKey="name" axisLine={false} tickLine={false} tick={{ fill: '#666', fontSize: 11 }} />
                <YAxis hide />
                <Tooltip
                  formatter={(value: number) => new Intl.NumberFormat('pt-BR', { style: 'currency', currency: 'BRL' }).format(value)}
                  contentStyle={{ backgroundColor: '#161618', border: '1px solid rgba(255,255,255,0.1)' }}
                />
                <Area type="monotone" dataKey="valor" stroke="#f97316" strokeWidth={3} fill="url(#miniReceita)" />
              </AreaChart>
            </ResponsiveContainer>
          </CardContent>
          <div className="h-1 w-full bg-orange-600/20"><div className="h-full bg-orange-600 w-1/3" /></div>
        </Card>

        <Card
          className="bg-[#161618] border-white/5 shadow-2xl overflow-hidden relative"
          title="Margem de Contribuição (MC). Fórmula: MC = Receita Líquida − Custos. Aqui, custos ≈ Σ(despesas do extrato: type=Expense) no período filtrado. Melhor mês = maior MC mensal."
        >
          <div className="absolute top-0 right-0 p-4 opacity-10"><DollarSign size={52} className="text-emerald-400" /></div>
          <CardHeader className="pb-2 p-4 sm:p-6">
            <CardTitle className="text-lg font-black uppercase tracking-tight text-white">Margem de Contribuição</CardTitle>
            <div className="flex items-center justify-between text-[11px] text-gray-400">
              <span>Melhor mês: {receitaMargemSeries.bestMargem.name}</span>
              <span className={cn('font-black', receitaMargemSeries.bestMargem.valor >= 0 ? 'text-emerald-400' : 'text-red-400')}>
                R$ {receitaMargemSeries.bestMargem.valor.toLocaleString('pt-BR', { maximumFractionDigits: 0 })}
              </span>
            </div>
            <div className={cn(
              'text-2xl sm:text-4xl font-black tracking-tighter',
              kpiMargemContribuicao >= 0 ? 'text-emerald-400' : 'text-red-500'
            )}>R$ {kpiMargemContribuicao.toLocaleString('pt-BR', { maximumFractionDigits: 0 })}</div>
          </CardHeader>
          <CardContent className="h-[150px] sm:h-[180px] pt-2 pb-4">
            <ResponsiveContainer width="100%" height="100%">
              <AreaChart data={receitaMargemSeries.margemChart} margin={{ top: 8, right: 8, left: 0, bottom: 0 }}>
                <defs>
                  <linearGradient id="miniMargem" x1="0" y1="0" x2="0" y2="1">
                    <stop offset="5%" stopColor="#10b981" stopOpacity={0.35} />
                    <stop offset="95%" stopColor="#10b981" stopOpacity={0} />
                  </linearGradient>
                </defs>
                <XAxis dataKey="name" axisLine={false} tickLine={false} tick={{ fill: '#666', fontSize: 11 }} />
                <YAxis hide />
                <Tooltip
                  formatter={(value: number) => new Intl.NumberFormat('pt-BR', { style: 'currency', currency: 'BRL' }).format(value)}
                  contentStyle={{ backgroundColor: '#161618', border: '1px solid rgba(255,255,255,0.1)' }}
                />
                <Area type="monotone" dataKey="valor" stroke="#10b981" strokeWidth={3} fill="url(#miniMargem)" />
              </AreaChart>
            </ResponsiveContainer>
          </CardContent>
          <div className="h-1 w-full bg-emerald-600/20"><div className="h-full bg-emerald-500 w-1/3" /></div>
        </Card>

        <Card
          className="bg-[#161618] border-white/5 shadow-2xl overflow-hidden relative"
          title="MC Geral (%). Fórmula: MC% = (MC / Receita Líquida) × 100, onde MC = Receita Líquida − (Custos Variáveis + Custos Diretos). Melhor mês = maior MC% mensal."
        >
          <div className="absolute top-0 right-0 p-4 opacity-10"><Percent size={52} className="text-violet-400" /></div>
          <CardHeader className="pb-2 p-4 sm:p-6">
            <CardTitle className="text-lg font-black uppercase tracking-tight text-white">MC Geral (%)</CardTitle>
            <div className="flex items-center justify-between text-[11px] text-gray-400">
              <span>Melhor mês: {receitaMargemSeries.bestMcPercent.name}</span>
              <span className="font-black text-violet-400">{receitaMargemSeries.bestMcPercent.valor.toLocaleString('pt-BR', { maximumFractionDigits: 1 })}%</span>
            </div>
            <div className={cn(
              'text-2xl sm:text-4xl font-black tracking-tighter',
              mcGeralPercent >= 0 ? 'text-white' : 'text-red-300'
            )}>{mcGeralPercent.toLocaleString('pt-BR', { maximumFractionDigits: 1 })}%</div>
          </CardHeader>
          <CardContent className="h-[150px] sm:h-[180px] pt-2 pb-4">
            <ResponsiveContainer width="100%" height="100%">
              <AreaChart data={receitaMargemSeries.mcPercentChart} margin={{ top: 8, right: 8, left: 0, bottom: 0 }}>
                <defs>
                  <linearGradient id="miniMcPct" x1="0" y1="0" x2="0" y2="1">
                    <stop offset="5%" stopColor="#8b5cf6" stopOpacity={0.35} />
                    <stop offset="95%" stopColor="#8b5cf6" stopOpacity={0} />
                  </linearGradient>
                </defs>
                <XAxis dataKey="name" axisLine={false} tickLine={false} tick={{ fill: '#666', fontSize: 11 }} />
                <YAxis hide />
                <Tooltip
                  formatter={(value: number) => `${Number(value || 0).toLocaleString('pt-BR', { maximumFractionDigits: 1 })}%`}
                  contentStyle={{ backgroundColor: '#161618', border: '1px solid rgba(255,255,255,0.1)' }}
                />
                <Area type="monotone" dataKey="valor" stroke="#8b5cf6" strokeWidth={3} fill="url(#miniMcPct)" />
              </AreaChart>
            </ResponsiveContainer>
          </CardContent>
          <div className="h-1 w-full bg-violet-600/20"><div className="h-full bg-violet-500 w-1/3" /></div>
        </Card>
      </div>
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-4 sm:gap-8">
        <Card className="lg:col-span-2 bg-[#161618] border-white/5 shadow-2xl" title="Resumo por Obra (todo o período). Receita Operacional = soma de NF (títulos a receber). MC = Receita Líquida − (Custos Variáveis + Custos Diretos) (aqui aproximado pelos títulos a pagar/CPV). %MC = MC / Receita Líquida × 100.">
          <CardHeader>
            <CardTitle className="text-lg font-black uppercase tracking-tight text-white">MC por Obra</CardTitle>
          </CardHeader>
          <CardContent className="pt-2">
            <Table className="text-xs sm:text-sm">
              <TableHeader className="border-white/10">
                <TableRow className="border-white/10 hover:bg-transparent">
                  <TableHead className="text-gray-300">Obra</TableHead>
                  <TableHead className="text-gray-300">Receita Operacional</TableHead>
                  <TableHead className="text-gray-300">Margem Contribuição</TableHead>
                  <TableHead className="text-gray-300 text-right">% MC</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {mcByBuildingLoading ? (
                  <TableRow className="border-white/10 hover:bg-white/5">
                    <TableCell colSpan={4} className="text-gray-300">
                      Carregando dados por obra...
                    </TableCell>
                  </TableRow>
                ) : resumoPorObra.rows.length === 0 ? (
                  <TableRow className="border-white/10 hover:bg-white/5">
                    <TableCell colSpan={4} className="text-gray-300">
                      {mcByBuildingResp.diagnostic?.status === 'not_configured'
                        ? 'Sienge não configurado para rateio por obra (buildings-cost).'
                        : 'Sem dados por obra no período.'}
                    </TableCell>
                  </TableRow>
                ) : (
                  resumoPorObra.rows.map((r) => (
                  <TableRow key={r.id} className="border-white/10 hover:bg-white/5">
                    <TableCell className="text-white font-semibold max-w-[220px] truncate">{r.name}</TableCell>

                    <TableCell>
                      <div className="relative h-7 rounded bg-white/5 overflow-hidden">
                        <div className="absolute inset-y-0 left-0 bg-orange-500/30" style={{ width: `${Math.round((r.receita / resumoPorObra.maxReceita) * 100)}%` }} />
                        <div className="relative z-10 px-2 h-full flex items-center justify-end text-white font-semibold">
                          {new Intl.NumberFormat('pt-BR', { style: 'currency', currency: 'BRL', maximumFractionDigits: 0 }).format(r.receita)}
                        </div>
                      </div>
                    </TableCell>

                    <TableCell>
                      <div className="relative h-7 rounded bg-white/5 overflow-hidden">
                        <div
                          className={cn('absolute inset-y-0 left-0', r.mc >= 0 ? 'bg-emerald-500/30' : 'bg-red-500/30')}
                          style={{ width: `${Math.round((Math.abs(r.mc) / resumoPorObra.maxMcAbs) * 100)}%` }}
                        />
                        <div className={cn(
                          'relative z-10 px-2 h-full flex items-center justify-end font-semibold',
                          r.mc >= 0 ? 'text-emerald-400' : 'text-red-400'
                        )}>
                          {new Intl.NumberFormat('pt-BR', { style: 'currency', currency: 'BRL', maximumFractionDigits: 0 }).format(r.mc)}
                        </div>
                      </div>
                    </TableCell>

                    <TableCell className="text-right font-bold">
                      <span className={cn(
                        'inline-flex items-center justify-center min-w-[56px] px-2 py-1 rounded',
                        r.pct >= 0 ? 'bg-violet-500/15 text-violet-300' : 'bg-red-500/15 text-red-300'
                      )}>
                        {r.pct.toLocaleString('pt-BR', { maximumFractionDigits: 0 })}%
                      </span>
                    </TableCell>
                  </TableRow>
                  ))
                )}
              </TableBody>
              <TableFooter className="bg-transparent border-white/10">
                <TableRow className="border-white/10 hover:bg-transparent">
                  <TableCell className="text-white font-black">Total</TableCell>
                  <TableCell className="text-white font-black">
                    {new Intl.NumberFormat('pt-BR', { style: 'currency', currency: 'BRL', maximumFractionDigits: 0 }).format(resumoPorObra.total.receita)}
                  </TableCell>
                  <TableCell className={cn('font-black', resumoPorObra.total.mc >= 0 ? 'text-emerald-400' : 'text-red-400')}>
                    {new Intl.NumberFormat('pt-BR', { style: 'currency', currency: 'BRL', maximumFractionDigits: 0 }).format(resumoPorObra.total.mc)}
                  </TableCell>
                  <TableCell className="text-right text-white font-black">
                    {resumoPorObra.total.pct.toLocaleString('pt-BR', { maximumFractionDigits: 0 })}%
                  </TableCell>
                </TableRow>
              </TableFooter>
            </Table>
          </CardContent>
        </Card>
        <Card className="bg-[#161618] border-white/5 shadow-2xl">
          <CardHeader><CardTitle className="text-lg font-black uppercase tracking-tight text-white">Status dos Pedidos</CardTitle></CardHeader>
          <CardContent className="h-[220px] sm:h-[350px]">
            <ResponsiveContainer width="100%" height="100%">
              <PieChart>
                <Pie data={orderStatusData} cx="50%" cy="50%" innerRadius={60} outerRadius={80} paddingAngle={5} dataKey="value">
                  {orderStatusData.map((e, index) => <Cell key={index} fill={['#f97316', '#3b82f6', '#10b981', '#f59e0b', '#6366f1'][index % 5]} />)}
                </Pie>
                <Tooltip contentStyle={{ backgroundColor: '#161618', border: 'none', borderRadius: '8px' }} />
                <Legend />
              </PieChart>
            </ResponsiveContainer>
          </CardContent>
        </Card>
      </div>
    </motion.div>
  );
}
