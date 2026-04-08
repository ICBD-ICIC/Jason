/* ==========================================================
   kialo_auditor.asl

   Monitors the Kialo debate feed and detects polarization.
   Polarization is computed as the mean absolute score across
   messages, where:

     score_i     = impact_i * depth_i * relation_abs_i
     impact_i    = (sum_{k=0..4} k * n_k) / (sum_{k=0..4} n_k) / 4
     depth_i     = depth of message normalised by max depth in feed
     relation_abs_i = value of public variable "relation_abs"

   If polarization exceeds the threshold, a balancing comment is
   posted on the longest leaf in the underrepresented group.
   The comment's "relation" variable is derived from the parent
   node's relation and the required side (pro/con).
   ========================================================== */

polarization_threshold(0.5).
audit_interval(15000).

!start.

+!start : true <-
    .print("[Auditor] Starting polarization monitor...");
    !audit_loop.

+!audit_loop : true <-
    !run_audit;
    audit_interval(Interval);
    .wait(Interval);
    !audit_loop.

/* ---- main audit cycle ---- */

+!run_audit : true <-
    .print("[Auditor] Fetching feed...");
    updateFeed(true);
    .wait(feed_order(Ids));
    !collect_depths(Ids, Ids, Depths);        
    !find_max(Depths, 0, MaxDepth);
    !compute_scores(Ids, MaxDepth, [], Scores);
    !mean_scores(Scores, ProMean, ConMean, OverallMean);
    .print("[Auditor] Polarization=", OverallMean, " ProMean=", ProMean, " ConMean=", ConMean); /*TODO: save logs */
    !evaluate_polarization(OverallMean, ProMean, ConMean, Ids, MaxDepth).

/* ---- depth collection ---- */

+!collect_depths([], _AllIds, []) : true <- true.

+!collect_depths([Id|Rest], AllIds, [D|Ds]) : true <-
    !get_depth(Id, 0, D);
    !collect_depths(Rest, AllIds, Ds).

/* Base case: no parent_id found — this is the root */
+!get_depth(Id, Acc, Acc) : true <-
    .wait(message(Id, "parent_id", _ParentId), 3000).

/* Recursive case: follow the parent link */
+!get_depth(Id, Acc, Depth) : true <-
    .wait(message_var(Id, "parent_id", ParentId), 3000, _TimedOut);
    NewAcc = Acc + 1;
    !get_depth(ParentId, NewAcc, Depth).

/* ---- max helper ---- */

+!find_max([], Acc, Acc) : true <- true.

+!find_max([H|T], Acc, Max) : H > Acc <-
    !find_max(T, H, Max).

+!find_max([H|T], Acc, Max) : H =< Acc <-
    !find_max(T, Acc, Max).

/* ---- per-message score computation ---- */

+!compute_scores([], _MaxDepth, Acc, Acc) : true <- true.

+!compute_scores([Id|Rest], MaxDepth, Acc, Scores) : MaxDepth > 0 <-
    !get_message_vars(Id, RawDepth, RelAbs, Votes);
    !compute_impact(Votes, Impact);
    NormDepth = RawDepth / MaxDepth;
    Score = Impact * NormDepth * RelAbs;
    !get_relation(Id, Relation);
    !compute_scores(Rest, MaxDepth, [score(Id, Score, Relation, RawDepth)|Acc], Scores).

+!compute_scores([Id|Rest], MaxDepth, Acc, Scores) : true <-
    !get_message_vars(Id, _RawDepth, RelAbs, Votes);
    !compute_impact(Votes, Impact);
    Score = Impact * 0 * RelAbs;
    !get_relation(Id, Relation);
    !compute_scores(Rest, MaxDepth, [score(Id, Score, Relation, 0)|Acc], Scores).

+!get_message_vars(Id, Depth, RelAbs, Votes) : true <-
    .wait(message_var(Id, "depth",        Depth),    3000, T1);
    .wait(message_var(Id, "relation_abs", RelAbs),   3000, T2);
    .wait(message_var(Id, "votes",        Votes),    3000, T3);
    (T1 -> Depth   = 0   ; true);
    (T2 -> RelAbs  = 0.0 ; true);
    (T3 -> Votes   = [0,0,0,0,0] ; true).

/* ---- impact formula: (sum k*n_k) / (sum n_k) / 4 ---- */

+!compute_impact(Votes, Impact) : true <-
    Votes = [N0, N1, N2, N3, N4];
    WeightedSum = 0*N0 + 1*N1 + 2*N2 + 3*N3 + 4*N4;
    TotalVotes  = N0 + N1 + N2 + N3 + N4;
    (TotalVotes > 0 ->
        Impact = WeightedSum / TotalVotes / 4
    ;
        Impact = 0.0
    ).

/* ---- aggregate mean scores ---- */

+!mean_scores(Scores, ProMean, ConMean, OverallMean) : true <-
    !filter_scores(Scores, 1,  ProScores);
    !filter_scores(Scores, -1, ConScores);
    !list_mean_abs(ProScores, ProMean);
    !list_mean_abs(ConScores, ConMean);
    !list_mean_abs(Scores,    OverallMean).

+!filter_scores([], _Side, []) : true <- true.

+!filter_scores([score(Id, S, R, D)|Rest], Side, [score(Id, S, R, D)|Filtered]) :
        R = Side <-
    !filter_scores(Rest, Side, Filtered).

+!filter_scores([_|Rest], Side, Filtered) : true <-
    !filter_scores(Rest, Side, Filtered).

+!list_mean_abs([], 0.0) : true <- true.

+!list_mean_abs(Scores, Mean) : .length(Scores, N) & N > 0 <-
    !sum_abs_scores(Scores, 0.0, Sum);
    Mean = Sum / N.

+!list_mean_abs(Scores, 0.0) : true <-
    true.

+!sum_abs_scores([], Acc, Acc) : true <- true.

+!sum_abs_scores([score(_, S, _, _)|Rest], Acc, Sum) : true <-
    Abs = math.abs(S);
    NewAcc = Acc + Abs;
    !sum_abs_scores(Rest, NewAcc, Sum).

/* ---- polarization decision ---- */

+!evaluate_polarization(OverallMean, _ProMean, _ConMean, _Ids, _MaxDepth) :
        polarization_threshold(Threshold) &
        OverallMean =< Threshold <-
    .print("[Auditor] Debate not polarized (score=", OverallMean, "). No action.").

+!evaluate_polarization(OverallMean, ProMean, ConMean, Ids, MaxDepth) : true <-
    .print("[Auditor] Polarization detected (score=", OverallMean, "). Intervening...");
    !choose_target_side(ProMean, ConMean, TargetSide);
    !find_longest_leaf(Ids, TargetSide, MaxDepth, LeafId, LeafRelation);
    !post_balancing_comment(TargetSide, LeafId, LeafRelation).

/* ---- choose which side to reinforce (the weaker one) ---- */

+!choose_target_side(ProMean, ConMean, "pro") :
        ProMean < ConMean <-
    .print("[Auditor] PRO side is weaker — targeting pro.").

+!choose_target_side(ProMean, ConMean, "con") :
        ConMean =< ProMean <-
    .print("[Auditor] CON side is weaker — targeting con.").

/* ---- find longest leaf on the target side ---- */ /* TODO is the right side? */
/* A leaf is a message with no children in the feed. */
/* We pick the one with greatest depth from the target side. */

+!find_longest_leaf(Ids, TargetSide, MaxDepth, LeafId, LeafRelation) : true <-
    !build_parent_set(Ids, [], ParentSet);
    !best_leaf(Ids, ParentSet, TargetSide, MaxDepth, none, -1, LeafId, LeafRelation).

+!build_parent_set([], Acc, Acc) : true <- true.

+!build_parent_set([Id|Rest], Acc, ParentSet) : true <-
    .wait(message_var(Id, "parent_id", PId), 3000, TimedOut);
    (TimedOut ->
        !build_parent_set(Rest, Acc, ParentSet)
    ;
        !build_parent_set(Rest, [PId|Acc], ParentSet)
    ).

+!best_leaf([], _Parents, _Side, _MaxDepth, BestId, _BestD, BestId, BestRelation) : true <- /*TODO: ver que hace esto*/
    /* Fall back to no relation if no leaf found on that side */
    (BestId = none ->
        BestRelation = "none"
    ;
        .wait(message_var(BestId, "relation", BestRelation), 3000, _T)
    ).

+!best_leaf([Id|Rest], Parents, Side, MaxDepth, CurBestId, CurBestD, FinalId, FinalRelation) : true <-
    .member(Id, Parents) ->
        /* Id is a parent — not a leaf */
        !best_leaf(Rest, Parents, Side, MaxDepth, CurBestId, CurBestD, FinalId, FinalRelation)
    ;
    (
        .wait(message_var(Id, "relation",     R),    3000, T1);
        .wait(message_var(Id, "relation_abs", RA),   3000, T2);
        .wait(message_var(Id, "depth",        D),    3000, T3);
        (T1 -> R  = "none" ; true);
        (T2 -> RA = 0      ; true);
        (T3 -> D  = 0      ; true);
        !side_of_relation(R, RA, NodeSide);
        (NodeSide = Side & D > CurBestD ->
            !best_leaf(Rest, Parents, Side, MaxDepth, Id, D, FinalId, FinalRelation)
        ;
            !best_leaf(Rest, Parents, Side, MaxDepth, CurBestId, CurBestD, FinalId, FinalRelation)
        )
    ).

/* Map (relation, relation_abs) → "pro" | "con" | "neutral" */
+!side_of_relation(R, _RA, "pro")     : R = 1  <- true.
+!side_of_relation(R, _RA, "pro")     : R = "pro" <- true.
+!side_of_relation(R, _RA, "con")     : R = -1 <- true.
+!side_of_relation(R, _RA, "con")     : R = "con" <- true.
+!side_of_relation(_R, _RA, "neutral") : true <- true.

/* ---- derive comment relation from parent relation + target side ----
   Rules:
     parent is pro  (1)  + target side is pro  → comment supports pro  → relation  1 (agrees with parent)
     parent is pro  (1)  + target side is con  → comment attacks pro   → relation -1 (disagrees with parent)
     parent is con  (-1) + target side is con  → comment supports con  → relation -1 (agrees with parent)
     parent is con  (-1) + target side is pro  → comment attacks con   → relation  1 (disagrees with parent)
     parent is neutral   + target side is pro  → relation  1
     parent is neutral   + target side is con  → relation -1
   -------------------------------------------------------------------- */

+!derive_relation("pro",  "pro",  1)  : true <- true.
+!derive_relation("pro",  "con", -1)  : true <- true.
+!derive_relation("con",  "con", -1)  : true <- true.
+!derive_relation("con",  "pro",  1)  : true <- true.
+!derive_relation(_,      "pro",  1)  : true <- true.
+!derive_relation(_,      "con", -1)  : true <- true.

/* ---- post the balancing comment ---- */

+!post_balancing_comment(_TargetSide, none, _LeafRelation, _Ids) : true <-
    .print("[Auditor] No suitable leaf found. Skipping comment.").

+!post_balancing_comment(TargetSide, LeafId, LeafRelation, Ids) : true <-
    !derive_relation(LeafRelation, TargetSide, CommentRelation);
    .wait(message(LeafId, _A1, LeafContent, ParentId, _T1), 3000);
    .wait(message(ParentId, _A2, ParentContent, _P2, _T2), 3000);
    !get_siblings(LeafId, ParentId, Ids, [], SiblingsRaw);
    !take_first_n(SiblingsRaw, 3, Siblings);
    Topics    = ["debate balance", TargetSide];
    Variables = [
        relation(CommentRelation),
        public(relation(CommentRelation)),
        stance(TargetSide),
        targetLeaf(LeafContent),
        parentClaim(ParentContent),
        siblings(Siblings)
    ],
    ia.createContent(Topics, Variables, GeneratedContent);
    .print("[Auditor] Posting comment (side=", TargetSide,
           ", relation=", CommentRelation,
           ", parent=", LeafId, "): ", GeneratedContent);
    PostVariables = [
        relation(CommentRelation),
        public(relation(CommentRelation)),
        public(relation_abs(math.abs(CommentRelation))),
        sentiment(neutral),
        role("auditor"),
        parent_id(LeafId)
    ];
    commentPost(Topics, PostVariables, GeneratedContent, LeafId).

+!get_siblings(_LeafId, _ParentId, [], Acc, Acc) : true <- true.

+!get_siblings(LeafId, ParentId, [Id|Rest], Acc, Siblings) :
    message(Id, _A, C, P, _T) & P = ParentId & Id \= LeafId <-
    !get_siblings(LeafId, ParentId, Rest, [C|Acc], Siblings).

+!get_siblings(LeafId, ParentId, [Id|Rest], Acc, Siblings) : true <-
    !get_siblings(LeafId, ParentId, Rest, Acc, Siblings).

+!take_first_n(_, 0, []) : true <- true.
+!take_first_n([], _, []) : true <- true.

+!take_first_n([H|T], N, [H|R]) : N > 0 <-
    N1 = N - 1;
    !take_first_n(T, N1, R).

