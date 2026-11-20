import pytest

from clipworker.states import TransitionError, check_clip, check_local


def test_local_stages_in_order():
    check_local("detected", "captured")
    check_local("rendered", "qa_failed")
    with pytest.raises(TransitionError):
        check_local("detected", "rendered")
    with pytest.raises(TransitionError):
        check_local("uploaded", "detected")


def test_worker_cannot_approve_or_skip_review():
    with pytest.raises(TransitionError):
        check_clip("pending_review", "approved", "worker")
    with pytest.raises(TransitionError):
        check_clip("pending_review", "scheduled", "worker")
    with pytest.raises(TransitionError):
        check_clip("qa_passed", "published", "worker")
    check_clip("approved", "scheduled", "worker")
    check_clip("pending_review", "approved", "human")
