package ia;

import arch.LlmAgArch;
import jason.architecture.AgArch;
import jason.asSemantics.DefaultInternalAction;
import jason.asSemantics.TransitionSystem;
import jason.asSemantics.Unifier;
import jason.asSyntax.StringTermImpl;
import jason.asSyntax.Term;

public class generate extends DefaultInternalAction {

    @Override
    public Object execute(TransitionSystem ts, Unifier un, Term[] args) throws Exception {
        AgArch arch = ts.getAgArch();
        if (!(arch instanceof LlmAgArch)) {
            throw new Exception("AgArch does not support content generation.");
        }

        LlmAgArch generator = (LlmAgArch) arch;
        String content;

        if (args.length == 3) {
            Term topics = args[0];
            Term variables = args[1];
            content = generator.createContent(topics, variables);
        } else if (args.length == 5) {
            Term interpretations = args[0];
            Term originalContent = args[1];
            Term topics = args[2];
            Term variables = args[3];
            content = generator.createContent(interpretations, originalContent, topics, variables);
        } else {
            throw new Exception("Invalid number of arguments.");
        }

        return un.unifies(args[args.length - 1], new StringTermImpl(content));
    }
}
