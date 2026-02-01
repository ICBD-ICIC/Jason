package ia;

import arch.LlmAgArch;
import jason.architecture.AgArch;
import jason.asSemantics.DefaultInternalAction;
import jason.asSemantics.TransitionSystem;
import jason.asSemantics.Unifier;
import jason.asSyntax.NumberTermImpl;
import jason.asSyntax.Term;

public class initiateAffectivity extends DefaultInternalAction {

    @Override
    public Object execute(TransitionSystem ts, Unifier un, Term[] args) throws Exception {
        AgArch arch = ts.getAgArch();
        if (!(arch instanceof LlmAgArch)) {
            throw new Exception("AgArch does not support affectivity initialization.");
        }

        String affectivity = args[0].toString();
        Term group = args[1];
        Term politicalStandpoint = args[2];
        Term demographics = args[3];
        Term personaDescription = args[4];

        LlmAgArch llm = (LlmAgArch) arch;

        int newAffectivity; 

        switch(affectivity) {
            case "love": 
                newAffectivity = llm.initiateLove(group, politicalStandpoint, demographics, personaDescription);
                break;
            case "hate": 
                newAffectivity = llm.initiateHate(group, politicalStandpoint, demographics, personaDescription);
                break;
            default: 
                throw new Exception("Affectivity type not supported.");
        }
        
        return un.unifies(args[5], new NumberTermImpl(newAffectivity));
    }
}