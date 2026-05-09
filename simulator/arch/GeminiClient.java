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
import java.util.concurrent.ExecutionException;

public class GeminiClient {

    public static final String MODEL = "gemini-2.5-flash-lite";

    private static final int MAX_ATTEMPTS  = 3;
    private static final long RETRY_DELAY = 1000L;

    // Shared across ALL agents — one client, limited concurrency
    private static final Client    client    = new Client();
    private static final Semaphore semaphore = new Semaphore(150);

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
        while (attempt < MAX_ATTEMPTS) {
            try {
                waitingForSemaphore.incrementAndGet();
                semaphore.acquire();
                waitingForSemaphore.decrementAndGet();
                activeGeminiCalls.incrementAndGet();
                try {
                    Future<String> future = executor.submit(() -> {
                        GenerateContentResponse response =
                            client.models.generateContent(MODEL, prompt, config);
                        String text = response.text();
                        if (text == null || text.isBlank()) {
                            throw new RuntimeException("Empty response from Gemini");
                        }
                        return text;
                    });
                    String result = future.get(30, TimeUnit.SECONDS);
                    return result;
                } catch (TimeoutException te) {
                    logger.warning("[GeminiClient] TIMEOUT.");
                    attempt++;
                } finally {
                    activeGeminiCalls.decrementAndGet();
                    semaphore.release();
                }
            } catch (InterruptedException ie) {
                Thread.currentThread().interrupt();
                return "";
            } catch (Exception e) {
                attempt++;
                Throwable cause = (e instanceof ExecutionException && e.getCause() != null)
                    ? e.getCause() : e;
                String msg = cause.getMessage() != null ? cause.getMessage() : "";
                boolean isRateLimit = msg.contains("429") || msg.toLowerCase().contains("quota");

                if (attempt >= MAX_ATTEMPTS) {
                    logger.severe("[GeminiClient] Max retries reached.");
                    return "";
                }

                long delay;
                if (isRateLimit) {
                    delay = Math.min(15_000L * (1L << (attempt - 1)), 60_000L);
                    logger.warning("[GeminiClient] Rate limited. Waiting " + delay + "ms...");
                } else {
                    delay = RETRY_DELAY * attempt;
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