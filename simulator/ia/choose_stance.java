package ia;

import jason.asSemantics.*;
import jason.asSyntax.*;

/**
 * ia.choose_stance(+Scores, -Stance)
 *
 * Scores: list of score(Id, Score, RelationAbs) terms.
 *
 * Logic:
 *   - Compute mean polarization for relation_abs = 1  (pro group)
 *   - Compute mean polarization for relation_abs = -1 (con group)
 *   - If pro_mean > con_mean  → Stance = -1  (counter the dominant side)
 *   - If pro_mean < con_mean  → Stance =  1
 *   - If equal                → Stance =  1  (tie-break: always go pro)
 */
public class choose_stance extends DefaultInternalAction {

    @Override
    public Object execute(TransitionSystem ts, Unifier un, Term[] args) throws Exception {
        if (args.length != 2) throw new IllegalArgumentException("choose_stance expects 2 args");

        ListTerm scores = (ListTerm) args[0];

        double proSum = 0, conSum = 0;
        int proCount = 0, conCount = 0;

        for (Term t : scores) {
            Structure s = (Structure) t; // score(Id, Score, RelationAbs)
            double score    = ((NumberTerm) s.getTerm(1)).solve();
            double relAbs   = ((NumberTerm) s.getTerm(2)).solve();

            if (relAbs > 0) {
                proSum += score;
                proCount++;
            } else if (relAbs < 0) {
                conSum += score;
                conCount++;
            }
        }

        double proMean = proCount > 0 ? proSum / proCount : 0;
        double conMean = conCount > 0 ? conSum / conCount : 0;

        // Counter the dominant side; tie-break = 1
        int stance = (proMean > conMean) ? -1 : 1;

        return un.unifies(args[1], ASSyntax.createNumber(stance));
    }
}
