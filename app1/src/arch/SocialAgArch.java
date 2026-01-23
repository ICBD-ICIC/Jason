package arch;

import jason.architecture.AgArch;
import jason.asSyntax.*;
import static jason.asSyntax.ASSyntax.*;

import java.util.ArrayList;
import java.util.List;
import java.util.Collection;
import java.util.*;

import jason.asSemantics.ActionExec;

import lib.Translator;

//TODO: if we use gemini, change the class name
public class SocialAgArch extends AgArch {

    @Override
    public void act(ActionExec actionExec) {
        Structure action = actionExec.getActionTerm();
        switch (action.getFunctor()) {
            case "createPost" -> {
                Term topics = action.getTerm(0);
                Term variables = action.getTerm(1);
                
                String content = Llm.createContent(topics, variables);

                Structure envAction = createStructure(
                    "createPost",
                    topics,
                    variables,
                    createString(content)
                );
                ActionExec envActionExec = new ActionExec(envAction, actionExec.getIntention());
                super.act(envActionExec);
            }
            case "comment" -> {
                Term originalId = action.getTerm(0);
                Term interpretations = action.getTerm(1);
                Term originalContent = action.getTerm(2);
                Term topics = action.getTerm(3);
                Term variables = action.getTerm(4);
                
                String content = Llm.createContent(interpretations, originalContent, topics, variables);

                Structure envAction = createStructure(
                    "comment",
                    originalId,
                    topics,
                    variables,
                    createString(content)
                );
                ActionExec envActionExec = new ActionExec(envAction, actionExec.getIntention());
                super.act(envActionExec);
            }
            default -> super.act(actionExec);
        }
    }

    @Override
    public List<Literal> perceive() {
        Collection<Literal> percepts = super.perceive();
        if (percepts == null) {
            percepts = List.of(); // no percepts this cycle
        }
        List<Literal> allPercepts = new ArrayList<>();
        for (Literal p : percepts) {
            allPercepts.add(p);
            if (p.getFunctor().equals("message")) {
                int id = Integer.parseInt(p.getTerm(0).toString());
                String content = p.getTerm(2).toString();
                allPercepts.addAll(interpret(id, content));
            }
        }
        System.out.print("\n" + allPercepts + "\n");
        return allPercepts;
    }

    //TODO: if it is a message from the agent, shouldn't the t and v be the originals?
    private List<Literal> interpret(int id, String content) {
        List<Literal> derived = new ArrayList<>();
        String sentiment = sentiment(content);
        boolean spam = isSpam(content);

        Term sentimentTerm = createLiteral("sentiment", createString(sentiment));
        Literal sentimentInterpretation = createLiteral("interpretation", createNumber(id), sentimentTerm);
        derived.add(sentimentInterpretation);

        Term spamTerm = createLiteral("spam", createAtom(Boolean.toString(spam)));
        Literal spamInterpretation = createLiteral("interpretation", createNumber(id), spamTerm);
        derived.add(spamInterpretation);

        return derived;
    }

    //TODO: use LLM to calculate this
    private String sentiment(String text) {
        return "positive";
    }

    //TODO: use LLM to calculate this
    private boolean isSpam(String text) {
        return false;
    }
}
