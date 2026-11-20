// `npm run demo`: start the dashboard with sample data, no Supabase needed. Works on Windows.
import { spawn } from "node:child_process";
const p = spawn("npx", ["next", "dev", "-p", process.env.PORT || "3000"], {
  stdio: "inherit",
  shell: process.platform === "win32",
  env: { ...process.env, NEXT_PUBLIC_CLIPP_DEMO: "1" },
});
p.on("exit", (code) => process.exit(code ?? 0));
