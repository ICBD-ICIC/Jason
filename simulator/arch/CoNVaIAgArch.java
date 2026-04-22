package arch;

import jason.asSyntax.Term;
import lib.JasonToJavaTranslator;

import java.util.*;

/**
 * CoNVaI agent architecture.
 *
 * The CoNVaI transition logic (Algorithms 2-4) lives in the ASL,
 * which drives the BDI cycle. This arch is responsible only for
 * computing the two LLM-based textual probability components that
 * the ASL cannot compute internally:
 *
 *   - Pnov(p, t): novelty of content relative to recent context.
 *   - Pnw(p):     predicted engagement/influence of the content.
 *
 * interpretContent() returns these as a variable map so the ASL
 * can use them inside its transition guards. createContent() handles
 * text generation once the agent has already decided to spread.
 *
 * The f() decision function (whether to spread at all) remains in
 * the ASL — this arch never makes that call.
 */
public class CoNVaIAgArch extends GeminiAgArch {

    // Sliding window of recently seen content for novelty computation.
    // Keyed by agent name so each agent has its own context window.
    private static final Map<String, Deque<String>> recentContentByAgent =
        Collections.synchronizedMap(new HashMap<>());

    private static final int CONTEXT_WINDOW_SIZE = 10;

    // ----------------------------------------------------------------
    // interpretContent — returns Pnov and Pnw for the ASL
    // ----------------------------------------------------------------

    /**
     * Given a message content term, asks Gemini to estimate:
     *   - pnov: how novel this content is (0.0–1.0), relative to
     *           recently seen content in this agent's context window.
     *   - pnw:  how likely this content is to drive engagement (0.0–1.0).
     *   - state_suggestion: "infected" | "vaccinated" | "neutral" —
     *           the agent's likely stance after reading this content,
     *           used by the ASL transition guards (Algorithms 3/4).
     *   - credibility: high | medium | low
     *   - misinformation_risk: high | medium | low
     *
     * The ASL uses pnov and pnw directly inside the probabilistic guards
     * of the CoNVaI transition function.
     */
    @Override
    public Map<String, Object> interpretContent(Term content) {
        String agentName  = getAgName();
        String contentStr = JasonToJavaTranslator.translateString(content);

        Deque<String> recentContent = recentContentByAgent
            .computeIfAbsent(agentName, k -> new ArrayDeque<>());

        String prompt = buildCoNVaIInterpretPrompt(contentStr, recentContent);
        String raw    = getResponse(prompt);
        Map<String, Object> result = parseInterpretation(raw);

        // Update the sliding window after the call
        synchronized (recentContent) {
            recentContent.addLast(contentStr);
            if (recentContent.size() > CONTEXT_WINDOW_SIZE) {
                recentContent.removeFirst();
            }
        }

        return result;
    }

    private String buildCoNVaIInterpretPrompt(String content, Deque<String> recentContent) {
        String contextBlock = recentContent.isEmpty()
            ? "(none)"
            : String.join("\n- ", recentContent);

        return String.format(
            "You are evaluating a social media post for an information diffusion simulation. " +
            "Recently seen posts by this agent:\n- %s\n\n" +
            "New post to evaluate: \"%s\"\n\n" +
            "Respond ONLY with a JSON object (no markdown, no explanation) with these keys:\n" +
            "  \"pnov\": float 0.0-1.0 — how novel is this post compared to the recent ones " +
                        "(1.0 = completely new topic, 0.0 = already seen).\n" +
            "  \"pnw\": float 0.0-1.0 — how likely is this post to drive engagement/sharing.\n" +
            "  \"state_suggestion\": \"infected\" | \"vaccinated\" | \"neutral\" — " +
                        "would a typical user believe (infected), debunk (vaccinated), " +
                        "or ignore (neutral) this post?\n" +
            "  \"credibility\": \"high\" | \"medium\" | \"low\".\n" +
            "  \"misinformation_risk\": \"high\" | \"medium\" | \"low\".",
            contextBlock,
            content
        );
    }

    // ----------------------------------------------------------------
    // createContent — text generation after the ASL decides to spread
    // ----------------------------------------------------------------

    /**
     * Generates tweet text for an agent that has already decided
     * (via the CoNVaI f() function in ASL) to spread or debunk.
     * The variables map is expected to include a "state" key
     * ("infected" or "vaccinated") so the prompt can frame the
     * content accordingly.
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

        return getResponse(prompt);
    }
}
