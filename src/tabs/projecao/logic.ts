/**
 * PROJEÇÃO DE FLUXO — Lógica de dados isolada
 *
 * Contém funções puras para cálculo de projeção de fluxo de caixa,
 * separadas do componente React ProjecaoTab.
 */

export interface ProjectionEntry {
  company: string;
  obra: string;
  date: string;
  entrada: number;
  saida: number;
}

export interface MonthlyProjection {
  key: string;
  label: string;
  entrada: number;
  saida: number;
  saldo: number;
}

export function toMoney(value: unknown): number {
  const n = Number(value);
  return Number.isFinite(n) ? Math.abs(n) : 0;
}

export function monthKey(date: Date): string {
  const y = date.getFullYear();
  const m = String(date.getMonth() + 1).padStart(2, '0');
  return `${y}-${m}`;
}

export function monthLabel(date: Date): string {
  return date.toLocaleDateString('pt-BR', { month: 'short' }).replace('.', '');
}

export function parseCsv(text: string): ProjectionEntry[] {
  const lines = text.split(/\r?\n/).filter((l) => l.trim());
  if (lines.length < 2) return [];
  const split = (line: string) => line.split(/[;,]/).map((c) => c.trim().replace(/^"|"$/g, ''));
  const header = split(lines[0]).map((h) => h.toLowerCase());
  const idx = (names: string[]) => header.findIndex((h) => names.some((n) => h.includes(n)));
  const dateIdx = idx(['data', 'vencto', 'venc']);
  const companyIdx = idx(['empresa', 'company']);
  const obraIdx = idx(['obra', 'building']);
  const entradaIdx = idx(['credito', 'entrada']);
  const saidaIdx = idx(['debito', 'saida']);

  return lines.slice(1).map((line) => {
    const cols = split(line);
    const parseNum = (v: string) => Number(String(v || '0').replace(/\./g, '').replace(',', '.')) || 0;
    return {
      company: companyIdx >= 0 ? String(cols[companyIdx] || '') : '',
      obra: obraIdx >= 0 ? String(cols[obraIdx] || '') : '',
      date: dateIdx >= 0 ? String(cols[dateIdx] || '') : '',
      entrada: entradaIdx >= 0 ? parseNum(cols[entradaIdx]) : 0,
      saida: saidaIdx >= 0 ? parseNum(cols[saidaIdx]) : 0,
    };
  });
}

export function parseXlsx(file: File, XLSX: any): Promise<ProjectionEntry[]> {
  return file.arrayBuffer().then((ab) => {
    const wb = XLSX.read(ab, { type: 'array' });
    const ws = wb.Sheets[wb.SheetNames[0]];
    const json: any[] = XLSX.utils.sheet_to_json(ws, { defval: '' });
    const get = (obj: any, candidates: string[]) => {
      const keys = Object.keys(obj);
      const match = keys.find((k) => candidates.some((c) => k.toLowerCase().includes(c)));
      return match ? obj[match] : '';
    };
    const parseNum = (v: any) => Number(String(v || '0').replace(/\./g, '').replace(',', '.')) || 0;
    return json.map((obj: any) => ({
      company: String(get(obj, ['empresa', 'company']) || ''),
      obra: String(get(obj, ['obra', 'building']) || ''),
      date: String(get(obj, ['data', 'vencto', 'venc']) || ''),
      entrada: parseNum(get(obj, ['credito', 'entrada'])),
      saida: parseNum(get(obj, ['debito', 'saida'])),
    }));
  });
}

export function buildMonthColumns(startMonth: string, span: number): Date[] {
  const [y, m] = startMonth.split('-').map(Number);
  const base = new Date(y || new Date().getFullYear(), (m || (new Date().getMonth() + 1)) - 1, 1);
  const cols: Date[] = [];
  for (let i = 0; i < span; i += 1) {
    cols.push(new Date(base.getFullYear(), base.getMonth() + i, 1));
  }
  return cols;
}

export function aggregateMonthly(
  rows: ProjectionEntry[],
  monthColumns: Date[],
): MonthlyProjection[] {
  const bucket: Record<string, { entrada: number; saida: number }> = {};
  monthColumns.forEach((d) => {
    bucket[monthKey(d)] = { entrada: 0, saida: 0 };
  });

  rows.forEach((r) => {
    const d = new Date(r.date);
    if (Number.isNaN(d.getTime())) return;
    const key = monthKey(new Date(d.getFullYear(), d.getMonth(), 1));
    if (!bucket[key]) return;
    bucket[key].entrada += r.entrada;
    bucket[key].saida += r.saida;
  });

  return monthColumns.map((d) => {
    const key = monthKey(d);
    const item = bucket[key] || { entrada: 0, saida: 0 };
    return {
      key,
      label: monthLabel(d),
      entrada: item.entrada,
      saida: item.saida,
      saldo: item.entrada - item.saida,
    };
  });
}

export function aggregateByBuilding(
  rows: ProjectionEntry[],
  limit = 10,
): Array<{ obra: string; entrada: number; saida: number; saldo: number }> {
  const map: Record<string, { entrada: number; saida: number }> = {};
  rows.forEach((r) => {
    const key = r.obra || 'Obra sem nome';
    if (!map[key]) map[key] = { entrada: 0, saida: 0 };
    map[key].entrada += r.entrada;
    map[key].saida += r.saida;
  });
  return Object.entries(map)
    .map(([obra, values]) => ({ obra, ...values, saldo: values.entrada - values.saida }))
    .sort((a, b) => b.saida - a.saida)
    .slice(0, limit);
}
