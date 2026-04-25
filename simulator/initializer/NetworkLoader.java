package initializer;

import tech.tablesaw.api.*;
import tech.tablesaw.io.csv.CsvReadOptions;

import jason.asSyntax.ASSyntax;
import jason.environment.Environment;

import java.io.IOException;
import java.util.*;

import env.NetworkManager;

public class NetworkLoader {

    /**
     * Loads edges from CSV into NetworkManager and injects follows/followed_by
     * percepts directly into the Jason environment for each agent.
     *
     * CSV columns: from, to, weight
     *
     * Rules:
     * - from, to: non-empty strings representing agent names.
     * - weight optional, defaults to NetworkManager.DEFAULT_WEIGHT if missing or empty.
     *
     * @param networkManager the network used to register links/edges
     * @param env            the Jason environment used to inject agent percepts
     * @param csvPath        path to the CSV file to load
     * @throws IOException if the file cannot be read or a row is malformed
     */
    public static void load(NetworkManager networkManager, Environment env, String csvPath) throws IOException {
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

            // Inject network beliefs as percepts — same pattern as createLink/removeLink in Env
            env.addPercept(from, ASSyntax.createLiteral("follows",     ASSyntax.createString(to)));
            env.addPercept(to,   ASSyntax.createLiteral("followed_by", ASSyntax.createString(from)));
        }
    }
}