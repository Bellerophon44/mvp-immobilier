import { CSSProperties, ReactNode } from "react";

interface IconProps {
  size?: number;
  className?: string;
  style?: CSSProperties;
}

function Icon({ size = 16, className, style, children }: IconProps & { children: ReactNode }) {
  return (
    <svg
      viewBox="0 0 24 24"
      width={size}
      height={size}
      fill="none"
      stroke="currentColor"
      strokeWidth="1.5"
      strokeLinecap="round"
      strokeLinejoin="round"
      className={className}
      style={style}
    >
      {children}
    </svg>
  );
}

export function ArrowRight(p: IconProps) {
  return (
    <Icon {...p}>
      <path d="M5 12 H19" />
      <path d="M13 6 L19 12 L13 18" />
    </Icon>
  );
}

export function LinkIcon(p: IconProps) {
  return (
    <Icon {...p}>
      <path d="M10 14 a4 4 0 0 1 0 -5.66 L13.5 4.84 a4 4 0 0 1 5.66 5.66 L17.5 12.18" />
      <path d="M14 10 a4 4 0 0 1 0 5.66 L10.5 19.16 a4 4 0 0 1 -5.66 -5.66 L6.5 11.82" />
    </Icon>
  );
}

export function MapPin(p: IconProps) {
  return (
    <Icon {...p}>
      <path d="M12 21 s-7 -7.5 -7 -12 a7 7 0 0 1 14 0 c0 4.5 -7 12 -7 12 z" />
      <circle cx="12" cy="9" r="2.5" />
    </Icon>
  );
}

export function SquareCheck({ checked = true, ...p }: IconProps & { checked?: boolean }) {
  return (
    <Icon {...p}>
      <rect x="4" y="4" width="16" height="16" rx="2" />
      {checked && <path d="M8.5 12 L11 14.5 L16 9.5" />}
    </Icon>
  );
}

export function Copy(p: IconProps) {
  return (
    <Icon {...p}>
      <rect x="9" y="9" width="11" height="11" rx="2" />
      <path d="M14 9 V5 a1 1 0 0 0 -1 -1 H5 a1 1 0 0 0 -1 1 V13 a1 1 0 0 0 1 1 H9" />
    </Icon>
  );
}

export function Download(p: IconProps) {
  return (
    <Icon {...p}>
      <path d="M12 4 V15" />
      <path d="M8 11 L12 15 L16 11" />
      <path d="M5 19 H19" />
    </Icon>
  );
}

// Cachet — sceau « contexte local » de l'édition Metz : l'anneau du sceau
// notarial (confiance) + le losange de marque embossé au centre (le même mark
// que le wordmark). Posé en or Jaumont, c'est le seul signe local de l'UI.
// Conservé comme fallback du cachet à l'alérion (AlerionSeal ci-dessous).
export function Seal(p: IconProps) {
  return (
    <Icon {...p}>
      <circle cx="12" cy="12" r="9" />
      <circle cx="12" cy="12" r="6.5" strokeDasharray="1 2" />
      <path d="M12 8.5 L15.5 12 L12 15.5 L8.5 12 Z" />
    </Icon>
  );
}

// Cachet à l'alérion — variante locale (voir docs/brand/METZ-LOCAL.md §2/§7 et
// Design System/preview/brand-alerion.html). Réutilise l'anneau de sceau plein
// du Seal, mais remplace le losange par un alérion lorrain gravé : aiglon
// héraldique ailes déployées, sans bec ni pattes (corps central, deux ailes en
// courbe, petite queue fourchue). Encré en or Jaumont via currentColor.
// RÉSERVÉ AUX GRANDS FORMATS (≥ 64 px) : favicon, en-tête de rapport, page
// « à propos ». À 20 px l'alérion devient illisible (ailes/corps se confondent)
// — l'UI utilise alors le losange Seal. SVG source :
// Design System/assets/icons/alerion.svg.
export function AlerionSeal(p: IconProps) {
  return (
    <Icon {...p}>
      <circle cx="12" cy="12" r="9" />
      <path d="M12 10.2 L12 14.6" />
      <path d="M12 14.6 L11.1 15.4 M12 14.6 L12.9 15.4" />
      <path d="M6.6 10.6 C 8.2 9.8 9 11.8 9.8 11.6 C 10.6 11.4 11.4 11 12 10.6" />
      <path d="M17.4 10.6 C 15.8 9.8 15 11.8 14.2 11.6 C 13.4 11.4 12.6 11 12 10.6" />
    </Icon>
  );
}

// Sceau aux trois alérions de Lorraine — les armes du duché : « D'or à la bande
// de gueules chargée de trois alérions d'argent » (voir docs/brand/METZ-LOCAL.md
// §2 et Design System/preview/brand-alerion-lorraine.html). Réutilise l'anneau de
// sceau plein du Seal et y répète TROIS fois le glyphe d'AlerionSeal (aiglon
// ailes déployées, sans bec ni pattes, queue fourchue), réduit et aligné le long
// de la bande : du chef dextre (haut-gauche) à la pointe senestre (bas-droite).
// Encré en or Jaumont via currentColor. L'anneau garde le trait 1,5 px du set ;
// les glyphes internes descendent à 1,1 px (la densité des trois l'impose) — le
// <g> override le strokeWidth hérité d'Icon sans toucher à l'API (size/className/
// style uniquement). MARK GRAND FORMAT (≥ 96 px) : favicon, en-tête de rapport,
// héro, page « à propos ». Sous ~96 px les gaps et les queues fourchues se
// referment — l'UI 20 px conserve le losange (Seal), le cachet 64 px conserve
// l'alérion unique (AlerionSeal). Variante « bande » (deux hairlines) documentée
// dans Design System/assets/icons/lorraine-seal.svg pour les ≥ 160 px.
export function LorraineSeal(p: IconProps) {
  return (
    <Icon {...p}>
      <circle cx="12" cy="12" r="9" />
      <g strokeWidth="1.1">
        {/* alérion 1 — chef dextre (haut-gauche) */}
        <path d="M8.20 7.34 L8.20 8.92" />
        <path d="M8.20 8.92 L7.88 9.21 M8.20 8.92 L8.52 9.21" />
        <path d="M6.26 7.48 C 6.83 7.19 7.12 7.91 7.41 7.84 C 7.70 7.77 7.98 7.62 8.20 7.48" />
        <path d="M10.14 7.48 C 9.57 7.19 9.28 7.91 8.99 7.84 C 8.70 7.77 8.42 7.62 8.20 7.48" />
        {/* alérion 2 — cœur */}
        <path d="M12.00 11.14 L12.00 12.72" />
        <path d="M12.00 12.72 L11.68 13.01 M12.00 12.72 L12.32 13.01" />
        <path d="M10.06 11.28 C 10.63 10.99 10.92 11.71 11.21 11.64 C 11.50 11.57 11.78 11.42 12.00 11.28" />
        <path d="M13.94 11.28 C 13.37 10.99 13.08 11.71 12.79 11.64 C 12.50 11.57 12.22 11.42 12.00 11.28" />
        {/* alérion 3 — pointe senestre (bas-droite) */}
        <path d="M15.80 14.94 L15.80 16.52" />
        <path d="M15.80 16.52 L15.48 16.81 M15.80 16.52 L16.12 16.81" />
        <path d="M13.86 15.08 C 14.43 14.79 14.72 15.51 15.01 15.44 C 15.30 15.37 15.58 15.22 15.80 15.08" />
        <path d="M17.74 15.08 C 17.17 14.79 16.88 15.51 16.59 15.44 C 16.30 15.37 16.02 15.22 15.80 15.08" />
      </g>
    </Icon>
  );
}
