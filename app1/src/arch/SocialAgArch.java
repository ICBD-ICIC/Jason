package arch;

import jason.architecture.AgArch;
import jason.asSyntax.*;
import static jason.asSyntax.ASSyntax.*;

import java.util.ArrayList;
import java.util.List;
import java.util.Collection;
import java.util.*;

import lib.Translator;

//TODO: if we use gemini, change the class name
public class SocialAgArch extends AgArch {

    @Override
    public boolean act(Literal action) {
        try {
            switch (action.getFunctor()) {
                case "createPost" -> {
                    List<String> topics = Translator.translateTopics(action.getTerm(0));
                    Map<String, String> variables = Translator.translateVariables(action.getTerm(1));
                    
                    String content = Llm.createContent(topics, variables);

                    Structure envAction = createStructure(
                        "createPost",
                        action.getTerm(0),
                        action.getTerm(1),
                        createString(content)  // pass content to env
                    );

                    // Send the action to the environment
                    act(envAction);
                    return true;
                }

                //entiendo que el comment tiene que tener o el contenido original, o las variables interpretadas
                /* case "comment" -> {
                    // Action structure: comment(OriginalId, TopicsList, VariablesMap)
                    int originalId = Integer.parseInt(action.getTerm(0).toString());
                    Term topicsTerm = action.getTerm(1);
                    Term varsTerm = action.getTerm(2);

                    List<String> topics = Translator.translateTopics(topicsTerm);
                    var variables = Translator.translateVariables(varsTerm);

                    // Retrieve original content if needed
                    String originalContent = ""; // could be percepts or another agent function
                    for (Literal p : getAllPercepts()) {
                        if (p.getFunctor().equals("message") && 
                            Integer.parseInt(p.getTerm(0).toString()) == originalId) {
                            originalContent = p.getTerm(2).toString();
                            break;
                        }
                    }

                    // Generate comment content
                    String content = Llm.createContent(originalContent, topics, variables);

                    // Build the action literal with content included
                    Structure envAction = ASSyntax.createStructure(
                        "comment",
                        createNumber(originalId),
                        topicsTerm,
                        varsTerm,
                        createString(content) // pass content to env
                    );

                    // Send the action to the environment
                    getTS().getAg().getEnvironment().executeAction(getAgName(), envAction);
                    return true;
                }

                // Other actions can be forwarded as-is
                default -> {
                    getTS().getAg().getEnvironment().executeAction(getAgName(), action);
                    return true;
                } */
            }

        } catch (Exception e) {
            e.printStackTrace();
            return false;
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
