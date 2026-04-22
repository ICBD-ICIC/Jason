/* ==========================================================
   CoNVaI Agent

   The BDI cycle implements the CoNVaI f() and g() decision
   functions (Algorithms 2-4 from the paper). The arch computes
   Pnov and Pnw via Gemini; all transition logic lives here.

   Conversation tracking
   ---------------------
   Each agent generates its own conversation ids: agentName_N.
   When starting a new conversation, the agent increments its
   counter and stores in_conversation(CId) before posting, so
   it can recognise the thread in future feed updates.
   When replying, the agent reads conversation_id from the
   parent's message_var percept and stores that instead.

   Agent states: neutral | infected | vaccinated
   ========================================================== */

// --- Initial beliefs ---
state(neutral).
conversation_counter(0).

// --- Startup ---
+!start: true <-
    updateFeed(true).

// Triggered automatically each time updateFeed produces a new feed_order percept.
+feed_order(Ids): true <-
    !process_messages(Ids).

+!process_messages([]): true <- true.

+!process_messages([Id|Rest]): true <-
    !process_single_message(Id);
    !process_messages(Rest).

// --- Single message processing: Algorithm 2 entry point ---
+!process_single_message(Id): true <-
    .wait(message(Id, Author, Content, Original, Timestamp));
    .wait(message_var(Id, "conversation_id", CId));
    ia.interpretContent(Content, Interpretation);
    if (in_conversation(CId)) {
        !apply_read_ms(Id, Author, Content, CId, Interpretation);
        !log_state(Id, "known_conversation")
    } else {
        !apply_read_sc(Id, Author, Content, CId, Interpretation);
        !log_state(Id, "unknown_conversation")
    }.

// --- Algorithm 3: ReadSc (unknown conversation) ---
// ia suggests infected and agent is neutral -> may spread
+!apply_read_sc(Id, Author, Content, CId, Interpretation):
    state(neutral) &
    .member(state_suggestion(infected), Interpretation) &
    .member(pnov(Pnov), Interpretation) &
    .random(R) & R < Pnov <-
    .random(R2);
    if (R2 < 0.1) {         // PINF
        -+state(infected);
        +in_conversation(CId);
        !spread_content(Id, Content, CId, infected)
    } else {
        .random(R3);
        if (R3 < 0.05) {    // PMD
            -+state(vaccinated);
            +in_conversation(CId);
            !spread_content(Id, Content, CId, vaccinated)
        }
    }.

// Gemini suggests vaccinated and agent is neutral -> may debunk
+!apply_read_sc(Id, Author, Content, CId, Interpretation):
    state(neutral) &
    .member(state_suggestion(vaccinated), Interpretation) &
    .member(pnov(Pnov), Interpretation) &
    .random(R) & R < Pnov <-
    -+state(vaccinated);
    +in_conversation(CId);
    !spread_content(Id, Content, CId, vaccinated).

// Default: do nothing
+!apply_read_sc(Id, Author, Content, CId, Interpretation): true <- true.

// --- Algorithm 4: ReadMs (known conversation) ---
// Same state as message -> opinion reinforcement (confirmation bias)
+!apply_read_ms(Id, Author, Content, CId, Interpretation):
    state(S) &
    .member(state_suggestion(S), Interpretation) &
    .member(pnov(Pnov), Interpretation) &
    .random(R) & R < Pnov <-
    .random(R2);
    if (R2 < 0.15) {        // POPI
        !spread_content(Id, Content, CId, S)
    }.

// Differing state -> may change mind (PAD) or backfire (POPI)
+!apply_read_ms(Id, Author, Content, CId, Interpretation):
    state(S) &
    .member(state_suggestion(OtherS), Interpretation) &
    S \== OtherS &
    .member(pnov(Pnov), Interpretation) &
    .random(R) & R < Pnov <-
    .random(R2);
    if (R2 < 0.1) {         // PAD — change mind
        -+state(OtherS);
        !spread_content(Id, Content, CId, OtherS)
    } else {
        .random(R3);
        if (R3 < 0.15) {    // POPI — backfire, reinforce own view
            !spread_content(Id, Content, CId, S)
        }
    }.

// Default: do nothing
+!apply_read_ms(Id, Author, Content, CId, Interpretation): true <- true.

// --- Spreading: new conversation ---
// Agent generates its own CId, stores it before posting.
+!spread_content(Id, Content, _ParentCId, infected):
    state(infected) &
    .my_name(Me) &
    conversation_counter(N) <-
    N1 = N + 1;
    -+conversation_counter(N1);
    .concat(Me, "_", N1, NewCId);
    +in_conversation(NewCId);
    Topics    = ["misinformation", "spread"];
    Variables = [state(infected), source_id(Id),
                 public(conversation_id(NewCId))];
    ia.createContent(Topics, Variables, NewContent);
    createPost(Topics, Variables, NewContent);
    !reply_to(Id, Content, NewCId, infected);
    !maybe_react(Id);
    ia.save_logs([event("spread"), message_id(Id), agent_state(infected),
                  conversation_id(NewCId), content(NewContent)]).

+!spread_content(Id, Content, _ParentCId, vaccinated):
    state(vaccinated) &
    .my_name(Me) &
    conversation_counter(N) <-
    N1 = N + 1;
    -+conversation_counter(N1);
    .concat(Me, "_", N1, NewCId);
    +in_conversation(NewCId);
    Topics    = ["misinformation", "debunk"];
    Variables = [state(vaccinated), source_id(Id),
                 public(conversation_id(NewCId))];
    ia.createContent(Topics, Variables, NewContent);
    createPost(Topics, Variables, NewContent);
    !reply_to(Id, Content, NewCId, vaccinated);
    !maybe_react(Id);
    ia.save_logs([event("debunk"), message_id(Id), agent_state(vaccinated),
                  conversation_id(NewCId), content(NewContent)]).

+!spread_content(Id, Content, CId, neutral): true <- true.

// --- Reply: inherits parent's conversation_id ---
+!reply_to(Id, Content, CId, infected): true <-
    Topics    = ["misinformation", "spread"];
    Variables = [state(infected), public(conversation_id(CId))];
    ia.createContent(Topics, Variables, ReplyContent);
    comment(Id, Topics, Variables, ReplyContent).

+!reply_to(Id, Content, CId, vaccinated): true <-
    Topics    = ["misinformation", "debunk"];
    Variables = [state(vaccinated), public(conversation_id(CId))];
    ia.createContent(Topics, Variables, ReplyContent);
    comment(Id, Topics, Variables, ReplyContent).

// --- Optional reaction ---
+!maybe_react(Id): .random(R) & R < 0.4 <-
    react(Id, like).
+!maybe_react(Id): true <- true.

// --- Feed refresh after joining a conversation ---
+in_conversation(CId): true <-
    updateFeed(true).

// --- Logging helper ---
+!log_state(Id, ConversationType): state(S) <-
    ia.save_logs([event("state_check"), message_id(Id),
                  agent_state(S), conversation_type(ConversationType)]).
