import requests
import json
import os
import boto3
from datetime import datetime, timezone
from dotenv import load_dotenv

load_dotenv()

# Pure data domain subreddits
SUBREDDITS = [
    'datascience',
    'dataengineering',
    'machinelearning',
    'learnmachinelearning',
    'analytics',
    'businessintelligence',
    'sql',
    'python',
    'aws',
    'rstats'
]

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
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
    'Accept': 'application/json, text/plain, */*',
    'Accept-Language': 'en-US,en;q=0.9',
}

def extract_tool_mentions(title: str) -> dict:
    """Extract tool mentions from post title"""
    title_lower = title.lower()
    padded = f" {title_lower} "
    mentions = {}

    for category, tools in TOOL_CATEGORIES.items():
        for tool in tools:
            # Skip tools shorter than 3 characters — too ambiguous
            if len(tool) < 3:
                continue

            # Special multi-word tools
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
                found = 'pyspark' in title_lower or 'pyspark' in title_lower
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
def fetch_subreddit(subreddit: str, limit: int = 25) -> list:
    """Fetch top posts from a subreddit"""
    url = f"https://www.reddit.com/r/{subreddit}/hot.json?limit={limit}"
    try:
        response = requests.get(url, headers=HEADERS, timeout=10)
        response.raise_for_status()
        data = response.json()
        posts = []
        for post in data['data']['children']:
            p = post['data']
            title = p.get('title', '')
            tool_mentions = extract_tool_mentions(title)
            posts.append({
                'post_id':        p.get('id'),
                'subreddit':      p.get('subreddit'),
                'title':          title,
                'score':          p.get('score'),
                'upvote_ratio':   p.get('upvote_ratio'),
                'num_comments':   p.get('num_comments'),
                'author':         p.get('author'),
                'created_utc':    p.get('created_utc'),
                'is_self':        p.get('is_self'),
                'over_18':        p.get('over_18'),
                'fetched_at':     datetime.now(timezone.utc).isoformat(),
                'tool_mentions':  json.dumps(tool_mentions),
                'mention_count':  len(tool_mentions)
            })
        print(f"Fetched {len(posts)} posts from r/{subreddit}")
        return posts
    except Exception as e:
        print(f"Error fetching r/{subreddit}: {e}")
        return []

def fetch_all() -> list:
    """Fetch posts from all subreddits"""
    all_posts = []
    for subreddit in SUBREDDITS:
        posts = fetch_subreddit(subreddit)
        all_posts.extend(posts)
    print(f"\nTotal posts fetched: {len(all_posts)}")
    return all_posts

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