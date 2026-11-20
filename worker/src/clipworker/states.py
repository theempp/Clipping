"""Two state machines.

Local job stages (SQLite, restart-safe, Install plan gap 5):
  detected > captured > transcribed > judged > rendered > qa_passed > uploaded
  plus terminal dropped / qa_failed / error.

Remote clip states (Supabase, publish-approval-gate):
  qa_passed > pending_review > approved|revise|rejected > scheduled > published|failed
Only `approved` can reach a publisher. The worker itself may only move a clip
to `pending_review` (review handoff) and approved > scheduled > published|failed.
The same table is enforced again by a Postgres trigger (defense in depth).
"""
from __future__ import annotations

LOCAL_STAGES = ["detected", "captured", "transcribed", "judged", "rendered",
                "qa_passed", "uploaded"]
LOCAL_TERMINAL = {"uploaded", "dropped", "qa_failed", "error"}

CLIP_TRANSITIONS: dict[str, set[str]] = {
    "qa_passed": {"pending_review"},
    "pending_review": {"approved", "revise", "rejected"},
    "revise": {"pending_review", "rejected"},       # re-render then back to review
    "approved": {"scheduled", "revise", "rejected"},
    "scheduled": {"published", "failed"},
    "failed": {"scheduled", "rejected"},            # retry only via scheduled
    "published": set(),
    "rejected": set(),
}

# Who may make which move. "human" = Zo through the dashboard RPC.
WORKER_MOVES = {("qa_passed", "pending_review"), ("revise", "pending_review"),
                ("approved", "scheduled"), ("scheduled", "published"),
                ("scheduled", "failed"), ("failed", "scheduled")}


class TransitionError(ValueError):
    pass


def next_local(stage: str) -> str:
    i = LOCAL_STAGES.index(stage)
    if i + 1 >= len(LOCAL_STAGES):
        raise TransitionError(f"{stage} is final")
    return LOCAL_STAGES[i + 1]


def check_local(src: str, dst: str) -> None:
    if src in LOCAL_TERMINAL:
        raise TransitionError(f"job is terminal ({src})")
    if dst in {"dropped", "qa_failed", "error"}:
        return
    if dst != next_local(src):
        raise TransitionError(f"local stage {src} -> {dst} not allowed")


def check_clip(src: str, dst: str, actor: str) -> None:
    if dst not in CLIP_TRANSITIONS.get(src, set()):
        raise TransitionError(f"clip state {src} -> {dst} not allowed")
    if actor == "worker" and (src, dst) not in WORKER_MOVES:
        raise TransitionError(f"worker may not move clip {src} -> {dst}")
