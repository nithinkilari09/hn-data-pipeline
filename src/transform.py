import json
import os
import glob
import duckdb
from datetime import datetime, timezone, timedelta
from dotenv import load_dotenv

load_dotenv()

def load_local_files(data_dir: str = "data/raw") -> list:
    """Load all JSON files from local raw folder"""
    all_posts = []
    pattern = f"{data_dir}/**/*.json"
    files = glob.glob(pattern, recursive=True)
    print(f"Found {len(files)} JSON files locally")
    for file in files:
        with open(file, 'r') as f:
            posts = json.load(f)
            all_posts.extend(posts)
    print(f"Total posts loaded: {len(all_posts)}")
    return all_posts

def load_from_s3(days: int = 7) -> list:
    """Load JSON files from S3 — last N days only"""
    import boto3
    bucket = os.getenv('S3_BUCKET')
    if not bucket:
        print("No S3_BUCKET — falling back to local files")
        return load_local_files()

    s3 = boto3.client(
        's3',
        aws_access_key_id=os.getenv('AWS_ACCESS_KEY_ID'),
        aws_secret_access_key=os.getenv('AWS_SECRET_ACCESS_KEY'),
        region_name=os.getenv('AWS_REGION', 'us-east-1')
    )

    cutoff = datetime.now(timezone.utc) - timedelta(days=days)
    print(f"Loading S3 files from last {days} days (since {cutoff.strftime('%Y-%m-%d')})")

    all_posts = []
    paginator = s3.get_paginator('list_objects_v2')
    pages = paginator.paginate(Bucket=bucket, Prefix='raw/')

    file_count = 0
    for page in pages:
        for obj in page.get('Contents', []):
            if obj['LastModified'].replace(tzinfo=timezone.utc) >= cutoff:
                key = obj['Key']
                if key.endswith('.json'):
                    response = s3.get_object(Bucket=bucket, Key=key)
                    posts = json.loads(response['Body'].read())
                    all_posts.extend(posts)
                    file_count += 1

    print(f"Loaded {file_count} files from S3 (last {days} days): {len(all_posts)} posts")
    return all_posts

def transform(posts: list) -> list:
    """Clean and enrich raw posts"""
    transformed = []
    for p in posts:
        if p.get('author') in ['[deleted]', '[removed]', None, '']:
            continue

        created_utc = p.get('created_utc', 0)
        try:
            created_dt = datetime.fromtimestamp(created_utc, tz=timezone.utc)
            created_date = created_dt.strftime('%Y-%m-%d')
            created_hour = created_dt.hour
            created_weekday = created_dt.strftime('%A')
        except:
            created_date = None
            created_hour = None
            created_weekday = None

        score = p.get('score', 0) or 0
        comments = p.get('num_comments', 0) or 0
        engagement_score = round((score * 0.6) + (comments * 0.4), 2)

        tool_mentions = p.get('tool_mentions', '{}')
        if isinstance(tool_mentions, str):
            try:
                tool_mentions_dict = json.loads(tool_mentions)
            except:
                tool_mentions_dict = {}
        else:
            tool_mentions_dict = tool_mentions or {}

        transformed.append({
            'post_id':          p.get('post_id'),
            'source':           p.get('source', 'top'),
            'title':            p.get('title', '')[:300],
            'url':              p.get('url', '')[:500],
            'score':            score,
            'num_comments':     comments,
            'engagement_score': engagement_score,
            'author':           p.get('author'),
            'created_date':     created_date,
            'created_hour':     created_hour,
            'created_weekday':  created_weekday,
            'fetched_at':       p.get('fetched_at'),
            'tool_mentions':    json.dumps(tool_mentions_dict),
            'mention_count':    len(tool_mentions_dict)
        })

    print(f"Transformed {len(transformed)} posts")
    return transformed

def load_to_duckdb(posts: list, db_path: str = "data/reddit.duckdb"):
    """Load transformed posts into DuckDB"""
    os.makedirs(os.path.dirname(db_path), exist_ok=True)
    conn = duckdb.connect(db_path)

    conn.execute("DROP TABLE IF EXISTS posts")
    conn.execute("""
        CREATE TABLE posts (
            post_id          VARCHAR,
            source           VARCHAR,
            title            VARCHAR,
            url              VARCHAR,
            score            INTEGER,
            num_comments     INTEGER,
            engagement_score DOUBLE,
            author           VARCHAR,
            created_date     VARCHAR,
            created_hour     INTEGER,
            created_weekday  VARCHAR,
            fetched_at       VARCHAR,
            tool_mentions    VARCHAR,
            mention_count    INTEGER
        )
    """)

    conn.execute("DROP TABLE IF EXISTS tool_mentions")
    conn.execute("""
        CREATE TABLE tool_mentions (
            post_id    VARCHAR,
            tool       VARCHAR,
            category   VARCHAR,
            source     VARCHAR,
            score      INTEGER,
            fetched_at VARCHAR
        )
    """)

    for p in posts:
        title_clean = str(p['title']).replace("'", "''")
        author_clean = str(p['author']).replace("'", "''")
        url_clean = str(p['url']).replace("'", "''")
        conn.execute(f"""
            INSERT INTO posts VALUES (
                '{p['post_id']}',
                '{p['source']}',
                '{title_clean}',
                '{url_clean}',
                {p['score']},
                {p['num_comments']},
                {p['engagement_score']},
                '{author_clean}',
                '{p['created_date']}',
                {p['created_hour'] or 0},
                '{p['created_weekday'] or ''}',
                '{p['fetched_at']}',
                '{p['tool_mentions'].replace("'", "''")}',
                {p['mention_count']}
            )
        """)

        tool_dict = json.loads(p['tool_mentions'])
        for tool, category in tool_dict.items():
            conn.execute(f"""
                INSERT INTO tool_mentions VALUES (
                    '{p['post_id']}',
                    '{tool}',
                    '{category}',
                    '{p['source']}',
                    {p['score']},
                    '{p['fetched_at']}'
                )
            """)

    post_count = conn.execute("SELECT COUNT(*) FROM posts").fetchone()[0]
    mention_count = conn.execute("SELECT COUNT(*) FROM tool_mentions").fetchone()[0]
    print(f"DuckDB: {post_count} posts, {mention_count} tool mentions")
    conn.close()
    return post_count

if __name__ == "__main__":
    posts = load_from_s3(days=7)
    if not posts:
        posts = load_local_files()
    transformed = transform(posts)
    load_to_duckdb(transformed)