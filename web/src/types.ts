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
  vinmonopolet_summary: string | null;
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

export interface MunicipalityData {
  municipality: {
    id: string;
    name: string;
    county: string;
    sources: { title: string; url: string }[];
    last_verified: string;
  };
  days: DayData[];
  vinmonopolet_stores: ResolvedStore[];
}
