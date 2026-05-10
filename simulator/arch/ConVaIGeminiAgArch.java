package arch;

import jason.architecture.AgArch;
import jason.asSyntax.*;
import lib.JasonToJavaTranslator;

import java.util.*;
import java.util.logging.Logger;

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
 *   - topics (List<String>): 1-5 short topic labels extracted from the message content.
 *
 * createContent() generates tweet text once the ASL f() function has already decided to spread,
 * and incorporates the message's topics to produce more contextually grounded output.
 */
public class CoNVaIGeminiAgArch extends AgArch implements SocialAgArch {

    private static final GeminiClient gemini = new GeminiClient();

    private static final com.fasterxml.jackson.databind.ObjectMapper MAPPER =
        new com.fasterxml.jackson.databind.ObjectMapper();

    private static final Logger logger = Logger.getLogger(CoNVaIGeminiAgArch.class.getName());
    /**
     * Estimates Pnov, Prpl, Pnw, and a topics list for a given message content,
     * given the agent's reading history.
     *
     * @param contentStructure Jason structure expected to contain:
     *                         - Term 0: content string
     *                         - Term 1: list of past messages (strings)
     *                         - Term 2: current cycle (int)
     *                         - Term 3: cycle of the message creation (int)
     * @return Map with keys "pnov", "prpl", "pnw" (doubles in [0,1]) and
     *         "topics" (List<String>; of 1-5 short labels).
     */
    @Override
    public Map<String, Object> interpretContent(Term contentStructure) {
        Structure s       = (Structure) contentStructure;
        String content    = JasonToJavaTranslator.translateString(s.getTerm(0));
        List<String> past = JasonToJavaTranslator.translateTopics(s.getTerm(1));
        int currentCycle  = JasonToJavaTranslator.translateInt(s.getTerm(2));
        int messageCycle  = JasonToJavaTranslator.translateInt(s.getTerm(3));

        // pnw: cached per conversation root as a plain double — no map involved
        String convCacheKey = "conv\u0000" + content.strip().replaceAll("\\s+", " ");
        double pnw = SharedInterpretationCache.getDouble(convCacheKey, k -> {
            String prompt = buildInfluencePrompt(content);
            String raw    = gemini.getResponse(prompt, GeminiClient.CONFIG_ANALYTICAL);
            return parseDouble(raw, "pnw");
        });

        // pnov, prpl, topics: never cached — always fresh per message
        List<String> recentWindow = past.size() > 3 ? past.subList(0, 3) : past;
        String prompt     = buildMessagePrompt(content, recentWindow, past.size());
        String raw        = gemini.getResponse(prompt, GeminiClient.CONFIG_ANALYTICAL);
        Map<String, Object> msgResult = parseInterpretation(raw);

        // Merge
        Map<String, Object> merged = new LinkedHashMap<>(msgResult);
        merged.put("pnw", pnw);

        logger.info(String.format(
            "[CoNVaIGeminiAgArch] interpretContent | content=\"%s\" | pnov=%.3f | prpl=%.3f | pnw=%.3f | topics=%s",
            content, merged.get("pnov"), merged.get("prpl"), merged.get("pnw"), merged.get("topics")
        ));

        return applyTimeDecay(merged, currentCycle, messageCycle, past.size());
    }

    private Map<String, Object> applyTimeDecay(Map<String, Object> base, int t, int ini, int historySize) {
        Map<String, Object> result = new LinkedHashMap<>(base);

        double pnovBase = (double) base.get("pnov");
        double prplBase = (double) base.get("prpl");

        // Temporal decay from paper: Gaussian over (t - ini)
        double timeDiff = t - ini;
        // double fnov = 0.1;
        double gaussianDecay = Math.exp(-(timeDiff * timeDiff) / (2.0 * 100.0));
        double pnov = pnovBase * gaussianDecay;

        // P_rpl: combine temporal decay AND agent saturation
        // historySaturation: e^(-0.1 * historySize) → 1.0 at 0 messages, ~0.37 at 10, ~0.14 at 20
        double historySaturation = Math.exp(-0.1 * historySize);
        double temporalScale = Math.max(0.05, 1.0 - (t / 1000.0));
        double prpl = prplBase * historySaturation * temporalScale;

        result.put("pnov", Math.min(pnov, 1.0));
        result.put("prpl", Math.min(prpl, 1.0));
        return result;
    }

    /**
     * Prompt for pnw only — keyed per conversation root.
     * No history needed since cumulative influence is a property of the content itself.
     */
    private String buildInfluencePrompt(String content) {
        return String.format(
            "You are an analytical engine for a social media diffusion simulation.\n\n" +

            "=== MESSAGE ===\n" +
            "\"%s\"\n\n" +

            "Return ONLY a JSON object with one key:\n\n" +

            "\"pnw\": float [0.0-1.0]. The cumulative influence of this message — how broadly\n" +
            "  impactful it is likely to become overall, considering topic salience,\n" +
            "  shareability, and persuasive strength.\n\n" +

            "No markdown. No explanation. Raw JSON only.",
            content
        );
    }

    /**
     * Prompt for pnov + prpl + topics — keyed per message + agent history.
     * These are agent-relative: they depend on what this agent has already seen.
     */
    private String buildMessagePrompt(String content, List<String> recentWindow, int totalSeen) {
        String recentBlock = recentWindow.isEmpty()
            ? "(none — this is the first message)"
            : "- " + String.join("\n- ", recentWindow);

        String seenNote = totalSeen == 0
            ? "This is the first message the agent has seen."
            : "The agent has read " + totalSeen + " messages in this conversation so far.";

        return String.format(
            "You are an analytical engine for a social media diffusion simulation.\n\n" +

            "=== LAST 3 MESSAGES THIS AGENT READ (most recent first) ===\n" +
            "%s\n\n" +

            "=== NEW MESSAGE TO EVALUATE ===\n" +
            "\"%s\"\n\n" +

            "%s\n\n" +

            "=== YOUR TASK ===\n" +
            "Return ONLY a valid JSON object with exactly these three keys.\n\n" +

            "\"pnov\": float [0.0-1.0]. How much NEW information does this message introduce\n" +
            "  compared only to the last 3 messages above?\n" +
            "  - 0.0 = near-verbatim repeat of something just seen\n" +
            "  - 0.2 = same topic, minor rephrasing\n" +
            "  - 0.4 = same topic, adds a new claim or detail\n" +
            "  - 0.6 = shifts angle or introduces a new sub-topic\n" +
            "  - 0.8 = substantially new framing or evidence\n" +
            "  - 1.0 = completely new topic\n" +
            "  Do NOT return 0.0 unless the message is a near-verbatim duplicate.\n\n" +

            "\"prpl\": float [0.0-1.0]. How likely is a typical social media user to reply\n" +
            "  to this specific message? Consider emotional charge, controversy, calls to\n" +
            "  action, and rhetorical provocation. Independent of novelty.\n\n" +

            "\"topics\": array of 1-5 strings. The specific subjects raised IN THIS MESSAGE.\n" +
            "  Use the actual message content, not the conversation theme. Each label 1-3\n" +
            "  words, lowercase. E.g. [\"police cover-up\", \"eyewitness accounts\"] not\n" +
            "  just [\"ottawa shooting\"].\n\n" +

            "No markdown. No explanation. Raw JSON only.",
            recentBlock, content, seenNote
        );
    }
    
    private double parseDouble(String raw, String key) {
        try {
            String clean = raw.replaceAll("(?s)```json|```", "").trim();
            @SuppressWarnings("unchecked")
            Map<String, Object> parsed = MAPPER.readValue(clean, Map.class);
            if (parsed.containsKey(key)) {
                return Math.max(0.0, Math.min(((Number) parsed.get(key)).doubleValue(), 1.0));
            }
        } catch (Exception e) {
            logger.warning("[CoNVaIGeminiAgArch] Failed to parse pnw: " + e.getMessage());
        }
        return 0.0;
    }

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

        String agentState = String.valueOf(varMap.get("state"));
        boolean spreading = agentState.equals("infected");

        String content = String.valueOf(varMap.get("content"));

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

        return gemini.getResponse(prompt, GeminiClient.CONFIG_CREATIVE);
    }

    /**
     * Parses the LLM response into a map containing "pnov", "prpl", "pnw",
     * and "topics". Falls back to 0.0 / empty list for any key that cannot
     * be extracted.
     */
    private Map<String, Object> parseInterpretation(String raw) {
        Map<String, Object> result = new LinkedHashMap<>();
        // Defaults for all possible keys
        result.put("pnov",   0.0);
        result.put("prpl",   0.0);
        result.put("pnw",    0.0);
        result.put("topics", new ArrayList<String>());

        if (raw == null || raw.isBlank()) {
            logger.warning("[CoNVaIGeminiAgArch] Empty response from Gemini, using defaults.");
            return result;
        }

        try {
            String clean = raw.replaceAll("(?s)```json|```", "").trim();

            @SuppressWarnings("unchecked")
            Map<String, Object> parsed = MAPPER.readValue(clean, Map.class);

            for (String key : List.of("pnov", "prpl", "pnw")) {
                if (parsed.containsKey(key)) {
                    double value = ((Number) parsed.get(key)).doubleValue();
                    result.put(key, Math.max(0.0, Math.min(value, 1.0)));
                }
            }

            if (parsed.containsKey("topics")) {
                Object rawTopics = parsed.get("topics");
                if (rawTopics instanceof List<?> list) {
                    List<String> topics = list.stream()
                        .filter(Objects::nonNull)
                        .map(Object::toString)
                        .toList();
                    result.put("topics", topics);
                }
            }
        } catch (Exception e) {
            logger.warning("[CoNVaIGeminiAgArch] Failed to parse interpretation JSON: "
                + e.getMessage() + " | raw=" + raw);
        }

        return result;
    }
}