/**
 * audio-utils.ts — Extracted audio volume logic for The Obsidian Archive.
 *
 * Three core functions:
 *   buildNarrationMask  — pre-compute speech mask from word timestamps
 *   buildVolumeEnvelope — per-act volume shaping
 *   applyDucking        — narration-aware volume ducking
 *
 * Keeping this logic in pure functions (no React, no Remotion hooks)
 * makes it testable with Vitest and reusable across compositions.
 */

export interface WordTimestamp {
  word: string;
  start: number;
  end: number;
}

// ── Narration Mask ─────────────────────────────────────────────────────────

/**
 * Build a sorted array of speech intervals from word timestamps.
 * Adjacent words within `gapThreshold` seconds are merged into
 * continuous speech blocks to avoid rapid volume toggling.
 */
export function buildNarrationMask(
  words: WordTimestamp[],
  gapThreshold = 0.3,
): Array<{ start: number; end: number }> {
  if (!words || words.length === 0) return [];

  // Sort by start time (defensive — should already be sorted)
  const sorted = [...words].sort((a, b) => a.start - b.start);

  const intervals: Array<{ start: number; end: number }> = [];
  let current = { start: sorted[0].start, end: sorted[0].end };

  for (let i = 1; i < sorted.length; i++) {
    const w = sorted[i];
    if (w.start <= current.end + gapThreshold) {
      // Merge: extend current interval
      current.end = Math.max(current.end, w.end);
    } else {
      // Gap too large: finalize current, start new
      intervals.push({ ...current });
      current = { start: w.start, end: w.end };
    }
  }
  intervals.push({ ...current });

  return intervals;
}

/**
 * Compute minimum distance from a time point to any speech interval.
 * Returns 0 when inside a speech interval.
 */
export function distanceToSpeech(
  time: number,
  mask: Array<{ start: number; end: number }>,
): number {
  if (mask.length === 0) return 99999; // No speech = music plays freely

  // Binary search for nearest interval
  let lo = 0;
  let hi = mask.length - 1;

  while (lo <= hi) {
    const mid = (lo + hi) >> 1;
    const interval = mask[mid];

    if (time >= interval.start && time <= interval.end) {
      return 0; // Inside speech
    }
    if (time < interval.start) {
      hi = mid - 1;
    } else {
      lo = mid + 1;
    }
  }

  // Check distances to nearest intervals
  let minDist = Infinity;
  if (lo < mask.length) {
    minDist = Math.min(minDist, mask[lo].start - time);
  }
  if (lo > 0) {
    minDist = Math.min(minDist, time - mask[lo - 1].end);
  }
  return Math.max(0, minDist);
}

// ── Volume Envelope ────────────────────────────────────────────────────────

export interface ActBoundaries {
  /** 0-1 progress where Act 2 begins (default: 0.25) */
  act2Start?: number;
  /** 0-1 progress where Act 3 begins (default: 0.65) */
  act3Start?: number;
  /** 0-1 progress where Ending begins (default: 0.90) */
  endingStart?: number;
}

export interface ActMultipliers {
  act1?: number;
  act2?: number;
  act3?: number;
  ending?: number;
}

const DEFAULT_BOUNDARIES: Required<ActBoundaries> = {
  act2Start: 0.25,
  act3Start: 0.65,
  endingStart: 0.90,
};

const DEFAULT_MULTIPLIERS: Required<ActMultipliers> = {
  act1: 0.80,
  act2: 1.20,
  act3: 0.60,
  ending: 1.40,
};

/**
 * Get the act-based volume multiplier for a given progress (0-1).
 *
 *   Act 1 (0–25%):    0.9  — moderate, building
 *   Act 2 (25–65%):   1.1  — tension rising
 *   Act 3 (65–90%):   0.75 — quieter, let narration carry
 *   Ending (90–100%): 1.15 — swell for emotional close
 */
export function buildVolumeEnvelope(
  progress: number,
  boundaries: ActBoundaries = {},
  multipliers: ActMultipliers = {},
): number {
  const b = { ...DEFAULT_BOUNDARIES, ...boundaries };
  const m = { ...DEFAULT_MULTIPLIERS, ...multipliers };

  if (progress < b.act2Start) return m.act1;
  if (progress < b.act3Start) return m.act2;
  if (progress < b.endingStart) return m.act3;
  return m.ending;
}

// ── Ducking ────────────────────────────────────────────────────────────────

export interface DuckingConfig {
  /** Volume during speech (default: 0.13) */
  speechVolume?: number;
  /** Volume during silence (default: 0.28) */
  silenceVolume?: number;
  /** Ramp duration in seconds (default: 0.5) */
  rampSeconds?: number;
}

const DEFAULT_DUCKING: Required<DuckingConfig> = {
  speechVolume: 0.08,
  silenceVolume: 0.38,
  rampSeconds: 0.5,
};

/**
 * Compute the ducked volume at a given time.
 *
 * Smoothly ramps between speechVolume (during narration) and
 * silenceVolume (during gaps) over rampSeconds.
 *
 * @param time Current time in seconds.
 * @param mask Pre-computed narration mask from buildNarrationMask().
 * @param config Ducking parameters.
 * @returns Base volume (before act multiplier).
 */
export function applyDucking(
  time: number,
  mask: Array<{ start: number; end: number }>,
  config: DuckingConfig = {},
): number {
  const c = { ...DEFAULT_DUCKING, ...config };
  const dist = distanceToSpeech(time, mask);
  const t = Math.min(dist / c.rampSeconds, 1);
  return c.speechVolume + t * (c.silenceVolume - c.speechVolume);
}

// ── Crossfade ──────────────────────────────────────────────────────────────

/**
 * Compute crossfade multiplier for primary/secondary tracks.
 *
 * @param progress 0-1 overall progress.
 * @param role 'primary' or 'secondary'.
 * @param crossfadeStart Progress where crossfade begins (default: 0.60).
 * @param crossfadeEnd Progress where crossfade completes (default: 0.70).
 * @returns Multiplier (0-1) for the track's volume.
 */
export function crossfadeMultiplier(
  progress: number,
  role: 'primary' | 'secondary',
  crossfadeStart = 0.60,
  crossfadeEnd = 0.70,
): number {
  if (progress < crossfadeStart) {
    return role === 'primary' ? 1.0 : 0.0;
  }
  if (progress >= crossfadeEnd) {
    return role === 'primary' ? 0.5 : 1.0;
  }
  // Linear interpolation during crossfade window
  const t = (progress - crossfadeStart) / (crossfadeEnd - crossfadeStart);
  return role === 'primary' ? 1.0 - t * 0.5 : t;
}

// ── Ambient Volume ─────────────────────────────────────────────────────────

/**
 * Compute per-scene ambient sound volume.
 *
 * @param sceneProgress 0-1 progress within the current scene.
 * @param isSpeaking Whether narration is active at this point.
 * @param fadeRatio Fraction of scene duration for fade in/out (default: 0.1).
 * @returns Ambient volume.
 */
export function ambientVolume(
  sceneProgress: number,
  isSpeaking: boolean,
  fadeRatio = 0.1,
): number {
  let envFade: number;
  if (sceneProgress < fadeRatio) {
    envFade = sceneProgress / fadeRatio;
  } else if (sceneProgress > 1 - fadeRatio) {
    envFade = (1 - sceneProgress) / fadeRatio;
  } else {
    envFade = 1;
  }
  return envFade * (isSpeaking ? 0.03 : 0.08);
}

// ── Scene Lookup ─────────────────────────────────────────────────────────

export interface AudioScene {
  start_time: number;
  end_time: number;
  intent_scene_energy?: number;
  intent_music_volume_base?: number;
}

/**
 * Find the scene that contains a given frame using binary search.
 * Scenes are sorted by start_time — O(log n) instead of O(n).
 */
function getSceneAtFrame(
  scenes: AudioScene[],
  frame: number,
  fps: number,
): AudioScene | null {
  let lo = 0;
  let hi = scenes.length - 1;
  while (lo <= hi) {
    const mid = (lo + hi) >> 1;
    const s = scenes[mid];
    const startFrame = Math.floor(s.start_time * fps);
    const endFrame = Math.floor(s.end_time * fps);
    if (frame < startFrame) {
      hi = mid - 1;
    } else if (frame >= endFrame) {
      lo = mid + 1;
    } else {
      return s;
    }
  }
  return null;
}

// ── Composite Helpers ──────────────────────────────────────────────────────

/**
 * Full primary music volume at a given frame.
 * Combines intent base + act envelope + ducking + crossfade + silence beats.
 */
export function primaryMusicVolume(
  frame: number,
  fps: number,
  totalDuration: number,
  mask: Array<{ start: number; end: number }>,
  hasSecondary: boolean,
  scenes: AudioScene[] = [],
  duckingConfig: DuckingConfig = {},
  actMultipliersConfig: ActMultipliers = {},
): number {
  const time = frame / fps;
  const progress = time / (totalDuration || 1);

  // Scene-aware intent base volume
  const scene = scenes.length > 0 ? getSceneAtFrame(scenes, frame, fps) : null;
  const intentBase = scene?.intent_music_volume_base ?? 0.5;

  // Silence beat override: near-zero music for very low energy scenes
  if (scene && (scene.intent_scene_energy ?? 0.5) < 0.15) {
    return 0.02; // Near-silence for devastating moments
  }

  const actMul = buildVolumeEnvelope(progress, {}, actMultipliersConfig);
  const crossMul = hasSecondary ? crossfadeMultiplier(progress, 'primary') : 1.0;
  const ducked = applyDucking(time, mask, duckingConfig);
  return Math.min(1.0, intentBase * actMul * ducked * crossMul);
}

/**
 * Full secondary music volume at a given frame.
 * Combines ducking + crossfade + intent base (no act shaping — secondary is emotional bed).
 */
export function secondaryMusicVolume(
  frame: number,
  fps: number,
  totalDuration: number,
  mask: Array<{ start: number; end: number }>,
  scenes: AudioScene[] = [],
  duckingConfig: DuckingConfig = {},
): number {
  const time = frame / fps;
  const progress = time / (totalDuration || 1);

  const scene = scenes.length > 0 ? getSceneAtFrame(scenes, frame, fps) : null;
  const intentBase = scene?.intent_music_volume_base ?? 0.5;

  // Silence beat override
  if (scene && (scene.intent_scene_energy ?? 0.5) < 0.15) {
    return 0.01;
  }

  // Secondary track uses softer ducking defaults, overridden by config
  const secondaryDucking = {
    speechVolume: 0.06,
    silenceVolume: 0.30,
    ...duckingConfig,
  };
  const crossMul = crossfadeMultiplier(progress, 'secondary');
  const ducked = applyDucking(time, mask, secondaryDucking);
  return Math.min(1.0, intentBase * ducked * crossMul);
}


/**
 * Per-stem volume for separated music tracks (bass, drums, instruments).
 * Each stem has its own ducking profile — drums stay rhythmic during speech,
 * instruments duck hard, bass stays warm.
 */
export interface StemDuckingConfig {
  bass?: { speechVolume?: number; silenceVolume?: number };
  drums?: { speechVolume?: number; silenceVolume?: number };
  instruments?: { speechVolume?: number; silenceVolume?: number };
}

const DEFAULT_STEM_DUCKING: Required<StemDuckingConfig> = {
  bass:        { speechVolume: 0.15, silenceVolume: 0.35 },
  drums:       { speechVolume: 0.20, silenceVolume: 0.30 },
  instruments: { speechVolume: 0.05, silenceVolume: 0.40 },
};

export function stemVolume(
  frame: number,
  stem: 'bass' | 'drums' | 'instruments',
  fps: number,
  totalDuration: number,
  mask: Array<{ start: number; end: number }>,
  hasSecondary: boolean,
  scenes: AudioScene[] = [],
  stemDuckingConfig: StemDuckingConfig = {},
  actMultipliersConfig: ActMultipliers = {},
): number {
  const time = frame / fps;
  const progress = time / (totalDuration || 1);

  const scene = scenes.length > 0 ? getSceneAtFrame(scenes, frame, fps) : null;
  const intentBase = scene?.intent_music_volume_base ?? 0.5;

  // Silence beat override
  if (scene && (scene.intent_scene_energy ?? 0.5) < 0.15) {
    return stem === 'drums' ? 0.03 : 0.01;
  }

  const actMul = buildVolumeEnvelope(progress, undefined, actMultipliersConfig);
  const crossMul = hasSecondary ? crossfadeMultiplier(progress, 'primary') : 1.0;

  // Stem-specific ducking
  const stemConfig = { ...DEFAULT_STEM_DUCKING[stem], ...(stemDuckingConfig[stem] || {}) };
  const ducked = applyDucking(time, mask, {
    speechVolume: stemConfig.speechVolume,
    silenceVolume: stemConfig.silenceVolume,
  });

  return Math.min(1.0, intentBase * actMul * ducked * crossMul);
}
