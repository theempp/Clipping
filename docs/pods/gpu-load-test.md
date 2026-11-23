# GPU load test — two pods, one queue (D096)

Goal: prove the RTX 5060 (8 GB) PC can serve Pod 1 + one Pod 2 streamer live at once, with whisperX large-v3 fp16 loaded once (`worker/src/clipworker/transcribe.py`) and one shared, pod-tagged job queue. Pass = commit to Pod 2. Fail = fix, or Pod 2 waits.

## Setup
- Worker build with pod-tagged jobs (`pod_id` on each job; one consumer; FIFO with round-robin across pods so one pod can't starve the other).
- Streams: Pod 1's live streamers (D069) + one Pod 2 streamer. If they aren't live together, replay VODs through `detector/replay.py` at 1x real time on the same clock.
- Run length: 4 h minimum, including at least one high-chat window per streamer (spike burst).
- Log every 10 s to CSV: VRAM used/peak (`nvidia-smi --query-gpu=memory.used,utilization.gpu,temperature.gpu,power.draw`), CPU %, RAM, disk free, queue depth per pod, per-job timings (enqueue, start, transcribe, render, QA, done), errors.
- Baseline first: 1 h with Pod 1 only, same logging, for comparison.

## Pass / fail thresholds
| Metric | Pass | Fail |
|---|---|---|
| Model loads | exactly 1 whisperX + 1 align model for the whole run | any second load, or a reload after OOM |
| VRAM peak | <= 7.0 GB (1 GB headroom) | > 7.5 GB or any CUDA OOM |
| Detect-to-review latency (spike end to clip in review queue), p50 / p95 | <= 5 min / <= 12 min | p95 > 20 min |
| Queue depth, any pod | drains to 0 at least once every 30 min | grows for 30 min straight |
| Pod fairness | neither pod waits > 2x the other's median wait | one pod's jobs wait > 3x |
| Job failures | < 2% of jobs, all retried OK | any job lost, or > 5% failing |
| Pod isolation | 0 clips tagged with the wrong pod; 0 cross-pod rows | any mismatch |
| Capture | 0 dropped segments in the live buffers; chat clock drift < 2 s | any gap in a buffer |
| GPU temp / throttling | < 83 °C sustained, no throttle flags | thermal throttling |
| Disk | > 50 GB free at end; buffers rotate | < 20 GB free |
| Latency vs baseline | p95 no more than 2x the Pod 1-only p95 | > 3x |

Any single Fail = test fails. Borderline (between Pass and Fail) = rerun once at peak hours before deciding.

## Stress step (after a pass)
Add a third simultaneous spike burst (replayed) for 30 min. Record where it breaks. That sets the cap for adding more streamers.

## Output
Write the result as a D-number: pass/fail, peak VRAM, p50/p95 latency, cap found. Keep the CSV in `ops/loadtest/`.
