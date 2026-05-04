export interface LogisticsEntry {
  id: string;
  date: string;
  type: 'combustivel' | 'manutencao' | 'rota' | 'outros';
  vehicle: string;
  user: string;
  cost: number;
  routeStart?: string;
  routeEnd?: string;
  fuelConsumed?: number;
  notes?: string;
}

export type RouteOption = {
  value: string;
  label: string;
  code?: string;
  address?: string;
  latitude?: number;
  longitude?: number;
  type?: string;
};

export type RouteEstimate = {
  km: number | null;
  provider: string;
};
