/* ==========================================================
   Full LLM Agent

   The BDI cycle is a thin wrapper. interpretContent() returns
   the full decision from Gemini (action + state). The ASL
   reads that decision and executes the corresponding
   environment actions — no transition logic lives here.

   Agent states: neutral | infected | vaccinated
   ========================================================== */

// --- Initial beliefs ---
state(neutral).

// --- Startup ---
+!start: true <-
    updateFeed;
    !main_cycle.

+!main_cycle: true <-
    .wait(feed_order(_));
    !process_feed;
    .wait(5000);
    !main_cycle.

// --- Feed processing ---
+!process_feed: feed_order(Ids) <-
    !process_messages(Ids).

+!process_feed: not feed_order(_) <- true.

+!process_messages([]): true <- true.

+!process_messages([Id|Rest]): true <-
    !process_single_message(Id);
    !process_messages(Rest).

// --- Single message: delegate entirely to LLM ---
+!process_single_message(Id):
    message(Id, Author, Content, Original, Timestamp) <-
    // Gemini decides action, state, reaction, and reasoning
    ia.interpretContent(Content, Decision);
    .member(action(Action), Decision);
    .member(state(NewState), Decision);
    -+state(NewState);
    !execute_action(Id, Content, Decision, Action);
    !log_decision(Id, Decision).

+!process_single_message(Id): not message(Id, _, _, _, _) <- true.

// --- Execute the LLM's chosen action ---
+!execute_action(Id, Content, Decision, "spread"): state(S) <-
    Topics    = ["misinformation", "spread"];
    Variables = [state(S), source_id(Id)];
    ia.createContent(Topics, Variables, NewContent);
    createPost(Topics, Variables, NewContent);
    repost(Id);
    updateFeed.

+!execute_action(Id, Content, Decision, "debunk"): state(S) <-
    Topics    = ["misinformation", "debunk"];
    Variables = [state(S), source_id(Id)];
    ia.createContent(Topics, Variables, NewContent);
    createPost(Topics, Variables, NewContent);
    comment(Id, Topics, Variables, NewContent);
    updateFeed.

+!execute_action(Id, Content, Decision, "react"): true <-
    .member(reaction(Reaction), Decision);
    react(Id, Reaction);
    updateFeed.

+!execute_action(Id, Content, Decision, "comment"): state(S) <-
    Topics    = ["comment"];
    Variables = [state(S), source_id(Id)];
    ia.createContent(Topics, Variables, NewContent);
    comment(Id, Topics, Variables, NewContent);
    updateFeed.

+!execute_action(Id, Content, Decision, "ignore"): true <- true.

// Default fallback
+!execute_action(Id, Content, Decision, _): true <- true.

// --- Logging ---
+!log_decision(Id, Decision): state(S) <-
    .member(action(Action), Decision);
    .member(reasoning(Reasoning), Decision);
    .member(misinformation_risk(Risk), Decision);
    ia.save_logs([event("llm_decision"), message_id(Id), agent_state(S),
                  action(Action), reasoning(Reasoning),
                  misinformation_risk(Risk)]).
