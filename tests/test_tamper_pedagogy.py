# tests/test_tamper_pedagogy.py

from cryptix_academy.models import LearningProgress
from cryptix_academy.sandbox import (
    TamperLabSandbox,
    NoOpExperiment,
    CiphertextTamperExperiment,
    MetadataTamperExperiment,
    VersionTamperExperiment,
    AlgorithmTamperExperiment,
    TruncationExperiment,
    TagTamperExperiment,
)
from cryptix_academy.tamper_pedagogy import (
    TAMPER_CHALLENGES,
    TamperChallengeSession,
    get_challenge_for_experiment,
    validate_pedagogy,
    apply_challenge_outcome,
    XP_CORRECT_PREDICTION,
    XP_FULL_MATCH,
    XP_PARTIAL_MATCH,
)


def _full_correct_session(challenge):
    session = TamperChallengeSession(challenge)
    assert session.record_prediction(challenge.prediction_correct) is True
    assert session.record_experiment_run() is True
    selections = [item.correct for item in challenge.matching_items]
    assert session.submit_matching(selections) is True
    return session


def test_pedagogy_structural_validation():
    problems = validate_pedagogy()
    assert problems == [], f"Pedagogy validation problems: {problems}"


def test_every_experiment_has_a_challenge():
    experiments = [
        NoOpExperiment(),
        CiphertextTamperExperiment(),
        MetadataTamperExperiment(),
        VersionTamperExperiment(),
        AlgorithmTamperExperiment(),
        TruncationExperiment(),
        TagTamperExperiment(),
    ]
    for exp in experiments:
        challenge = get_challenge_for_experiment(exp.name)
        assert challenge is not None, f"No challenge for experiment '{exp.name}'"
    assert len(TAMPER_CHALLENGES) == 7


def test_state_machine_gating():
    challenge = get_challenge_for_experiment("Ciphertext Mutation")
    session = TamperChallengeSession(challenge)

    # Cannot run the experiment before predicting
    assert session.record_experiment_run() is False
    # Cannot submit matching before the experiment ran
    assert session.submit_matching([0, 0, 0]) is False
    # Verdicts are hidden before reveal
    assert session.prediction_verdict is None
    assert session.matching_results is None
    assert session.xp_earned is None
    assert session.explanation is None

    # Prediction is single-shot
    assert session.record_prediction(0) is True
    assert session.record_prediction(1) is False  # no re-recording
    assert session.record_experiment_run() is True  # first run is allowed
    assert session.record_experiment_run() is False  # cannot 'run' twice

    # Matching only after the experiment
    assert session.submit_matching([0, 0]) is False  # wrong arity
    assert session.submit_matching([0, 0, 0]) is True

    # Everything exposed after reveal
    assert session.state == TamperChallengeSession.STATE_REVEALED
    assert session.prediction_verdict is False  # option 0 was deliberately wrong for this challenge
    assert session.matching_results == [False, True, True]  # layer item (correct=2) was answered 0
    assert session.explanation is not None

    # Reset returns to a pristine prediction state
    session.reset()
    assert session.state == TamperChallengeSession.STATE_PREDICTION
    assert session.prediction_verdict is None


def test_invalid_inputs_are_rejected():
    challenge = get_challenge_for_experiment("Container Truncation")
    session = TamperChallengeSession(challenge)

    assert session.record_prediction(-1) is False
    assert session.record_prediction(4) is False
    assert session.record_prediction("2") is False
    assert session.state == TamperChallengeSession.STATE_PREDICTION  # unchanged

    assert session.record_prediction(2) is True
    assert session.record_experiment_run() is True
    assert session.submit_matching([0, 0, 9]) is False  # out-of-range match
    assert session.submit_matching([0, 0, "1"]) is False  # non-int match
    assert session.state == TamperChallengeSession.STATE_MATCHING  # unchanged


def test_xp_award_rules():
    # Full success: correct prediction + 3/3 matching
    challenge = get_challenge_for_experiment("Ciphertext Mutation")
    session = _full_correct_session(challenge)
    assert session.xp_earned == XP_CORRECT_PREDICTION + XP_FULL_MATCH

    # Wrong prediction + 3/3 matching
    session = TamperChallengeSession(challenge)
    wrong = (challenge.prediction_correct + 1) % 4
    session.record_prediction(wrong)
    session.record_experiment_run()
    session.submit_matching([item.correct for item in challenge.matching_items])
    assert session.xp_earned == XP_FULL_MATCH

    # Wrong prediction + exactly 2/3 matching
    session = TamperChallengeSession(challenge)
    session.record_prediction(wrong)
    session.record_experiment_run()
    selections = [item.correct for item in challenge.matching_items]
    selections[0] = (selections[0] + 1) % len(challenge.matching_items[0].options)
    session.submit_matching(selections)
    assert session.xp_earned == XP_PARTIAL_MATCH

    # Correct prediction + 0-1/3 matching: prediction XP only
    session = TamperChallengeSession(challenge)
    session.record_prediction(challenge.prediction_correct)
    session.record_experiment_run()
    session.submit_matching([1, 1, 1])  # every match wrong (correct index is 2/0 layouts)
    assert session.xp_earned in (0, XP_CORRECT_PREDICTION)
    if all(item.correct == 1 for item in challenge.matching_items) is False:
        assert session.xp_earned == XP_CORRECT_PREDICTION


def test_reality_cross_validation():
    """
    The pedagogy must teach what the real engine actually does:
    every challenge's canonical layer is compared against the live
    VerificationTrace produced by the real sandbox.
    """
    sandbox = TamperLabSandbox()

    experiments = [
        NoOpExperiment(),
        CiphertextTamperExperiment(),
        MetadataTamperExperiment(),
        VersionTamperExperiment(),
        AlgorithmTamperExperiment(),
        TruncationExperiment(),
        TagTamperExperiment(),
    ]

    for exp in experiments:
        challenge = get_challenge_for_experiment(exp.name)
        assert challenge is not None

        _, trace = sandbox.run_experiment(exp)

        if exp.is_control_group:
            assert trace.success is True
            assert trace.rejection_layer == "NONE"
        else:
            assert trace.success is False, f"{exp.name}: attack must not succeed"

        assert trace.rejection_layer == challenge.canonical_rejection_layer, (
            f"{exp.name}: pedagogy teaches '{challenge.canonical_rejection_layer}' "
            f"but engine reality is '{trace.rejection_layer}'"
        )


def test_progress_outcome_application():
    challenge = get_challenge_for_experiment("Format Version Mutation")

    # Pre-existing progress must be preserved (never overwritten wholesale)
    progress = LearningProgress()
    progress.xp = 120
    progress.completed_lessons = ["crypto_fundamentals"]
    progress.completed_challenges["q_legacy_1"] = {"attempts": 1, "hints_used": 0, "xp": 10, "first_attempt": True}

    session = _full_correct_session(challenge)
    awarded = apply_challenge_outcome(progress, session)
    assert awarded == XP_CORRECT_PREDICTION + XP_FULL_MATCH
    assert progress.xp == 120 + awarded
    assert "tamper_version" in progress.completed_challenges
    assert "q_legacy_1" in progress.completed_challenges  # preserved
    assert progress.completed_lessons == ["crypto_fundamentals"]  # preserved
    assert progress.total_attempts == 1
    assert progress.first_attempt_successes == 1

    # Re-completion awards zero XP and does not duplicate the entry
    session2 = _full_correct_session(challenge)
    assert apply_challenge_outcome(progress, session2) == 0
    assert progress.xp == 120 + awarded  # unchanged

    # Unrevealed sessions can never touch progress
    fresh = TamperChallengeSession(challenge)
    fresh.record_prediction(0)
    assert apply_challenge_outcome(progress, fresh) == 0
    assert progress.total_attempts == 1  # unchanged
