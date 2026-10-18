# /query — example fixture

> **This is an example fixture, not a live production response.**
> The response below uses mocked data. The `status` and citation shape are real;
> the answer text and scores are not. Do not treat as eval evidence.

## Request
```http
POST /query HTTP/1.1
Authorization: Bearer <task2-or-task3-token>
Content-Type: application/json

{"question": "How do I reset a password?"}

Response (mocked QA — insufficient_evidence)
json
{
  "question": "How do I reset a password?",
  "status": "insufficient_evidence",
  "answer": "Not enough evidence in the knowledge base to answer.",
  "sources": [],
  "image_refs": [],
  "escalation_required": true
}
Response (mocked QA — answered)
json
{
  "question": "How do I reset a password?",
  "status": "answered",
  "answer": "[SIMULATED] Answer derived from retrieved evidence. [chunk_id=1]",
  "sources": [
    {"title": null, "url": "https://support.brilliantdirectories.com/article/a", "section": "Steps", "chunk_id": 1}
  ],
  "image_refs": [],
  "escalation_required": false
}
