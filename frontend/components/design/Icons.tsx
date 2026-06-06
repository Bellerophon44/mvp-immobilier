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

export function Printer(p: IconProps) {
  return (
    <Icon {...p}>
      <path d="M6 9 V4 a1 1 0 0 1 1 -1 H17 a1 1 0 0 1 1 1 V9" />
      <path d="M6 18 H4 a2 2 0 0 1 -2 -2 V13 a2 2 0 0 1 2 -2 H20 a2 2 0 0 1 2 2 V16 a2 2 0 0 1 -2 2 H18" />
      <rect x="6" y="14" width="12" height="7" rx="1" />
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
// Encré en or Jaumont via currentColor. Glyphes calibrés (scale 0.5, espacés sur
// la bande) pour remplir l'anneau ; trait des glyphes 1,25 px, anneau 1,5 px — le
// <g> override le strokeWidth hérité d'Icon sans toucher à l'API (size/className/
// style uniquement). MARK GRAND FORMAT (≥ 96 px) : en-tête de rapport, héro,
// héro, page « à propos ». Sous ~96 px les gaps et les queues fourchues se
// referment — l'UI 20 px conserve le losange (Seal), le cachet 64 px conserve
// l'alérion unique (AlerionSeal). Variante « bande » (deux hairlines) documentée
// dans Design System/assets/icons/lorraine-seal.svg pour les ≥ 160 px.
export function LorraineSeal(p: IconProps) {
  return (
    <Icon {...p}>
      <circle cx="12" cy="12" r="9" />
      <g strokeWidth="1.25">
        {/* alérion 1 — chef dextre (haut-gauche) */}
        <path d="M8.7 7.6 L8.7 9.8" />
        <path d="M8.7 9.8 L8.25 10.2 M8.7 9.8 L9.15 10.2" />
        <path d="M6.0 7.8 C 6.8 7.4 7.2 8.4 7.6 8.3 C 8.0 8.2 8.4 8.0 8.7 7.8" />
        <path d="M11.4 7.8 C 10.6 7.4 10.2 8.4 9.8 8.3 C 9.4 8.2 9.0 8.0 8.7 7.8" />
        {/* alérion 2 — cœur */}
        <path d="M12.0 10.9 L12.0 13.1" />
        <path d="M12.0 13.1 L11.55 13.5 M12.0 13.1 L12.45 13.5" />
        <path d="M9.3 11.1 C 10.1 10.7 10.5 11.7 10.9 11.6 C 11.3 11.5 11.7 11.3 12.0 11.1" />
        <path d="M14.7 11.1 C 13.9 10.7 13.5 11.7 13.1 11.6 C 12.7 11.5 12.3 11.3 12.0 11.1" />
        {/* alérion 3 — pointe senestre (bas-droite) */}
        <path d="M15.3 14.2 L15.3 16.4" />
        <path d="M15.3 16.4 L14.85 16.8 M15.3 16.4 L15.75 16.8" />
        <path d="M12.6 14.4 C 13.4 14.0 13.8 15.0 14.2 14.9 C 14.6 14.8 15.0 14.6 15.3 14.4" />
        <path d="M18.0 14.4 C 17.2 14.0 16.8 15.0 16.4 14.9 C 16.0 14.8 15.6 14.6 15.3 14.4" />
      </g>
    </Icon>
  );
}
