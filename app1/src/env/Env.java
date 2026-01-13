package env;

import jason.asSyntax.*;
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
        private final Message original; // null = empty_reference
        private final long timestamp;

        public Message(int id, String author, String content, Message original) {
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
            "It's hard not to feel a sense of dread watching the climate crisis intensify. We have a shared responsibility to act and demand change. The time for denial is over. Let's face this challenge together.",
            null
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
            m1
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
            "10k followers FAST? Like & RT this, follow all LIKES and drop a YES below. #GrowthHacks",
            null
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
}
