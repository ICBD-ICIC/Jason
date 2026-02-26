package env;

import jason.asSyntax.*;
import static jason.asSyntax.ASSyntax.*;
import jason.environment.Environment;

import java.util.*;
import java.util.concurrent.atomic.AtomicInteger;
import java.util.concurrent.ConcurrentHashMap;

import lib.JasonToJavaTranslator;
import initializer.MessageLoader;

public class Env extends Environment {
    
    private final NetworkManager networkManager = new NetworkManager();
    private final ContentManager contentManager = new DefaultContentManager(networkManager);
    private final KnowledgeManager knowledgeManager = new DefaultKnowledgeManager();

    @Override
    public void init(String[] args) {
        try {
            MessageLoader.load(contentManager);
        } catch (Exception e) {
            throw new RuntimeException("Failed to load messages: " + e.getMessage(), e);
        }
    }

    @Override
    public boolean executeAction(String agent, Structure action) {
        switch (action.getFunctor()) {
            case "updateFeed" -> updateFeed(agent);
            case "searchContent" -> searchContent(agent, action);
            case "searchAuthor" -> searchAuthor(agent, action);
            case "createPost" -> createPost(agent, action);
            case "repost" -> repost(agent, action);
            case "comment" -> comment(agent, action);
            case "react" -> react(agent, action);
            case "ask" -> ask(agent, action);
            case "createLink" -> createLink(agent, action);
            case "removeLink" -> removeLink(agent, action);
            case "readPublicProfile" -> readPublicProfile(agent, action);
            default -> System.out.println("Unknown action: "+action);
        }
        return true;
    }

    private boolean updateFeed(String agent){
        List<Message> feed = contentManager.feedFilter(agent);
        updatePercepts(agent, feed);
        return true;
    }

    private boolean searchContent(String agent, Structure action){
        String concept = action.getTerm(0).toString();
        List<Message> feed = contentManager.topicFilter(agent, concept);
        updatePercepts(agent, feed);
        return true;
    }
    
    private boolean searchAuthor(String agent, Structure action){
        String author = action.getTerm(0).toString();
        List<Message> feed = contentManager.authorFilter(agent, author);
        updatePercepts(agent, feed);
        return true;
    }
    
    private void updatePercepts(String agent, List<Message> messages){
        clearPercepts(agent);

        messages.forEach(m -> {
            addPercept(agent, createLiteral("message",
                createNumber(m.id),
                createString(m.author),
                createString(m.content),
                createNumber(m.original),
                createNumber(m.timestamp)
            ));
            m.reactions.forEach(r -> addPercept(agent, createLiteral("reaction",
                createNumber(m.id),
                createString(r.author()),
                createString(r.reaction())
            )));
        });

        List<Term> ids = messages.stream()
            .map(m -> (Term) createNumber(m.id))
            .toList();
        addPercept(agent, createLiteral("feed_order", createList(ids)));
    }

    private boolean createPost(String agent, Structure action){
        List<String> topics = JasonToJavaTranslator.translateTopics(action.getTerm(0));
        Map<String, Object> variables = JasonToJavaTranslator.translateVariables(action.getTerm(1));
        String messageContent = action.getTerm(2).toString();
        contentManager.addMessage(agent, messageContent, topics, variables);
        return true;
    }

    private boolean repost(String agent, Structure action){
        int originalId = Integer.parseInt(action.getTerm(0).toString());
        contentManager.repost(agent, originalId);
        return true;
    }

    private boolean comment(String agent, Structure action){
        int originalId = Integer.parseInt(action.getTerm(0).toString());
        List<String> topics = JasonToJavaTranslator.translateTopics(action.getTerm(1));
        Map<String, Object> variables = JasonToJavaTranslator.translateVariables(action.getTerm(2));
        String messageContent = action.getTerm(3).toString();
        contentManager.addMessage(agent, messageContent, topics, variables, originalId);
        return true;
    }

    private boolean react(String agent, Structure action){
        int originalId = Integer.parseInt(action.getTerm(0).toString());
        String reaction = action.getTerm(1).toString();
        contentManager.addReaction(originalId, agent, reaction);
        return true;
    }

    private boolean createLink(String agent, Structure action){
        String to = action.getTerm(0).toString();
        networkManager.addEdge(agent, to);
        addPercept(agent, createLiteral("follows", createString(to)));
        addPercept(to, createLiteral("followedBy", createString(agent)));
        return true;
    }

    private boolean removeLink(String agent, Structure action){
        String to = action.getTerm(0).toString();
        networkManager.removeEdge(agent, to);
        removePercept(agent, createLiteral("follows", createString(to)));
        removePercept(to, createLiteral("followedBy", createString(agent)));
        return true;
    }

    private boolean ask(String agent, Structure action){
        String query = action.getTerm(0).toString();
        Object result = knowledgeManager.query(agent, query);
        // TODO: convert result to percepts
        return true;
    }

    private boolean readPublicProfile(String agent, Structure action){
        String requestedAgent = action.getTerm(0).toString();
        // TODO
        return true;
    }
}
