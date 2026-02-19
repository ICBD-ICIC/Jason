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

    private static record MessageCreationParams(List<String> topics, Map<String, Object> variables){}

    private final Map<Integer, MessageCreationParams> content = new ConcurrentHashMap<>();
    private final Map<Integer, Message> filteredContent = new ConcurrentHashMap<>();
    private final AtomicInteger messageCounter = new AtomicInteger(0);

    @Override
    public void init(String[] args) {
        addMessage(
            new Message(
                messageCounter.incrementAndGet(),
                "Joe Biden", 
                "If we don't take urgent action to address the climate emergency, our planet may never recover. We must get the climate change denier out of the White House and tackle this crisis head-on."
            ), 
            new MessageCreationParams(new ArrayList<>(), new HashMap<>())
        );
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
            case "createLink" -> createLink(agent, action);
            case "removeLink" -> removeLink(agent, action);
            default -> System.out.println("Unknown action: "+action);
        }
        return true;
    }

    private boolean updateFeed(String agent){
        List<Message> feed = new ArrayList<>(filteredContent.values());
        feed.sort((m1, m2) -> Long.compare(m2.timestamp, m1.timestamp));
        updatePercepts(agent, feed);
        return true;
    }

    private boolean searchContent(String agent, Structure action){
        String concept = action.getTerm(0).toString();
        List<Message> feed = new ArrayList<>(filteredContent.values());
        feed = feed.stream()
                    .filter(message -> {
                        MessageCreationParams params = content.get(message.id);
                        return params.topics().contains(concept);
                    }).toList();
        feed.sort((m1, m2) -> Long.compare(m2.timestamp, m1.timestamp));
        updatePercepts(agent, feed);
        return true;
    }
    
    private boolean searchAuthor(String agent, Structure action){
        String author = action.getTerm(0).toString();
        List<Message> feed = new ArrayList<>(filteredContent.values());
        feed = feed.stream()
                    .filter(message -> {
                        return message.author.equals(author);
                    }).toList();
        feed.sort((m1, m2) -> Long.compare(m2.timestamp, m1.timestamp));
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
            for (Reaction r : m.reactions) {
                Literal reactionLiteral = createLiteral("reaction",
                    createNumber(m.id),
                    createString(r.author),
                    createString(r.reaction)
                );
                addPercept(agent, reactionLiteral);
            }
        }
        Literal feedOrder = createLiteral("feed_order", createList(ids));
        addPercept(agent, feedOrder);
    }

    private boolean createPost(String agent, Structure action){
        List<String> topics = Translator.translateTopics(action.getTerm(0));
        Map<String, Object> variables = Translator.translateVariables(action.getTerm(1));
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
        Map<String, Object> variables = Translator.translateVariables(action.getTerm(2));
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
        return true;
    }

    private boolean createLink(String agent, Structure action){
        String to = action.getTerm(0).toString();
        Edge link = new Edge(agent, to);
        socialNetwork.add(link);
        addPercept(agent, createLiteral("follows", createString(to)));
        addPercept(to, createLiteral("followedBy", createString(agent)));
        return true;
    }

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
