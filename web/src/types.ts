export interface DayData {
  date: string;
  weekday: string;
  day_type: string;
  day_type_label: string;
  beer_sale_allowed: boolean;
  beer_open: string | null;
  beer_close: string | null;
  beer_close_large_stores: string | null;
  is_deviation: boolean;
  comment: string | null;
  vinmonopolet_summary: VinmonopoletSummary | null;
}

export interface VinmonopoletSummary {
  type: "uniform" | "range" | "closed";
  open?: string;
  close?: string;
  min_open?: string;
  max_open?: string;
  min_close?: string;
  max_close?: string;
  open_count: number;
  closed_count: number;
}

export interface VinmonopoletDaySummary extends VinmonopoletSummary {
  date: string;
}

export interface StoreDay {
  date: string;
  open: string | null;
  close: string | null;
}

export interface ResolvedStore {
  store_id: string;
  name: string;
  address: string;
  hours: StoreDay[];
}

export type VinmonopoletMode = "local" | "nearest" | "fallback";

export interface NearestVinmonopolet {
  store: ResolvedStore;
  distance_km: number;
  source_municipality_id: string;
  source_municipality_name: string;
  day_summary: (VinmonopoletDaySummary | null)[];
}

export interface MunicipalityData {
  municipality: {
    id: string;
    name: string;
    county: string;
    sources: { title: string; url: string }[];
    last_verified: string | null;
    verified: boolean;
  };
  days: DayData[];
  vinmonopolet_mode: VinmonopoletMode;
  vinmonopolet_stores: ResolvedStore[];
  vinmonopolet_day_summary: (VinmonopoletDaySummary | null)[];
  vinmonopolet_fetched_at?: string | null;
  nearest_vinmonopolet: NearestVinmonopolet | null;
}
