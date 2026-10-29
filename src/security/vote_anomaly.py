import numpy as np


def detect_model_bias(votes_for_model: int, total_votes: int, min_total: int = 5):
    if total_votes < min_total:
        return False, 0.0
    ratio = votes_for_model / total_votes
    return ratio > 0.8, ratio


def detect_coordinated_voting(recent_votes, model_id, window: int = 200,
                               min_users: int = 5, min_consistency: float = 0.7):
    user_choices: dict[str, list[int]] = {}
    for v in recent_votes[:window]:
        if v.model_a == model_id:
            user_choices.setdefault(v.voter_id, []).append(1 if v.winner == "A" else 0)
        elif v.model_b == model_id:
            user_choices.setdefault(v.voter_id, []).append(1 if v.winner == "B" else 0)

    suspects = [uid for uid, c in user_choices.items()
                if len(c) >= 3 and float(np.mean(c)) >= min_consistency]
    if len(suspects) >= min_users:
        return True, len(suspects), sum(len(user_choices[u]) for u in suspects), suspects
    return False, 0, 0, []
