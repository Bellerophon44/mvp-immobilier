// Cohérence — brand icon set. 1.5 px stroke, 24×24 viewBox.
// All icons accept { size = 16, className, style } and inherit currentColor.

const Icon = ({ size = 16, className, style, children }) => (
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

const Diamond = (p) => (
  <Icon {...p}><path d="M12 3 L21 12 L12 21 L3 12 Z" /></Icon>
);
const DiamondSolid = ({ size = 16, color = "currentColor", style }) => (
  <svg viewBox="0 0 24 24" width={size} height={size} style={style}>
    <path d="M12 3 L21 12 L12 21 L3 12 Z" fill={color} />
  </svg>
);
const ArrowRight = (p) => (
  <Icon {...p}>
    <path d="M5 12 H19" />
    <path d="M13 6 L19 12 L13 18" />
  </Icon>
);
const LinkIcon = (p) => (
  <Icon {...p}>
    <path d="M10 14 a4 4 0 0 1 0 -5.66 L13.5 4.84 a4 4 0 0 1 5.66 5.66 L17.5 12.18" />
    <path d="M14 10 a4 4 0 0 1 0 5.66 L10.5 19.16 a4 4 0 0 1 -5.66 -5.66 L6.5 11.82" />
  </Icon>
);
const MapPin = (p) => (
  <Icon {...p}>
    <path d="M12 21 s-7 -7.5 -7 -12 a7 7 0 0 1 14 0 c0 4.5 -7 12 -7 12 z" />
    <circle cx="12" cy="9" r="2.5" />
  </Icon>
);
const Scales = (p) => (
  <Icon {...p}>
    <path d="M12 4 V20" />
    <path d="M7 20 H17" />
    <path d="M5 10 L8 4 L11 10" />
    <path d="M13 10 L16 4 L19 10" />
    <path d="M5 10 a3 3 0 0 0 6 0" />
    <path d="M13 10 a3 3 0 0 0 6 0" />
  </Icon>
);
const SquareCheck = ({ checked = true, ...p }) => (
  <Icon {...p}>
    <rect x="4" y="4" width="16" height="16" rx="2" />
    {checked && <path d="M8.5 12 L11 14.5 L16 9.5" />}
  </Icon>
);
const Copy = (p) => (
  <Icon {...p}>
    <rect x="9" y="9" width="11" height="11" rx="2" />
    <path d="M14 9 V5 a1 1 0 0 0 -1 -1 H5 a1 1 0 0 0 -1 1 V13 a1 1 0 0 0 1 1 H9" />
  </Icon>
);

Object.assign(window, { Diamond, DiamondSolid, ArrowRight, LinkIcon, MapPin, Scales, SquareCheck, Copy });
