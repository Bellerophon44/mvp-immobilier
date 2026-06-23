// Spike on-device (Phase 2 mobile) — extraction texte + URLs photo dans une WebView.
// Jetable. Voir docs/specs/mobile-phase2-spike-PROTOCOLE.md pour le protocole et
// les critères de réussite. Ce fichier est à déposer dans un projet Expo blank
// (voir README.md de ce dossier).
//
// Principe : la WebView affiche une vraie annonce comme le ferait l'utilisateur
// (un vrai navigateur sur un vrai appareil n'est pas un bot → le mur DataDome de
// la PAGE ne se déclenche pas). On laisse l'utilisateur fermer la bannière cookies
// et faire défiler la galerie, PUIS on injecte un script qui lit le DOM et renvoie
// le texte + les URLs d'images au natif. Le fetch des URLs par OpenAI est déjà
// tranché (Spike A), donc ce spike ne teste QUE cette extraction amont.

import React, { useRef, useState } from 'react';
import {
  SafeAreaView,
  View,
  Text,
  TextInput,
  Button,
  ScrollView,
  StyleSheet,
  Platform,
} from 'react-native';
import { WebView } from 'react-native-webview';

// Hôte du CDN d'images à conserver. LBC = img.leboncoin.fr. Pour tester un autre
// portail, ajouter son hôte d'images ici (ex. SeLoger : v.seloger.com / cdn...).
const IMAGE_HOSTS = ['img.leboncoin.fr'];

// Script injecté à la demande (bouton « Extraire »). On scrolle d'abord en bas
// pour déclencher le lazy-load, on attend, puis on collecte texte + images et on
// renvoie le tout au natif via postMessage.
const buildExtractor = (hosts) => `
(function () {
  try {
    window.scrollTo(0, document.body.scrollHeight);
    setTimeout(function () {
      var hosts = ${JSON.stringify(hosts)};
      var texte = document.body.innerText || '';
      var raw = Array.prototype.slice.call(document.querySelectorAll('img')).map(function (i) {
        // plus grande candidate de srcset si présent, sinon src
        return i.srcset ? i.srcset.split(',').pop().trim().split(' ')[0] : i.src;
      }).filter(function (u) {
        return u && hosts.some(function (h) { return u.indexOf(h) !== -1; });
      });
      var uniques = raw.filter(function (u, idx) { return raw.indexOf(u) === idx; });
      window.ReactNativeWebView.postMessage(JSON.stringify({
        ok: true,
        textLength: texte.length,
        textSample: texte.slice(0, 800),
        photos: uniques
      }));
    }, 1500);
  } catch (e) {
    window.ReactNativeWebView.postMessage(JSON.stringify({ ok: false, error: String(e) }));
  }
  true;
})();
`;

export default function App() {
  const webRef = useRef(null);
  const [url, setUrl] = useState('https://www.leboncoin.fr/');
  const [loadedUrl, setLoadedUrl] = useState('https://www.leboncoin.fr/');
  const [result, setResult] = useState(null);
  const [status, setStatus] = useState('Charge une annonce, ferme les cookies, fais défiler la galerie, puis « Extraire ».');

  const onMessage = (event) => {
    try {
      const data = JSON.parse(event.nativeEvent.data);
      if (!data.ok) {
        setStatus('Erreur dans la page : ' + data.error);
        return;
      }
      setResult(data);
      setStatus('Extraction OK.');
    } catch (e) {
      setStatus('Réponse illisible : ' + String(e));
    }
  };

  const extraire = () => {
    setStatus('Extraction en cours…');
    webRef.current && webRef.current.injectJavaScript(buildExtractor(IMAGE_HOSTS));
  };

  return (
    <SafeAreaView style={styles.root}>
      <View style={styles.bar}>
        <TextInput
          style={styles.input}
          value={url}
          onChangeText={setUrl}
          autoCapitalize="none"
          autoCorrect={false}
          placeholder="Colle l'URL d'une annonce LeBonCoin"
        />
        <Button title="Charger" onPress={() => { setResult(null); setLoadedUrl(url); }} />
      </View>

      <View style={styles.webBox}>
        <WebView
          ref={webRef}
          source={{ uri: loadedUrl }}
          onMessage={onMessage}
          // un vrai UA mobile aide la page à se comporter comme pour un humain
          userAgent={Platform.select({
            ios: 'Mozilla/5.0 (iPhone; CPU iPhone OS 17_0 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.0 Mobile/15E148 Safari/604.1',
            android: 'Mozilla/5.0 (Linux; Android 14) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0 Mobile Safari/537.36',
          })}
        />
      </View>

      <View style={styles.actions}>
        <Button title="Extraire le contenu" onPress={extraire} />
      </View>

      <ScrollView style={styles.results} contentContainerStyle={{ padding: 12 }}>
        <Text style={styles.status}>{status}</Text>
        {result && (
          <View>
            <Text style={styles.h}>Texte : {result.textLength} caractères</Text>
            <Text style={styles.sample}>{result.textSample}</Text>
            <Text style={styles.h}>Photos trouvées : {result.photos.length}</Text>
            {result.photos.map((u, i) => (
              <Text key={i} style={styles.url} numberOfLines={1}>{i + 1}. {u}</Text>
            ))}
          </View>
        )}
      </ScrollView>
    </SafeAreaView>
  );
}

const styles = StyleSheet.create({
  root: { flex: 1, backgroundColor: '#fff' },
  bar: { flexDirection: 'row', alignItems: 'center', padding: 8, gap: 8 },
  input: { flex: 1, borderWidth: 1, borderColor: '#ccc', borderRadius: 6, paddingHorizontal: 10, paddingVertical: 6 },
  webBox: { flex: 1, borderTopWidth: 1, borderBottomWidth: 1, borderColor: '#eee' },
  actions: { padding: 8 },
  results: { maxHeight: 260, backgroundColor: '#fafafa' },
  status: { fontStyle: 'italic', color: '#555', marginBottom: 8 },
  h: { fontWeight: '600', marginTop: 8, marginBottom: 4 },
  sample: { color: '#333', fontSize: 12 },
  url: { fontSize: 11, color: '#0a58ca', marginVertical: 1 },
});
