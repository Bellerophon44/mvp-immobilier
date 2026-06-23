import React from 'react';
import { View, Text, StyleSheet } from 'react-native';
import Svg, { Path } from 'react-native-svg';
import { colors, fontFamily } from '../theme';

// Logo Coherence porte du web (frontend/components/design/Wordmark.tsx) :
// losange brique exterieur + losange parchemin interieur + mot en serif.
export function Wordmark({ compact = false, size = 28 }: { compact?: boolean; size?: number }) {
  return (
    <View style={styles.row}>
      <Svg width={size} height={size} viewBox="0 0 64 64">
        <Path d="M32 6 L58 32 L32 58 L6 32 Z" fill={colors.brick} />
        <Path d="M32 20 L44 32 L32 44 L20 32 Z" fill={colors.parchment} />
      </Svg>
      {!compact ? (
        <Text style={[styles.word, { fontSize: size * 0.95 }]}>Cohérence</Text>
      ) : null}
    </View>
  );
}

const styles = StyleSheet.create({
  row: { flexDirection: 'row', alignItems: 'center', gap: 10 },
  word: {
    fontFamily: fontFamily.serif,
    lineHeight: undefined,
    letterSpacing: -0.5,
    color: colors.ink,
  },
});
