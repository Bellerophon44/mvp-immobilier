import React, { useState } from 'react';
import {
  SafeAreaView,
  View,
  Text,
  TextInput,
  Pressable,
  StyleSheet,
} from 'react-native';
import { firstUrl } from '../lib/extractUrl';
import { Wordmark } from '../components/Wordmark';
import { colors, spacing, radii, fontSize, fontFamily } from '../theme';

/**
 * Ecran de saisie : collage manuel d'une URL ou d'un texte contenant une URL
 * d'annonce. SPEC mobile-phase2-tranche1 §4.1. Au clic sur Analyser :
 * firstUrl(saisie) ; si null -> message d'erreur, pas de navigation ; sinon on
 * transmet l'URL extraite a l'ecran WebView via onSubmit.
 *
 * Habillage Coherence : fond parchment, titre serif editorial, carte de collage
 * sur paper a bord stoneLine, bouton primaire brique.
 */
export function InputScreen({ onSubmit }: { onSubmit: (url: string) => void }) {
  const [value, setValue] = useState('');
  const [error, setError] = useState<string | null>(null);

  const handleAnalyser = () => {
    const url = firstUrl(value);
    if (!url) {
      setError("Aucune URL d'annonce détectée");
      return;
    }
    setError(null);
    onSubmit(url);
  };

  return (
    <SafeAreaView style={styles.root}>
      <View style={styles.header}>
        <Wordmark />
      </View>
      <View style={styles.content}>
        <Text style={styles.eyebrow}>Analyse d'annonce</Text>
        <Text style={styles.title}>Une lecture honnête, avant la visite.</Text>
        <Text style={styles.subtitle}>
          Colle l'URL d'une annonce LeBonCoin (ou le texte de partage qui la
          contient), puis lance l'analyse.
        </Text>

        <View style={styles.card}>
          <TextInput
            style={styles.input}
            value={value}
            onChangeText={setValue}
            autoCapitalize="none"
            autoCorrect={false}
            multiline
            placeholder="https://www.leboncoin.fr/ad/ventes_immobilieres/..."
            placeholderTextColor={colors.stone}
          />
        </View>

        {error ? <Text style={styles.error}>{error}</Text> : null}

        <Pressable
          style={({ pressed }) => [styles.cta, pressed && styles.ctaPressed]}
          onPress={handleAnalyser}
          accessibilityRole="button"
        >
          <Text style={styles.ctaLabel}>Analyser</Text>
        </Pressable>
      </View>
    </SafeAreaView>
  );
}

const styles = StyleSheet.create({
  root: { flex: 1, backgroundColor: colors.parchment },
  header: {
    paddingHorizontal: spacing.s5,
    paddingTop: spacing.s4,
    paddingBottom: spacing.s2,
  },
  content: { flex: 1, paddingHorizontal: spacing.s5, justifyContent: 'center', gap: spacing.s4 },
  eyebrow: {
    fontFamily: fontFamily.sansMedium,
    fontSize: 11,
    letterSpacing: 1.3,
    textTransform: 'uppercase',
    color: colors.stone,
  },
  title: {
    fontFamily: fontFamily.serif,
    fontSize: fontSize.xl,
    lineHeight: fontSize.xl * 1.05,
    color: colors.ink,
  },
  subtitle: {
    fontFamily: fontFamily.sans,
    fontSize: fontSize.base,
    lineHeight: fontSize.base * 1.55,
    color: colors.ink2,
  },
  card: {
    backgroundColor: colors.paper,
    borderWidth: 1,
    borderColor: colors.stoneLine,
    borderRadius: radii.lg,
    padding: spacing.s4,
    marginTop: spacing.s2,
  },
  input: {
    fontFamily: fontFamily.sans,
    fontSize: fontSize.base,
    color: colors.ink,
    minHeight: 96,
    textAlignVertical: 'top',
  },
  error: {
    fontFamily: fontFamily.sans,
    color: colors.brick,
    fontSize: fontSize.sm,
  },
  cta: {
    backgroundColor: colors.brick,
    borderRadius: radii.lg,
    paddingVertical: spacing.s4,
    alignItems: 'center',
    minHeight: 52,
    justifyContent: 'center',
    marginTop: spacing.s2,
  },
  ctaPressed: { backgroundColor: colors.brickDeep },
  ctaLabel: {
    fontFamily: fontFamily.sansSemiBold,
    fontSize: fontSize.base,
    color: colors.paper,
    letterSpacing: 0.2,
  },
});
