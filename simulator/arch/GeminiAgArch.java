package arch;

import jason.architecture.AgArch;
import jason.asSyntax.*;

import java.util.*;
import lib.JasonToJavaTranslator;

import com.google.genai.Client;
import com.google.genai.types.GenerateContentResponse;

public class GeminiAgArch extends AgArch implements SocialAgArch {

    private final Client client = new Client();
    private static final String model = "gemini-2.0-flash";

    // ---------------- PUBLIC API ----------------

    public String createContent(Term topics, Term variables) {
        // if variables has "originalContent", include it in the prompt
        List<String> topicList = JasonToJavaTranslator.translateTopics(topics);
        Map<String, Object> varMap = JasonToJavaTranslator.translateVariables(variables);
        String prompt = String.format("Create a tweet that talks about %s and has the following characteristics: %s", topicList.toString(), varMap.toString());
        return getResponse(prompt);
    }

    public Map<String, Object> interpretContent(Term content) {
        String contentString = content.toString();
        String prompt = String.format("Interpret the following content: %s", contentString);
        //aca habria que traducir a key(value)
        Map<String, Object> response = new HashMap<>();
        response.put("interpretation", (Object) getResponse(prompt));
        return response;
    }

    private String getResponse(String prompt) {
        final int maxRetries = 3; 
        final long retryDelay = 1000; 
        int attempt = 0;

        while (attempt < maxRetries) {
            try {
                GenerateContentResponse response = client.models.generateContent(model, prompt, null);
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
}
