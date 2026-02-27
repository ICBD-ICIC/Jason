package initializer;

import tech.tablesaw.api.*;
import tech.tablesaw.io.csv.CsvReadOptions;

import java.io.IOException;
import java.nio.file.*;
import java.util.List;
import java.util.Optional;

public class CsvLoader {

    /**
     * Attempts to load a CSV file into a Tablesaw Table.
     *
     * Returns an empty Optional if the file does not exist, is empty, or has no data rows.
     * Throws IOException if a required column is missing or the file cannot be read.
     *
     * All columns are read as strings. Missing cells are treated as empty strings.
     */
    public static Optional<Table> load(String csvPath, List<String> requiredColumns) throws IOException {
        Path path = Path.of(csvPath);

        if (!Files.exists(path)) {
            System.out.println("[CsvLoader] File '" + csvPath + "' not found. Skipping.");
            return Optional.empty();
        }

        if (Files.size(path) == 0) {
            System.out.println("[CsvLoader] File '" + csvPath + "' is empty. Skipping.");
            return Optional.empty();
        }

        Table table = Table.read().usingOptions(
            CsvReadOptions.builder(csvPath)
                .missingValueIndicator("")
                .columnTypesToDetect(List.of(ColumnType.STRING))
                .build()
        );

        if (table.rowCount() == 0) {
            System.out.println("[CsvLoader] File '" + csvPath + "' has no data rows. Skipping.");
            return Optional.empty();
        }

        for (String col : requiredColumns) {
            if (!table.columnNames().contains(col))
                throw new IOException("CSV header missing required column: '" + col + "'");
        }
        return Optional.of(table);
    }
}