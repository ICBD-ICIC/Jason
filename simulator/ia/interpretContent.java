package ia;

import arch.SocialAgArch;
import jason.architecture.AgArch;
import jason.asSemantics.DefaultInternalAction;
import jason.asSemantics.TransitionSystem;
import jason.asSemantics.Unifier;
import jason.asSyntax.Term;
import java.util.Map;

import lib.JavaToJasonTranslator;
import java.util.logging.Logger;

public class interpretContent extends DefaultInternalAction {

    @Override
    public Object execute(TransitionSystem ts, Unifier un, Term[] args) throws Exception {
        AgArch arch = ts.getAgArch();
        if (!(arch instanceof SocialAgArch)) {
            throw new Exception("Agent does not have a SocialAgArch architecture.");
        }

        Term content = args[0];
        SocialAgArch socialArch = (SocialAgArch) arch;

        try {
            Map<String, Object> interpretation = socialArch.interpretContent(content);
            Term term = JavaToJasonTranslator.translateVariables(interpretation);
            return un.unifies(args[1], term);
        } catch (Exception e) {
            ts.getLogger().severe("interpretContent failed: " + e.getMessage());
            for (StackTraceElement el : e.getStackTrace()) {
                ts.getLogger().severe(el.toString());
            }
            throw e;
        }
    }
}