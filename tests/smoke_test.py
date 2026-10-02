"""End-to-end smoke test against a running stack (rasa run + rasa run actions + mock API).

Usage: python tests/smoke_test.py [http://localhost:5005]
Plays scripted conversations through the REST channel and prints every bot reply.
"""
import json
import sys
import urllib.request
import uuid

RASA = (sys.argv[1] if len(sys.argv) > 1 else "http://localhost:5005").rstrip("/")

CONVERSATIONS = {
    "English order tracking": ["hi", "where is my order?", "48213", "no thanks"],
    "Arabic order in one message": ["الأوردر رقم 77777 فين"],
    "Arabic digits + unknown order": ["طلبي فين؟", "٩٩٩٩٩"],
    "Complaint with mid-form FAQ, bad phone, then valid": [
        "I have a problem with my order",
        "how can I pay?",
        "my package arrived broken",
        "12345",
        "01012345678",
    ],
    "Arabic complaint via button payload": [
        "عندي مشكلة في الطلب",
        '/inform{"issue_type": "delivery"}',
        "رقمي 01198765432",
    ],
    "Cancel mid-form": ["track my order", "never mind"],
    "Handoff + FAQ + bot challenge": ["are you a bot?", "مواعيد العمل ايه", "talk to an agent"],
}


def send(sender: str, message: str) -> list:
    req = urllib.request.Request(
        f"{RASA}/webhooks/rest/webhook",
        data=json.dumps({"sender": sender, "message": message}).encode(),
        headers={"Content-Type": "application/json"},
    )
    with urllib.request.urlopen(req, timeout=60) as resp:
        return json.loads(resp.read())


for title, turns in CONVERSATIONS.items():
    sender = uuid.uuid4().hex
    print(f"\n=== {title}")
    for msg in turns:
        print(f"  user: {msg}")
        for reply in send(sender, msg):
            print(f"  bot : {reply.get('text', '')}")
            for b in reply.get("buttons", []):
                print(f"        [{b['title']}]")
