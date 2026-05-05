package arch;

import com.google.genai.Client;
import com.google.genai.types.GenerateContentResponse;
import java.util.concurrent.Semaphore;
import java.util.logging.Logger;

public class GeminiClient {

    public static final String MODEL = "gemini-2.0-flash-lite";

    private static final int MAX_RETRIES  = 3;
    private static final long RETRY_DELAY = 1000L;

    // Shared across ALL agents — one client, limited concurrency
    private static final Client    client    = new Client();
    private static final Semaphore semaphore = new Semaphore(500); // max 500 concurrent Gemini calls

    private static final Logger logger = Logger.getLogger(GeminiClient.class.getName());

    public static final GenerateContentConfig CONFIG_ANALYTICAL = GenerateContentConfig.builder()
        .temperature(0.0f)
        .build();

    public static final GenerateContentConfig CONFIG_CREATIVE = GenerateContentConfig.builder()
        .temperature(0.8f)
        .build();

    public String getResponse(String prompt) {
        return getResponse(prompt, CONFIG_ANALYTICAL); 
    }

    public String getResponse(String prompt, GenerateContentConfig config) {
        int attempt = 0;
        while (attempt < MAX_RETRIES) {
            try {
                semaphore.acquire();
                try {
                    GenerateContentResponse response =
                        client.models.generateContent(MODEL, prompt, config);
                    return response.text();
                } finally {
                    semaphore.release();
                }
            } catch (InterruptedException ie) {
                Thread.currentThread().interrupt();
                return "";
            } catch (Exception e) {
                attempt++;
                String msg = e.getMessage() != null ? e.getMessage() : "";
                boolean isRateLimit = msg.contains("429") || msg.toLowerCase().contains("quota");

                if (attempt >= MAX_RETRIES) {
                    logger.severe("[GeminiClient] Max retries reached.");
                    return "";
                }

                long delay;
                if (isRateLimit) {
                    // Exponential backoff capped at 60s — no need to sleep a full minute
                    // at 4k RPM the window resets in 60s, so 15s → 30s → 60s is enough
                    delay = Math.min(15_000L * (1L << (attempt - 1)), 60_000L);
                    logger.warning("[GeminiClient] Rate limited. Waiting " + delay + "ms...");
                } else {
                    delay = RETRY_DELAY * attempt; // linear backoff for transient errors
                    logger.warning("[GeminiClient] Error (attempt " + attempt + "): " + msg);
                }

                try { Thread.sleep(delay); } catch (InterruptedException ie) {
                    Thread.currentThread().interrupt();
                    return "";
                }
            }
        }
        return "";
    }
}