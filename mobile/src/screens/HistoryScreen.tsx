import React, { useCallback, useEffect, useState } from 'react';
import {
  SafeAreaView,
  View,
  Text,
  Pressable,
  ScrollView,
  ActivityIndicator,
  Alert,
  StyleSheet,
} from 'react-native';
import { ApiResult } from '../lib/types';
import {
  HistoryRecord,
  HistoryStore,
  listAnalyses,
  removeAnalysis,
  clearAnalyses,
} from '../lib/history';
import { ScoreDonut } from '../components/ScoreDonut';
import { Wordmark } from '../components/Wordmark';
import {
  colors,
  spacing,
  radii,
  fontSize,
  fontFamily,
  verdictColorFromLabel,
} from '../theme';

/**
 * Ecran « Mes analyses » (etat 'history' de App.tsx). SPEC
 * mobile-tranche-b-historique §3.3 / §7.B. Liste les enregistrements triees plus
 * recent d'abord (via listAnalyses, SOURCE UNIQUE DE VERITE), chaque vignette =
 * date + titre + ScoreDonut colore par verdictColorFromLabel(result.verdict).
 *
 * Toute la logique (tri, dedup, plafond, whitelist) vit dans src/lib/history.ts :
 * cet ecran ne fait que rendre et deleguer (listAnalyses/removeAnalysis/
 * clearAnalyses). Aucun appel reseau : rouvrir reaffiche un ApiResult stocke.
 *
 * Robustesse (AC-B8) : un echec du store n'est jamais propage en crash ; il
 * affiche un etat d'erreur LISIBLE. L'etat vide est explicite.
 */
export function HistoryScreen({
  store,
  onOpen,
  onBack,
}: {
  store: HistoryStore;
  onOpen: (result: ApiResult) => void;
  onBack: () => void;
}) {
  const [records, setRecords] = useState<HistoryRecord[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const refresh = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const list = await listAnalyses(store);
      setRecords(list);
    } catch {
      // why: on n'expose pas le message technique du store a l'acheteur ; un
      // libelle lisible suffit, le detail reste dans le throw cote logique.
      setError('Impossible de charger vos analyses pour le moment.');
      setRecords([]);
    } finally {
      setLoading(false);
    }
  }, [store]);

  useEffect(() => {
    void refresh();
  }, [refresh]);

  const handleRemove = useCallback(
    async (id: string) => {
      try {
        const next = await removeAnalysis(store, id);
        setRecords(next);
      } catch {
        setError('La suppression a echoue. Reessayez.');
      }
    },
    [store],
  );

  const handleClearAll = useCallback(() => {
    if (records.length === 0) {
      return;
    }
    Alert.alert(
      'Tout effacer',
      'Supprimer definitivement toutes vos analyses enregistrees ?',
      [
        { text: 'Annuler', style: 'cancel' },
        {
          text: 'Tout effacer',
          style: 'destructive',
          onPress: async () => {
            try {
              await clearAnalyses(store);
              setRecords([]);
            } catch {
              setError("L'effacement a echoue. Reessayez.");
            }
          },
        },
      ],
    );
  }, [records.length, store]);

  return (
    <SafeAreaView style={styles.root}>
      <View style={styles.header}>
        <Pressable style={styles.back} onPress={onBack} accessibilityRole="button">
          <Text style={styles.backLabel}>Retour</Text>
        </Pressable>
        <Wordmark compact />
      </View>

      <View style={styles.titleBlock}>
        <Text style={styles.eyebrow}>Sur cet appareil</Text>
        <Text style={styles.title}>Mes analyses</Text>
      </View>

      <ScrollView contentContainerStyle={styles.content}>
        {loading ? (
          <View style={styles.centered}>
            <ActivityIndicator color={colors.brick} />
          </View>
        ) : error ? (
          <View style={styles.errorBanner}>
            <Text style={styles.errorText}>{error}</Text>
            <Pressable onPress={refresh} accessibilityRole="button">
              <Text style={styles.retry}>Reessayer</Text>
            </Pressable>
          </View>
        ) : records.length === 0 ? (
          <View style={styles.centered}>
            <Text style={styles.empty}>Aucune analyse enregistree</Text>
            <Text style={styles.emptyHint}>
              Lancez une analyse : elle apparaitra ici automatiquement.
            </Text>
          </View>
        ) : (
          records.map((r) => (
            <HistoryCard key={r.id} record={r} onOpen={onOpen} onRemove={handleRemove} />
          ))
        )}
      </ScrollView>

      {!loading && !error && records.length > 0 ? (
        <View style={styles.footer}>
          <Pressable onPress={handleClearAll} accessibilityRole="button">
            <Text style={styles.clearAll}>Tout effacer</Text>
          </Pressable>
        </View>
      ) : null}
    </SafeAreaView>
  );
}

function HistoryCard({
  record,
  onOpen,
  onRemove,
}: {
  record: HistoryRecord;
  onOpen: (result: ApiResult) => void;
  onRemove: (id: string) => void;
}) {
  const verdictColor = verdictColorFromLabel(record.result.verdict);
  return (
    <View style={styles.card}>
      <Pressable
        style={styles.cardMain}
        onPress={() => onOpen(record.result)}
        accessibilityRole="button"
      >
        <ScoreDonut score={record.result.global_score} size={56} stroke={4} color={verdictColor} />
        <View style={styles.cardText}>
          <Text style={styles.cardDate}>{formatDate(record.savedAt)}</Text>
          <Text style={styles.cardTitle} numberOfLines={2}>
            {record.title}
          </Text>
          <Text style={[styles.cardVerdict, { color: verdictColor }]}>
            {record.result.verdict}
          </Text>
        </View>
      </Pressable>
      <Pressable
        style={styles.remove}
        onPress={() => onRemove(record.id)}
        accessibilityRole="button"
        accessibilityLabel="Supprimer cette analyse"
        hitSlop={8}
      >
        <Text style={styles.removeLabel}>Supprimer</Text>
      </Pressable>
    </View>
  );
}

// Format court lisible (jj/mm/aaaa) sans dependance i18n ; epoch ms -> Date.
function formatDate(savedAt: number): string {
  const d = new Date(savedAt);
  const dd = String(d.getDate()).padStart(2, '0');
  const mm = String(d.getMonth() + 1).padStart(2, '0');
  const yyyy = d.getFullYear();
  return `${dd}/${mm}/${yyyy}`;
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
  titleBlock: {
    paddingHorizontal: spacing.s5,
    paddingBottom: spacing.s3,
    gap: spacing.s1,
  },
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
    color: colors.ink,
  },
  content: {
    paddingHorizontal: spacing.s5,
    paddingBottom: spacing.s6,
    gap: spacing.s3,
    flexGrow: 1,
  },
  centered: {
    flex: 1,
    alignItems: 'center',
    justifyContent: 'center',
    paddingVertical: spacing.s8,
    gap: spacing.s2,
  },
  empty: {
    fontFamily: fontFamily.serif,
    fontSize: fontSize.md,
    color: colors.ink2,
  },
  emptyHint: {
    fontFamily: fontFamily.sans,
    fontSize: fontSize.sm,
    color: colors.stone,
    textAlign: 'center',
  },
  errorBanner: {
    backgroundColor: colors.brickSoft,
    borderRadius: radii.md,
    padding: spacing.s4,
    gap: spacing.s2,
  },
  errorText: {
    fontFamily: fontFamily.sans,
    fontSize: fontSize.sm,
    color: colors.brickDeep,
    lineHeight: fontSize.sm * 1.5,
  },
  retry: {
    fontFamily: fontFamily.sansMedium,
    fontSize: fontSize.sm,
    color: colors.brick,
  },
  card: {
    backgroundColor: colors.paper,
    borderWidth: 1,
    borderColor: colors.stoneLine,
    borderRadius: radii.lg,
    overflow: 'hidden',
  },
  cardMain: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: spacing.s4,
    padding: spacing.s4,
  },
  cardText: { flex: 1, gap: spacing.s1 },
  cardDate: {
    fontFamily: fontFamily.monoRegular,
    fontSize: fontSize.xs,
    color: colors.stone,
  },
  cardTitle: {
    fontFamily: fontFamily.serif,
    fontSize: fontSize.md,
    color: colors.ink,
  },
  cardVerdict: {
    fontFamily: fontFamily.sansMedium,
    fontSize: fontSize.sm,
  },
  remove: {
    borderTopWidth: 1,
    borderTopColor: colors.stoneLine,
    paddingVertical: spacing.s3,
    alignItems: 'center',
    minHeight: 44,
    justifyContent: 'center',
  },
  removeLabel: {
    fontFamily: fontFamily.sansMedium,
    fontSize: fontSize.sm,
    color: colors.brick,
  },
  footer: {
    paddingHorizontal: spacing.s5,
    paddingVertical: spacing.s4,
    borderTopWidth: 1,
    borderTopColor: colors.stoneLine,
    alignItems: 'center',
  },
  clearAll: {
    fontFamily: fontFamily.sansSemiBold,
    fontSize: fontSize.base,
    color: colors.brick,
    minHeight: 44,
    textAlignVertical: 'center',
  },
});
