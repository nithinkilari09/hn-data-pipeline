# -*- coding: utf-8 -*-
import os
import math
import streamlit as st
import duckdb
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from dotenv import load_dotenv
load_dotenv()

st.set_page_config(
    page_title="Data Community Intelligence",
    page_icon="📊",
    layout="wide"
)

@st.cache_resource
def get_conn():
    import sys
    base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    db_path = os.path.join(base_dir, 'data', 'reddit.duckdb')
    os.makedirs(os.path.join(base_dir, 'data'), exist_ok=True)
    sys.path.append(os.path.join(base_dir, 'src'))
    from transform import load_from_s3, transform, load_to_duckdb
    posts = load_from_s3(days=7)
    if posts:
        transformed = transform(posts)
        load_to_duckdb(transformed, db_path)
    if os.path.exists(db_path):
        return duckdb.connect(db_path, read_only=True)
    else:
        conn = duckdb.connect(':memory:')
        conn.execute("""
            CREATE TABLE IF NOT EXISTS posts (
                post_id VARCHAR, source VARCHAR, title VARCHAR, url VARCHAR,
                score INTEGER, num_comments INTEGER, engagement_score DOUBLE,
                author VARCHAR, created_date VARCHAR, created_hour INTEGER,
                created_weekday VARCHAR, fetched_at VARCHAR,
                tool_mentions VARCHAR, mention_count INTEGER
            )
        """)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS tool_mentions (
                post_id VARCHAR, tool VARCHAR, category VARCHAR,
                source VARCHAR, score INTEGER, fetched_at VARCHAR
            )
        """)
        return conn

conn = get_conn()

def safe_int(val):
    try:
        return 0 if (val is None or math.isnan(float(val))) else int(val)
    except:
        return 0

# Sidebar
st.sidebar.title("Data Community Intelligence")
st.sidebar.markdown("Tracking trending tools across Hacker News tech community")
page = st.sidebar.radio("Navigate", [
    "Overview",
    "Trending Tools",
    "Tool Categories",
    "Top Stories",
    "Community Activity",
    "Pipeline Status"
])

# ═══════════════════════════════════════
# PAGE 1 — OVERVIEW
# ═══════════════════════════════════════
if page == "Overview":
    st.title("Data Community Intelligence Dashboard")
    st.markdown("**What is the tech community talking about right now?**")
    st.markdown("Automated pipeline tracking tool mentions across Hacker News — updated twice daily via GitHub Actions + AWS S3.")
    st.markdown("---")

    kpis = conn.execute("""
        SELECT
            COUNT(*)                    AS total_posts,
            COUNT(DISTINCT source)      AS sources,
            COUNT(DISTINCT author)      AS unique_authors,
            ROUND(AVG(score), 0)        AS avg_score,
            SUM(mention_count)          AS total_tool_mentions,
            MAX(fetched_at)             AS last_fetch
        FROM posts
    """).df()

    c1, c2, c3, c4, c5 = st.columns(5)
    c1.metric("Total Posts", f"{safe_int(kpis['total_posts'][0]):,}")
    c2.metric("Data Sources", f"{safe_int(kpis['sources'][0])}")
    c3.metric("Unique Authors", f"{safe_int(kpis['unique_authors'][0]):,}")
    c4.metric("Avg Score", f"{safe_int(kpis['avg_score'][0]):,}")
    c5.metric("Tool Mentions", f"{safe_int(kpis['total_tool_mentions'][0]):,}")

    st.markdown("---")

    col1, col2 = st.columns(2)
    with col1:
        top_tools = conn.execute("""
            SELECT tool, category,
                COUNT(*) AS mentions,
                ROUND(AVG(score), 0) AS avg_post_score
            FROM tool_mentions
            GROUP BY tool, category
            ORDER BY mentions DESC
            LIMIT 15
        """).df()
        if not top_tools.empty:
            fig = px.bar(top_tools, x='mentions', y='tool',
                         orientation='h',
                         title='Top 15 Most Mentioned Data Tools',
                         color='category',
                         color_discrete_sequence=px.colors.qualitative.Set2)
            fig.update_layout(yaxis={'categoryorder': 'total ascending'},
                              legend_title='Category')
            st.plotly_chart(fig, use_container_width=True)
        else:
            st.info("No tool mentions yet — pipeline building data...")

    with col2:
        source_activity = conn.execute("""
            SELECT source,
                COUNT(*) AS post_count,
                ROUND(AVG(score), 0) AS avg_score,
                SUM(mention_count) AS tool_mentions
            FROM posts
            GROUP BY source
            ORDER BY post_count DESC
        """).df()
        if not source_activity.empty:
            fig = px.bar(source_activity, x='source', y='tool_mentions',
                         title='Tool Mentions by Source',
                         color='tool_mentions',
                         color_continuous_scale='Blues')
            st.plotly_chart(fig, use_container_width=True)

    st.markdown("---")
    st.subheader("Top Posts With Tool Mentions")
    top_posts = conn.execute("""
        SELECT source, title, score, num_comments,
               engagement_score, mention_count, url
        FROM posts
        WHERE mention_count > 0
        ORDER BY engagement_score DESC
        LIMIT 10
    """).df()
    st.dataframe(top_posts, use_container_width=True)
    st.info(f"Last pipeline run: {kpis['last_fetch'][0]}")

# ═══════════════════════════════════════
# PAGE 2 — TRENDING TOOLS
# ═══════════════════════════════════════
elif page == "Trending Tools":
    st.title("Trending Data Tools")
    st.markdown("Which tools is the tech community discussing most on Hacker News?")
    st.markdown("---")

    all_tools = conn.execute("""
        SELECT tool, category,
            COUNT(*) AS mentions,
            COUNT(DISTINCT source) AS sources,
            ROUND(AVG(score), 0) AS avg_post_score
        FROM tool_mentions
        GROUP BY tool, category
        ORDER BY mentions DESC
    """).df()

    if all_tools.empty:
        st.info("No tool data yet — check back after pipeline runs.")
    else:
        col1, col2 = st.columns(2)
        with col1:
            fig = px.bar(all_tools.head(20), x='mentions', y='tool',
                         orientation='h',
                         title='Top 20 Tools by Mention Count',
                         color='category',
                         color_discrete_sequence=px.colors.qualitative.Set2)
            fig.update_layout(yaxis={'categoryorder': 'total ascending'})
            st.plotly_chart(fig, use_container_width=True)

        with col2:
            fig = px.scatter(all_tools, x='mentions', y='avg_post_score',
                             size='mentions', color='category',
                             title='Mentions vs Avg Post Score',
                             hover_data=['tool'],
                             color_discrete_sequence=px.colors.qualitative.Set2)
            st.plotly_chart(fig, use_container_width=True)

        st.markdown("---")
        st.subheader("Tool Mention Heatmap")
        heatmap_data = conn.execute("""
            SELECT tool, source, COUNT(*) AS mentions
            FROM tool_mentions
            GROUP BY tool, source
        """).df()
        if not heatmap_data.empty:
            pivot = heatmap_data.pivot_table(
                index='tool', columns='source',
                values='mentions', fill_value=0
            )
            fig = px.imshow(pivot,
                            title='Tool Mentions by Source',
                            color_continuous_scale='Blues',
                            aspect='auto')
            st.plotly_chart(fig, use_container_width=True)

        st.markdown("---")
        st.subheader("Complete Tool Rankings")
        st.dataframe(all_tools, use_container_width=True)

# ═══════════════════════════════════════
# PAGE 3 — TOOL CATEGORIES
# ═══════════════════════════════════════
elif page == "Tool Categories":
    st.title("Tool Category Analysis")
    st.markdown("Which category of data tools dominates tech discussions?")
    st.markdown("---")

    categories = conn.execute("""
        SELECT category,
            COUNT(*) AS total_mentions,
            COUNT(DISTINCT tool) AS unique_tools,
            ROUND(AVG(score), 0) AS avg_post_score
        FROM tool_mentions
        GROUP BY category
        ORDER BY total_mentions DESC
    """).df()

    if categories.empty:
        st.info("No category data yet.")
    else:
        col1, col2 = st.columns(2)
        with col1:
            fig = px.pie(categories, values='total_mentions', names='category',
                         title='Tool Category Share of Discussions',
                         color_discrete_sequence=px.colors.qualitative.Set2)
            st.plotly_chart(fig, use_container_width=True)

        with col2:
            fig = px.bar(categories, x='category', y='total_mentions',
                         title='Total Mentions by Category',
                         color='total_mentions',
                         color_continuous_scale='Viridis')
            fig.update_layout(xaxis_tickangle=45)
            st.plotly_chart(fig, use_container_width=True)

        st.markdown("---")
        selected_cat = st.selectbox("Drill down into category:",
                                    categories['category'].tolist())
        cat_tools = conn.execute(f"""
            SELECT tool,
                COUNT(*) AS mentions,
                ROUND(AVG(score), 0) AS avg_score
            FROM tool_mentions
            WHERE category = '{selected_cat}'
            GROUP BY tool
            ORDER BY mentions DESC
        """).df()

        col1, col2 = st.columns(2)
        with col1:
            fig = px.bar(cat_tools, x='tool', y='mentions',
                         title=f'{selected_cat} — Tool Mentions',
                         color='mentions',
                         color_continuous_scale='Blues')
            st.plotly_chart(fig, use_container_width=True)
        with col2:
            st.subheader(f"{selected_cat} Rankings")
            st.dataframe(cat_tools, use_container_width=True)

# ═══════════════════════════════════════
# PAGE 4 — TOP STORIES
# ═══════════════════════════════════════
elif page == "Top Stories":
    st.title("Top Stories")
    st.markdown("Highest engagement stories from Hacker News")
    st.markdown("---")

    source_filter = st.selectbox("Filter by source:", ["All", "top", "best"])

    if source_filter == "All":
        stories = conn.execute("""
            SELECT source, title, score, num_comments,
                   engagement_score, mention_count, url, author, created_date
            FROM posts
            ORDER BY engagement_score DESC
            LIMIT 50
        """).df()
    else:
        stories = conn.execute(f"""
            SELECT source, title, score, num_comments,
                   engagement_score, mention_count, url, author, created_date
            FROM posts
            WHERE source = '{source_filter}'
            ORDER BY engagement_score DESC
            LIMIT 50
        """).df()

    col1, col2 = st.columns(2)
    with col1:
        fig = px.scatter(stories, x='score', y='num_comments',
                         color='source', size='engagement_score',
                         title='Score vs Comments',
                         hover_data=['title'])
        st.plotly_chart(fig, use_container_width=True)

    with col2:
        fig = px.histogram(stories, x='score', nbins=20,
                           title='Score Distribution',
                           color_discrete_sequence=['#3498db'])
        st.plotly_chart(fig, use_container_width=True)

    st.markdown("---")
    st.subheader("Stories Table")
    st.dataframe(stories[['source', 'title', 'score',
                           'num_comments', 'mention_count', 'author']],
                 use_container_width=True)

# ═══════════════════════════════════════
# PAGE 5 — COMMUNITY ACTIVITY
# ═══════════════════════════════════════
elif page == "Community Activity":
    st.title("Community Activity")
    st.markdown("When does the tech community engage most?")
    st.markdown("---")

    col1, col2 = st.columns(2)
    with col1:
        hourly = conn.execute("""
            SELECT created_hour,
                COUNT(*) AS posts,
                ROUND(AVG(score), 0) AS avg_score
            FROM posts
            WHERE created_hour IS NOT NULL
            GROUP BY created_hour
            ORDER BY created_hour
        """).df()
        fig = px.bar(hourly, x='created_hour', y='posts',
                     title='Post Volume by Hour (UTC)',
                     color='posts', color_continuous_scale='Blues')
        st.plotly_chart(fig, use_container_width=True)

    with col2:
        weekday = conn.execute("""
            SELECT created_weekday,
                COUNT(*) AS posts,
                ROUND(AVG(score), 0) AS avg_score
            FROM posts
            WHERE created_weekday IS NOT NULL
              AND created_weekday != ''
            GROUP BY created_weekday
        """).df()
        day_order = ['Monday','Tuesday','Wednesday',
                     'Thursday','Friday','Saturday','Sunday']
        weekday['created_weekday'] = pd.Categorical(
            weekday['created_weekday'], categories=day_order, ordered=True)
        weekday = weekday.sort_values('created_weekday')
        fig = px.bar(weekday, x='created_weekday', y='posts',
                     title='Post Volume by Day of Week',
                     color='avg_score', color_continuous_scale='Viridis')
        st.plotly_chart(fig, use_container_width=True)

    st.markdown("---")
    col1, col2 = st.columns(2)
    with col1:
        fig = px.box(conn.execute("""
            SELECT source, score FROM posts WHERE score > 0
        """).df(), x='source', y='score',
                     title='Score Distribution by Source',
                     color='source')
        st.plotly_chart(fig, use_container_width=True)

    with col2:
        top_authors = conn.execute("""
            SELECT author,
                COUNT(*) AS posts,
                ROUND(AVG(score), 0) AS avg_score,
                SUM(num_comments) AS total_comments
            FROM posts
            WHERE author NOT IN ('', 'None')
            GROUP BY author
            HAVING COUNT(*) > 1
            ORDER BY avg_score DESC
            LIMIT 15
        """).df()
        st.subheader("Most Active Authors")
        st.dataframe(top_authors, use_container_width=True)

# ═══════════════════════════════════════
# PAGE 6 — PIPELINE STATUS
# ═══════════════════════════════════════
elif page == "Pipeline Status":
    st.title("Pipeline Status")
    st.markdown("---")

    col1, col2, col3 = st.columns(3)
    total = conn.execute("SELECT COUNT(*) FROM posts").fetchone()[0]
    mentions = conn.execute("SELECT COUNT(*) FROM tool_mentions").fetchone()[0]
    runs = conn.execute(
        "SELECT COUNT(DISTINCT fetched_at) FROM posts").fetchone()[0]
    col1.metric("Total Posts Collected", f"{total:,}")
    col2.metric("Tool Mentions Extracted", f"{mentions:,}")
    col3.metric("Pipeline Runs", f"{runs:,}")

    st.markdown("---")
    st.subheader("Pipeline Architecture")
    st.code("""
Pipeline: Data Community Intelligence
──────────────────────────────────────────────────────
GitHub Actions (cron: 9am + 6pm UTC daily)
    ↓ triggers twice daily
src/fetch.py
    ↓ calls Hacker News Firebase API
    ↓ fetches top 100 + best 100 stories
    ↓ deduplicates to ~150 unique posts
    ↓ extracts tool mentions (80+ tools, 10 categories)
AWS S3 (raw/YYYY/MM/DD/HH-MM.json)
    ↓ time-partitioned data lake (7-day rolling window)
src/transform.py
    ↓ cleans and enriches posts
    ↓ computes engagement scores
    ↓ expands tool mentions into separate table
DuckDB (posts + tool_mentions tables)
    ↓ columnar analytics layer
Streamlit Dashboard
    ↓ 6-page interactive intelligence dashboard
──────────────────────────────────────────────────────
Data Source : Hacker News (Firebase API — no auth)
Schedule    : Twice daily (9am + 6pm UTC)
AWS Cost    : ~$0.00 (S3 free tier)
GitHub Cost : ~60 Actions minutes/month (free tier)
    """, language="text")

    st.markdown("---")
    recent_runs = conn.execute("""
        SELECT fetched_at,
            COUNT(*) AS posts,
            SUM(mention_count) AS tool_mentions
        FROM posts
        GROUP BY fetched_at
        ORDER BY fetched_at DESC
        LIMIT 10
    """).df()
    st.subheader("Recent Pipeline Runs")
    st.dataframe(recent_runs, use_container_width=True)

# Footer
st.sidebar.markdown("---")
st.sidebar.markdown("Stack: GitHub Actions + AWS S3 + DuckDB + Streamlit")
st.sidebar.markdown("Data: Hacker News API")
st.sidebar.markdown("Schedule: Twice daily — 9am + 6pm UTC")
st.sidebar.markdown("Nithin Kilari | 2026")