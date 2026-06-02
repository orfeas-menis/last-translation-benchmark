#!/usr/bin/env python3
import sqlite3
import json
import argparse
import collections

args = argparse.ArgumentParser(
    description="Extract confirmed submissions from sqlite database."
)
args.add_argument("--db", help="Path to the .sqlite file", default="data/db.sqlite")
args = args.parse_args()


conn = sqlite3.connect(args.db)
cur = conn.cursor()

# loading
cur.execute("SELECT data FROM submissions")
submissions = [
    json.loads(row[0])
    for row in cur.fetchall()
]
cur.execute("SELECT data FROM users")
users = [
    json.loads(row[0])
    for row in cur.fetchall()
]
username_to_user = {x["username"]: x for x in users}
conn.close()

print(collections.Counter([x["status"] for x in submissions]), "\n\n")

# analysis

submissions_pending = [
    x for x in submissions if x["status"] == "pending"
]

pending_languages = collections.Counter([x["source_lang"] for x in submissions_pending]+[x["target_lang"] for x in submissions_pending])

for lang, count in pending_languages.most_common():
    if lang == "English":
        continue
    print(f"{lang:>25}: {count} pending")


print("\n\nSuggestions for who can review what")
# who can review what
users = collections.defaultdict(set)
for submission in submissions:
    if submission["status"] == "accepted":
        continue
    users[submission["username"]].add(submission["source_lang"])
    users[submission["username"]].add(submission["target_lang"])

for user, langs in users.items():
    submissions_feasible = [
        x for x in submissions_pending
        if x["source_lang"] in langs and x["target_lang"] in langs and x["username"] != user]
    if not submissions_feasible:
        continue
    print(f"{username_to_user[user]['name']} can review:")
    for submission in submissions_feasible:
        submission["covered"] = True
        print(f"      (#{submission['id']}) {submission['source_lang']}->{submission['target_lang']} by {username_to_user[submission['username']]['name']}")
    if "reviewer" not in username_to_user[user]["roles"]:
        # red color
        print("\033[31m      ..but they're not a reviewer yet! \033[0m")

print("\n\nSubmissions that are not covered by any reviewer:")
for submission in submissions_pending:
    if "covered" not in submission:
        print(f"(#{submission['id']}) {submission['source_lang']}->{submission['target_lang']} by {username_to_user[submission['username']]['name']}")