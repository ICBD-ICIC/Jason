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
        String group = args[1].toString();
        String current = args[2].toString();
        String politicalStandpoint = args[3].toString();
        String demographics = args[4].toString();
        String personaDescription = args[5].toString();
        String content = args[6].toString();

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