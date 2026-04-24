package ia;

import jason.asSemantics.*;
import jason.asSyntax.*;

import java.util.Random;

public class U extends DefaultInternalAction {

    private final Random rand = new Random();

    @Override
    public Object execute(TransitionSystem ts, Unifier un, Term[] args) throws Exception {
        double max = 1.0;
        if (args.length == 2) {
            max = ((NumberTerm) args[0]).solve();
            max = Math.max(0.0, Math.min(1.0, max));
        } else if (args.length != 1) {
            throw new IllegalArgumentException("U expects 1 or 2 args");
        }

        double u;
        do {
            u = new Random().nextDouble() * max;
        } while (u == 0.0);

        return un.unifies(args[args.length - 1], ASSyntax.createNumber(u));
    }
}