// Tipos (models) compartilhados pelo frontend.
// Mantém separado do client HTTP para evitar acoplamento e circularidade.

export interface LogisticsLocation {
  id: number;
  code: string;
  name: string;
  address?: string;
  latitude?: number;
  longitude?: number;
  type: string;
  source: string;
}

export interface Building {
  id: number;
  name: string;
  code?: string;
  latitude?: number;
  longitude?: number;
  address?: string;
  companyId?: number;
  company_id?: number;
  company_name?: string;
  building_type?: string;
  engineer?: string;
}

export interface DirectoryUser {
  id: string;
  name: string;
  email?: string;
  active: boolean;
}

export interface AuthUser {
  id: number;
  email: string;
  username?: string;
  full_name?: string;
  name?: string; // alias de full_name — usado no App legado
  role: string;
  department?: string;
  is_active?: boolean;
}

export interface Creditor {
  id: number;
  name: string;
  cnpj?: string;
  city?: string;
  state?: string;
  active: boolean;
}

export interface Company {
  id: number;
  name: string;
  cnpj?: string;
  trade_name?: string;
  companyName?: string;
  legalName?: string;
}

export interface Client {
  id: number;
  name: string;
  fantasy_name?: string;
  cnpj_cpf?: string;
  city?: string;
  state?: string;
  email?: string;
  phone?: string;
  status?: string;
}

export interface SummaryCard {
  label: string;
  value: number;
}

export interface DashboardSummary {
  cards: SummaryCard[];
  companies_by_buildings: Array<{ company_name: string; total: number }>;
  creditor_states: Array<{ state: string; total: number }>;
  client_cities: Array<{ city: string; total: number }>;
  active_directory_users: number;
}

export interface User {
  id: string | number;
  name: string;
}

export interface PurchaseOrder {
  id: number;
  buildingId: number;
  companyId?: string;
  buyerId?: string;
  date: string;
  dateNumeric: number;
  totalAmount: number;
  supplierId?: string | number;
  creditorId?: string | number;
  idCredor?: string | number;
  nomeFornecedor?: string;
  supplierName?: string;
  creditorName?: string;
  valorTotal?: number;
  amount?: number;
  status: string;
  paymentCondition: string;
  paymentConditionDescription?: string;
  condicaoPagamentoDescricao?: string;
  deliveryDate: string;
  internalNotes: string;
  createdBy: string;
  requesterId: string;
  items?: any[];
}

export interface PriceAlert {
  item: string;
  oldPrice: number;
  newPrice: number;
  diff: number;
  oldDate: string;
  newDate: string;
  history: Array<{ price: number; date: string; orderId?: number; buyerId?: string; creditorId?: string }>;
}
