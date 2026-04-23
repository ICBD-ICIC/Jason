package arch;

import jason.architecture.AgArch;
import jason.asSyntax.Term;
import lib.JasonToJavaTranslator;

import java.util.*;

/**
 * Gemini-backed architecture for the Kialo debate moderator agent.
 *
 * Generates pro/con/neutral arguments for a target claim,
 * taking into account the parent claim and sibling arguments
 * already in the branch to avoid repetition.
 */
public class KialoGeminiAgArch extends AgArch implements SocialAgArch {

    private final GeminiClient gemini = new GeminiClient();

    // ----------------------------------------------------------------
    // SocialAgArch — createContent
    // ----------------------------------------------------------------

    /**
     * For the Kialo agent, topics is an empty list and variables contains:
     *   stance, targetLeaf, parentClaim, siblings
     */
    @Override
    public String createContent(Term topics, Term variables) {
        Map<String, Object> varMap = JasonToJavaTranslator.translateVariables(variables);

        String stance     = relationToStance(varMap.get("stance"));
        String targetLeaf = stringify(varMap.get("targetLeaf"));
        String parent     = stringify(varMap.getOrDefault("parentClaim", ""));
        Object siblingsRaw = varMap.getOrDefault("siblings", List.of());

        String siblings;
        if (siblingsRaw instanceof List<?> list) {
            siblings = list.isEmpty()
                ? "(no other arguments in this branch)"
                : list.stream()
                      .map(KialoGeminiAgArch::stringify)
                      .collect(java.util.stream.Collectors.joining("\n"));
        } else {
            siblings = stringify(siblingsRaw);
        }

        String prompt = String.format(
            "You are a neutral moderator participating in an online debate to reduce polarization.\n\n" +
            "Target claim (the message you are directly replying to):\n\"%s\"\n\n" +
            "Parent claim (the message the target claim responds to):\n\"%s\"\n\n" +
            "Other arguments already in this branch:\n%s\n\n" +
            "Your task:\n" +
            "- Write a %s argument responding to the target claim\n" +
            "- Be persuasive and concise (2-4 sentences)\n" +
            "- Do NOT repeat existing arguments\n" +
            "- Add new reasoning or evidence\n" +
            "- Your goal is to rebalance the conversation, not to inflame it\n",
            targetLeaf, parent, siblings, stance
        );

        return gemini.getResponse(prompt);
    }

    // ----------------------------------------------------------------
    // SocialAgArch — interpretContent
    // ----------------------------------------------------------------

    @Override
    public Map<String, Object> interpretContent(Term content) {
        throw new UnsupportedOperationException("interpretContent is not implemented for KialoGeminiAgArch.");
    }

    // ----------------------------------------------------------------
    // Helpers
    // ----------------------------------------------------------------

    private static String relationToStance(Object value) {
        if (value == null) return "neutral";
        double rel;
        try {
            rel = Double.parseDouble(value.toString());
        } catch (NumberFormatException e) {
            return value.toString();
        }
        if (rel > 0) return "pro";
        if (rel < 0) return "con";
        return "neutral";
    }

    private static String stringify(Object o) {
        return o == null ? "" : o.toString();
    }
}
