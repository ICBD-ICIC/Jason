package initializer;

import tech.tablesaw.api.*;
import tech.tablesaw.io.csv.CsvReadOptions;

import java.io.IOException;
import java.util.*;

import env.NetworkManager;

public class NetworkLoader {

    private static final String csvPath = "network.csv";

    /**
     * Loads edges from CSV into NetworkManager.
     *
     * CSV columns: from, to, weight
     *
     * Rules:
     * - from, to: non-empty strings representing agent names.
     * - weight optional, defaults to NetworkManager.DEFAULT_WEIGHT if missing or empty. Must be a valid number if present.
     */
    public static void load(NetworkManager networkManager) throws IOException {
        Optional<Table> result = CsvLoader.load(csvPath, List.of("from", "to", "weight"));
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