package env;

import java.util.*;
import java.util.logging.Logger;

public class ExampleContentManager extends ContentManager {

    public ExampleContentManager(NetworkManager networkManager, Logger logger) {
        super(networkManager, logger);
    }

    @Override
    protected boolean passFilter(Message message, MessageCreationParams params) {
        return true;
    }

    private boolean hasStrongEdge(String agent, String creator) {
        return networkManager.getSocialNetwork().stream()
            .anyMatch(edge -> edge.from.equals(agent)
                           && edge.to.equals(creator)
                           && edge.weight > 5);
    }

    @Override
    public List<Message> feedFilter(String agent) {
        return filteredContent.values().stream()
            .filter(message -> hasStrongEdge(agent, message.author))
            .sorted(Comparator.comparingLong((Message m) -> m.timestamp).reversed())
            .toList();
    }

    @Override
    public List<Message> topicFilter(String agent, String concept) {
        return filteredContent.values().stream()
            .filter(message -> {
                MessageCreationParams params = content.get(message.id);
                return params.topics().contains(concept);
            })
            .sorted(Comparator.comparingLong((Message m) -> m.timestamp).reversed())
            .toList();
    }

    @Override
    public List<Message> authorFilter(String agent, String author) {
        return filteredContent.values().stream()
            .filter(message -> message.author.equals(author))
            .sorted(Comparator.comparingLong((Message m) -> m.timestamp).reversed())
            .toList();
    }
}