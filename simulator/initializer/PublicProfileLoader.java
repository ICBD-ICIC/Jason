package initializer;

import tech.tablesaw.api.*;
import java.io.IOException;
import java.util.*;

public class PublicProfileLoader {

    /**
     * Loads public profiles from CSV into a Map<String, Map<String, Object>>.
     *
     * CSV columns: agent, attribute, value
     *
     * Rules:
     * - agent, attribute: non-empty strings.
     * - value: stored as String; may be empty.
     * 
     * @param publicProfiles the map used to save the pairs atribute-value for each agent
     * @param csvPath path to the CSV file to load, following the specified rules
     * @throws IOException if the file cannot be read, a row is malformed, or a referential constraint is violated
     */
    public static void load(Map<String, Map<String, String>> publicProfiles, String csvPath) throws IOException {
        Optional<Table> result = CsvLoader.load(csvPath, List.of("agent", "attribute", "value"));
        if (result.isEmpty()) return;
        Table table = result.get();

        for (int rowIdx = 0; rowIdx < table.rowCount(); rowIdx++) {
            Row row = table.row(rowIdx);

            String agent     = row.isMissing("agent")     ? null : row.getString("agent").trim();
            String attribute = row.isMissing("attribute") ? null : row.getString("attribute").trim();

            if (agent == null || agent.isBlank())
                throw new IOException("Row " + rowIdx + ": 'agent' is missing or blank.");
            if (attribute == null || attribute.isBlank())
                throw new IOException("Row " + rowIdx + ": 'attribute' is missing or blank.");

            String value = row.isMissing("value") ? "" : row.getString("value").trim();

            publicProfiles
                .computeIfAbsent(agent, k -> new LinkedHashMap<>())
                .put(attribute, value);
        }
    }
}