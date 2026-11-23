import { redirect } from "next/navigation";

/** Old streamer URL (Stage dashboard). Streamer pages now live under /streamers. */
export default async function OldLive({ params }: { params: Promise<{ slug: string }> }) {
  const { slug } = await params;
  redirect(`/streamers/${encodeURIComponent(slug)}`);
}
