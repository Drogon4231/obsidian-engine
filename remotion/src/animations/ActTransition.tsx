import {useCurrentFrame, useVideoConfig, interpolate} from 'remotion';

/**
 * Brief visual pulse at the start of scenes marked as reveal moments.
 * Creates a dramatic "beat" — quick warm flash.
 */
export const TwistReveal: React.FC = () => {
  const frame = useCurrentFrame();
  const {fps} = useVideoConfig();

  // Quick 0.6s flash that fades
  const flashOpacity = interpolate(frame, [0, fps*0.08, fps*0.6], [0.7, 0.4, 0],
    {extrapolateLeft:'clamp', extrapolateRight:'clamp'});

  if (frame > fps * 0.7) return null;

  return (
    <div style={{
      position:'absolute', top:0, left:0, right:0, bottom:0,
      background:`radial-gradient(ellipse at 50% 50%, rgba(180,140,80,${flashOpacity * 0.5}) 0%, rgba(0,0,0,${flashOpacity}) 70%)`,
      zIndex: 50,
      pointerEvents: 'none',
    }}/>
  );
};

/**
 * Scene boundary transition — varies by narrative beat.
 * - 'act': Slower 0.8s fade with deeper black (act transitions = breathing room)
 * - 'normal': Softer 0.4s crossfade at 35% black (subtle scene change)
 */
export const SceneDip: React.FC<{
  duration: number;
  intensity?: 'normal' | 'act';
  transitionDurationSec?: number;
}> = ({duration, intensity = 'normal', transitionDurationSec}) => {
  const frame = useCurrentFrame();
  const {fps} = useVideoConfig();

  const isAct = intensity === 'act';
  // Use explicit duration if provided, otherwise fall back to intensity-based defaults
  const dipDuration = transitionDurationSec ?? (isAct ? 0.8 : 0.4);
  const peakOpacity = dipDuration >= 1.0 ? 0.85 : (isAct ? 0.7 : 0.35);
  const dipFrames = Math.floor(fps * dipDuration);

  const fadeIn = interpolate(frame, [0, dipFrames], [peakOpacity, 0],
    {extrapolateLeft:'clamp', extrapolateRight:'clamp'});
  const fadeOut = interpolate(frame, [duration - dipFrames, duration], [0, peakOpacity],
    {extrapolateLeft:'clamp', extrapolateRight:'clamp'});

  // Act transitions: hold full black briefly in the middle for a breath beat
  const holdOpacity = isAct
    ? interpolate(frame, [dipFrames, dipFrames + Math.floor(fps * 0.15)], [0, 0],
        {extrapolateLeft:'clamp', extrapolateRight:'clamp'})
    : 0;

  const opacity = Math.max(fadeIn, fadeOut, holdOpacity);

  if (opacity < 0.01) return null;

  return (
    <div style={{
      position:'absolute', top:0, left:0, right:0, bottom:0,
      backgroundColor: `rgba(0,0,0,${opacity})`,
      zIndex: 40,
      pointerEvents: 'none',
    }}/>
  );
};
