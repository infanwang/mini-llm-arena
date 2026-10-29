def assign_tied_groups(model_ids, beta_hat, rank_ci_lower, rank_ci_upper):
    order = sorted(range(len(model_ids)), key=lambda i: -beta_hat[i])
    groups, current = [], [order[0]]
    for i in order[1:]:
        prev = current[-1]
        if rank_ci_lower[i] <= rank_ci_upper[prev]:
            current.append(i)
        else:
            groups.append(current)
            current = [i]
    groups.append(current)
    return [
        {"group_rank": g + 1, "models": [model_ids[i] for i in group]}
        for g, group in enumerate(groups)
    ]
