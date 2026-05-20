import duckdb
import json

conn = duckdb.connect('data/reddit.duckdb')

# Find posts with 'r' in tool_mentions
results = conn.execute("""
    SELECT title, tool_mentions 
    FROM posts 
    WHERE tool_mentions LIKE '%"r"%'
    LIMIT 10
""").df()

print(f"Posts with 'r' mention: {len(results)}")
for _, row in results.iterrows():
    print(f"\nTitle: {row['title'][:80]}")
    print(f"Mentions: {row['tool_mentions']}")

conn.close()