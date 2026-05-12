/* ==========================================================
    CoNVaI Agent (Jason BDI)
    RodrÃ­guez-GarcÃ­a et al. (2025) - "Simulating Misinformation
    Diffusion on Social Media Through CoNVaI"

    Implements Definition 6 (CoNVaI-agent): <S, O, Uin, g, f, per, s0>
    where g and f depend on both epidemiological (PT_R) and
    textual (PT_X) parameter sets, plus user characteristics (Pusr).

    -- Internal States S --------------------------------------
        neutral      (Neu) - unaware of the information
        infected     (Inf) - agrees with / spreads the information
        vaccinated   (Vac) - disagrees with / debunks the information

    -- Epidemiological Parameters PT_R ------------------------
        pinf   (P_INF)  Probability of becoming Infected on first contact
        pmd    (P_MD)   Probability of becoming Vaccinated on first contact
                        when not Infected 
        pad    (P_AD)   Probability of adopting the opposing state when
                        in disagreement with a message 
        popi   (P_OPI)  Probability of reinforcing one's own opinion when
                        in agreement or after resisting adoption
        prd    (P_RD)   Read rate per time unit; gates message processing
                        via Pread(ui, t) = P_RD / mr(ui, t), 
                        where mr(ui, t) is the messages read so far

    -- Textual Parameters PT_X ----------
        pnov   (P_nov)  News novelty to reduce engagement with familiar content
        prpl   (P_rpl)  Engagement over time
        pnw    (P_nw)   News influence, cumulative engagement

    -- User Characteristics (from Public Profiles) ------------
        pusr   (Pusr)   Poster influence probability, derived from
                        follower/followee ratio, listed posts, and
                        verified status 

    -- Actions A -----------------------
        anew        Start a new conversation (not yet implemented;
                    a_new condition is never true with current g)
        areply(c)   Reply to conversation c - requires Replying flag
                    set during g and state â‰  neutral
        askip       Do nothing

    -- Algorithms implemented ----------------------------------
        Algorithm 2  g transition function     -> +feed_order / +!process_*
        Algorithm 3  ReadSc (new conversation) -> +!read_sc
        Algorithm 4  ReadMs (known conv.)      -> +!read_ms
        f (Eq. 3)    Decision / action         -> +!act
   ========================================================== */

read_history([]).

// --- Cycle / idle tracking ---
cycle(0).
max_cycles(1000).
max_cycles_reached(false).

idle_cycles(0).
inactivity_limit(60).
idle_limit_reached(false).

!init.

+!init: susceptible(false) & state(State) <-
    .my_name(Me);
    ia.saveLogs([info("Killing agent."), agent(Me), state(State)]);
    .kill_agent(Me).

+!init: state(State) <-
    ia.saveLogs([state(State)]);
    !start.

+!start: true <-
    updateFeed(true).

-!start: true <-
    +restart.

+feed_order([]): true <-
    ia.saveLogs([info("Feed is empty. Waiting before restart.")]);
    .wait(1000);
    .abolish(feed_order(_));
    !end_cycle(false);
    +restart.

+feed_order(Ids): true <-
    -feed_order(Ids);
    -+messages_read(0);
    ia.saveLogs([info("Started processing messages.")]);
    !process_messages(Ids, 0, ActCount);
    ia.saveLogs([info("Finished processing messages.")]);
    !end_cycle(ActCount > 0);
    +restart.

+!end_cycle(WasActive):
    cycle(C) & idle_cycles(IC) & inactivity_limit(X) & max_cycles(T) &
    idle_limit_reached(IdleLimitReached) & max_cycles_reached(MaxReached)
<-
    C1 = C + 1;
    -+cycle(C1);
    if (WasActive) {
        -+idle_cycles(0);
        if (IdleLimitReached) {
            ia.saveLogs([info("Agent became active again after idle limit."), cycle(C1)]);
            -+idle_limit_reached(false);
            .my_name(Me);
            .send(convai_monitor, untell, idle_limit_reached(Me))
        }
    } else {
        IC1 = IC + 1;
        -+idle_cycles(IC1);
        ia.saveLogs([idle_cycles(IC1), cycle(C1)]);
        if (IC1 > X & IdleLimitReached == false) {
            ia.saveLogs([info("Idle limit reached. Notifying monitor."), cycle(C1)]);
            -+idle_limit_reached(true);
            .my_name(Me);
            .send(convai_monitor, tell, idle_limit_reached(Me))
        }
    };

    if (C1 > T & MaxReached == false) {
        ia.saveLogs([info("Max cycles reached. Notifying monitor."), cycle(C1)]);
        -+max_cycles_reached(true);
        .my_name(Me);
        .send(convai_monitor, tell, max_cycles_reached(Me))
    }.

+!end_cycle(_): true <-
    ia.saveLogs([info("end_cycle skipped.")]).

+restart: true <-
    -restart;
    .abolish(feed_order(_));
    !start.

+!process_messages([], ActCount, ActCount): true <- true.

+!process_messages([Id|Rest], ActSoFar, ActFinal):
    messages_read(MR) & prd(Prd)
<-
    MR1 = MR + 1;
    -+messages_read(MR1);
    Pread = Prd / MR1;
    ia.U(U1);
    if (U1 <= Pread) {
        !process_single_message(Id);
        !act(ActedNow)
    } else {
        ActedNow = false
    };
    if (ActedNow) { ActNext = ActSoFar + 1 } else { ActNext = ActSoFar };
    !process_messages(Rest, ActNext, ActFinal).

-!process_messages(Ids, ActSoFar, ActFinal): true <-
    ActFinal = ActSoFar;
    ia.saveLogs([info("process_messages failed."), remaining_count(Ids)]).

+!process_single_message(Id): 
    read_history(PastMessages) & message(Id, Author, Content, Original, Timestamp) & 
    message_var(Id, "conversation_id", CId) & cycle(C)
<-
    ia.saveLogs([info("Got all information for message. Waiting for interpretation.")]);
    ia.interpretContent(content(Content, PastMessages, C), Interpretation);
    .member(pnov(Pnov), Interpretation);
    .member(prpl(Prpl), Interpretation);
    .member(pnw(Pnw),   Interpretation);
    .member(topics(Topics), Interpretation);
    ia.saveLogs([info("Interpretation complete."), cycle(C), pnov(Pnov), prpl(Prpl), pnw(Pnw), topics(Topics)]);
    -+message_topics(Id, Topics);
    if (known_conversation(CId)) {
        ia.saveLogs([info("Message is part of a known conversation. Processing with ReadMs.")]);
        !read_ms(Id, Author, Content, CId, pnov(Pnov), prpl(Prpl), pnw(Pnw))
    } else {
        ia.saveLogs([info("Message is not part of a known conversation. Processing with ReadSc.")]);
        !read_sc(Id, Author, Content, CId, pnov(Pnov), prpl(Prpl), pnw(Pnw))
    };
    +known_conversation(CId);
    -read_history(PastMessages);
    +read_history([Content | PastMessages]).

-!process_single_message(_): true <-
    ia.saveLogs([info("Failed to process message, skipping."), message_id(Id)]).

+known_conversation(CId): true <-
    ia.saveLogs([info("Now agent is aware of the conversation."), conversation_id(CId)]).

/* Algorithm 3 */
+!read_sc(Id, Author, Content, CId, pnov(Pnov), prpl(Prpl), pnw(Pnw)):
    pinf(Pinf) & pmd(Pmd)
<-
    Max1 = 1 - Pnov;
    ia.U(Max1, U1);
    ia.saveLogs([u(U1), prpl(Prpl)]);
    if (U1 <= Prpl) {
        ia.saveLogs([info("Decided to engage with the message.")]);
        -+replying(CId, Id);
        readPublicProfile(Author);
        ?public_profile(Author, "pusr", Pusr);
        Max2 = 1 - Pusr - Pnw;
        ia.U(Max2, U2);
        ia.U(Max2, U3);
        ia.saveLogs([u(U2), pinf(Pinf)]);
        ia.saveLogs([u(U3), pmd(Pmd)]);
        if (U2 <= Pinf) {
            ia.saveLogs([state(infected)]);
            -+state(infected)
        } elif (U3 <= Pmd) {
            ia.saveLogs([state(vaccinated)]);
            -+state(vaccinated)
        } else {
            -+state(neutral);
            ia.saveLogs([state(neutral)])
        }
    } else {
        -+state(neutral);
        ia.saveLogs([state(neutral)])
    }.

/* Algorithm 4 */
+!read_ms(Id, Author, Content, CId, pnov(Pnov), prpl(Prpl), pnw(Pnw)):
    state(State) & popi(Popi) & pad(Pad) & message_var(Id, "state", Sk)
<-
    readPublicProfile(Author);
    ?public_profile(Author, "pusr", Pusr);
    Max1 = 1 - Pnov - Pusr;
    ia.U(Max1, U1);
    ia.saveLogs([u(U1), prpl(Prpl)]);
    if (U1 <= Prpl) {
        ia.saveLogs([info("Decided to engage with the message.")]);
        Max2 = 1 - Pnov - Pusr;
        ia.U(Max2, U2);
        ia.U(Max2, U3);
        ia.U(Max2, U4);
        ia.saveLogs([u(U2), popi(Popi)]);
        if (State == Sk & U2 <= Popi) {
            ia.saveLogs([info("Same state, decided to reply.")]);
            -+replying(CId, Id)
        } elif (State \== Sk) {
            ia.saveLogs([u(U3), pad(Pad)]);
            if (U3 <= Pad) {
                ia.saveLogs([info("Different state, adopted message state, decided to reply."), state(Sk)]);
                -+replying(CId, Id);
                -+state(Sk)
            } else {
                ia.saveLogs([u(U4), popi(Popi)]);
                if (U4 <= Popi) {
                    ia.saveLogs([info("Different state, kept own state, decided to reply."), state(State)]);
                    -+replying(CId, Id);
                    -+state(State)
                } else {
                    ia.saveLogs([info("No reply.")])
                }
            }
        } else {
            ia.saveLogs([info("No reply.")])
        }
    } else {
        ia.saveLogs([info("Decided not to engage with the message.")])
    }.

/* f(state) */
+!act(ActedNow):
    replying(CId, Id) & state(State) & message(Id, _, Content, _, _) &
    message_topics(Id, Topics) & cycle(Cycle) & State \== neutral
<-
    ActedNow = true;
    PromptParams = [content(Content), state(State)];
    Variables = [public(state(State), conversation_id(CId), cycle(Cycle))];
    ia.saveLogs([info("Waiting for content generation.")]);
    ia.createContent(Topics, PromptParams, GeneratedContent);
    ia.saveLogs([info("Finished content generation.")]);
    comment(Id, Topics, Variables, GeneratedContent);
    -message_topics(Id, _);
    -replying(CId, Id).

+!act(ActedNow): true <-
    ActedNow = false;
    ia.saveLogs([info("Skipping action.")]);
    .abolish(replying(_, _)).
