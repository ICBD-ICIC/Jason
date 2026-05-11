package arch;

import com.google.genai.Client;
import com.google.genai.types.GenerateContentConfig;
import com.google.genai.types.GenerateContentResponse;
import com.google.genai.types.Schema;

import java.util.concurrent.*;
import java.util.concurrent.ThreadLocalRandom;
import java.util.logging.Logger;

/**
 * Thin, reliable wrapper around the Gemini SDK.
 *
 * Design principles
 * -----------------
 *  1. Agent threads NEVER block on Gemini directly. They submit a request to a
 *     shared bounded queue and park on a CompletableFuture until the result is
 *     ready. The Jason plan thread is suspended (not spinning) while waiting,
 *     keeping all 225 pool threads available for other agent reasoning.
 *
 *  2. A fixed dispatcher pool (DISPATCHER_THREADS) drains the queue and calls
 *     the Gemini SDK. This is the only concurrency ceiling — no Semaphore needed.
 *     With 50 dispatchers and ~2 s avg latency, sustained throughput is ~25 RPS,
 *     well under the 4 000 RPM (≈67 RPS) quota.
 *
 *  3. Retries are re-enqueued asynchronously after a backoff delay, so a failing
 *     dispatcher thread is freed immediately and can handle other requests.
 *     Rate-limit (429 / RESOURCE_EXHAUSTED) and unavailability (503 / UNAVAILABLE)
 *     errors both get the longer pause; everything else gets a short one with
 *     linear growth and random jitter to avoid thundering-herd re-spikes.
 *
 *  4. Queue capacity (2 000) comfortably exceeds the worst-case burst:
 *     400 agents × 5 messages ≈ 2 000 outstanding requests.  If the queue is
 *     ever full the call fails fast with "" rather than blocking the agent.
 *
 *  5. Returns "" on failure — callers already handle that gracefully.
 *     Futures are always completed normally (never exceptionally) so agent
 *     plans see a consistent String result.
 */
public class GeminiClient {

    public static final String MODEL = "gemini-2.5-flash-lite";

    public static final GenerateContentConfig CONFIG_ANALYTICAL =
            GenerateContentConfig.builder().temperature(0.0f).build();

    public static final GenerateContentConfig CONFIG_CREATIVE =
            GenerateContentConfig.builder().temperature(0.8f).build();

    public static GenerateContentConfig jsonConfigCreative(Schema schema) {
        return GenerateContentConfig.builder()
                .temperature(0.8f)
                .responseMimeType("application/json")
                .responseSchema(schema)
                .build();
    }

    // ── Dispatcher pool (shared across ALL GeminiClient instances) ────────────

    /**
     * Number of threads that may call Gemini concurrently.
     * With 4 000 RPM quota (≈67 RPS) and ~2 s average latency,
     * 50 threads yields ~25 RPS sustained — leaving headroom for bursts.
     */
    private static final int DISPATCHER_THREADS = 50;

    /**
     * Bounded request queue. Sized for worst-case burst:
     * 400 agents × 5 messages ≈ 2 000. Adjust upward if needed.
     */
    private static final int QUEUE_CAPACITY = 2_000;

    private static final LinkedBlockingQueue<GeminiRequest> QUEUE =
            new LinkedBlockingQueue<>(QUEUE_CAPACITY);

    /** One Client per dispatcher thread to avoid internal SDK contention. */
    private static final ExecutorService DISPATCHER =
            Executors.newFixedThreadPool(DISPATCHER_THREADS, r -> {
                Thread t = new Thread(r, "gemini-dispatcher");
                t.setDaemon(true);
                return t;
            });

    static {
        for (int i = 0; i < DISPATCHER_THREADS; i++) {
            DISPATCHER.submit(GeminiClient::dispatchLoop);
        }
    }

    // ── Tuning constants ──────────────────────────────────────────────────────

    /**
     * Per-attempt Gemini SDK timeout. The agent-side timeout is this value
     * multiplied by MAX_ATTEMPTS, giving the SDK time for all retry attempts.
     */
    private static final long TIMEOUT_MS             = 45_000L;

    /** How many times to attempt a call before giving up (1 = no retry). */
    private static final int  MAX_ATTEMPTS           = 4;

    /** Base back-off after a generic error. Grows linearly each retry. */
    private static final long BASE_BACKOFF_MS        = 2_000L;

    /**
     * Back-off after HTTP 429 / RESOURCE_EXHAUSTED / 503 / UNAVAILABLE.
     * Reduced from 30 s to 10 s because with 4 000 RPM the quota bucket
     * refills in seconds, not tens of seconds.
     */
    private static final long RATE_LIMIT_BACKOFF_MS = 10_000L;

    // ── State ─────────────────────────────────────────────────────────────────

    private static final Logger logger = Logger.getLogger(GeminiClient.class.getName());

    // ── Public API ────────────────────────────────────────────────────────────

    /**
     * Sends {@code prompt} to Gemini and returns the response text.
     *
     * The calling thread parks on a CompletableFuture and does NOT spin.
     * Jason agent plan threads are therefore not wasted while Gemini responds.
     *
     * Returns {@code ""} if every attempt fails, times out, or the queue is full.
     */
    public String getResponse(String prompt, GenerateContentConfig config) {
        CompletableFuture<String> future = new CompletableFuture<>();

        boolean accepted = QUEUE.offer(new GeminiRequest(prompt, config, future, MAX_ATTEMPTS));
        if (!accepted) {
            logger.severe("Gemini request queue is full — dropping request. "
                    + "Consider increasing QUEUE_CAPACITY or reducing simulation load.");
            return "";
        }

        try {
            // Parks the agent thread until the dispatcher completes the future.
            // Total timeout covers all retry attempts plus their back-offs.
            long totalTimeoutMs = (TIMEOUT_MS + RATE_LIMIT_BACKOFF_MS) * MAX_ATTEMPTS;
            return future.get(totalTimeoutMs, TimeUnit.MILLISECONDS);

        } catch (TimeoutException e) {
            logger.severe("Agent-side timeout waiting for Gemini result after "
                    + totalTimeoutMs() + " ms.");
            future.cancel(true);
            return "";
        } catch (InterruptedException e) {
            Thread.currentThread().interrupt();
            return "";
        } catch (ExecutionException e) {
            // Dispatchers always complete normally; this branch is a safety net.
            logger.warning("Gemini future completed exceptionally: "
                    + (e.getCause() != null ? e.getCause().getMessage() : e.getMessage()));
            return "";
        }
    }

    // ── Dispatcher loop ───────────────────────────────────────────────────────

    /** Runs forever on each dispatcher thread. Each thread owns its own Client. */
    private static void dispatchLoop() {
        Client client = new Client();
        while (!Thread.currentThread().isInterrupted()) {
            try {
                GeminiRequest req = QUEUE.take(); // blocks only the dispatcher
                handleRequest(client, req);
            } catch (InterruptedException e) {
                Thread.currentThread().interrupt();
                break;
            } catch (Exception e) {
                // Unexpected dispatcher crash — log and keep the loop alive.
                logger.severe("Unexpected error in Gemini dispatcher: " + e.getMessage());
            }
        }
    }

    private static void handleRequest(Client client, GeminiRequest req) {
        if (req.future().isCancelled()) {
            // Agent gave up (e.g. agent-side timeout fired) — discard silently.
            return;
        }

        try {
            GenerateContentResponse response =
                    client.models.generateContent(MODEL, req.prompt(), req.config());
            String text = (response != null && response.text() != null) ? response.text() : "";
            req.future().complete(text);

        } catch (Exception e) {
            boolean isRateLimit = isRateLimitOrUnavailable(e);
            int attemptsLeft   = req.attemptsLeft() - 1;

            if (attemptsLeft <= 0) {
                logger.severe(String.format(
                        "All %d Gemini attempts exhausted. Last error: %s",
                        MAX_ATTEMPTS, e.getMessage()));
                req.future().complete(""); // always complete normally
                return;
            }

            long backoff = isRateLimit
                    ? RATE_LIMIT_BACKOFF_MS
                    : BASE_BACKOFF_MS * (MAX_ATTEMPTS - attemptsLeft);
            // Jitter: ± 33 % of backoff to spread retry storms.
            backoff += ThreadLocalRandom.current().nextLong(0, Math.max(1, backoff / 3));

            logger.warning(String.format(
                    "Gemini error (%s). Retrying in %d ms. Attempts left: %d",
                    e.getMessage(), backoff, attemptsLeft));

            // Re-enqueue after backoff on a separate task so the dispatcher
            // thread is freed immediately and can handle other requests.
            final long finalBackoff = backoff;
            GeminiRequest retry = new GeminiRequest(
                    req.prompt(), req.config(), req.future(), attemptsLeft);
            DISPATCHER.submit(() -> {
                sleep(finalBackoff);
                boolean requeued = QUEUE.offer(retry);
                if (!requeued) {
                    logger.severe("Gemini retry queue full — dropping request.");
                    req.future().complete("");
                }
            });
        }
    }

    // ── Helpers ───────────────────────────────────────────────────────────────

    private static boolean isRateLimitOrUnavailable(Throwable e) {
        while (e != null) {
            String msg = e.getMessage();
            if (msg != null && (
                    msg.contains("429")                ||
                    msg.contains("RESOURCE_EXHAUSTED") ||
                    msg.contains("503")                ||
                    msg.contains("UNAVAILABLE"))) {
                return true;
            }
            e = e.getCause();
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

    /** Convenience — avoids repeating the arithmetic in the log message. */
    private static long totalTimeoutMs() {
        return (TIMEOUT_MS + RATE_LIMIT_BACKOFF_MS) * MAX_ATTEMPTS;
    }

    // ── Internal request record ───────────────────────────────────────────────

    private record GeminiRequest(
            String                    prompt,
            GenerateContentConfig     config,
            CompletableFuture<String> future,
            int                       attemptsLeft
    ) {}

    // ── Lifecycle ─────────────────────────────────────────────────────────────

    /**
     * Shuts down the shared dispatcher pool.
     * Call once when the simulation ends, not per-agent.
     */
    public void shutdown() {
        DISPATCHER.shutdownNow();
    }
}