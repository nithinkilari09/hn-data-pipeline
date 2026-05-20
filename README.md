# HN Data Intelligence Pipeline

An automated data engineering pipeline that tracks trending tools and technologies across the Hacker News tech community — updated twice daily via GitHub Actions and AWS S3.

**Live Demo:** [Click here](https://hn-data-pipeline-xc4xyvbsdue9merl8lbfgw.streamlit.app/) *(may take 30-60 seconds to load on first visit — free tier hosting)*

---

## Business Problem

The data and tech industry moves fast. New tools emerge constantly — dbt, Polars, DuckDB, LangChain — and staying current is critical for data professionals and hiring managers alike.

This pipeline answers: **What tools is the serious tech community actively discussing right now?**

---

## Pipeline Architecture
GitHub Actions (cron: 9am + 6pm UTC)
↓
src/fetch.py — Hacker News Firebase API
↓ fetches top + best stories (~150 unique posts)
↓ extracts tool mentions (80+ tools, 10 categories)
AWS S3 — time-partitioned data lake
raw/YYYY/MM/DD/HH-MM.json
↓ 7-day rolling window
src/transform.py — cleans, enriches, computes engagement scores
↓
DuckDB — columnar analytics layer
↓
Streamlit — 6-page interactive dashboard
---

## Key Features

- **Fully automated** — runs twice daily with zero manual intervention
- **7-day rolling window** — always shows what is trending NOW, not historical noise
- **80+ tools tracked** across 10 categories: Programming Languages, Data Engineering, Cloud Platforms, ML & AI, Databases, Visualization & BI, Storage & Formats, DevOps & Infra
- **Tool mention extraction** from post titles using keyword matching with special case handling for compound names (scikit-learn, Power BI, HuggingFace)
- **Engagement scoring** — weighted combination of upvotes (60%) and comments (40%)
- **Zero cost** — entirely on free tiers (GitHub Actions, AWS S3, Streamlit Cloud)

---

## Dashboard Pages

| Page | What It Shows |
|---|---|
| Overview | KPIs, top 15 tools, tool mentions by source |
| Trending Tools | Full tool rankings, mentions vs score scatter, heatmap |
| Tool Categories | Category share of discussions, drill-down by category |
| Top Stories | Highest engagement stories, score distribution |
| Community Activity | Post volume by hour and weekday, score distributions |
| Pipeline Status | Architecture diagram, recent pipeline runs |

---

## Technical Stack

| Layer | Technology | Purpose |
|---|---|---|
| Scheduling | GitHub Actions (cron) | Trigger pipeline twice daily |
| Data Source | Hacker News Firebase API | Live tech community stories |
| Storage | AWS S3 | Time-partitioned raw data lake |
| Transformation | Python + pandas | Clean, enrich, deduplicate |
| Analytics | DuckDB | Columnar query layer |
| Dashboard | Streamlit + Plotly | Interactive visualizations |
| Version Control | Git + GitHub | Source control + CI/CD |

---

## Why Hacker News?

Hacker News has a uniquely high-signal audience — senior engineers, data scientists, founders, and CTOs. An upvote on HN carries more professional weight than Reddit or Twitter engagement. When the HN community discusses a tool, it reflects genuine adoption and interest among technical decision-makers.

---

## Why DuckDB Over PostgreSQL?

This project is pure analytics — scanning all records, computing aggregations, running window functions. DuckDB is a columnar OLAP database optimized for exactly this pattern, 10-100x faster than PostgreSQL for analytical queries. It also requires zero server setup — a single file, no ports, no SSL. In production at scale, this pattern maps directly to Snowflake or BigQuery, which use identical SQL syntax.

---

## Data Retention

Raw S3 files use a 7-day rolling window — only the last 7 days of data are loaded into DuckDB. This ensures the dashboard shows genuinely trending tools rather than accumulating historical bias. In production, S3 Lifecycle Rules would automate file expiration. Converting from JSON to Parquet format would reduce storage by 8x.

---

## How to Run Locally

```bash
git clone https://github.com/nithinkilari09/hn-data-pipeline.git
cd hn-data-pipeline
python -m venv venv
venv\Scripts\activate
pip install -r requirements.txt

# Create .env file with AWS credentials
# AWS_ACCESS_KEY_ID=your_key
# AWS_SECRET_ACCESS_KEY=your_secret
# AWS_REGION=us-east-1
# S3_BUCKET=your-bucket-name

python src/fetch.py
python src/transform.py
streamlit run app/streamlit_app.py
```

---

## Author

**Nithin Kilari**
M.S. Computer Science (Data Science) — Oklahoma City University, 2026
[LinkedIn](https://www.linkedin.com/in/kilari-nithin-619481272/) | [GitHub](https://github.com/nithinkilari09)