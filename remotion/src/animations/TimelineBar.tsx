import {useCurrentFrame, useVideoConfig, interpolate} from 'remotion';

interface Props {
  currentYear: string;
  eraStart: string;
  eraEnd: string;
  duration: number;
}

export const TimelineBar: React.FC<Props> = ({currentYear, eraStart, eraEnd, duration}) => {
  const frame = useCurrentFrame();
  const {fps} = useVideoConfig();

  // Progress across the scene duration
  const progress = interpolate(frame, [0, duration], [0, 1],
    {extrapolateLeft: 'clamp', extrapolateRight: 'clamp'});

  // Fade in/out
  const fadeIn = interpolate(frame, [0, fps * 0.5], [0, 1],
    {extrapolateLeft: 'clamp', extrapolateRight: 'clamp'});
  const fadeOut = interpolate(frame, [duration - fps * 0.5, duration], [1, 0],
    {extrapolateLeft: 'clamp', extrapolateRight: 'clamp'});
  const opacity = fadeIn * fadeOut;

  if (opacity < 0.01) return null;

  const barWidth = 82; // percent of screen width
  const barLeft = 9;   // percent offset

  return (
    <div style={{
      position: 'absolute', top: 95, left: 0, right: 0,
      opacity,
      zIndex: 60,
      pointerEvents: 'none',
    }}>
      {/* Era start label */}
      <div style={{
        position: 'absolute', top: -18, left: `${barLeft}%`,
        color: 'rgba(180,140,80,0.5)', fontFamily: 'Georgia,serif',
        fontSize: 11, letterSpacing: '0.1em',
      }}>
        {eraStart}
      </div>

      {/* Era end label */}
      <div style={{
        position: 'absolute', top: -18, left: `${barLeft + barWidth}%`,
        transform: 'translateX(-100%)',
        color: 'rgba(180,140,80,0.5)', fontFamily: 'Georgia,serif',
        fontSize: 11, letterSpacing: '0.1em',
      }}>
        {eraEnd}
      </div>

      {/* Background track */}
      <div style={{
        position: 'absolute', top: 0,
        left: `${barLeft}%`, width: `${barWidth}%`,
        height: 2, background: 'rgba(180,140,80,0.2)',
        borderRadius: 1,
      }}/>

      {/* Filled progress */}
      <div style={{
        position: 'absolute', top: 0,
        left: `${barLeft}%`, width: `${barWidth * progress}%`,
        height: 2,
        background: 'linear-gradient(90deg, rgba(180,140,80,0.4), rgba(180,140,80,0.9))',
        borderRadius: 1,
      }}/>

      {/* Progress point with glow */}
      <div style={{
        position: 'absolute', top: -3,
        left: `${barLeft + barWidth * progress}%`,
        transform: 'translateX(-4px)',
        width: 8, height: 8, borderRadius: '50%',
        background: '#d4a855',
        boxShadow: '0 0 8px rgba(180,140,80,0.7), 0 0 16px rgba(180,140,80,0.3)',
      }}/>

      {/* Current year label above progress point */}
      <div style={{
        position: 'absolute', top: -22,
        left: `${barLeft + barWidth * progress}%`,
        transform: 'translateX(-50%)',
        color: '#d4a855', fontFamily: 'Georgia,serif',
        fontSize: 13, fontWeight: 'bold',
        letterSpacing: '0.1em',
        textShadow: '0 1px 6px rgba(0,0,0,0.8)',
      }}>
        {currentYear}
      </div>
    </div>
  );
};
