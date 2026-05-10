package arch;

import java.util.List;
import java.util.Map;
import java.util.concurrent.*;
import java.util.concurrent.atomic.AtomicInteger;
import java.util.function.Function;

public class SharedInterpretationCache {

    // Only pnw is cached now — per conversation root, as a plain double.
    // pnov, prpl, and topics are computed fresh per message (no cache).
    private static final ConcurrentHashMap<String, CompletableFuture<Double>> doubleCache =
        new ConcurrentHashMap<>();

    private static final int MAX_SIZE = 10_000;

    public static double getDouble(String key, Function<String, Double> loader) {
        CompletableFuture<Double> existing = doubleCache.get(key);
        if (existing != null) {
            try { return existing.get(); }
            catch (Exception e) { doubleCache.remove(key); }
        }

        CompletableFuture<Double> future = new CompletableFuture<>();
        CompletableFuture<Double> prior  = doubleCache.putIfAbsent(key, future);

        if (prior != null) {
            try { return prior.get(); }
            catch (Exception e) { return 0.0; }
        }

        try {
            double result = loader.apply(key);
            future.complete(result);
            evictIfNeeded();
            return result;
        } catch (Exception e) {
            future.completeExceptionally(e);
            doubleCache.remove(key);
            return 0.0;
        }
    }

    private static void evictIfNeeded() {
        if (doubleCache.size() > MAX_SIZE) {
            AtomicInteger toRemove = new AtomicInteger(MAX_SIZE / 10);
            doubleCache.keys().asIterator().forEachRemaining(k -> {
                if (toRemove.getAndDecrement() > 0) doubleCache.remove(k);
            });
        }
    }
}