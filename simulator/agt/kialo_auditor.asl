/* ==========================================================
   kialo_auditor.asl

   Monitors the Kialo debate feed and detects polarization.
   Polarization is computed as the mean absolute score across
   messages, where:

     score_i        = impact_i * depth_i * relation_abs_i
     impact_i       = (sum_{k=0..4} k * n_k) / (sum_{k=0..4} n_k) / 4
     depth_i        = depth of message normalised by max depth in feed
     relation_abs_i = value of public variable "relation_abs"

   If polarization exceeds the threshold, a balancing comment is
   posted on the deepest leaf in the underrepresented group.
   ========================================================== */

polarization_threshold(0.5).
audit_interval(15000).
wait_timeout(3000).

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
    !collect_depths(Ids, IdsWithDepths);
    !find_max_depth(IdsWithDepths, MaxDepth);
    !compute_scores(IdsWithDepths, MaxDepth, [], Scores);
    !mean_scores(Scores, ProMean, ConMean, OverallMean);
    .print("[Auditor] Polarization=", OverallMean, " ProMean=", ProMean, " ConMean=", ConMean);
    !evaluate_polarization(OverallMean, ProMean, ConMean, IdsWithDepths).

/* ---- depth collection (cached as id_depth/2 beliefs) ---- */

+!collect_depths([], []) : true <- true.

+!collect_depths([Id|Rest], [id_depth(Id, D)|Tail]) : id_depth(Id, D) <-
    !collect_depths(Rest, Tail).

+!collect_depths([Id|Rest], [id_depth(Id, D)|Tail]) : true <-
    !get_depth(Id, 0, D);
    +id_depth(Id, D);
    !collect_depths(Rest, Tail).

/* Root node: timed out waiting for message */
+!get_depth(Id, Acc, Acc) :
        not message(Id, _, _, _, _) <-
    wait_timeout(T);
    .wait(message(Id, _Author, _Content, _Original, _Timestamp), T, true).

/* Root node: Original = 0 means no parent */
+!get_depth(Id, Acc, Acc) :
        message(Id, _, _, 0, _) <- true.

/* Recursive case: follow parent */
+!get_depth(Id, Acc, Depth) :
        message(Id, _, _, Original, _) & Original \== 0 <-
    NewAcc = Acc + 1;
    !get_depth(Original, NewAcc, Depth).

/* ---- max depth helper ---- */

+!find_max_depth([], 0) : true <- true.

+!find_max_depth(IdsWithDepths, MaxDepth) : true <-
    .findall(D, .member(id_depth(_, D), IdsWithDepths), Depths);
    .max(Depths, MaxDepth).

/* ---- per-message score computation ---- */

+!compute_scores([], _MaxDepth, Acc, Acc) : true <- true.

+!compute_scores([id_depth(Id, RawDepth)|Rest], 0, Acc, Scores) : true <-
    !get_message_vars(Id, RelAbs, Votes);
    !compute_impact(Votes, Impact);
    Score = Impact * 0 * RelAbs;
    !get_relation(Id, Relation);
    !compute_scores(Rest, 0, [score(Id, Score, Relation, RawDepth)|Acc], Scores).

+!compute_scores([id_depth(Id, RawDepth)|Rest], MaxDepth, Acc, Scores) : MaxDepth > 0 <-
    !get_message_vars(Id, RelAbs, Votes);
    !compute_impact(Votes, Impact);
    NormDepth = RawDepth / MaxDepth;
    Score = Impact * NormDepth * RelAbs;
    !get_relation(Id, Relation);
    !compute_scores(Rest, MaxDepth, [score(Id, Score, Relation, RawDepth)|Acc], Scores).

+!get_message_vars(Id, RelAbs, Votes) : true <-
    wait_timeout(T);
    .wait(message_var(Id, "relation_abs", RelAbs), T, T2);
    .wait(message_var(Id, "votes",        Votes),  T, T3);
    !default_if_timeout(T2, RelAbs, 0.0);
    !default_if_timeout(T3, Votes,  [0,0,0,0,0]).

+!default_if_timeout(true, X, Default) : true <- X = Default.
+!default_if_timeout(false, _, _)      : true <- true.

+!get_relation(Id, Relation) : true <-
    wait_timeout(T);
    .wait(message_var(Id, "relation", Relation), T, TimedOut);
    !default_if_timeout(TimedOut, Relation, 0).

/* ---- impact formula: (sum k*n_k) / (sum n_k) / 4 ---- */

+!compute_impact([0,0,0,0,0], 0.0) : true <- true.

+!compute_impact(Votes, Impact) : true <-
    Votes = [N0, N1, N2, N3, N4];
    WeightedSum = 0*N0 + 1*N1 + 2*N2 + 3*N3 + 4*N4;
    TotalVotes  = N0 + N1 + N2 + N3 + N4;
    Impact = WeightedSum / TotalVotes / 4.

/* ---- aggregate mean scores ---- */

+!mean_scores(Scores, ProMean, ConMean, OverallMean) : true <-
    !filter_scores(Scores, 1,  ProScores);
    !filter_scores(Scores, -1, ConScores);
    !list_mean_abs(ProScores,  ProMean);
    !list_mean_abs(ConScores,  ConMean);
    !list_mean_abs(Scores,     OverallMean).

+!filter_scores([], _Side, []) : true <- true.

+!filter_scores([score(Id, S, R, D)|Rest], Side, [score(Id, S, R, D)|Filtered]) : R = Side <-
    !filter_scores(Rest, Side, Filtered).

+!filter_scores([_|Rest], Side, Filtered) : true <-
    !filter_scores(Rest, Side, Filtered).

+!list_mean_abs([], 0.0) : true <- true.

+!list_mean_abs(Scores, Mean) : .length(Scores, N) & N > 0 <-
    !sum_abs_scores(Scores, 0.0, Sum);
    Mean = Sum / N.

+!list_mean_abs(_, 0.0) : true <- true.

+!sum_abs_scores([], Acc, Acc) : true <- true.

+!sum_abs_scores([score(_, S, _, _)|Rest], Acc, Sum) : true <-
    Abs = math.abs(S);
    NewAcc = Acc + Abs;
    !sum_abs_scores(Rest, NewAcc, Sum).

/* ---- polarization decision ---- */

+!evaluate_polarization(OverallMean, _ProMean, _ConMean, _IdsWithDepths) :
        polarization_threshold(Threshold) & OverallMean <= Threshold <-
    .print("[Auditor] Debate not polarized (score=", OverallMean, "). No action.").

+!evaluate_polarization(OverallMean, ProMean, ConMean, IdsWithDepths) : true <-
    .print("[Auditor] Polarization detected (score=", OverallMean, "). Intervening...");
    !choose_target_side(ProMean, ConMean, TargetSide);
    !find_deepest_leaf(IdsWithDepths, TargetSide, LeafId, LeafRelation);
    !post_balancing_comment(TargetSide, LeafId, LeafRelation).

/* ---- choose which side to reinforce (the weaker one) ---- */

+!choose_target_side(ProMean, ConMean, 1) : ProMean < ConMean <-
    .print("[Auditor] PRO side is weaker — targeting pro.").

+!choose_target_side(_ProMean, _ConMean, -1) : true <-
    .print("[Auditor] CON side is weaker — targeting con.").

/* ---- find the deepest leaf on the target side ---- */
/* A leaf is a message with no children in the feed.   */

+!find_deepest_leaf(IdsWithDepths, TargetSide, LeafId, LeafRelation) : true <-
    !build_parent_set(IdsWithDepths, [], ParentSet);
    !best_leaf(IdsWithDepths, ParentSet, TargetSide, none, -1, LeafId);
    !get_leaf_relation(LeafId, LeafRelation).

+!get_leaf_relation(none, 0) : true <- true.

+!get_leaf_relation(LeafId, LeafRelation) : true <-
    wait_timeout(T);
    .wait(message_var(LeafId, "relation", LeafRelation), T, TimedOut);
    !default_if_timeout(TimedOut, LeafRelation, 0).

+!build_parent_set([], Acc, Acc) : true <- true.

+!build_parent_set([id_depth(Id,_)|Rest], Acc, ParentSet) : true <-
    wait_timeout(T);
    .wait(message(Id, _Author, _Content, Original, _Timestamp), T, TimedOut);
    !add_parent(TimedOut, Original, Rest, Acc, ParentSet).

+!add_parent(true, _Original, Rest, Acc, ParentSet) : true <-
    !build_parent_set(Rest, Acc, ParentSet).

+!add_parent(_, 0, Rest, Acc, ParentSet) : true <-
    !build_parent_set(Rest, Acc, ParentSet).

+!add_parent(_, Original, Rest, Acc, ParentSet) : true <-
    !build_parent_set(Rest, [Original|Acc], ParentSet).

+!best_leaf([], _Parents, _Side, BestId, _BestD, BestId) : true <- true.

+!best_leaf([id_depth(Id, _)|Rest], Parents, Side, CurBestId, CurBestD, FinalId) :
        .member(Id, Parents) <-
    !best_leaf(Rest, Parents, Side, CurBestId, CurBestD, FinalId).

+!best_leaf([id_depth(Id, D)|Rest], Parents, Side, CurBestId, CurBestD, FinalId) : true <-
    wait_timeout(T);
    .wait(message_var(Id, "relation", R), T, TimedOut);
    !default_if_timeout(TimedOut, R, 0);
    !update_best(Id, D, R, Side, CurBestId, CurBestD, NewBestId, NewBestD);
    !best_leaf(Rest, Parents, Side, NewBestId, NewBestD, FinalId).

+!update_best(Id, D, Side, Side, _CurBestId, CurBestD, Id, D) : D > CurBestD <- true.

+!update_best(_Id, _D, _R, _Side, CurBestId, CurBestD, CurBestId, CurBestD) : true <- true.

/* ---- derive comment relation from parent relation + target side ----
   CommentRelation = TargetSide, since the comment is a direct child
   of the leaf and must point in the direction we are reinforcing.
   -------------------------------------------------------------------- */

+!derive_relation(_LeafRelation, TargetSide, TargetSide) : true <- true.

/* ---- post the balancing comment ---- */

+!post_balancing_comment(_TargetSide, none, _LeafRelation) : true <-
    .print("[Auditor] No suitable leaf found. Skipping comment.").

+!post_balancing_comment(TargetSide, LeafId, LeafRelation) : true <-
    !derive_relation(LeafRelation, TargetSide, CommentRelation);
    wait_timeout(T);
    .wait(message(LeafId,   _A1, LeafContent,   ParentId, _T1), T);
    .wait(message(ParentId, _A2, ParentContent, _P2,      _T2), T);
    .findall(C, (message(SibId, _A, C, ParentId, _T) & SibId \== LeafId), SiblingsRaw);
    !take_first_n(SiblingsRaw, 3, Siblings);
    Topics    = ["debate balance", TargetSide];
    Variables = [
        relation(CommentRelation),
        stance(TargetSide),
        targetLeaf(LeafContent),
        parentClaim(ParentContent),
        siblings(Siblings)
    ];
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
    comment(LeafId, Topics, PostVariables, GeneratedContent).

+!take_first_n(_, 0, []) : true <- true.
+!take_first_n([], _, []) : true <- true.

+!take_first_n([H|T], N, [H|R]) : N > 0 <-
    N1 = N - 1;
    !take_first_n(T, N1, R).
