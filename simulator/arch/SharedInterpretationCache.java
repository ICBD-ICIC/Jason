package arch;

import java.util.List;
import java.util.Map;
import java.util.concurrent.*;
import java.util.concurrent.atomic.AtomicInteger;
import java.util.function.Function;

public class SharedInterpretationCache {

    private static final ConcurrentHashMap<String, CompletableFuture<Map<String, Object>>> cache =
        new ConcurrentHashMap<>();

    private static final int MAX_SIZE = 10_000;

    public static Map<String, Object> get(
            String content,                                    // FIX: renamed param was never used; introduce local 'key'
            Function<String, Map<String, Object>> loader) {

        String key = content;                                  // FIX: 'key' was referenced but never declared

        CompletableFuture<Map<String, Object>> existing = cache.get(key);
        if (existing != null) {
            try { return existing.get(); }
            catch (Exception e) { cache.remove(key); }
        }

        CompletableFuture<Map<String, Object>> future = new CompletableFuture<>();
        CompletableFuture<Map<String, Object>> prior  = cache.putIfAbsent(key, future);

        if (prior != null) {
            try { return prior.get(); }
            catch (Exception e) { return fallback(); }
        }

        try {
            Map<String, Object> result = loader.apply(content);
            future.complete(result);
            evictIfNeeded();
            return result;
        } catch (Exception e) {
            future.completeExceptionally(e);
            cache.remove(key);
            return fallback();
        }
    }

    private static void evictIfNeeded() {
        if (cache.size() > MAX_SIZE) {
            AtomicInteger toRemove = new AtomicInteger(MAX_SIZE / 10); // FIX: AtomicInteger now imported
            cache.keys().asIterator().forEachRemaining(k -> {
                if (toRemove.getAndDecrement() > 0) cache.remove(k);
            });
        }
    }

    private static Map<String, Object> fallback() {
        return Map.of("pnov", 0.0, "prpl", 0.0, "pnw", 0.0, "topics", List.of()); // FIX: List now imported
    }
}