/**
 * TIPOS COMPARTILHADOS — interfaces de props para todos os componentes de aba.
 * Ao adicionar um novo campo de estado no App.tsx, adicione aqui também.
 */

import type { AuthUser, Building, Creditor, PriceAlert, PurchaseOrder, User } from '../lib/types';

export interface SharedTabProps {
  isDark: boolean;
  sessionUser: AuthUser | null;
  isAdmin: boolean;
}

export interface FinancialTabProps extends SharedTabProps {
  orders: PurchaseOrder[];
  allOrders: PurchaseOrder[];
  financialTitles: any[];
  allFinancialTitles: any[];
  receivableTitles: any[];
  allReceivableTitles: any[];
  buildings: Building[];
  users: User[];
  creditors: Creditor[];
  companies: any[];
  saldoBancario: number | null;
  syncing: boolean;
  syncSienge: () => Promise<void>;
}
