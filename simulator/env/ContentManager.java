package env;

import java.util.*;
import java.util.function.Predicate;
import java.util.concurrent.ConcurrentHashMap;
import java.util.concurrent.atomic.AtomicInteger;

import com.fasterxml.jackson.databind.ObjectMapper;
import java.io.File;
import java.io.FileWriter;
import java.io.IOException;

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
    private static final String LOG_FILE = "logs/messages.jsonl";
    private static final ObjectMapper mapper = new ObjectMapper();

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

        boolean passed = passFilter(message, params);
        if (passed) {
            filteredContent.put(message.id, message);
        }

        Map<String, Object> logVars = new LinkedHashMap<>(variables);
        logVars.put("passedFilter", passed);
        save_logs(message,  new MessageCreationParams(topics, logVars));

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
            save_logs(message);
        }
        else {
            throw new IllegalArgumentException("Message with ID " + messageId + " does not exist.");
        }
    }

    private void save_logs(Message message) {
        MessageCreationParams originalParams = content.get(message.id);
        save_logs(message, originalParams);
    }

    private void save_logs(Message message, MessageCreationParams params) {
        try {
            File dir = new File("logs");
            if (!dir.exists()) {
                dir.mkdirs();
            }

            Map<String, Object> log = new LinkedHashMap<>();

            Map<String, Object> msg = new LinkedHashMap<>();
            msg.put("id", message.id);
            msg.put("author", message.author);
            msg.put("content", message.content);
            msg.put("original", message.original);
            msg.put("timestamp", message.timestamp);
            List<Map<String, Object>> reactionsList = new ArrayList<>();
            synchronized (message.reactions) {
                for (Message.Reaction r : message.reactions) {
                    Map<String, Object> rMap = new LinkedHashMap<>();
                    rMap.put("author", r.author());
                    rMap.put("reaction", r.reaction());
                    reactionsList.add(rMap);
                }
            }
            msg.put("reactions", reactionsList);
            log.put("message", msg);

            log.put("topics", params.topics());
            log.put("variables", params.variables());

            try (FileWriter file = new FileWriter(LOG_FILE, true)) {
                file.write(mapper.writeValueAsString(log));
                file.write(System.lineSeparator());
            }
        } catch (IOException e) {
            System.err.println("[ContentManager] Logging failed: " + e.getMessage());
        }
    }
}