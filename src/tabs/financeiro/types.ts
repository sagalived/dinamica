export interface LeandroRow {
  id?: string | number;
  data: string;
  baixa?: string;
  vencto?: string;
  companyId?: string;
  historico: string;
  clienteFornecedor?: string;
  tituloParcela?: string;
  documento?: string;
  obra: string;
  obraId?: string;
  entrada: number;
  saida: number;
  saldo: number;
}

export interface LeandroPeriod {
  mes: string;
  entradas: number;
  saidas: number;
  saldo: number;
}

export interface LeandroProps {
  isDark: boolean;
  allFinancialTitles: any[];
  allReceivableTitles: any[];
  orders: any[];
  buildings: any[];
  companies: any[];
  syncing: boolean;
  syncSienge: () => Promise<void>;
}
