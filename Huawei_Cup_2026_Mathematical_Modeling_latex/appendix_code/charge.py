def charge(self, g, soc):
    full = self.batts[g][0][1]
    return full * (0.65 * (0.9 - soc) / 0.9 + 0.35) if soc < 0.9 else full * 0.35 * (1 - soc) / 0.1
