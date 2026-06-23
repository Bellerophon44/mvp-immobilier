import React, { useRef, useState } from 'react';
import {
  SafeAreaView,
  View,
  Text,
  Button,
  ActivityIndicator,
  StyleSheet,
  Platform,
} from 'react-native';
import { WebView, WebViewMessageEvent } from 'react-native-webview';
import { buildInjectedScript } from '../webview/injectedScript';
import { filterGallery } from '../lib/gallery';
import { analyzeListing } from '../lib/analyzeApi';
import { ApiResult } from '../lib/types';

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
  const [status, setStatus] = useState(
    'Ferme la banniere cookies, fais defiler la galerie, puis « Extraire et analyser ».',
  );

  const onMessage = async (event: WebViewMessageEvent) => {
    let data: ExtractMessage;
    try {
      data = JSON.parse(event.nativeEvent.data) as ExtractMessage;
    } catch {
      setLoading(false);
      setStatus('Reponse de la page illisible.');
      return;
    }
    if (!data.ok || typeof data.text !== 'string') {
      setLoading(false);
      setStatus('Erreur lors de l\'extraction : ' + (data.error ?? 'inconnue'));
      return;
    }
    const gallery = filterGallery(data.rawImageUrls ?? []);
    try {
      const result = await analyzeListing(data.text, gallery);
      setLoading(false);
      onResult(result);
    } catch (e) {
      setLoading(false);
      setStatus('Echec de l\'analyse : ' + (e instanceof Error ? e.message : String(e)));
    }
  };

  const extraire = () => {
    setLoading(true);
    setStatus('Extraction et analyse en cours...');
    webRef.current?.injectJavaScript(buildInjectedScript());
  };

  return (
    <SafeAreaView style={styles.root}>
      <View style={styles.bar}>
        <Button title="Retour" onPress={onBack} />
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
        <Text style={styles.status}>{status}</Text>
        {loading ? (
          <ActivityIndicator />
        ) : (
          <Button title="Extraire et analyser" onPress={extraire} />
        )}
      </View>
    </SafeAreaView>
  );
}

const styles = StyleSheet.create({
  root: { flex: 1, backgroundColor: '#fff' },
  bar: { flexDirection: 'row', padding: 8 },
  webBox: { flex: 1, borderTopWidth: 1, borderBottomWidth: 1, borderColor: '#eee' },
  actions: { padding: 12, gap: 8 },
  status: { fontStyle: 'italic', color: '#555' },
});
