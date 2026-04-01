import { describe, it, expect } from 'vitest';
import {
  buildNarrationMask,
  distanceToSpeech,
  buildVolumeEnvelope,
  applyDucking,
  crossfadeMultiplier,
  ambientVolume,
  primaryMusicVolume,
  secondaryMusicVolume,
  type WordTimestamp,
} from '../audio-utils';

// ── buildNarrationMask ──────────────────────────────────────────────────────

describe('buildNarrationMask', () => {
  it('returns empty for empty input', () => {
    expect(buildNarrationMask([])).toEqual([]);
  });

  it('returns single interval for one word', () => {
    const words: WordTimestamp[] = [{ word: 'hello', start: 1.0, end: 1.5 }];
    expect(buildNarrationMask(words)).toEqual([{ start: 1.0, end: 1.5 }]);
  });

  it('merges adjacent words within gap threshold', () => {
    const words: WordTimestamp[] = [
      { word: 'the', start: 0, end: 0.2 },
      { word: 'quick', start: 0.3, end: 0.6 },
      { word: 'fox', start: 0.7, end: 1.0 },
    ];
    // Gap between words is 0.1s and 0.1s — within default 0.3s threshold
    const mask = buildNarrationMask(words);
    expect(mask).toHaveLength(1);
    expect(mask[0]).toEqual({ start: 0, end: 1.0 });
  });

  it('splits at gaps larger than threshold', () => {
    const words: WordTimestamp[] = [
      { word: 'first', start: 0, end: 0.5 },
      { word: 'second', start: 2.0, end: 2.5 },
    ];
    const mask = buildNarrationMask(words);
    expect(mask).toHaveLength(2);
    expect(mask[0]).toEqual({ start: 0, end: 0.5 });
    expect(mask[1]).toEqual({ start: 2.0, end: 2.5 });
  });

  it('respects custom gap threshold', () => {
    const words: WordTimestamp[] = [
      { word: 'a', start: 0, end: 0.2 },
      { word: 'b', start: 0.6, end: 0.8 },
    ];
    // Default threshold 0.3s: gap of 0.4s splits
    expect(buildNarrationMask(words, 0.3)).toHaveLength(2);
    // Larger threshold: merges
    expect(buildNarrationMask(words, 0.5)).toHaveLength(1);
  });

  it('handles unsorted input', () => {
    const words: WordTimestamp[] = [
      { word: 'b', start: 1.0, end: 1.5 },
      { word: 'a', start: 0, end: 0.5 },
    ];
    const mask = buildNarrationMask(words);
    expect(mask[0].start).toBe(0);
  });
});

// ── distanceToSpeech ────────────────────────────────────────────────────────

describe('distanceToSpeech', () => {
  const mask = [
    { start: 1.0, end: 2.0 },
    { start: 5.0, end: 6.0 },
  ];

  it('returns 0 inside speech interval', () => {
    expect(distanceToSpeech(1.5, mask)).toBe(0);
    expect(distanceToSpeech(5.5, mask)).toBe(0);
  });

  it('returns 0 at interval boundaries', () => {
    expect(distanceToSpeech(1.0, mask)).toBe(0);
    expect(distanceToSpeech(2.0, mask)).toBe(0);
  });

  it('returns distance before first interval', () => {
    expect(distanceToSpeech(0.5, mask)).toBeCloseTo(0.5);
  });

  it('returns distance between intervals', () => {
    expect(distanceToSpeech(3.0, mask)).toBeCloseTo(1.0);
    expect(distanceToSpeech(4.0, mask)).toBeCloseTo(1.0);
  });

  it('returns distance after last interval', () => {
    expect(distanceToSpeech(7.0, mask)).toBeCloseTo(1.0);
  });

  it('returns 99999 for empty mask', () => {
    expect(distanceToSpeech(5.0, [])).toBe(99999);
  });
});

// ── buildVolumeEnvelope ─────────────────────────────────────────────────────

describe('buildVolumeEnvelope', () => {
  it('returns act1 multiplier at start', () => {
    expect(buildVolumeEnvelope(0)).toBe(0.85);
    expect(buildVolumeEnvelope(0.24)).toBe(0.85);
  });

  it('returns act2 multiplier at midpoint', () => {
    expect(buildVolumeEnvelope(0.25)).toBe(1.00);
    expect(buildVolumeEnvelope(0.5)).toBe(1.00);
  });

  it('returns act3 multiplier for reveals', () => {
    expect(buildVolumeEnvelope(0.65)).toBe(1.25);
    expect(buildVolumeEnvelope(0.8)).toBe(1.25);
  });

  it('returns ending swell', () => {
    expect(buildVolumeEnvelope(0.9)).toBe(0.90);
    expect(buildVolumeEnvelope(1.0)).toBe(0.90);
  });

  it('accepts custom boundaries', () => {
    expect(buildVolumeEnvelope(0.1, { act2Start: 0.1 })).toBe(1.00);
  });

  it('accepts custom multipliers', () => {
    expect(buildVolumeEnvelope(0, {}, { act1: 0.5 })).toBe(0.5);
  });
});

// ── applyDucking ────────────────────────────────────────────────────────────

describe('applyDucking', () => {
  const mask = [{ start: 1.0, end: 2.0 }];

  it('returns speechVolume during speech', () => {
    expect(applyDucking(1.5, mask)).toBe(0.18);
  });

  it('returns silenceVolume far from speech', () => {
    expect(applyDucking(10.0, mask)).toBe(0.28);
  });

  it('ramps between speech and silence with asymmetric timing', () => {
    // At 0.2s after speech ends: release ramp, t = 0.2/0.4 = 0.5
    const vol = applyDucking(2.2, mask);
    expect(vol).toBeCloseTo(0.18 + 0.5 * 0.10, 2);
  });

  it('accepts custom ducking config', () => {
    const vol = applyDucking(1.5, mask, { speechVolume: 0.05 });
    expect(vol).toBe(0.05);
  });
});

// ── crossfadeMultiplier ─────────────────────────────────────────────────────

describe('crossfadeMultiplier', () => {
  it('primary is 1.0 before crossfade', () => {
    expect(crossfadeMultiplier(0.5, 'primary')).toBe(1.0);
  });

  it('secondary is 0.0 before crossfade', () => {
    expect(crossfadeMultiplier(0.5, 'secondary')).toBe(0.0);
  });

  it('primary is 0.5 after crossfade', () => {
    expect(crossfadeMultiplier(0.75, 'primary')).toBe(0.5);
  });

  it('secondary is 1.0 after crossfade', () => {
    expect(crossfadeMultiplier(0.75, 'secondary')).toBe(1.0);
  });

  it('interpolates during crossfade window', () => {
    // Midpoint of 0.60-0.70 = 0.65
    expect(crossfadeMultiplier(0.65, 'primary')).toBeCloseTo(0.75);
    expect(crossfadeMultiplier(0.65, 'secondary')).toBeCloseTo(0.5);
  });
});

// ── ambientVolume ───────────────────────────────────────────────────────────

describe('ambientVolume', () => {
  it('fades in at start of scene', () => {
    // At 5% progress with 10% fade ratio: 0.05/0.10 = 0.5 envelope
    const vol = ambientVolume(0.05, false);
    expect(vol).toBeCloseTo(0.5 * 0.08);
  });

  it('fades out at end of scene', () => {
    const vol = ambientVolume(0.95, false);
    expect(vol).toBeCloseTo(0.5 * 0.08);
  });

  it('ducks during speech', () => {
    expect(ambientVolume(0.5, true)).toBeCloseTo(0.03);
  });

  it('full volume during silence', () => {
    expect(ambientVolume(0.5, false)).toBeCloseTo(0.08);
  });
});

// ── Composite helpers ───────────────────────────────────────────────────────

describe('primaryMusicVolume', () => {
  const mask = buildNarrationMask([
    { word: 'test', start: 1.0, end: 1.5 },
  ]);

  it('returns positive value', () => {
    const vol = primaryMusicVolume(30, 30, 100, mask, false);
    expect(vol).toBeGreaterThan(0);
  });

  it('is lower during speech than silence', () => {
    // Frame 30 = 1.0s (during speech)
    const duringSpeech = primaryMusicVolume(30, 30, 100, mask, false);
    // Frame 300 = 10s (silence)
    const duringSilence = primaryMusicVolume(300, 30, 100, mask, false);
    expect(duringSpeech).toBeLessThan(duringSilence);
  });

  it('applies crossfade when secondary exists', () => {
    // At progress 0.75 with secondary: primary gets 0.5 crossfade multiplier
    const withSecondary = primaryMusicVolume(2250, 30, 100, mask, true);
    const withoutSecondary = primaryMusicVolume(2250, 30, 100, mask, false);
    expect(withSecondary).toBeLessThan(withoutSecondary);
  });
});

describe('secondaryMusicVolume', () => {
  const mask = buildNarrationMask([
    { word: 'test', start: 1.0, end: 1.5 },
  ]);

  it('is silent before crossfade', () => {
    // Frame 30 = 1s, progress = 0.01 — well before 0.60
    const vol = secondaryMusicVolume(30, 30, 100, mask);
    expect(vol).toBe(0);
  });

  it('has volume after crossfade', () => {
    // Frame 2400 = 80s, progress = 0.8 — after crossfade
    const vol = secondaryMusicVolume(2400, 30, 100, mask);
    expect(vol).toBeGreaterThan(0);
  });
});
