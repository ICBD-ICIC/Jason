package ia;

import arch.SocialAgArch;
import jason.architecture.AgArch;
import jason.asSemantics.DefaultInternalAction;
import jason.asSemantics.TransitionSystem;
import jason.asSemantics.Unifier;
import jason.asSyntax.StringTermImpl;
import jason.asSyntax.Term;
import java.util.Map;

import lib.JavaToJasonTranslator;

public class interpretContent extends DefaultInternalAction {

    @Override
    public Object execute(TransitionSystem ts, Unifier un, Term[] args) throws Exception {
        AgArch arch = ts.getAgArch();
        if (!(arch instanceof SocialAgArch)) {
            throw new Exception("Agent does not have a SocialAgArch architecture.");
        }

        Term content = args[0];
        SocialAgArch socialArch = (SocialAgArch) arch;
        Map<String, Object> interpretation = socialArch.interpretContent(content);
        
        Term term = JavaToJasonTranslator.translateVariables(interpretation);
        return un.unifies(args[1], term);
    }
}