# HN Data Intelligence Pipeline

An automated data engineering pipeline that tracks trending tools and technologies across the Hacker News tech community — updated twice daily via GitHub Actions and AWS S3.

**Live Demo:** [Click here](https://hn-data-pipeline-xc4xyvbsdue9merl8lbfgw.streamlit.app/) *(may take 30-60 seconds to load on first visit — free tier hosting)*

---

## Business Problem

The data and tech industry moves fast. New tools emerge constantly — dbt, Polars, DuckDB, LangChain — and staying current is critical for data professionals and hiring managers alike.

This pipeline answers: **What tools is the serious tech community actively discussing right now?**

---

## Pipeline Architecture

**GitHub Actions** (cron: 9am + 6pm UTC daily)

→ **src/fetch.py** calls Hacker News Firebase API

→ Fetches top 100 + best 100 stories, deduplicates to ~150 unique posts

→ Extracts tool mentions from titles (80+ tools across 10 categories)

→ **AWS S3** stores raw JSON with time-partitioned structure: raw/YYYY/MM/DD/HH-MM.json

→ **src/transform.py** reads last 7 days from S3, cleans and enriches data, computes engagement scores

→ **DuckDB** columnar analytics layer with posts and tool_mentions tables

→ **Streamlit** 6-page interactive intelligence dashboard

---

## Key Features

- **Fully automated** — runs twice daily with zero manual intervention
- **7-day rolling window** — always shows what is trending NOW, not historical noise
- **80+ tools tracked** across 10 categories: Programming Languages, Data Engineering, Cloud Platforms, ML and AI, Databases, Visualization and BI, Storage and Formats, DevOps and Infra
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
| Scheduling | GitHub Actions cron | Trigger pipeline twice daily |
| Data Source | Hacker News Firebase API | Live tech community stories |
| Storage | AWS S3 | Time-partitioned raw data lake |
| Transformation | Python + pandas | Clean, enrich, deduplicate |
| Analytics | DuckDB | Columnar query layer |
| Dashboard | Streamlit + Plotly | Interactive visualizations |
| Version Control | Git + GitHub | Source control and CI/CD |

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
```

Create a .env file with your AWS credentials:
AWS_ACCESS_KEY_ID=your_key
AWS_SECRET_ACCESS_KEY=your_secret
AWS_REGION=us-east-1
S3_BUCKET=your-bucket-name
Then run:

```bash
python src/fetch.py
python src/transform.py
streamlit run app/streamlit_app.py
```

---

## Author

**Nithin Kilari**
M.S. Computer Science (Data Science) — Oklahoma City University, 2026

[LinkedIn](https://www.linkedin.com/in/kilari-nithin-619481272/) | [GitHub](https://github.com/nithinkilari09)