import {useCurrentFrame, useVideoConfig, spring} from 'remotion';

interface Word {
  word: string;
  start: number;
  end: number;
}

interface ShortCaptionsProps {
  words: Word[];
  sceneStartTime: number;
}

const PHRASE_SIZE = 4;

const clean = (w: string) => w.replace(/[^\p{L}\p{N} '''.,!?;\u2014-]/gu, '').toUpperCase().trim();

export const ShortCaptions: React.FC<ShortCaptionsProps> = ({words, sceneStartTime}) => {
  const frame = useCurrentFrame();
  const {fps} = useVideoConfig();
  const globalTime = sceneStartTime + frame / fps;

  // Find the currently spoken word index
  const currentWordIdx = words.findIndex(
    (w) => globalTime >= w.start && globalTime < w.end
  );

  // If between words, find the last spoken word to hold the phrase
  const displayIdx = currentWordIdx >= 0
    ? currentWordIdx
    : words.reduce((acc, w, i) => (globalTime > w.end ? i : acc), -1);

  if (displayIdx < 0) return null;

  const phraseStart = Math.floor(displayIdx / PHRASE_SIZE) * PHRASE_SIZE;
  const phraseEnd   = Math.min(phraseStart + PHRASE_SIZE, words.length);
  const phraseWords = words.slice(phraseStart, phraseEnd);

  // Phrase slide-in animation — triggers when this phrase becomes active
  const phraseStartTime = words[phraseStart]?.start ?? 0;
  const phraseActivationFrame = Math.max(0, Math.round((phraseStartTime - sceneStartTime) * fps));
  const frameIntoPhrase = Math.max(0, frame - phraseActivationFrame);

  const phraseTranslateY = spring({
    frame: frameIntoPhrase,
    fps,
    config: {damping: 22, stiffness: 200, mass: 0.6},
    from: 50,
    to: 0,
  });

  const phraseOpacity = Math.min(1, frameIntoPhrase / Math.max(1, fps * 0.08));

  return (
    <div
      style={{
        position: 'absolute',
        bottom: 160,
        left: 0,
        right: 0,
        padding: '0 48px',
        display: 'flex',
        flexWrap: 'wrap',
        justifyContent: 'center',
        alignItems: 'flex-end',
        gap: 6,
        transform: `translateY(${phraseTranslateY}px)`,
        opacity: phraseOpacity,
      }}
    >
      {phraseWords.map((w, i) => {
        const globalIdx   = phraseStart + i;
        const isCurrent   = globalIdx === currentWordIdx;
        const isPast      = globalIdx < currentWordIdx || (currentWordIdx < 0 && globalIdx < displayIdx);

        // Spring scale pops the current word when it first becomes active
        const wordActivationTime  = w.start - sceneStartTime;
        const wordActivationFrame = Math.max(0, Math.round(wordActivationTime * fps));
        const frameIntoWord       = Math.max(0, frame - wordActivationFrame);

        const wordScale = isCurrent
          ? spring({
              frame: frameIntoWord,
              fps,
              config: {damping: 8, stiffness: 400, mass: 0.3},
              from: 0.72,
              to: 1.0,
            })
          : 1.0;

        const wordColor = isCurrent
          ? '#FFD700'
          : isPast
          ? 'rgba(255,255,255,0.32)'
          : 'rgba(255,255,255,0.88)';

        const wordShadow = isCurrent
          ? '0 0 50px rgba(255,215,0,0.65), 0 0 20px rgba(255,215,0,0.3), 0 3px 12px rgba(0,0,0,1)'
          : '0 2px 12px rgba(0,0,0,0.95)';

        return (
          <span
            key={`${phraseStart}-${i}`}
            style={{
              fontSize: 78,
              fontWeight: 900,
              fontFamily: '"Helvetica Neue", Helvetica, Arial, sans-serif',
              color: wordColor,
              display: 'inline-block',
              transform: `scale(${wordScale})`,
              transformOrigin: 'center bottom',
              textShadow: wordShadow,
              letterSpacing: '-1.5px',
              textTransform: 'uppercase',
              lineHeight: 1.05,
              willChange: 'transform',
            }}
          >
            {clean(w.word)}
          </span>
        );
      })}
    </div>
  );
};
