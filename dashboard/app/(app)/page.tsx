"use client";
import { useRouter, useSearchParams } from "next/navigation";
import { Suspense, useEffect } from "react";
import { Editor } from "@/components/halo/editor";
import { useReview } from "@/components/halo/review";
import { Channels, Funnel, Hero, Next24, Pocket, Queue, Spend, useQueue } from "@/components/halo/sections";
import { POD_HOME_ON } from "@/lib/env";
import { useStore } from "@/lib/store";
import { PodHome } from "./PodHome";

/** Review (Halo Pro, D116): streamers left, top pick in the middle, queue right, four widgets below. */
export default function ReviewHome() {
  const { pod } = useStore();
  // Pod home (Phase 3): members always, the admin once a pod is picked. Admin "All" keeps the review console.
  if (POD_HOME_ON && pod) return <div className="legacy z-legacy"><PodHome podId={pod} /></div>;
  return <Suspense fallback={null}><Console /></Suspense>;
}

function Console() {
  const { snap } = useStore();
  const ui = useReview();
  const params = useSearchParams();
  const router = useRouter();
  const { queue, hero, rest } = useQueue();
  const editing = ui.edit ? snap.clips.find((c) => c.id === ui.edit) ?? null : null;

  // Deep links from search, alerts and old routes: /?clip=<id> opens the review popup, /?edit=<id> the editor.
  const clipParam = params.get("clip"), editParam = params.get("edit");
  useEffect(() => {
    if (!clipParam && !editParam) return;
    if (!snap.clips.length) return;
    if (editParam && snap.clips.some((c) => c.id === editParam)) ui.openEditor(editParam);
    else if (clipParam && snap.clips.some((c) => c.id === clipParam)) ui.openPop(clipParam);
    router.replace("/", { scroll: false });
  }, [clipParam, editParam, snap.clips.length]); // eslint-disable-line react-hooks/exhaustive-deps

  return (
    <>
      <Pocket />
      <Hero clip={hero} rank={hero && queue[0]?.id === hero.id ? 0 : 1} />
      <Queue queue={queue} rest={rest} />
      <Spend />
      <div className="z-lower"><Funnel /><Next24 /><Channels /></div>
      {editing && <Editor key={editing.id} clip={editing} />}
    </>
  );
}
