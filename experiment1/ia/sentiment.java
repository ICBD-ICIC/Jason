package ia;

import arch.LlmAgArch;
import jason.architecture.AgArch;
import jason.asSemantics.DefaultInternalAction;
import jason.asSemantics.TransitionSystem;
import jason.asSemantics.Unifier;
import jason.asSyntax.StringTermImpl;
import jason.asSyntax.Term;

public class sentiment extends DefaultInternalAction {

    @Override
    public Object execute(TransitionSystem ts, Unifier un, Term[] args) throws Exception {
        AgArch arch = ts.getAgArch();
        if (!(arch instanceof LlmAgArch)) {
            throw new Exception("AgArch does not support sentiment calculation.");
        }

        String content = args[0].toString();
        LlmAgArch generator = (LlmAgArch) arch;
        String sentiment = generator.sentiment(content);
        
        return un.unifies(args[1], new StringTermImpl(sentiment));
    }
}