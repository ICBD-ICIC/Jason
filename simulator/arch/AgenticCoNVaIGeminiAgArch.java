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

    private static final int HISTORY_CAP = 10;

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
            String raw = gemini.getResponse(
                            decisionPrompt, 
                            GeminiClient.jsonConfigCreative(
                                GeminiSchemas.DECISION_SCHEMA
                            )
                        );
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

        String historySize = "You have read " + history.size() + " message/s so far from the conversation.";
        
        text        = text.replace("%", "%%");
        personality = personality.replace("%", "%%");
        historyBlock = historyBlock.replace("%", "%%");
        
        return String.format("""
            %s

            You are an agent in a social media information diffusion simulation.
            You have just received a message. Follow the steps below exactly to decide
            your new state and whether you reply.

            === YOUR BELIEF STATE ===
            neutral    - you have not yet formed an opinion about the claim
            infected   - you believe the claim is true and are inclined to share it
            vaccinated - you believe the claim is false and are inclined to debunk it

            Your current state: %s

            === MESSAGE AUTHOR'S SOCIAL PROFILE ===
            Followers: %d  |  Following: %d  |  Listed: %d  |  Verified: %s

            === YOUR READING HISTORY (last 10 messages, most recent first) ===
            %s

            === NEW MESSAGE ===
            "%s"

            === DECISION PROCESS (follow each step in order) ===

            STEP 1 - NOVELTY: Is this message familiar?
            Compare the new message against your reading history.
            If you have seen this exact message before, treat it as a repeat.
            If your history is empty or the message is new to you, treat it as novel.
            Note: seeing a message for the first time is always novel, regardless of topic.

            STEP 2 - ENGAGEMENT: Do you bother reading this carefully?
            Active readers engage with most messages they encounter.
            Only skip if: the message is an exact repeat AND you have already formed an opinion about it.
            If you are still neutral, always engage - you have not yet decided what to believe.

            STEP 3 - AUTHOR INFLUENCE: How much weight does this author carry?
            A high follower count, high listed count, or verified status increases influence.
            A low-profile author carries less weight.
            Factor this into Steps 4 and 5.

            STEP 4 - STATE TRANSITION:
            If your current state is NEUTRAL:
            - You are reading this message for the first time. Form an opinion.
            - Ask yourself: does this claim seem believable or not?
            - Factor in the author's influence (Step 3). A verified or high-follower
                author makes the claim harder to ignore in either direction.
            - Your personality determines the threshold:
                * Highly susceptible: believe the claim unless it is obviously false.
                * Moderately susceptible: believe it if the author is credible or the claim is compelling.
                * Resistant: default to disbelief unless the evidence is strong.
                * Quick to scepticism: lean vaccinated when in doubt.
            - Staying neutral is only appropriate if the message is completely incoherent,
                the author has zero credibility, AND your personality makes you hard to move.
                In all other cases, form an opinion - infected or vaccinated.

            If your current state is INFECTED or VACCINATED:
            - Does the message AGREE with your current state?
                Based on your opinion-reinforcement tendency: stay in your state.
                Lean toward replying to express agreement or amplify.
            - Does the message DISAGREE with your current state?
                Based on your willingness to flip (from your personality):
                consider switching to the opposing state.
                If you resist: based on your reinforcement tendency, hold your ground.
                Lean toward replying to push back or correct.

            STEP 5 - REPLY DECISION:
            Only reply if you are infected or vaccinated after Step 4.
            Your reply likelihood decreases as your reading history grows (fatigue),
            meaning you change/keep your current state, but you do not reply.
            %s
            A highly influential author or a provocative message can override fatigue.
            Never reply if neutral.

            Replies must feel authentic. Match your emotional register:
            infected:   alarmed, convinced, urgent, curious, outraged
            vaccinated: skeptical, corrective, sarcastic, dismissive, calm
            Write like a real social media user. Short, direct, personal. No formal language.

            === HARD RULES ===
            - Once infected or vaccinated you can never return to neutral.
            - If new_state is neutral: reply_content MUST be "" and topics MUST be [].
            - If reply_content is non-empty: new_state MUST be infected or vaccinated.
            - topics reflects only what you say in reply_content; if no reply, topics is [].

            === OUTPUT FORMAT ===
            Return ONLY a raw JSON object - no markdown, no explanation, no extra keys.

            {
            "new_state":     "<neutral | infected | vaccinated>",
            "reply_content": "<your tweet, max 280 characters, or empty string>",
            "topics":        ["<1-3 word topic>", ...]
            }

            Your response:
            """,
            personality,
            currentState,
            authorFollowers, authorFriends, authorListed, verifiedLabel,
            historyBlock,
            text,
            historySize);
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