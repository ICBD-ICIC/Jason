package env;

import java.util.List;
import java.util.Map;

public class VisualMessage {
    public final int id;
    public final String author;
    public final String content;
    public final List<Message.Reaction> reactions;
    public final int original;
    public final long timestamp;

    public final List<String> topics;
    public final Map<String, Object> variables;

    public VisualMessage(Message message, ContentManager.MessageCreationParams params) {
        this.id = message.id;
        this.author = message.author;
        this.content = message.content;
        this.reactions = List.copyOf(message.reactions);
        this.original = message.original;
        this.timestamp = message.timestamp;

        this.topics = params.topics();
        this.variables = params.variables();
    }
}