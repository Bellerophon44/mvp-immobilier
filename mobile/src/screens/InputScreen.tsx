import React, { useState } from 'react';
import {
  SafeAreaView,
  View,
  Text,
  TextInput,
  Button,
  StyleSheet,
} from 'react-native';
import { firstUrl } from '../lib/extractUrl';

/**
 * Ecran de saisie : collage manuel d'une URL ou d'un texte contenant une URL
 * d'annonce. SPEC mobile-phase2-tranche1 §4.1. Au clic sur Analyser :
 * firstUrl(saisie) ; si null -> message d'erreur, pas de navigation ; sinon on
 * transmet l'URL extraite a l'ecran WebView via onSubmit.
 */
export function InputScreen({ onSubmit }: { onSubmit: (url: string) => void }) {
  const [value, setValue] = useState('');
  const [error, setError] = useState<string | null>(null);

  const handleAnalyser = () => {
    const url = firstUrl(value);
    if (!url) {
      setError("Aucune URL d'annonce detectee");
      return;
    }
    setError(null);
    onSubmit(url);
  };

  return (
    <SafeAreaView style={styles.root}>
      <View style={styles.content}>
        <Text style={styles.title}>Coherence</Text>
        <Text style={styles.subtitle}>
          Colle l'URL d'une annonce LeBonCoin (ou le texte de partage qui la
          contient), puis lance l'analyse.
        </Text>
        <TextInput
          style={styles.input}
          value={value}
          onChangeText={setValue}
          autoCapitalize="none"
          autoCorrect={false}
          multiline
          placeholder="https://www.leboncoin.fr/ad/ventes_immobilieres/..."
        />
        {error ? <Text style={styles.error}>{error}</Text> : null}
        <Button title="Analyser" onPress={handleAnalyser} />
      </View>
    </SafeAreaView>
  );
}

const styles = StyleSheet.create({
  root: { flex: 1, backgroundColor: '#fff' },
  content: { flex: 1, padding: 16, gap: 12, justifyContent: 'center' },
  title: { fontSize: 28, fontWeight: '700' },
  subtitle: { fontSize: 14, color: '#555' },
  input: {
    borderWidth: 1,
    borderColor: '#ccc',
    borderRadius: 8,
    paddingHorizontal: 12,
    paddingVertical: 10,
    minHeight: 80,
    textAlignVertical: 'top',
  },
  error: { color: '#c0392b', fontSize: 13 },
});
