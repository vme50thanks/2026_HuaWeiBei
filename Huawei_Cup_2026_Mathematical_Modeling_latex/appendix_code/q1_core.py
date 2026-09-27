def energy(site, g, q):
    m = models[g]
    go = legs['O01', site]
    back = legs[site, 'O01']
    L = m['L0'] - (m['L0'] - m['LF']) * (q / m['Q']) ** 1.5
    eh = m['Eu'] * float(go['horizontal_distance_m']) / L
    eu = (m['m0'] + q) * 9.80665 * float(go['climb_m']) / (m['eta'] * 3600000.0)
    rh = m['Eu'] * float(back['horizontal_distance_m']) / m['L0']
    ru = m['m0'] * 9.80665 * float(back['climb_m']) / (m['eta'] * 3600000.0)
    return eh + eu + rh + ru

def solve_site(s, rho, order):
    pp = [p for p in patterns[s] if p['soc'] >= rho]

    @lru_cache(None)
    def dp(rem):
        if not any(rem):
            return ((0, Decimal(0), Decimal(0)), ())
        anchor = next((k for k, n in enumerate(rem) if n))
        best = None
        for ix, p in enumerate(pp):
            v = p['vector']
            if not v[anchor] or any((a > b for a, b in zip(v, rem))):
                continue
            sub = dp(tuple((b - a for a, b in zip(v, rem))))
            if sub is None:
                continue
            c = sub[0]
            cost = (c[0] + 1, c[1] + Decimal(str(p['E'])), c[2] + Decimal(str(p['T'])))
            key = tuple((cost[k] for k in order))
            if best is None or key < best[0]:
                best = (key, cost, (ix,) + sub[1])
        return None if best is None else (best[1], best[2])
    ans = dp(states[s])
    missing = [bid for k, idlist in enumerate(groups[s][1]) for bid in idlist if not any((p['vector'][k] > 0 for p in pp))]
    return (None if ans is None else [pp[i] for i in ans[1]], dp.cache_info().currsize, len(pp), missing)
