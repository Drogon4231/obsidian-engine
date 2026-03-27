import {useCurrentFrame, useVideoConfig, interpolate} from 'remotion';

const toRoman = (n: number): string => {
  const vals = [10,9,5,4,1];
  const syms = ['X','IX','V','IV','I'];
  let result = '';
  for (let i = 0; i < vals.length; i++) {
    while (n >= vals[i]) { result += syms[i]; n -= vals[i]; }
  }
  return result;
};

export const ChapterMarker: React.FC<{chapter: number; total: number}> = ({chapter, total}) => {
  const frame = useCurrentFrame();
  const {fps} = useVideoConfig();

  const opacity = interpolate(frame, [fps*0.3,fps*0.8,fps*5,fps*6], [0,0.8,0.8,0],
    {extrapolateLeft:'clamp', extrapolateRight:'clamp'});

  const slideIn = interpolate(frame, [fps*0.3,fps*0.8], [20,0],
    {extrapolateLeft:'clamp', extrapolateRight:'clamp'});

  const lineWidth = interpolate(frame, [fps*0.5,fps*1.2], [0,50],
    {extrapolateLeft:'clamp', extrapolateRight:'clamp'});

  return (
    <div style={{position:'absolute', top:95, right:70,
      display:'flex', flexDirection:'column', alignItems:'flex-end', gap:6,
      opacity, transform:`translateX(${slideIn}px)`}}>
      <div style={{color:'rgba(180,140,80,0.85)', fontSize:16,
        fontFamily:'Georgia,serif', letterSpacing:'0.35em', textTransform:'uppercase',
        textShadow:'0 1px 8px rgba(0,0,0,0.8)'}}>
        {toRoman(chapter)} / {toRoman(total)}
      </div>
      <div style={{width:lineWidth, height:1, background:'linear-gradient(90deg, transparent, rgba(180,140,80,0.7))', alignSelf:'flex-end'}}/>
    </div>
  );
};
