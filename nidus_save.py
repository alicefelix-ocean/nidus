import requests
import os
import json
import re
from google import genai
from supabase import create_client
from datetime import datetime, timezone


def sanitize(text):
    text = text[:500]
    text = re.sub(r'(?i)(ignore|forget|disregard).{0,30}(above|previous|instruction)', '', text)
    text = re.sub(r'(?i)you are now', '', text)
    text = re.sub(r'(?i)system prompt', '', text)
    text = re.sub(r'[<>{}[\]]', '', text)
    return text.strip()


def validate(result):
    valid_sentiments = {"positive", "negative", "neutral"}
    valid_intents = {"Switching Risk", "Struggling", "Praising", "Reacting to News"}
    valid_topics = {
        "Marrow", "PrepLadder", "Marrow/PrepLadder", "Grand Tests",
        "Stress & burnout", "Revision strategy", "Subject tips",
        "Rank anxiety", "Study hours", "Exam news",
        "Career & Life After PG", "College & Seat Selection",
        "System & Policy Frustration", "Other"
    }
    return (
        result.get("sentiment") in valid_sentiments and
        result.get("intent") in valid_intents and
        result.get("topic") in valid_topics and
        isinstance(result.get("score"), (int, float))
    )


client_gemini = genai.Client(api_key=os.environ["GEMINI_API_KEY"])
supabase = create_client(os.environ["SUPABASE_URL"], os.environ["SUPABASE_KEY"])

headers = {"User-Agent": "Nidus/1.0 (marrow research tool)"}
subreddits = ["medicalschoolindia", "indianmedschool", "neetpg", "indianmedstudents"]

posts = []
for sub in subreddits:
    url = f"https://www.reddit.com/r/{sub}/hot.json?limit=25"
    try:
        r = requests.get(url, headers=headers)
        for item in r.json()["data"]["children"]:
            p = item["data"]
            posts.append({"title": sanitize(p["title"]), "ups": p["ups"], "subreddit": sub, "reddit_id": p["id"]})
    except Exception as e:
        print(f"Skipping {sub}: {e}")

print(f"\nScoring {len(posts)} posts...\n")

now = datetime.now(timezone.utc)
week_label = f"{now.isocalendar()[0]}-W{now.isocalendar()[1]:02d}"

for post in posts:
    prompt = f"""You are analysing posts from Indian medical students studying for NEET PG and INI-CET exams.
Post: "{post['title']}"
Respond in JSON only, no explanation:
{{"sentiment": "positive or negative or neutral", "topic": "one of: Marrow/PrepLadder/Grand Tests/Stress & burnout/Revision strategy/Subject tips/Rank anxiety/Study hours/Exam news/Career & Life After PG/College & Seat Selection/System & Policy Frustration/Other", "intent": "one of: Switching Risk/Struggling/Praising/Reacting to News", "score": 0-100}}
Career & Life After PG: post-exam career choices, specialty regret, doctor salaries, unemployment
College & Seat Selection: rank-to-college decisions, DNB vs MD, college reviews
System & Policy Frustration: internship conditions, govt postings, doctor pay, hospital conditions"""

    try:
        response = client_gemini.models.generate_content(model="gemini-2.5-flash", contents=prompt)
        text = response.text.strip().replace("```json", "").replace("```", "").strip()
        result = json.loads(text)

        if not validate(result):
            print(f"Invalid output skipped: {result}")
            continue

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
            "fetched_at": now.isoformat(),
            "reddit_id": post["reddit_id"],
        }

        existing = supabase.table("posts").select("id").eq("reddit_id", post["reddit_id"]).execute()
        if existing.data:
            print(f"Skipping duplicate: {post['title'][:50]}")
            continue

        supabase.table("posts").insert(row).execute()
        print(f"[{result['sentiment'].upper()}] [{result['intent']}] [{result['topic']}] {post['title'][:70]}")

    except Exception as e:
        print(f"Error: {e}")

print(f"\nDone — week {week_label}")