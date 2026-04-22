package arch;

import jason.asSyntax.Term;
import lib.JasonToJavaTranslator;

import java.util.*;

/**
 * Condition 1: Full LLM agent architecture.
 *
 * Unlike ConVaIAgArch, this arch replaces the f() decision function
 * entirely. interpretContent() does not just return probabilities —
 * it asks Gemini to make the spreading decision outright, given the
 * agent's current belief state injected as context.
 *
 * The ASL for this condition is a thin wrapper: it calls
 * ia.interpretContent, reads the "action" key from the result,
 * and executes the corresponding environment action. No BDI
 * transition logic lives in the ASL itself.
 *
 * Agent persona and belief state are maintained here across calls
 * so that Gemini has consistent context for each decision.
 */
public class LLMSocialAgArch extends GeminiAgArch {

    // Per-agent belief state passed as context to Gemini on each call.
    // Keys: "persona", "current_state", "conversation_history"
    private static final Map<String, Map<String, Object>> agentContexts =
        Collections.synchronizedMap(new HashMap<>());

    // ----------------------------------------------------------------
    // interpretContent — Gemini makes the full spreading decision
    // ----------------------------------------------------------------

    /**
     * Asks Gemini to decide what action the agent should take after
     * reading this content. Returns a map with:
     *
     *   "action":    "spread" | "debunk" | "ignore" | "react" | "comment"
     *   "state":     "infected" | "vaccinated" | "neutral"
     *   "reaction":  e.g. "like", "love", "angry" (used if action = react)
     *   "reasoning": short explanation (for qualitative analysis logs)
     *   "credibility":        high | medium | low
     *   "misinformation_risk": high | medium | low
     *
     * The ASL reads "action" and "state" to decide which environment
     * actions to execute (createPost, repost, react, etc.).
     */
    @Override
    public Map<String, Object> interpretContent(Term content) {
        String agentName  = getAgName();
        String contentStr = JasonToJavaTranslator.translateString(content);

        Map<String, Object> ctx = agentContexts.computeIfAbsent(
            agentName, k -> initContext(k)
        );

        String prompt = buildDecisionPrompt(contentStr, ctx);
        String raw    = getResponse(prompt);
        Map<String, Object> result = parseInterpretation(raw);

        // Update belief state so future calls have consistent context
        updateContext(ctx, contentStr, result);

        return result;
    }

    // ----------------------------------------------------------------
    // createContent — full LLM generation with persona context
    // ----------------------------------------------------------------

    /**
     * Generates tweet text using the agent's persona and current
     * belief state as context, so content reflects a consistent
     * agent identity across the simulation.
     */
    @Override
    public String createContent(Term topics, Term variables) {
        String agentName = getAgName();
        List<String> topicList = JasonToJavaTranslator.translateTopics(topics);
        Map<String, Object> varMap = JasonToJavaTranslator.translateVariables(variables);

        Map<String, Object> ctx = agentContexts.computeIfAbsent(
            agentName, k -> initContext(k)
        );

        String prompt = String.format(
            "You are a social media user with this persona: %s. " +
            "Your current stance on the topic is: %s. " +
            "Write a single tweet (max 280 characters) about: %s. " +
            "Reflect these characteristics: %s. " +
            "Reply with only the tweet text, no commentary.",
            ctx.get("persona"),
            ctx.get("current_state"),
            topicList,
            varMap
        );

        return getResponse(prompt);
    }

    // ----------------------------------------------------------------
    // Context management
    // ----------------------------------------------------------------

    private Map<String, Object> initContext(String agentName) {
        Map<String, Object> ctx = new LinkedHashMap<>();
        ctx.put("persona", generatePersona(agentName));
        ctx.put("current_state", "neutral");
        ctx.put("conversation_history", new ArrayList<String>());
        return ctx;
    }

    /**
     * Derives a short persona description from the agent name.
     * In a fuller implementation this would be loaded from
     * public_profiles, but agent names alone give a stable seed.
     */
    private String generatePersona(String agentName) {
        return String.format(
            "A social media user identified as '%s'. " +
            "They engage with news and current events and form opinions based on what they read.",
            agentName
        );
    }

    @SuppressWarnings("unchecked")
    private void updateContext(Map<String, Object> ctx,
                               String contentSeen,
                               Map<String, Object> decision) {
        // Update stance
        Object state = decision.get("state");
        if (state != null) {
            ctx.put("current_state", state.toString());
        }

        // Append to conversation history (capped at last 5 entries)
        List<String> history = (List<String>) ctx.get("conversation_history");
        history.add(contentSeen);
        if (history.size() > 5) {
            history.remove(0);
        }
    }

    private String buildDecisionPrompt(String content, Map<String, Object> ctx) {
        @SuppressWarnings("unchecked")
        List<String> history = (List<String>) ctx.get("conversation_history");
        String historyBlock = history.isEmpty()
            ? "(none)"
            : String.join("\n- ", history);

        return String.format(
            "You are simulating a social media user with this persona: %s\n" +
            "Your current stance: %s\n" +
            "Recent posts you have seen:\n- %s\n\n" +
            "You just read this new post: \"%s\"\n\n" +
            "Decide what to do. Respond ONLY with a JSON object (no markdown, no explanation) with:\n" +
            "  \"action\": \"spread\" | \"debunk\" | \"ignore\" | \"react\" | \"comment\"\n" +
            "  \"state\": \"infected\" | \"vaccinated\" | \"neutral\"\n" +
            "  \"reaction\": one of \"like\", \"love\", \"angry\", \"sad\", \"wow\" " +
                           "(only relevant if action is react, otherwise null)\n" +
            "  \"reasoning\": one sentence explaining your decision (for analysis)\n" +
            "  \"credibility\": \"high\" | \"medium\" | \"low\"\n" +
            "  \"misinformation_risk\": \"high\" | \"medium\" | \"low\"",
            ctx.get("persona"),
            ctx.get("current_state"),
            historyBlock,
            content
        );
    }
}
