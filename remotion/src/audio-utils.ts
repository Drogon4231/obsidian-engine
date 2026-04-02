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
  act1: 0.85,
  act2: 1.00,
  act3: 1.25,
  ending: 0.90,
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
  /** Volume during speech (default: 0.18) */
  speechVolume?: number;
  /** Volume during silence (default: 0.28) */
  silenceVolume?: number;
  /** Attack: seconds to duck DOWN when speech approaches (default: 0.1) */
  attackSeconds?: number;
  /** Release: seconds to bring music back UP after speech ends (default: 0.4) */
  releaseSeconds?: number;
  /** @deprecated Use attackSeconds/releaseSeconds. Symmetric ramp fallback. */
  rampSeconds?: number;
}

const DEFAULT_DUCKING = {
  speechVolume: 0.18,
  silenceVolume: 0.28,
  attackSeconds: 0.1,
  releaseSeconds: 0.4,
};

/**
 * Compute the ducked volume at a given time.
 *
 * Uses asymmetric ramp: fast attack (duck down quickly when speech starts)
 * and slower release (bring music back gently after speech ends).
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
  const speechVol = config.speechVolume ?? DEFAULT_DUCKING.speechVolume;
  const silenceVol = config.silenceVolume ?? DEFAULT_DUCKING.silenceVolume;
  const attack = config.attackSeconds ?? config.rampSeconds ?? DEFAULT_DUCKING.attackSeconds;
  const release = config.releaseSeconds ?? config.rampSeconds ?? DEFAULT_DUCKING.releaseSeconds;

  const dist = distanceToSpeech(time, mask);
  if (dist === 0) return speechVol; // Inside speech — fully ducked

  // Determine if we're approaching speech (pre-speech) or leaving it (post-speech).
  // Use distanceToSpeech at time+ε: if distance decreases, we're moving toward speech.
  // Both calls use binary search — O(log n) — replacing the O(n) mask.some() scan.
  const isPreSpeech = mask.length > 0 && distanceToSpeech(time + 0.001, mask) < dist;
  const ramp = isPreSpeech ? attack : release;
  const t = Math.min(dist / ramp, 1);
  return speechVol + t * (silenceVol - speechVol);
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
  style: 'blend' | 'dip' = 'blend',
): number {
  if (progress < crossfadeStart) {
    return role === 'primary' ? 1.0 : 0.0;
  }
  if (progress >= crossfadeEnd) {
    return role === 'primary' ? (style === 'dip' ? 0.0 : 0.5) : 1.0;
  }

  const t = (progress - crossfadeStart) / (crossfadeEnd - crossfadeStart);

  if (style === 'dip') {
    // Dip crossfade: primary cosine-fades to 0, silence gap, secondary cosine-fades in
    // Eliminates key/tempo collision between tracks
    const dipMid = 0.5;
    const silenceGap = 0.08; // ~8% of crossfade window is silence
    if (t < dipMid - silenceGap) {
      // Primary fading out
      const fadeT = t / (dipMid - silenceGap);
      return role === 'primary' ? Math.cos(fadeT * Math.PI / 2) : 0;
    } else if (t < dipMid + silenceGap) {
      // Silence gap — both tracks at 0
      return 0;
    } else {
      // Secondary fading in
      const fadeT = (t - dipMid - silenceGap) / (1 - dipMid - silenceGap);
      return role === 'primary' ? 0 : Math.sin(fadeT * Math.PI / 2);
    }
  }

  // Blend crossfade (original behavior)
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
  intent_speech_intensity?: number;
  intent_silence_beat?: boolean;
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

// ── Silence Beat Ramp ─────────────────────────────────────────────────────

/**
 * Cosine (equal-power) volume ramp for silence beat scenes.
 * Replaces the hard `return 0.02` with a perceptually smooth transition.
 * Asymmetric: entry ramp is faster (1.5s) than exit (3.0s minimum) because ears
 * notice sounds appearing more than disappearing.
 * Guarantees at least 2s of actual silence in the middle of the beat.
 *
 * exitTarget: volume to ramp toward on exit (should be speechVol / ducked volume,
 * not normalVol — avoids jarring full-volume jump after silence).
 */
export function silenceBeatVolume(
  time: number,
  scene: AudioScene,
  normalVol: number,
  silenceFloor: number,
  entryRamp = 1.5,
  exitRamp = 3.0,
  exitTarget?: number,
): number {
  const sceneDur = scene.end_time - scene.start_time;
  const effectiveEntry = Math.min(entryRamp, Math.max(0.3, (sceneDur - 2.0) / 2));
  // Exit ramp minimum is 3.0s for a gentle rise back to speech-ducked volume
  const effectiveExit = Math.max(3.0, Math.min(exitRamp, Math.max(0.3, (sceneDur - 2.0) / 2)));
  const timeSinceStart = time - scene.start_time;
  const timeUntilEnd = scene.end_time - time;
  // On exit, ramp to exitTarget (speechVol / ducked) rather than full normalVol
  const rampTarget = exitTarget !== undefined ? exitTarget : normalVol;

  if (timeSinceStart < effectiveEntry) {
    const t = timeSinceStart / effectiveEntry;
    const curve = Math.cos(t * Math.PI / 2);
    return silenceFloor + (normalVol - silenceFloor) * curve;
  }
  if (timeUntilEnd < effectiveExit) {
    const t = timeUntilEnd / effectiveExit;
    const curve = Math.cos(t * Math.PI / 2);
    return silenceFloor + (rampTarget - silenceFloor) * curve;
  }
  return silenceFloor;
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

  // Compute normal volume first (needed for silence beat ramp)
  const actMul = buildVolumeEnvelope(progress, {}, actMultipliersConfig);
  const crossMul = hasSecondary ? crossfadeMultiplier(progress, 'primary') : 1.0;
  const ducked = applyDucking(time, mask, duckingConfig);
  const normalVol = Math.min(1.0, intentBase * actMul * ducked * crossMul);

  // Silence beat: cosine ramp to near-silence (replaces hard cut).
  // Exit ramp targets ducked (speechVol) not normalVol — avoids jarring volume jump.
  // silenceFloor is relative to the UN-DUCKED volume (intentBase) so the drop is
  // perceptible even when music is already ducked during speech.
  if (scene?.intent_silence_beat) {
    const undduckedBase = intentBase;
    const silenceFloor = Math.max(0.01, undduckedBase * 0.03);
    return silenceBeatVolume(time, scene, normalVol, silenceFloor, 1.5, 3.0, ducked);
  }

  return normalVol;
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

  // Compute normal volume first (needed for silence beat ramp)
  const secondaryDucking = {
    speechVolume: 0.06,
    silenceVolume: 0.30,
    ...duckingConfig,
  };
  const crossMul = crossfadeMultiplier(progress, 'secondary');
  const ducked = applyDucking(time, mask, secondaryDucking);
  const normalVol = Math.min(1.0, intentBase * ducked * crossMul);

  // Silence beat: cosine ramp to near-silence (replaces hard cut).
  // Exit ramp targets ducked volume not normalVol — avoids jarring volume jump.
  // silenceFloor is relative to the UN-DUCKED volume (intentBase).
  if (scene?.intent_silence_beat) {
    const undduckedBase = intentBase;
    const silenceFloor = Math.max(0.01, undduckedBase * 0.03);
    return silenceBeatVolume(time, scene, normalVol, silenceFloor, 1.5, 3.0, ducked);
  }

  return normalVol;
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
  bass:        { speechVolume: 0.10, silenceVolume: 0.35 },
  drums:       { speechVolume: 0.08, silenceVolume: 0.30 },
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

  // Compute normal volume first (needed for silence beat ramp)
  const actMul = buildVolumeEnvelope(progress, undefined, actMultipliersConfig);
  const crossMul = hasSecondary ? crossfadeMultiplier(progress, 'primary') : 1.0;

  // Stem-specific ducking
  const stemConfig = { ...DEFAULT_STEM_DUCKING[stem], ...(stemDuckingConfig[stem] || {}) };
  const ducked = applyDucking(time, mask, {
    speechVolume: stemConfig.speechVolume,
    silenceVolume: stemConfig.silenceVolume,
  });

  const normalVol = Math.min(1.0, intentBase * actMul * ducked * crossMul);

  // Silence beat: cosine ramp (drums keep faint pulse, others near-silent).
  // Exit ramp targets ducked volume not normalVol — avoids jarring volume jump.
  // silenceFloor is relative to the UN-DUCKED volume (intentBase).
  if (scene?.intent_silence_beat) {
    const undduckedBase = intentBase;
    const floor = stem === 'drums'
      ? Math.max(0.02, undduckedBase * 0.05)
      : Math.max(0.01, undduckedBase * 0.03);
    return silenceBeatVolume(time, scene, normalVol, floor, 1.5, 3.0, ducked);
  }

  return normalVol;
}
