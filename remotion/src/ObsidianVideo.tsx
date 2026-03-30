import {
  AbsoluteFill, Audio, Sequence, Img,
  useCurrentFrame, useVideoConfig, interpolate, staticFile, spring,
} from 'remotion';
import {Captions} from './Captions';

import {Letterbox} from './animations/Letterbox';
import {ChapterMarker} from './animations/ChapterMarker';
import {KenBurns} from './animations/KenBurns';
import {MultiImageKenBurns} from './animations/MultiImageKenBurns';
import {TwistReveal, SceneDip} from './animations/ActTransition';
import {MapAnimation} from './animations/MapAnimation';
import {TimelineBar} from './animations/TimelineBar';
import {LowerThird} from './animations/LowerThird';
import {KeyText} from './animations/KeyText';
import {FilmGrain} from './animations/FilmGrain';
import {
  buildNarrationMask, distanceToSpeech,
  primaryMusicVolume, secondaryMusicVolume, ambientVolume, stemVolume,
  type WordTimestamp,
} from './audio-utils';
import videoData from './video-data.json';
interface Scene {
  narration: string; start_time: number; end_time: number;
  mood: string; year?: string; location?: string; ai_image?: string; ai_images?: string[];
  is_reveal_moment?: boolean; narrative_position?: string;
  narrative_function?: string;
  show_map?: boolean; show_timeline?: boolean;
  lower_third?: string | null; key_text?: string | null;
  key_text_type?: 'date' | 'claim' | 'name' | null;
  era_start?: string; era_end?: string;
  ambient_file?: string | null;
  sfx_file?: string | null;
  sfx_start_offset?: number;
  visual_treatment?: 'standard' | 'close_portrait' | 'wide_establishing' | 'artifact_detail' | 'map_overhead' | 'text_overlay_dark';
  is_breathing_room?: boolean;
  // Scene intent fields (resolved by Python scene_intent.py)
  intent_transition_type?: 'normal' | 'act' | 'reveal' | 'silence';
  intent_motion_seed?: number;
  intent_music_volume_base?: number;
  intent_pace_modifier?: number;
  intent_caption_style?: 'standard' | 'emphasis' | 'whisper';
  intent_scene_energy?: number;
  intent_speech_intensity?: number;
  intent_silence_beat?: boolean;
  claim_confidence?: 'established' | 'contested' | 'speculative' | null;
  is_synthetic?: boolean;
  film_grain_intensity?: number;
  vignette_intensity?: number;
}
interface EndscreenRecommended {
  youtube_id: string;
  title: string;
  thumbnail: string;
}
interface AudioConfig {
  ducking?: { speechVolume?: number; silenceVolume?: number; attackSeconds?: number; releaseSeconds?: number; rampSeconds?: number };
  actMultipliers?: { act1?: number; act2?: number; act3?: number; ending?: number };
  stemDucking?: {
    bass?: { speechVolume?: number; silenceVolume?: number };
    drums?: { speechVolume?: number; silenceVolume?: number };
    instruments?: { speechVolume?: number; silenceVolume?: number };
  };
}
interface VideoData {
  scenes: Scene[]; word_timestamps: WordTimestamp[]; total_duration_seconds: number;
  music_file?: string | null;
  music_start_offset?: number;
  music_file_secondary?: string | null;
  music_secondary_start_offset?: number;
  music_adapted?: boolean;
  music_stems?: { bass?: string; drums?: string; instruments?: string } | null;
  showEndscreen?: boolean;
  endscreen_recommended?: EndscreenRecommended | null;
  audio_config?: AudioConfig;
}

const Particle: React.FC<{seed: number; mood: string}> = ({seed, mood}) => {
  const frame = useCurrentFrame();
  const moodColor: Record<string,string> = {
    dark:'rgba(180,140,80,', tense:'rgba(200,80,80,',
    dramatic:'rgba(80,180,120,', cold:'rgba(120,160,220,', reverent:'rgba(220,200,120,',
    wonder:'rgba(100,160,220,', warmth:'rgba(220,180,100,', absurdity:'rgba(200,160,80,',
  };
  const color = moodColor[mood] || moodColor.dark;
  const speed = 0.15 + (seed % 7) * 0.04;
  const x = (seed * 137.5) % 100;
  const y = (100 + (seed % 30)) - frame * speed;
  const size = 1 + (seed % 3) * 0.8;
  if (y < -10 || y > 110) return null;
  const opacity = interpolate(Math.min(100, y), [-10,20,60,100], [0,0.3,0.6,0], {extrapolateLeft:'clamp',extrapolateRight:'clamp'});
  return <div style={{position:'absolute',left:`${x}%`,top:`${y}%`,width:size,height:size*4,background:`linear-gradient(180deg,transparent,${color}0.8))`,borderRadius:'50%',opacity}}/>;
};

const GeometricAccent: React.FC<{mood:string}> = ({mood}) => {
  const frame = useCurrentFrame();
  const {fps} = useVideoConfig();
  const rotate = interpolate(frame,[0,fps*60],[0,45]);
  const scale = 1 + Math.sin(frame/(fps*4))*0.05;
  const moodColor: Record<string,string> = {dark:'#b48c50',tense:'#c85050',dramatic:'#50b478',cold:'#7890dc',reverent:'#dccc78',wonder:'#5090dc',warmth:'#dca050',absurdity:'#c8a050'};
  const color = moodColor[mood] || moodColor.dark;
  return (
    <>
      <div style={{position:'absolute',top:'50%',left:'50%',width:600,height:600,transform:`translate(-50%,-50%) rotate(${rotate}deg) scale(${scale})`,border:`1px solid ${color}`,opacity:0.06}}/>
      <div style={{position:'absolute',top:'50%',left:'50%',width:400,height:400,transform:`translate(-50%,-50%) rotate(${-rotate*1.5}deg) scale(${scale})`,border:`1px solid ${color}`,opacity:0.09}}/>
      {([[0,0],[1,0],[0,1],[1,1]] as [number,number][]).map(([cx,cy],i) => (
        <div key={i} style={{position:'absolute',left:cx===0?60:undefined,right:cx===1?60:undefined,top:cy===0?60:undefined,bottom:cy===1?60:undefined,width:40,height:40,borderTop:cy===0?`1px solid ${color}`:undefined,borderBottom:cy===1?`1px solid ${color}`:undefined,borderLeft:cx===0?`1px solid ${color}`:undefined,borderRight:cx===1?`1px solid ${color}`:undefined,opacity:0.4}}/>
      ))}
    </>
  );
};

const DarkBackground: React.FC<{mood:string}> = ({mood}) => {
  const frame = useCurrentFrame();
  const {fps} = useVideoConfig();
  const moodBg: Record<string,[string,string]> = {dark:['#08080e','#140a14'],tense:['#0e0808','#200808'],dramatic:['#080e08','#081408'],cold:['#08080e','#080e14'],reverent:['#0e0e08','#141408'],wonder:['#08081a','#0a1028'],warmth:['#0e0a08','#1a1008'],absurdity:['#0e0c08','#181208']};
  const [bg1,bg2] = moodBg[mood] || moodBg.dark;
  const px = 50 + Math.sin(frame/(fps*8))*8;
  const py = 50 + Math.cos(frame/(fps*6))*6;
  return (
    <AbsoluteFill style={{background:`radial-gradient(ellipse at ${px}% ${py}%, ${bg2} 0%, ${bg1} 65%)`}}>
      <AbsoluteFill style={{background:'radial-gradient(ellipse at 50% 50%, transparent 35%, rgba(0,0,0,0.85) 100%)'}}/>
      <GeometricAccent mood={mood}/>
      {Array.from({length:4},(_,i) => <Particle key={i} seed={i*17+3} mood={mood}/>)}
    </AbsoluteFill>
  );
};

/** Mood-specific color overlay on images — subtle tint that reinforces emotion */
const MoodOverlay: React.FC<{mood: string}> = ({mood}) => {
  const overlays: Record<string, string> = {
    tense:    'radial-gradient(ellipse at 50% 50%, rgba(100,20,20,0.12) 0%, rgba(60,0,0,0.25) 100%)',
    dramatic: 'radial-gradient(ellipse at 50% 50%, rgba(80,60,20,0.1) 0%, rgba(40,20,0,0.2) 100%)',
    dark:     'radial-gradient(ellipse at 50% 50%, transparent 30%, rgba(0,0,0,0.3) 100%)',
    cold:     'radial-gradient(ellipse at 50% 50%, rgba(20,30,60,0.15) 0%, rgba(10,15,40,0.25) 100%)',
    reverent: 'radial-gradient(ellipse at 50% 30%, rgba(80,60,20,0.1) 0%, rgba(20,10,0,0.2) 100%)',
    wonder:   'radial-gradient(ellipse at 50% 40%, rgba(20,40,80,0.1) 0%, rgba(10,20,50,0.18) 100%)',
    warmth:   'radial-gradient(ellipse at 50% 50%, rgba(80,50,10,0.08) 0%, rgba(40,25,5,0.15) 100%)',
    absurdity:'radial-gradient(ellipse at 50% 50%, rgba(60,50,20,0.08) 0%, rgba(30,20,5,0.15) 100%)',
  };
  return (
    <div style={{
      position:'absolute', top:0, left:0, right:0, bottom:0,
      background: overlays[mood] || overlays.dark,
      pointerEvents: 'none',
    }}/>
  );
};

/** Era-specific color grading — historical tint based on time period.
 *  Uses CSS filter (not backdropFilter) for much better render performance.
 *  filter applies to the div itself, which is an empty overlay — the visual
 *  result is the same tint effect but without GPU recomposition per frame. */
const EraGrading: React.FC<{year: string}> = ({year}) => {
  if (!year) return null;
  const yearNum = parseInt(year.replace(/[^\d-]/g, ''), 10);
  const isBC = /BC|BCE/i.test(year);
  const effectiveYear = isBC ? -Math.abs(yearNum) : yearNum;

  let overlay = '';
  if (effectiveYear < 0) {
    overlay = 'linear-gradient(180deg, rgba(120,90,40,0.15) 0%, rgba(80,50,20,0.22) 100%)';
  } else if (effectiveYear < 500) {
    overlay = 'linear-gradient(180deg, rgba(100,80,30,0.12) 0%, rgba(60,40,10,0.18) 100%)';
  } else if (effectiveYear < 1500) {
    overlay = 'linear-gradient(180deg, rgba(30,40,60,0.14) 0%, rgba(20,25,40,0.20) 100%)';
  } else if (effectiveYear < 1800) {
    overlay = 'linear-gradient(180deg, rgba(60,50,30,0.10) 0%, rgba(40,30,15,0.16) 100%)';
  } else if (effectiveYear < 1950) {
    overlay = 'linear-gradient(180deg, rgba(40,40,40,0.12) 0%, rgba(20,20,20,0.18) 100%)';
  } else if (effectiveYear < 2000) {
    overlay = 'linear-gradient(180deg, rgba(50,40,30,0.08) 0%, rgba(30,25,15,0.12) 100%)';
  }

  if (!overlay) return null;

  return (
    <div style={{
      position:'absolute', top:0, left:0, right:0, bottom:0,
      background: overlay,
      mixBlendMode: 'multiply',
      pointerEvents: 'none',
    }}/>
  );
};

const EraStamp: React.FC<{text:string}> = ({text}) => {
  const frame = useCurrentFrame();
  const {fps} = useVideoConfig();
  if (!text) return null;
  const opacity = interpolate(frame,[fps*0.2,fps*0.7,fps*2.5,fps*3],[0,1,1,0],{extrapolateLeft:'clamp',extrapolateRight:'clamp'});
  const lineW = interpolate(frame,[fps*0.2,fps*0.9],[0,200],{extrapolateLeft:'clamp',extrapolateRight:'clamp'});
  return (
    <div style={{display:'flex',flexDirection:'column',alignItems:'center',gap:8,opacity}}>
      <div style={{color:'rgba(180,140,80,0.9)',fontSize:20,fontFamily:'Georgia,serif',letterSpacing:'0.3em',textTransform:'uppercase',
        textShadow:'0 1px 12px rgba(0,0,0,0.9)'}}>{text}</div>
      <div style={{width:lineW,height:1,background:'linear-gradient(90deg,transparent,rgba(180,140,80,0.7),transparent)'}}/>
    </div>
  );
};


const SceneContent: React.FC<{
  scene: Scene; duration: number; words: WordTimestamp[];
  chapterNum: number; totalChapters: number;
}> = ({scene, duration, words, chapterNum, totalChapters}) => {
  const frame = useCurrentFrame();
  const {fps} = useVideoConfig();

  const fadeFrames = Math.floor(fps * 0.5);
  const fadeIn  = interpolate(frame,[0,fadeFrames],[0,1],{extrapolateLeft:'clamp',extrapolateRight:'clamp'});
  const fadeOut = interpolate(frame,[duration-fadeFrames,duration],[1,0],{extrapolateLeft:'clamp',extrapolateRight:'clamp'});
  const opacity = Math.min(fadeIn, fadeOut);

  const hasEraInfo = !!(scene.year || scene.location);
  const isReveal = scene.is_reveal_moment === true;

  return (
    <AbsoluteFill style={{opacity}}>
      {/* Background: AI image(s) with Ken Burns (treatment-aware) OR animated dark background */}
      {scene.ai_images && scene.ai_images.length > 1 ? (
        <MultiImageKenBurns images={scene.ai_images} duration={duration}
          seed={scene.intent_motion_seed ?? chapterNum}
          treatment={scene.visual_treatment || 'standard'}/>
      ) : scene.ai_image ? (
        <KenBurns imageSrc={scene.ai_image} duration={duration}
          seed={scene.intent_motion_seed ?? chapterNum}
          treatment={scene.visual_treatment || 'standard'}/>
      ) : (
        <DarkBackground mood={scene.mood || 'dark'}/>
      )}

      {/* Mood-specific color overlay */}
      <MoodOverlay mood={scene.mood || 'dark'}/>

      {/* Era-specific color grading */}
      <EraGrading year={scene.year || ''}/>

      {/* Scene boundary dip — intent_transition_type overrides energy-based mapping */}
      {scene.intent_transition_type !== 'reveal' && (
        <SceneDip
          duration={duration}
          intensity={
            scene.intent_transition_type === 'act' || scene.intent_transition_type === 'silence'
              ? 'act'
              : (scene.narrative_position === 'act2' || scene.narrative_position === 'act3' ? 'act' : 'normal')
          }
          transitionDurationSec={
            scene.intent_transition_type === 'silence' ? 2.0
            : scene.intent_transition_type === 'act' ? 1.5
            : (scene.intent_scene_energy ?? 0.5) <= 0.3 ? 1.2
            : (scene.intent_scene_energy ?? 0.5) >= 0.7 ? 0.25
            : 0.6
          }
        />
      )}

      {/* Twist reveal flash effect */}
      {isReveal && <TwistReveal/>}

      <Letterbox/>
      <ChapterMarker chapter={chapterNum} total={totalChapters}/>

      {/* ── Graphics Priority Ladder ──────────────────────────────────────── */}
      {/* Silence beats: suppress ALL overlays for a clean dramatic frame.    */}
      {/* Otherwise: max 2 concurrent overlays. Lower-third suppresses map.   */}
      {/* key_text suppressed when lower_third is present.                    */}
      {!scene.intent_silence_beat && (<>

      {/* Era stamp — only show if NO timeline bar (they overlap at top) */}
      {hasEraInfo && !scene.show_timeline && (
        <AbsoluteFill style={{display:'flex',flexDirection:'column',alignItems:'center',justifyContent:'flex-start',paddingTop:100}}>
          <EraStamp text={scene.year || scene.location || ''}/>
        </AbsoluteFill>
      )}

      {/* Motion graphics: Timeline bar (replaces EraStamp when active — top area) */}
      {scene.show_timeline && scene.year && (
        <TimelineBar
          currentYear={scene.year}
          eraStart={scene.era_start || ''}
          eraEnd={scene.era_end || ''}
          duration={duration}
        />
      )}

      {/* Motion graphics: Map animation — suppressed when lower_third is active (same visual lane) */}
      {scene.show_map && scene.location && !scene.lower_third && (
        <MapAnimation location={scene.location} year={scene.year || ''} duration={duration}/>
      )}

      {/* Motion graphics: Lower-third for key figures (left side, above caption zone) */}
      {scene.lower_third && (
        <LowerThird
          name={scene.lower_third.split(',')[0]?.trim() || scene.lower_third}
          title={scene.lower_third.split(',').slice(1).join(',').trim() || ''}
          duration={duration}
        />
      )}

      {/* Motion graphics: On-screen key text (center, only when no lower-third to avoid clutter) */}
      {scene.key_text && !scene.lower_third && (
        <KeyText
          text={scene.key_text}
          emphasis={scene.key_text_type || 'claim'}
          duration={duration}
        />
      )}

      </>)}

      {/* Captions — hidden during silence beats and breathing room for dramatic silence */}
      {!scene.is_breathing_room && !scene.intent_silence_beat && (
        <Captions words={words} sceneStartTime={scene.start_time} captionStyle={scene.intent_caption_style ?? 'standard'}/>
      )}

      {/* Breathing room overlay — subtle "let it sink in" visual treatment */}
      {scene.is_breathing_room && (
        <AbsoluteFill style={{
          background: 'linear-gradient(180deg, transparent 60%, rgba(0,0,0,0.4) 100%)',
          pointerEvents: 'none',
        }}/>
      )}

      {/* Film grain — subtle texture to mask AI-generated feel */}
      <FilmGrain intensity={scene.film_grain_intensity ?? 0.1} vignetteIntensity={scene.vignette_intensity ?? 0.15}/>
    </AbsoluteFill>
  );
};

// ── End screen (20-second CTA) ─────────────────────────────────────────────────
export const END_SCREEN_DURATION_SEC = 12;

const EndScreen: React.FC<{durationFrames: number; lastSceneImage?: string}> = ({durationFrames, lastSceneImage}) => {
  const frame = useCurrentFrame();
  const {fps} = useVideoConfig();

  const titleScale = spring({frame, fps, config:{damping:18, stiffness:120, mass:0.8}, from:0.85, to:1.0});
  const lineW = interpolate(frame, [fps*0.3, fps*1.5], [0, 500], {extrapolateLeft:'clamp', extrapolateRight:'clamp'});
  const taglineOpacity = interpolate(frame, [fps*1.5, fps*2.5], [0, 1], {extrapolateLeft:'clamp', extrapolateRight:'clamp'});
  const quoteOpacity = interpolate(frame, [fps*3.0, fps*4.5], [0, 1], {extrapolateLeft:'clamp', extrapolateRight:'clamp'});

  const fadeOut = interpolate(frame, [durationFrames - fps*0.8, durationFrames], [1, 0], {extrapolateLeft:'clamp', extrapolateRight:'clamp'});

  return (
    <AbsoluteFill style={{opacity: fadeOut}}>
      {/* Background: last scene image (blurred + darkened) for visual continuity */}
      {lastSceneImage ? (
        <AbsoluteFill>
          <Img src={staticFile(lastSceneImage)} style={{
            width:'100%', height:'100%', objectFit:'cover',
            filter: 'blur(20px) brightness(0.25) saturate(0.6)',
            transform: 'scale(1.1)',
          }}/>
        </AbsoluteFill>
      ) : (
        <AbsoluteFill style={{background:'radial-gradient(ellipse at 50% 40%, #140a20 0%, #08080e 70%)'}}/>
      )}

      {/* Dark overlay to ensure text readability */}
      <AbsoluteFill style={{background:'rgba(0,0,0,0.5)'}}/>

      {/* Film grain on end screen too */}
      <FilmGrain/>

      <AbsoluteFill style={{display:'flex', flexDirection:'column', alignItems:'center', justifyContent:'center', gap:40}}>
        {/* Channel brand — cinematic title card */}
        <div style={{transform:`scale(${titleScale})`, textAlign:'center'}}>
          <div style={{
            width: lineW, height: 1,
            background: 'linear-gradient(90deg, transparent, rgba(180,140,80,0.6), transparent)',
            margin: '0 auto 20px',
          }}/>
          <div style={{color:'rgba(180,140,80,0.95)', fontSize:28, fontFamily:'Georgia,serif',
            letterSpacing:'0.5em', textTransform:'uppercase',
            textShadow:'0 0 50px rgba(180,140,80,0.3), 0 2px 8px rgba(0,0,0,0.9)'}}>
            THE OBSIDIAN ARCHIVE
          </div>
          <div style={{
            width: lineW, height: 1,
            background: 'linear-gradient(90deg, transparent, rgba(180,140,80,0.6), transparent)',
            margin: '20px auto 0',
          }}/>
        </div>

        {/* Tagline */}
        <div style={{opacity: taglineOpacity, textAlign:'center'}}>
          <div style={{color:'rgba(240,232,216,0.8)', fontSize:22, fontFamily:'Georgia,serif',
            letterSpacing:'0.2em', fontStyle:'italic',
            textShadow:'0 2px 10px rgba(0,0,0,0.8)'}}>
            Every story has a shadow. We find it.
          </div>
        </div>

        {/* Closing quote — more cinematic than "LIKE SUBSCRIBE SHARE" */}
        <div style={{opacity: quoteOpacity, textAlign:'center', maxWidth: 700}}>
          <div style={{color:'rgba(180,140,80,0.6)', fontSize:16, fontFamily:'Georgia,serif',
            letterSpacing:'0.15em', textTransform:'uppercase'}}>
            More stories await
          </div>
        </div>
      </AbsoluteFill>
    </AbsoluteFill>
  );
};

// ── Endscreen overlay with YouTube endscreen placeholders ────────────────────

const EndscreenOverlay: React.FC<{durationFrames: number; totalNarrativeFrames: number; recommended?: EndscreenRecommended | null; lastSceneImage?: string}> = ({durationFrames, totalNarrativeFrames, recommended, lastSceneImage}) => {
  const frame = useCurrentFrame();
  const {fps} = useVideoConfig();

  const fadeIn = interpolate(frame, [0, Math.floor(fps * 1.5)], [0, 1], {extrapolateLeft:'clamp', extrapolateRight:'clamp'});
  // Graceful fade-out in the last second of the endscreen
  const fadeOut = durationFrames > 0
    ? interpolate(frame, [durationFrames - fps, durationFrames], [1, 0], {extrapolateLeft:'clamp', extrapolateRight:'clamp'})
    : 1;
  // Scale endscreen pacing relative to total video length — longer videos get slower reveals
  const pacingScale = totalNarrativeFrames > 0 ? Math.min(1.5, Math.max(1.0, totalNarrativeFrames / (fps * 300))) : 1.0;
  const channelScale = spring({frame, fps, config:{damping:20, stiffness:100, mass:0.9}, from:0.85, to:1.0});
  const lineW = interpolate(frame, [fps*0.3, fps*1.5], [0, 400], {extrapolateLeft:'clamp', extrapolateRight:'clamp'});
  const watchNextOpacity = interpolate(frame, [Math.floor(fps * 0.8 * pacingScale), Math.floor(fps * 1.8 * pacingScale)], [0, 1], {extrapolateLeft:'clamp', extrapolateRight:'clamp'});
  const placeholderOpacity = interpolate(frame, [Math.floor(fps * 1.2 * pacingScale), Math.floor(fps * 2.5 * pacingScale)], [0, 1], {extrapolateLeft:'clamp', extrapolateRight:'clamp'});
  const taglineOpacity = interpolate(frame, [Math.floor(fps * 2.0 * pacingScale), Math.floor(fps * 3.0 * pacingScale)], [0, 1], {extrapolateLeft:'clamp', extrapolateRight:'clamp'});

  const gold = '#b48c50';
  const cream = '#f0e8d8';

  return (
    <AbsoluteFill style={{opacity: fadeIn * fadeOut}}>
      {/* Background: last scene image blurred for visual continuity */}
      {lastSceneImage ? (
        <AbsoluteFill>
          <Img src={staticFile(lastSceneImage)} style={{
            width:'100%', height:'100%', objectFit:'cover',
            filter: 'blur(20px) brightness(0.25) saturate(0.6)',
            transform: 'scale(1.1)',
          }}/>
        </AbsoluteFill>
      ) : (
        <AbsoluteFill style={{background:'radial-gradient(ellipse at 50% 40%, #1a0e2a 0%, #08080e 75%)'}}/>
      )}

      <AbsoluteFill style={{background:'rgba(0,0,0,0.45)'}}/>
      <FilmGrain/>

      {/* Top section: branding */}
      <div style={{position:'absolute', top:'10%', left:0, right:0, display:'flex', flexDirection:'column', alignItems:'center', gap:20}}>
        <div style={{transform:`scale(${channelScale})`, textAlign:'center'}}>
          <div style={{
            width: lineW, height: 1,
            background: `linear-gradient(90deg, transparent, ${gold}, transparent)`,
            margin: '0 auto 16px',
          }}/>
          <div style={{color:gold, fontSize:24, fontFamily:'Georgia,serif',
            letterSpacing:'0.5em', textTransform:'uppercase',
            textShadow:'0 0 50px rgba(180,140,80,0.4), 0 2px 8px rgba(0,0,0,0.9)'}}>
            THE OBSIDIAN ARCHIVE
          </div>
          <div style={{
            width: lineW, height: 1,
            background: `linear-gradient(90deg, transparent, ${gold}, transparent)`,
            margin: '16px auto 0',
          }}/>
        </div>

        <div style={{opacity:watchNextOpacity, textAlign:'center'}}>
          <div style={{color:cream, fontSize:42, fontFamily:'Georgia,serif',
            fontWeight:'bold', letterSpacing:'0.06em',
            textShadow:'0 0 40px rgba(180,140,80,0.25), 0 2px 8px rgba(0,0,0,0.9)'}}>
            WATCH NEXT
          </div>
        </div>
      </div>

      {/* Bottom section: YouTube endscreen element placeholders — larger cards */}
      <div style={{position:'absolute', bottom:'12%', left:0, right:0, display:'flex', justifyContent:'center', gap:32, opacity:placeholderOpacity}}>
        {/* Recommended video card — larger for visibility */}
        <div style={{
          width:480, height:270,
          borderRadius:10,
          overflow:'hidden',
          border:`2px solid rgba(180,140,80,0.4)`,
          background:'rgba(10,8,14,0.9)',
          display:'flex', flexDirection:'column',
          boxShadow: '0 8px 32px rgba(0,0,0,0.6)',
        }}>
          {recommended ? (
            <>
              <div style={{flex:1, position:'relative', overflow:'hidden'}}>
                <Img src={recommended.thumbnail} style={{width:'100%', height:'100%', objectFit:'cover'}} />
                <div style={{position:'absolute', bottom:0, left:0, right:0, height:60,
                  background:'linear-gradient(transparent, rgba(10,8,14,0.95))'}} />
              </div>
              <div style={{padding:'10px 16px', background:'rgba(10,8,14,0.95)'}}>
                <div style={{color:cream, fontSize:16, fontFamily:'Georgia,serif',
                  lineHeight:'1.3', overflow:'hidden', display:'-webkit-box',
                  WebkitLineClamp:2, WebkitBoxOrient:'vertical' as const}}>
                  {recommended.title}
                </div>
              </div>
            </>
          ) : (
            <div style={{flex:1, display:'flex', alignItems:'center', justifyContent:'center',
              background:'rgba(180,140,80,0.04)'}}>
              <div style={{color:'rgba(180,140,80,0.5)', fontSize:16, fontFamily:'Georgia,serif',
                letterSpacing:'0.15em', textTransform:'uppercase'}}>
                RECOMMENDED
              </div>
            </div>
          )}
        </div>

        {/* Subscribe placeholder */}
        <div style={{
          width:480, height:270,
          border:`2px solid rgba(180,140,80,0.3)`,
          borderRadius:10,
          background:'rgba(180,140,80,0.04)',
          display:'flex', flexDirection:'column', alignItems:'center', justifyContent:'center', gap:16,
          boxShadow: '0 8px 32px rgba(0,0,0,0.4)',
        }}>
          <div style={{color:gold, fontSize:44, fontFamily:'Georgia,serif', fontWeight:'bold',
            textShadow:'0 0 30px rgba(180,140,80,0.3)'}}>
            +
          </div>
          <div style={{color:'rgba(180,140,80,0.6)', fontSize:15, fontFamily:'Georgia,serif',
            letterSpacing:'0.2em', textTransform:'uppercase'}}>
            SUBSCRIBE
          </div>
        </div>
      </div>

      {/* Tagline */}
      <div style={{position:'absolute', bottom:'6%', left:0, right:0, textAlign:'center', opacity:taglineOpacity}}>
        <div style={{color:'rgba(240,232,216,0.6)', fontSize:16, fontFamily:'Georgia,serif',
          letterSpacing:'0.2em', fontStyle:'italic',
          textShadow:'0 2px 8px rgba(0,0,0,0.8)'}}>
          Every story has a shadow. We find it.
        </div>
      </div>
    </AbsoluteFill>
  );
};

export const ObsidianVideo: React.FC = () => {
  const {fps} = useVideoConfig();
  const data = videoData as VideoData;
  const words: WordTimestamp[] = data.word_timestamps || [];
  const totalChapters = data.scenes.length;

  const narrativeDurationFrames = Math.ceil((data.total_duration_seconds || 1) * fps);
  const endScreenFrames         = END_SCREEN_DURATION_SEC * fps;
  const totalDur                = data.total_duration_seconds || 1;
  const hasSecondary            = !!data.music_file_secondary;

  // Pre-compute narration mask once (avoids O(n) scan per frame per track)
  const narrationMask = buildNarrationMask(words);
  const audioConfig = data.audio_config ?? {};

  // Find last scene's AI image for end screen background continuity
  const lastSceneImage = [...data.scenes].reverse().find(s => s.ai_image)?.ai_image;

  return (
    <AbsoluteFill style={{backgroundColor:'#08080e'}}>
      <Audio src={staticFile('narration.mp3')}/>
      {/* Music: stem-aware rendering if stems available, else legacy single track */}
      {data.music_stems ? (
        <>
          {data.music_stems.bass && (
            <Audio
              src={staticFile(data.music_stems.bass)}
              startFrom={Math.round((data.music_start_offset || 0) * fps)}
              volume={(f) => stemVolume(f, 'bass', fps, totalDur, narrationMask, hasSecondary, data.scenes, audioConfig.stemDucking ?? {}, audioConfig.actMultipliers)}
              loop={!data.music_adapted}
            />
          )}
          {data.music_stems.drums && (
            <Audio
              src={staticFile(data.music_stems.drums)}
              startFrom={Math.round((data.music_start_offset || 0) * fps)}
              volume={(f) => stemVolume(f, 'drums', fps, totalDur, narrationMask, hasSecondary, data.scenes, audioConfig.stemDucking ?? {}, audioConfig.actMultipliers)}
              loop={!data.music_adapted}
            />
          )}
          {data.music_stems.instruments && (
            <Audio
              src={staticFile(data.music_stems.instruments)}
              startFrom={Math.round((data.music_start_offset || 0) * fps)}
              volume={(f) => stemVolume(f, 'instruments', fps, totalDur, narrationMask, hasSecondary, data.scenes, audioConfig.stemDucking ?? {}, audioConfig.actMultipliers)}
              loop={!data.music_adapted}
            />
          )}
        </>
      ) : data.music_file && (
        <Audio
          src={staticFile(data.music_file)}
          startFrom={Math.round((data.music_start_offset || 0) * fps)}
          volume={(f) => primaryMusicVolume(f, fps, totalDur, narrationMask, hasSecondary, data.scenes, audioConfig.ducking, audioConfig.actMultipliers)}
          loop={!data.music_adapted}
        />
      )}
      {/* Secondary music track — crossfades in at Act 3 for emotional shift */}
      {data.music_file_secondary && (
        <Audio
          src={staticFile(data.music_file_secondary)}
          startFrom={Math.round((data.music_secondary_start_offset || 0) * fps)}
          volume={(f) => secondaryMusicVolume(f, fps, totalDur, narrationMask, data.scenes, audioConfig.ducking)}
          loop
        />
      )}

      {/* ── Narrative scenes with L-cut/J-cut overlap ── */}
      {/* Each scene's visuals extend slightly past its audio boundary,     */}
      {/* creating a cinematic overlap where the next scene's narration     */}
      {/* begins over the previous scene's imagery (L-cut effect).          */}
      {data.scenes.map((scene, i) => {
        const startFrame = Math.floor(scene.start_time * fps);
        const endFrame   = Math.ceil(scene.end_time * fps);
        const hasNextScene = i < data.scenes.length - 1;
        const energy = scene.intent_scene_energy ?? 0.5;
        const transType = scene.intent_transition_type ?? 'normal';

        // Energy-driven L-cut/J-cut durations
        // Reveal/silence: hard cuts (no overlap)
        // Breathing room: long lingering overlap
        // Normal: energy-based
        let lCutSec = 0.3;
        let jCutSec = 0.2;
        if (transType === 'reveal') {
          lCutSec = 0; jCutSec = 0;
        } else if (transType === 'silence') {
          lCutSec = 0.8; jCutSec = 0.4;
        } else if (scene.is_breathing_room) {
          lCutSec = 0.8; jCutSec = 0.4;
        } else if (energy >= 0.7) {
          lCutSec = 0.2; jCutSec = 0.1;  // Quick but not hard cut for high energy
        } else if (energy <= 0.3) {
          lCutSec = 0.5; jCutSec = 0.3;  // Slow dissolve for low energy
        }

        const overlapFrames = Math.floor(fps * lCutSec);
        const extendedEnd = hasNextScene ? endFrame + overlapFrames : endFrame;
        const jCutFrames = i > 0 ? Math.floor(fps * jCutSec) : 0;
        const adjustedStart = Math.max(0, startFrame - jCutFrames);
        const duration = extendedEnd - adjustedStart;
        if (duration <= 0) return null;
        return (
          <Sequence key={i} from={adjustedStart} durationInFrames={duration}>
            <SceneContent
              scene={scene}
              duration={duration}
              words={words}
              chapterNum={i+1}
              totalChapters={totalChapters}
            />
            {/* Per-scene ambient sound layer — suppressed during silence beats */}
            {scene.ambient_file && !scene.intent_silence_beat && (
              <Audio
                src={staticFile(scene.ambient_file)}
                volume={(f) => {
                  const t = (adjustedStart + f) / fps;
                  const isSpeaking = distanceToSpeech(t, narrationMask) === 0;
                  return ambientVolume(f / duration, isSpeaking);
                }}
                loop
              />
            )}
            {/* Per-scene SFX one-shot — suppressed during silence beats */}
            {scene.sfx_file && !scene.intent_silence_beat && (
              <Audio
                src={staticFile(scene.sfx_file)}
                startFrom={Math.round((scene.sfx_start_offset || 0) * fps)}
                volume={(f) => {
                  const progress = f / Math.min(duration, fps * 3);
                  // Quick fade in over 0.1s, sustain, fade out over 0.5s
                  const fadeIn = interpolate(progress, [0, 0.05], [0, 1], {extrapolateLeft:'clamp', extrapolateRight:'clamp'});
                  const fadeOut = interpolate(progress, [0.7, 1], [1, 0], {extrapolateLeft:'clamp', extrapolateRight:'clamp'});
                  return Math.min(fadeIn, fadeOut) * 0.35;
                }}
              />
            )}
          </Sequence>
        );
      })}

      {/* ── End screen: either branded EndScreen or YouTube-optimized EndscreenOverlay ── */}
      {/* When showEndscreen is enabled, use the YouTube placeholder overlay (better for algorithm). */}
      {/* Otherwise, fall back to the branded EndScreen. Never render both — they collide. */}
      {data.showEndscreen !== false ? (
        <Sequence from={narrativeDurationFrames} durationInFrames={endScreenFrames}>
          <EndscreenOverlay durationFrames={endScreenFrames} totalNarrativeFrames={narrativeDurationFrames} recommended={data.endscreen_recommended} lastSceneImage={lastSceneImage}/>
        </Sequence>
      ) : (
        <Sequence from={narrativeDurationFrames} durationInFrames={endScreenFrames}>
          <EndScreen durationFrames={endScreenFrames} lastSceneImage={lastSceneImage}/>
        </Sequence>
      )}
    </AbsoluteFill>
  );
};
