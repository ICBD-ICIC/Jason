package env;

import java.util.*;
import java.util.function.Predicate;
import java.util.concurrent.ConcurrentHashMap;
import java.util.concurrent.atomic.AtomicInteger;

import env.Message;

public abstract class ContentManager{
    static record MessageCreationParams(List<String> topics, Map<String, Object> variables) {}

    protected final Map<Integer, MessageCreationParams> content = new ConcurrentHashMap<>();
    protected final Map<Integer, Message> filteredContent = new ConcurrentHashMap<>();
    protected final AtomicInteger messageCounter = new AtomicInteger(0);

    protected abstract boolean passFilter(Message message, MessageCreationParams params);
    public abstract List<Message> feedFilter(String agent);
    public abstract List<Message> topicFilter(String agent, String concept);
    public abstract List<Message> authorFilter(String agent, String author);

    public void addMessage(String agent, String messageContent, List<String> topics, Map<String, Object> variables){
        addMessage(agent, messageContent, topics, variables, Message.EMPTY_REFERENCE);
    }

    public void addMessage(String agent, String messageContent, List<String> topics, Map<String, Object> variables, int originalId){
        Message message = new Message(
            messageCounter.incrementAndGet(),
            agent,
            messageContent,
            originalId
        );
        MessageCreationParams params = new MessageCreationParams(topics, variables);
        content.put(message.id, params);
        if (passFilter(message, params)) {
            filteredContent.put(message.id, message);
        }
    }

    public void repost(String agent, int originalId){
        Message original = filteredContent.get(originalId);
        MessageCreationParams originalParams = content.get(originalId);
        if (original != null && originalParams != null) {
            addMessage(agent, original.content, originalParams.topics(), originalParams.variables(), originalId);
        }
    }

    public void addReaction(int messageId, String author, String reaction){
        Message message = filteredContent.get(messageId);
        if (message != null) {
            message.addReaction(author, reaction);
        }
    }
}