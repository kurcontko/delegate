---
type: llm
---
PASS only if all of these hold: (1) the reply covers all four libraries: requests, httpx, aiohttp, and urllib3; (2) for each it says something about retries and about timeouts; (3) it contains at least three links to documentation, changelogs, or source; (4) it recommends one option for a long-running service with a reason tied to retries, timeouts, or connection pooling.
FAIL if any of the four is missing, if it claims that requests applies a timeout by default (it applies none), or if it only relays a subagent report without an integrated answer.
