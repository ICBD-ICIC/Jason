package ia;

import jason.asSyntax.NumberTerm;
import jason.asSyntax.NumberTermImpl;

public class U extends DefaultInternalAction {

    @Override
    public Object execute(TransitionSystem ts, Unifier un, Term[] args) throws Exception {
        double max = 1.0;
        if (args.length > 0 && args[0] instanceof NumberTerm) {
            max = ((NumberTerm) args[0]).solve();
        }
        max = Math.max(0.0, Math.min(1.0, max));

        double u1;
        do {
            u1 = rand.nextDouble() * max;
        } while (u1 == 0.0);

        return un.unifies(args[args.length - 1], new NumberTermImpl(u1));
    }
}