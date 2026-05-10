package arch;

import jason.architecture.AgArch;
import jason.asSyntax.*;
import lib.JasonToJavaTranslator;

import java.util.*;
import java.util.stream.Collectors; 
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

        // --- Cache 1: per conversation root (pnw + topics) ---
        // pnw is a fixed property of the news piece itself, not of any reply.
        // We key only on the root content so all replies share the same pnw.
        String convCacheKey = "conv\u0000" + content.strip().replaceAll("\\s+", " ");
        Map<String, Object> convLevel = SharedInterpretationCache.get(convCacheKey, k -> {
            String prompt = buildInfluencePrompt(content);
            String raw    = gemini.getResponse(prompt, GeminiClient.CONFIG_ANALYTICAL);
            return parseInterpretation(raw);
        });

        // --- Cache 2: per message + history (pnov + prpl) ---
        // These depend on what this specific agent has already seen,
        // so the full history must be part of the cache key.
        List<String> recentWindow = past.size() > 3 ? past.subList(0, 3) : past;
        String msgCacheKey = content.strip().replaceAll("\\s+", " ")
            + "\u0000"
            + recentWindow.stream()
                .map(m -> m.strip().replaceAll("\\s+", " "))
                .collect(Collectors.joining("\u0000"));

        Map<String, Object> msgLevel = SharedInterpretationCache.get(msgCacheKey, k -> {
            String prompt = buildEngagementPrompt(content, past); // still passes full past for context size
            String raw    = gemini.getResponse(prompt, GeminiClient.CONFIG_ANALYTICAL);
            return parseInterpretation(raw);
        });

        // --- Merge and apply time decay ---
        Map<String, Object> merged = new LinkedHashMap<>();
        merged.put("pnov",   msgLevel.getOrDefault("pnov",   0.0));
        merged.put("prpl",   msgLevel.getOrDefault("prpl",   0.0));
        merged.put("pnw",    convLevel.getOrDefault("pnw",   0.0));
        merged.put("topics", convLevel.getOrDefault("topics", new ArrayList<String>()));

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
     * Prompt for pnw + topics only — keyed per conversation root.
     * No history needed since cumulative influence is a property of the content itself.
     */
    private String buildInfluencePrompt(String content) {
        return String.format(
            "You are an analytical engine for an information-diffusion simulation.\n" +
            "Given a social media message, estimate its cumulative influence and extract topics.\n\n" +

            "=== MESSAGE ===\n" +
            "\"%s\"\n\n" +

            "=== TASK ===\n" +
            "Return ONLY a JSON object with exactly these two keys:\n\n" +

            "  \"pnw\"  — Cumulative influence (float in [0.0, 1.0]): how broadly impactful\n" +
            "            this message is likely to become overall, considering topic salience,\n" +
            "            shareability, and persuasive strength.\n\n" +

            "  \"topics\" — Topics (array of 1-5 short strings): the main subjects or themes\n" +
            "            present in the message. Each label should be 1-3 words, lowercase,\n" +
            "            and specific enough to guide a reply (e.g. \"vaccine safety\",\n" +
            "            \"election fraud\", \"climate policy\").\n\n" +

            "No markdown, no explanation — output the raw JSON object only.",
            content
        );
    }

    /**
     * Prompt for pnov + prpl only — keyed per message + agent history.
     * These are agent-relative: they depend on what this agent has already seen.
     */
    private String buildEngagementPrompt(String content, List<String> pastMessages) {
        // For pnov: only use the last 3 messages — mirrors KL-divergence over a recent window
        // For prpl: the full history size matters for saturation
        List<String> recentWindow = pastMessages.size() > 3
            ? pastMessages.subList(0, 3)  // list is most-recent-first
            : pastMessages;

        String recentBlock = recentWindow.isEmpty()
            ? "(none — this is the first message the agent has seen)"
            : "- " + String.join("\n- ", recentWindow);

        String fullHistorySize = pastMessages.isEmpty()
            ? "This is the first message."
            : "The agent has read " + pastMessages.size() + " messages in this conversation so far.";

        return String.format(
            "You are an analytical engine for an information-diffusion simulation.\n\n" +

            "=== RECENT MESSAGES (last 3 the agent read, most recent first) ===\n" +
            "%s\n\n" +

            "=== NEW MESSAGE ===\n" +
            "\"%s\"\n\n" +

            "=== CONTEXT ===\n" +
            "%s\n\n" +

            "=== TASK ===\n" +
            "Return ONLY a JSON object with exactly these two keys:\n\n" +

            "  \"pnov\" — Novelty (float in [0.0, 1.0]): how much NEW information or vocabulary\n" +
            "            this message introduces compared to the last 3 messages shown above.\n" +
            "            Compare only to the recent window, not all history.\n" +
            "            0.0 = identical topic and wording to recent messages.\n" +
            "            0.3 = same topic but adds new claims or framing.\n" +
            "            0.7 = shifts to a related but distinct angle.\n" +
            "            1.0 = entirely new topic or vocabulary.\n" +
            "            IMPORTANT: avoid returning exactly 0.0 unless the message is a\n" +
            "            near-verbatim repeat. Even familiar topics can introduce new framing.\n\n" +

            "  \"prpl\" — Engagement likelihood (float in [0.0, 1.0]): probability that a\n" +
            "            typical user would reply to or interact with this message, based on\n" +
            "            its emotional charge, rhetorical features, call-to-action language,\n" +
            "            and controversy. This is independent of novelty.\n\n" +

            "No markdown, no explanation — output the raw JSON object only.",
            recentBlock, content, fullHistorySize
        );
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