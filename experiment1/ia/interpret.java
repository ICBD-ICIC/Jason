package ia;

import jason.asSemantics.DefaultInternalAction;
import jason.asSemantics.TransitionSystem;
import jason.asSemantics.Unifier;
import jason.asSyntax.StringTermImpl;
import jason.asSyntax.Term;

public class interpret extends DefaultInternalAction {

    @Override
    public Object execute(TransitionSystem ts, Unifier un, Term[] args) throws Exception {
        // args[0] = C (input)
        // args[1] = Interpretation (output)

        //ts.getUserAgArch()
        /*
        if (arch instanceof MyAgArch) {
    MyAgArch myArch = (MyAgArch) arch;
    myArch.myCustomMethod(...); <- para usar el LLM
} */

        String interpretation = "hola";

        // Unify the output argument
        return un.unifies(args[1], new StringTermImpl(interpretation));
    }
}
