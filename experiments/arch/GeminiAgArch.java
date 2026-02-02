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
    private static final String model = "gemini-2.0-flash";

    // ---------------- PUBLIC API ----------------

    public String createContent(Term topics, Term variables) {
        List<String> topicList = Translator.translateTopics(topics);
        Map<String, String> varMap = Translator.translateVariables(variables);
        String prompt = String.format("Create a tweet that talks about %s and has the following characteristics: %s", topicList.toString(), varMap.toString());
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
        return getResponse(prompt);
    }

    public String reply(Term politicalStandpoint, Term demographics, Term personaDescription, Term conversation) {
        String prompt = String.format(
            "Your are %s. %s %s\n" +
            "You are a Twitter user reading the following thread: \n '%s'\n" +
            "Reply to it. Stay under 280 characters per message", 
            fromJasonString(politicalStandpoint),
            fromJasonString(demographics),
            fromJasonString(personaDescription),
            fromJasonString(conversation));
        return getResponse(prompt);
    }

    public String sentiment(Term text) {
        String prompt = String.format(
            "Analyze the following text and determine its sentiment. Respond only with one of these labels: Positive, Negative, or Neutral. " + 
            "Do not add any explanations or punctuation.\n " +
            "Text: %s", fromJasonString(text));
        return getResponse(prompt);
    }

    public int affectivity(
            Term type,                     // "love" or "hate"
            Term group,
            Term current,                  // use null for initiation
            Term politicalStandpoint,
            Term demographics,
            Term personaDescription,
            Term conversation              // use null for initiation
    ) {

        String t = fromJasonString(type).toLowerCase();

        String attitudeName;
        String zeroLabel;
        String tenLabel;
        String partyAdj = partyAdjective(fromJasonString(group));

        if ("love".equals(t)) {
            attitudeName = "support";
            zeroLabel = "no support at all";
            tenLabel = "unwavering support";
        } else if ("hate".equals(t)) {
            attitudeName = "dislike";
            zeroLabel = "no dislike at all";
            tenLabel = "extreme hatred";
        } else {
            throw new IllegalArgumentException("Unknown attitude type: " + t);
        }

        boolean hasCurrent = current != null;
        boolean hasConversation = conversation != null;

        String prompt = String.format(
            "Your are %s. %s %s\n" +
            (hasCurrent
                ? "Your current level of %s for the %s Party is %s (on a scale from 0 to 10).\n"
                : "") +
            (hasConversation
                ? "Given the following thread:\n'%s'\n"
                : "") +
            "On a scale from 0 to 10, where 0 means %s and 10 means %s, " +
            "how would you rate your level of %s for the %s Party?\n" +
            "Respond with a single integer between 0 and 10.",
            fromJasonString(politicalStandpoint),
            fromJasonString(demographics),
            fromJasonString(personaDescription),
            hasCurrent ? attitudeName : "",
            hasCurrent ? partyAdjective : "",
            hasCurrent ? fromJasonString(current) : "",
            hasConversation ? fromJasonString(conversation) : "",
            zeroLabel,
            tenLabel,
            attitudeName,
            partyAdj
        );

        return getIntValue(getResponse(prompt));
    }

    private static String partyAdjective(String group) {
        String g = group.toLowerCase();

        if (g.contains("democrat")) {
            return "Democratic";
        }
        if (g.contains("republican")) {
            return "Republican";
        }
        return group;
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

    private static int getIntValue(String s) {
        try {
            return Integer.parseInt(s.trim());
        } catch (NumberFormatException e) {
            return -1; 
        }
    }
}
