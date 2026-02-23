package env;

import jason.asSyntax.*;
import static jason.asSyntax.ASSyntax.*;
import jason.environment.Environment;

import java.util.*;
import java.util.concurrent.atomic.AtomicInteger;
import java.util.concurrent.ConcurrentHashMap;

import lib.JasonToJavaTranslator;
import env.Message;
import env.ContentManager;

public class Env extends Environment {
    private static class Edge {
        private static final double DEFAULT_WEIGHT = 1.0;

        private final String from;
        private final String to;
        private double weight;

        private Edge(String from, String to) {
            this(from, to, DEFAULT_WEIGHT);
        }

        private Edge(String from, String to, double weight) {
            this.from = from;
            this.to = to;
            this.weight = weight;
        }

        private void updateWeight(double weight) {
            this.weight = weight;
        }

        @Override
        public boolean equals(Object obj) { 
            if (this == obj) return true;
            if (obj == null || getClass() != obj.getClass()) return false;
            Edge edge = (Edge) obj;
            return from.equals(edge.from) && to.equals(edge.to);
        }
    }

    private final Set<Edge> socialNetwork = Collections.synchronizedSet(new HashSet<>());
    private final ContentManager contentManager = new DefaultContentManager();

    @Override
    public void init(String[] args) {
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
            //case "ask" -> ask(agent, action);
            case "createLink" -> createLink(agent, action);
            case "removeLink" -> removeLink(agent, action);
            //case "readPublicProfile" -> readPublicProfile(agent, action);
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

        List<Term> ids = new ArrayList<>();

        for (Message m : messages) {
            ids.add(createNumber(m.id));

            Literal literal = createLiteral("message",
                createNumber(m.id),
                createString(m.author),
                createString(m.content),
                createNumber(m.original),
                createNumber(m.timestamp)
            );
            addPercept(agent, literal);
            for (Message.Reaction r : m.reactions) { 
                Literal reactionLiteral = createLiteral("reaction",
                    createNumber(m.id),
                    createString(r.author()), 
                    createString(r.reaction())
                );
                addPercept(agent, reactionLiteral);
            }
        }
        Literal feedOrder = createLiteral("feed_order", createList(ids));
        addPercept(agent, feedOrder);
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
/*         String to = action.getTerm(0).toString();
        Edge link = new Edge(agent, to);
        socialNetwork.add(link);
        addPercept(agent, createLiteral("follows", createString(to)));
        addPercept(to, createLiteral("followedBy", createString(agent))); */
        return true;
    }

    private boolean removeLink(String agent, Structure action){
/*         String to = action.getTerm(0).toString();
        Edge target = new Edge(agent, to);
        synchronized (socialNetwork) {
            if (socialNetwork.remove(target)) {
                removePercept(agent, createLiteral("follows", createString(to)));
                removePercept(to, createLiteral("followedBy", createString(agent)));
            }
        } */
        return true;
    }
}
