package ia;

import arch.LlmAgArch;
import jason.architecture.AgArch;
import jason.asSemantics.DefaultInternalAction;
import jason.asSemantics.TransitionSystem;
import jason.asSemantics.Unifier;
import jason.asSyntax.NumberTermImpl;
import jason.asSyntax.Term;

public class affectivity extends DefaultInternalAction {

    @Override
    public Object execute(TransitionSystem ts, Unifier un, Term[] args) throws Exception {
        AgArch arch = ts.getAgArch();
        if (!(arch instanceof LlmAgArch)) {
            throw new Exception("AgArch does not support affectivity calculation.");
        }

        LlmAgArch llm = (LlmAgArch) arch;

         Term affectivityType;
        Term group;
        Term current = null;
        Term politicalStandpoint;
        Term demographics;
        Term personaDescription;
        Term content = null;
        Term result;

        if (args.length == 6) {
            // initiation: no current, no content
            affectivityType     = args[0];
            group               = args[1];
            politicalStandpoint = args[2];
            demographics        = args[3];
            personaDescription  = args[4];
            result              = args[5];

        } else if (args.length == 8) {
            // update: with current and content
            affectivityType     = args[0];
            group               = args[1];
            current             = args[2];
            politicalStandpoint = args[3];
            demographics        = args[4];
            personaDescription  = args[5];
            content             = args[6];
            result              = args[7];

        } else {
            throw new Exception(
                "Invalid number of arguments. Expected:\n" +
                "  affectivity(Type, Group, Political, Demographics, Persona, Result)\n" +
                "or\n" +
                "  affectivity(Type, Group, Current, Political, Demographics, Persona, Content, Result)"
            );
        }

        int newAffectivity = llm.affectivity(
            affectivityType,
            group,
            current,
            politicalStandpoint,
            demographics,
            personaDescription,
            content
        );
        
        return un.unifies(result, new NumberTermImpl(newAffectivity));
    }
}