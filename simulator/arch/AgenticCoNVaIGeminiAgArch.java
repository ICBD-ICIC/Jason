package arch;

import jason.architecture.AgArch;
import jason.asSyntax.*;
import lib.JasonToJavaTranslator;

import java.util.*;
import java.util.logging.Logger;

/**
 * Architecture for the LLM-driven CoNVaI agent.
 *
 * Replaces the probabilistic transition function g (Algorithms 2-4)
 * with a single unified LLM call per message.  The LLM receives:
 *
 *   - The agent's personality description (second-person prompt directive)
 *   - The MESSAGE AUTHOR's social profile (followers, friends, listed, verified),
 *     used to reason about the author's credibility - NOT the agent's own profile
 *   - The agent's current belief state and full conversation history
 *
 * And returns in a single JSON response:
 *
 *   new_state      - neutral | infected | vaccinated
 *   reply_content  - tweet text to post, or "" to stay silent
 *   topics         - subjects raised in the REPLY (empty array if no reply)
 *
 * All three fields are returned by one unified LLM call, eliminating the
 * need for a separate topics-extraction call.
 *
 * Caching strategy
 * ----------------
 * The per-message LLM call is agent-specific (it depends on personality,
 * current state, and reading history) so it is NEVER cached globally.
 * Topics are reply-specific and agent-specific for the same reason.
 *
 * State transition constraints
 * ----------------------------
 * Belief states are irreversible with respect to neutral: once an agent
 * has formed an opinion (infected or vaccinated) it cannot regress to
 * neutral. It may still switch between infected and vaccinated.
 */
public class AgenticCoNVaIGeminiAgArch extends AgArch implements SocialAgArch {

    private static final GeminiClient gemini = new GeminiClient();
    private static final com.fasterxml.jackson.databind.ObjectMapper MAPPER =
        new com.fasterxml.jackson.databind.ObjectMapper();
    private static final Logger logger = Logger.getLogger(AgenticCoNVaIGeminiAgArch.class.getName());
    private static final Set<String> VALID_STATES = Set.of("neutral", "infected", "vaccinated");

    private static final int HISTORY_CAP = 30;

    // -------------------------------------------------------------------------
    // interpretContent  - unified read + react + generate
    // -------------------------------------------------------------------------

    /**
     * @param contentStructure Jason structure:
     *   content(
     *     Text,               // message text (string)
     *     PastMessages,       // list of strings, most-recent first
     *     CurrentState,       // atom: neutral | infected | vaccinated
     *     FollowersCount,     // int  - MESSAGE AUTHOR's followers
     *     FriendsCount,       // int  - MESSAGE AUTHOR's friends
     *     ListedCount,        // int  - MESSAGE AUTHOR's listed count
     *     Verified,           // atom: true | false - MESSAGE AUTHOR's verified status
     *     PersonalityDesc     // string - second-person personality prompt
     *   )
     * @return map with keys:
     *   new_state     (String)       - neutral | infected | vaccinated
     *   reply_content (String)       - tweet text or ""
     *   topics        (List<String>) - subjects raised in the reply (empty list if no reply)
     */
    @Override
    public Map<String, Object> interpretContent(Term contentStructure) {
        String       text;
        List<String> past;
        String       currentState;
        int          followers, friends, listed;
        boolean      verified;
        String       personality;
        try {
            Structure s = (Structure) contentStructure;
            text        = JasonToJavaTranslator.translateString(s.getTerm(0));
            past        = JasonToJavaTranslator.translateTopics(s.getTerm(1));
            currentState =  s.getTerm(2).toString().replace("\"", "").strip().toLowerCase();
            followers   = JasonToJavaTranslator.translateInt(s.getTerm(3));
            friends     = JasonToJavaTranslator.translateInt(s.getTerm(4));
            listed      = JasonToJavaTranslator.translateInt(s.getTerm(5));
            verified    = "true".equals(s.getTerm(6).toString());
            personality = JasonToJavaTranslator.translateString(s.getTerm(7));
        } catch (Exception e) {
            throw new RuntimeException("[CoNVaILLMAgArch] Failed to parse input params: " + e.getMessage());
        }
        try {
            String decisionPrompt = buildDecisionPrompt(
                text, past, currentState,
                followers, friends, listed, verified,
                personality
            );
            String raw = gemini.getResponse(decisionPrompt, GeminiClient.CONFIG_CREATIVE);
            return parseDecision(raw, currentState);

        } catch (Exception e) {
            logger.severe("[CoNVaILLMAgArch] LLM call or parsing failed, returning safe defaults: "
                + e.getMessage());
            return safeFallback(currentState);
        }
    }

    // -------------------------------------------------------------------------
    // createContent - not used; reply text is produced inside interpretContent
    // -------------------------------------------------------------------------

    /**
     * Not called by convai_llm_agent.asl.
     * Kept to satisfy the {@link SocialAgArch} interface contract.
     */
    @Override
    public String createContent(Term topics, Term variables) {
        logger.warning("[CoNVaILLMAgArch] createContent called but is not used by this agent.");
        return "";
    }

    // -------------------------------------------------------------------------
    // Prompts
    // -------------------------------------------------------------------------

    /**
     * Unified decision prompt - agent-specific, never cached.
     *
     * The LLM plays the role of the agent described by {@code personality}.
     * The social profile attributes belong to the MESSAGE AUTHOR.
     * They are surfaced so the agent can reason about the author's credibility
     * (mirroring the role Pusr played in the original arch).
     */
    private String buildDecisionPrompt(
            String text,
            List<String> history,
            String currentState,
            int authorFollowers, int authorFriends, int authorListed, boolean authorVerified,
            String personality) {

        List<String> window = history.size() > HISTORY_CAP ? history.subList(0, HISTORY_CAP) : history;
        String historyBlock = history.isEmpty()
            ? "(none - this is the first message you have read)"
            : (history.size() > HISTORY_CAP
                ? "(showing most recent " + HISTORY_CAP + " of " + history.size() + " total)\n- "
                : "- ")
              + String.join("\n- ", window);

        String verifiedLabel = authorVerified ? "yes (verified account)" : "no";

        String rule1 = "neutral".equals(currentState)
            ? "You are currently neutral. You may stay neutral, become \"infected\", or become \"vaccinated\"."
            : "You are currently \"" + currentState + "\". You may stay or switch to the other opinion state, "
                + "but you MUST NOT revert to \"neutral\". That door is permanently closed.";
        
        
        return String.format("""
            %s

            You are taking part in a social media simulation about misinformation diffusion.
            You have just read the following message and must decide how it affects you.

            === MESSAGE AUTHOR'S SOCIAL PROFILE ===
            Followers        : %d
            Following        : %d
            Times listed     : %d
            Verified account : %s

            Use this profile to judge the author's credibility and reach.
            A high follower count or verified status may increase the message's influence on you.

            === BELIEF STATES ===
            neutral    - you have not yet formed an opinion
            infected   - you believe the misinformation and are inclined to spread it
            vaccinated - you disbelieve the misinformation and are inclined to debunk it

            === YOUR CURRENT BELIEF STATE: %s ===

            === ALL MESSAGES YOU HAVE READ SO FAR (most recent first) ===
            %s

            === NEW MESSAGE ===
            "%s"

            === YOUR TASK ===
            Decide, in character, how this message affects you and whether you reply.

            === HARD RULES — violating any of these is an error ===
            RULE 1 — State irreversibility  : %s
            RULE 2 — Replying requires commitment: if reply_content is non-empty,
                    new_state MUST be "infected" or "vaccinated", never "neutral".
                    A reply means you have formed an opinion; fence-sitters do not post.
            RULE 3 — Silence is always allowed: you may change state WITHOUT replying,
                    and you may stay silent WITHOUT changing state.
            RULE 4 — No reply while neutral: if new_state is "neutral",
                    reply_content MUST be "" and topics MUST be [].

            Return ONLY a JSON object with exactly these keys:

            "new_state": string - one of "neutral", "infected", "vaccinated".

            "reply_content": string - your reply tweet (max 280 characters) if you
            choose to engage, or "" to stay silent.
            Write in first person, as a real social media user would.
            Do NOT explain your reasoning — just write the tweet or leave it empty.

            "topics": array of 1-5 strings — specific subjects raised IN YOUR REPLY.
            1-3 words each, lowercase. E.g. ["police cover-up", "eyewitness accounts"].
            If reply_content is "", this MUST be an empty array [].

            No markdown. No explanation. Raw JSON only.
            
            EXAMPLE of the exact output format required:
            {"new_state":"infected","reply_content":"Can't believe they're hiding this. There were definitely more incidents.","topics":["cover-up","incident count"]}

            Your response:""",
            personality,
            authorFollowers, authorFriends, authorListed, verifiedLabel,
            currentState,      
            historyBlock,
            text,
            rule1);
    }           
    
    // -------------------------------------------------------------------------
    // Parsing helpers
    // -------------------------------------------------------------------------

    private Map<String, Object> parseDecision(String raw, String fallbackState) {
        String normalizedFallback = fallbackState.replace("\"", "").strip().toLowerCase();

        Map<String, Object> result = new LinkedHashMap<>();
        result.put("new_state",     normalizedFallback);
        result.put("reply_content", "");
        result.put("topics",        new ArrayList<String>());

        if (raw == null || raw.isBlank()) {
            logger.warning("[CoNVaILLMAgArch] Empty decision response from LLM.");
            return result;
        }

        try {
            String json = extractJsonObject(raw);
            if (json == null) {
                logger.warning("[CoNVaILLMAgArch] No JSON object found in response. raw=" + raw);
                return result;
            }

            @SuppressWarnings("unchecked")
            Map<String, Object> parsed = MAPPER.readValue(json, Map.class);

            if (parsed.containsKey("new_state")) {
                String s = String.valueOf(parsed.get("new_state")).toLowerCase().strip();
                String resolved = VALID_STATES.contains(s) ? s : normalizedFallback;
                // Enforce irreversibility: infected/vaccinated agents cannot regress to neutral.
                if ("neutral".equals(resolved) && !("neutral".equals(normalizedFallback))) {
                    logger.warning("[CoNVaILLMAgArch] LLM attempted illegal regression to neutral "
                        + "from " + normalizedFallback + "; keeping current state.");
                    resolved = normalizedFallback;
                }
                result.put("new_state", resolved);
            }

            String newState = (String) result.get("new_state");

            if (parsed.containsKey("reply_content")) {
                String reply = String.valueOf(parsed.get("reply_content")).strip();
                // Enforce: neutral agents must not post
                if ("neutral".equals(newState)) {
                    result.put("reply_content", "");
                } else {
                    // Truncate to Twitter's character limit
                    result.put("reply_content", reply.length() > 280
                        ? reply.substring(0, 280) : reply);
                }
            }

            // Topics belong to the reply; clear them if the agent ended up silent
            String finalReply = (String) result.get("reply_content");
            if (!finalReply.isBlank() && parsed.containsKey("topics")
                    && parsed.get("topics") instanceof List<?> list) {
                List<String> topics = list.stream()
                    .filter(Objects::nonNull)
                    .map(Object::toString)
                    .toList();
                result.put("topics", topics);
            }

        } catch (Exception e) {
            logger.warning("[CoNVaILLMAgArch] Failed to parse decision JSON: "
                + e.getMessage() + " | raw=" + raw);
        }

        return result;
    }

    /**
     * Extracts the first top-level JSON object {...} from a string that may
     * contain prose before or after it (e.g. Gemini chain-of-thought preambles).
     * Returns null if no balanced object is found.
     */
    private static String extractJsonObject(String text) {
        if (text == null) return null;
            text = text.replace('\u2018', '\'').replace('\u2019', '\'')  // curly single quotes
                       .replace('\u201C', '"').replace('\u201D', '"');   // curly double quotes
        int start = text.indexOf('{');
        if (start == -1) return null;

        int depth = 0;
        boolean inString = false;
        boolean escape = false;

        for (int i = start; i < text.length(); i++) {
            char c = text.charAt(i);

            if (escape) { escape = false; continue; }
            if (c == '\\' && inString) { escape = true; continue; }
            if (c == '"') { inString = !inString; continue; }
            if (inString) continue;

            if (c == '{') depth++;
            else if (c == '}') {
                depth--;
                if (depth == 0) return text.substring(start, i + 1);
            }
        }
        return null; // unbalanced
    }

    private Map<String, Object> safeFallback(String currentState) {
        Map<String, Object> result = new LinkedHashMap<>();
        result.put("new_state",     currentState);
        result.put("reply_content", "");
        result.put("topics",        new ArrayList<String>());
        return result;
    }

}