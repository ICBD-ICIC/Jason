package arch;

import jason.architecture.AgArch;
import jason.asSyntax.*;
import lib.JasonToJavaTranslator;

import java.util.*;

/**
 * CoNVaI agent architecture.
 *
 * Responsible for computing the three LLM-based textual probability
 * components from PTX = {Pnov, Prpl, Pnw} (Algorithms 2-4):
 *
 * interpretContent(contentTerm, pastMessagesTerm) receives:
 *   - contentTerm:      the message text (Jason Term)
 *   - pastMessagesTerm: list of previously read messages by this agent (Jason Term)
 *
 * Returns a map with exactly four keys:
 *   - pnov   (double):       novelty — semantic/lexical divergence from prior messages.
 *   - prpl   (double):       engagement likelihood — how likely this provokes a reply.
 *   - pnw    (double):       cumulative influence — how broadly impactful the message seems.
 *   - topics (List<String>): 1–5 short topic labels extracted from the message content.
 *
 * createContent() generates tweet text once the ASL f() function has already decided to spread,
 * and now incorporates the message's topics to produce more contextually grounded output.
 */
public class CoNVaIGeminiAgArch extends AgArch implements SocialAgArch {

    private final GeminiClient gemini = new GeminiClient();

    // ----------------------------------------------------------------
    // SocialAgArch — interpretContent
    // ----------------------------------------------------------------

    /**
     * Estimates Pnov, Prpl, Pnw, and a topics list for {@code contentTerm}
     * given the agent's reading history ({@code pastMessagesTerm}).
     *
     * @param contentStructure Jason structure expected to contain:
     *                         - Term 0: content string
     *                         - Term 1: list of past messages (strings)
     * @return Map with keys "pnov", "prpl", "pnw" (doubles in [0,1]) and
     *         "topics" (List<String>; of 1–5 short labels).
     */
    @Override
    public Map<String, Object> interpretContent(Term contentStructure) {
        Structure s       = (Structure) contentStructure;
        String content    = JasonToJavaTranslator.translateString(s.getTerm(0));
        List<String> past = JasonToJavaTranslator.translateTopics(s.getTerm(1));

        String prompt = buildInterpretPrompt(content, past);
        String raw    = gemini.getResponse(prompt);
        return parseInterpretation(raw);
    }

    /**
     * Builds a single prompt that asks the LLM to estimate all three
     * PTX components and extract topics in one shot.
     */
    private String buildInterpretPrompt(String content, List<String> pastMessages) {
        String historyBlock = pastMessages.isEmpty()
            ? "(none)"
            : "- " + String.join("\n- ", pastMessages);

        return String.format(
            "You are an analytical engine for an information-diffusion simulation.\n" +
            "Given an agent's reading history and a new message, estimate three scores " +
            "and extract the main topics.\n\n" +

            "=== READING HISTORY (messages the agent has already seen, most recent first) ===\n" +
            "%s\n\n" +

            "=== NEW MESSAGE ===\n" +
            "\"%s\"\n\n" +

            "=== TASK ===\n" +
            "Return ONLY a JSON object with exactly these four keys:\n\n" +

            "  \"pnov\" — Novelty (float in [0.0, 1.0]): semantic and lexical divergence of\n" +
            "            the new message from the reading history. 1.0 = entirely new\n" +
            "            topic/vocabulary, 0.0 = near-duplicate of something already seen.\n\n" +

            "  \"prpl\" — Engagement likelihood (float in [0.0, 1.0]): probability that a\n" +
            "            typical user would reply to or interact with this message, based on\n" +
            "            its emotional charge, rhetorical features, call-to-action language,\n" +
            "            and controversy.\n\n" +

            "  \"pnw\"  — Cumulative influence (float in [0.0, 1.0]): how broadly impactful\n" +
            "            this message is likely to become overall, considering topic salience,\n" +
            "            shareability, and persuasive strength.\n\n" +

            "  \"topics\" — Topics (array of 1–5 short strings): the main subjects or themes\n" +
            "            present in the new message. Each label should be 1–3 words, lowercase,\n" +
            "            and specific enough to guide a reply (e.g. \"vaccine safety\",\n" +
            "            \"election fraud\", \"climate policy\").\n\n" +

            "No markdown, no explanation — output the raw JSON object only.",
            historyBlock, content
        );
    }

    // ----------------------------------------------------------------
    // SocialAgArch — createContent
    // ----------------------------------------------------------------

    /**
     * Generates tweet text for an agent that has already decided
     * (via the CoNVaI f() function in the ASL) to spread or debunk.
     *
     * @param topics    Jason list term of topic strings extracted during
     *                  {@link #interpretContent}. Used to ground the reply
     *                  in the message's actual subject matter.
     * @param variables Jason structure whose map must contain "state" and "content".
     */
    @Override
    public String createContent(Term topics, Term variables) {
        Map<String, Object> varMap = JasonToJavaTranslator.translateVariables(variables);

        String agentState = stringify(varMap.get("state"));
        boolean spreading = agentState.equals("infected");

        String content = stringify(varMap.get("content"));

        // Build a comma-separated topic hint from the topics term.
        List<String> topicList = JasonToJavaTranslator.translateTopics(topics);
        String topicHint = topicList.isEmpty()
            ? ""
            : " The discussion covers the following topics: " +
              String.join(", ", topicList) + ".";

        String stance = spreading
            ? "You believe this information and want to spread it."
            : "You think this information is false and want to debunk it.";

        String prompt = String.format(
            "You are a social media user. %s%s " +
            "Write a single tweet (max 280 characters) replying to: %s. " +
            "Reply with only the tweet text, no commentary.",
            stance, topicHint, content
        );

        return gemini.getResponse(prompt);
    }

    // ----------------------------------------------------------------
    // Helpers
    // ----------------------------------------------------------------

    /**
     * Parses the LLM response into a map containing "pnov", "prpl", "pnw",
     * and "topics". Falls back to 0.0 / empty list for any key that cannot
     * be extracted.
     */
    private Map<String, Object> parseInterpretation(String raw) {
        Map<String, Object> result = new LinkedHashMap<>();
        result.put("pnov",   0.0);
        result.put("prpl",   0.0);
        result.put("pnw",    0.0);
        result.put("topics", new ArrayList<String>());

        try {
            String clean = raw.replaceAll("(?s)```json|```", "").trim();
            com.fasterxml.jackson.databind.ObjectMapper mapper =
                new com.fasterxml.jackson.databind.ObjectMapper();

            @SuppressWarnings("unchecked")
            Map<String, Object> parsed = mapper.readValue(clean, Map.class);

            for (String key : List.of("pnov", "prpl", "pnw")) {
                if (parsed.containsKey(key)) {
                    double value = ((Number) parsed.get(key)).doubleValue();
                    result.put(key, Math.min(value, 1.0));
                }
            }

            if (parsed.containsKey("topics")) {
                Object raw_topics = parsed.get("topics");
                if (raw_topics instanceof List<?> list) {
                    List<String> topics = list.stream()
                        .filter(Objects::nonNull)
                        .map(Object::toString)
                        .toList();
                    result.put("topics", topics);
                }
            }
        } catch (Exception e) {
            System.err.println("[CoNVaIGeminiAgArch] Failed to parse interpretation JSON: "
                + e.getMessage() + " | raw=" + raw);
        }

        return result;
    }

    private static String stringify(Object o) {
        return o == null ? "" : o.toString();
    }
}