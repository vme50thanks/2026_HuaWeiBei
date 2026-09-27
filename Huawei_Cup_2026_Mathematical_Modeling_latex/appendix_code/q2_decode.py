def decode(state, full=False):
    ur = {g: [(0, u) for u in pr.units if pr.units[u] == g] for g in 'ABC'}
    br = {g: [(0, b) for b, _ in pr.batts[g]] for g in 'ABC'}
    D = E = C = 0
    plan = []
    for g, ids in state:
        ut, u = min(ur[g])
        bt, b = min(br[g])
        start = max(ut, bt)
        opts = []
        for dur, en, chg, hard, due, route in profiles(g, ids):
            if start > hard + 1e-08:
                continue
            delay = sum((w * max(0, start + off) for off, w in due))
            opts.append((delay, dur, en, chg, route))
        if not opts:
            return None
        delay, dur, en, chg, route = min(opts)
        finish = start + dur
        D += delay
        E += en
        C = max(C, finish)
        ur[g].remove((ut, u))
        ur[g].append((finish, u))
        br[g].remove((bt, b))
        br[g].append((finish + chg, b))
        if full:
            p = pr.evaluate(g, ids, route, start)
            assert p is not None
            p.update(unit=u, battery=b, sortie=f'P{len(plan) + 1:03d}', charge_start=p['finish'], battery_ready=p['finish'] + chg)
            plan.append(p)
    return plan if full else (D, C, E, len(state))
