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

    /**
     * Called by ia.createContent.
     * For the audit agent, topics is an empty list and variables contains:
     *   stance, targetLeaf, parentClaim, siblings
     */
    public String createContent(Term topics, Term variables) {
        Map<String, Object> varMap = JasonToJavaTranslator.translateVariables(variables);

        String stance      = relationToStance(varMap.get("stance"));
        String targetLeaf  = stringify(varMap.get("targetLeaf"));
        String parent      = stringify(varMap.getOrDefault("parentClaim", ""));
        Object siblingsRaw = varMap.getOrDefault("siblings", List.of());
        String siblings;
        if (siblingsRaw instanceof List<?> list) {
            if (list.isEmpty()) {
                siblings = "(no other arguments in this branch)";
            } else {
                siblings = list.stream()
                            .map(item -> stringify(item))
                            .collect(java.util.stream.Collectors.joining("\n"));
            }
        } else {
            siblings = stringify(siblingsRaw);
        }

        String prompt = String.format(
            "You are a neutral moderator participating in an online debate to reduce polarization.\n\n" +
            "Target claim (the message you are directly replying to):\n\"%s\"\n\n" +
            "Parent claim (the message the target claim responds to):\n\"%s\"\n\n" +
            "Other arguments already in this branch:\n%s\n\n" +
            "Your task:\n" +
            "- Write a %s argument responding to the target claim\n" +
            "- Be persuasive and concise (2-4 sentences)\n" +
            "- Do NOT repeat existing arguments\n" +
            "- Add new reasoning or evidence\n" +
            "- Your goal is to rebalance the conversation, not to inflame it\n",
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

    private static String stringify(Object o) {
        if (o == null) return "";
        return o.toString();
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
