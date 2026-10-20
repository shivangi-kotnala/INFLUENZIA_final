# INFLUENZIA (Python / Streamlit)
Real data: MUSAE Twitch social networks (Rozemberczki, Allen & Sarkar, 2021). Included: English (ENGB) and Portuguese-Brazil (PTBR).
Run: pip install -r requirements.txt, then streamlit run app.py
Add regions: put {REGION}_edges.csv and {REGION}_target.csv from github.com/benedekrozemberczki/MUSAE (input/edges, input/target) in data/raw/ and run python preprocess.py REGION
Deploy: push to GitHub, then share.streamlit.io with main file app.py
