// Types du contrat /analyze, refletes du backend (cf. frontend/lib/api.ts).
// Gardes minimaux pour la tranche 1 (rendu du resultat + retour de analyzeListing).

export interface ApiPillar {
  label: string;
  verdict: string;
  explanation: string;
  points?: number;
  max?: number;
  scope?: 'quartier' | 'secteur' | 'metropole' | 'ville' | null;
  scope_name?: string | null;
  dpe_band?: string | null;
  n_comparables?: number | null;
  refinable?: boolean;
  listing_price_m2?: number | null;
}

export interface LocalClaim {
  text: string;
  type: string;
  status: 'coherent' | 'a_verifier' | 'peu_plausible';
  note: string;
  photo_status?: 'confirme' | 'non_trouve' | 'non_applicable';
}

export interface LocalFact {
  label: string;
  value: string;
  mode?: 'WALK' | 'DRIVE' | 'BICYCLE' | 'TRANSIT';
  duration_s?: number;
  distance_m?: number;
  estimated?: boolean;
  poi_id?: string;
}

export interface LocalContext {
  district: string;
  summary: string;
  facts: LocalFact[];
  claims?: LocalClaim[];
  address?: string;
  precision?: 'quartier' | 'adresse';
  district_caveat?: string;
}

export interface ApiResult {
  global_score: number;
  verdict: string;
  confidence: string;
  pillars: ApiPillar[];
  actions: {
    highlights?: string[];
    questions: string[];
    negotiation: string[];
  };
  local_context?: LocalContext | null;
}
