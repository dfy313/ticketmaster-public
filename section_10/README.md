# 📺 Ticketmaster – Section 10

In this section, we improve search performance by placing a **CloudFront CDN** in front of the `/search/{term}` endpoint. This caches repeated queries, reducing OpenSearch load and improving latency.
We’ll set up a CloudFront distribution, apply caching policies, verify cache hits via headers, and update the Event Discovery Service to route traffic through the CDN.

<div align="center">
    <img src="./section_10_design.png" alt="System Architecture Diagram" width="1500"/>
</div>

## 🎥 Video Walkthrough

**Title:** Ticketmaster – Section 10  
**Link:** [Watch on Udemy](https://www.udemy.com)

# ⚙️ Instructions and Commands

From project root `~Desktop/ticketmaster_demo`:

### 1. Configure Environment Variables

After adding `SEARCH_CDN_URL` to your environment file, reload the variables into your current shell session:

```bash
source .ticketmaster_env
```

- <img src="https://raw.githubusercontent.com/PowerShell/PowerShell/master/assets/powershell_128.svg" width="18" /> On **Windows PowerShell**:
  ```bash
  . .\.ticketmaster_env.ps1
  ```

### 2. Query Search via CDN

Issue a request to the CDN-backed search endpoint for the term `bob`:

```bash
curl -i $SEARCH_CDN_URL/search/bob
```

- <img src="https://raw.githubusercontent.com/PowerShell/PowerShell/master/assets/powershell_128.svg" width="18" /> On **Windows PowerShell**:
  ```bash
  curl.exe -i "${SEARCH_CDN_URL}/search/bob"
  ```

### 3. Repeat Search to Observe Cache HIT

Re-run the same request from **[Step 2](#2-query-search-via-cdn)**:

> _This time, the response should be served from cache._

### 4. Add "Bob Marley Tribute" Event to Database

Use a temporary MySQL client container to connect to your database:

```bash
docker run --rm -it \
  -e MYSQL_PWD='Password100!' \
  mysql:8.0 \
  mysql -h $TICKETMASTER_DB_URL -u admin
```

- <img src="https://raw.githubusercontent.com/PowerShell/PowerShell/master/assets/powershell_128.svg" width="18" /> On **Windows PowerShell**:
  ```bash
  docker run --rm -it `
    -e MYSQL_PWD='Password100!' `
    mysql:8.0 `
    mysql -h $TICKETMASTER_DB_URL -u admin
  ```

Once connected, switch to the `ticketmaster_db` database:

```bash
USE ticketmaster_db;
```

Insert a new event for **"Bob Marley Tribute"**:

```sql
INSERT INTO Events (eventId, name, description, date, createdAt)
VALUES
    ('4L', 'Bob Marley Tribute', 'A tribute concert celebrating the legacy of reggae icon Bob Marley.', '2030-07-11 17:00:00', NOW());
```

Verify that the event was inserted successfully:

```sql
SELECT * FROM Events;
```

Exit the MySQL session:

```bash
exit
```

### 5. Index "Bob Marley Tribute" Event in OpenSearch

Add a new document to the `ticketmaster_index`:

```bash
curl -u admin:Password100! -X PUT \
  -H "Content-Type: application/json" \
  $OPENSEARCH_URL/ticketmaster_index/_doc/4 \
  -d '{
    "eventId": "4L",
    "name": "Bob Marley Tribute",
    "description": "A tribute concert celebrating the legacy of reggae icon Bob Marley.",
    "date": "2030-07-11 17:00:00"
  }'
```

- <img src="https://raw.githubusercontent.com/PowerShell/PowerShell/master/assets/powershell_128.svg" width="18" /> On **Windows PowerShell**:
  ```bash
  curl.exe -u "admin:Password100!" -X PUT `
    -H "Content-Type: application/json" `
    "{$OPENSEARCH_URL}/ticketmaster_index/_doc/4" `
    -d '{
      \"eventId\": \"4L\",
      \"name\": \"Bob Marley Tribute\",
      \"description\": \"A tribute concert celebrating the legacy of reggae icon Bob Marley.\",
      \"date\": \"2030-07-11 17:00:00\"
    }'
  ```

Query OpenSearch to confirm the event was indexed successfully:

```bash
curl -u 'admin:Password100!' -X GET \
  -H "Content-Type: application/json" \
  $OPENSEARCH_URL/ticketmaster_index/_search \
  -d '{
    "query": {
      "match_phrase": {
        "name": "bob"
      }
    }
  }'
```

- <img src="https://raw.githubusercontent.com/PowerShell/PowerShell/master/assets/powershell_128.svg" width="18" /> On **Windows PowerShell**:
  ```bash
  curl.exe -u "admin:Password100!" -X GET `
    -H "Content-Type: application/json" `
    "${OPENSEARCH_URL}/ticketmaster_index/_search" `
    -d '{
      \"query\": {
        \"match_phrase\": {
          \"name\": \"bob\"
        }
      }
    }'
  ```

### 6. Query Search via CDN to Observe Stale Cache

After adding the new event to the database and indexing it in OpenSearch, re-run the request from **[Step 2](#2-query-search-via-cdn)**:

> _The response should still be stale and served from the CDN cache (cache HIT)._

After updating the search service Lambda to return a shorter TTL via the `Cache-Control` header, re-run the same request from **[Step 2](#2-query-search-via-cdn)**:

> _The stale response should still be served from cache until the existing cache entry expires._

### 7. Query Search via CDN After Cache Invalidation

After creating an invalidation for `/search/*`, re-run the request from **[Step 2](#2-query-search-via-cdn)**:

> _The response should result in a cache MISS and return the updated results (with a new TTL applied)._

Before the 60-second TTL expires, re-run the same request from **[Step 2](#2-query-search-via-cdn)**:

> _The response should be served from cache (cache HIT) with the updated results._

After the TTL expires, re-run the request from **[Step 2](#2-query-search-via-cdn)** again:

> _The response should result in another cache MISS._

<br>
