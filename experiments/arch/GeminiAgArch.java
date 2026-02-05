package arch;

import jason.architecture.AgArch;
import jason.asSyntax.*;
import java.util.regex.Pattern;
import java.util.regex.Matcher;

import java.util.List;
import java.util.Map;

import lib.Translator;

import com.google.genai.Client;
import com.google.genai.types.GenerateContentConfig;
import com.google.genai.types.GenerateContentResponse;

public class GeminiAgArch extends AgArch implements LlmAgArch{

    private final Client client = new Client();
    private static final String model = "gemini-2.0-flash"; 
    private static final GenerateContentConfig config = GenerateContentConfig.builder().temperature(0.7f).build();

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
            "Consider and respond to the full context of the conversation. Avoid repetition; introduce new angles or synthesize previous ideas.\n" +
            "You may tag the users you are replying to.\n" +
            "Stay under 280 characters per message.", 
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

    public Term affectivity(Term currentAffect, Term context, Term content) {
        Structure ctx = (Structure) context;
        String politicalStandpoint = fromJasonString(ctx.getTerm(0));
        String demographics        = fromJasonString(ctx.getTerm(1));
        String persona             = fromJasonString(ctx.getTerm(2));

        int lr = 0, ld = 0, hr = 0, hd = 0;

        boolean hasCurrent = currentAffect != null;
        boolean hasContent = content != null;

        if (hasCurrent) {
            Structure affect = (Structure) currentAffect;
            lr = solveInt(affect.getTerm(0));
            ld = solveInt(affect.getTerm(1));
            hr = solveInt(affect.getTerm(2));
            hd = solveInt(affect.getTerm(3));
        }

        StringBuilder prompt = new StringBuilder();

        prompt.append(String.format(
            "You are %s. %s %s\n",
            politicalStandpoint,
            demographics,
            persona
        ));

        if (hasCurrent) {
            prompt.append(String.format(
                "Your previous responses to the questionnaire are: \n" +
                "Q1: %d\n" +
                "Q2: %d\n" +
                "Q3: %d\n" +
                "Q4: %d\n",
                lr, ld, hr, hd
            ));
        }

        if (hasContent) {
            prompt.append(String.format(
                "Based on the conversation:\n\"%s\"\n",
                fromJasonString(content)
            ));
        }

        prompt.append(
            "Q1. On a scale from 0 to 10, where 0 represents no support at all and 10 signifies unwavering support, " +
            "how would you rate your level of support for the Republican Party?\n" +
            "Q2. On a scale from 0 to 10, where 0 represents no support at all and 10 signifies unwavering support, " +
            "how would you rate your level of support for the Democratic Party?\n" +
            "Q3. On a scale from 0 to 10, where 0 means no dislike at all and 10 represents extreme hatred, " +
            "how would you rate your level of dislike for the Republican Party?\n" +
            "Q4. On a scale from 0 to 10, where 0 means no dislike at all and 10 represents extreme hatred, " +
            "how would you rate your level of dislike for the Democratic Party?\n" +
            "Reply to the four questions using the format <question identifier>: <value>. " +
            "Just return the values."
        );

        // -------- Call LLM --------
        String response = getResponse(prompt.toString());

        int[] values = parseQFormat(response);

        // -------- Return affect structure --------
        return ASSyntax.createStructure(
            "affect",
            new NumberTermImpl(values[0]), // Love Rep
            new NumberTermImpl(values[1]), // Love Dem
            new NumberTermImpl(values[2]), // Hate Rep
            new NumberTermImpl(values[3])  // Hate Dem
        );
    }

    private int solveInt(Term t) {
        try {
            return (int) ((NumberTerm) t).solve();
        } catch (Exception e) {
            throw new RuntimeException("Expected a NumberTerm, but got: " + t, e);
        }
    }


    /**
     * Parses responses like:
     * Q1: 3
     * Q2: 7
     * Q3: 2
     * Q4: 6
     */
    private int[] parseQFormat(String response) {

        int[] values = new int[4];

        Pattern p = Pattern.compile(
            "Q([1-4])\\s*:\\s*(\\d+)",
            Pattern.CASE_INSENSITIVE
        );

        Matcher m = p.matcher(response);

        while (m.find()) {
            int index = Integer.parseInt(m.group(1)) - 1;
            int value = Integer.parseInt(m.group(2));
            values[index] = value;
        }

        // basic validation
        for (int i = 0; i < 4; i++) {
            if (values[i] < 0 || values[i] > 10) {
                throw new RuntimeException(
                    "Invalid affectivity response: " + response
                );
            }
        }

        return values;
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
                GenerateContentResponse response = client.models.generateContent(model, prompt, config);
                System.out.print("\nPROMPT: " + prompt + "\n");
                System.out.print("RESPONSE:\n" + response.text() + "\n");
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
