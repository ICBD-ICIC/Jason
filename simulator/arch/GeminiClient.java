package arch;

import com.google.genai.Client;
import com.google.genai.types.GenerateContentResponse;
import java.util.concurrent.Semaphore;

public class GeminiClient {

    public static final String MODEL = "gemini-2.5-flash";

    private static final int MAX_RETRIES  = 3;
    private static final long RETRY_DELAY = 1000L;

    // Shared across ALL agents — one client, limited concurrency
    private static final Client    client      = new Client();
    private static final Semaphore semaphore   = new Semaphore(10); // max 10 concurrent Gemini calls

    public String getResponse(String prompt) {
        int attempt = 0;
        while (attempt < MAX_RETRIES) {
            try {
                semaphore.acquire();  // wait for a slot — does NOT block the thread pool permanently
                try {
                    GenerateContentResponse response =
                        client.models.generateContent(MODEL, prompt, null);
                    return response.text();
                } finally {
                    semaphore.release();  // always release, even on exception
                }
            } catch (InterruptedException ie) {
                Thread.currentThread().interrupt();
                return "";
            } catch (Exception e) {
                attempt++;
                System.err.println("[GeminiClient] Error (attempt " + attempt + "): " + e.getMessage());
                if (attempt >= MAX_RETRIES) {
                    System.err.println("[GeminiClient] Max retries reached. Returning empty string.");
                    return "";
                }
                try { Thread.sleep(RETRY_DELAY); } catch (InterruptedException ie) {
                    Thread.currentThread().interrupt();
                    return "";
                }
            }
        }
        return "";
    }
}