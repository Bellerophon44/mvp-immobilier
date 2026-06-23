import React, { useState } from 'react';
import { StatusBar } from 'expo-status-bar';
import { InputScreen } from './src/screens/InputScreen';
import { WebViewScreen } from './src/screens/WebViewScreen';
import { ResultScreen } from './src/screens/ResultScreen';
import { ApiResult } from './src/lib/types';

// Machine a etats minimale (sans react-navigation) reliant les 3 ecrans de la
// boucle : saisie -> webview -> resultat. SPEC mobile-phase2-tranche1 §4.
type Screen = 'input' | 'webview' | 'result';

export default function App() {
  const [screen, setScreen] = useState<Screen>('input');
  const [url, setUrl] = useState<string | null>(null);
  const [result, setResult] = useState<ApiResult | null>(null);

  return (
    <>
      <StatusBar style="auto" />
      {screen === 'input' ? (
        <InputScreen
          onSubmit={(u) => {
            setUrl(u);
            setScreen('webview');
          }}
        />
      ) : null}
      {screen === 'webview' && url ? (
        <WebViewScreen
          url={url}
          onResult={(r) => {
            setResult(r);
            setScreen('result');
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
    </>
  );
}
