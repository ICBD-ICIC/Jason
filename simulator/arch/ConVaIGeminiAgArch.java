package arch;

import jason.architecture.AgArch;
import jason.asSyntax.*;
import lib.JasonToJavaTranslator;

import java.util.*;
import java.util.logging.Logger;

/**
 * CoNVaI agent architecture (Definition 6).
 *
 * Computes PTX = {Pnov, Prpl, Pnw} via three focused LLM calls with different
 * caching strategies reflecting the semantic nature of each component:
 *
 *   Pnw    - cumulative influence of the news piece itself         → cached per conversation root
 *   Prpl   - intrinsic engagement likelihood of the message        → cached per message content
 *   topics - subjects raised in the message                        → cached per message content
 *   Pnov   - novelty relative to this agent's reading history      → cached per content + recent window
 *
 * Time decay and agent saturation are applied individually after cache lookup,
 * so each agent receives personalised effective probabilities even when raw
 * LLM scores are shared.
 */
public class CoNVaIGeminiAgArch extends AgArch implements SocialAgArch {

    private static final GeminiClient gemini = new GeminiClient();
    private static final com.fasterxml.jackson.databind.ObjectMapper MAPPER =
        new com.fasterxml.jackson.databind.ObjectMapper();
    private static final Logger logger = Logger.getLogger(CoNVaIGeminiAgArch.class.getName());

    // -------------------------------------------------------------------------
    // interpretContent  (PTX computation)
    // -------------------------------------------------------------------------

    @Override
    public Map<String, Object> interpretContent(Term contentStructure) {
        try {
            Structure s = (Structure) contentStructure;

            String       content      = JasonToJavaTranslator.translateString(s.getTerm(0));
            List<String> past         = JasonToJavaTranslator.translateTopics(s.getTerm(1));
            int          currentCycle = JasonToJavaTranslator.translateInt(s.getTerm(2));

            // ── Pnw ──────────────────────────────────────────────────────────
            String convKey = "conv\u0000" + normalise(content);
            Double cachedPnw = SharedInterpretationCache.getDoubleIfPresent(convKey);
            double pnw;
            if (cachedPnw != null) {
                pnw = cachedPnw;
            } else {
                String raw = gemini.getResponse(buildInfluencePrompt(content), GeminiClient.CONFIG_ANALYTICAL);
                pnw = parseDouble(raw, "pnw");
                SharedInterpretationCache.putDouble(convKey, pnw);
            }

            // ── Prpl + topics ─────────────────────────────────────────────────
            String msgKey = "msg\u0000" + normalise(content);
            Map<String, Object> engagement;
            Map<String, Object> cachedEng = SharedInterpretationCache.getIfPresent(msgKey);
            if (cachedEng != null) {
                engagement = cachedEng;
            } else {
                String raw = gemini.getResponse(buildEngagementPrompt(content), GeminiClient.CONFIG_ANALYTICAL);
                engagement = parseEngagement(raw);
                SharedInterpretationCache.put(msgKey, engagement);
            }

            // ── Pnov — cached per content + recent window ─────────────────────
            List<String> recentWindow = past.size() > 3 ? past.subList(0, 3) : past;

            String novKey = "nov\u0000" + normalise(content) + "\u0000" + String.join("\u0001", recentWindow);
            Double cachedPnov = SharedInterpretationCache.getDoubleIfPresent(novKey);
            double pnov;
            if (cachedPnov != null) {
                pnov = cachedPnov;
            } else {
                String novRaw = gemini.getResponse(buildNoveltyPrompt(content, recentWindow, past.size()), GeminiClient.CONFIG_ANALYTICAL);
                pnov = parseDouble(novRaw, "pnov");
                SharedInterpretationCache.putDouble(novKey, pnov);
            }

            // ── Merge & decay ─────────────────────────────────────────────────
            Map<String, Object> merged = new LinkedHashMap<>(engagement);
            merged.put("pnw",  pnw);
            merged.put("pnov", pnov);

            return applyTimeDecay(merged, currentCycle, past.size());

        } catch (Exception e) {
            logger.severe(String.format("interpretContent failed, returning safe defaults: %s", e.getMessage()));
            return safeFallback();
        }
    }

    private Map<String, Object> safeFallback() {
        Map<String, Object> result = new LinkedHashMap<>();
        result.put("pnov",   0.0);
        result.put("prpl",   0.0);
        result.put("pnw",    0.0);
        result.put("topics", new ArrayList<String>());
        return result;
    }

    // -------------------------------------------------------------------------
    // Time decay  (paper 4.2 / 4.3)
    // -------------------------------------------------------------------------

    private Map<String, Object> applyTimeDecay(Map<String, Object> base,
                                                int currentCycle,
                                                int historySize) {
        Map<String, Object> result = new LinkedHashMap<>(base);

        double historySat    = Math.exp(-0.1 * historySize);
        double temporalScale = Math.max(0.05, 1.0 - (currentCycle / 1000.0));
        double prpl          = Math.min((double) base.get("prpl") * historySat * temporalScale, 1.0);

        result.put("pnov", base.get("pnov"));
        result.put("prpl", prpl);
        return result;
    }

    // -------------------------------------------------------------------------
    // Prompts
    // -------------------------------------------------------------------------

    private String buildInfluencePrompt(String content) {
        return String.format("""
            You are an analytical engine for a social media diffusion simulation.

            === MESSAGE ===
            "%s"

            Return ONLY a JSON object with exactly one key:

            "pnw": float [0.0-1.0]. Cumulative influence of this message - how broadly
              impactful it is likely to become, considering topic salience, shareability,
              and persuasive strength.

            No markdown. No explanation. Raw JSON only.""",
            content);
    }

    private String buildEngagementPrompt(String content) {
        return String.format("""
            You are an analytical engine for a social media diffusion simulation.

            === MESSAGE ===
            "%s"

            Return ONLY a JSON object with exactly these two keys:

            "prpl": float [0.0-1.0]. Probability that a typical social media user replies
              to this message. Consider emotional charge, controversy, calls to action,
              and rhetorical provocation.

            "topics": array of 1-5 strings. Specific subjects raised IN THIS MESSAGE.
              1-3 words each, lowercase. E.g. ["police cover-up", "eyewitness accounts"].

            No markdown. No explanation. Raw JSON only.""",
            content);
    }

    private String buildNoveltyPrompt(String content, List<String> recentWindow, int totalSeen) {
        String recentBlock = recentWindow.isEmpty()
            ? "(none - this is the first message this agent has seen)"
            : "- " + String.join("\n- ", recentWindow);

        String seenNote = totalSeen == 0
            ? "This is the first message the agent has seen."
            : "This agent has read " + totalSeen + " messages in this conversation so far.";

        return String.format("""
            You are an analytical engine for a social media diffusion simulation.

            === LAST 3 MESSAGES THIS AGENT READ (most recent first) ===
            %s

            === NEW MESSAGE TO EVALUATE ===
            "%s"

            %s

            Return ONLY a JSON object with exactly one key:

            "pnov": float [0.0-1.0]. How much NEW information this message introduces
              compared to the last 3 messages above.
                0.0 = near-verbatim repeat
                0.2 = same topic, minor rephrasing
                0.4 = same topic, new claim or detail
                0.6 = related but distinct angle
                0.8 = substantially new framing or evidence
                1.0 = completely new topic
              Do NOT return 0.0 unless the message is a near-verbatim duplicate.

            No markdown. No explanation. Raw JSON only.""",
            recentBlock, content, seenNote);
    }

    // -------------------------------------------------------------------------
    // createContent  (f function - Equation 3)
    // -------------------------------------------------------------------------

    @Override
    public String createContent(Term topics, Term variables) {
        Map<String, Object> varMap = JasonToJavaTranslator.translateVariables(variables);

        boolean spreading = "infected".equals(String.valueOf(varMap.get("state")));
        String  content   = String.valueOf(varMap.get("content"));

        List<String> topicList = JasonToJavaTranslator.translateTopics(topics);
        String topicHint = topicList.isEmpty() ? "" :
            " The discussion covers: " + String.join(", ", topicList) + ".";

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

    // -------------------------------------------------------------------------
    // Parsing helpers
    // -------------------------------------------------------------------------

    private double parseDouble(String raw, String key) {
        if (raw == null || raw.isBlank()) {
            return 0.0;
        }
        try {
            String clean = raw.replaceAll("(?s)```json|```", "").trim();
            @SuppressWarnings("unchecked")
            Map<String, Object> parsed = MAPPER.readValue(clean, Map.class);
            if (parsed.containsKey(key)) {
                return Math.max(0.0, Math.min(((Number) parsed.get(key)).doubleValue(), 1.0));
            } else {
                logger.warning(String.format("parseDouble('%s'): key not found in: %s", key, raw));
            }
        } catch (Exception e) {
            logger.warning(String.format("parseDouble('%s'): JSON parse failed: %s | raw=%s", key, e.getMessage(), raw));
        }
        return 0.0;
    }

    private Map<String, Object> parseEngagement(String raw) {
        Map<String, Object> result = new LinkedHashMap<>();
        result.put("prpl",   0.0);
        result.put("topics", new ArrayList<String>());

        if (raw == null || raw.isBlank()) {
            logger.warning("parseEngagement: empty input");
            return result;
        }

        try {
            String clean = raw.replaceAll("(?s)```json|```", "").trim();
            @SuppressWarnings("unchecked")
            Map<String, Object> parsed = MAPPER.readValue(clean, Map.class);

            if (parsed.containsKey("prpl")) {
                double v = ((Number) parsed.get("prpl")).doubleValue();
                result.put("prpl", Math.max(0.0, Math.min(v, 1.0)));
            } else {
                logger.warning(String.format("parseEngagement: 'prpl' key missing. parsed keys=%s | raw=%s", parsed.keySet(), raw));
            }

            if (parsed.containsKey("topics") && parsed.get("topics") instanceof List<?> list) {
                result.put("topics", list.stream()
                    .filter(Objects::nonNull)
                    .map(Object::toString)
                    .toList());
            } else {
                logger.warning(String.format("parseEngagement: 'topics' key missing or wrong type. parsed keys=%s | raw=%s", parsed.keySet(), raw));
            }
        } catch (Exception e) {
            logger.warning(String.format("parseEngagement: JSON parse failed: %s | raw=%s", e.getMessage(), raw));
        }

        return result;
    }

    // -------------------------------------------------------------------------
    // Utilities
    // -------------------------------------------------------------------------

    private static String normalise(String s) {
        return s.strip().replaceAll("\\s+", " ");
    }
}