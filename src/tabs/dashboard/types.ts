export type McByBuildingRow = {
  building_id: string;
  building_name: string;
  receita_operacional: number;
  mc: number;
  mc_percent: number;
};

export type McByBuildingResponse = {
  rows: McByBuildingRow[];
  total: { receita_operacional: number; mc: number; mc_percent: number };
  diagnostic?: any;
};

export interface DashboardFinanceiroProps {
  cashFlowData: any[];
  financeBalanceData: any[];
}

export interface DashboardObrasProps {
  buildingCostData: any[];
}

export interface DashboardLogisticaProps {
  supplierData: any[];
  paymentMethodData: any[];
}
