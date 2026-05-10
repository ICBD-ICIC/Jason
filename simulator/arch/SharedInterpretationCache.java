package arch;

import java.util.Map;
import java.util.concurrent.*;
import java.util.concurrent.atomic.AtomicInteger;
import java.util.function.Function;

/**
 * Shared LLM result cache for CoNVaI agents.
 *
 * Two independent stores reflect the two caching strategies in use:
 *
 *   doubleCache - single double values; used for Pnw (one entry per conversation root)
 *   mapCache    - Map<String,Object> values; used for Prpl+topics (one entry per message text)
 *
 * Both stores use CompletableFuture to prevent duplicate LLM calls when multiple
 * agents concurrently miss the same cache key: only the first caller fires the
 * request; all others block on the same future until it resolves.
 *
 * Pnov is intentionally excluded from this cache because novelty is relative to
 * each agent's individual reading history and must be computed fresh per agent.
 */
public class SharedInterpretationCache {

    private static final int MAX_SIZE    = 10_000;
    private static final int EVICT_COUNT = MAX_SIZE / 10;

    private static final ConcurrentHashMap<String, CompletableFuture<Double>>              doubleCache =
        new ConcurrentHashMap<>();
    private static final ConcurrentHashMap<String, CompletableFuture<Map<String, Object>>> mapCache    =
        new ConcurrentHashMap<>();

    // -------------------------------------------------------------------------
    // Public API
    // -------------------------------------------------------------------------

    /**
     * Returns a cached double for {@code key}, computing it via {@code loader} on a miss.
     * Used for Pnw (keyed by conversation root content).
     */
    public static double getDouble(String key, Function<String, Double> loader) {
        return resolve(doubleCache, key, loader, 0.0);
    }

    /**
     * Returns a cached map for {@code key}, computing it via {@code loader} on a miss.
     * Used for Prpl + topics (keyed by message content).
     */
    public static Map<String, Object> get(String key, Function<String, Map<String, Object>> loader) {
        return resolve(mapCache, key, loader, Map.of());
    }

    // -------------------------------------------------------------------------
    // Internal
    // -------------------------------------------------------------------------

    /**
     * Generic cache-and-wait resolver.
     *
     * On a cache miss the calling thread races to insert a new CompletableFuture.
     * The winner calls the loader; all other threads block on the same future,
     * ensuring exactly one LLM call per unique key regardless of concurrency.
     */
    private static <V> V resolve(ConcurrentHashMap<String, CompletableFuture<V>> cache,
                              String key,
                              Function<String, V> loader,
                              V fallback) {
        while (true) {
            CompletableFuture<V> existing = cache.get(key);
            if (existing != null) {
                try {
                    V value = existing.get();
                    // If the future completed exceptionally, get() throws -
                    // so reaching here means we have a valid result
                    return value;
                } catch (ExecutionException e) {
                    // Previous attempt failed - remove and retry from scratch
                    cache.remove(key, existing);
                    continue;
                } catch (InterruptedException e) {
                    Thread.currentThread().interrupt();
                    return fallback;
                }
            }

            CompletableFuture<V> promise = new CompletableFuture<>();
            CompletableFuture<V> prior   = cache.putIfAbsent(key, promise);

            if (prior != null) {
                // Lost the race - wait, but handle failure by retrying
                try {
                    return prior.get();
                } catch (ExecutionException e) {
                    // Winner failed - loop back and try to become the new winner
                    cache.remove(key, prior);
                    continue;
                } catch (InterruptedException e) {
                    Thread.currentThread().interrupt();
                    return fallback;
                }
            }

            // Won the race - call loader
            try {
                V result = loader.apply(key);
                if (result == null) {
                    // Treat null as a failed load - don't cache it
                    promise.completeExceptionally(new RuntimeException("Loader returned null"));
                    cache.remove(key, promise);
                    return fallback;
                }
                promise.complete(result);
                evictIfNeeded(cache);
                return result;
            } catch (Exception e) {
                promise.completeExceptionally(e);
                cache.remove(key, promise);
                return fallback;
            }
        }
    }

    private static void evictIfNeeded(ConcurrentHashMap<?, ?> cache) {
        if (cache.size() > MAX_SIZE) {
            AtomicInteger remaining = new AtomicInteger(EVICT_COUNT);
            cache.keys().asIterator().forEachRemaining(k -> {
                if (remaining.getAndDecrement() > 0) cache.remove(k);
            });
        }
    }
}