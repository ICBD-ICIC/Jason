package initializer;

import tech.tablesaw.api.*;
import tech.tablesaw.io.csv.CsvReadOptions;

import java.io.IOException;
import java.util.*;

import env.ContentManager;
import env.Message;

public class MessageLoader {

    private static final String csvPath = "messages.csv";

    /**
     * Loads messages from a CSV file and returns them as an ordered list of Message objects.
     *
     * CSV columns: id, author, content, reactions, original, topics
     *
     * Rules:
     * - id: numeric, used only to resolve "original" references within the file.
     *        Simulation ids are reassigned in file order using idCounter.
     * - content: if empty, treated as a repost of original.
     *        If both content and original are empty → error on that row.
     * - reactions: semicolon-separated "agentName: reaction" pairs.
     * - original: numeric, must reference an id present in the file, or be empty.
     * - topics: semicolon-separated list of topics associated with the message.
     * - timestamps assigned in file order automatically.
     * - variables not included in the CSV.
     */
    public static void load(ContentManager contentManager) throws IOException {
        Optional<Table> result = CsvLoader.load(csvPath, List.of("id", "author", "content", "reactions", "original", "topics"));
        if (result.isEmpty()) return;
        Table table = result.get();
        
        Map<String, Integer> idMap = new LinkedHashMap<>();

        for (int rowIdx = 0; rowIdx < table.rowCount(); rowIdx++) {
            Row row = table.row(rowIdx);

            String csvId   = row.getString("id");
            String author  = row.getString("author");
            String content = row.getString("content");
            String reactionsRaw = row.getString("reactions");
            String originalCsvId = row.getString("original");
            List<String> topics = Arrays.stream(row.getString("topics").split(";"))
                                                                        .map(String::trim)
                                                                        .filter(s -> !s.isBlank())
                                                                        .toList();
            if (author == null || author.isBlank())
                throw new IOException("Row " + rowIdx + " is missing an author.");

            int originalSimId = Message.EMPTY_REFERENCE;
            if (originalCsvId != null && !originalCsvId.isBlank()) {
                if (!idMap.containsKey(originalCsvId))
                    throw new IOException("Row " + rowIdx + ": 'original' references unknown or not-yet-seen id '" + originalCsvId + "'.");
                originalSimId = idMap.get(originalCsvId);
            }

            int assignedSimId;
            if (content == null || content.isBlank()) {
                // Repost
                if (originalSimId == Message.EMPTY_REFERENCE)
                    throw new IOException("Row " + rowIdx + ": both 'content' and 'original' are empty.");
                assignedSimId = contentManager.repost(author, originalSimId);
            } else {
                // New message or comment
                assignedSimId = contentManager.addMessage(
                    author,
                    content,
                    topics,
                    null,
                    originalSimId
                );
            }

            idMap.put(csvId, assignedSimId);

            if (reactionsRaw != null && !reactionsRaw.isBlank()) {
                for (String pair : reactionsRaw.split(";")) {
                    String[] parts = pair.split(":", 2);
                    if (parts.length != 2)
                        throw new IOException("Row " + rowIdx + ": malformed reaction '" + pair.trim() + "'. Expected 'agentName: reaction'.");
                    String reactionAuthor   = parts[0].trim();
                    String reactionValue    = parts[1].trim();
                    contentManager.addReaction(assignedSimId, reactionAuthor, reactionValue);
                }
            }
        }
    }
}