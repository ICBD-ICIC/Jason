package arch;

import com.google.genai.Client;
import com.google.genai.types.GenerateContentConfig;
import com.google.genai.types.GenerateContentResponse;

import java.util.logging.Logger;


public class GeminiClient {

    public static final String MODEL = "gemini-2.5-flash-lite";

    public static final GenerateContentConfig CONFIG_ANALYTICAL = GenerateContentConfig.builder()
            .temperature(0.0f)
            .build();

    public static final GenerateContentConfig CONFIG_CREATIVE = GenerateContentConfig.builder()
            .temperature(0.8f)
            .build();

    private static final int MAX_RETRIES = 2;
    private static final long INITIAL_RETRY_DELAY_MS = 5_000L;
    private static final long RATE_LIMIT_DELAY_MS    = 30_000L;

    private static final Logger logger = Logger.getLogger(GeminiClient.class.getName());

    private final Client client;

    public GeminiClient() {
        this.client = new Client();
    }

    /**
     * Sends a text prompt with the given config and returns the model's text response,
     * or an empty string if all retry attempts fail.
     *
     * @param prompt the user prompt
     * @param config one of {@link #CONFIG_ANALYTICAL} or {@link #CONFIG_CREATIVE}
     * @return the model's text reply, or {@code ""} on failure
     */
    public String getResponse(String prompt, GenerateContentConfig config) {
        GenerateContentResponse response = executeWithRetry(() ->
                client.models.generateContent(MODEL, prompt, config)
        );
        return response != null ? response.text() : "";
    }

    // ── Retry Logic ──────────────────────────────────────────────────────────

    private <T> T executeWithRetry(ThrowingSupplier<T> call) {
        for (int attempt = 0; attempt <= MAX_RETRIES; attempt++) {
            try {
                return call.get();
            } catch (Exception e) {
                boolean isRateLimit = isRateLimitError(e);

                if (attempt == MAX_RETRIES) {
                    logger.severe(String.format(
                            "All %d attempts failed: %s", MAX_RETRIES + 1, e.getMessage()));
                    return null;
                }

                long delayMs = isRateLimit
                        ? RATE_LIMIT_DELAY_MS
                        : INITIAL_RETRY_DELAY_MS * (1L << attempt); // 5s, 10s

                logger.warning(String.format(
                        "Attempt %d/%d failed (%s). Retrying in %d ms…",
                        attempt + 1,
                        MAX_RETRIES + 1,
                        isRateLimit ? "429 rate-limited" : e.getMessage(),
                        delayMs));

                sleep(delayMs);
            }
        }
        return null; // unreachable, but required by the compiler
    }

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