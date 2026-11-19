import { useEffect, useMemo, useRef, useState, type CSSProperties } from "react";
import type { RadioClip, RadioTimeline } from "../../features/session-review/contracts";
import { useReplayTime, useSessionTimeLabel, useSessionWorkspace } from "../../features/sessions/SessionWorkspaceContext";
import { getEntryAccent, getEntryDisplayName } from "../../features/sessions/session-utils";
import { radioClipsInWindow } from "./radio-clips";

type Playback = { key: string; status: "loading" | "playing" | "paused" | "error" };

function clipKey(clip: RadioClip) {
  return `${clip.entry_id}:${clip.time_ms}:${clip.recording_url}`;
}

export function TeamRadio({ radio }: { radio: RadioTimeline }) {
  const { mode, replay, entries, selectedDriverIds } = useSessionWorkspace();
  const timeMs = useReplayTime();
  const timeLabel = useSessionTimeLabel();
  const inReplay = mode === "simulation";
  const selectedClips = useMemo(() => {
    const selection = new Set(selectedDriverIds);
    return radio.clips.filter((clip) => !selection.size || selection.has(clip.entry_id));
  }, [radio.clips, selectedDriverIds]);
  const clips = radioClipsInWindow(selectedClips, inReplay ? { startMs: replay.minTimeMs, timeMs } : undefined);
  const hasReplayClips = selectedClips.some((clip) =>
    clip.time_ms >= replay.minTimeMs && clip.time_ms <= replay.maxTimeMs,
  );
  const playerRef = useRef<HTMLAudioElement>(null);
  const request = useRef(0);
  const [playback, setPlayback] = useState<Playback>();
  const stillVisible = !playback || clips.some((clip) => clipKey(clip) === playback.key);

  useEffect(() => {
    const player = playerRef.current;
    return () => { player?.pause(); };
  }, []);

  useEffect(() => {
    const player = playerRef.current;
    if (!stillVisible && player?.hasAttribute("src")) {
      request.current++;
      player.pause();
      player.removeAttribute("src");
      player.load();
    }
  }, [stillVisible]);

  function play(clip: RadioClip) {
    const player = playerRef.current;
    if (!player) return;
    const key = clipKey(clip);
    const current = ++request.current;
    if (playback?.key === key && (playback.status === "playing" || playback.status === "loading")) {
      player.pause();
      setPlayback({ key, status: "paused" });
      return;
    }
    if (player.getAttribute("src") !== clip.recording_url) player.src = clip.recording_url;
    else if (playback?.status === "error") player.load();
    setPlayback({ key, status: "loading" });
    void player.play().then(() => {
      if (current === request.current) setPlayback({ key, status: "playing" });
    }).catch(() => {
      if (current === request.current) setPlayback({ key, status: "error" });
    });
  }

  return (
    <>
      {inReplay ? (
        <div className="insight-context"><span>Replay · {timeLabel(timeMs)}</span></div>
      ) : null}
      <audio
        ref={playerRef}
        preload="none"
        onEnded={() => setPlayback(undefined)}
        onEmptied={(event) => {
          if (!event.currentTarget.hasAttribute("src")) setPlayback(undefined);
        }}
        onError={(event) => {
          if (event.currentTarget.error) setPlayback((state) => state && { ...state, status: "error" });
        }}
      />
      {clips.length ? (
        <ol className="review-list team-radio-list" aria-label="Team radio clips">
          {clips.map((clip) => {
            const key = clipKey(clip);
            const entry = entries.find((driver) => driver.id === clip.entry_id);
            const name = entry ? entry.driver_name || getEntryDisplayName(entry) : "Driver";
            const status = playback?.key === key ? playback.status : undefined;
            const active = status === "playing" || status === "loading";
            const time = timeLabel(clip.time_ms);
            const action = `${active ? "Pause" : "Play"} ${name} radio at ${time}`;
            const estimated = clip.timing_basis === "estimated_recording";
            return (
              <li key={key} style={entry ? { "--radio-team": getEntryAccent(entry) } as CSSProperties : undefined}
                data-playing={active} data-radio-time-ms={clip.time_ms}>
                <span className="team-radio-list__driver">
                  {entry ? <span className="team-radio-list__number">#{entry.car_number}</span> : null}
                  <strong>{name}</strong>
                </span>
                <time title={estimated
                  ? `Estimated recording time. Feed time ${timeLabel(clip.feed_time_ms)}.`
                  : "Feed time. The recording time is unknown."}>
                  {estimated ? `≈ ${time}` : `${time} · Feed`}
                </time>
                <button type="button" className="team-radio-list__play" aria-label={action} title={action} onClick={() => play(clip)}>
                  <span aria-hidden="true">{active ? "Ⅱ" : "▶"}</span>
                </button>
                {status === "error" ? <small role="status">Clip couldn’t play. Press play to retry.</small> : null}
              </li>
            );
          })}
        </ol>
      ) : (
        <p>
          {!radio.available ? "Radio metadata is unavailable for this session."
            : !selectedClips.length ? "No published clips for the selected drivers."
              : inReplay && !hasReplayClips ? "No published clips within this replay."
                : "Radio clips appear here as the race unfolds."}
        </p>
      )}
    </>
  );
}
