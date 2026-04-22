package env;

import java.util.*;
import java.util.stream.Collectors;

public class CoNVaIContentManager extends ContentManager {

    public CoNVaIContentManager(NetworkManager networkManager) {
        super(networkManager);
    }

    /**
     * Always passes — misinformation filtering is handled at the agent level.
     */
    @Override
    protected boolean passFilter(Message message, MessageCreationParams params) {
        return true;
    }

    /**
     * Implements the per() function from Definition 5 (AB-SIR / CoNVaI).
     *
     * Agent ui perceives a message m if and only if the author of m
     * is in Uin(ui) — i.e. ui follows that author.
     */
    @Override
    public List<Message> feedFilter(String agent) {
        Set<String> followees = networkManager.getSocialNetwork().stream()
            .filter(edge -> edge.from.equals(agent))
            .map(edge -> edge.to)
            .collect(Collectors.toSet());

        return filteredContent.values().stream()
            .filter(m -> followees.contains(m.author))
            .sorted(Comparator.comparingLong(m -> m.timestamp))
            .toList();
    }

    @Override
    public List<Message> topicFilter(String agent, String concept) {
        throw new UnsupportedOperationException("topicFilter is not used in the CoNVaI experiment.");
    }

    @Override
    public List<Message> authorFilter(String agent, String author) {
        throw new UnsupportedOperationException("authorFilter is not used in the CoNVaI experiment.");
    }
}
