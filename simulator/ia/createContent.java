package ia;

import arch.SocialAgArch;
import jason.architecture.AgArch;
import jason.asSemantics.DefaultInternalAction;
import jason.asSemantics.TransitionSystem;
import jason.asSemantics.Unifier;
import jason.asSyntax.StringTermImpl;
import jason.asSyntax.Term;

public class createContent extends DefaultInternalAction {

    @Override
    public Object execute(TransitionSystem ts, Unifier un, Term[] args) throws Exception {
        AgArch arch = ts.getAgArch();
        if (!(arch instanceof SocialAgArch)) {
            throw new Exception("Agent does not have a SocialAgArch architecture.");
        }

        SocialAgArch socialArch = (SocialAgArch) arch;
        String content;

        if (args.length == 3) {
            Term topics = args[0];
            Term variables = args[1];
            content = socialArch.createContent(topics, variables);
        } else {
            throw new Exception("Invalid number of arguments.");
        }

        return un.unifies(args[2], new StringTermImpl(content));
    }
}
