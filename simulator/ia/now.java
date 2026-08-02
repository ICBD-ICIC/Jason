package ia;

import jason.asSemantics.*;
import jason.asSyntax.*;

public class now extends DefaultInternalAction {
    @Override
    public Object execute(TransitionSystem ts, Unifier un, Term[] args) throws Exception {
        NumberTerm t = ASSyntax.createNumber(System.currentTimeMillis());
        return un.unifies(args[0], t);
    }
}