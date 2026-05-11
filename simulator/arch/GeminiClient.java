package arch;

import com.google.genai.Client;
import com.google.genai.types.GenerateContentConfig;
import com.google.genai.types.GenerateContentResponse;
import com.google.genai.types.Schema;

import java.util.concurrent.ExecutionException;
import java.util.concurrent.ExecutorService;
import java.util.concurrent.Executors;
import java.util.concurrent.Future;
import java.util.concurrent.TimeUnit;
import java.util.concurrent.TimeoutException;
import java.util.concurrent.atomic.AtomicInteger;
import java.util.concurrent.atomic.AtomicLong;
import java.util.logging.Logger;

public class GeminiClient {

    public static final String MODEL = "gemini-2.5-flash-lite";

    public static final GenerateContentConfig CONFIG_ANALYTICAL = GenerateContentConfig.builder()
            .temperature(0.0f)
            .build();

    public static final GenerateContentConfig CONFIG_CREATIVE = GenerateContentConfig.builder()
            .temperature(0.8f)
            .build();

    public static GenerateContentConfig jsonConfigCreative(Schema schema) {
        return GenerateContentConfig.builder()
                .temperature(0.8f)
                .responseMimeType("application/json")
                .responseSchema(schema)
                .build();
    }

    private static final int    MAX_RETRIES            = 2;
    private static final long   REQUEST_TIMEOUT_MS     = 60_000L;
    private static final long   TIMEOUT_RETRY_DELAY_MS = 15_000L; // wait before retrying a timeout
    private static final long   INITIAL_RETRY_DELAY_MS = 5_000L;
    private static final long   RATE_LIMIT_DELAY_MS    = 30_000L;

    // ── Circuit breaker ───────────────────────────────────────────────────────
    // If too many consecutive failures happen across all threads, stop trying
    // for a cooldown period rather than piling on a sick API.
    private static final int  CB_FAILURE_THRESHOLD   = 5;
    private static final long CB_COOLDOWN_MS         = 60_000L;

    private final AtomicInteger consecutiveFailures = new AtomicInteger(0);
    private final AtomicLong    circuitOpenUntil    = new AtomicLong(0);

    private static final Logger logger = Logger.getLogger(GeminiClient.class.getName());

    private final Client client;
    private final ExecutorService executor = Executors.newVirtualThreadPerTaskExecutor();

    public GeminiClient() {
        this.client = new Client();
    }

    public String getResponse(String prompt, GenerateContentConfig config) {
        GenerateContentResponse response = executeWithRetry(() ->
                client.models.generateContent(MODEL, prompt, config)
        );
        return response != null ? response.text() : "";
    }

    // ── Retry logic ───────────────────────────────────────────────────────────

    private <T> T executeWithRetry(ThrowingSupplier<T> call) {
        for (int attempt = 0; attempt <= MAX_RETRIES; attempt++) {

            // Circuit breaker: bail out early if the API is globally sick
            long openUntil = circuitOpenUntil.get();
            if (openUntil > System.currentTimeMillis()) {
                long remaining = openUntil - System.currentTimeMillis();
                logger.warning(String.format(
                        "Circuit open — skipping attempt, cooldown has %d ms remaining.", remaining));
                return null;
            }

            try {
                T result = callWithTimeout(call);
                consecutiveFailures.set(0); // success — reset the breaker
                return result;

            } catch (TimeoutException e) {
                int failures = consecutiveFailures.incrementAndGet();
                if (failures >= CB_FAILURE_THRESHOLD) {
                    circuitOpenUntil.set(System.currentTimeMillis() + CB_COOLDOWN_MS);
                    logger.severe(String.format(
                            "Circuit breaker tripped after %d consecutive failures. " +
                            "Cooling down for %d ms.", failures, CB_COOLDOWN_MS));
                    return null;
                }

                if (attempt == MAX_RETRIES) {
                    logger.severe(String.format(
                            "All %d attempts timed out after %d ms each.",
                            MAX_RETRIES + 1, REQUEST_TIMEOUT_MS));
                    return null;
                }

                logger.warning(String.format(
                        "Attempt %d/%d timed out. Waiting %d ms before retry…",
                        attempt + 1, MAX_RETRIES + 1, TIMEOUT_RETRY_DELAY_MS));
                sleep(TIMEOUT_RETRY_DELAY_MS);

            } catch (Exception e) {
                boolean isRateLimit = isRateLimitError(e);
                consecutiveFailures.incrementAndGet();

                if (attempt == MAX_RETRIES) {
                    logger.severe(String.format(
                            "All %d attempts failed: %s", MAX_RETRIES + 1, e.getMessage()));
                    return null;
                }

                long delayMs = isRateLimit
                        ? RATE_LIMIT_DELAY_MS
                        : INITIAL_RETRY_DELAY_MS * (1L << attempt);

                logger.warning(String.format(
                        "Attempt %d/%d failed (%s). Retrying in %d ms…",
                        attempt + 1, MAX_RETRIES + 1,
                        isRateLimit ? "429 rate-limited" : e.getMessage(),
                        delayMs));
                sleep(delayMs);
            }
        }
        return null;
    }

    private <T> T callWithTimeout(ThrowingSupplier<T> call) throws Exception {
        Future<T> future = executor.submit(() -> {
            try {
                return call.get();
            } catch (Exception e) {
                throw new RuntimeException(e);
            }
        });

        try {
            return future.get(REQUEST_TIMEOUT_MS, TimeUnit.MILLISECONDS);
        } catch (TimeoutException e) {
            future.cancel(true);
            throw e;
        } catch (ExecutionException e) {
            Throwable cause = e.getCause();
            if (cause instanceof RuntimeException re && re.getCause() instanceof Exception inner) {
                throw inner;
            }
            throw e;
        }
    }

    // ── Helpers ───────────────────────────────────────────────────────────────

    private static boolean isRateLimitError(Exception e) {
        Throwable current = e;
        while (current != null) {
            String msg = current.getMessage();
            if (msg != null && (msg.contains("429") || msg.contains("RESOURCE_EXHAUSTED"))) {
                return true;
            }
            current = current.getCause();
        }
        return false;
    }

    private static void sleep(long ms) {
        try {
            Thread.sleep(ms);
        } catch (InterruptedException ie) {
            Thread.currentThread().interrupt();
        }
    }

    @FunctionalInterface
    private interface ThrowingSupplier<T> {
        T get() throws Exception;
    }
}