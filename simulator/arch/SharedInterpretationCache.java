package arch;

import com.github.benmanes.caffeine.cache.Cache;
import com.github.benmanes.caffeine.cache.Caffeine;

import java.util.Map;
import java.util.concurrent.*;
import java.util.function.Function;
import java.util.logging.Logger;

public class SharedInterpretationCache {

    private static final Logger logger = Logger.getLogger(SharedInterpretationCache.class.getName());

    private static final Cache<String, Double> doubleCache =
            Caffeine.newBuilder().maximumSize(10_000).build();

    private static final Cache<String, Map<String, Object>> mapCache =
            Caffeine.newBuilder().maximumSize(10_000).build();

    // Returns null on miss — caller computes and calls putDouble()
    public static Double getDoubleIfPresent(String key) {
        return doubleCache.getIfPresent(key);
    }

    public static void putDouble(String key, double value) {
        doubleCache.put(key, value);
    }

    // Returns null on miss — caller computes and calls put()
    public static Map<String, Object> getIfPresent(String key) {
        return mapCache.getIfPresent(key);
    }

    public static void put(String key, Map<String, Object> value) {
        mapCache.put(key, value);
    }

    public static void clear() {
        doubleCache.invalidateAll();
        mapCache.invalidateAll();
        logger.info("[Cache] Cleared.");
    }
}