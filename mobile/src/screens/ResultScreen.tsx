import React from 'react';
import {
  SafeAreaView,
  ScrollView,
  View,
  Text,
  Pressable,
  StyleSheet,
} from 'react-native';
import { ApiResult, ApiPillar, LocalClaim, LocalFact } from '../lib/types';
import { ScoreDonut } from '../components/ScoreDonut';
import { colors, spacing, radii, fontSize, fontFamily, verdictMeta } from '../theme';

/**
 * Ecran de resultat : rend l'ApiResult renvoye par /analyze. SPEC
 * mobile-phase2-tranche1 §4.4. Affiche global_score, verdict, confidence, les
 * pillars (label/verdict/explanation/points/max), actions (highlights?/
 * questions/negotiation) et, si present, local_context (district/summary/facts/
 * claims).
 *
 * Habillage Coherence : HERO = anneau de score colore selon le score ; le LABEL
 * de verdict affiche vient du BACKEND (result.verdict), pas d'un recalcul ; sa
 * couleur derive de verdictMeta(score). L'OR DE JAUMONT n'apparait QUE sur le
 * cachet « contexte local ».
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
  const verdictColor = verdictMeta(result.global_score).color;

  return (
    <SafeAreaView style={styles.root}>
      <ScrollView contentContainerStyle={styles.content}>
        <View style={styles.hero}>
          <ScoreDonut score={result.global_score} />
          <View style={styles.heroText}>
            <Text style={styles.eyebrow}>Score de cohérence</Text>
            <Text style={[styles.verdict, { color: verdictColor }]}>{result.verdict}</Text>
            <Text style={styles.confidence}>Confiance : {result.confidence}</Text>
          </View>
        </View>

        <Section title="Piliers">
          {result.pillars.map((p: ApiPillar, i: number) => {
            const hasScore = typeof p.points === 'number' && typeof p.max === 'number';
            // Accent par pilier selon le ratio points/max (meme echelle de
            // verdict que le score global), neutre si non chiffrable.
            const accent =
              hasScore && (p.max as number) > 0
                ? verdictMeta(((p.points as number) / (p.max as number)) * 100).color
                : colors.stoneLine;
            return (
              <View key={i} style={styles.card}>
                <View style={[styles.pillarAccent, { backgroundColor: accent }]} />
                <View style={styles.pillarBody}>
                  <Text style={styles.pillarLabel}>{p.label}</Text>
                  <Text style={styles.pillarVerdict}>
                    {p.verdict}
                    {hasScore ? ` — ${p.points}/${p.max}` : ''}
                  </Text>
                  <Text style={styles.body}>{p.explanation}</Text>
                </View>
              </View>
            );
          })}
        </Section>

        {result.actions.highlights && result.actions.highlights.length > 0 ? (
          <ActionList title="Points forts" items={result.actions.highlights} accent={colors.moss} />
        ) : null}

        <ActionList title="Questions à poser" items={result.actions.questions} accent={colors.ochre} />
        <ActionList title="Pistes de négociation" items={result.actions.negotiation} accent={colors.brick} />

        {result.local_context ? (
          <View style={styles.cachet}>
            <Text style={styles.cachetEyebrow}>Contexte local</Text>
            <Text style={styles.cachetDistrict}>{result.local_context.district}</Text>
            <Text style={styles.cachetSummary}>{result.local_context.summary}</Text>
            {result.local_context.facts.map((f: LocalFact, i: number) => (
              <View key={i} style={styles.factRow}>
                <Text style={styles.factLabel}>{f.label}</Text>
                <Text style={styles.factValue}>{f.value}</Text>
              </View>
            ))}
            {result.local_context.claims
              ? result.local_context.claims.map((c: LocalClaim, i: number) => (
                  <Text key={`c${i}`} style={styles.claim}>
                    {c.text} ({c.status})
                    {c.photo_status ? ` [photo : ${c.photo_status}]` : ''}
                  </Text>
                ))
              : null}
          </View>
        ) : null}

        <Text style={styles.disclaimer}>
          Cette analyse évalue la cohérence de l'annonce et ne constitue pas une
          estimation de prix.
        </Text>

        <Pressable
          style={({ pressed }) => [styles.cta, pressed && styles.ctaPressed]}
          onPress={onBack}
          accessibilityRole="button"
        >
          <Text style={styles.ctaLabel}>Nouvelle analyse</Text>
        </Pressable>
      </ScrollView>
    </SafeAreaView>
  );
}

function Section({ title, children }: { title: string; children: React.ReactNode }) {
  return (
    <View style={styles.section}>
      <Text style={styles.sectionTitle}>{title}</Text>
      {children}
    </View>
  );
}

// accent : couleur semantique du lisere (Points forts = vert, Questions = ambre,
// Pistes de negociation = rouge), pour que la marge porte le sens de la section.
function ActionList({ title, items, accent }: { title: string; items: string[]; accent: string }) {
  if (!items.length) return null;
  return (
    <View style={styles.section}>
      <Text style={styles.sectionTitle}>{title}</Text>
      {items.map((it, i) => (
        <View key={i} style={styles.listRow}>
          <View style={[styles.listMark, { backgroundColor: accent }]} />
          <Text style={styles.listText}>{it}</Text>
        </View>
      ))}
    </View>
  );
}

const styles = StyleSheet.create({
  root: { flex: 1, backgroundColor: colors.parchment },
  content: { padding: spacing.s5, gap: spacing.s5, paddingBottom: spacing.s8 },

  hero: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: spacing.s5,
    flexWrap: 'wrap',
  },
  heroText: { flex: 1, minWidth: 160, gap: spacing.s2 },
  eyebrow: {
    fontFamily: fontFamily.sansMedium,
    fontSize: 11,
    letterSpacing: 1.3,
    textTransform: 'uppercase',
    color: colors.stone,
  },
  verdict: {
    fontFamily: fontFamily.serifItalic,
    fontSize: fontSize.xxl,
    lineHeight: fontSize.xxl,
  },
  confidence: {
    fontFamily: fontFamily.sans,
    fontSize: fontSize.xs,
    color: colors.stone,
  },

  section: { gap: spacing.s2 },
  sectionTitle: {
    fontFamily: fontFamily.serif,
    fontSize: fontSize.lg,
    color: colors.ink,
    marginBottom: spacing.s1,
  },

  card: {
    flexDirection: 'row',
    backgroundColor: colors.paper,
    borderWidth: 1,
    borderColor: colors.stoneLine,
    borderRadius: radii.lg,
    overflow: 'hidden',
  },
  pillarAccent: { width: 4 },
  pillarBody: { flex: 1, padding: spacing.s4, gap: spacing.s1 },
  pillarLabel: {
    fontFamily: fontFamily.serif,
    fontSize: fontSize.md,
    color: colors.ink,
  },
  pillarVerdict: {
    fontFamily: fontFamily.monoRegular,
    fontSize: fontSize.sm,
    color: colors.stone,
  },
  body: {
    fontFamily: fontFamily.sans,
    fontSize: fontSize.sm,
    color: colors.ink2,
    lineHeight: fontSize.sm * 1.55,
  },

  listRow: { flexDirection: 'row', gap: spacing.s3, paddingVertical: spacing.s1 },
  listMark: {
    width: 2,
    borderRadius: 1,
    backgroundColor: colors.brick,
    alignSelf: 'stretch',
  },
  listText: {
    flex: 1,
    fontFamily: fontFamily.sans,
    fontSize: fontSize.base,
    color: colors.ink2,
    lineHeight: fontSize.base * 1.5,
  },

  // Cachet « contexte local » : SEUL endroit ou l'or de Jaumont est utilise.
  cachet: {
    backgroundColor: colors.jaumontSoft,
    borderWidth: 1,
    borderColor: colors.jaumont,
    borderRadius: radii.lg,
    padding: spacing.s5,
    gap: spacing.s2,
  },
  cachetEyebrow: {
    fontFamily: fontFamily.sansMedium,
    fontSize: 11,
    letterSpacing: 1.3,
    textTransform: 'uppercase',
    color: colors.jaumont,
  },
  cachetDistrict: {
    fontFamily: fontFamily.serif,
    fontSize: fontSize.lg,
    color: colors.ink,
  },
  cachetSummary: {
    fontFamily: fontFamily.sans,
    fontSize: fontSize.sm,
    color: colors.ink2,
    lineHeight: fontSize.sm * 1.55,
  },
  factRow: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    gap: spacing.s3,
    paddingTop: spacing.s1,
  },
  factLabel: {
    fontFamily: fontFamily.sans,
    fontSize: fontSize.sm,
    color: colors.ink3,
    flexShrink: 1,
  },
  factValue: {
    fontFamily: fontFamily.monoRegular,
    fontSize: fontSize.sm,
    color: colors.ink,
    textAlign: 'right',
    flexShrink: 1,
  },
  claim: {
    fontFamily: fontFamily.sans,
    fontSize: fontSize.sm,
    color: colors.ink2,
    lineHeight: fontSize.sm * 1.5,
    paddingTop: spacing.s1,
  },

  disclaimer: {
    fontFamily: fontFamily.serifItalic,
    fontSize: fontSize.xs,
    color: colors.stone,
    lineHeight: fontSize.xs * 1.5,
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
