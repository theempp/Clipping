"use client";
import { useRouter, useSearchParams } from "next/navigation";
import { Suspense, useEffect } from "react";

/** Old editor route: Edit clip opens the editor inside the review console now (D116). */
function Go() {
  const router = useRouter();
  const clip = useSearchParams().get("clip");
  useEffect(() => { router.replace(clip ? `/?edit=${encodeURIComponent(clip)}` : "/"); }, [clip, router]);
  return null;
}
export default function EditorRedirect() { return <Suspense fallback={null}><Go /></Suspense>; }
