package ia;

import jason.asSemantics.*;
import jason.asSyntax.*;

import java.util.*;

/**
 * ia.compute_scores(+MsgData, -Scores, -GlobalPolarization, -DeepestLeaf, -VoteStats)
 *
 * MsgData: list of msg(Id, Original, Votes, RelAbs) terms.
 *          Collected in ASL via .findall after !wait_for_percepts guarantees
 *          all percepts are present — so every Id in the feed is represented.
 *
 * Pure computation — no belief base access.
 *
 * Two-pass approach:
 *   Pass 1 — compute all depths, identify leaves, collect maxDepth
 *   Pass 2 — compute scores using normalised depths
 *
 * score_i        = impact_i * depth_i_norm * relation_abs_i   (signed: pro > 0, con < 0)
 * impact_i       = (sum_{k=0..4} k * n_k) / (sum_{k=0..4} n_k) / 4
 * depth_i_norm   = depth_i / max_depth_in_feed                (root = depth 0)
 * relation_abs_i = -1 or 1
 *
 * GlobalPolarization = |mean(score_i)|   (always positive, for threshold comparison)
 *
 * Outputs:
 *   Scores            : list of score(Id, Score, RelationAbs) — signed scores
 *   GlobalPolarization: absolute value of the mean score
 *   DeepestLeaf       : Id of the deepest leaf (any relation_abs)
 *   VoteStats         : list of slot_stats(Mean, Variance) — one per vote slot 0..4
 */
public class compute_scores extends DefaultInternalAction {

    @Override
    public Object execute(TransitionSystem ts, Unifier un, Term[] args) throws Exception {
        if (args.length != 5)
            throw new IllegalArgumentException("compute_scores expects 5 args");

        ListTerm msgData = (ListTerm) args[0];
        int n = msgData.size();

        // ---- Parse MsgData ----

        List<Integer> ids = new ArrayList<>(n);
        Map<Integer, Integer> originalOf = new HashMap<>(n);
        Map<Integer, List<Integer>> voteMap = new HashMap<>(n);
        Map<Integer, Double> relationAbsMap = new HashMap<>(n);

        for (Term t : msgData) {
            Structure s = (Structure) t;

            int id       = (int) ((NumberTerm) s.getTerm(0)).solve();
            int original = (int) ((NumberTerm) s.getTerm(1)).solve();
            double rel   = ((NumberTerm) s.getTerm(3)).solve();

            ids.add(id);
            originalOf.put(id, original);
            voteMap.put(id, parseVotesList(s.getTerm(2)));
            relationAbsMap.put(id, rel);
        }

        // ---- Pass 1: compute all depths, find maxDepth and deepest leaf ----

        Map<Integer, Integer> depthMap = new HashMap<>(n);
        for (int id : ids)
            computeDepth(id, originalOf, depthMap);

        Set<Integer> parents = new HashSet<>(originalOf.values());

        int maxDepth = 0;
        int deepestLeafId = ids.get(0);
        int maxLeafDepth = -1;

        for (int id : ids) {
            int depth = depthMap.get(id);
            boolean isLeaf = !parents.contains(id);

            if (depth > maxDepth)
                maxDepth = depth;

            if (isLeaf && depth > maxLeafDepth) {
                maxLeafDepth = depth;
                deepestLeafId = id;
            }
        }

        // avoid division by zero (only roots case)
        if (maxDepth == 0) maxDepth = 1;

        // ---- Pass 2: compute signed scores using normalised depths ----
        
        List<Term> scoredTerms = new ArrayList<>(n);
        double scoreSum = 0;
        int scoreCount = 0;

        for (int id : ids) {
            double rel = relationAbsMap.get(id);
            if (rel == 0) continue;

            double impact = computeImpact(voteMap.get(id));
            double depthNorm = (double) depthMap.get(id) / maxDepth;
            double score = impact * depthNorm * rel;

            scoreSum += score;
            scoreCount++;

            scoredTerms.add(ASSyntax.createStructure("score", new Term[]{
                ASSyntax.createNumber(id),
                ASSyntax.createNumber(score),
                ASSyntax.createNumber(rel)
            }));
        }

        double globalPolarization = Math.abs(scoreSum / scoreCount);

        // ---- Per-slot vote stats across all feed messages ----

        final int SLOTS = 5;
        double[] sum = new double[SLOTS];
        double[] sumSq = new double[SLOTS];

        for (List<Integer> votes : voteMap.values()) {
            for (int k = 0; k < SLOTS; k++) {
                double v = votes.get(k);
                sum[k]   += v;
                sumSq[k] += v * v;
            }
        }

        List<Term> statTerms = new ArrayList<>(SLOTS);

        for (int k = 0; k < SLOTS; k++) {
            double mean = sum[k] / n;
            double var  = (sumSq[k] / n) - (mean * mean);

            statTerms.add(ASSyntax.createStructure("slot_stats", new Term[]{
                ASSyntax.createNumber(mean),
                ASSyntax.createNumber(Math.max(0.0, var))
            }));
        }

        // ---- Unify ----

        System.out.println("Computed scores: " + scoredTerms);
        System.out.println("Global polarization: " + globalPolarization);
        System.out.println("Deepest leaf ID: " + deepestLeafId);
        System.out.println("Slot stats: " + statTerms);

        return un.unifies(args[1], ASSyntax.createList(scoredTerms))
            && un.unifies(args[2], ASSyntax.createNumber(globalPolarization))
            && un.unifies(args[3], ASSyntax.createNumber(deepestLeafId))
            && un.unifies(args[4], ASSyntax.createList(statTerms));
    }

    // ---- Helpers ----

    private int computeDepth(int id, 
                             Map<Integer, Integer> originalOf,
                             Map<Integer, Integer> memo) {

        Integer cached = memo.get(id);
        if (cached != null) return cached;

        int parent = originalOf.get(id);

        if (parent <= 0) {
            memo.put(id, 0);
            return 0;
        }

        int depth = 1 + computeDepth(parent, originalOf, memo);
        memo.put(id, depth);
        return depth;
    }

    private double computeImpact(List<Integer> votes) {
        double weighted = 0;
        double total = 0;

        for (int k = 0; k < votes.size(); k++) {
            int v = votes.get(k);
            weighted += k * v;
            total += v;
        }

        if (total == 0) return 0;
        return (weighted / total) / 4.0;
    }

    private List<Integer> parseVotesList(Term t) {
        List<Integer> result = new ArrayList<>(5);
        ListTerm lt = (ListTerm) t;

        for (Term item : lt) {
            try {
                result.add((int) ((NumberTerm) item).solve());
            } catch (Exception e) {
                throw new RuntimeException("Invalid number term: " + item, e);
            }
        }

        return result;
    }
}