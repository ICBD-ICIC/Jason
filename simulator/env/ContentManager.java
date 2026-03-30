package env;

import java.util.*;
import java.util.function.Predicate;
import java.util.concurrent.ConcurrentHashMap;
import java.util.concurrent.atomic.AtomicInteger;

import env.Message;

public abstract class ContentManager{
    static record MessageCreationParams(List<String> topics, Map<String, Object> variables) {
        public MessageCreationParams {
            topics = topics == null ? List.of() : topics;
            variables = variables == null ? Map.of() : variables;
        }
    }

    protected final Map<Integer, MessageCreationParams> content = new ConcurrentHashMap<>();
    protected final Map<Integer, Message> filteredContent = new ConcurrentHashMap<>();
    protected final AtomicInteger messageCounter = new AtomicInteger(0);
    protected final NetworkManager networkManager;

    public ContentManager(NetworkManager networkManager) {
        this.networkManager = networkManager;
    }
    
    protected abstract boolean passFilter(Message message, MessageCreationParams params);
    public abstract List<Message> feedFilter(String agent);
    public abstract List<Message> topicFilter(String agent, String concept);
    public abstract List<Message> authorFilter(String agent, String author);

    public int addMessage(String agent, String messageContent, List<String> topics, Map<String, Object> variables){
        return addMessage(agent, messageContent, topics, variables, Message.EMPTY_REFERENCE);
    }

    public int addMessage(String agent, String messageContent, List<String> topics, Map<String, Object> variables, int originalId){
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
        return message.id;
    }

    public int repost(String agent, int originalId) throws IllegalArgumentException {
        Message original = filteredContent.get(originalId);
        MessageCreationParams originalParams = content.get(originalId);
        if (original != null && originalParams != null) {
            return addMessage(agent, original.content, originalParams.topics(), originalParams.variables(), originalId);
        } else {
            throw new IllegalArgumentException("Original message with ID " + originalId + " does not exist.");
        }
    }

    public void addReaction(int messageId, String author, String reaction) throws IllegalArgumentException {
        Message message = filteredContent.get(messageId);
        if (message != null) {
            message.addReaction(author, reaction);
        }
        else {
            throw new IllegalArgumentException("Message with ID " + messageId + " does not exist.");
        }
    }
}