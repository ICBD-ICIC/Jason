/* ==========================================================
   CoNVaI Agent (Jason BDI)

   The BDI cycle implements the CoNVaI f() and g() decision
   functions (Algorithms 2-4 from the paper). The arch computes
   Pnov, Prpl and Pnw via LLM. Pusr is computed here using
   ia.computeSc and agent profile beliefs.

   Probability parameters (configurable)
   --------------------------------------
   finfl(0.1)          — weight of user influence
   alpha_ratio(0.01)   — alpha for sc(followers/followees)
   alpha_posts(0.001)  — alpha for sc(posts)
   pinf(0.1)           — infection rate
   pmd(0.05)           — vaccination rate on new content
   pad(0.1)            — adoption rate (change mind)
   popi(0.15)          — opinion sharing rate

   Agent states: neutral | infected | vaccinated
   ========================================================== */

// --- Profile beliefs ---
verified(true).
number_posts(10).
finfl(0.1).
alpha_ratio(0.01).
alpha_posts(0.001).

// --- Transition parameters ---
pinf(0.1).
pmd(0.05).
pad(0.1).
popi(0.15).
prd(0.3).    // read rate per time unit

// --- Read counter (resets each feed cycle) ---
messages_read(0).

// --- State and conversation tracking ---
state(neutral).
conversation_counter(0).

// --- Startup ---
+!start: true <-
    updateFeed(true).

// Triggered automatically each time updateFeed produces a new feed_order percept.
+feed_order(Ids): true <-
    -+messages_read(0);
    !process_messages(Ids).

+!process_messages([]): true <- true.

+!process_messages([Id|Rest]): true <-
    messages_read(MR);
    MR1 = MR + 1;
    -+messages_read(MR1);
    prd(Prd);
    Pread = Prd / MR1;
    .random(R);
    if (R < Pread) {
        !process_single_message(Id)
    };
    !process_messages(Rest).

// --- Pusr computation (paper Section 4.1) ---
+!compute_pusr(Pusr): true <-
    .count(follows(_), Followees);
    .count(followedBy(_), Followers);
    number_posts(Posts);
    verified(Verified);
    finfl(Finfl);
    alpha_ratio(AlphaRatio);
    alpha_posts(AlphaPosts);
    (Followees > 0 -> Ratio = Followers / Followees ; Ratio = 0);
    ia.computeSc(Ratio, AlphaRatio, ScRatio);
    ia.computeSc(Posts, AlphaPosts, ScPosts);
    (Verified == true -> VerifiedVal = 1.0 ; VerifiedVal = 0.0);
    Infl = 0.4 * ScRatio + 0.4 * ScPosts + 0.2 * VerifiedVal;
    Pusr = Finfl * Infl.

// --- Single message processing: Algorithm 2 entry point ---
+!process_single_message(Id): true <-
    .wait(message(Id, Author, Content, Original, Timestamp));
    .wait(message_var(Id, "conversation_id", CId));
    !compute_pusr(Pusr);
    // Encode pusr into the content string for the arch to extract
    .concat(Content, "|||pusr=", Pusr, ContentWithPusr);
    if (in_conversation(CId)) {
        ia.interpretContent(ContentWithPusr, Interpretation);
        !apply_read_ms(Id, Author, Content, CId, Interpretation);
        !log_state(Id, "known_conversation")
    } else {
        ia.interpretContent(ContentWithPusr, Interpretation);
        !apply_read_sc(Id, Author, Content, CId, Interpretation);
        !log_state(Id, "unknown_conversation")
    }.

// --- Algorithm 3: ReadSc (unknown conversation) ---
// Prpl is the outer gate: is now the right moment to engage?
// Then Pnov * Pusr adjusts the probability bounds.

+!apply_read_sc(Id, Author, Content, CId, Interpretation):
    state(neutral) &
    .member(state_suggestion(infected), Interpretation) &
    .member(prpl(Prpl), Interpretation) &
    .member(pnov(Pnov), Interpretation) &
    .random(R1) & R1 < Prpl <-
    pinf(Pinf);
    pmd(Pmd);
    !compute_pusr(Pusr);
    .random(R2);
    if (R2 < (Pinf / (1 - Pusr - Pnov))) {
        -+state(infected);
        +in_conversation(CId);
        !spread_content(Id, Content, CId, infected)
    } else {
        .random(R3);
        if (R3 < (Pmd / (1 - Pusr - Pnov))) {
            -+state(vaccinated);
            +in_conversation(CId);
            !spread_content(Id, Content, CId, vaccinated)
        }
    }.

+!apply_read_sc(Id, Author, Content, CId, Interpretation):
    state(neutral) &
    .member(state_suggestion(vaccinated), Interpretation) &
    .member(prpl(Prpl), Interpretation) &
    .member(pnov(Pnov), Interpretation) &
    .random(R1) & R1 < Prpl <-
    pmd(Pmd);
    !compute_pusr(Pusr);
    .random(R2);
    if (R2 < (Pmd / (1 - Pusr - Pnov))) {
        -+state(vaccinated);
        +in_conversation(CId);
        !spread_content(Id, Content, CId, vaccinated)
    }.

// Default: do nothing
+!apply_read_sc(Id, Author, Content, CId, Interpretation): true <- true.

// --- Algorithm 4: ReadMs (known conversation) ---

// Same state -> confirmation bias (POPI)
+!apply_read_ms(Id, Author, Content, CId, Interpretation):
    state(S) &
    .member(state_suggestion(S), Interpretation) &
    .member(prpl(Prpl), Interpretation) &
    .member(pnov(Pnov), Interpretation) &
    .random(R1) & R1 < Prpl <-
    popi(Popi);
    !compute_pusr(Pusr);
    .random(R2);
    if (R2 < (Popi / (1 - Pnov - Pusr))) {
        !spread_content(Id, Content, CId, S)
    }.

// Differing state -> change mind (PAD) or backfire (POPI)
+!apply_read_ms(Id, Author, Content, CId, Interpretation):
    state(S) &
    .member(state_suggestion(OtherS), Interpretation) &
    S \== OtherS &
    .member(prpl(Prpl), Interpretation) &
    .member(pnov(Pnov), Interpretation) &
    .random(R1) & R1 < Prpl <-
    pad(Pad);
    popi(Popi);
    !compute_pusr(Pusr);
    .random(R2);
    if (R2 < (Pad / (1 - Pnov - Pusr))) {
        -+state(OtherS);
        !spread_content(Id, Content, CId, OtherS)
    } else {
        .random(R3);
        if (R3 < (Popi / (1 - Pnov - Pusr))) {
            !spread_content(Id, Content, CId, S)
        }
    }.

// Default: do nothing
+!apply_read_ms(Id, Author, Content, CId, Interpretation): true <- true.

// --- Spreading: new standalone post + reply ---
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
    !reply_to(Id, NewCId, infected);
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
    !reply_to(Id, NewCId, vaccinated);
    !maybe_react(Id);
    ia.save_logs([event("debunk"), message_id(Id), agent_state(vaccinated),
                  conversation_id(NewCId), content(NewContent)]).

+!spread_content(Id, Content, CId, neutral): true <- true.

// --- Reply: inherits conversation_id from spread_content ---
+!reply_to(Id, CId, infected): true <-
    Topics    = ["misinformation", "spread"];
    Variables = [state(infected), public(conversation_id(CId))];
    ia.createContent(Topics, Variables, ReplyContent);
    comment(Id, Topics, Variables, ReplyContent).

+!reply_to(Id, CId, vaccinated): true <-
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
