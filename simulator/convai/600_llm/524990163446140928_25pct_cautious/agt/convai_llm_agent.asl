/* ==========================================================
    CoNVaI LLM Agent (Jason BDI)
    Variant of the CoNVaI agent (Definition 6) in which the
    probabilistic transition function g (Algorithms 2-4) is
    replaced by a single LLM call per message.

    The LLM receives:
      - The agent's personality_description (second-person prompt)
      - Raw social profile: followers_count, friends_count,
        listed_count, verified
      - The message content and conversation history
      - The agent's current state

    And returns:
      - new_state     : neutral | infected | vaccinated
      - reply_content : tweet text, or "" if the agent stays silent

    The SocialAgArch interface is used as follows:
      interpretContent(Term)  ->  Map<String,Object>
          Input  : content(Text, PastMessages, CurrentState,
                           FollowersCount, FriendsCount,
                           ListedCount, Verified,
                           PersonalityDescription)
          Output : {new_state: string, reply_content: string}

      createContent is NOT used by this agent; the LLM generates
      reply text inside interpretContent in a single unified call.

    Internal state S and Actions A are unchanged from the original.
    P_RD / messages_read gating is removed; the LLM decides whether
    to reply via the reply_content field (empty string = skip).
   ========================================================== */

cycle(0).
max_cycles(1000).
max_cycles_reached(false).

idle_cycles(0).
inactivity_limit(60).
idle_limit_reached(false).

!init.

+!init: susceptible(false) & state(State) <-
    .my_name(Me);
    ia.saveLogs([info("Killing agent - not reachable in network."), agent(Me), state(State)]);
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
    ia.saveLogs([info("Started processing messages.")]);
    !process_messages(Ids, 0, ActCount);
    .length(Ids, Len);
    ia.saveLogs([info("Finished processing messages. Waiting before restart."), messages_processed(Len), actions_taken(ActCount)]);
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

+!process_messages([Id|Rest], ActSoFar, ActFinal): true <-
    !process_single_message(Id, ActedNow);
    if (ActedNow) { ActNext = ActSoFar + 1 } else { ActNext = ActSoFar };
    !process_messages(Rest, ActNext, ActFinal).

-!process_messages(_Ids, ActSoFar, ActFinal): true <-
    ActFinal = ActSoFar;
    ia.saveLogs([info("process_messages failed.")]).

+!process_single_message(Id, ActedNow):
    read_history(PastMessages) &
    message(Id, Author, Content, _Original, _Timestamp) &
    message_var(Id, "conversation_id", CId) &
    cycle(C) &
    state(CurrentState) &
    personality_description(PersonalityDesc) 
<-
    ia.saveLogs([info("Processing message with LLM."), cycle(C), message_id(Id)]);
    readPublicProfile(Author);
    ?public_profile(Author, "followers_count", Followers);
    ?public_profile(Author, "friends_count", Friends);
    ?public_profile(Author, "listed_count", Listed);
    ?public_profile(Author, "verified", Verified);
    ia.interpretContent(
        content(Content, PastMessages, CurrentState,
                Followers, Friends, Listed, Verified,
                PersonalityDesc),
        LLMResult
    );
    ia.saveLogs([llm_result(LLMResult)]);
    .member(new_state(NewState),       LLMResult);
    .member(reply_content(ReplyText),  LLMResult);
    .member(topics(Topics),            LLMResult);

    if (NewState \== CurrentState) {
        -+state(NewState);
        ia.saveLogs([info("State transition."), state(NewState)])
    } else {
        ia.saveLogs([info("No state transition."), state(CurrentState)])
    };

    -read_history(PastMessages);
    if (ReplyText \== "" & NewState \== neutral) {
        Variables = [public(state(NewState), conversation_id(CId), cycle(C))];
        comment(Id, Topics, Variables, ReplyText);
        +read_history([Content, ReplyText | PastMessages]);
        ActedNow = true;
        ia.saveLogs([info("Reply posted.")])
    } else {
        +read_history([Content | PastMessages]);
        ActedNow = false;
        ia.saveLogs([info("No reply.")])
    }.

-!process_single_message(_Id, ActedNow): true <-
    ActedNow = false;
    ia.saveLogs([info("Failed to process message, skipping.")]).

