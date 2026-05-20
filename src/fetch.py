import requests
import json
import os
import boto3
from datetime import datetime, timezone
from dotenv import load_dotenv

load_dotenv()

# Hacker News API endpoints
HN_TOP_STORIES = "https://hacker-news.firebaseio.com/v0/topstories.json"
HN_ITEM = "https://hacker-news.firebaseio.com/v0/item/{}.json"
HN_NEW_STORIES = "https://hacker-news.firebaseio.com/v0/newstories.json"
HN_BEST_STORIES = "https://hacker-news.firebaseio.com/v0/beststories.json"

# Number of stories to fetch per category
STORIES_LIMIT = 100

# Complete data tool categories
TOOL_CATEGORIES = {
    'Programming Languages': [
        'python', 'scala', 'java', 'golang', 'rust'
    ],
    'Query Languages': [
        'sql', 'nosql', 'graphql', 'sparksql', 'hiveql'
    ],
    'Data Engineering': [
        'airflow', 'dbt', 'prefect', 'dagster', 'luigi',
        'kafka', 'spark', 'pyspark', 'flink', 'nifi'
    ],
    'Cloud Platforms': [
        'aws', 'gcp', 'azure', 'snowflake', 'databricks',
        'redshift', 'bigquery', 'synapse'
    ],
    'Databases': [
        'postgresql', 'mysql', 'mongodb', 'cassandra',
        'redis', 'duckdb', 'sqlite', 'elasticsearch'
    ],
    'Visualization & BI': [
        'powerbi', 'tableau', 'looker', 'metabase',
        'grafana', 'superset', 'streamlit', 'plotly'
    ],
    'Machine Learning & AI': [
        'tensorflow', 'pytorch', 'scikitlearn', 'keras',
        'xgboost', 'lightgbm', 'huggingface', 'langchain',
        'openai', 'llm', 'llms', 'chatgpt', 'claude'
    ],
    'Data Science Libraries': [
        'pandas', 'numpy', 'scipy', 'matplotlib',
        'seaborn', 'shap', 'mlflow', 'optuna', 'polars'
    ],
    'Storage & Formats': [
        'parquet', 'iceberg', 'delta', 'hudi', 's3', 'hdfs'
    ],
    'DevOps & Infra': [
        'docker', 'kubernetes', 'terraform', 'git',
        'github', 'gitlab'
    ]
}

HEADERS = {
    'User-Agent': 'Mozilla/5.0 (compatible; DataPipeline/1.0)',
}

def extract_tool_mentions(title: str) -> dict:
    """Extract tool mentions from post title"""
    title_lower = title.lower()
    padded = f" {title_lower} "
    mentions = {}

    BLACKLIST = ['r', 's', 'go', 'tf']

    for category, tools in TOOL_CATEGORIES.items():
        for tool in tools:
            if tool in BLACKLIST:
                continue
            if len(tool) < 3:
                continue

            if tool == 'scikitlearn':
                found = 'scikit-learn' in title_lower or 'sklearn' in title_lower
            elif tool == 'powerbi':
                found = 'power bi' in title_lower or 'powerbi' in title_lower
            elif tool == 'huggingface':
                found = 'hugging face' in title_lower or 'huggingface' in title_lower
            elif tool == 'langchain':
                found = 'langchain' in title_lower or 'lang chain' in title_lower
            elif tool == 'pytorch':
                found = 'pytorch' in title_lower or 'torch' in title_lower
            elif tool == 'tensorflow':
                found = 'tensorflow' in title_lower or 'tf2' in title_lower
            elif tool == 'pyspark':
                found = 'pyspark' in title_lower
            elif tool == 'bigquery':
                found = 'bigquery' in title_lower or 'big query' in title_lower
            else:
                found = (
                    f" {tool} " in padded or
                    f" {tool}," in padded or
                    f" {tool}." in padded or
                    f" {tool}:" in padded or
                    f"({tool})" in padded
                )

            if found:
                mentions[tool] = category

    return mentions

def fetch_story(story_id: int) -> dict:
    """Fetch a single story from HN"""
    try:
        response = requests.get(
            HN_ITEM.format(story_id),
            headers=HEADERS,
            timeout=5
        )
        response.raise_for_status()
        return response.json()
    except:
        return None

def fetch_stories(endpoint: str, limit: int, source: str) -> list:
    """Fetch stories from a HN endpoint"""
    try:
        response = requests.get(endpoint, headers=HEADERS, timeout=10)
        response.raise_for_status()
        story_ids = response.json()[:limit]
        print(f"Fetching {len(story_ids)} {source} stories...")

        posts = []
        for story_id in story_ids:
            story = fetch_story(story_id)
            if not story:
                continue
            if story.get('type') != 'story':
                continue
            if not story.get('title'):
                continue

            title = story.get('title', '')
            tool_mentions = extract_tool_mentions(title)

            posts.append({
                'post_id':        str(story.get('id')),
                'source':         source,
                'title':          title,
                'url':            story.get('url', ''),
                'score':          story.get('score', 0) or 0,
                'num_comments':   story.get('descendants', 0) or 0,
                'author':         story.get('by', ''),
                'created_utc':    story.get('time', 0),
                'fetched_at':     datetime.now(timezone.utc).isoformat(),
                'tool_mentions':  json.dumps(tool_mentions),
                'mention_count':  len(tool_mentions)
            })

        print(f"Fetched {len(posts)} valid {source} stories")
        return posts
    except Exception as e:
        print(f"Error fetching {source}: {e}")
        return []

def fetch_all() -> list:
    """Fetch from all HN endpoints"""
    all_posts = []

    # Top stories — most upvoted
    top = fetch_stories(HN_TOP_STORIES, STORIES_LIMIT, 'top')
    all_posts.extend(top)

    # Best stories — highest quality
    best = fetch_stories(HN_BEST_STORIES, STORIES_LIMIT, 'best')
    all_posts.extend(best)

    # Deduplicate by post_id
    seen = set()
    unique_posts = []
    for post in all_posts:
        if post['post_id'] not in seen:
            seen.add(post['post_id'])
            unique_posts.append(post)

    print(f"\nTotal unique posts: {len(unique_posts)}")
    return unique_posts

def save_local(posts: list) -> str:
    """Save posts to local data/raw folder"""
    now = datetime.now(timezone.utc)
    folder = f"data/raw/{now.strftime('%Y/%m/%d')}"
    os.makedirs(folder, exist_ok=True)
    filename = f"{folder}/{now.strftime('%H-%M')}.json"
    with open(filename, 'w') as f:
        json.dump(posts, f, indent=2)
    print(f"Saved locally: {filename}")
    return filename

def save_to_s3(posts: list, local_path: str) -> bool:
    """Upload to AWS S3"""
    bucket = os.getenv('S3_BUCKET')
    if not bucket:
        print("No S3_BUCKET set — skipping S3 upload")
        return False
    try:
        s3 = boto3.client(
            's3',
            aws_access_key_id=os.getenv('AWS_ACCESS_KEY_ID'),
            aws_secret_access_key=os.getenv('AWS_SECRET_ACCESS_KEY'),
            region_name=os.getenv('AWS_REGION', 'us-east-1')
        )
        now = datetime.now(timezone.utc)
        s3_key = f"raw/{now.strftime('%Y/%m/%d/%H-%M')}.json"
        s3.upload_file(local_path, bucket, s3_key)
        print(f"Uploaded to S3: s3://{bucket}/{s3_key}")
        return True
    except Exception as e:
        print(f"S3 upload failed: {e}")
        return False

if __name__ == "__main__":
    posts = fetch_all()
    local_path = save_local(posts)
    save_to_s3(posts, local_path)