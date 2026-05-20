# -*- coding: utf-8 -*-
import os
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
    import boto3

    base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    db_path = os.path.join(base_dir, 'data', 'reddit.duckdb')
    os.makedirs(os.path.join(base_dir, 'data'), exist_ok=True)

    sys.path.append(os.path.join(base_dir, 'src'))
    from transform import load_from_s3, transform, load_to_duckdb

    bucket = os.getenv('S3_BUCKET')
    posts = load_from_s3(days=7)

    if posts:
        transformed = transform(posts)
        load_to_duckdb(transformed, db_path)

    # Only connect if file exists
    if os.path.exists(db_path):
        return duckdb.connect(db_path, read_only=True)
    else:
        # Return empty in-memory database
        conn = duckdb.connect(':memory:')
        conn.execute("""
            CREATE TABLE IF NOT EXISTS posts (
                post_id VARCHAR, subreddit VARCHAR, title VARCHAR,
                score INTEGER, upvote_ratio DOUBLE, num_comments INTEGER,
                engagement_score DOUBLE, author VARCHAR, created_date VARCHAR,
                created_hour INTEGER, created_weekday VARCHAR, is_self BOOLEAN,
                fetched_at VARCHAR, tool_mentions VARCHAR, mention_count INTEGER
            )
        """)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS tool_mentions (
                post_id VARCHAR, tool VARCHAR, category VARCHAR,
                subreddit VARCHAR, score INTEGER, fetched_at VARCHAR
            )
        """)
        return conn

conn = get_conn()

# Sidebar
st.sidebar.title("Data Community Intelligence")
st.sidebar.markdown("Tracking trending tools and topics across 10 data subreddits")
page = st.sidebar.radio("Navigate", [
    "Overview",
    "Trending Tools",
    "Tool Categories",
    "Subreddit Intelligence",
    "Community Activity",
    "Pipeline Status"
])

# ═══════════════════════════════════════
# PAGE 1 — OVERVIEW
# ═══════════════════════════════════════
if page == "Overview":
    st.title("Data Community Intelligence Dashboard")
    st.markdown("**What is the data community talking about right now?**")
    st.markdown("Automated pipeline tracking tool mentions and trending topics across r/datascience, r/dataengineering, r/machinelearning and 7 more data subreddits.")
    st.markdown("---")

    # KPIs
    kpis = conn.execute("""
        SELECT
            COUNT(*)                        AS total_posts,
            COUNT(DISTINCT subreddit)       AS subreddits,
            COUNT(DISTINCT author)          AS unique_authors,
            ROUND(AVG(score), 0)            AS avg_score,
            SUM(mention_count)              AS total_tool_mentions,
            MAX(fetched_at)                 AS last_fetch
        FROM posts
    """).df()

    c1, c2, c3, c4, c5 = st.columns(5)
    c1.metric("Total Posts", f"{int(kpis['total_posts'][0] or 0):,}")
c2.metric("Subreddits Tracked", f"{int(kpis['subreddits'][0] or 0)}")
c3.metric("Unique Authors", f"{int(kpis['unique_authors'][0] or 0):,}")
c4.metric("Avg Post Score", f"{int(kpis['avg_score'][0] or 0):,}")
c5.metric("Tool Mentions", f"{int(kpis['total_tool_mentions'][0] or 0):,}")

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
        fig = px.bar(top_tools, x='mentions', y='tool',
                     orientation='h',
                     title='Top 15 Most Mentioned Data Tools',
                     color='category',
                     color_discrete_sequence=px.colors.qualitative.Set2)
        fig.update_layout(yaxis={'categoryorder': 'total ascending'},
                          legend_title='Category')
        st.plotly_chart(fig, use_container_width=True)

    with col2:
        subreddit_activity = conn.execute("""
            SELECT subreddit,
                COUNT(*) AS post_count,
                SUM(num_comments) AS total_comments,
                ROUND(AVG(score), 0) AS avg_score,
                SUM(mention_count) AS tool_mentions
            FROM posts
            GROUP BY subreddit
            ORDER BY post_count DESC
        """).df()
        fig = px.bar(subreddit_activity, x='subreddit', y='tool_mentions',
                     title='Tool Mentions by Subreddit',
                     color='tool_mentions',
                     color_continuous_scale='Blues')
        fig.update_layout(xaxis_tickangle=45)
        st.plotly_chart(fig, use_container_width=True)

    st.markdown("---")
    st.subheader("Top Posts With Tool Mentions")
    top_posts = conn.execute("""
        SELECT subreddit, title, score, num_comments,
               engagement_score, mention_count
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
    st.markdown("Which tools is the data community discussing most?")
    st.markdown("---")

    all_tools = conn.execute("""
        SELECT tool, category,
            COUNT(*) AS mentions,
            COUNT(DISTINCT subreddit) AS subreddits_mentioning,
            ROUND(AVG(score), 0) AS avg_post_score
        FROM tool_mentions
        GROUP BY tool, category
        ORDER BY mentions DESC
    """).df()

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
                         title='Mentions vs Avg Post Score by Tool',
                         hover_data=['tool', 'subreddits_mentioning'],
                         color_discrete_sequence=px.colors.qualitative.Set2)
        st.plotly_chart(fig, use_container_width=True)

    st.markdown("---")
    st.subheader("Tool Mention Heatmap — Tool vs Subreddit")
    heatmap_data = conn.execute("""
        SELECT tool, subreddit, COUNT(*) AS mentions
        FROM tool_mentions
        GROUP BY tool, subreddit
        ORDER BY mentions DESC
    """).df()

    if not heatmap_data.empty:
        pivot = heatmap_data.pivot_table(
            index='tool', columns='subreddit',
            values='mentions', fill_value=0
        )
        fig = px.imshow(pivot,
                        title='Tool Mentions Heatmap (Tool vs Subreddit)',
                        color_continuous_scale='Blues',
                        aspect='auto')
        fig.update_layout(height=600)
        st.plotly_chart(fig, use_container_width=True)

    st.markdown("---")
    st.subheader("Complete Tool Rankings")
    st.dataframe(all_tools, use_container_width=True)

# ═══════════════════════════════════════
# PAGE 3 — TOOL CATEGORIES
# ═══════════════════════════════════════
elif page == "Tool Categories":
    st.title("Tool Category Analysis")
    st.markdown("Which category of data tools dominates community discussions?")
    st.markdown("---")

    categories = conn.execute("""
        SELECT category,
            COUNT(*) AS total_mentions,
            COUNT(DISTINCT tool) AS unique_tools,
            COUNT(DISTINCT subreddit) AS subreddits,
            ROUND(AVG(score), 0) AS avg_post_score
        FROM tool_mentions
        GROUP BY category
        ORDER BY total_mentions DESC
    """).df()

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

    # Category drill down
    selected_cat = st.selectbox("Drill down into category:",
                                categories['category'].tolist())
    cat_tools = conn.execute(f"""
        SELECT tool,
            COUNT(*) AS mentions,
            COUNT(DISTINCT subreddit) AS subreddits,
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
# PAGE 4 — SUBREDDIT INTELLIGENCE
# ═══════════════════════════════════════
elif page == "Subreddit Intelligence":
    st.title("Subreddit Intelligence")
    st.markdown("What does each data community care about?")
    st.markdown("---")

    subreddits = conn.execute("""
        SELECT DISTINCT subreddit FROM posts ORDER BY subreddit
    """).df()['subreddit'].tolist()

    selected_sub = st.selectbox("Select subreddit:", subreddits)

    col1, col2, col3, col4 = st.columns(4)
    sub_kpis = conn.execute(f"""
        SELECT
            COUNT(*) AS posts,
            ROUND(AVG(score), 0) AS avg_score,
            ROUND(AVG(num_comments), 0) AS avg_comments,
            ROUND(AVG(upvote_ratio), 3) AS avg_upvote_ratio
        FROM posts
        WHERE subreddit = '{selected_sub}'
    """).df()
    col1.metric("Posts", f"{int(sub_kpis['posts'][0]):,}")
    col2.metric("Avg Score", f"{int(sub_kpis['avg_score'][0]):,}")
    col3.metric("Avg Comments", f"{int(sub_kpis['avg_comments'][0]):,}")
    col4.metric("Upvote Ratio", f"{sub_kpis['avg_upvote_ratio'][0]:.3f}")

    st.markdown("---")
    col1, col2 = st.columns(2)
    with col1:
        sub_tools = conn.execute(f"""
            SELECT tool, category, COUNT(*) AS mentions
            FROM tool_mentions
            WHERE subreddit = '{selected_sub}'
            GROUP BY tool, category
            ORDER BY mentions DESC
            LIMIT 15
        """).df()
        if not sub_tools.empty:
            fig = px.bar(sub_tools, x='mentions', y='tool',
                         orientation='h',
                         title=f'Top Tools in r/{selected_sub}',
                         color='category',
                         color_discrete_sequence=px.colors.qualitative.Set2)
            fig.update_layout(yaxis={'categoryorder': 'total ascending'})
            st.plotly_chart(fig, use_container_width=True)
        else:
            st.info("No tool mentions found for this subreddit yet")

    with col2:
        top_posts = conn.execute(f"""
            SELECT title, score, num_comments, engagement_score
            FROM posts
            WHERE subreddit = '{selected_sub}'
            ORDER BY engagement_score DESC
            LIMIT 10
        """).df()
        st.subheader(f"Top Posts in r/{selected_sub}")
        st.dataframe(top_posts, use_container_width=True)

    st.markdown("---")
    st.subheader("Cross-Subreddit Tool Comparison")
    cross = conn.execute("""
        SELECT subreddit, category,
            COUNT(*) AS mentions
        FROM tool_mentions
        GROUP BY subreddit, category
        ORDER BY subreddit, mentions DESC
    """).df()
    fig = px.bar(cross, x='subreddit', y='mentions',
                 color='category', barmode='stack',
                 title='Tool Category Mentions by Subreddit',
                 color_discrete_sequence=px.colors.qualitative.Set2)
    fig.update_layout(xaxis_tickangle=45)
    st.plotly_chart(fig, use_container_width=True)

# ═══════════════════════════════════════
# PAGE 5 — COMMUNITY ACTIVITY
# ═══════════════════════════════════════
elif page == "Community Activity":
    st.title("Community Activity")
    st.markdown("When and how does the data community engage?")
    st.markdown("---")

    col1, col2 = st.columns(2)
    with col1:
        hourly = conn.execute("""
            SELECT created_hour,
                COUNT(*) AS posts,
                ROUND(AVG(score), 0) AS avg_score,
                ROUND(AVG(num_comments), 0) AS avg_comments
            FROM posts
            WHERE created_hour IS NOT NULL
            GROUP BY created_hour
            ORDER BY created_hour
        """).df()
        fig = px.bar(hourly, x='created_hour', y='posts',
                     title='Post Volume by Hour (UTC)',
                     color='posts', color_continuous_scale='Blues')
        fig.update_layout(xaxis_title='Hour of Day (UTC)')
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
            ORDER BY posts DESC
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
            SELECT subreddit, score FROM posts WHERE score > 0
        """).df(), x='subreddit', y='score',
                     title='Score Distribution by Subreddit',
                     color='subreddit')
        fig.update_layout(xaxis_tickangle=45, showlegend=False)
        st.plotly_chart(fig, use_container_width=True)

    with col2:
        top_authors = conn.execute("""
            SELECT author,
                COUNT(*) AS posts,
                ROUND(AVG(score), 0) AS avg_score,
                SUM(num_comments) AS total_comments
            FROM posts
            WHERE author NOT IN ('[deleted]','[removed]','AutoModerator')
            GROUP BY author
            HAVING COUNT(*) > 1
            ORDER BY posts DESC
            LIMIT 15
        """).df()
        st.subheader("Most Active Authors (2+ posts)")
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
GitHub Actions (cron: 0 9,18 * * * — 9am + 6pm UTC)
    ↓ triggers twice daily
src/fetch.py
    ↓ calls Reddit Public API (no auth)
    ↓ fetches 25 posts × 10 subreddits = 250 posts
    ↓ extracts tool mentions from titles (80+ tools)
    ↓ categorizes into 10 technology categories
AWS S3 (raw/YYYY/MM/DD/HH-MM.json)
    ↓ time-partitioned data lake
src/transform.py
    ↓ cleans, deduplicates, enriches
    ↓ computes engagement scores
    ↓ expands tool mentions into separate table
DuckDB (posts table + tool_mentions table)
    ↓ columnar analytics layer
Streamlit Dashboard
    ↓ 6-page interactive intelligence dashboard
──────────────────────────────────────────────────────
Schedule : Twice daily (9am + 6pm UTC)
AWS Cost  : ~$0.00 (S3 free tier — 5GB)
GitHub    : ~60 Actions minutes/month (free tier: 2000)
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
st.sidebar.markdown("Data: Reddit Public API — 10 data subreddits")
st.sidebar.markdown("Schedule: Twice daily — 9am + 6pm UTC")
st.sidebar.markdown("Nithin Kilari | 2026")