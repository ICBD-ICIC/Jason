package arch;

import jason.architecture.AgArch;
import jason.asSyntax.Term;
import lib.JasonToJavaTranslator;

import java.util.*;

/**
 * Condition 2: CoNVaI agent architecture.
 *
 * Responsible for computing the three LLM-based textual probability
 * components from PTX = {Pnov, Prpl, Pnw} (Algorithms 2-4):
 * 
 * interpretContent(content, variables) receives:
 *   - content:   the message text
 *   - variables: map containing at minimum pusr(float)
 *
 * Returns a map with:
 *   - Pnov(p): novelty of content relative to recently seen content.
 *   - Prpl(p): likelihood of engaging at this point in the diffusion timeline (engagement over time).
 *   - Pnw(p):  predicted cumulative engagement/influence.
 *
 * createContent() generates tweet text once the ASL f() function has
 * already decided to spread.
 */
public class ConVaIGeminiAgArch extends AgArch implements SocialAgArch {

    private final GeminiClient gemini = new GeminiClient();

    // Sliding window of recently seen content per agent for Pnov estimation.
    private static final Map<String, Deque<String>> recentContentByAgent =
        Collections.synchronizedMap(new HashMap<>());

    private static final int CONTEXT_WINDOW_SIZE = 10;

    // ----------------------------------------------------------------
    // SocialAgArch — interpretContent
    // ----------------------------------------------------------------

    /**
     * Accepts content encoded as "post text|||pusr=0.42" so the ASL
     * can pass both the message and the author influence score in a
     * single Term without changing the SocialAgArch signature.
     */
    @Override
    public Map<String, Object> interpretContent(Term contentTerm) {
        String agentName  = getAgName();
        String contentStr = JasonToJavaTranslator.translateString(contentTerm);

        double pusr = 0.0;
        String pureContent = contentStr;
        if (contentStr.contains("|||")) {
            String[] parts = contentStr.split("\\|\\|\\|", 2);
            pureContent = parts[0];
            try {
                pusr = Double.parseDouble(parts[1].replace("pusr=", "").trim());
            } catch (NumberFormatException e) {
                System.err.println("[ConVaIGeminiAgArch] Could not parse pusr from: " + parts[1]);
            }
        }

        Deque<String> recentContent = recentContentByAgent
            .computeIfAbsent(agentName, k -> new ArrayDeque<>());

        String prompt = buildInterpretPrompt(pureContent, pusr, recentContent);
        String raw    = gemini.getResponse(prompt);
        Map<String, Object> result = parseInterpretation(raw);

        synchronized (recentContent) {
            recentContent.addLast(pureContent);
            if (recentContent.size() > CONTEXT_WINDOW_SIZE) {
                recentContent.removeFirst();
            }
        }

        return result;
    }

    private String buildInterpretPrompt(String content,
                                        double pusr,
                                        Deque<String> recentContent) {
        String contextBlock = recentContent.isEmpty()
            ? "(none)"
            : String.join("\n- ", recentContent);

        return String.format(
            "You are evaluating a social media post for an information diffusion simulation.\n" +
            "The author's influence score (Pusr) is %.4f (range 0.0-1.0, higher = more influential).\n\n" +
            "Recently seen posts by this agent:\n- %s\n\n" +
            "New post to evaluate: \"%s\"\n\n" +
            "Respond ONLY with a JSON object (no markdown, no explanation) with these keys:\n" +
            "  \"pnov\": float 0.0-1.0 — how novel is this post compared to recent ones " +
                        "(1.0 = completely new topic, 0.0 = already seen).\n" +
            "  \"prpl\": float 0.0-1.0 — how likely is engagement with this post RIGHT NOW " +
                        "given its age and momentum in the diffusion timeline " +
                        "(higher early in diffusion, lower as momentum fades).\n" +
            "  \"pnw\": float 0.0-1.0 — predicted cumulative engagement this post will receive.\n" +
            "  \"state_suggestion\": \"infected\" | \"vaccinated\" | \"neutral\" — " +
                        "would a typical user believe (infected), debunk (vaccinated), " +
                        "or ignore (neutral) this post?\n" +
            "  \"credibility\": \"high\" | \"medium\" | \"low\".\n" +
            "  \"misinformation_risk\": \"high\" | \"medium\" | \"low\".",
            pusr, contextBlock, content
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
        List<String> topicList = JasonToJavaTranslator.translateTopics(topics);
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

    private Map<String, Object> parseInterpretation(String raw) {
        Map<String, Object> result = new LinkedHashMap<>();
        try {
            String clean = raw.replaceAll("(?s)```json|```", "").trim();
            com.fasterxml.jackson.databind.ObjectMapper mapper =
                new com.fasterxml.jackson.databind.ObjectMapper();
            @SuppressWarnings("unchecked")
            Map<String, Object> parsed = mapper.readValue(clean, Map.class);
            result.putAll(parsed);
        } catch (Exception e) {
            System.err.println("[ConVaIGeminiAgArch] Failed to parse interpretation JSON: " + e.getMessage());
            result.put("raw", raw);
        }
        return result;
    }
}
