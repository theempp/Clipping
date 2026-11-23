"use client";
import { useEffect, useState } from "react";
import type { Clip, Streamer } from "@/lib/types";
import { livePlayer } from "@/lib/view";
import { Avatar } from "./Avatar";
import { ClipPlayer } from "./ClipPlayer";
import { Icon } from "./Icon";

/** "live" = the PC sees the stream; "offline" = the PC is up and the streamer is not live;
 * "unknown" = the PC is not reporting, so we cannot tell and show the player anyway. */
export type LiveStatus = "live" | "offline" | "unknown";

const FRAME_ALLOW = "autoplay; fullscreen; picture-in-picture; encrypted-media";
const SANDBOX = "allow-scripts allow-same-origin allow-popups allow-popups-to-escape-sandbox allow-presentation";

export function useHost(): string {
  const [host, setHost] = useState("");
  useEffect(() => setHost(window.location.hostname), []);
  return host;
}

/** The 16:9 screen on a streamer page: the real Twitch/Kick player, the offline card, or the latest clip. */
export function LiveStage({ s, status, liveKey, view, clip }: {
  s: Streamer; status: LiveStatus; liveKey: string | null; view: "stream" | "clip"; clip: Clip | null;
}) {
  const host = useHost();
  const player = livePlayer(s, liveKey, host);
  const [force, setForce] = useState(false);
  useEffect(() => setForce(false), [s.id]);
  const showPlayer = !!player && (status !== "offline" || force);

  if (view === "clip") {
    return (
      <div className="clipv">
        <ClipPlayer clip={clip} autoPlay />
      </div>
    );
  }
  if (showPlayer && player) {
    return (
      <div className="stage">
        <iframe key={player.src} src={player.src} title={`${s.display_name} live on ${player.platform}`}
          allow={FRAME_ALLOW} allowFullScreen sandbox={SANDBOX} referrerPolicy="origin" />
      </div>
    );
  }
  return (
    <div className="stage">
      <div className="off">
        <Avatar s={s} size={88} />
        <b>{player ? `${s.display_name} is offline` : host ? "No player for this channel" : "Loading player…"}</b>
        <span>{player ? "Clipp starts watching the moment they go live." : "This streamer has no Twitch or Kick channel saved."}</span>
        {player && (
          <div className="chips">
            <button type="button" className="b ok" onClick={() => setForce(true)}><Icon name="play" /> Load player anyway</button>
            <a className="b" href={player.watch} target="_blank" rel="noreferrer noopener"><Icon name="external" /> Open on {player.platform === "kick" ? "Kick" : "Twitch"}</a>
          </div>
        )}
      </div>
    </div>
  );
}

/** Twitch chat beside the stream (Kick does not allow its chat in a frame). */
export function LiveChat({ s, liveKey }: { s: Streamer; liveKey: string | null }) {
  const host = useHost();
  const player = livePlayer(s, liveKey, host);
  if (!player?.chat) {
    return <p className="quiet">{player?.platform === "kick" ? "Kick does not allow its chat inside other sites. Open it on Kick instead." : "Chat loads here."}</p>;
  }
  return <iframe className="chatf" src={player.chat} title={`${s.display_name} chat`} sandbox={SANDBOX} referrerPolicy="origin" />;
}
