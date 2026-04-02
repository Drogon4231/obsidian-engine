import {Composition} from 'remotion';
import {ObsidianVideo, END_SCREEN_DURATION_SEC} from './ObsidianVideo';
import {ShortVideo} from './ShortVideo';
import videoData from './video-data.json';
import shortVideoData from './short-video-data.json';

export const RemotionRoot = () => {
  const fps = 30;
  const durationInFrames      = Math.max(24, Math.ceil((videoData.total_duration_seconds || 1) * fps) + END_SCREEN_DURATION_SEC * fps);
  // total_duration_seconds in short-video-data.json already includes the 1.5s
  // breathing room added by run_short_convert — do NOT add it again here.
  const shortDurationInFrames = Math.max(24, Math.ceil((shortVideoData.total_duration_seconds || 1) * fps));

  return (
    <>
      <Composition
        id="ObsidianArchive"
        component={ObsidianVideo}
        durationInFrames={durationInFrames}
        fps={fps}
        width={1920}
        height={1080}
        defaultProps={{}}
      />
      <Composition
        id="ObsidianShort"
        component={ShortVideo}
        durationInFrames={shortDurationInFrames}
        fps={fps}
        width={1080}
        height={1920}
        defaultProps={{}}
      />
    </>
  );
};
