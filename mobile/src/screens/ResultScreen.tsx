import React from 'react';
import {
  SafeAreaView,
  ScrollView,
  View,
  Text,
  Button,
  StyleSheet,
} from 'react-native';
import { ApiResult, ApiPillar, LocalClaim, LocalFact } from '../lib/types';

/**
 * Ecran de resultat : rend l'ApiResult renvoye par /analyze. SPEC
 * mobile-phase2-tranche1 §4.4. Affiche global_score, verdict, confidence, les
 * pillars (label/verdict/explanation/points/max), actions (highlights?/
 * questions/negotiation) et, si present, local_context (district/summary/facts/
 * claims).
 *
 * Anti-pattern produit (CONTEXT §11) : AUCUNE estimation de prix cote app. On
 * affiche uniquement ce que le backend renvoie ; le disclaimer rappelle que ce
 * n'est pas une estimation de prix.
 */
export function ResultScreen({
  result,
  onBack,
}: {
  result: ApiResult;
  onBack: () => void;
}) {
  return (
    <SafeAreaView style={styles.root}>
      <ScrollView contentContainerStyle={styles.content}>
        <View style={styles.bar}>
          <Button title="Nouvelle analyse" onPress={onBack} />
        </View>

        <Text style={styles.score}>{result.global_score}/100</Text>
        <Text style={styles.verdict}>{result.verdict}</Text>
        <Text style={styles.confidence}>Confiance : {result.confidence}</Text>

        <Text style={styles.sectionTitle}>Piliers</Text>
        {result.pillars.map((p: ApiPillar, i: number) => (
          <View key={i} style={styles.card}>
            <Text style={styles.pillarLabel}>{p.label}</Text>
            <Text style={styles.pillarVerdict}>
              {p.verdict}
              {typeof p.points === 'number' && typeof p.max === 'number'
                ? ` (${p.points}/${p.max})`
                : ''}
            </Text>
            <Text style={styles.body}>{p.explanation}</Text>
          </View>
        ))}

        {result.actions.highlights && result.actions.highlights.length > 0 ? (
          <>
            <Text style={styles.sectionTitle}>Points forts</Text>
            {result.actions.highlights.map((h, i) => (
              <Text key={i} style={styles.bullet}>
                - {h}
              </Text>
            ))}
          </>
        ) : null}

        <Text style={styles.sectionTitle}>Questions a poser</Text>
        {result.actions.questions.map((q, i) => (
          <Text key={i} style={styles.bullet}>
            - {q}
          </Text>
        ))}

        <Text style={styles.sectionTitle}>Pistes de negociation</Text>
        {result.actions.negotiation.map((n, i) => (
          <Text key={i} style={styles.bullet}>
            - {n}
          </Text>
        ))}

        {result.local_context ? (
          <>
            <Text style={styles.sectionTitle}>
              Contexte local : {result.local_context.district}
            </Text>
            <Text style={styles.body}>{result.local_context.summary}</Text>
            {result.local_context.facts.map((f: LocalFact, i: number) => (
              <Text key={i} style={styles.bullet}>
                - {f.label} : {f.value}
              </Text>
            ))}
            {result.local_context.claims
              ? result.local_context.claims.map((c: LocalClaim, i: number) => (
                  <Text key={i} style={styles.bullet}>
                    - {c.text} ({c.status})
                    {c.photo_status ? ` [photo : ${c.photo_status}]` : ''}
                  </Text>
                ))
              : null}
          </>
        ) : null}

        <Text style={styles.disclaimer}>
          Cette analyse evalue la coherence de l'annonce et ne constitue pas une
          estimation de prix.
        </Text>
      </ScrollView>
    </SafeAreaView>
  );
}

const styles = StyleSheet.create({
  root: { flex: 1, backgroundColor: '#fff' },
  content: { padding: 16, gap: 6 },
  bar: { marginBottom: 8 },
  score: { fontSize: 40, fontWeight: '800' },
  verdict: { fontSize: 18, fontWeight: '600' },
  confidence: { fontSize: 14, color: '#555', marginBottom: 8 },
  sectionTitle: { fontSize: 16, fontWeight: '700', marginTop: 16, marginBottom: 4 },
  card: {
    borderWidth: 1,
    borderColor: '#eee',
    borderRadius: 8,
    padding: 12,
    marginBottom: 8,
  },
  pillarLabel: { fontSize: 15, fontWeight: '600' },
  pillarVerdict: { fontSize: 14, color: '#333', marginVertical: 2 },
  body: { fontSize: 14, color: '#333' },
  bullet: { fontSize: 14, color: '#333', marginVertical: 1 },
  disclaimer: {
    fontSize: 12,
    fontStyle: 'italic',
    color: '#888',
    marginTop: 24,
  },
});
