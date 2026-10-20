"""
INFLUENZIA - preprocessing pipeline
===================================
Raw data  ->  data tables  ->  graph metrics  ->  compact JSON for the browser.

Dataset: MUSAE Twitch social networks (Rozemberczki, Allen & Sarkar, 2019,
"Multi-scale Attributed Node Embedding", Journal of Complex Networks).
  * Vertices: Twitch streamers (one network per broadcast language/region)
  * Edges:    mutual follower relationships between two streamers (undirected)
  * Attributes: views, partner (Twitch Partner = verified, monetised creator),
                mature (explicit-content flag), days (account age)

Usage:
    pip install networkx pandas numpy
    python preprocess.py                # all regions
    python preprocess.py ENGB PTBR      # selected regions

Output: data/influenzia_data.js  (a single `window.INFLUENZIA_DATA = {...}`
        file so the app also opens straight from disk, no web server needed)
        data/<REGION>.json           (same content, one file per region)
"""
import json
import math
import sys
from collections import Counter, defaultdict
from pathlib import Path

import networkx as nx
import numpy as np
import pandas as pd

RAW = Path(__file__).parent / "data" / "raw"
OUT = Path(__file__).parent / "data"
REGIONS = {
    "ENGB": "English",
    "DE": "German",
    "FR": "French",
    "ES": "Spanish",
    "RU": "Russian",
    "PTBR": "Portuguese (Brazil)",
    "ZHTW": "Chinese (Taiwan)",
}
TOP_K = 1200          # nodes (by PageRank) shipped with edges + layout
MAX_GROUPS = 9        # 8 coloured communities (validated palette) + "Other"
SEED = 42


def r(x, d=4):
    return None if x is None or (isinstance(x, float) and math.isnan(x)) else round(float(x), d)


def load(region):
    tgt = pd.read_csv(RAW / f"{region}_target.csv")
    edges = pd.read_csv(RAW / f"{region}_edges.csv")
    tgt = tgt.sort_values("new_id").reset_index(drop=True)
    G = nx.Graph()
    for row in tgt.itertuples():
        G.add_node(int(row.new_id), twitch_id=int(row.id), days=int(row.days),
                   mature=bool(row.mature), views=int(row.views), partner=bool(row.partner))
    raw_edges = len(edges)
    for a, b in edges[["from", "to"]].itertuples(index=False):
        if a != b:
            G.add_edge(int(a), int(b))
    self_loops = int((edges["from"] == edges["to"]).sum())
    return G, raw_edges, self_loops


def graph_properties(G, partition, self_loops, raw_edges):
    n, m = G.number_of_nodes(), G.number_of_edges()
    degs = np.array([d for _, d in G.degree()])
    comps = sorted(nx.connected_components(G), key=len, reverse=True)
    giant = G.subgraph(comps[0])
    # Average shortest path estimated from 300 BFS sources on the giant component
    rng = np.random.default_rng(SEED)
    src = rng.choice(list(giant.nodes()), size=min(300, giant.number_of_nodes()), replace=False)
    tot, cnt, ecc_max = 0, 0, 0
    for s in src:
        L = nx.single_source_shortest_path_length(giant, s)
        tot += sum(L.values()); cnt += len(L) - 1; ecc_max = max(ecc_max, max(L.values()))
    diam = nx.approximation.diameter(giant, seed=SEED)
    partner_attr = {v: int(G.nodes[v]["partner"]) for v in G}
    nx.set_node_attributes(G, partner_attr, "p_int")
    return {
        "vertices": n,
        "edges": m,
        "raw_edge_rows": raw_edges,
        "self_loops_removed": self_loops,
        "finite": True,
        "directed": False,
        "simple": True,
        "density": r(nx.density(G), 6),
        "avg_degree": r(degs.mean(), 2),
        "median_degree": int(np.median(degs)),
        "max_degree": int(degs.max()),
        "min_degree": int(degs.min()),
        "isolated": int((degs == 0).sum()),
        "pendant": int((degs == 1).sum()),
        "components": len(comps),
        "giant_size": len(comps[0]),
        "giant_share": r(len(comps[0]) / n, 4),
        "connected": len(comps) == 1,
        "avg_clustering": r(nx.average_clustering(G), 4),
        "transitivity": r(nx.transitivity(G), 4),
        "degree_assortativity": r(nx.degree_assortativity_coefficient(G), 4),
        "partner_assortativity": r(nx.attribute_assortativity_coefficient(G, "partner"), 4),
        "mature_assortativity": r(nx.attribute_assortativity_coefficient(G, "mature"), 4),
        "diameter_lower_bound": int(diam),
        "avg_shortest_path_est": r(tot / cnt, 3),
        "modularity": r(nx.community.modularity(G, partition), 4),
        "communities_found": len(partition),
        "max_core": int(max(nx.core_number(G).values())),
        "partner_share": r(np.mean([G.nodes[v]["partner"] for v in G]), 4),
        "mature_share": r(np.mean([G.nodes[v]["mature"] for v in G]), 4),
    }


def process(region):
    print(f"[{region}] loading", flush=True)
    G, raw_edges, self_loops = load(region)
    n = G.number_of_nodes()

    # ---- communities (Louvain, fixed seed for reproducibility) ----
    partition = nx.community.louvain_communities(G, seed=SEED, resolution=1.0)
    partition = sorted(partition, key=len, reverse=True)
    props = graph_properties(G, partition, self_loops, raw_edges)
    print(f"[{region}] n={n} m={G.number_of_edges()} communities={len(partition)}", flush=True)

    # Level-of-detail: the largest communities keep their own colour; communities that are
    # tiny (< 1% of nodes) or beyond the colour budget are aggregated into one "Other" group.
    min_size = max(10, int(0.01 * n))
    big = [c for c in partition if len(c) >= min_size][:MAX_GROUPS - 1]
    rest = [c for c in partition if not any(c is b for b in big)]
    comm_of = {}
    for ci, c in enumerate(big):
        for v in c:
            comm_of[v] = ci
    for c in rest:
        for v in c:
            comm_of[v] = len(big)
    n_groups = len(big) + (1 if rest else 0)
    n_rest = len(rest)

    # ---- node metrics ----
    deg = dict(G.degree())
    pr = nx.pagerank(G, alpha=0.85)
    k = min(600, n)
    btw = nx.betweenness_centrality(G, k=k, seed=SEED, normalized=True)
    clus = nx.clustering(G)
    core = nx.core_number(G)
    # participation: share of a node's ties that leave its own community
    part = {}
    for v in G:
        d = deg[v]
        part[v] = 0.0 if d == 0 else sum(comm_of[u] != comm_of[v] for u in G[v]) / d

    views = np.array([G.nodes[v]["views"] for v in range(n)])
    pr_arr = np.array([pr[v] for v in range(n)])
    pr_pct = pd.Series(pr_arr).rank(pct=True).values
    views_pct = pd.Series(views).rank(pct=True).values
    btw_pct = pd.Series([btw[v] for v in range(n)]).rank(pct=True).values
    deg_pct = pd.Series([deg[v] for v in range(n)]).rank(pct=True).values

    # Influence score = mean of network position (PageRank) and audience reach (views) percentiles
    influence = 0.5 * pr_pct + 0.5 * views_pct

    # roles (hidden patterns)
    role = {}
    for v in range(n):
        if pr_pct[v] >= 0.97 and views_pct[v] >= 0.9:
            role[v] = "Hub"                 # central AND large audience
        elif pr_pct[v] >= 0.85 and views_pct[v] < 0.5:
            role[v] = "Hidden gem"          # well-connected among creators, small audience
        elif btw_pct[v] >= 0.9 and part[v] >= 0.5 and deg[v] >= 5:
            role[v] = "Bridge"              # mostly links outside own community
        elif views_pct[v] >= 0.95 and pr_pct[v] < 0.5:
            role[v] = "Lone star"           # big audience, weakly embedded in creator network
        else:
            role[v] = ""
    ROLE_CODES = ["", "Hub", "Hidden gem", "Bridge", "Lone star"]

    # ---- community summaries ----
    groups = []
    members = defaultdict(list)
    for v in range(n):
        members[comm_of[v]].append(v)
    for g in range(n_groups):
        mem = members[g]
        sub = G.subgraph(mem)
        top = sorted(mem, key=lambda v: -pr[v])[:5]
        groups.append({
            "id": g,
            "label": f"C{g+1}" if g < len(big) else "Other",
            "size": len(mem),
            "internal_edges": sub.number_of_edges(),
            "density": r(nx.density(sub), 5) if len(mem) > 1 else 0,
            "partner_share": r(np.mean([G.nodes[v]["partner"] for v in mem]), 3),
            "mature_share": r(np.mean([G.nodes[v]["mature"] for v in mem]), 3),
            "median_views": int(np.median([G.nodes[v]["views"] for v in mem])),
            "total_views": int(np.sum([G.nodes[v]["views"] for v in mem])),
            "median_days": int(np.median([G.nodes[v]["days"] for v in mem])),
            "avg_degree": r(np.mean([deg[v] for v in mem]), 2),
            "top": top,
            "subcommunities": n_rest if g == len(big) else 1,
        })
    meta = Counter()
    for a, b in G.edges():
        ga, gb = comm_of[a], comm_of[b]
        if ga != gb:
            meta[tuple(sorted((ga, gb)))] += 1
    meta_edges = [[a, b, c] for (a, b), c in sorted(meta.items())]

    # ---- degree distribution ----
    dd = Counter(deg.values())
    degree_dist = sorted([[int(d), int(c)] for d, c in dd.items()])

    # ---- top-K subgraph + precomputed layout ----
    topk = sorted(range(n), key=lambda v: -pr[v])[:min(TOP_K, n)]
    topset = set(topk)
    H = G.subgraph(topk).copy()
    print(f"[{region}] layout on {H.number_of_nodes()} nodes / {H.number_of_edges()} edges", flush=True)
    try:
        pos = nx.forceatlas2_layout(H, max_iter=300, seed=SEED, scaling_ratio=2.0, gravity=1.0,
                                    dissuade_hubs=True)
    except Exception:
        pos = nx.spring_layout(H, seed=SEED, iterations=200)
    xs = np.array([p[0] for p in pos.values()]); ys = np.array([p[1] for p in pos.values()])
    cx, cy = np.median(xs), np.median(ys)
    sc = np.percentile(np.abs(np.concatenate([xs - cx, ys - cy])), 98) or 1
    layout = {v: ((pos[v][0] - cx) / sc, (pos[v][1] - cy) / sc) for v in H}

    # ---- compact node table ----
    NODE_FIELDS = ["id", "twitch_id", "views", "partner", "mature", "days", "degree", "pagerank",
                   "pr_pct", "views_pct", "betweenness", "clustering", "core", "participation",
                   "group", "influence", "role", "x", "y"]
    nodes = []
    for v in range(n):
        a = G.nodes[v]
        x, y = layout.get(v, (None, None))
        nodes.append([v, a["twitch_id"], a["views"], int(a["partner"]), int(a["mature"]), a["days"],
                      deg[v], r(pr[v] * n, 4),  # PageRank scaled by n (1.0 = average)
                      r(pr_pct[v], 4), r(views_pct[v], 4), r(btw[v], 6), r(clus[v], 3), core[v],
                      r(part[v], 3), comm_of[v], r(influence[v], 4), ROLE_CODES.index(role[v]),
                      r(x, 3), r(y, 3)])
    edges = [[a, b] for a, b in H.edges()]

    role_counts = Counter(role.values())
    insights = build_insights(G, props, groups, nodes, NODE_FIELDS, role_counts, pr, part, comm_of, n)

    return {
        "region": region,
        "language": REGIONS[region],
        "properties": props,
        "node_fields": NODE_FIELDS,
        "nodes": nodes,
        "edges": edges,
        "top_k": len(topk),
        "groups": groups,
        "meta_edges": meta_edges,
        "degree_dist": degree_dist,
        "role_codes": ROLE_CODES,
        "role_counts": {k: v for k, v in role_counts.items() if k},
        "insights": insights,
    }


def build_insights(G, P, groups, nodes, F, role_counts, pr, part, comm_of, n):
    ins = []
    ins.append(f"{P['vertices']:,} streamers share {P['edges']:,} mutual follows — density {P['density']:.4f}: "
               f"only ~{P['density']*100:.2f}% of possible pairs are connected (a sparse network).")
    ins.append(f"Small world: any two streamers in the giant component are on average "
               f"{P['avg_shortest_path_est']} hops apart (diameter ≥ {P['diameter_lower_bound']}).")
    # heavy tail
    degs = sorted([row[F.index('degree')] for row in nodes], reverse=True)
    top1 = max(1, n // 100)
    share = sum(degs[:top1]) / max(1, sum(degs))
    ins.append(f"Heavy-tailed degree: the top 1% of streamers hold {share*100:.0f}% of all tie endpoints "
               f"(max degree {P['max_degree']} vs median {P['median_degree']}).")
    pa = P["partner_assortativity"]
    if pa is not None:
        word = "prefer to connect with other Partners" if pa > 0.02 else ("mix freely across Partner status" if pa > -0.02 else "connect across Partner status more than within it")
        ins.append(f"Partner assortativity = {pa:+.3f}: verified Partners {word}.")
    da = P["degree_assortativity"]
    ins.append(f"Degree assortativity = {da:+.3f}: " + ("big hubs tend to link with small creators (hub-and-spoke / mentoring pattern)." if da < -0.05 else "creators link with others of similar connectedness." if da > 0.05 else "no strong preference between hubs and small creators."))
    big = groups[0]
    ins.append(f"Louvain found {P['communities_found']} communities (modularity {P['modularity']:.2f}); "
               f"the largest, {big['label']}, holds {big['size']/n*100:.0f}% of streamers.")
    real = [g for g in groups if g["label"] != "Other" and g["size"] >= 0.03 * n] or groups
    gp = sorted(real, key=lambda g: -g["partner_share"])[0]
    ins.append(f"{gp['label']} is the most 'professional' community: {gp['partner_share']*100:.0f}% Partners vs "
               f"{P['partner_share']*100:.0f}% overall.")
    gm = sorted(real, key=lambda g: -g["mature_share"])[0]
    ins.append(f"{gm['label']} has the highest share of mature-content streamers ({gm['mature_share']*100:.0f}% vs "
               f"{P['mature_share']*100:.0f}% overall) — content style clusters in the network.")
    if role_counts.get("Hidden gem"):
        ins.append(f"{role_counts['Hidden gem']} 'hidden gems' sit in the top 15% by network centrality yet below median views — "
                   f"well-connected creators the audience hasn't found yet.")
    if role_counts.get("Bridge"):
        ins.append(f"{role_counts['Bridge']} 'bridges' have most of their ties outside their own community — "
                   f"natural brokers for cross-community collaborations.")
    return ins


def main():
    regions = [a.upper() for a in sys.argv[1:]] or list(REGIONS)
    out = {}
    for reg in regions:
        d = process(reg)
        (OUT / f"{reg}.json").write_text(json.dumps(d, separators=(",", ":")))
        out[reg] = d
    # merge with already-built regions so partial runs don't drop data
    for reg in REGIONS:
        if reg not in out and (OUT / f"{reg}.json").exists():
            out[reg] = json.loads((OUT / f"{reg}.json").read_text())
    ordered = {k: out[k] for k in REGIONS if k in out}
    (OUT / "influenzia_data.js").write_text("window.INFLUENZIA_DATA=" + json.dumps(ordered, separators=(",", ":")) + ";")
    print("wrote", OUT / "influenzia_data.js", f"{(OUT / 'influenzia_data.js').stat().st_size/1e6:.1f} MB")


if __name__ == "__main__":
    main()
