package arch;

import jason.architecture.AgArch;
import jason.asSyntax.*;

import java.util.*;
import lib.JasonToJavaTranslator;

import com.google.genai.Client;
import com.google.genai.types.GenerateContentResponse;

public class KialoGeminiAgArch extends AgArch implements SocialAgArch {

    private final Client client = new Client();
    private static final String model = "gemini-2.0-flash";

    // ---------------- PUBLIC API ----------------

    public String createContent(Term topics, Term variables) {
        Map<String, Object> varMap = JasonToJavaTranslator.translateVariables(variables);

        String stance = relationToStance(varMap.get("stance"));
        String targetLeaf = varMap.get("targetLeaf").toString();
        String parent = varMap.getOrDefault("parentClaim", "").toString();
        String siblings = varMap.getOrDefault("siblings", "").toString();

        String prompt = String.format(
            "You are participating in an online debate.\n\n" +
            "Target claim:\n\"%s\"\n\n" +
            "Parent claim:\n\"%s\"\n\n" +
            "Other arguments in this branch:\n%s\n\n" +
            "Your task:\n" +
            "- Write a %s argument responding to the target claim\n" +
            "- Be persuasive and concise\n" +
            "- Do NOT repeat existing arguments\n" +
            "- Add new reasoning\n",
            targetLeaf,
            parent,
            siblings,
            stance
        );
        return getResponse(prompt);
    }

    public Map<String, Object> interpretContent(Term content) {
        throw new UnsupportedOperationException("interpretContent is not implemented yet.");
    }

    // ---------------- HELPERS ----------------

    private static String relationToStance(Object value) {
        if (value == null) return "neutral";
        double rel;
        try {
            rel = Double.parseDouble(value.toString());
        } catch (NumberFormatException e) {
            return value.toString();
        }
        if (rel > 0) return "pro";
        if (rel < 0) return "con";
        return "neutral";
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