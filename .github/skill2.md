# Redis Sprint 3 — Film Review Platform

## Caching & Token Lifecycle

You are working on my existing **Film Review Platform FastAPI project**.

Implement today's Redis exercise completely in the existing codebase.

### IMPORTANT RULES

1. **First inspect the existing project structure and implementation.**
2. Do not rewrite working code unnecessarily.
3. Follow the architecture already used in the project:
   **Routes → Handlers → Services → DAOs**
4. Database access must remain inside the **DAO layer**.
5. Use the existing **centralized config/settings object** for Redis configuration.
6. Keep the implementation beginner-friendly and consistent with the code I have already learned.
7. Do not introduce advanced Redis patterns or libraries that I have not learned.
8. Make the implementation production-clean but simple.
9. Do not hardcode configuration values that should come from settings.
10. After implementation, verify all affected flows and fix any errors.

---

# Topics I Have Learned — MUST USE THESE ONLY

I have already learned these Redis topics and today's implementation must be based on them:

### 1. Redis basics

* Redis is an in-memory data store.
* PostgreSQL remains the main persistent database.
* Redis is used for fast temporary/cache data.

### 2. Redis data types

* String
* Hash
* List
* Set
* Sorted Set

For today's exercise, use the **Redis String type** for serialized cached film-list results and refresh-token storage.

### 3. Async Redis with Python

Use the async Redis client:

```python
import redis.asyncio as redis
```

Use `await` for Redis operations.

### 4. Redis connection configuration

Redis must be configured using the existing centralized settings object.

Example:

```python
redis_client = redis.from_url(
    settings.REDIS_URL,
    decode_responses=True,
    max_connections=10,
)
```

Use the project's existing configuration pattern rather than creating a separate configuration system.

### 5. Connection pooling

The Redis client must be created once and shared.

Use:

```python
max_connections=10
```

The Redis connection pool must not be created separately for every request.

### 6. Read-through caching

Use this flow:

```text
Request
   ↓
Redis
   ↓
Cache HIT ─────→ Return cached result
   ↓ MISS
PostgreSQL
   ↓
Store result in Redis
   ↓
Return result
```

The first request should query PostgreSQL.

The next request within the TTL should return the Redis result without querying PostgreSQL.

### 7. TTL

Use Redis TTL for cached data.

Example:

```python
await redis_client.set(
    key,
    value,
    ex=60,
)
```

Use a configurable TTL from the centralized settings if the existing configuration structure supports it.

Do not leave cached film lists without expiration.

### 8. Cache invalidation

When film data changes:

* Film created
* Film updated
* Film soft-deleted

Remove the relevant film-list cache entries from Redis.

The next film-list request must query PostgreSQL again and rebuild the cache.

### 9. Refresh token storage in Redis

Store the refresh token in Redis when it is issued.

The Redis TTL must match the refresh token's expiration time.

Example concept:

```text
refresh_token:<token> → user/session information
TTL → same lifetime as refresh token
```

### 10. Token/session invalidation

When the user logs out:

```text
Logout
  ↓
Delete refresh token from Redis
  ↓
Refresh token can no longer be used
```

A refresh token that was deleted from Redis must be rejected even if its JWT expiration time has not been reached.

---

# TASK 1 — Redis Connection

Create/reuse a Redis connection using the existing centralized settings.

Requirements:

* Use `redis.asyncio`.
* Use the existing `settings` object.
* Use `decode_responses=True`.
* Configure:

```python
max_connections=10
```

* Create the Redis client/pool once.
* Reuse the same client across requests.
* Do NOT create a Redis connection inside each endpoint/request.
* Do NOT repeatedly open and close Redis connections for every request.

Follow the existing project structure and dependency/lifespan pattern where appropriate.

---

# TASK 2 — Film List Read-Through Cache

Find the existing **film list endpoint** and implement read-through caching.

The logic must be:

```text
GET /films

      ↓

Check Redis cache

      ↓
 ┌───────────────┐
 │ Cache exists? │
 └───────────────┘
      ↓       ↓
     YES      NO
      ↓       ↓
 Return     Query DAO
 cached       ↓
 result     Serialize result
                ↓
             Store Redis
             with TTL
                ↓
             Return result
```

### Requirements

* The DAO must still be responsible for PostgreSQL access.
* Check Redis before calling the DAO.
* If the cache exists:

  * Deserialize it.
  * Return it.
  * Do NOT query PostgreSQL.
* If the cache does not exist:

  * Call the existing DAO.
  * Serialize the result.
  * Store it in Redis.
  * Apply a TTL.
  * Return the result.

Use a clear cache key such as:

```text
films:list
```

If the existing film-list endpoint supports filters such as genre/year, make sure different filter combinations do not incorrectly share the same cache entry.

For example:

```text
films:list
films:list:genre=action
films:list:year=2020
```

Use a deterministic key based on the actual query parameters.

---

# TASK 3 — Cache Serialization

Redis String values should contain the serialized film-list result.

Use the project's existing Pydantic response schemas for serialization where appropriate.

The general flow should be:

```text
Pydantic response data
        ↓
serialize
        ↓
Redis String
        ↓
deserialize
        ↓
response schema
```

Do not store raw SQLAlchemy ORM objects directly in Redis.

Make sure the cached response returned to the API has the same structure as the normal database response.

---

# TASK 4 — Cache Invalidation

Whenever a film is:

* created
* updated
* soft-deleted

invalidate the film-list cache.

The important requirement is:

```text
Film changed
    ↓
Remove affected film-list cache
    ↓
Next GET /films
    ↓
Cache MISS
    ↓
Fetch latest data from PostgreSQL
    ↓
Store fresh result in Redis
```

If the application has multiple film-list cache keys because of filters, make sure **all cache entries that could contain the affected film are removed**.

Do not leave stale film-list results after a create/update/delete operation.

Keep this logic in the appropriate existing service/handler layer rather than putting database logic into Redis code.

---

# TASK 5 — Refresh Token Storage in Redis

Find the existing JWT refresh-token implementation.

Change the refresh-token lifecycle so that issued refresh tokens are stored in Redis.

When a refresh token is created:

```text
Create refresh JWT
       ↓
Store refresh token in Redis
       ↓
Set Redis TTL equal to refresh token expiry
```

Use the refresh token itself or the existing token/session identifier as the Redis key according to the current project design.

The important requirement is:

```text
Redis TTL = refresh token lifetime
```

Do not create a refresh token that exists in Redis forever.

---

# TASK 6 — Refresh Token Validation

Find the existing refresh-token endpoint/flow.

Before accepting a refresh token:

1. Validate the JWT normally.
2. Check that the token exists in Redis.
3. If the token does not exist in Redis, reject it.
4. If it exists, continue the refresh flow.

This provides server-side revocation.

Therefore:

```text
JWT valid + Redis exists
        ↓
       ACCEPT

JWT valid + Redis missing
        ↓
       REJECT
```

The JWT expiration must still be validated. Redis is the additional server-side invalidation mechanism.

---

# TASK 7 — /logout Endpoint

Implement:

```text
POST /logout
```

The endpoint must:

1. Require a valid access token.
2. Identify the authenticated user.
3. Find the refresh token associated with the user's current session according to the existing authentication design.
4. Delete that refresh token from Redis.
5. Return a success response.

After logout:

```text
refresh token
      ↓
Redis key deleted
      ↓
Attempt to use refresh token
      ↓
Redis lookup fails
      ↓
Reject refresh request
```

The important requirement is that logout must actually revoke the refresh token server-side.

---

# TASK 8 — Do Not Break Existing Authentication

Preserve the existing:

* Access token generation
* Refresh token generation
* JWT validation
* Password hashing
* Authentication dependency
* RBAC
* User DAO
* Existing route structure

Only modify the refresh-token lifecycle where necessary to integrate Redis.

Do not replace the existing JWT authentication system with Redis sessions.

Redis should provide **refresh-token storage and revocation**, while JWT continues to provide token authentication/expiration.

---

# TASK 9 — Error Handling

Handle Redis failures cleanly and consistently with the existing project.

Do not expose internal Redis errors directly to API users.

Follow the project's existing exception/error-handling style.

Do not add unnecessary custom exception systems if the project already has an appropriate pattern.

---

# TASK 10 — Verification

After implementation, verify all of these scenarios.

### Film caching

#### First request

```text
GET /films
→ Redis MISS
→ PostgreSQL queried
→ Result stored in Redis
→ Response returned
```

#### Second request

```text
GET /films
→ Redis HIT
→ PostgreSQL NOT queried
→ Cached response returned
```

#### After TTL expires

```text
GET /films
→ Redis MISS
→ PostgreSQL queried
→ New cache created
```

### Film invalidation

Test:

```text
Create film
→ film-list cache removed
```

```text
Update film
→ film-list cache removed
```

```text
Soft-delete film
→ film-list cache removed
```

Then:

```text
GET /films
→ Redis MISS
→ Latest PostgreSQL data
→ New cache
```

### Refresh token

Test:

```text
Login
→ Refresh token created
→ Refresh token stored in Redis
→ Redis TTL matches token expiry
```

Then:

```text
Valid refresh token
→ Redis exists
→ Refresh succeeds
```

### Logout

Test:

```text
Login
→ Refresh token stored in Redis

POST /logout
→ Refresh token deleted from Redis

Use same refresh token
→ Redis MISS
→ Request rejected
```

Also verify that an expired Redis refresh-token entry cannot be used.

---

# CODE QUALITY REQUIREMENTS

Before finishing:

* Follow the existing project naming conventions.
* Keep responsibilities separated.
* Do not put PostgreSQL queries outside DAOs.
* Do not create Redis connections per request.
* Reuse the shared Redis client.
* Use async Redis operations.
* Use TTL.
* Use cache invalidation.
* Keep JWT validation.
* Keep existing authentication/RBAC behavior.
* Avoid unnecessary refactoring.
* Remove unused imports.
* Add clear comments only where they help explain the Redis flow.
* Ensure the project still starts successfully.
* Ensure existing endpoints are not broken.

---

# FINAL REPORT

After completing the implementation, give me a concise report containing:

1. Files changed
2. What was implemented in each file
3. Redis cache flow
4. Refresh-token Redis flow
5. Logout/revocation flow
6. Tests/checks performed
7. Any assumptions made

Most importantly, **do not implement concepts outside the Redis topics I have already learned unless absolut**
