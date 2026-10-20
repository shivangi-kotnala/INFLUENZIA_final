# INFLUENZIA: Design Report

**Course:** DSE3150 Graph Visualization  
**Theme:** Social / collaboration networks  
**Data structure:** an undirected attributed graph, with communities as groups

INFLUENZIA is an interactive visualization of social connections between Twitch creators. It is built to find influential creators, the communities they form, and patterns in the network that are hard to see otherwise. This report follows the five components in the project guidelines. Unless stated otherwise, the figures come from the **English (ENGB)** network, which the app opens by default.

---

## 1. Foundations and problem framing

### Dataset

The data is the MUSAE Twitch social networks dataset (Rozemberczki, Allen & Sarkar, *Journal of Complex Networks*, 2021), collected from the public Twitch API in May 2018. There are seven networks, one for each broadcast language. Two streamers are linked when they follow each other. Each streamer has four attributes:

- **views**: total channel views
- **partner**: whether the streamer is a Twitch Partner, Twitch's verified and monetised creator tier
- **mature**: the explicit-content flag
- **days**: account age in days

Mutual follows between creators are a reasonable proxy for collaboration. Creators who follow each other tend to raid, host and co-stream together.

### Questions the visualization answers

| # | Question | Answered by |
|---|---|---|
| Q1 | Who is influential, and is influence among creators the same as audience size? | PageRank vs views scatter plot, size encoding, influence ranking |
| Q2 | Which communities exist, and how do they differ? | Communities view, community regions, community profile table |
| Q3 | Who connects communities? | Betweenness and participation, the Bridge role, ego-network highlighting |
| Q4 | Which hidden patterns exist? | Roles (hidden gem, lone star), assortativity, degree distribution, matrix blocks |

### Formal graph description (ENGB)

Let G = (V, E), where V is the set of streamers and E is the set of unordered pairs {u, v} of streamers who follow each other.

| Property | Value | Meaning |
|---|---:|---|
| \|V\| | 7,126 | Finite vertex set |
| \|E\| | 35,324 | Finite edge set |
| Type | Simple, undirected | No self-loops (0 removed) and no multi-edges |
| Density 2\|E\| / (\|V\|(\|V\|−1)) | 0.00139 | Very sparse: about 0.14% of possible pairs are linked |
| Degree: min / median / mean / max | 1 / 5 / 9.91 / 720 | Heavy-tailed. Mean is about 2 × median. |
| Isolated vertices (deg 0) | 0 | — |
| Pendant vertices (deg 1) | 1,161 | 16% of creators hang off a single tie |
| Connected components | 1 | G is connected; the giant component covers 100% |
| Average path length (est., 300 BFS sources) | 3.67 | Small world |
| Diameter (lower bound) | 10 | — |
| Average clustering / transitivity | 0.131 / 0.042 | Local triangles are far more common than in a random graph of this density |
| Degree assortativity | −0.122 | Disassortative: hubs link to small creators |
| Partner assortativity | −0.141 | Partners tend to link with non-Partners |
| Mature assortativity | +0.085 | Mild homophily by content rating |
| Max k-core | 14 | — |
| Louvain communities / modularity Q | 16 / 0.457 | Strong community structure |

The other six networks are computed the same way and shown live in the detail panel when you switch networks. For example, Portuguese (Brazil) has |V| = 1,912, |E| = 31,299 and a density of 0.0171.

---

## 2. Design principles

### Gestalt principles

| Principle | Where it is applied | Why |
|---|---|---|
| **Proximity** | ForceAtlas2 layout; the "Pull communities apart" force; the community graph | Creators who follow each other are drawn close, so groups read as groups even without colour. |
| **Similarity** | Hue for community, shape for role (circle, diamond, square, triangle) | Same colour or shape means same class. The interface itself is monochrome, so colour always carries data and never decoration. |
| **Closure / common region** | Translucent regions around the core 80% of each community | The regions turn scattered dots into one perceived shape. Using the core 80% stops a few outliers from inflating the region. |
| **Connectedness** | Edges; the ego network drawn in solid ink on hover or selection | Connectedness overrides similarity, so a creator's neighbours read as one unit even when they span several communities. |
| **Continuity** | Matrix ordered by community, with colour bands along both axes | Ordering makes cells form continuous diagonal blocks. Random order is included so the effect can be demonstrated. |
| **Figure–ground** | Everything outside the selection fades to 12% opacity | The selection becomes the figure and the rest becomes context. |

### Managing information overload

- **Aggregation.** The Communities view replaces 7,126 creators with 9 community nodes. Communities smaller than 1% of the nodes, and any beyond the colour budget, fold into "Other". For ENGB that is 8 small communities.
- **Filtering.** Top-N creators by PageRank (50 to 1,200), minimum degree, partner and mature filters, and legend rows that toggle classes on and off.
- **Level of detail.** The interface follows Shneiderman's mantra: an overview of communities first, then zoom and filter in the network, then details on demand in the side panel. Labels appear only for the top 5 creators (top 12 when zoomed in) and use collision avoidance.
- **Sampling with full statistics.** The node-link view ships the top 1,200 creators by PageRank. All metrics and the Analytics scatter plot use the complete graph.
- **Restrained edges.** Edges are thin and low-contrast at rest. They are emphasised only for the focused creator.

---

## 3. Reference model and pipeline

```
Raw data           Data tables             Derived data                 Visual structures           Views
edges.csv     →    node table (pandas)  →  NetworkX: degree, PageRank, →  node-link (ForceAtlas2),  →  zoom/pan, filter,
target.csv         edge list (cleaned)     betweenness, clustering,       community graph,            brush & link,
                                           k-core, Louvain, roles,        adjacency matrix,           details on demand,
                                           layout, graph properties       scatter, histogram          search
```

1. **Raw → tables.** Each region's `target.csv` becomes a node table indexed by `new_id`. `edges.csv` becomes an edge list, with self-loops removed.
2. **Tables → derived data.** `preprocess.py` computes the graph properties, Louvain communities (seed 42), node metrics, the influence score (mean of the PageRank and views percentiles) and the four roles. It precomputes a ForceAtlas2 layout for the top 1,200 creators.
3. **Derived data → visual structures.** The browser maps attributes to visual variables, as listed below.
4. **Visual structures → views.** Five linked views with shared state for selection, brush and filters.

### Visual mapping

| Data attribute | Data type | Visual variable | Justification |
|---|---|---|---|
| Mutual follow | Relation | Line | The direct, standard encoding of a relation |
| Topology | Structure | 2D position (force-directed) | Position is the most accurately perceived channel. Distance approximates graph distance. |
| Community | Nominal (8 + Other) | Hue + enclosing region | Hue suits unordered categories. Eight validated colours keep adjacent pairs distinguishable under colour-vision deficiency. |
| Partner, Mature | Binary | One saturated hue vs neutral grey | The "yes" class pops out pre-attentively. |
| Role | Nominal (4) | Hue + shape | Redundant coding, so roles stay readable without colour. |
| PageRank, degree | Quantitative | Area (square-root scale) | Area grows in proportion to value, so hubs don't swamp the view. |
| Views | Quantitative, spans about 6 orders of magnitude | Area (log) / y-position (log) | A log scale keeps small channels visible. |
| Ties between communities | Quantitative | Link width | Width reads as connection strength. |
| Partner share of a community | Proportion | Arc length of the outer ring | Part-of-whole, placed directly on the community without a second chart |
| Graph adjacency | Relation | Filled matrix cell | No edge crossings, and dense groups appear as blocks. |

---

## 4. Interaction techniques

| Technique | Implementation |
|---|---|
| Zoom and pan | `d3.zoom` on the network canvas, from 0.3× to 30×, plus a Fit button |
| Details on demand | Hover tooltips. Click to pin a creator or community in the detail panel, which shows metrics, roles and connected creators. |
| Filtering | Top-N, minimum degree, partner, mature, and legend rows as toggles |
| Search | By dataset ID or Twitch user ID with autocomplete. The view zooms to the match. |
| Brushing and linking | A 2D brush on the views vs PageRank scatter plot selects creators. They are highlighted in the network, matrix and detail panel. |
| Dynamic layout | A live `d3.forceSimulation` restarts from the precomputed layout. An optional community-anchor force pulls groups apart. |
| Drill-down | Double-click a community, or use "Open in network", to show that community alone in the node-link view. |
| Reordering | Matrix ordering by community, PageRank or random |
| Encoding switches | Colour by community, partner, mature or role. Size by PageRank, views or degree. |

---

## 5. Domain-appropriate representation and visualization of groups

The data is a graph, so the primary representation is a **force-directed node-link diagram**. It is drawn on Canvas so it stays responsive with 1,200 nodes and around 40,000 edges.

The guidelines ask for at least one technique from "Visualization of Groups". This project uses three:

1. **Aggregated group graph** (Communities view): each Louvain community becomes a node.
2. **Group regions** over the node-link diagram, as in Bubble Sets and GMap-style overlays.
3. **Community-ordered adjacency matrix**, where groups appear as dense diagonal blocks.

The Analytics view adds multi-dimensional support: a log–log scatter plot and the degree distribution.

---

## 6. Findings (the story)

1. **Influence among creators is not the same as audience size.** PageRank and views correlate, but the scatter plot has a wide band. ENGB has 146 **hidden gems** (top 15% PageRank, below-median views) and 31 **lone stars** (top 5% views, weak network position).
2. **Hub-and-spoke structure.** Degree assortativity is negative (−0.12) and the degree distribution is heavy-tailed: the top 1% of creators hold 16% of all tie endpoints. Big streamers follow and are followed by many small ones.
3. **Partners mentor rather than form an elite club.** Partner assortativity is −0.14. This pattern holds in all seven networks (PTBR: −0.27).
4. **Communities are real.** Modularity is 0.46. The matrix shows clear diagonal blocks, and content rating clusters mildly (mature assortativity +0.09).
5. **Bridges are collaboration brokers.** 217 creators have high betweenness and most of their ties outside their own community. They are natural partners for cross-community events.

---

## 7. Evaluation plan

The guidelines ask for evidence that a real user can use the tool. A short task-based usability test is suggested, with 5 participants, the think-aloud protocol and timed tasks:

| Task | Success criterion |
|---|---|
| T1. Which community is the largest, and what share of its members are Partners? | Correct community and an answer within ±2% |
| T2. Find streamer 4949 and name their community and degree. | Uses search; correct values |
| T3. Find one creator with a large creator network but a small audience. | Brushes bottom-right or uses the Hidden gem role |
| T4. Which two communities are most strongly connected? | Reads link width in the Communities view |
| T5. Is the network sparse or dense? Give one number. | Quotes density or average degree |

Record completion rate, time per task and a SUS questionnaire (System Usability Scale), then report the results in the presentation.
