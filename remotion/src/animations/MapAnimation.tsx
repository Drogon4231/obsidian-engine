import {useCurrentFrame, useVideoConfig, interpolate, spring} from 'remotion';

interface Props {
  location: string;
  year: string;
  duration: number;
}

export const MapAnimation: React.FC<Props> = ({location, year, duration}) => {
  const frame = useCurrentFrame();
  const {fps} = useVideoConfig();

  // Pin drop spring animation (lands ~0.5s)
  const pinDrop = spring({frame, fps, config: {damping: 12, stiffness: 120, mass: 0.8}});
  const pinY = interpolate(pinDrop, [0, 1], [-40, 0]);
  const pinScale = interpolate(pinDrop, [0, 1], [0.3, 1]);

  // Location text fades in after pin lands (~0.6s)
  const textOpacity = interpolate(frame, [fps * 0.5, fps * 0.9], [0, 1],
    {extrapolateLeft: 'clamp', extrapolateRight: 'clamp'});
  const textSlide = interpolate(frame, [fps * 0.5, fps * 0.9], [12, 0],
    {extrapolateLeft: 'clamp', extrapolateRight: 'clamp'});

  // Year text fades in slightly after location
  const yearOpacity = interpolate(frame, [fps * 0.7, fps * 1.1], [0, 1],
    {extrapolateLeft: 'clamp', extrapolateRight: 'clamp'});

  // Fade out near end of duration (last 0.5s), with fallback to 3s hold
  const exitStart = duration > 0 ? duration - Math.floor(fps * 0.5) : fps * 3;
  const exitEnd = duration > 0 ? duration : Math.floor(fps * 3.5);
  const fadeOut = interpolate(frame, [exitStart, exitEnd], [1, 0],
    {extrapolateLeft: 'clamp', extrapolateRight: 'clamp'});

  // Overall fade in
  const fadeIn = interpolate(frame, [0, fps * 0.3], [0, 1],
    {extrapolateLeft: 'clamp', extrapolateRight: 'clamp'});

  const opacity = fadeIn * fadeOut;

  if (opacity < 0.01) return null;

  return (
    <div style={{
      position: 'absolute', bottom: 200, left: 40,
      width: 300, minHeight: 120, padding: '16px 20px',
      background: 'rgba(0,0,0,0.65)',
      borderLeft: '2px solid rgba(180,140,80,0.6)',
      borderRadius: 4,
      opacity,
      zIndex: 60,
      pointerEvents: 'none',
    }}>
      {/* Gold pin icon (CSS triangle + circle) */}
      <div style={{
        position: 'absolute', top: 16, left: 20,
        transform: `translateY(${pinY}px) scale(${pinScale})`,
        transformOrigin: 'bottom center',
      }}>
        <div style={{
          width: 16, height: 16, borderRadius: '50% 50% 50% 0',
          background: 'linear-gradient(135deg, #d4a855, #b48c50)',
          transform: 'rotate(-45deg)',
          boxShadow: '0 2px 8px rgba(180,140,80,0.5)',
        }}/>
        <div style={{
          width: 6, height: 6, borderRadius: '50%',
          background: '#1a1a1a',
          position: 'absolute', top: 5, left: 5,
        }}/>
      </div>

      {/* Location text */}
      <div style={{
        marginLeft: 30, marginTop: 0,
        opacity: textOpacity,
        transform: `translateX(${textSlide}px)`,
      }}>
        <div style={{
          color: '#f0e8d8',
          fontFamily: 'Georgia,serif',
          fontSize: 20,
          fontWeight: 'bold',
          letterSpacing: '0.05em',
          textShadow: '0 1px 6px rgba(0,0,0,0.8)',
        }}>
          {location}
        </div>
        <div style={{
          color: 'rgba(180,140,80,0.9)',
          fontFamily: 'Georgia,serif',
          fontSize: 14,
          marginTop: 4,
          letterSpacing: '0.15em',
          opacity: yearOpacity,
          textShadow: '0 1px 4px rgba(0,0,0,0.6)',
        }}>
          {year}
        </div>
      </div>
    </div>
  );
};
