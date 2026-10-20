# INFLUENZIA

An interactive visualization of social connections between Twitch creators. It helps you find influential creators, the communities they form, and network patterns that are hard to see otherwise: hidden gems, bridges, and hub-and-spoke structure.

DSE3150 Graph Visualization project.

## Quick start

No build step and no server needed.

1. Open `index.html` in a modern browser (Chrome, Edge, Firefox or Safari).
2. You need internet access the first time so the page can load D3 v7.9.0 and Google Fonts from their CDNs. All of the data is local, in `data/influenzia_data.js`.

If your browser blocks local scripts, serve the folder instead:

```bash
python -m http.server 8000      # then open http://localhost:8000
```

## Rebuilding the data (optional)

The processed data is already included. To regenerate it from the raw CSVs:

```bash
pip install networkx pandas numpy      # tested with networkx 3.6, pandas 2.x
python preprocess.py                   # all 7 regions, about 10–15 minutes
python preprocess.py ENGB PTBR         # or only some regions
```

The script needs NetworkX 3.4 or newer for `forceatlas2_layout`. With an older version it falls back to `spring_layout`.

## Dataset

**MUSAE Twitch social networks.** B. Rozemberczki, C. Allen, R. Sarkar, *Multi-scale Attributed Node Embedding*, Journal of Complex Networks, 2021 (arXiv:1909.13021). The data was collected in May 2018.

- Source: https://github.com/benedekrozemberczki/MUSAE (`input/edges`, `input/target`). It is also on SNAP: https://snap.stanford.edu/data/twitch-social-networks.html
- There are 7 networks, one per broadcast language: English, German, French, Spanish, Russian, Portuguese (Brazil) and Chinese (Taiwan).
- **Vertices** are streamers. **Edges** are mutual follower relationships between two streamers, so the graph is undirected.
- **Vertex attributes:** `views` (total channel views), `partner` (Twitch Partner, a verified and monetised creator), `mature` (explicit-content flag) and `days` (account age).
- The raw files are in `data/raw/`.

| Network | Vertices | Edges |
|---|---:|---:|
| English (ENGB) | 7,126 | 35,324 |
| German (DE) | 9,498 | 153,138 |
| French (FR) | 6,549 | 112,666 |
| Spanish (ES) | 4,648 | 59,382 |
| Russian (RU) | 4,385 | 37,304 |
| Portuguese (PTBR) | 1,912 | 31,299 |
| Chinese (ZHTW) | 2,772 | 63,462 |

## Project structure

```
influenzia/
├── index.html              the application (HTML + CSS + JS, uses D3 v7)
├── preprocess.py           raw CSV → graph metrics → data/influenzia_data.js
├── data/
│   ├── raw/                original MUSAE edge and target CSVs
│   ├── influenzia_data.js  processed data for all regions (loaded by index.html)
│   └── <REGION>.json       the same data, one JSON file per region
├── README.md               this file
└── REPORT.md               design report mapped to the project guidelines
```

## What the preprocessing computes

All of these are computed on the full graph:

- Formal properties: |V|, |E|, density, degree statistics, isolated and pendant vertices, connected components, giant component, average clustering, transitivity, degree and attribute assortativity, estimated average path length, a lower bound on the diameter, and the maximum k-core.
- Communities: Louvain (seed 42, resolution 1.0) and its modularity Q. The 8 largest communities get their own colour, and communities under 1% of the nodes are merged into **Other**.
- Per-node metrics: degree, PageRank, betweenness (estimated from 600 sampled sources), local clustering, core number, and participation (the share of a node's ties that leave its community).
- **Influence score:** the mean of the node's PageRank percentile and views percentile.
- **Roles** (hidden patterns):
  - Hub: top 3% PageRank and top 10% views.
  - Hidden gem: top 15% PageRank but below-median views.
  - Bridge: top 10% betweenness, at least 50% of ties outside the node's own community, and degree of at least 5.
  - Lone star: top 5% views but below-median PageRank.
- **Network sample:** the top 1,200 creators by PageRank, with the edges among them and a precomputed ForceAtlas2 layout.

## Using the app

| View | What it shows | Interactions |
|---|---|---|
| **Communities** | Aggregated graph with one circle per community. Circle area is the number of creators, link width is the number of ties between communities, and the outer ring shows the share of Partners. | Hover for statistics, click to inspect, double-click to open that community in the Network view. |
| **Network** | Node-link diagram of the top-N creators, with translucent regions around each community. | Zoom and pan, hover to see a creator's ego network, click to pin details, live force layout, "Pull communities apart", Fit. |
| **Matrix** | Adjacency matrix of the top 150 visible creators. | Reorder by community, PageRank or random. Hover a cell to see the pair, click a row to select that creator. |
| **Analytics** | Views vs PageRank scatter plot (all creators), degree distribution, and a community profile table. | Brush the scatter plot to select creators. The selection is linked to the network, the matrix and the detail panel. |
| **Method** | The pipeline, visual mappings, Gestalt principles and techniques, written for the presentation. | |

The left panel has the encoding controls (colour by community, partner, mature or role; size by PageRank, views or degree) and the filters (top-N, minimum degree, partner, mature). Each legend row also works as a filter: click it to hide or show that group. The search box finds a creator by dataset ID or Twitch user ID.

## Suggested demo (about 7 minutes)

1. **Question (30 s).** Who really holds influence among Twitch creators, and is it the same as having the biggest audience?
2. **Graph facts (1 min).** Pick English. The right panel shows |V|, |E|, density, components, pendant vertices and assortativity. Point out that the network is sparse but a small world.
3. **Communities (1.5 min).** Explain the aggregated view and the partner ring. Click the largest community, then double-click it to open it in the Network view.
4. **Network (2 min).** Reset the filters and switch on community regions. Hover a hub to show its ego network. Switch colour to **Role** and point out hidden gems (diamonds) and bridges (squares). Turn on "Pull communities apart" to show proximity at work.
5. **Matrix (45 s).** Switch the order from Random to By community. The diagonal blocks appear, which shows why ordering matters.
6. **Analytics (1.5 min).** Brush the top-right of the scatter plot (high PageRank and high views), then switch back to Network to show the linked highlight. Brush the bottom-right (high PageRank, low views) to find the hidden gems.
7. **Close (30 s).** Influence among creators and audience size are correlated but not the same thing. Bridges and hidden gems are where collaboration opportunities are.

## Tools

D3.js v7.9.0 (rendering, force layouts, zoom, brushing), Canvas 2D (for performance with thousands of nodes), Python with NetworkX and pandas (graph analytics).
