// Quartiers de Metz proposés dans le sélecteur d'affinage (#6-A). Liste alignée
// sur les localités reconnues par le backend (scrapers.base._KNOWN_LOCALITIES),
// restreinte aux quartiers intra-muros de Metz : le label est envoyé tel quel à
// /analyze, qui le normalise (canonical_district) pour requêter les comparables
// du même quartier. Les communes limitrophes (Montigny, Woippy…) sont volontairement
// exclues — on demande ici "le quartier de Metz", pas la commune.
export const METZ_DISTRICTS: string[] = [
  "Centre-Ville",
  "Nouvelle Ville",
  "Sablon",
  "Queuleu",
  "Plantières",
  "Bellecroix",
  "Borny",
  "Magny",
  "Vallières",
  "Devant-les-Ponts",
  "La Patrotte",
  "Outre-Seille",
  "Grange-aux-Bois",
  "Technopôle",
];
