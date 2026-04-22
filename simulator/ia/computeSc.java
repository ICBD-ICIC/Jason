package ia;

import jason.asSemantics.DefaultInternalAction;
import jason.asSemantics.TransitionSystem;
import jason.asSemantics.Unifier;
import jason.asSyntax.NumberTerm;
import jason.asSyntax.NumberTermImpl;
import jason.asSyntax.Term;

/**
 * Computes the logarithmic scaling function from the CoNVaI paper:
 *   sc(X) = 1 - e^(-alpha * X)
 *
 * Usage: ia.computeSc(+X, +Alpha, -Result)
 *   X:      the value to scale (number)
 *   Alpha:  controls the midpoint of the curve (number)
 *   Result: the scaled value in [0.0, 1.0] (unified on output)
 */
public class computeSc extends DefaultInternalAction {

    @Override
    public Object execute(TransitionSystem ts, Unifier un, Term[] args) throws Exception {
        if (args.length != 3) {
            throw new IllegalArgumentException("computeSc expects 3 arguments: X, Alpha, Result");
        }

        double x     = ((NumberTerm) args[0]).solve();
        double alpha = ((NumberTerm) args[1]).solve();
        double result = 1.0 - Math.exp(-alpha * x);

        return un.unifies(args[2], new NumberTermImpl(result));
    }
}
