import React, { useState } from 'react';
import { View, Text, ActivityIndicator, StyleSheet } from 'react-native';
import { StatusBar } from 'expo-status-bar';
import { useFonts } from 'expo-font';
import {
  InstrumentSerif_400Regular,
  InstrumentSerif_400Regular_Italic,
} from '@expo-google-fonts/instrument-serif';
import {
  Geist_400Regular,
  Geist_500Medium,
  Geist_600SemiBold,
} from '@expo-google-fonts/geist';
import {
  GeistMono_400Regular,
  GeistMono_500Medium,
} from '@expo-google-fonts/geist-mono';
import { InputScreen } from './src/screens/InputScreen';
import { WebViewScreen } from './src/screens/WebViewScreen';
import { ResultScreen } from './src/screens/ResultScreen';
import { HistoryScreen } from './src/screens/HistoryScreen';
import { ApiResult } from './src/lib/types';
import { saveAnalysis } from './src/lib/history';
import { SqliteHistoryStore } from './src/lib/historyStoreSqlite';
import { Wordmark } from './src/components/Wordmark';
import { colors, spacing } from './src/theme';

// Machine a etats minimale (sans react-navigation) reliant les ecrans de la
// boucle : saisie -> webview -> resultat, + l'historique local. SPEC
// mobile-phase2-tranche1 §4, mobile-tranche-b-historique §3.
type Screen = 'input' | 'webview' | 'result' | 'history';

// Adaptateur sqlite instancie UNE seule fois (niveau module) : un seul handle de
// base partage par la sauvegarde auto (onResult) et l'ecran « Mes analyses ».
const historyStore = new SqliteHistoryStore();

export default function App() {
  // Garde de chargement : les noms charges ici doivent correspondre aux cles
  // de theme.fontFamily (Geist / GeistMono / InstrumentSerif).
  const [fontsLoaded] = useFonts({
    InstrumentSerif_400Regular,
    InstrumentSerif_400Regular_Italic,
    Geist_400Regular,
    Geist_500Medium,
    Geist_600SemiBold,
    GeistMono_400Regular,
    GeistMono_500Medium,
  });

  const [screen, setScreen] = useState<Screen>('input');
  const [url, setUrl] = useState<string | null>(null);
  const [result, setResult] = useState<ApiResult | null>(null);

  if (!fontsLoaded) {
    // Ecran d'attente sobre, dans les codes de marque (parchment + brique).
    return (
      <View style={styles.splash}>
        <StatusBar style="dark" />
        <Wordmark />
        <ActivityIndicator color={colors.brick} style={styles.splashSpinner} />
        <Text style={styles.splashText}>Préparation...</Text>
      </View>
    );
  }

  return (
    <View style={styles.root}>
      <StatusBar style="dark" />
      {screen === 'input' ? (
        <InputScreen
          onSubmit={(u) => {
            setUrl(u);
            setScreen('webview');
          }}
          onOpenHistory={() => setScreen('history')}
        />
      ) : null}
      {screen === 'webview' && url ? (
        <WebViewScreen
          url={url}
          onResult={(r, title) => {
            setResult(r);
            setScreen('result');
            // Sauvegarde auto BEST-EFFORT : un echec de store (sqlite) ne doit
            // jamais empecher l'affichage du resultat (§9 pas 5, AC-B8). Le titre
            // est deja derive du texte extrait cote WebViewScreen ; le raw_text
            // n'arrive jamais ici (invariant §11.3).
            void saveAnalysis(historyStore, {
              url,
              title,
              result: r,
              savedAt: Date.now(),
            }).catch(() => {
              // why: degradation silencieuse — l'historique est un confort, pas
              // un bloquant du parcours d'analyse.
            });
          }}
          onBack={() => setScreen('input')}
        />
      ) : null}
      {screen === 'result' && result ? (
        <ResultScreen
          result={result}
          onBack={() => {
            setResult(null);
            setUrl(null);
            setScreen('input');
          }}
        />
      ) : null}
      {screen === 'history' ? (
        <HistoryScreen
          store={historyStore}
          // Reouverture SANS appel reseau : on reaffiche l'ApiResult stocke.
          onOpen={(stored) => {
            setResult(stored);
            setScreen('result');
          }}
          onBack={() => setScreen('input')}
        />
      ) : null}
    </View>
  );
}

const styles = StyleSheet.create({
  root: { flex: 1, backgroundColor: colors.parchment },
  splash: {
    flex: 1,
    backgroundColor: colors.parchment,
    alignItems: 'center',
    justifyContent: 'center',
    gap: spacing.s4,
  },
  splashSpinner: { marginTop: spacing.s2 },
  splashText: {
    // System font here on purpose: brand fonts are not loaded yet.
    color: colors.stone,
    fontSize: 14,
  },
});
