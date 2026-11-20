// Small line icons drawn for Clipp (1.6 px stroke, round caps), sized by font-size.
const P: Record<string, string> = {
  bolt: "M13 2 4 14h7l-1 8 9-12h-7z",
  queue: "M4 6h16M4 12h16M4 18h10",
  live: "M12 12h.01M8.5 15.5a5 5 0 0 1 0-7M15.5 8.5a5 5 0 0 1 0 7M5.6 18.4a9 9 0 0 1 0-12.8M18.4 5.6a9 9 0 0 1 0 12.8",
  check: "M5 12.5 10 17 19 7",
  x: "M6 6l12 12M18 6 6 18",
  pen: "M4 20h4L19 9l-4-4L4 16zM13.5 6.5l4 4",
  eye: "M2 12s3.5-7 10-7 10 7 10 7-3.5 7-10 7S2 12 2 12zM12 15a3 3 0 1 0 0-6 3 3 0 0 0 0 6z",
  wave: "M3 12h3l3-7 4 14 3-7h5",
  text: "M5 6h14M12 6v13M8 19h8",
  film: "M4 4h16v16H4zM4 9h16M4 15h16M9 4v16M15 4v16",
  chip: "M7 7h10v10H7zM9 3v4M15 3v4M9 17v4M15 17v4M3 9h4M3 15h4M17 9h4M17 15h4",
  download: "M12 4v11M7 10l5 5 5-5M5 20h14",
  copy: "M9 9h11v11H9zM5 15V4h11",
  arrow: "M5 12h14M13 6l6 6-6 6",
  back: "M19 12H5M11 6l-6 6 6 6",
  out: "M15 4h4v16h-4M10 8l-4 4 4 4M6 12h11",
  undo: "M9 14 4 9l5-5M4 9h10a6 6 0 0 1 0 12h-3",
  sun: "M12 4V2M12 22v-2M4 12H2M22 12h-2M5.6 5.6 4.2 4.2M19.8 19.8l-1.4-1.4M5.6 18.4l-1.4 1.4M19.8 4.2l-1.4 1.4M12 17a5 5 0 1 0 0-10 5 5 0 0 0 0 10z",
  scissors: "M6 9a3 3 0 1 0 0-6 3 3 0 0 0 0 6zM6 21a3 3 0 1 0 0-6 3 3 0 0 0 0 6zM8.1 7.9 20 20M8.1 16.1 20 4",
};

export function Icon({ name, size = "1em" }: { name: keyof typeof P | string; size?: string | number }) {
  return (
    <svg width={size} height={size} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={1.6}
      strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
      <path d={P[name] ?? ""} />
    </svg>
  );
}
