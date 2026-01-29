package ia;

import arch.LlmAgArch;
import jason.architecture.AgArch;
import jason.asSemantics.DefaultInternalAction;
import jason.asSemantics.TransitionSystem;
import jason.asSemantics.Unifier;
import jason.asSyntax.NumberTermImpl;
import jason.asSyntax.Term;

public class updateAffectivity extends DefaultInternalAction {

    @Override
    public Object execute(TransitionSystem ts, Unifier un, Term[] args) throws Exception {
        AgArch arch = ts.getAgArch();
        if (!(arch instanceof LlmAgArch)) {
            throw new Exception("AgArch does not support affectivity updates.");
        }

        String affectivity = args[0].toString();
        Term group = args[1];
        Term current = args[2];
        Term politicalStandpoint = args[3];
        Term demographics = args[4];
        Term personaDescription = args[5];
        Term content = args[6];

        LlmAgArch llm = (LlmAgArch) arch;

        int newAffectivity; 

        switch(affectivity) {
            case "love": 
                newAffectivity = llm.updateLove(group, current, politicalStandpoint, demographics, personaDescription, content);
                break;
            case "hate": 
                newAffectivity = llm.updateHate(group, current, politicalStandpoint, demographics, personaDescription, content);
                break;
            default: 
                throw new Exception("Affectivity type not supported.");
        }
        
        return un.unifies(args[7], new NumberTermImpl(newAffectivity));
    }
}