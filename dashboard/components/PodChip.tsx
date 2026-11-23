"use client";
import { podName } from "@/lib/pods";
import { useStore } from "@/lib/store";
import type { Clip } from "@/lib/types";

/** Which pod a clip belongs to: admin only, and only while the switcher is on All (Atlas pods §1). */
export function PodChip({ clip }: { clip: Pick<Clip, "pod_id"> }) {
  const { podsOn, access, pod, snap } = useStore();
  if (!podsOn || !access?.admin || pod !== null) return null;
  return <span className="pill">{podName(snap.pods, clip.pod_id)}</span>;
}

/** Shown where review buttons would be when this user may not review the clip (the DB refuses it too). */
export const NOT_YOURS = "Only this pod's owner reviews this clip.";
