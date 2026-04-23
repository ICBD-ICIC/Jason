package arch;

import com.google.genai.Client;
import com.google.genai.types.GenerateContentResponse;

/**
 * Thin wrapper around the Gemini API.
 *
 * Owns the Client lifecycle and retry logic so that agent
 * architectures only need to build prompts and parse responses.
 */
public class GeminiClient {

    public static final String MODEL = "gemini-2.0-flash";

    private static final int  MAX_RETRIES = 3;
    private static final long RETRY_DELAY = 1000L;

    private final Client client = new Client();

    /**
     * Sends a prompt to Gemini and returns the raw text response.
     * Retries up to MAX_RETRIES times on transient failures.
     * Returns an empty string if all attempts fail.
     */
    public String getResponse(String prompt) {
        int attempt = 0;
        while (attempt < MAX_RETRIES) {
            try {
                GenerateContentResponse response =
                    client.models.generateContent(MODEL, prompt, null);
                return response.text();
            } catch (Exception e) {
                attempt++;
                System.err.println("[GeminiClient] Error (attempt " + attempt + "): " + e.getMessage());
                if (attempt >= MAX_RETRIES) {
                    System.err.println("[GeminiClient] Max retries reached. Returning empty string.");
                    return "";
                }
                try {
                    Thread.sleep(RETRY_DELAY);
                } catch (InterruptedException ie) {
                    Thread.currentThread().interrupt();
                    return "";
                }
            }
        }
        return "";
    }
}
