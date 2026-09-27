def margin(self, a, b, typ, method='cells', spacing=5):
    distance = float(np.linalg.norm(a - b))
    free = 32.45 + 20 * math.log10(self.f) + 20 * math.log10(max(distance / 1000, 1e-09))
    limit = self.threshold[typ]
    if free + self.obs <= limit:
        return (limit - free - self.obs, True)
    if free > limit:
        return (limit - free, False)
    if method == 'sample':
        n = max(1, math.ceil(float(np.linalg.norm((a - b)[:2])) / spacing))
        ts = np.linspace(0, 1, n + 1)
        x0, y0 = self.grid(a)
        x1, y1 = self.grid(b)
        cs = np.floor(x0 + (x1 - x0) * ts).astype(int)
        rs = np.floor(y0 + (y1 - y0) * ts).astype(int)
        blocked = bool(np.any(self.dem[rs, cs] >= a[2] + (b[2] - a[2]) * ts - 1e-09))
    else:
        t, rs, cs = self.ray_cells(a, b)
        z = a[2] + (b[2] - a[2]) * t
        blocked = bool(np.any(self.dem[rs, cs] >= np.minimum(z[:-1], z[1:]) - 1e-09))
        x0, y0 = self.grid(a)
        x1, y1 = self.grid(b)
        xx = x0 + (x1 - x0) * t
        yy = y0 + (y1 - y0) * t
        for dc, dr in [(1e-08, 1e-08), (-1e-08, 1e-08), (1e-08, -1e-08), (-1e-08, -1e-08)]:
            cc = np.floor(xx + dc).astype(int)
            rr = np.floor(yy + dr).astype(int)
            blocked = blocked or bool(np.any(self.dem[rr, cc] >= z - 1e-09))
    return (limit - free - (self.obs if blocked else 0), False)
