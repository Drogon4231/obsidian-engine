import {useCurrentFrame, useVideoConfig, interpolate, Sequence} from 'remotion';
import {KenBurns} from './KenBurns';

interface Props {
  images: string[];
  duration: number;
  seed?: number;
  treatment?: 'standard' | 'close_portrait' | 'wide_establishing' | 'artifact_detail' | 'map_overhead' | 'text_overlay_dark';
}

/**
 * MultiImageKenBurns — crossfades between 2-3 images within a single scene.
 * Each image gets its own Ken Burns motion, and they blend at transitions.
 * Falls back to single KenBurns if only 1 image provided.
 */
export const MultiImageKenBurns: React.FC<Props> = ({images, duration, seed = 0, treatment = 'standard'}) => {
  const frame = useCurrentFrame();
  const {fps} = useVideoConfig();

  if (!images.length) return null;
  if (images.length === 1) {
    return <KenBurns imageSrc={images[0]} duration={duration} seed={seed} treatment={treatment}/>;
  }

  const n = images.length;
  const segmentFrames = Math.floor(duration / n);
  // Crossfade window: 15% of segment duration (smooth blend)
  const crossfadeFrames = Math.max(Math.floor(segmentFrames * 0.15), Math.floor(fps * 0.4));

  return (
    <div style={{position:'absolute', top:0, left:0, right:0, bottom:0, overflow:'hidden'}}>
      {images.map((img, i) => {
        const segStart = i * segmentFrames;
        const segEnd = (i + 1) * segmentFrames;

        // Opacity: fade in at start, full during middle, fade out at end
        const fadeIn = i === 0 ? 1 : interpolate(
          frame, [segStart - crossfadeFrames, segStart + crossfadeFrames], [0, 1],
          {extrapolateLeft: 'clamp', extrapolateRight: 'clamp'},
        );
        const fadeOut = i === n - 1 ? 1 : interpolate(
          frame, [segEnd - crossfadeFrames, segEnd + crossfadeFrames], [1, 0],
          {extrapolateLeft: 'clamp', extrapolateRight: 'clamp'},
        );
        const opacity = Math.min(fadeIn, fadeOut);

        // Skip rendering images that are fully transparent
        if (opacity <= 0) return null;

        // Each image gets a unique seed for different Ken Burns motion
        const imgSeed = seed + i * 3;

        // Wrap each image in a Sequence so KenBurns' useCurrentFrame()
        // resets to 0 at each image's start, giving correct motion speed
        return (
          <div key={i} style={{position:'absolute', top:0, left:0, right:0, bottom:0, opacity}}>
            <Sequence from={segStart} durationInFrames={segmentFrames}>
              <KenBurns imageSrc={img} duration={segmentFrames} seed={imgSeed} treatment={treatment}/>
            </Sequence>
          </div>
        );
      })}
    </div>
  );
};
