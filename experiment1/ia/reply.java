package ia;

import arch.LlmAgArch;
import jason.architecture.AgArch;
import jason.asSemantics.DefaultInternalAction;
import jason.asSemantics.TransitionSystem;
import jason.asSemantics.Unifier;
import jason.asSyntax.StringTermImpl;
import jason.asSyntax.Term;

public class reply extends DefaultInternalAction {

    @Override
    public Object execute(TransitionSystem ts, Unifier un, Term[] args) throws Exception {
        AgArch arch = ts.getAgArch();
        if (!(arch instanceof LlmAgArch)) {
            throw new Exception("AgArch does not support replies.");
        }

        LlmAgArch generator = (LlmAgArch) arch;

        Term politicalStandpoint = args[0];
        Term demographics = args[1];
        Term personaDescription = args[2];
        Term conversation = args[3];

        String content = generator.reply(politicalStandpoint, demographics, personaDescription, conversation);

        return un.unifies(args[4], new StringTermImpl(content));
    }
}
