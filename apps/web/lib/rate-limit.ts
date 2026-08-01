// In-memory token-bucket rate limiter for the catchment point-in-polygon
// check endpoint (the only endpoint that does real geometry work per
// request). This is process-local state: on Vercel Fluid Compute a single
// warm instance handles a burst of requests from the same caller reasonably
// well, but a cold start or a second concurrent instance gets its own
// bucket. That is an acceptable trade-off for a portfolio deployment; a
// production system serving real traffic would back this with a shared
// store (e.g. Upstash Redis) so all instances share one bucket. Not adding
// that dependency here since it cannot be wired to anything real in this
// environment.
type Bucket = {
  tokens: number;
  lastRefillMs: number;
};

const buckets = new Map<string, Bucket>();

const CAPACITY = 20;
const REFILL_PER_MS = 10 / 60_000; // 10 tokens per minute

/** Periodically drop stale buckets so this Map does not grow without bound
 * over the lifetime of a warm serverless instance. */
const MAX_BUCKETS = 5000;

export type RateLimitResult = {
  allowed: boolean;
  remaining: number;
  retryAfterSeconds: number;
};

export function checkRateLimit(key: string, cost = 1): RateLimitResult {
  const now = Date.now();
  let bucket = buckets.get(key);
  if (!bucket) {
    if (buckets.size >= MAX_BUCKETS) {
      // Cheap eviction: drop the oldest-looking entry rather than tracking
      // full LRU order, this endpoint's traffic does not warrant more.
      const firstKey = buckets.keys().next().value;
      if (firstKey !== undefined) buckets.delete(firstKey);
    }
    bucket = { tokens: CAPACITY, lastRefillMs: now };
    buckets.set(key, bucket);
  }

  const elapsed = now - bucket.lastRefillMs;
  bucket.tokens = Math.min(CAPACITY, bucket.tokens + elapsed * REFILL_PER_MS);
  bucket.lastRefillMs = now;

  if (bucket.tokens >= cost) {
    bucket.tokens -= cost;
    return { allowed: true, remaining: Math.floor(bucket.tokens), retryAfterSeconds: 0 };
  }

  const deficit = cost - bucket.tokens;
  const retryAfterSeconds = Math.ceil(deficit / (REFILL_PER_MS * 1000));
  return { allowed: false, remaining: Math.floor(bucket.tokens), retryAfterSeconds };
}

/** Derives a rate-limit key from a request. Prefers the standard proxy
 * header Vercel sets; falls back to a constant key locally (acceptable for
 * a portfolio deployment, not a substitute for real client identification
 * behind a different proxy). */
export function rateLimitKeyFromHeaders(headers: Headers): string {
  const forwardedFor = headers.get("x-forwarded-for");
  if (forwardedFor) return forwardedFor.split(",")[0]?.trim() ?? "unknown";
  const realIp = headers.get("x-real-ip");
  if (realIp) return realIp;
  return "local";
}
