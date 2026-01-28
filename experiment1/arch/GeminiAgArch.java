package arch;

import jason.architecture.AgArch;
import jason.asSyntax.*;

import java.util.List;
import java.util.Map;

import lib.Translator;

import com.google.genai.Client;
import com.google.genai.types.GenerateContentResponse;

public class GeminiAgArch extends AgArch implements LlmAgArch{

    private final Client client = new Client();
    private static final String model = "gemini-3-flash-preview";

    // ---------------- PUBLIC API ----------------

    public String createContent(Term topics, Term variables) {
        List<String> topicList = Translator.translateTopics(topics);
        Map<String, String> varMap = Translator.translateVariables(variables);
        String prompt = String.format("Create a tweet that talks about %s and has the following characteristics: %s", topicList.toString(), varMap.toString());

        System.out.print("\nPROMPT: " + prompt + "\n");

        return getResponse(prompt);
    }

    public String createContent(Term interpretations, Term originalContent, Term topics, Term variables) {
        List<String> topicList = Translator.translateTopics(topics);
        Map<String, String> varMap = Translator.translateVariables(variables);

        String original = originalContent.toString();
        Map<String, String> interpMap = Translator.translateVariables(interpretations);

        String prompt = String.format(
            "Using the original content: \"%s\" and its interpretation: \"%s\", " +
            "create a new tweet that also discusses %s and includes the following characteristics: %s",
            original, interpMap.toString(), topicList.toString(), varMap.toString()
        );

        System.out.print("\nPROMPT: " + prompt + "\n");

        return getResponse(prompt);
    }

    public String sentiment(String text) {
        String prompt = String.format(
            "Analyze the following text and determine its sentiment. Respond only with one of these labels: Positive, Negative, or Neutral. " + 
            "Do not add any explanations or punctuation.\n " +
            "Text: %s", text);

        System.out.print("\nPROMPT: " + prompt + "\n");

        return getResponse(prompt);
    }

    private String getResponse(String prompt) {
        final int maxRetries = 3; 
        final long retryDelay = 1000; 
        int attempt = 0;

        while (attempt < maxRetries) {
            try {
                GenerateContentResponse response = client.models.generateContent(model, prompt, null);
                System.out.print("\nRESPONSE: " + response.text() + "\n");
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
