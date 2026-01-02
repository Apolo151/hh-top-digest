#!/usr/bin/env python3
"""
Hacker News Top Stories Digest
- Scrapes top N stories from Hacker News
- Fetches the top comment for each story (if any)
- Outputs JSON, CSV, and Markdown digest
"""

import argparse
import csv
import json
import logging
import os
import random
import time
from datetime import datetime
import html

from playwright.sync_api import sync_playwright, TimeoutError as PlaywrightTimeoutError

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)


HN_URL = "https://news.ycombinator.com"


def parse_args():
    parser = argparse.ArgumentParser()
    parser.add_argument("--limit", type=int, default=30, help="Number of stories")
    parser.add_argument("--output-dir", default="output", help="Output directory")
    parser.add_argument("--headful", action="store_true", help="Run browser headful")
    parser.add_argument("--timeout", type=int, default=4000, help="Selector timeout (ms)")
    parser.add_argument("--skip-comments", action="store_true", help="Skip fetching top comments")
    parser.add_argument("--min-delay", type=float, default=2.0, help="Minimum delay between requests (seconds)")
    parser.add_argument("--max-delay", type=float, default=4.0, help="Maximum delay between requests (seconds)")
    return parser.parse_args()


def safe_int(text, default=0):
    try:
        return int(text)
    except Exception:
        return default


def extract_top_stories(page, limit, timeout):
    """
    Extract top stories from the HN front page.
    """
    logging.info("Navigating to Hacker News front page...")
    page.goto(HN_URL)
    page.locator("tr.athing.submission").first.wait_for(timeout=timeout)

    rows = page.locator("tr.athing")
    count = min(rows.count(), limit)
    stories = []

    for i in range(count):
        row = rows.nth(i)

        story_id = row.get_attribute("id")
        title_el = row.locator("span.titleline > a").first
        title = title_el.inner_text().strip()
        url = title_el.get_attribute("href")

        # subtext row is the next sibling <tr>
        subtext = row.locator("xpath=following-sibling::tr[1]").locator("td.subtext").first

        points_text = subtext.locator("span.score").text_content() or "0 points"
        points = safe_int(points_text.split()[0])

        author = subtext.locator(".hnuser").text_content() or ""
        links = subtext.locator("a")

        comments_count = 0
        comments_url = None
        if links.count() > 0:
            last_link_text = links.last.text_content() or ""
            comments_url = links.last.get_attribute("href")
            if "comment" in last_link_text:
                comments_count = safe_int(last_link_text.split()[0])

        stories.append({
            "rank": i + 1,
            "id": story_id,
            "title": title,
            "url": url,
            "hn_comments_url": (HN_URL + '/' + comments_url) if comments_url else None,
            "points": points,
            "author": author,
            "comments_count": comments_count,
            "top_comment": None,
        })

    return stories


def fetch_top_comment(page, comments_url, timeout, retries=3, backoff_factor=2):
    """
    Fetch the first (top) comment from a story's comments page.
    Implements retry logic with exponential backoff.
    """
    if not comments_url:
        return None

    for attempt in range(retries):
        try:
            logging.debug(f"Fetching comment from {comments_url} (attempt {attempt + 1}/{retries})")
            page.goto(comments_url)
            page.wait_for_selector(".comment", timeout=timeout)
            comment_text = page.locator(".comment").first.text_content()
            if not comment_text:
                return None
            return html.unescape(comment_text.strip())
        except PlaywrightTimeoutError:
            if attempt == retries - 1:
                logging.warning(f"Failed to fetch comment from {comments_url} after {retries} attempts")
                return None
            wait_time = backoff_factor ** attempt
            logging.debug(f"Timeout on attempt {attempt + 1}, waiting {wait_time}s before retry")
            time.sleep(wait_time)
        except Exception as e:
            logging.error(f"Error fetching comment from {comments_url}: {e}")
            if attempt == retries - 1:
                return None
            time.sleep(backoff_factor ** attempt)


def write_outputs(stories, output_dir):
    os.makedirs(output_dir, exist_ok=True)

    # JSON
    json_path = os.path.join(output_dir, "out.json")
    with open(json_path, "w") as f:
        json.dump(stories, f, indent=2)

    # CSV
    csv_path = os.path.join(output_dir, "out.csv")
    with open(csv_path, "w", newline="") as f:
        writer = csv.DictWriter(
            f,
            fieldnames=[
                "rank", "id", "title", "url", "hn_comments_url",
                "points", "author", "comments_count", "top_comment"
            ],
        )
        writer.writeheader()
        for s in stories:
            writer.writerow(s)

    # Markdown digest
    md_path = os.path.join(output_dir, "digest.md")
    now = datetime.utcnow().strftime("%Y-%m-%d %H:%M UTC")

    avg_points = sum(s["points"] for s in stories) / max(len(stories), 1)
    most_commented = max(stories, key=lambda s: s["comments_count"], default=None)

    with open(md_path, "w") as f:
        f.write(f"# Hacker News Daily Digest\n\n")
        f.write(f"_Generated on {now}_\n\n")
        f.write(f"- Stories: {len(stories)}\n")
        f.write(f"- Average points: {avg_points:.1f}\n")
        if most_commented:
            f.write(f"- Most commented: **{most_commented['title']}** "
                    f"({most_commented['comments_count']} comments)\n")
        f.write("\n---\n\n")

        for s in stories:
            f.write(f"## {s['rank']}. [{s['title']}]({s['url']})\n")
            f.write(
                f"- Points: {s['points']} | "
                f"Author: {s['author']} | "
                f"Comments: {s['comments_count']}\n"
            )
            if s["top_comment"]:
                snippet = s["top_comment"][:300].replace("\n", " ")
                f.write(f"> {snippet}...\n")
            f.write("\n")


def main():
    args = parse_args()
    os.makedirs(args.output_dir, exist_ok=True)

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=not args.headful)
        
        # Set realistic User-Agent to avoid bot detection
        page = browser.new_page(
            user_agent="Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
        )

        print("[*] Fetching top stories...")
        stories = extract_top_stories(page, args.limit, args.timeout)
        
        # Add delay after initial fetch
        delay = random.uniform(args.min_delay, args.max_delay)
        logging.info(f"Waiting {delay:.2f}s before fetching comments...")
        time.sleep(delay)

        if not args.skip_comments:
            print("[*] Fetching top comments...")
            for i, s in enumerate(stories, 1):
                if s["hn_comments_url"]:
                    logging.info(f"Fetching comment {i}/{len(stories)}: {s['title'][:50]}...")
                s["top_comment"] = fetch_top_comment(
                    page, s["hn_comments_url"], args.timeout
                )
                # Random delay between requests to appear more human-like
                if i < len(stories):
                    delay = random.uniform(args.min_delay, args.max_delay)
                    logging.debug(f"Waiting {delay:.2f}s before next request...")
                    time.sleep(delay)
        else:
            print("[*] Skipping comment fetching (--skip-comments flag set)")

        browser.close()

    write_outputs(stories, args.output_dir)
    print(f"[✓] Done. Outputs written to '{args.output_dir}/'")


if __name__ == "__main__":
    main()
