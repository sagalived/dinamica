export interface FluxoProjectionProps {
  buildings: any[];
  companies: any[];
  allFinancialTitles: any[];
  allReceivableTitles: any[];
  syncing: boolean;
  syncSienge: () => Promise<void>;
}
