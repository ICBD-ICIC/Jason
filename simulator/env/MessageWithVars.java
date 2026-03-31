package env;

import java.util.Map;

/**
 * Pairs a {@link Message} with the subset of its creation-time variables that
 * are stored under the {@code "public"} key, ready to be exposed as percepts
 * when {@code includePublicVars} is {@code true}.
 *
 * <p>If no public variables exist the map will be empty, never {@code null}.</p>
 */
public record MessageWithVars(Message message, Map<String, Object> publicVars) {

    /** Wraps a message with no public variables. */
    public static MessageWithVars of(Message message) {
        return new MessageWithVars(message, Map.of());
    }
}
