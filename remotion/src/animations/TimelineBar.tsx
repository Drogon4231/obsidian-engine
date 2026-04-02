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

  // Pill background style shared by era labels
  const pillStyle: React.CSSProperties = {
    display: 'inline-block',
    background: 'rgba(0,0,0,0.65)',
    borderRadius: 4,
    padding: '2px 8px',
  };

  // Layout: outer div at top:100 (below 70px letterbox).
  // Inner container is positioned normally (not absolute with negative offsets)
  // so all children stay visible and outside the letterbox zone.
  return (
    <div style={{
      position: 'absolute', top: 100, left: `${barLeft - 1}%`, width: `${barWidth + 2}%`,
      opacity,
      zIndex: 60,
      pointerEvents: 'none',
    }}>
      {/* Current year label — above the bar container */}
      <div style={{
        position: 'relative',
        marginBottom: 8,
        left: `${barWidth * progress / (barWidth + 2) * 100}%`,
        transform: 'translateX(-50%)',
        display: 'inline-block',
        fontFamily: 'Georgia,serif',
        fontSize: 32, fontWeight: 'bold',
        letterSpacing: '0.08em',
        whiteSpace: 'nowrap',
      }}>
        <span style={{
          ...pillStyle,
          color: '#d4a855',
          textShadow: '0 2px 8px rgba(0,0,0,0.95), 0 0 20px rgba(0,0,0,0.7)',
        }}>
          {currentYear}
        </span>
      </div>

      {/* Bar container with background */}
      <div style={{
        position: 'relative',
        backgroundColor: 'rgba(0,0,0,0.7)',
        padding: '16px 8px',
        borderRadius: 6,
        border: '2px solid rgba(212,168,85,0.8)',
      }}>
        {/* Background track */}
        <div style={{
          width: '100%',
          height: 8, background: 'rgba(180,140,80,0.25)',
          borderRadius: 4,
          position: 'relative',
        }}>
          {/* Filled progress */}
          <div style={{
            position: 'absolute', top: 0, left: 0,
            width: `${progress * 100}%`,
            height: 8,
            background: 'linear-gradient(90deg, rgba(180,140,80,0.4), rgba(180,140,80,0.95))',
            borderRadius: 4,
          }}/>
          {/* Progress point with glow */}
          <div style={{
            position: 'absolute', top: -4,
            left: `${progress * 100}%`,
            transform: 'translateX(-8px)',
            width: 16, height: 16, borderRadius: '50%',
            background: '#d4a855',
            boxShadow: '0 0 10px rgba(180,140,80,0.8), 0 0 20px rgba(180,140,80,0.4)',
          }}/>
        </div>
      </div>

      {/* Era labels — below the bar */}
      {(eraStart || eraEnd) && (
        <div style={{
          display: 'flex',
          justifyContent: 'space-between',
          marginTop: 6,
          padding: '0 8px',
        }}>
          {eraStart ? (
            <span style={{
              ...pillStyle,
              fontFamily: 'Georgia,serif',
              fontSize: 28, letterSpacing: '0.08em',
              color: 'rgba(212,168,85,0.9)',
              textShadow: '0 2px 8px rgba(0,0,0,0.95), 0 0 20px rgba(0,0,0,0.7)',
            }}>
              {eraStart}
            </span>
          ) : <span/>}
          {eraEnd ? (
            <span style={{
              ...pillStyle,
              fontFamily: 'Georgia,serif',
              fontSize: 28, letterSpacing: '0.08em',
              color: 'rgba(212,168,85,0.9)',
              textShadow: '0 2px 8px rgba(0,0,0,0.95), 0 0 20px rgba(0,0,0,0.7)',
            }}>
              {eraEnd}
            </span>
          ) : <span/>}
        </div>
      )}
    </div>
  );
};
