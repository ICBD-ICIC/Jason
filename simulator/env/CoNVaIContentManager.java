package env;

import java.util.*;
import java.util.stream.Collectors;

public class CoNVaIContentManager extends ContentManager {

    public CoNVaIContentManager(NetworkManager networkManager) {
        super(networkManager);
    }

    @Override
    protected boolean passFilter(Message message, MessageCreationParams params) {
        return true;
    }

    /**
     * Implements the per() function from Definition 5 (AB-SIR / CoNVaI).
     *
     * Agent ui perceives a message m if and only if:
     *   (a) the author of m is in Uin(ui) — i.e. ui follows that author, OR
     *   (b) m carries a public {@code conversation_id} variable and ui has
     *       authored at least one message with that same {@code conversation_id}.
     *
     * Results are ordered by timestamp, newest first.
     */
    @Override
    public List<MessageWithVars> feedFilter(String agent, boolean includePublicVars) {
        Set<String> followees = networkManager.getSocialNetwork().stream()
            .filter(edge -> edge.from.equals(agent))
            .map(edge -> edge.to)
            .collect(Collectors.toSet());

        // Collect all conversation_ids from messages authored by this agent.
        Set<Object> agentConversationIds = content.entrySet().stream()
            .filter(e -> {
                Message m = filteredContent.get(e.getKey());
                return m != null && agent.equals(m.author);
            })
            .map(e -> e.getValue().publicVars().get("conversation_id"))
            .filter(Objects::nonNull)
            .collect(Collectors.toSet());

        return filteredContent.values().stream()
            .filter(m -> {
                if (followees.contains(m.author)) return true;
                Object convId = Optional.ofNullable(content.get(m.id))
                    .map(p -> p.publicVars().get("conversation_id"))
                    .orElse(null);
                return convId != null && agentConversationIds.contains(convId);
            })
            .map(m -> {
                Map<String, Object> pubVars = includePublicVars
                    ? Optional.ofNullable(content.get(m.id))
                              .map(MessageCreationParams::publicVars)
                              .orElse(Map.of())
                    : Map.of();
                return new MessageWithVars(m, pubVars);
            })
            .sorted(Comparator.comparingLong((MessageWithVars mwv) -> mwv.message().timestamp).reversed())
            .toList();
    }

    @Override
    public List<Message> feedFilter(String agent) {
        throw new UnsupportedOperationException("feedFilter(agent) is not used in the CoNVaI experiment.");
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