"use client";
import { useRouter, useSearchParams } from "next/navigation";
import { Suspense, useEffect } from "react";

/** Old review route: the review console is the home page now (D116). Keeps ?clip= deep links working. */
function Go() {
  const router = useRouter();
  const clip = useSearchParams().get("clip");
  useEffect(() => { router.replace(clip ? `/?clip=${encodeURIComponent(clip)}` : "/"); }, [clip, router]);
  return null;
}
export default function ReviewRedirect() { return <Suspense fallback={null}><Go /></Suspense>; }
