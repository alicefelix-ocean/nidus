import requests
import os
import json
from google import genai
from supabase import create_client
from datetime import datetime, timezone

client_gemini = genai.Client(api_key=os.environ["GEMINI_API_KEY"])
supabase = create_client(os.environ["SUPABASE_URL"], os.environ["SUPABASE_KEY"])

headers = {"User-Agent": "Nidus/1.0 (marrow research tool)"}
subreddits = ["medicalschoolindia", "indianmedschool"]

posts = []
for sub in subreddits:
    url = f"https://www.reddit.com/r/{sub}/hot.json?limit=10"
    try:
        r = requests.get(url, headers=headers)
        for item in r.json()["data"]["children"]:
            p = item["data"]
            posts.append({"title": p["title"], "ups": p["ups"], "subreddit": sub})
    except Exception as e:
        print(f"Skipping {sub}: {e}")

print(f"\nScoring {len(posts)} posts...\n")

now = datetime.now(timezone.utc)
week_label = f"{now.isocalendar()[0]}-W{now.isocalendar()[1]:02d}"

for post in posts:
    prompt = f"""You are analysing posts from Indian medical students studying for NEET PG and INI-CET exams.

Post: "{post['title']}"

Respond in JSON only, no explanation:
{{"sentiment": "positive or negative or neutral", "topic": "one of: Marrow/PrepLadder/Grand Tests/Stress & burnout/Revision strategy/Subject tips/Rank anxiety/Study hours/Exam news/Other", "intent": "one of: Switching Risk/Struggling/Praising/Reacting to News", "score": 0-100}}"""

    try:
        response = client_gemini.models.generate_content(model="gemini-2.5-flash", contents=prompt)
        text = response.text.strip().replace("```json", "").replace("```", "").strip()
        result = json.loads(text)
        row = {
            "title": post["title"],
            "sentiment": result["sentiment"],
            "topic": result["topic"],
            "intent": result["intent"],
            "score": int(result["score"]),
            "ups": post["ups"],
            "subreddit": post["subreddit"],
            "source": "Reddit",
            "week": week_label,
            "fetched_at": now.isoformat()
        }
        supabase.table("posts").insert(row).execute()
        print(f"[{result['sentiment'].upper()}] [{result['intent']}] [{result['topic']}] {post['title'][:70]}")
    except Exception as e:
        print(f"Error: {e}")

print(f"\nDone — week {week_label}")