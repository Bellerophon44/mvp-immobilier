import React from 'react';
import { View, Text, StyleSheet } from 'react-native';
import Svg, { Circle } from 'react-native-svg';
import { colors, fontFamily, verdictMeta } from '../theme';

// Anneau de score porte du web (frontend/components/design/ScoreRing.tsx) :
// deux cercles (piste stoneLine + arc colore selon verdictMeta), gros nombre
// central en mono + « / 100 ». Pas d'animation (rendu statique mobile).
export function ScoreDonut({
  score = 0,
  size = 148,
  stroke = 7,
}: {
  score?: number;
  size?: number;
  stroke?: number;
}) {
  const r = (size - stroke * 2) / 2;
  const c = 2 * Math.PI * r;
  const clamped = Math.max(0, Math.min(100, score));
  const offset = c - (clamped / 100) * c;
  const color = verdictMeta(score).color;
  const center = size / 2;

  return (
    <View style={{ width: size, height: size }}>
      <Svg width={size} height={size} style={styles.svg}>
        <Circle cx={center} cy={center} r={r} fill="none" stroke={colors.stoneLine} strokeWidth={stroke} />
        <Circle
          cx={center}
          cy={center}
          r={r}
          fill="none"
          stroke={color}
          strokeWidth={stroke}
          strokeLinecap="round"
          strokeDasharray={c}
          strokeDashoffset={offset}
        />
      </Svg>
      <View style={[StyleSheet.absoluteFill, styles.label]}>
        <Text style={[styles.number, { fontSize: size * 0.3 }]}>{Math.round(clamped)}</Text>
        <Text style={styles.outOf}>/ 100</Text>
      </View>
    </View>
  );
}

const styles = StyleSheet.create({
  // L'arc demarre a midi : on tourne le SVG de -90deg comme la version web.
  svg: { transform: [{ rotate: '-90deg' }] },
  label: { alignItems: 'center', justifyContent: 'center' },
  number: {
    fontFamily: fontFamily.mono,
    color: colors.ink,
    letterSpacing: -1,
  },
  outOf: {
    fontFamily: fontFamily.mono,
    fontSize: 11,
    color: colors.stone,
    letterSpacing: 0.6,
    marginTop: 4,
  },
});
