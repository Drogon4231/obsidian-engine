import {useMemo} from 'react';
import {useCurrentFrame, useVideoConfig, interpolate, interpolateColors, spring} from 'remotion';

interface Word {
  word: string;
  start: number;
  end: number;
}

/**
 * Premium documentary-style subtitle captions.
 * Groups words into natural reading chunks (4-7 words),
 * splitting at punctuation boundaries when possible.
 * Features: slide-up entrance, word-by-word highlight with scale pop,
 * text stroke for contrast, larger bold font.
 */

interface CaptionGroup {
  words: Word[];
  text: string;
  start: number;
  end: number;
}

function buildCaptionGroups(words: Word[]): CaptionGroup[] {
  const groups: CaptionGroup[] = [];
  let current: Word[] = [];

  for (let i = 0; i < words.length; i++) {
    current.push(words[i]);
    const word = words[i].word;

    // Split at natural boundaries: punctuation or after 6 words
    const endsWithPunct = /[.!?,;:\u2014]$/.test(word);
    const atMaxLength = current.length >= 6;
    const atMinForPunct = current.length >= 3 && endsWithPunct;
    const isLast = i === words.length - 1;

    if (atMinForPunct || atMaxLength || isLast) {
      if (current.length > 0) {
        groups.push({
          words: [...current],
          text: current.map(w => w.word).join(' '),
          start: current[0].start,
          end: current[current.length - 1].end,
        });
        current = [];
      }
    }
  }
  return groups;
}

export const Captions: React.FC<{
  words: Word[];
  sceneStartTime: number;
  captionStyle?: 'standard' | 'emphasis' | 'whisper';
}> = ({words, sceneStartTime, captionStyle = 'standard'}) => {
  const frame = useCurrentFrame();
  const {fps} = useVideoConfig();

  const globalTime = sceneStartTime + frame / fps;

  const groups = useMemo(() => buildCaptionGroups(words), [words]);

  // Find active group
  const activeGroup = groups.find(g => globalTime >= g.start - 0.05 && globalTime < g.end + 0.15);

  if (!activeGroup) return null;

  // Slide-up entrance spring
  const groupStartFrame = Math.round((activeGroup.start - sceneStartTime) * fps);
  const localFrame = frame - groupStartFrame;
  const slideUp = spring({
    frame: Math.max(0, localFrame),
    fps,
    config: {damping: 18, stiffness: 140, mass: 0.8},
  });

  const fadeOutStart = activeGroup.end - 0.08;
  const opacity = globalTime > fadeOutStart
    ? interpolate(globalTime, [fadeOutStart, activeGroup.end + 0.1], [1, 0], {extrapolateLeft: 'clamp', extrapolateRight: 'clamp'})
    : 1;

  // Highlight the currently spoken word within the group
  const activeWordIdx = activeGroup.words.findIndex(
    w => globalTime >= w.start && globalTime < w.end
  );

  const clean = (w: string) => w.replace(/[^\p{L}\p{M}\p{N} '''.,!?;\u2014-]/gu, '');

  return (
    <div style={{
      position: 'absolute',
      bottom: 80,
      left: 0,
      right: 0,
      display: 'flex',
      justifyContent: 'center',
      alignItems: 'center',
      opacity,
      transform: `translateY(${interpolate(slideUp, [0, 1], [18, 0])}px)`,
      pointerEvents: 'none',
      zIndex: 200,
    }}>
      <div style={{
        position: 'relative',
        borderRadius: 10,
        padding: '16px 36px',
        maxWidth: '82%',
        textAlign: 'center',
        borderBottom: '2px solid rgba(240, 220, 160, 0.15)',
      }}>
        {/* Background + blur on a separate layer so blur doesn't bleed into text */}
        <div style={{
          position: 'absolute', top: 0, left: 0, right: 0, bottom: 0,
          backgroundColor: 'rgba(0, 0, 0, 0.78)',
          backdropFilter: 'blur(6px)',
          borderRadius: 10,
          zIndex: -1,
        }}/>
        {activeGroup.words.map((w, i) => {
          const isActive = i === activeWordIdx;
          const isPast = i < activeWordIdx;
          // Scale pop on active word
          const wordStartFrame = Math.round((w.start - sceneStartTime) * fps);
          const wordLocalFrame = frame - wordStartFrame;
          const wordScale = isActive ? spring({
            frame: Math.max(0, wordLocalFrame),
            fps,
            config: {damping: 12, stiffness: 200, mass: 0.5},
            from: 0.88,
            to: 1,
          }) : 1;
          // Emphasis detection: em-dashes, all-caps words, or numbers get special treatment
          const cleanWord = clean(w.word);
          const isEmphasis = /^\d{3,4}$/.test(cleanWord) || (cleanWord === cleanWord.toUpperCase() && cleanWord.length > 2);
          const emphasisScale = isEmphasis && isActive ? 1.15 : 1;
          // Frame-based color transition (3 frames ≈ 0.1s at 30fps)
          const transitionFrames = 3;
          const colorProgress = isActive
            ? interpolate(wordLocalFrame, [0, transitionFrames], [0, 1], {extrapolateLeft: 'clamp', extrapolateRight: 'clamp'})
            : (isPast ? 1 : 0);
          const inactiveColor = isPast ? 'rgba(240, 235, 225, 0.7)' : 'rgba(240, 235, 225, 0.95)';
          const activeColor = isEmphasis ? '#ffd700' : '#f0dca0';
          const wordColor = isActive
            ? interpolateColors(colorProgress, [0, 1], [inactiveColor, activeColor])
            : inactiveColor;

          // Caption style variants
          const baseFontSize = captionStyle === 'emphasis' ? 58 : captionStyle === 'whisper' ? 46 : 54;
          const emphFontSize = captionStyle === 'emphasis' ? 64 : captionStyle === 'whisper' ? 50 : 60;
          const baseWeight = captionStyle === 'emphasis' ? 700 : captionStyle === 'whisper' ? 500 : 600;
          const activeWeight = captionStyle === 'emphasis' ? 900 : captionStyle === 'whisper' ? 600 : 800;
          const styleOpacity = captionStyle === 'whisper' ? 0.7 : 1.0;
          const fontStyle = captionStyle === 'whisper' ? 'italic' as const : 'normal' as const;

          return (
            <span key={i} style={{
              color: wordColor,
              fontSize: isEmphasis && isActive ? emphFontSize : baseFontSize,
              fontFamily: '"Helvetica Neue", "Helvetica", Arial, sans-serif',
              fontWeight: isActive ? activeWeight : baseWeight,
              fontStyle,
              opacity: styleOpacity,
              letterSpacing: '0.02em',
              textShadow: isActive
                ? (captionStyle === 'emphasis'
                  ? '0 0 24px rgba(240, 220, 160, 0.6), 0 0 1px #000, 0 0 2px #000, 0 1px 3px rgba(0,0,0,0.9)'
                  : '0 0 20px rgba(240, 220, 160, 0.5), 0 0 1px #000, 0 0 2px #000, 0 1px 3px rgba(0,0,0,0.9)')
                : '0 0 1px #000, 0 0 2px #000, 0 1px 3px rgba(0,0,0,0.9)',
              // eslint-disable-next-line @typescript-eslint/no-explicit-any
              WebkitFontSmoothing: 'antialiased' as any,
              marginRight: i < activeGroup.words.length - 1 ? 16 : 0,
              display: 'inline-block',
              transform: `scale(${wordScale * emphasisScale})`,
            }}>
              {clean(w.word)}
            </span>
          );
        })}
      </div>
    </div>
  );
};
