def components(sites, edges):
    parent = {s: s for s in sites}

    def find(x):
        while parent[x] != x:
            x = parent[x]
        return x
    for edge in edges:
        for x in edge[1:]:
            parent[find(x)] = find(edge[0])
    groups = defaultdict(list)
    for s in sites:
        groups[find(s)].append(s)
    return sorted([sorted(v) for v in groups.values()])

def color(tasks, prefix):
    active = []
    free = []
    n = 0
    ans = []
    for t in sorted(tasks, key=lambda x: (x['start'], x['end'], x['task'])):
        while active and active[0][0] <= t['start']:
            _, i = heapq.heappop(active)
            heapq.heappush(free, i)
        if free:
            i = heapq.heappop(free)
        else:
            n += 1
            i = n
        heapq.heappush(active, (t['end'], i))
        ans.append(dict(t, resource=f'{prefix}-{i:02d}'))
    return (n, ans)
