package ia;

import jason.asSemantics.*;
import jason.asSyntax.*;

import java.util.*;

/**
 * ia.choose_votes(+VoteStats, -Votes)
 *
 * Samples a votes list from the feed distribution.
 * For each slot k, draws from Normal(mean_k, sqrt(var_k)), rounds, clamps to >= 0.
 * VoteStats: list of slot_stats(Mean, Variance) produced by compute_scores.
 * Votes: Jason list of 5 integers.
 */
public class choose_votes extends DefaultInternalAction {

    private static final Random RNG = new Random();

    @Override
    public Object execute(TransitionSystem ts, Unifier un, Term[] args) throws Exception {
        if (args.length != 2) throw new IllegalArgumentException("build_comment_vars expects 2 args");

        ListTerm voteStats = (ListTerm) args[0];

        List<Term> voteTerms = new ArrayList<>();
        int slot = 0;
        for (Term statTerm : voteStats) {
            Structure s = (Structure) statTerm; // slot_stats(Mean, Variance)
            double mean = ((NumberTerm) s.getTerm(0)).solve();
            double std  = Math.sqrt(((NumberTerm) s.getTerm(1)).solve());
            int value   = Math.max(0, (int) Math.round(mean + RNG.nextGaussian() * std));
            voteTerms.add(ASSyntax.createNumber(value));
            if (++slot >= 5) break;
        }
        while (voteTerms.size() < 5) voteTerms.add(ASSyntax.createNumber(0));

        return un.unifies(args[1], ASSyntax.createList(voteTerms));
    }
}
