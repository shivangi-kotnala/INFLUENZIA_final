import glob, json, os, random, numpy as np, pandas as pd
import plotly.express as px, plotly.graph_objects as go, streamlit as st

st.set_page_config("INFLUENZIA", layout="wide")
PAL = px.colors.qualitative.Bold

@st.cache_data
def load(region):
    D = json.load(open(f"data/{region}.json"))
    df = pd.DataFrame(D["nodes"], columns=D["node_fields"])
    df["role"] = df.role.map(lambda i: D["role_codes"][i] or "None")
    df["community"] = df.group.map(lambda g: D["groups"][g]["label"])
    return D, df

regions = sorted(os.path.basename(p)[:-5] for p in glob.glob("data/*.json"))
region = st.sidebar.selectbox("Network", regions)
D, df = load(region); P = D["properties"]
color_by = st.sidebar.radio("Color by", ["community", "partner", "mature", "role"])
size_by = st.sidebar.radio("Size by", ["pagerank", "views", "degree"])
top_n = st.sidebar.slider("Top creators (by PageRank)", 50, D["top_k"], 400, 50)
min_deg = st.sidebar.slider("Min connections", 0, 50, 0)
who = st.sidebar.text_input("Search creator ID")

st.title("INFLUENZIA")
st.caption(f"Real data: MUSAE Twitch network ({D['language']}). Streamer = vertex, mutual follow = edge.")
c = st.columns(6)
for col, (k, v) in zip(c, [("Streamers", f"{P['vertices']:,}"), ("Mutual follows", f"{P['edges']:,}"),
        ("Density", P["density"]), ("Components", P["components"]),
        ("Communities", P["communities_found"]), ("Modularity", P["modularity"])]):
    col.metric(k, v)

tab1, tab2, tab3, tab4 = st.tabs(["Network", "Communities", "Analytics", "Insights"])

with tab1:
    st.caption("Each dot is a streamer and each line a mutual follow; groups sit together and bridges link them.")
    sub = df[df.x.notna() & (df.degree >= min_deg)].nlargest(top_n, "pagerank")
    vis = set(sub.id); pos = dict(zip(df.id, zip(df.x, df.y)))
    E = [(a, b) for a, b in D["edges"] if a in vis and b in vis]
    if len(E) > 6000:
        random.seed(1); E = random.sample(E, 6000); st.caption("Showing 6,000 random edges for speed.")
    focus = None
    if who.strip().isdigit() and int(who) in vis:       # search -> highlight neighbours
        i = int(who); focus = {i} | {b if a == i else a for a, b in E if i in (a, b)}
    ex, ey = [], []
    for a, b in E: ex += [pos[a][0], pos[b][0], None]; ey += [pos[a][1], pos[b][1], None]
    v = sub[size_by].astype(float)
    cols = sub[color_by].astype(str); cmap = {k: PAL[i % len(PAL)] for i, k in enumerate(sorted(cols.unique()))}
    fig = go.Figure([go.Scatter(x=ex, y=ey, mode="lines", line=dict(width=.4, color="#666"), opacity=.3, hoverinfo="none"),
        go.Scatter(x=sub.x, y=sub.y, mode="markers", hoverinfo="text",
            text=[f"ID {r.id}<br>Connections {r.degree}<br>Views {r.views:,}<br>{r.community} | {r.role}" for r in sub.itertuples()],
            marker=dict(size=5 + 28 * np.sqrt(v / v.max()), color=[cmap[k] for k in cols],
                        opacity=[1 if focus is None or i in focus else .08 for i in sub.id]))])
    fig.update_layout(template="plotly_dark", height=650, showlegend=False, dragmode="pan",
        xaxis=dict(visible=False), yaxis=dict(visible=False), margin=dict(l=0, r=0, t=0, b=0))
    st.plotly_chart(fig, width="stretch", config={"scrollZoom": True})
    st.markdown("  ".join(f"<span style='color:{c}'>●</span> {k}" for k, c in cmap.items()), unsafe_allow_html=True)

with tab2:
    g = pd.DataFrame(D["groups"])
    st.caption("How many streamers each community holds, and how many of them are Twitch Partners.")
    st.plotly_chart(px.bar(g, x="label", y="size", color="partner_share", template="plotly_dark",
        color_continuous_scale="Viridis", labels={"label": "community", "size": "streamers"}), width="stretch")
    st.caption("Brighter cells mean more mutual follows between those two communities.")
    n = len(g); M = np.zeros((n, n))
    for a, b, k in D["meta_edges"]: M[a, b] = M[b, a] = k
    st.plotly_chart(px.imshow(M, x=g.label, y=g.label, template="plotly_dark", color_continuous_scale="Viridis"), width="stretch")
    st.dataframe(g[["label", "size", "partner_share", "mature_share", "median_views", "avg_degree"]], hide_index=True)

with tab3:
    st.caption("Views vs PageRank: popularity and network position are related but not the same, so hidden gems and lone stars appear.")
    st.plotly_chart(px.scatter(df, x="views", y="pagerank", color="role", log_x=True, log_y=True, template="plotly_dark",
        hover_data=["id", "degree"]), width="stretch")
    st.caption("Degree distribution: most streamers have a few connections while a handful have hundreds.")
    dd = pd.DataFrame(D["degree_dist"], columns=["degree", "streamers"])
    st.plotly_chart(px.scatter(dd, x="degree", y="streamers", log_x=True, log_y=True, template="plotly_dark"), width="stretch")
    st.caption("Top bridges: streamers on many shortest paths that also link outside their own community.")
    st.dataframe(df[df.role == "Bridge"].nlargest(10, "betweenness")[["id", "degree", "community", "views", "betweenness"]], hide_index=True)

with tab4:
    st.caption("Plain-language findings computed from this network.")
    for line in D["insights"]: st.markdown(f"- {line}")
