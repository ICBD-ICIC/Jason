/* ==========================================================
   kialo_auditor.asl

   Monitors the Kialo debate feed and detects imbalances between
   pro and con messages. If the imbalance exceeds a threshold,
   it uses Gemini (via ia.createContent) to generate and post
   a balancing argument on the underrepresented side.
   ========================================================== */

imbalance_threshold(0.3).
audit_interval(15000).

!start.

+!start : true <-
    .print("[Auditor] Starting debate balance monitor...");
    !audit_loop.

+!audit_loop : true <-
    !run_audit;
    audit_interval(Interval);
    .wait(Interval);
    !audit_loop.

+!run_audit : true <-
    .print("[Auditor] Fetching feed with public vars...");
    updateFeed(true);
    .wait(feed_order(Ids));
    !count_sides(Ids, 0, 0, ProCount, ConCount);
    .print("[Auditor] Pro messages: ", ProCount, " | Con messages: ", ConCount);
    !evaluate_balance(ProCount, ConCount).

+!count_sides([], ProAcc, ConAcc, ProAcc, ConAcc) : true <- true.

+!count_sides([Id|Rest], ProAcc, ConAcc, ProFinal, ConFinal) : true <-
    !get_relation(Id, Relation);
    !update_counts(Relation, ProAcc, ConAcc, NewPro, NewCon);
    !count_sides(Rest, NewPro, NewCon, ProFinal, ConFinal).

+!get_relation(Id, Relation) :
        message_var(Id, "relation", Relation) <- true.

+!get_relation(Id, Relation) : true <-
    .wait(message_var(Id, "relation", Relation), 3000, TimedOut);
    (TimedOut -> Relation = "none" ; true).

+!get_relation(_, "none") : true <- true.

+!update_counts(1,  P, C, NP, C)  : true <- NP = P + 1.
+!update_counts(-1, P, C, P,  NC) : true <- NC = C + 1.
+!update_counts(_,  P, C, P,  C)  : true <- true.   // neutral / none

+!evaluate_balance(0, 0) : true <-
    .print("[Auditor] No messages yet, nothing to balance.").

+!evaluate_balance(ProCount, ConCount) : true <-
    Total = ProCount + ConCount;
    Diff  = math.abs(ProCount - ConCount);
    Ratio = Diff / Total;
    imbalance_threshold(Threshold);
    (Ratio > Threshold ->
        !choose_side(ProCount, ConCount)
    ;
        .print("[Auditor] Debate is balanced (ratio=", Ratio, "). No action needed.")
    ).

+!choose_side(ProCount, ConCount) :
        ProCount < ConCount <-
    .print("[Auditor] Imbalance detected — PRO side is underrepresented. Generating pro argument...");
    !post_balancing_argument("pro").

+!choose_side(ProCount, ConCount) :
        ConCount < ProCount <-
    .print("[Auditor] Imbalance detected — CON side is underrepresented. Generating con argument...");
    !post_balancing_argument("con").

+!choose_side(_, _) : true <- true.   // perfectly equal, no action

+!post_balancing_argument(Side) : true <-
    Topics    = ["debate balance", Side];
    Variables = [public(relation(Side)), relation(Side)];
    ia.createContent(Topics, Variables, GeneratedContent);
    .print("[Auditor] Posting balancing argument (", Side, "): ", GeneratedContent);
    PostVariables = [relation(Side), public(relation(Side)), sentiment(neutral), role("auditor")];
    createPost(Topics, PostVariables, GeneratedContent).
