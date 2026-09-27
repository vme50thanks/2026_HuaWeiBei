def decode(state, end, full=False):
    late = end + c[1]['back'] + 300 + c[2]['earliest_service'] + 10
    ur = {g: [(0, u) for u in pr.units if pr.units[u] == g] for g in 'ABC'}
    br = {g: [(0, b) for b, _ in pr.batts[g]] for g in 'ABC'}
    finishmax = energy = totalfinish = 0
    plan = []
    for g, ids in state:
        ut, u = min(ur[g])
        bt, b = min(br[g])
        earliest = max(ut, bt)
        opts = []
        for p, first, emin, emax, lmin, both, hard in profile(g, ids):
            start = max(earliest, c[0]['earliest_service'] + 6 - first, c[1]['earliest_service'] + 6 - emin, late + 6 - lmin, 0)
            upper = min(hard, end - 6 - emax)
            for _ in range(5):
                bad = [t for t in both if not (c[1]['earliest_service'] + 6 <= start + t <= end - 6 or start + t >= late + 6)]
                if not bad:
                    break
                start = max(start, late + 6 - min(bad))
            else:
                continue
            if start > upper + 1e-08:
                continue
            opts.append((start + p['finish'], p['energy'], start, p))
        if not opts:
            return None
        finish, en, start, p = min(opts, key=lambda x: x[:2])
        ready = finish + pr.charge(g, p['soc'])
        ur[g].remove((ut, u))
        ur[g].append((finish, u))
        br[g].remove((bt, b))
        br[g].append((ready, b))
        finishmax = max(finishmax, finish)
        energy += en
        totalfinish += finish
        if full:
            q = pr.evaluate(g, ids, p['route'], start)
            q.update(unit=u, battery=b, sortie=f'P{len(plan) + 1:03d}', charge_start=q['finish'], battery_ready=q['finish'] + pr.charge(g, q['soc']))
            plan.append(q)
    return plan if full else (finishmax, energy, totalfinish)
