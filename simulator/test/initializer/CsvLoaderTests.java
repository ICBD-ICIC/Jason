import initializer.CsvLoader;
import org.junit.jupiter.api.*;

import java.io.*;
import java.nio.file.*;
import java.util.List;
import java.util.Optional;

import tech.tablesaw.api.Table;

import static org.junit.jupiter.api.Assertions.*;

public class CsvLoaderTests {

    private static final String CSV_PATH = "test.csv";
    private static final List<String> COLUMNS = List.of("a", "b", "c");

    private void writeCsv(String content) throws IOException {
        Files.writeString(Path.of(CSV_PATH), content);
    }

    @AfterEach
    void cleanUp() throws IOException {
        Files.deleteIfExists(Path.of(CSV_PATH));
    }

    @Test
    void load_fileNotFound_returnsEmpty() throws Exception {
        Optional<Table> result = CsvLoader.load(CSV_PATH, COLUMNS);
        assertTrue(result.isEmpty());
    }

    @Test
    void load_emptyFile_returnsEmpty() throws Exception {
        Files.writeString(Path.of(CSV_PATH), "");

        Optional<Table> result = CsvLoader.load(CSV_PATH, COLUMNS);
        assertTrue(result.isEmpty());
    }

    @Test
    void load_headerOnlyFile_returnsEmpty() throws Exception {
        writeCsv("a,b,c\n");

        Optional<Table> result = CsvLoader.load(CSV_PATH, COLUMNS);
        assertTrue(result.isEmpty());
    }

    @Test
    void load_validFile_returnsNonEmptyOptional() throws Exception {
        writeCsv("a,b,c\n" +
                 "1,2,3\n");

        Optional<Table> result = CsvLoader.load(CSV_PATH, COLUMNS);
        assertTrue(result.isPresent());
    }

    @Test
    void load_validFile_tableHasCorrectRowCount() throws Exception {
        writeCsv("a,b,c\n" +
                 "1,2,3\n" +
                 "4,5,6\n");

        Table table = CsvLoader.load(CSV_PATH, COLUMNS).get();
        assertEquals(2, table.rowCount());
    }

    @Test
    void load_validFile_tableHasCorrectColumns() throws Exception {
        writeCsv("a,b,c\n" +
                 "1,2,3\n");

        Table table = CsvLoader.load(CSV_PATH, COLUMNS).get();
        assertTrue(table.columnNames().containsAll(COLUMNS));
    }

    @Test
    void load_noRequiredColumns_validFileReturnsTable() throws Exception {
        writeCsv("a,b,c\n" +
                 "1,2,3\n");

        Optional<Table> result = CsvLoader.load(CSV_PATH, List.of());
        assertTrue(result.isPresent());
    }

    @Test
    void load_missingRequiredColumn_throwsIOException() {
        assertThrows(IOException.class, () -> {
            writeCsv("a,b\n" +
                     "1,2\n");
            CsvLoader.load(CSV_PATH, List.of("a", "b", "c"));
        });
    }
}