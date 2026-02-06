package arch;

import jason.architecture.AgArch;
import jason.asSyntax.*;

import java.util.List;
import java.util.Map;

import lib.Translator;

import com.google.genai.Client;
import com.google.genai.types.GenerateContentResponse;

public class GeminiBotAgArch extends AgArch implements LlmBotAgArch{

    private final Client client = new Client();
    private static final String model = "gemini-2.0-flash";

    // ---------------- PUBLIC API ----------------

    public String generateIntervention(Term conversation) {
        String prompt = String.format("Write a concise tweet responding to the thread below with the goal of reducing hostility and de-escalating the conversation.\n\n" +
        "The reply should:\n" +
        "- Acknowledge differing viewpoints without validating insults or aggression\n" +
        "- Use calm, respectful, non-judgmental language\n" +
        "- Avoid taking sides or escalating conflict\n" +
        "- Encourage understanding, nuance, or pausing before reacting\n" +
        "- Sound natural and human, not preachy or moralizing\n" +
        "- Be under 280 characters\n\n" +
        "Thread:\n%s", fromJasonString(conversation));
        return getResponse(prompt);
    }

    private String getResponse(String prompt) {
        final int maxRetries = 3; 
        final long retryDelay = 1000; 
        int attempt = 0;

        while (attempt < maxRetries) {
            try {
                GenerateContentResponse response = client.models.generateContent(model, prompt, null);
                System.out.print("\nPROMPT: " + prompt + "\n");
                System.out.print("RESPONSE: " + response.text() + "\n");
                return response.text();
            } catch (Exception e) {
                attempt++;
                System.err.println("Error generating content (attempt " + attempt + "): " + e.getMessage());
                if (attempt >= maxRetries) {
                    System.err.println("Max retries reached. Returning empty string.");
                    return "";
                }
                try {
                    Thread.sleep(retryDelay);
                } catch (InterruptedException ie) {
                    Thread.currentThread().interrupt();
                    System.err.println("Retry sleep interrupted.");
                    return "";
                }
            }
        }
        return "";
    }

    private static String fromJasonString(Term jasonString) {
        String s = jasonString.toString();
        if (s == null) return "";
            s = s.trim();
        if (s.length() >= 2 && s.startsWith("\"") && s.endsWith("\"")) {
            return s.substring(1, s.length() - 1);
        }
        return s;
    }
}
