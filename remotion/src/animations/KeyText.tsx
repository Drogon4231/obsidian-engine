import {useCurrentFrame, useVideoConfig, interpolate, spring} from 'remotion';

interface Props {
  text: string;
  emphasis?: 'date' | 'claim' | 'name';
  duration: number;
}

export const KeyText: React.FC<Props> = ({text, emphasis = 'claim', duration}) => {
  const frame = useCurrentFrame();
  const {fps} = useVideoConfig();

  // Spring entrance
  const entranceSpring = spring({frame, fps,
    config: {damping: 14, stiffness: 90, mass: 1}});
  const entranceScale = interpolate(entranceSpring, [0, 1], [0.92, 1]);

  // Typewriter reveal: characters appear over ~1.2s
  const revealDuration = fps * 1.2;
  const charsVisible = Math.floor(interpolate(frame, [fps * 0.2, fps * 0.2 + revealDuration], [0, text.length],
    {extrapolateLeft: 'clamp', extrapolateRight: 'clamp'}));

  // Underline animation for 'claim' emphasis
  const underlineWidth = interpolate(frame, [fps * 0.8, fps * 1.5], [0, 100],
    {extrapolateLeft: 'clamp', extrapolateRight: 'clamp'});

  // Decorative line animation for 'date' emphasis
  const lineWidth = interpolate(frame, [fps * 0.6, fps * 1.2], [0, 60],
    {extrapolateLeft: 'clamp', extrapolateRight: 'clamp'});

  // Fade out at end
  const fadeOut = interpolate(frame, [duration - fps * 0.6, duration], [1, 0],
    {extrapolateLeft: 'clamp', extrapolateRight: 'clamp'});

  if (fadeOut < 0.01) return null;

  // Per-emphasis styling
  const textStyles: React.CSSProperties = {
    fontFamily: 'Georgia,serif',
    textAlign: 'center' as const,
    position: 'relative' as const,
  };

  if (emphasis === 'date') {
    Object.assign(textStyles, {
      color: '#d4a855',
      fontSize: 42,
      fontWeight: 'bold',
      letterSpacing: '0.12em',
      textShadow: '0 2px 12px rgba(180,140,80,0.4), 0 1px 4px rgba(0,0,0,0.8)',
    });
  } else if (emphasis === 'claim') {
    Object.assign(textStyles, {
      color: '#f0e8d8',
      fontSize: 32,
      fontWeight: 'normal',
      letterSpacing: '0.04em',
      textShadow: '0 2px 10px rgba(0,0,0,0.9)',
    });
  } else {
    // name
    Object.assign(textStyles, {
      color: '#f0e8d8',
      fontSize: 36,
      fontStyle: 'italic',
      fontWeight: 'normal',
      letterSpacing: '0.06em',
      textShadow: '0 0 14px rgba(180,140,80,0.25), 0 2px 8px rgba(0,0,0,0.8)',
    });
  }

  const visibleText = text.slice(0, charsVisible);
  const hiddenText = text.slice(charsVisible);

  return (
    <div style={{
      position: 'absolute', top: 0, left: 0, right: 0, bottom: 0,
      display: 'flex', alignItems: 'center', justifyContent: 'center',
      opacity: fadeOut,
      zIndex: 60,
      pointerEvents: 'none',
    }}>
      <div style={{
        transform: `scale(${entranceScale})`,
        display: 'flex', flexDirection: 'column', alignItems: 'center',
      }}>
        {/* Backdrop blur */}
        <div style={{
          position: 'absolute', top: -20, left: -40, right: -40, bottom: -20,
          background: 'rgba(0,0,0,0.45)',
          borderRadius: 6,
          filter: 'blur(8px)',
        }}/>

        {/* Date emphasis: decorative lines flanking text */}
        {emphasis === 'date' && (
          <div style={{
            display: 'flex', alignItems: 'center', gap: 20,
            position: 'relative',
          }}>
            <div style={{
              width: lineWidth, height: 1,
              background: 'linear-gradient(90deg, transparent, rgba(180,140,80,0.7))',
            }}/>
            <div style={textStyles}>
              <span>{visibleText}</span>
              <span style={{visibility: 'hidden'}}>{hiddenText}</span>
            </div>
            <div style={{
              width: lineWidth, height: 1,
              background: 'linear-gradient(270deg, transparent, rgba(180,140,80,0.7))',
            }}/>
          </div>
        )}

        {/* Claim emphasis: text with gold underline */}
        {emphasis === 'claim' && (
          <div style={{position: 'relative'}}>
            <div style={textStyles}>
              <span>{visibleText}</span>
              <span style={{visibility: 'hidden'}}>{hiddenText}</span>
            </div>
            <div style={{
              width: `${underlineWidth}%`, height: 2, marginTop: 8,
              background: 'linear-gradient(90deg, rgba(180,140,80,0.8), rgba(180,140,80,0.2))',
              margin: '8px auto 0',
            }}/>
          </div>
        )}

        {/* Name emphasis: text with subtle glow */}
        {emphasis === 'name' && (
          <div style={{position: 'relative'}}>
            <div style={textStyles}>
              <span>{visibleText}</span>
              <span style={{visibility: 'hidden'}}>{hiddenText}</span>
            </div>
          </div>
        )}
      </div>
    </div>
  );
};
