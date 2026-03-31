package env;

import java.util.*;
import java.util.concurrent.ConcurrentHashMap;
import java.util.concurrent.atomic.AtomicInteger;

import com.fasterxml.jackson.databind.ObjectMapper;
import java.io.File;
import java.io.FileWriter;
import java.io.IOException;

public abstract class ContentManager {

    static record MessageCreationParams(List<String> topics, Map<String, Object> variables) {
        public MessageCreationParams {
            topics    = topics    == null ? List.of() : topics;
            variables = variables == null ? Map.of() : variables;
        }

        /**
         * Returns the sub-map stored under the {@code "public"} key of
         * {@code variables}, cast to {@code Map<String, Object>}.
         * Returns an empty map when the key is absent or the value is not a map.
         */
        @SuppressWarnings("unchecked")
        public Map<String, Object> publicVars() {
            Object pub = variables.get("public");
            if (pub instanceof Map<?, ?> map) {
                return (Map<String, Object>) map;
            }
            return Map.of();
        }
    }

    protected final Map<Integer, MessageCreationParams> content         = new ConcurrentHashMap<>();
    protected final Map<Integer, Message>               filteredContent = new ConcurrentHashMap<>();
    protected final AtomicInteger                       messageCounter  = new AtomicInteger(0);
    protected final NetworkManager                      networkManager;

    private static final String       LOG_FILE = "logs/messages.jsonl";
    private static final ObjectMapper mapper   = new ObjectMapper();

    public ContentManager(NetworkManager networkManager) {
        this.networkManager = networkManager;
    }

    protected abstract boolean passFilter(Message message, MessageCreationParams params);

    public abstract List<Message> feedFilter(String agent);
    public abstract List<Message> topicFilter(String agent, String concept);
    public abstract List<Message> authorFilter(String agent, String author);

    public List<MessageWithVars> feedFilter(String agent, boolean includePublicVars) {
        return toMessageWithVars(feedFilter(agent), includePublicVars);
    }

    public List<MessageWithVars> topicFilter(String agent, String concept, boolean includePublicVars) {
        return toMessageWithVars(topicFilter(agent, concept), includePublicVars);
    }

    public List<MessageWithVars> authorFilter(String agent, String author, boolean includePublicVars) {
        return toMessageWithVars(authorFilter(agent, author), includePublicVars);
    }

    public int addMessage(String agent, String messageContent,
                          List<String> topics, Map<String, Object> variables) {
        return addMessage(agent, messageContent, topics, variables, Message.EMPTY_REFERENCE);
    }

    public int addMessage(String agent, String messageContent,
                          List<String> topics, Map<String, Object> variables, int originalId) {
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
        save_logs(message, new MessageCreationParams(topics, logVars));

        return message.id;
    }

    public int repost(String agent, int originalId) throws IllegalArgumentException {
        Message               original       = filteredContent.get(originalId);
        MessageCreationParams originalParams = content.get(originalId);
        if (original != null && originalParams != null) {
            return addMessage(agent, original.content,
                              originalParams.topics(), originalParams.variables(), originalId);
        } else {
            throw new IllegalArgumentException(
                "Original message with ID " + originalId + " does not exist.");
        }
    }

    public void addReaction(int messageId, String author, String reaction)
            throws IllegalArgumentException {
        Message message = filteredContent.get(messageId);
        if (message != null) {
            message.addReaction(author, reaction);
            save_logs(message);
        } else {
            throw new IllegalArgumentException(
                "Message with ID " + messageId + " does not exist.");
        }
    }

    /**
     * Wraps each {@link Message} in a {@link MessageWithVars}, populating the
     * public-vars map only when requested.
     */
    private List<MessageWithVars> toMessageWithVars(List<Message> messages,
                                                     boolean includePublicVars) {
        return messages.stream()
            .map(m -> {
                Map<String, Object> pubVars = includePublicVars
                    ? Optional.ofNullable(content.get(m.id))
                              .map(MessageCreationParams::publicVars)
                              .orElse(Map.of())
                    : Map.of();
                return new MessageWithVars(m, pubVars);
            })
            .toList();
    }

    private void save_logs(Message message) {
        save_logs(message, content.get(message.id));
    }

    private void save_logs(Message message, MessageCreationParams params) {
        try {
            File dir = new File("logs");
            if (!dir.exists()) {
                dir.mkdirs();
            }

            Map<String, Object> log = new LinkedHashMap<>();

            Map<String, Object> msg = new LinkedHashMap<>();
            msg.put("id",        message.id);
            msg.put("author",    message.author);
            msg.put("content",   message.content);
            msg.put("original",  message.original);
            msg.put("timestamp", message.timestamp);

            List<Map<String, Object>> reactionsList = new ArrayList<>();
            synchronized (message.reactions) {
                for (Message.Reaction r : message.reactions) {
                    Map<String, Object> rMap = new LinkedHashMap<>();
                    rMap.put("author",   r.author());
                    rMap.put("reaction", r.reaction());
                    reactionsList.add(rMap);
                }
            }
            msg.put("reactions", reactionsList);
            log.put("message",   msg);

            log.put("topics",    params.topics());
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
