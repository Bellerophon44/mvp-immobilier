import React, { useRef, useState } from 'react';
import {
  SafeAreaView,
  View,
  Text,
  Pressable,
  ActivityIndicator,
  StyleSheet,
  Platform,
} from 'react-native';
import { WebView, WebViewMessageEvent } from 'react-native-webview';
import { buildInjectedScript } from '../webview/injectedScript';
import { filterGallery } from '../lib/gallery';
import { analyzeListing } from '../lib/analyzeApi';
import { ApiResult } from '../lib/types';
import { Wordmark } from '../components/Wordmark';
import { colors, spacing, radii, fontSize, fontFamily } from '../theme';

// UA mobile realiste (repris du spike) : une vraie page mobile se comporte comme
// pour un humain, le mur DataDome ne se declenche pas sur un appareil reel.
const MOBILE_USER_AGENT = Platform.select({
  ios: 'Mozilla/5.0 (iPhone; CPU iPhone OS 17_0 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.0 Mobile/15E148 Safari/604.1',
  android:
    'Mozilla/5.0 (Linux; Android 14) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0 Mobile Safari/537.36',
});

interface ExtractMessage {
  ok: boolean;
  text?: string;
  rawImageUrls?: string[];
  error?: string;
}

/**
 * Ecran WebView : charge l'URL de l'annonce, laisse l'utilisateur fermer les
 * cookies et faire defiler, puis sur « Extraire et analyser » injecte le script
 * d'extraction. SPEC mobile-phase2-tranche1 §4.2/§4.3.
 *
 * Sur message : filterGallery(rawImageUrls) (SOURCE UNIQUE DE VERITE du
 * filtrage) -> analyzeListing(text, gallery) -> transmet l'ApiResult a l'ecran
 * resultat. Toute erreur (firstUrl en amont, extraction, analyse) -> message
 * lisible (le message de analyzeListing porte le detail backend).
 */
export function WebViewScreen({
  url,
  onResult,
  onBack,
}: {
  url: string;
  onResult: (result: ApiResult) => void;
  onBack: () => void;
}) {
  const webRef = useRef<WebView>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [status, setStatus] = useState(
    'Ferme la bannière cookies, fais défiler la galerie, puis « Extraire et analyser ».',
  );

  const onMessage = async (event: WebViewMessageEvent) => {
    let data: ExtractMessage;
    try {
      data = JSON.parse(event.nativeEvent.data) as ExtractMessage;
    } catch {
      setLoading(false);
      setError('Réponse de la page illisible.');
      return;
    }
    if (!data.ok || typeof data.text !== 'string') {
      setLoading(false);
      setError("Erreur lors de l'extraction : " + (data.error ?? 'inconnue'));
      return;
    }
    const gallery = filterGallery(data.rawImageUrls ?? []);
    try {
      const result = await analyzeListing(data.text, gallery);
      setLoading(false);
      onResult(result);
    } catch (e) {
      setLoading(false);
      setError("Échec de l'analyse : " + (e instanceof Error ? e.message : String(e)));
    }
  };

  const extraire = () => {
    setLoading(true);
    setError(null);
    setStatus('Extraction et analyse en cours...');
    webRef.current?.injectJavaScript(buildInjectedScript());
  };

  return (
    <SafeAreaView style={styles.root}>
      <View style={styles.header}>
        <Pressable style={styles.back} onPress={onBack} accessibilityRole="button">
          <Text style={styles.backLabel}>Retour</Text>
        </Pressable>
        <Wordmark compact />
      </View>

      <View style={styles.webBox}>
        <WebView
          ref={webRef}
          source={{ uri: url }}
          onMessage={onMessage}
          userAgent={MOBILE_USER_AGENT}
        />
      </View>

      <View style={styles.actions}>
        {error ? (
          <View style={styles.errorBanner}>
            <Text style={styles.errorText}>{error}</Text>
          </View>
        ) : (
          <Text style={styles.status}>{status}</Text>
        )}

        {loading ? (
          <View style={styles.loadingRow}>
            <ActivityIndicator color={colors.brick} />
            <Text style={styles.loadingText}>Analyse en cours...</Text>
          </View>
        ) : (
          <Pressable
            style={({ pressed }) => [styles.cta, pressed && styles.ctaPressed]}
            onPress={extraire}
            accessibilityRole="button"
          >
            <Text style={styles.ctaLabel}>Extraire et analyser</Text>
          </Pressable>
        )}
      </View>
    </SafeAreaView>
  );
}

const styles = StyleSheet.create({
  root: { flex: 1, backgroundColor: colors.parchment },
  header: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: spacing.s4,
    paddingHorizontal: spacing.s4,
    paddingVertical: spacing.s3,
  },
  back: {
    minHeight: 44,
    justifyContent: 'center',
    paddingRight: spacing.s2,
  },
  backLabel: {
    fontFamily: fontFamily.sansMedium,
    fontSize: fontSize.base,
    color: colors.brick,
  },
  webBox: {
    flex: 1,
    borderTopWidth: 1,
    borderBottomWidth: 1,
    borderColor: colors.stoneLine,
    backgroundColor: colors.paper,
  },
  actions: {
    paddingHorizontal: spacing.s4,
    paddingVertical: spacing.s4,
    gap: spacing.s3,
  },
  status: {
    fontFamily: fontFamily.sans,
    fontSize: fontSize.sm,
    color: colors.ink3,
    lineHeight: fontSize.sm * 1.5,
  },
  errorBanner: {
    backgroundColor: colors.brickSoft,
    borderRadius: radii.md,
    padding: spacing.s3,
  },
  errorText: {
    fontFamily: fontFamily.sans,
    fontSize: fontSize.sm,
    color: colors.brickDeep,
    lineHeight: fontSize.sm * 1.5,
  },
  loadingRow: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: spacing.s2,
    minHeight: 52,
    justifyContent: 'center',
  },
  loadingText: {
    fontFamily: fontFamily.sans,
    fontSize: fontSize.sm,
    color: colors.ink3,
  },
  cta: {
    backgroundColor: colors.brick,
    borderRadius: radii.lg,
    paddingVertical: spacing.s4,
    alignItems: 'center',
    justifyContent: 'center',
    minHeight: 52,
  },
  ctaPressed: { backgroundColor: colors.brickDeep },
  ctaLabel: {
    fontFamily: fontFamily.sansSemiBold,
    fontSize: fontSize.base,
    color: colors.paper,
    letterSpacing: 0.2,
  },
});
