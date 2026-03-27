import {
  AbsoluteFill, Audio, Sequence, Img,
  useCurrentFrame, useVideoConfig, interpolate, staticFile,
} from 'remotion';
import {ShortCaptions} from './ShortCaptions';
import {buildNarrationMask, distanceToSpeech} from './audio-utils';
import shortVideoData from './short-video-data.json';

interface WordTimestamp {word: string; start: number; end: number;}

interface ShortScene {
  narration_segment: string;
  start_time: number;
  end_time: number;
  mood: string;
  ai_image?: string;
}

interface ShortAudioConfig {
  ducking?: { speechVolume?: number; silenceVolume?: number; rampSeconds?: number };
}
interface ShortVideoData {
  scenes: ShortScene[];
  word_timestamps: WordTimestamp[];
  total_duration_seconds: number;
  music_file?: string | null;
  audio_config?: ShortAudioConfig;
}

const MOOD_BG: Record<string, string> = {
  dark:     '#08080e',
  tense:    '#0e0808',
  dramatic: '#080e08',
  cold:     '#08080e',
  reverent: '#0e0e08',
  wonder:   '#08081a',
  warmth:   '#0e0a08',
  absurdity:'#0e0c08',
};

const CHANNEL_NAME = 'THE OBSIDIAN ARCHIVE';

// ── Per-scene component ────────────────────────────────────────────────────────
const ShortSceneContent: React.FC<{
  scene: ShortScene;
  duration: number;
  words: WordTimestamp[];
  sceneIndex: number;
}> = ({scene, duration, words, sceneIndex}) => {
  const frame = useCurrentFrame();
  const {fps}  = useVideoConfig();

  // Fade in / fade out — slightly longer for smoother transitions
  const fadeFrames = Math.floor(fps * 0.25);
  const fadeIn  = interpolate(frame, [0, fadeFrames],              [0, 1], {extrapolateLeft: 'clamp', extrapolateRight: 'clamp'});
  const fadeOut = interpolate(frame, [duration - fadeFrames, duration], [1, 0], {extrapolateLeft: 'clamp', extrapolateRight: 'clamp'});
  const opacity = Math.min(fadeIn, fadeOut);

  // Varied Ken Burns per scene — more dynamic than single zoom-out
  const zoomProgress = interpolate(frame, [0, duration], [0, 1], {extrapolateLeft: 'clamp', extrapolateRight: 'clamp'});
  const motionPattern = sceneIndex % 6;
  const shortMotions = [
    {scale:[1.12, 1.0],  x:[0, 0],    y:[0, 0],   origin:'center 25%'},   // 0: zoom out (reveal)
    {scale:[1.0, 1.12],  x:[0, 0],    y:[0, -2],  origin:'center 30%'},   // 1: zoom in + drift up
    {scale:[1.08, 1.08], x:[-3, 3],   y:[0, 0],   origin:'center 25%'},   // 2: horizontal pan
    {scale:[1.0, 1.14],  x:[0, 2],    y:[0, -1],  origin:'center 20%'},   // 3: zoom in + drift right
    {scale:[1.14, 1.0],  x:[2, -2],   y:[-1, 1],  origin:'center 30%'},   // 4: zoom out + diagonal
    {scale:[1.06, 1.10], x:[-2, 2],   y:[-2, 0],  origin:'center 25%'},   // 5: slow diagonal drift
  ];
  const motion = shortMotions[motionPattern];
  const imgScale = interpolate(zoomProgress, [0, 1], motion.scale);
  const imgX     = interpolate(zoomProgress, [0, 1], motion.x);
  const imgY     = interpolate(zoomProgress, [0, 1], motion.y);

  const bg = MOOD_BG[scene.mood] ?? MOOD_BG.dark;

  return (
    <AbsoluteFill style={{opacity, backgroundColor: bg}}>
      {/* Background: full-bleed portrait AI image */}
      {scene.ai_image && (
        <AbsoluteFill style={{overflow: 'hidden'}}>
          <Img
            src={staticFile(scene.ai_image)}
            style={{
              width:           '100%',
              height:          '100%',
              objectFit:       'cover',
              objectPosition:  'center 20%',
              transform:       `scale(${imgScale}) translate(${imgX}%, ${imgY}%)`,
              transformOrigin: motion.origin,
              willChange:      'transform',
            }}
          />
        </AbsoluteFill>
      )}

      {/* Gradient overlay — darkens top brand strip + bottom caption zone */}
      <AbsoluteFill
        style={{
          background: [
            'linear-gradient(180deg,',
            '  rgba(0,0,0,0.72) 0%,',
            '  rgba(0,0,0,0.20) 18%,',
            '  rgba(0,0,0,0.00) 38%,',
            '  rgba(0,0,0,0.00) 48%,',
            '  rgba(0,0,0,0.60) 65%,',
            '  rgba(0,0,0,0.88) 80%,',
            '  rgba(0,0,0,0.96) 100%)',
          ].join('\n'),
        }}
      />

      {/* ── Channel watermark — top ── */}
      <div
        style={{
          position:       'absolute',
          top:            72,
          left:           0,
          right:          0,
          display:        'flex',
          justifyContent: 'center',
          alignItems:     'center',
          gap:            12,
        }}
      >
        <div style={{width: 28, height: 1.5, background: '#c8973a', borderRadius: 1}}/>
        <span
          style={{
            color:          'rgba(255,255,255,0.72)',
            fontSize:       22,
            fontFamily:     '"Helvetica Neue", Helvetica, Arial, sans-serif',
            fontWeight:     700,
            letterSpacing:  '4px',
            textTransform:  'uppercase',
            textShadow:     '0 2px 10px rgba(0,0,0,0.9)',
          }}
        >
          {CHANNEL_NAME}
        </span>
        <div style={{width: 28, height: 1.5, background: '#c8973a', borderRadius: 1}}/>
      </div>

      {/* ── Word-by-word captions ── */}
      <ShortCaptions words={words} sceneStartTime={scene.start_time} />
    </AbsoluteFill>
  );
};

// ── Root Short composition ─────────────────────────────────────────────────────
export const ShortVideo: React.FC = () => {
  const {fps} = useVideoConfig();
  const data  = shortVideoData as ShortVideoData;
  const words: WordTimestamp[] = data.word_timestamps ?? [];
  const narrationMask = buildNarrationMask(words);
  const audioConfig = data.audio_config ?? {};
  const speechVol = audioConfig.ducking?.speechVolume ?? 0.12;
  const silenceVol = audioConfig.ducking?.silenceVolume ?? 0.25;

  return (
    <AbsoluteFill style={{backgroundColor: '#08080e'}}>
      <Audio src={staticFile('short_narration.mp3')} />
      {data.music_file && (
        <Audio src={staticFile(data.music_file)} volume={(f) => {
          const time = f / fps;
          const isSpeaking = distanceToSpeech(time, narrationMask) === 0;
          return isSpeaking ? speechVol : silenceVol;
        }} loop />
      )}

      {data.scenes.map((scene, i) => {
        const startFrame = Math.floor(scene.start_time * fps);
        const endFrame   = Math.ceil(scene.end_time   * fps);
        const duration   = endFrame - startFrame;
        if (duration <= 0) return null;

        return (
          <Sequence key={i} from={startFrame} durationInFrames={duration}>
            <ShortSceneContent
              scene={scene}
              duration={duration}
              words={words}
              sceneIndex={i}
            />
          </Sequence>
        );
      })}
    </AbsoluteFill>
  );
};
