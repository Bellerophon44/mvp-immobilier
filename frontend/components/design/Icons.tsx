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
// du Seal, mais remplace le losange (et l'anneau pointillé intérieur, devenu
// redondant) par un alérion lorrain gravé : aiglon héraldique ailes déployées,
// sans bec ni pattes. Corps central, deux ailes déployées, petite queue
// fourchue. Encré en or Jaumont via currentColor. L'anneau pointillé est retiré
// pour libérer le champ central : c'est la seule façon de garder l'alérion
// lisible à 20 px sans que les traits ne se touchent. SVG source :
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
