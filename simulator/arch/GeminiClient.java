package arch;

import com.google.genai.Client;
import com.google.genai.types.GenerateContentResponse;
import com.google.genai.types.GenerateContentConfig;
import java.util.concurrent.Semaphore;
import java.util.concurrent.ThreadPoolExecutor;
import java.util.concurrent.LinkedBlockingQueue;
import java.util.concurrent.TimeUnit;
import java.util.concurrent.Future;
import java.util.concurrent.TimeoutException;
import java.util.concurrent.atomic.AtomicInteger;
import java.util.logging.Logger;

public class GeminiClient {

    public static final String MODEL = "gemini-2.5-flash-lite";

    private static final int MAX_RETRIES  = 3;
    private static final long RETRY_DELAY = 1000L;

    // Shared across ALL agents — one client, limited concurrency
    private static final Client    client    = new Client();
    private static final Semaphore semaphore = new Semaphore(80);

    private static final AtomicInteger activeGeminiCalls    = new AtomicInteger(0);
    private static final AtomicInteger waitingForSemaphore  = new AtomicInteger(0);

    private static final Logger logger = Logger.getLogger(GeminiClient.class.getName());

    public static final GenerateContentConfig CONFIG_ANALYTICAL = GenerateContentConfig.builder()
        .temperature(0.0f)
        .build();

    public static final GenerateContentConfig CONFIG_CREATIVE = GenerateContentConfig.builder()
        .temperature(0.8f)
        .build();
    
    private static final ThreadPoolExecutor executor = new ThreadPoolExecutor(
        200, 200,
        60L, TimeUnit.SECONDS,
        new LinkedBlockingQueue<>(),
        r -> { Thread t = new Thread(r, "gemini-call"); t.setDaemon(true); return t; }
    );
        
    static {
        Thread watchdog = new Thread(() -> {
            while (true) {
                try {
                    Thread.sleep(30_000);
                    logger.info("[WATCHDOG] permits=" + semaphore.availablePermits()
                        + " activeGemini=" + activeGeminiCalls.get()
                        + " waitingForSemaphore=" + waitingForSemaphore.get()
                        + " executorQueueSize=" + ((ThreadPoolExecutor) executor).getQueue().size()
                        + " executorActiveThreads=" + ((ThreadPoolExecutor) executor).getActiveCount());
                } catch (InterruptedException e) {
                    break;
                }
            }
        }, "gemini-watchdog");
        watchdog.setDaemon(true);
        watchdog.start();
    }

    public String getResponse(String prompt) {
        return getResponse(prompt, CONFIG_ANALYTICAL); 
    }

    public String getResponse(String prompt, GenerateContentConfig config) {
        int attempt = 0;
        while (attempt < MAX_RETRIES) {
            try {
                waitingForSemaphore.incrementAndGet();
                logger.info("[GeminiClient] Waiting for semaphore. In queue: " + waitingForSemaphore.get() 
                    + " | Active calls: " + activeGeminiCalls.get()
                    + " | Available permits: " + semaphore.availablePermits());
                semaphore.acquire();
                waitingForSemaphore.decrementAndGet();
                activeGeminiCalls.incrementAndGet();
                logger.info("[GeminiClient] Acquired semaphore. Active calls: " + activeGeminiCalls.get());
                try {
                    Future<String> future = executor.submit(() -> {
                        GenerateContentResponse response =
                            client.models.generateContent(MODEL, prompt, config);
                        return response.text();
                    });
                    String result = future.get(30, TimeUnit.SECONDS);
                    logger.info("[GeminiClient] Got response. Active calls: " + activeGeminiCalls.decrementAndGet());
                    return result;
                } catch (TimeoutException te) {
                    activeGeminiCalls.decrementAndGet();
                    logger.warning("[GeminiClient] TIMEOUT. Active: " + activeGeminiCalls.get());
                    attempt++;
                } finally {
                    semaphore.release();
                }
            } catch (InterruptedException ie) {
                Thread.currentThread().interrupt();
                return "";
            } catch (Exception e) {
                activeGeminiCalls.decrementAndGet();

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