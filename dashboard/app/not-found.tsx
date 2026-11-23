import Link from "next/link";
export default function NotFound() {
  return (
    <>
      <div className="z-amb" aria-hidden="true" />
      <main className="z-gate"><div className="z-popbx z-sm"><h3>Not here</h3><div className="z-acts"><Link className="z-btn z-w" href="/">Back to Review</Link></div></div></main>
    </>
  );
}
