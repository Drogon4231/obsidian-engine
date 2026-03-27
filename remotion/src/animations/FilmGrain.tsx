import {useCurrentFrame} from 'remotion';

/**
 * Subtle animated film grain overlay using SVG turbulence filter.
 * Adds perceived texture and hides the "CG" feel of AI-generated images.
 * CPU-only — no GPU required.
 */
interface FilmGrainProps {
  intensity?: number;        // 0.0-0.3, controls grain opacity (default 0.1)
  vignetteIntensity?: number; // 0.0-0.4, controls vignette darkness (default 0.15)
}

export const FilmGrain: React.FC<FilmGrainProps> = ({
  intensity = 0.1,
  vignetteIntensity = 0.15,
}) => {
  const frame = useCurrentFrame();
  // Shift the noise seed every 6 frames (~5Hz at 30fps) for subtle grain without excess CPU
  const seed = Math.floor(frame / 6);
  // Clamp values to safe ranges
  const grainOpacity = Math.max(0, Math.min(0.3, intensity)) * 0.45; // scale to visual range
  const vignetteAlpha = Math.max(0, Math.min(0.4, vignetteIntensity));

  if (grainOpacity <= 0 && vignetteAlpha <= 0) return null;

  return (
    <>
      {grainOpacity > 0 && (
      <div style={{
        position: 'absolute', top: 0, left: 0, right: 0, bottom: 0,
        pointerEvents: 'none',
        zIndex: 90,
        opacity: grainOpacity,
        mixBlendMode: 'overlay',
      }}>
        <svg width="100%" height="100%" xmlns="http://www.w3.org/2000/svg">
          <filter id="grain">
            <feTurbulence
              type="fractalNoise"
              baseFrequency="0.75"
              numOctaves="4"
              seed={seed}
              stitchTiles="stitch"
            />
            <feColorMatrix type="saturate" values="0" />
          </filter>
          <rect width="100%" height="100%" filter="url(#grain)" />
        </svg>
      </div>
      )}
      {vignetteAlpha > 0 && (
        <div style={{
          position: 'absolute', top: 0, left: 0, right: 0, bottom: 0,
          pointerEvents: 'none',
          zIndex: 91,
          background: `radial-gradient(ellipse at center, transparent 50%, rgba(0,0,0,${vignetteAlpha}) 100%)`,
        }} />
      )}
    </>
  );
};
