package env;

import jason.asSyntax.*;
import static jason.asSyntax.ASSyntax.*;
import jason.environment.Environment;

import java.util.*;

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
    }

    private final List<Edge> socialNetwork = new ArrayList<>();

    /* -------- Messages -------- */
    private static record Reaction(String author, String reaction){}

    private static class Message {
        private final int id;
        private final String author;
        private final String content;
        private List<Reaction> reactions = new ArrayList<>();
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

    private static record MessageCreationParams(List<String> topics, Map<String, String> variables){}

    private final Map<Integer, MessageCreationParams> content = new HashMap<>();
    private final Set<Message> filteredContent = new HashSet<>();

    @Override
    public void init(String[] args) {
        /* --- Social Network (Example SN) --- */
        socialNetwork.add(new Edge("alice","bob",8.5));
        socialNetwork.add(new Edge("bob","alice",4.0));
        socialNetwork.add(new Edge("bob","carol",9.8));
        socialNetwork.add(new Edge("carol","bob",5.0));
        socialNetwork.add(new Edge("carol","alice",7.3));

        // ------------------ Message 1 ------------------
        Message m1 = new Message(
            101,
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
        filteredContent.add(m1);

        // ------------------ Message 2 ------------------
        Message m2 = new Message(
            107,
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
        filteredContent.add(m2);

        // ------------------ Message 3 ------------------
        Message m3 = new Message(
            120,
            "carol",
            "10k followers FAST? Like & RT this, follow all LIKES and drop a YES below. #GrowthHacks"
        );

        MessageCreationParams params3 = new MessageCreationParams(
            List.of("audience_building"),
            new HashMap(){{ 
                put("sentiment", "positive"); 
                put("toxicity", "0"); 
                put("spam", "True"); }}
        );

        content.put(m3.id, params3);
        // not added to filteredContent because it is spam

        // ------------------ Environment ready ------------------
        System.out.println("Initialized " + content.size() + " messages, "
                        + filteredContent.size() + " passed moderation.");
    }

    @Override
    public boolean executeAction(String agent, Structure action) {
        try {
            switch (action.getFunctor()) {
                case "updateFeed" -> updateFeed(agent);
                case "searchContent" -> searchContent(agent, action);
                case "searchAuthor" -> searchAuthor(agent, action);
                // CUANDO BUSCA ALGO, asocia ese mensaje a eso que busco
                case "createPost" -> createPost(agent, action);
           /*      
                case "search_content" -> searchContent(ag, act.getTerm(0).toString());
                case "search_author" -> searchAuthor(ag, act.getTerm(0).toString());
                case "create_post" -> createPost(ag, act);
                case "repost" -> repost(ag, act);
                case "comment" -> comment(ag, act);
                case "react" -> react(ag, act);
                case "ask" -> ask(ag, act);
                case "createLink" -> createLink(ag, act);
                case "removeLink" -> removeLink(ag, act);
                case "readPublicProfile" -> readProfile(ag, act); */

                default -> System.out.println("Unknown action: "+action);
            }
        } catch (Exception e) {
            e.printStackTrace();
        }
        return true;
    }

    private boolean updateFeed(String agent){
        List<Message> feed = new ArrayList<>(filteredContent); //TODO: implement proper recommendation algorithm
        updatePercepts(agent, feed);
        return true;
    }

    private boolean searchContent(String agent, Structure action){
        String concept = action.getTerm(0).toString();
        List<Message> feed = filteredContent.stream()
            .filter(message -> {
                MessageCreationParams params = content.get(message.id);
                return params.topics().contains(concept);
            }).toList(); //TODO: implement proper recommendation algorithm
        updatePercepts(agent, feed);
        return true;
    }
    
    private boolean searchAuthor(String agent, Structure action){
        String author = action.getTerm(0).toString();
        List<Message> feed = filteredContent.stream()
            .filter(message -> {
                return message.author.equals(author);
            }).toList(); //TODO: implement proper recommendation algorithm
        System.out.print(feed);
        updatePercepts(agent, feed);
        return true;
    }

    private void updatePercepts(String agent, List<Message> messages){
        //TODO: verify if I need to swipe the percepts.
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
        String messageContent = Llm.createContent(topics, variables);
        Message message = new Message(
            content.size() + 1,
            agent,
            messageContent
        );
        MessageCreationParams params = new MessageCreationParams(topics, variables);
        addMessage(message, params);
        return true;
    }

    private void addMessage(Message message, MessageCreationParams params) {
        content.put(message.id, params);
        if (passFilter(message, params)) {
            filteredContent.add(message);
        }
    }

    private boolean passFilter(Message message, MessageCreationParams params) {
        if (params.variables.containsKey("spam") && params.variables.get("spam").equals("true")) {
            return false;
        } else {
            return true;
        }
    }
}
