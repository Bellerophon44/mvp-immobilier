/**
 * URL du backend, lue depuis l'environnement Expo (EXPO_PUBLIC_API_URL), JAMAIS
 * codee en dur (SPEC mobile-phase2-tranche1 AC12). Fonction (pas constante) pour
 * etre lue au moment de l'appel et rester testable.
 */
export function getApiUrl(): string {
  throw new Error('NOT_IMPLEMENTED: getApiUrl');
}
