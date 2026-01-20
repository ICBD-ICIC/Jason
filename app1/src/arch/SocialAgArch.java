package arch;

import jason.architecture.AgArch;
import jason.asSyntax.*;
import static jason.asSyntax.ASSyntax.*;

import java.util.ArrayList;
import java.util.List;
import java.util.Collection;

//TODO: if we use gemini, change the class name
public class SocialAgArch extends AgArch {

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

    /**
     * Generate multiple percepts derived from a message
     */
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

//y si guardo en la arquitectura los percepts, y cuando haga act de updatefeed o similar, le borro los mensajes? 