import {useCurrentFrame, interpolate, Easing, Img, staticFile} from 'remotion';

type VisualTreatment = 'standard' | 'close_portrait' | 'wide_establishing' | 'artifact_detail' | 'map_overhead' | 'text_overlay_dark';

interface Props {
  imageSrc: string;
  duration: number;
  seed?: number;
  treatment?: VisualTreatment;
}

export const KenBurns: React.FC<Props> = ({imageSrc, duration, seed = 0, treatment = 'standard'}) => {
  const frame = useCurrentFrame();
  const progress = Math.min(frame / duration, 1);
  // Ease-in-out for organic feel
  const eased = Easing.inOut(Easing.quad)(progress);
  const pattern = seed % 16;

  const configs = [
    // Zoom-in variants — dramatic
    {scale:[1.0,1.22], x:[0,-4],  y:[0,-2]},    // 0: zoom-in, drift left
    {scale:[1.0,1.22], x:[0, 4],  y:[0,-2]},    // 1: zoom-in, drift right
    {scale:[1.0,1.20], x:[0, 0],  y:[0,-5]},    // 2: zoom-in, pan up
    {scale:[1.0,1.20], x:[0, 0],  y:[0, 5]},    // 3: zoom-in, pan down
    // Zoom-out variants — revealing
    {scale:[1.22,1.0], x:[-3,0],  y:[-2,0]},    // 4: zoom-out, drift right
    {scale:[1.22,1.0], x:[ 3,0],  y:[-2,0]},    // 5: zoom-out, drift left
    {scale:[1.20,1.0], x:[0, 0],  y:[-5,0]},    // 6: zoom-out, pan down
    {scale:[1.20,1.0], x:[0, 0],  y:[ 5,0]},    // 7: zoom-out, pan up
    // Diagonal drifts — cinematic
    {scale:[1.06,1.20],x:[-3, 3], y:[-3, 1]},   // 8: diagonal drift NW→SE
    {scale:[1.06,1.20],x:[ 3,-3], y:[ 3,-1]},   // 9: diagonal drift SE→NW
    {scale:[1.20,1.06],x:[-3, 3], y:[ 1,-3]},   // 10: reverse diagonal
    {scale:[1.20,1.06],x:[ 3,-3], y:[-1, 3]},   // 11: reverse diagonal 2
    // Slow pan across (good for landscapes/wide shots)
    {scale:[1.10,1.10],x:[-5, 5], y:[0, 0]},    // 12: horizontal pan L→R
    {scale:[1.10,1.10],x:[ 5,-5], y:[0, 0]},    // 13: horizontal pan R→L
    // Slow breathe — intimate
    {scale:[1.0,1.12], x:[-1, 1], y:[ 1,-1]},   // 14: gentle rotation feel
    {scale:[1.12,1.0], x:[ 1,-1], y:[-1, 1]},   // 15: reverse breathe
  ];

  // Treatment-specific motion overrides
  const treatmentOverrides: Partial<Record<VisualTreatment, {scale:[number,number], x:[number,number], y:[number,number]}>> = {
    close_portrait: {scale:[1.0, 1.08], x:[0, 0], y:[0, -1]},    // Very slow zoom into face
    wide_establishing: {scale:[1.22, 1.0], x:[0, 0], y:[0, 0]},  // Slow zoom out to reveal
    artifact_detail: {scale:[1.15, 1.0], x:[-2, 2], y:[0, 0]},   // Slow pan across object
    map_overhead: {scale:[1.12, 1.0], x:[0, 0], y:[3, -3]},      // Drift downward over map
  };

  const c = treatmentOverrides[treatment] || configs[pattern];
  const scale = interpolate(eased, [0,1], c.scale, {extrapolateRight: 'clamp'});
  const x     = interpolate(eased, [0,1], c.x, {extrapolateRight: 'clamp'});
  const y     = interpolate(eased, [0,1], c.y, {extrapolateRight: 'clamp'});

  // Treatment-specific object position — close_portrait centers on upper face
  const objectPosition = treatment === 'close_portrait' ? 'center 25%'
    : treatment === 'artifact_detail' ? 'center center'
    : treatment === 'map_overhead' ? 'center center'
    : 'center center';

  return (
    <div style={{position:'absolute',top:0,left:0,right:0,bottom:0,overflow:'hidden'}}>
      <Img src={staticFile(imageSrc)} style={{
        width:'100%', height:'100%', objectFit:'cover',
        objectPosition,
        transform:`scale(${scale}) translate(${x}%, ${y}%)`,
        transformOrigin:'center center',
        willChange: 'transform',
        imageRendering: 'auto',
      }}/>
      <div style={{
        position:'absolute', top:0, left:0, right:0, bottom:0,
        background:'radial-gradient(ellipse at center, rgba(0,0,0,0.05) 0%, rgba(0,0,0,0.35) 100%)',
      }}/>
    </div>
  );
};
