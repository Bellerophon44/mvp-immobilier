// Theme Coherence cote mobile — source unique de verite des tokens de marque.
// Valeurs reprises EXACTEMENT de frontend/app/globals.css (design system web).
// Ne pas diverger : ce fichier est l'equivalent RN des variables CSS :root.

export const colors = {
  // Marque
  ink: '#1A1814',
  ink2: '#3A352E',
  ink3: '#5A5347',
  parchment: '#F5F1EA',
  paper: '#FBF8F2',
  stone: '#8B8275',
  stoneLine: '#D9D2C5',
  stoneFill: '#ECE5D5',

  // Accent CTA (la BRIQUE est le seul accent d'action)
  brick: '#B5462F',
  brickDeep: '#6B2018',
  brickSoft: '#E8C9BD',

  // Ancrage local Metz — l'OR DE JAUMONT est RESERVE au cachet « contexte
  // local », ce n'est PAS un accent d'action (cf. commentaire globals.css).
  jaumont: '#C9A14A',
  jaumontSoft: '#ECD9B0',

  // Signaux de verdict
  moss: '#2E6E4F',
  mossSoft: '#C9D9CC',
  ochre: '#C28B3C',
  ochreSoft: '#ECD9B0',
} as const;

// Spacing base 4 (echelle globals.css s-0..s-9).
export const spacing = {
  s0: 0,
  s1: 4,
  s2: 8,
  s3: 12,
  s4: 16,
  s5: 24,
  s6: 32,
  s7: 48,
  s8: 64,
  s9: 96,
} as const;

// Radii globals.css.
export const radii = {
  sm: 2,
  md: 4,
  lg: 8,
  full: 999,
} as const;

// Echelle typographique globals.css (fs-xs..fs-4xl).
export const fontSize = {
  xs: 12,
  sm: 14,
  base: 16,
  md: 20,
  lg: 24,
  xl: 32,
  xxl: 44,
  xxxl: 60,
  xxxxl: 88,
} as const;

// Familles de polices. Les cles correspondent aux noms charges par useFonts
// dans App.tsx (cf. fontFamily des constantes @expo-google-fonts/*).
export const fontFamily = {
  serif: 'InstrumentSerif_400Regular',
  serifItalic: 'InstrumentSerif_400Regular_Italic',
  sans: 'Geist_400Regular',
  sansMedium: 'Geist_500Medium',
  sansSemiBold: 'Geist_600SemiBold',
  mono: 'GeistMono_500Medium',
  monoRegular: 'GeistMono_400Regular',
} as const;

export type VerdictMeta = { label: string; color: string };

// Reflet exact de verdictMeta() de frontend/components/design/ScoreRing.tsx.
// Seuils -> label -> couleur. Le LABEL affiche cote resultat vient du backend
// (result.verdict) ; cette couleur derive du score pour l'anneau et les accents.
export function verdictMeta(score: number): VerdictMeta {
  if (score >= 75) return { label: 'Favorable', color: colors.moss };
  if (score >= 55) return { label: 'À creuser', color: colors.ochre };
  if (score >= 35) return { label: 'Prudence', color: colors.brick };
  return { label: 'Déconseillé', color: colors.brickDeep };
}
