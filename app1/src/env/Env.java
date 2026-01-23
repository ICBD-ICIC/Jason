package env;

import jason.asSyntax.*;
import static jason.asSyntax.ASSyntax.*;
import jason.environment.Environment;

import java.util.*;
import java.util.concurrent.atomic.AtomicInteger;
import java.util.concurrent.ConcurrentHashMap;

import lib.Translator;

public class Env extends Environment {

    /* -------- Social Network -------- */
    private static class Edge {
        private final String from;
        private final String to;
        private double weight;

        public Edge(String from, String to) {
            this(from, to, 1.0); // default weight
        }

        public Edge(String from, String to, double weight) {
            this.from = from;
            this.to = to;
            this.weight = weight;
        }

        public void updateWeight(double weight) {
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

    //TODO: search for a more efficient implementation, maybe a list per agent.
    private final List<Edge> socialNetwork = Collections.synchronizedList(new ArrayList<>());

    /* -------- Messages -------- */
    private static record Reaction(String author, String reaction){}

    private static class Message {
        private final int id;
        private final String author;
        private final String content;
        private List<Reaction> reactions = Collections.synchronizedList(new ArrayList<>());
        private final int original; // 0 = empty_reference
        private final long timestamp;

        public Message(int id, String author, String content) {
            this(id, author, content, 0);
        }

        public Message(int id, String author, String content, int original) {
            this.id = id;
            this.author = author;
            this.content = content;
            this.original = original;
            this.timestamp = System.currentTimeMillis();
        }

        public void addReaction(String author, String reaction) {
            this.reactions.add(new Reaction(author, reaction));
        }
    }

    //TODO: do we need them in string or we can keep them as terms? to see searchContent 
    private static record MessageCreationParams(List<String> topics, Map<String, String> variables){}

    private final Map<Integer, MessageCreationParams> content = new ConcurrentHashMap<>();
    private final Map<Integer, Message> filteredContent = new ConcurrentHashMap<>();
    private final AtomicInteger messageCounter = new AtomicInteger(0);

    //TODO: start from 0 and make the agents setup with actions on !start 
    //OR use the functions here
    @Override
    public void init(String[] args) {
        /* --- Social Network (Example SN) --- */
        socialNetwork.add(new Edge("alice","bob",8.5));
        socialNetwork.add(new Edge("bob","alice",4.0));
        socialNetwork.add(new Edge("bob","carol",9.8));
        socialNetwork.add(new Edge("carol","bob",5.0));
        socialNetwork.add(new Edge("carol","alice",7.3));

        addPercept("carol", createLiteral("follows", createString("alice")));
        addPercept("carol", createLiteral("follows", createString("bob")));
        addPercept("alice", createLiteral("followedBy", createString("carol")));

        // ------------------ Message 1 ------------------
        Message m1 = new Message(
            messageCounter.incrementAndGet(),
            "alice",
            "It's hard not to feel a sense of dread watching the climate crisis intensify. We have a shared responsibility to act and demand change. The time for denial is over. Let's face this challenge together."
        );
        m1.addReaction("bob", "like");
        m1.addReaction("carol", "love");

        MessageCreationParams params1 = new MessageCreationParams(
            List.of("climate_change", "awareness"),
            new HashMap(){{ 
                put("sentiment", "negative"); 
                put("toxicity", "0"); }}
        );

        content.put(m1.id, params1);
        filteredContent.put(m1.id, m1);

        // ------------------ Message 2 ------------------
        Message m2 = new Message(
            messageCounter.incrementAndGet(),
            "bob",
            "We cannot ignore or be indifferent to the climate crisis",
            m1.id
        );

        MessageCreationParams params2 = new MessageCreationParams(
            List.of("climate_change", "awareness"),
            new HashMap(){{ 
                put("sentiment", "negative"); 
                put("toxicity", "0"); }}
        );

        content.put(m2.id, params2);
        filteredContent.put(m2.id, m2);

        // ------------------ Message 3 ------------------
        Message m3 = new Message(
            messageCounter.incrementAndGet(),
            "carol",
            "10k followers FAST? Like & RT this, follow all LIKES and drop a YES below. #GrowthHacks"
        );

        MessageCreationParams params3 = new MessageCreationParams(
            List.of("audience_building"),
            new HashMap(){{ 
                put("sentiment", "positive"); 
                put("toxicity", "0"); 
                put("spam", "true"); }}
        );

        content.put(m3.id, params3);
        // not added to filteredContent because it is spam

        // ------------------ Environment ready ------------------
        System.out.println("Initialized " + content.size() + " messages, "
                        + filteredContent.size() + " passed moderation.");
    }

    @Override
    public boolean executeAction(String agent, Structure action) {
        System.out.println("ENV executing: " + action.getFunctor());
        switch (action.getFunctor()) {
            case "updateFeed" -> updateFeed(agent);
            case "searchContent" -> searchContent(agent, action);
            case "searchAuthor" -> searchAuthor(agent, action);
            case "createPost" -> createPost(agent, action);
            case "repost" -> repost(agent, action);
            case "comment" -> comment(agent, action);
            case "react" -> react(agent, action);
            case "createLink" -> createLink(agent, action);
            case "removeLink" -> removeLink(agent, action);
        /*      
            case "ask" -> ask(ag, act); Hacer una coleccion de esos datos en el ENV?
            case "readPublicProfile" -> readProfile(ag, act); Hacer una coleccion de esos datos en el ENV*/

            default -> System.out.println("Unknown action: "+action);
        }
        return true;
    }

    private boolean updateFeed(String agent){
        List<Message> feed = new ArrayList<>(filteredContent.values()); //TODO: implement proper recommendation algorithm
        updatePercepts(agent, feed);
        return true;
    }

    //TODO: random or ordered but limited to an amount
    private boolean searchContent(String agent, Structure action){
        String concept = action.getTerm(0).toString();
        List<Message> feed = new ArrayList<>(filteredContent.values());
        feed = feed.stream()
                    .filter(message -> {
                        MessageCreationParams params = content.get(message.id);
                        return params.topics().contains(concept);
                    }).toList(); //TODO: implement proper recommendation algorithm
        updatePercepts(agent, feed);
        return true;
    }
    
    private boolean searchAuthor(String agent, Structure action){
        String author = action.getTerm(0).toString();
        List<Message> feed = new ArrayList<>(filteredContent.values());
        feed = feed.stream()
                    .filter(message -> {
                        return message.author.equals(author);
                    }).toList(); //TODO: implement proper recommendation algorithm
        updatePercepts(agent, feed);
        return true;
    }

    private void updatePercepts(String agent, List<Message> messages){
        clearPercepts(agent);
        for (Message m : messages) {
            Literal literal = createLiteral("message",
                createNumber(m.id),
                createString(m.author),
                createString(m.content),
                createNumber(m.original),
                createNumber(m.timestamp)
            );
            addPercept(agent, literal);
            for (Reaction r : m.reactions) {
                Literal reactionLiteral = createLiteral("reaction",
                    createNumber(m.id),
                    createString(r.author),
                    createString(r.reaction)
                );
                addPercept(agent, reactionLiteral);
            }
        }
    }

    private boolean createPost(String agent, Structure action){
        List<String> topics = Translator.translateTopics(action.getTerm(0));
        Map<String, String> variables = Translator.translateVariables(action.getTerm(1));
        String messageContent = action.getTerm(2).toString();
        Message message = new Message(
            messageCounter.incrementAndGet(),
            agent,
            messageContent
        );
        MessageCreationParams params = new MessageCreationParams(topics, variables);
        addMessage(message, params);
        return true;
    }

    private boolean repost(String agent, Structure action){
        int originalId = Integer.parseInt(action.getTerm(0).toString());
        Message original = filteredContent.get(originalId);
        MessageCreationParams originalParams = content.get(originalId);
        Message repost = new Message(
            messageCounter.incrementAndGet(),
            agent,
            original.content,
            original.id
        );
        content.put(repost.id, originalParams);
        filteredContent.put(repost.id, repost);
        return true;
    }

    private boolean comment(String agent, Structure action){
        int originalId = Integer.parseInt(action.getTerm(0).toString());
        List<String> topics = Translator.translateTopics(action.getTerm(1));
        Map<String, String> variables = Translator.translateVariables(action.getTerm(2));
        String messageContent = action.getTerm(3).toString();
        Message message = new Message(
            messageCounter.incrementAndGet(),
            agent,
            messageContent,
            originalId
        );
        MessageCreationParams params = new MessageCreationParams(topics, variables);
        addMessage(message, params);
        return true;
    }

    private boolean react(String agent, Structure action){
        int originalId = Integer.parseInt(action.getTerm(0).toString());
        Message originalMessage = filteredContent.get(originalId);
        String reaction = action.getTerm(1).toString();
        originalMessage.addReaction(agent, reaction);
        return true;
    }

    private void addMessage(Message message, MessageCreationParams params) {
        content.put(message.id, params);
        if (passFilter(message, params)) {
            filteredContent.put(message.id, message);
        }
    }

    private boolean passFilter(Message message, MessageCreationParams params) {
        if (params.variables.containsKey("spam") && params.variables.get("spam").equals("true")) {
            return false;
        } else {
            return true;
        }
    }

    //TODO if already existis, return false?
    private boolean createLink(String agent, Structure action){
        String to = action.getTerm(0).toString();
        Edge link = new Edge(agent, to);
        socialNetwork.add(link);
        addPercept(agent, createLiteral("follows", createString(to)));
        addPercept(to, createLiteral("followedBy", createString(agent)));
        return true;
    }

    //TODO do something if link does not exist?
    private boolean removeLink(String agent, Structure action){
        String to = action.getTerm(0).toString();
        Edge target = new Edge(agent, to);
        synchronized (socialNetwork) {
            Iterator<Edge> it = socialNetwork.iterator();
            while (it.hasNext()) {
                Edge e = it.next();
                if (e.equals(target)) {
                    it.remove();
                    removePercept(agent, createLiteral("follows", createString(to)));
                    removePercept(to, createLiteral("followedBy", createString(agent)));
                    break;
                }
            }
        }
        return true;
    }
}
