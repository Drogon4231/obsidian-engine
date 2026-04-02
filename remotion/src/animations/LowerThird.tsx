import {useCurrentFrame, useVideoConfig, interpolate, spring} from 'remotion';

interface Props {
  name: string;
  title: string;
  duration: number;
}

export const LowerThird: React.FC<Props> = ({name, title, duration}) => {
  const frame = useCurrentFrame();
  const {fps} = useVideoConfig();

  // Gold accent line slides in from left
  const lineWidth = interpolate(frame, [fps * 0.15, fps * 0.5], [0, 200],
    {extrapolateLeft: 'clamp', extrapolateRight: 'clamp'});

  // Vertical accent bar
  const barHeight = interpolate(frame, [fps * 0.1, fps * 0.4], [0, 56],
    {extrapolateLeft: 'clamp', extrapolateRight: 'clamp'});

  // Name slides in with spring — lower stiffness for smoother, more cinematic entrance
  const nameSpring = spring({frame: Math.max(0, frame - Math.floor(fps * 0.25)), fps,
    config: {damping: 16, stiffness: 80, mass: 0.7}});
  const nameSlide = interpolate(nameSpring, [0, 1], [-50, 0]);
  const nameScale = interpolate(nameSpring, [0, 1], [0.96, 1.0]);

  // Title slides in delayed
  const titleSpring = spring({frame: Math.max(0, frame - Math.floor(fps * 0.4)), fps,
    config: {damping: 16, stiffness: 80, mass: 0.7}});
  const titleSlide = interpolate(titleSpring, [0, 1], [-30, 0]);

  // Fade out near end of duration (last 0.5s), with fallback to 4s hold
  const exitStart = duration > 0 ? duration - Math.floor(fps * 0.5) : fps * 4;
  const exitEnd = duration > 0 ? duration : Math.floor(fps * 4.5);
  const slideOut = interpolate(frame, [exitStart, exitEnd], [0, -100],
    {extrapolateLeft: 'clamp', extrapolateRight: 'clamp'});
  const fadeOut = interpolate(frame, [exitStart, exitEnd], [1, 0],
    {extrapolateLeft: 'clamp', extrapolateRight: 'clamp'});

  if (fadeOut < 0.01) return null;

  return (
    <div style={{
      position: 'absolute', top: '58%', left: 60,
      opacity: fadeOut,
      transform: `translateX(${slideOut}px)`,
      zIndex: 60,
      pointerEvents: 'none',
      display: 'flex',
      alignItems: 'stretch',
      gap: 16,
    }}>
      {/* Dark backdrop with subtle border */}
      <div style={{
        position: 'absolute', top: -14, left: -20, right: -28, bottom: -14,
        background: 'linear-gradient(135deg, rgba(0,0,0,0.72) 0%, rgba(10,8,14,0.65) 100%)',
        borderRadius: 3,
        borderLeft: '3px solid rgba(180,140,80,0.6)',
        backdropFilter: 'blur(4px)',
      }}/>

      {/* Vertical gold accent bar */}
      <div style={{
        width: 3, height: barHeight,
        background: 'linear-gradient(180deg, #c8973a, rgba(180,140,80,0.3))',
        position: 'relative',
        borderRadius: 2,
        alignSelf: 'center',
      }}/>

      <div style={{position: 'relative'}}>
        {/* Horizontal gold line above name */}
        <div style={{
          width: lineWidth, height: 1.5,
          background: 'linear-gradient(90deg, #b48c50, rgba(180,140,80,0.15))',
          marginBottom: 10,
        }}/>

        {/* Name — larger, bolder */}
        <div style={{
          color: '#f0e8d8',
          fontFamily: '"Helvetica Neue", Helvetica, Arial, sans-serif',
          fontSize: 34,
          fontWeight: 800,
          letterSpacing: '0.04em',
          textTransform: 'uppercase',
          textShadow: '0 2px 10px rgba(0,0,0,0.95), 0 0 30px rgba(0,0,0,0.5)',
          transform: `translateX(${nameSlide}px) scale(${nameScale})`,
          opacity: nameSpring,
        }}>
          {name}
        </div>

        {/* Title/role — gold, italic */}
        <div style={{
          color: 'rgba(200,151,58,0.95)',
          fontFamily: 'Georgia,serif',
          fontSize: 17,
          fontStyle: 'italic',
          letterSpacing: '0.10em',
          marginTop: 5,
          textShadow: '0 1px 8px rgba(0,0,0,0.8)',
          transform: `translateX(${titleSlide}px)`,
          opacity: titleSpring,
        }}>
          {title}
        </div>

        {/* Bottom accent line */}
        <div style={{
          width: lineWidth * 0.6, height: 1,
          background: 'linear-gradient(90deg, rgba(180,140,80,0.4), transparent)',
          marginTop: 10,
        }}/>
      </div>
    </div>
  );
};
