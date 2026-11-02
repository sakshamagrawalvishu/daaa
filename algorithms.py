"""DAA algorithms used by the waste collection optimizer."""
from math import radians, sin, cos, sqrt, atan2
import heapq


def haversine(a, b):
    """Approximate road-independent distance in kilometres."""
    r = 6371.0
    lat1, lon1 = radians(a['lat']), radians(a['lon'])
    lat2, lon2 = radians(b['lat']), radians(b['lon'])
    dlat, dlon = lat2-lat1, lon2-lon1
    h = sin(dlat/2)**2 + cos(lat1)*cos(lat2)*sin(dlon/2)**2
    return 2*r*atan2(sqrt(h), sqrt(1-h))


def priority_score(bin_row):
    """Greedy score: urgency, waste quantity and a small overflow bonus."""
    return bin_row['priority'] * 20 + bin_row['waste_kg'] * 0.35


def greedy_rank(bins):
    """Sort bins by priority score (O(n log n))."""
    return sorted(bins, key=priority_score, reverse=True)


def knapsack_select(items, capacity):
    """0/1 DP knapsack. Capacity and weights are discretized to whole kg.
    Returns selected item IDs and maximum total priority value.
    Time O(n*C), space O(n*C).
    """
    cap = max(0, int(capacity))
    weights = [max(1, int(round(x['waste_kg']))) for x in items]
    values = [max(1, int(round(priority_score(x)))) for x in items]
    n = len(items)
    dp = [[0]*(cap+1) for _ in range(n+1)]
    for i in range(1, n+1):
        w, v = weights[i-1], values[i-1]
        for c in range(cap+1):
            dp[i][c] = dp[i-1][c]
            if w <= c:
                dp[i][c] = max(dp[i][c], v + dp[i-1][c-w])
    chosen, c = [], cap
    for i in range(n, 0, -1):
        if dp[i][c] != dp[i-1][c]:
            chosen.append(items[i-1])
            c -= weights[i-1]
    return chosen, dp[n][cap]


def dijkstra(graph, source):
    """Single-source shortest paths. O((V+E) log V) with a heap."""
    dist = {node: float('inf') for node in graph}
    prev = {node: None for node in graph}
    dist[source] = 0
    pq = [(0, source)]
    while pq:
        d, u = heapq.heappop(pq)
        if d != dist[u]:
            continue
        for v, weight in graph[u]:
            nd = d + weight
            if nd < dist[v]:
                dist[v], prev[v] = nd, u
                heapq.heappush(pq, (nd, v))
    return dist, prev


def build_graph(points):
    """Build a complete weighted graph from supplied coordinates.
    For a production deployment, replace this with a road-network graph.
    """
    graph = {p['id']: [] for p in points}
    for i, a in enumerate(points):
        for b in points[i+1:]:
            d = haversine(a, b)
            graph[a['id']].append((b['id'], d))
            graph[b['id']].append((a['id'], d))
    return graph


def route_distance(route, point_by_id):
    return sum(haversine(point_by_id[a], point_by_id[b]) for a,b in zip(route, route[1:]))


def nearest_neighbour_route(start, selected, point_by_id):
    """Construct a route greedily by repeatedly visiting nearest unvisited point."""
    remaining = {x['id'] for x in selected}
    route, current = [start['id']], start['id']
    while remaining:
        nxt = min(remaining, key=lambda x: haversine(point_by_id[current], point_by_id[x]))
        route.append(nxt)
        remaining.remove(nxt)
        current = nxt
    route.append(start['id'])
    return route


def two_opt(route, point_by_id):
    """Improve a route by reversing segments; worst-case O(n^3) simple implementation."""
    best = route[:]
    improved = True
    while improved:
        improved = False
        for i in range(1, len(best)-2):
            for j in range(i+1, len(best)-1):
                candidate = best[:i] + best[i:j+1][::-1] + best[j+1:]
                if route_distance(candidate, point_by_id) + 1e-9 < route_distance(best, point_by_id):
                    best, improved = candidate, True
    return best
