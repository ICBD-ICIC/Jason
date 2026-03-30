package env;

import java.util.*;

public class DefaultContentManager extends ContentManager {
    public DefaultContentManager(NetworkManager networkManager) {
        super(networkManager);
    }

    @Override
    protected boolean passFilter(Message message, MessageCreationParams params) {
        return true;
    }

    @Override
    public List<Message> feedFilter(String agent) {
        return new ArrayList<>(filteredContent.values());
    } 
    
    @Override
    public List<Message> topicFilter(String agent, String concept) { 
        return feedFilter(agent).stream()
                    .filter(message -> {
                        MessageCreationParams params = content.get(message.id);
                        return params.topics().contains(concept);
                    }).toList();
    }

    @Override
    public List<Message> authorFilter(String agent, String author) {
        return feedFilter(agent).stream()
                    .filter(message -> {
                        return message.author.equals(author);
                    }).toList();
    }
}
