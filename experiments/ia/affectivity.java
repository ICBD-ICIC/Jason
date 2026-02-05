package ia;

import arch.LlmAgArch;
import jason.architecture.AgArch;
import jason.asSemantics.*;
import jason.asSyntax.*;

public class affectivity extends DefaultInternalAction {

    @Override
    public Object execute(TransitionSystem ts, Unifier un, Term[] args ) throws Exception {
        AgArch arch = ts.getAgArch();
        if (!(arch instanceof LlmAgArch)) {
            throw new Exception("AgArch does not support affectivity.");
        }

        Term currentAffect = null;
        Term context;
        Term content = null;
        Term outputAffect;

        if (args.length == 2) {
            // initialization
            context       = args[0];
            outputAffect  = args[1];

        } else if (args.length == 4) {
            // update
            currentAffect = args[0];
            context       = args[1];
            content       = args[2];
            outputAffect  = args[3];

        } else {
            throw new Exception(
                "Usage:\n" +
                "  ia.affectivity(Context, NewAffect)\n" +
                "  ia.affectivity(Current, Context, Content, NewAffect)"
            );
        }

        LlmAgArch llm = (LlmAgArch) arch;

        Term result = llm.affectivity(
            currentAffect,
            context,
            content
        );

        return un.unifies(outputAffect, result);
    }
}
