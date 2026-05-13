package arch;

import jason.architecture.AgArch;
import jason.asSyntax.*;
import lib.JasonToJavaTranslator;

import java.util.*;
import java.util.logging.Logger;

import arch.schema.GeminiSchemas;

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
            logger.info("[CoNVaILLMAgArch] Prompt built successfully, calling LLM...");
            String raw = gemini.getResponse(
                            decisionPrompt, 
                            GeminiClient.jsonConfigCreative(
                                GeminiSchemas.DECISION_SCHEMA
                            )
                        );
            logger.info("[CoNVaILLMAgArch] Decision prompt sent to LLM: " + decisionPrompt);
            logger.info("[CoNVaILLMAgArch] Raw LLM response: " + raw);
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
        
            text        = text.replace("%", "%%");
            personality = personality.replace("%", "%%");
            historyBlock = historyBlock.replace("%", "%%");
        return String.format("""
            %s

            You are an agent in a social media misinformation simulation.
            You have just received a new message. Decide how it affects your belief and whether you respond.

            === YOUR BELIEF STATE ===
            Your state can be one of three values:
            neutral    - no opinion formed; you do not post
            infected   - you believe the claim and are inclined to spread it
            vaccinated - you disbelieve the claim and are inclined to debunk it

            Your current state: %s

            === MESSAGE AUTHOR'S SOCIAL PROFILE ===
            Followers: %d  |  Following: %d  |  Listed: %d  |  Verified: %s

            A high follower count or verified status increases the author's influence.
            Factor this into how seriously you take the message.

            === YOUR READING HISTORY (most recent first) ===
            %s

            === NEW MESSAGE ===
            "%s"

            === TRANSITION RULES (follow exactly) ===

            If you are NEUTRAL:
            - You may transition to infected or vaccinated based on message content and author influence.
            - You may stay neutral if the message is weak or unconvincing.
            - While neutral: reply_content MUST be "" and topics MUST be [].

            If you are INFECTED or VACCINATED:
            - If the message AGREES with your state you may reinforce your opinion (stay in same state).
                Lean toward replying to express agreement or amplify the claim.
            - If the message DISAGREES with your state you may be persuaded and switch states,
                OR resist and stay in your current state.
                Lean toward replying to push back or correct.
            - In either case you may stay silent (no reply, no state change).

            %s

            === REPEATED EXPOSURE ===
            Check your reading history. If this same message (or claim) has appeared before:
            - 1st exposure: normal evaluation.
            - 2nd exposure: treat as mild additional pressure.
            - 3rd exposure: you should be forming or reinforcing an opinion.
            - 4th+ exposure: staying neutral requires explicit justification by your personality.
                Your personality determines the direction: impressionable: infected, skeptical: vaccinated.

            Note: Repeated identical messages may indicate a stale feed (no new replies), not viral spread.
            Weight later repetitions less than the first exposure - familiarity reduces novelty and impact.

            === POSTING BEHAVIOR ===
            Base your likelihood of replying on your situation:
            - Neutral and staying neutral: do NOT reply (silent by rule)
            - Neutral transitioning to a new state: reply ~80%% of the time
            - Already opinionated, message agrees : reply ~60%% of the time
            - Already opinionated, message disagrees: reply ~70%% of the time
            - Very high author influence: increase reply likelihood

            Replies must feel authentic. Match your emotional register to your state:
            infected: alarmed, convinced, urgent, curious, outraged
            vaccinated: skeptical, corrective, sarcastic, dismissive, calm

            Write like a real social media user. Short, direct, personal. No formal language.

            === OUTPUT FORMAT ===
            Return ONLY a raw JSON object - no markdown, no explanation, no extra keys.

            {
            "new_state":     "<neutral | infected | vaccinated>",
            "reply_content": "<your tweet, max 280 characters, or empty string>",
            "topics":        ["<1-3 word topic>", ...]
            }

            Hard constraints:
            - If new_state is "neutral": reply_content MUST be ""  and topics MUST be []
            - If reply_content is non-empty: new_state MUST be "infected" or "vaccinated"
            - topics reflects only what you say in reply_content; if no reply, topics is []
            - %s

            Your response:""",
            personality,
            currentState,
            authorFollowers, authorFriends, authorListed, verifiedLabel,
            historyBlock,
            text,
            rule1,
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
            String json = raw.trim();
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
            if (finalReply.isBlank()) {
                result.put("topics", new ArrayList<String>());
            }

        } catch (Exception e) {
            logger.warning("[CoNVaILLMAgArch] Failed to parse decision JSON: "
                + e.getMessage() + " | raw=" + raw);
        }

        return result;
    }

    private Map<String, Object> safeFallback(String currentState) {
        Map<String, Object> result = new LinkedHashMap<>();
        result.put("new_state",     currentState);
        result.put("reply_content", "");
        result.put("topics",        new ArrayList<String>());
        return result;
    }

}