package env;

import java.util.*;

public class Message {

    public static record Reaction(String author, String reaction) {}

    public static final int EMPTY_REFERENCE = 0;

    public final int id;
    public final String author;
    public final String content;
    public final List<Reaction> reactions = Collections.synchronizedList(new ArrayList<>());
    public final int original;
    public final long timestamp;

    public Message(int id, String author, String content) {
        this(id, author, content, EMPTY_REFERENCE);
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