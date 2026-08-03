package initializer;

import tech.tablesaw.api.*;

import java.io.IOException;
import java.util.*;
import java.util.logging.Logger;

import env.NetworkManager;

public class NetworkLoader {

    /**
     * Loads edges from CSV into NetworkManager, which internally registers
     * the follows/followed_by percepts in the Jason environment.
     *
     * CSV columns: from, to, weight
     *
     * Rules:
     * - from, to: non-empty strings representing agent names.
     * - weight optional, defaults to NetworkManager.DEFAULT_WEIGHT if missing or empty.
     *
     * @param networkManager the network used to register links/edges (and percepts)
     * @param csvPath        path to the CSV file to load
     * @param logger         the logger used to log messages
     * @throws IOException if the file cannot be read or a row is malformed
     */
    public static void load(NetworkManager networkManager, String csvPath, Logger logger) throws IOException {
        Optional<Table> result = CsvLoader.load(csvPath, List.of("from", "to", "weight"), logger);
        if (result.isEmpty()) return;
        Table table = result.get();

        for (int rowIdx = 0; rowIdx < table.rowCount(); rowIdx++) {
            Row row = table.row(rowIdx);

            String from = row.isMissing("from") ? null : row.getString("from");
            String to   = row.isMissing("to")   ? null : row.getString("to");

            if (from == null || from.isBlank() || to == null || to.isBlank())
                throw new IOException("Row " + rowIdx + ": 'from' or 'to' is missing.");

            if (!row.isMissing("weight") && !row.getString("weight").isBlank()) {
                try {
                    double weight = Double.parseDouble(row.getString("weight").trim());
                    networkManager.addEdge(from, to, weight);
                } catch (NumberFormatException e) {
                    throw new IOException("Row " + rowIdx + ": invalid weight '" + row.getString("weight") + "'");
                }
            } else {
                networkManager.addEdge(from, to);
            }
        }
    }
}