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
    private static final String model = "gemini-2.5-flash";

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

    public String reply(Term politicalStandpoint, Term demographics, Term personaDescription, Term conversation) {
        String prompt = String.format(
            "Your are %s. %s %s\n" +
            "You are a Twitter user reading the following thread: \n '%s'\n" +
            "Reply to it. Stay under 280 characters per message", 
            fromJasonString(politicalStandpoint),
            fromJasonString(demographics),
            fromJasonString(personaDescription),
            fromJasonString(conversation));

        System.out.print("\nPROMPT: " + prompt + "\n");

        return getResponse(prompt);
    }

    public String sentiment(Term text) {
        String prompt = String.format(
            "Analyze the following text and determine its sentiment. Respond only with one of these labels: Positive, Negative, or Neutral. " + 
            "Do not add any explanations or punctuation.\n " +
            "Text: %s", fromJasonString(text));

        System.out.print("\nPROMPT: " + prompt + "\n");

        return getResponse(prompt);
    }

    public int updateLove(Term group, Term current, Term politicalStandpoint, Term demographics, Term personaDescription, Term content) {
        String prompt = String.format(
            "Your are %s. %s %s\n" +
            "Your current level of support for %s is %s (on a scale from 0 to 10). \n" +
            "Given the following message: \n '%s'\n" +
            "On a scale from 0 to 10, where 0 represents no support at all and 10 signifies unwavering support, how would you now rate your level of support for %s after considering the message above?\n" +
            "Respond with a single integer between 0 and 10.", 
            fromJasonString(politicalStandpoint),
            fromJasonString(demographics),
            fromJasonString(personaDescription),
            fromJasonString(group),
            fromJasonString(current),
            fromJasonString(content),
            fromJasonString(group));
        return Integer.parseInt(getResponse(prompt));
    }

    public int updateHate(Term group, Term current, Term politicalStandpoint, Term demographics, Term personaDescription, Term content) {
        String prompt = String.format(
            "Your are %s. %s %s\n" +
            "Your current level of dislike for %s is %s (on a scale from 0 to 10). \n" +
            "Given the following message: \n '%s'\n" +
            "On a scale from 0 to 10, where 0 means no dislike at all and 10 represents extreme hatred, how would you now rate your level of dislike for %s after considering the message above?\n" +
            "Respond with a single integer between 0 and 10.", 
            fromJasonString(politicalStandpoint),
            fromJasonString(demographics),
            fromJasonString(personaDescription),
            fromJasonString(group),
            fromJasonString(current),
            fromJasonString(content),
            fromJasonString(group));
        return Integer.parseInt(getResponse(prompt));
    }

    public int initiateLove(Term group, Term politicalStandpoint, Term demographics, Term personaDescription) {
        String prompt = String.format(
            "Your are %s. %s %s\n" +
            "On a scale from 0 to 10, where 0 represents no support at all and 10 signifies unwavering support, how would you now rate your level of support for %s?\n" +
            "Respond with a single integer between 0 and 10.", 
            fromJasonString(politicalStandpoint),
            fromJasonString(demographics),
            fromJasonString(personaDescription),
            fromJasonString(group));
        return Integer.parseInt(getResponse(prompt));
    }

    public int initiateHate(Term group, Term politicalStandpoint, Term demographics, Term personaDescription) {
        String prompt = String.format(
            "Your are %s. %s %s\n" +
            "On a scale from 0 to 10, where 0 means no dislike at all and 10 represents extreme hatred, how would you now rate your level of dislike for %s?\n" +
            "Respond with a single integer between 0 and 10.", 
            fromJasonString(politicalStandpoint),
            fromJasonString(demographics),
            fromJasonString(personaDescription),
            fromJasonString(group));
        return Integer.parseInt(getResponse(prompt));
    }

    private String getResponse(String prompt) {
        final int maxRetries = 3; 
        final long retryDelay = 1000; 
        int attempt = 0;

        while (attempt < maxRetries) {
            try {
                GenerateContentResponse response = client.models.generateContent(model, prompt, null);
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
