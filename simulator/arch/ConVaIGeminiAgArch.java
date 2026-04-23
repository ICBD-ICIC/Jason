package arch;

import jason.architecture.AgArch;
import jason.asSyntax.Term;
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
 * Returns a map with exactly three keys:
 *   - pnov (double): novelty — semantic/lexical divergence from prior messages.
 *   - prpl (double): engagement likelihood — how likely this provokes a reply.
 *   - pnw  (double): cumulative influence — how broadly impactful the message seems.
 *
 * createContent() generates tweet text once the ASL f() function has already decided to spread.
 */
public class CoNVaIGeminiAgArch extends AgArch implements SocialAgArch {

    private final GeminiClient gemini = new GeminiClient();

    // ----------------------------------------------------------------
    // SocialAgArch — interpretContent
    // ----------------------------------------------------------------

    /**
     * Estimates Pnov, Prpl, and Pnw for {@code contentTerm} given the
     * agent's reading history ({@code pastMessagesTerm}).
     *
     * @param contentTerm      Jason Term encoding the message text.
     * @param pastMessagesTerm Jason Term encoding a list of past messages.
     * @return Map with keys "pnov", "prpl", "pnw" (all doubles in [0, 1]).
     */
    @Override
    public Map<String, Object> interpretContent(Term term) {
        Structure s       = (Structure) term;
        String content    = JasonToJavaTranslator.translateString(s.getTerm(0));
        List<String> past = JasonToJavaTranslator.translateTopics(s.getTerm(1));

        String prompt = buildInterpretPrompt(content, past);
        String raw    = gemini.getResponse(prompt);
        return parseInterpretation(raw);
    }

    /**
     * Builds a single prompt that asks the LLM to estimate all three
     * PTX components in one shot.
     */
    private String buildInterpretPrompt(String content, List<String> pastMessages) {
        String historyBlock = pastMessages.isEmpty()
            ? "(none)"
            : "- " + String.join("\n- ", pastMessages);

        return String.format(
            "You are an analytical engine for an information-diffusion simulation.\n" +
            "Given an agent's reading history and a new message, estimate three scores.\n\n" +

            "=== READING HISTORY (messages the agent has already seen, most recent first) ===\n" +
            "%s\n\n" +

            "=== NEW MESSAGE ===\n" +
            "\"%s\"\n\n" +

            "=== TASK ===\n" +
            "Return ONLY a JSON object with exactly these three keys (floats in [0.0, 1.0]):\n\n" +

            "  \"pnov\" — Novelty: semantic and lexical divergence of the new message from\n" +
            "            the reading history (listed most recent first). 1.0 = entirely new\n" +
            "            topic/vocabulary, 0.0 = near-duplicate of something already seen.\n\n" +

            "  \"prpl\" — Engagement likelihood: probability that a typical user would reply\n" +
            "            to or interact with this message, based on its emotional charge,\n" +
            "            rhetorical features, call-to-action language, and controversy.\n\n" +

            "  \"pnw\"  — Cumulative influence: how broadly impactful this message is likely\n" +
            "            to become overall, considering topic salience, shareability, and\n" +
            "            persuasive strength.\n\n" +

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
     * Expects variables to contain a "state" key.
     */
    @Override
    public String createContent(Term topics, Term variables) {
        List<String> topicList   = JasonToJavaTranslator.translateTopics(topics);
        Map<String, Object> varMap = JasonToJavaTranslator.translateVariables(variables);

        String agentState = varMap.getOrDefault("state", "infected").toString();
        boolean spreading = agentState.equalsIgnoreCase("infected");

        String stance = spreading
            ? "You believe this information and want to spread it."
            : "You think this information is false and want to debunk it.";

        String prompt = String.format(
            "You are a social media user. %s " +
            "Write a single tweet (max 280 characters) about: %s. " +
            "Reflect these characteristics: %s. " +
            "Reply with only the tweet text, no commentary.",
            stance, topicList, varMap
        );

        return gemini.getResponse(prompt);
    }

    // ----------------------------------------------------------------
    // Helpers
    // ----------------------------------------------------------------

    /**
     * Parses the LLM response into a map containing exactly "pnov", "prpl", "pnw".
     * Falls back to 0.0 for any key that cannot be extracted.
     */
    private Map<String, Object> parseInterpretation(String raw) {
        Map<String, Object> result = new LinkedHashMap<>();
        result.put("pnov", 0.0);
        result.put("prpl", 0.0);
        result.put("pnw",  0.0);

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
        } catch (Exception e) {
            System.err.println("[ConVaIGeminiAgArch] Failed to parse interpretation JSON: "
                + e.getMessage() + " | raw=" + raw);
        }

        return result;
    }
}