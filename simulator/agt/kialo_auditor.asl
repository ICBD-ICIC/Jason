/* ==========================================================
   audit_agent.asl

   Audits the feed on a loop, computes message-level scores
   and global polarization, and intervenes with a balancing
   comment when polarization exceeds the threshold.

   Beliefs
   -------
   polarization_threshold(+T)   modifiable; default 0.5

   Cycle
   -----
   1. updateFeed(true)          — refresh percepts with public vars
   2. wait for feed_order(Ids)  — signals all percepts are being sent
   3. !wait_for_percepts(Ids)   — blocks until every message and its vars are in BB
   4. .findall                  — safe to collect all msg/4 terms now
   5. compute_scores            — pure computation, no BB access
   6. if |polarization| > T     — choose stance, build context, post comment
      else                      — log and wait
   7. wait 30 s, repeat
   ========================================================== */

polarization_threshold(0.5).

!start.

+!start : true <-
    !audit_cycle.

/* ---- Main audit loop ---- */

+!audit_cycle : true <-
    updateFeed(true);
    .wait(feed_order(Ids));
    .if_then_else(
        Ids == [],
        {
            .print("[audit] empty feed - skipping cycle");
            !audit_cycle
        },
        {
            !wait_for_percepts(Ids);
            .findall(
                msg(Id, Original, Votes, RelAbs),
                (message(Id, _, _, Original, _) &
                message_var(Id, "votes", Votes) &
                message_var(Id, "relation_abs", RelAbs)),
                MsgData
            );
            ia.compute_scores(MsgData, Scores, GlobalPolarization, DeepestLeaf, VoteStats);
            .print("[audit] global polarization = ", GlobalPolarization);
            !check_and_intervene(GlobalPolarization, DeepestLeaf, Scores, VoteStats);
            !audit_cycle
        }
    ).

/* ---- Wait until every message and its vars are in the BB ---- */

+!wait_for_percepts([]) : true <- true.
+!wait_for_percepts([Id|Rest]) : true <-
    .wait(message(Id, _, _, _, _));
    .wait(message_var(Id, "votes", _));
    .wait(message_var(Id, "relation_abs", _));
    !wait_for_percepts(Rest).

/* ---- Intervention decision ---- */

+!check_and_intervene(GlobalPolarization, DeepestLeaf, Scores, VoteStats) :
        polarization_threshold(T) & GlobalPolarization > T <-
    .print("[audit] polarization above threshold - selecting target leaf ", DeepestLeaf);
    !intervene(DeepestLeaf, Scores, VoteStats, GlobalPolarization).

+!check_and_intervene(GlobalPolarization, _, _, _) :
        polarization_threshold(T) & GlobalPolarization <= T <-
    .print("[audit] polarization within threshold - no action needed");
    ia.save_logs([polarization(GlobalPolarization), action(none), threshold(T)]).

/* ---- Build context and post comment ---- */

+!intervene(LeafId, Scores, VoteStats, GlobalPolarization) <-
    .wait(message(LeafId, _, LeafContent, ParentId, _));
    .wait(message(ParentId, _, ParentClaim, _, _));
    .findall(C, (message(SibId, _, C, ParentId, _) & SibId \== LeafId), SibContents);
    .concat(SibContents, "\n", SiblingsStr);
    ia.choose_stance(Scores, Stance);
    .wait(message_var(LeafId, "relation_abs", LeafRelAbs));
    .if_then_else(
        Stance == LeafRelAbs,
        Relation = 1,
        Relation = -1
    );
    PromptParams = [stance(Stance), 
                    targetLeaf(LeafContent), 
                    parentClaim(ParentClaim), 
                    siblings(SiblingsStr)];
    ia.createContent([], PromptParams, CommentContent);
    ia.choose_votes(VoteStats, Votes);
    CommentVars = [
        generated(true),
        public([relation_abs(Stance), relation(Relation), votes(Votes)]),
        prompt_params(PromptParams)];
    comment(LeafId, [], CommentVars, CommentContent);
    .print("[audit] comment posted on leaf ", LeafId, " with stance ", Stance);
    polarization_threshold(T);
    ia.save_logs([polarization(GlobalPolarization), action(comment),
                  leaf(LeafId), stance(Stance), threshold(T)]).
