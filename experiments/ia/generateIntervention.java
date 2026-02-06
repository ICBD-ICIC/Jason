package ia;

import arch.LlmBotAgArch;
import jason.architecture.AgArch;
import jason.asSemantics.DefaultInternalAction;
import jason.asSemantics.TransitionSystem;
import jason.asSemantics.Unifier;
import jason.asSyntax.StringTermImpl;
import jason.asSyntax.Term;

public class generateIntervention extends DefaultInternalAction {

    @Override
    public Object execute(TransitionSystem ts, Unifier un, Term[] args) throws Exception {
        AgArch arch = ts.getAgArch();
        if (!(arch instanceof LlmBotAgArch)) {
            throw new Exception("AgArch does not support interventions.");
        }

        LlmBotAgArch generator = (LlmBotAgArch) arch;
        Term conversation = args[0];

        String content = generator.generateIntervention(conversation);

        return un.unifies(args[1], new StringTermImpl(content));
    }
}
