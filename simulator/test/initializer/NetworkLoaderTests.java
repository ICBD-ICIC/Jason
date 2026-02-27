import initializer.NetworkLoader;
import env.NetworkManager;
import env.NetworkManager.Edge;
import org.junit.jupiter.api.*;

import java.io.*;
import java.nio.file.*;
import java.util.Optional;

import static org.junit.jupiter.api.Assertions.*;

public class NetworkLoaderTests {

    private NetworkManager networkManager;
    private double defaultWeight = 1; // Should match NetworkManager.DEFAULT_WEIGHT
    private static final String csvFileName = "network.csv";

    private void writeCsv(String content) throws IOException {
        Files.writeString(Path.of(csvFileName), content);
    }

    private Optional<Edge> findEdge(String from, String to) {
        return networkManager.getSocialNetwork().stream()
                .filter(e -> e.from.equals(from) && e.to.equals(to))
                .findFirst();
    }

    @BeforeEach
    void setUp() {
        networkManager = new NetworkManager();
    }

    @AfterEach
    void cleanUp() throws IOException {
        Files.deleteIfExists(Path.of(csvFileName));
    }

    @Test
    void load_singleEdge() throws Exception {
        writeCsv("from,to,weight\n" +
                 "Alice,Bob,0.5\n");

        NetworkLoader.load(networkManager);

        Optional<Edge> edge = findEdge("Alice", "Bob");
        assertTrue(edge.isPresent());
        assertEquals("Alice", edge.get().from);
        assertEquals("Bob",   edge.get().to);
        assertEquals(0.5, edge.get().weight);
    }

    @Test
    void load_multipleEdges() throws Exception {
        writeCsv("from,to,weight\n" +
                 "Alice,Bob,0.5\n" +
                 "Bob,Carol,\n" +
                 "Carol,Alice,2.0\n");

        NetworkLoader.load(networkManager);

        assertEquals(3, networkManager.getSocialNetwork().size());
        assertEquals(0.5, findEdge("Alice", "Bob").get().weight);
        assertEquals(defaultWeight, findEdge("Bob",   "Carol").get().weight);
        assertEquals(2.0, findEdge("Carol", "Alice").get().weight);
    }

    @Test
    void load_duplicateEdge_notAddedTwice() throws Exception {
        writeCsv("from,to,weight\n" +
                 "Alice,Bob,1.0\n" +
                 "Alice,Bob,2.0\n");

        NetworkLoader.load(networkManager);

        assertEquals(1, networkManager.getSocialNetwork().size());
        assertEquals(1.0, findEdge("Alice", "Bob").get().weight);
    }

    @Test
    void load_negativeWeight() throws Exception {
        writeCsv("from,to,weight\n" +
                 "Alice,Bob,-1.5\n");

        NetworkLoader.load(networkManager);

        assertEquals(-1.5, findEdge("Alice", "Bob").get().weight);
    }

    @Test
    void load_zeroWeight() throws Exception {
        writeCsv("from,to,weight\n" +
                 "Alice Smith,Bob,0.0\n");

        NetworkLoader.load(networkManager);

        assertEquals(0.0, findEdge("Alice Smith", "Bob").get().weight);
    }

    @Test
    void load_directedEdges() throws Exception {
        writeCsv("from,to,weight\n" +
                 "Alice,Bob,1.0\n" +
                 "Bob,Alice,2.0\n");

        NetworkLoader.load(networkManager);

        assertEquals(2,   networkManager.getSocialNetwork().size());
        assertEquals(1.0, findEdge("Alice", "Bob").get().weight);
        assertEquals(2.0, findEdge("Bob", "Alice").get().weight);
    }

    @Test
    void load_blankFrom_throwsIOException() {
        assertThrows(IOException.class, () -> {
            writeCsv("from,to,weight\n" +
                     ",Bob,1.0\n");
            NetworkLoader.load(networkManager);
        });
    }

    @Test
    void load_blankTo_throwsIOException() {
        assertThrows(IOException.class, () -> {
            writeCsv("from,to,weight\n" +
                     "Alice,,1.0\n");
            NetworkLoader.load(networkManager);
        });
    }
    
    @Test
    void load_invalidWeight_throwsIOException() {
        assertThrows(IOException.class, () -> {
            writeCsv("from,to,weight\n" +
                     "Alice,Bob,notanumber\n");
            NetworkLoader.load(networkManager);
        });
    }

    @Test
    void load_invalidRowAfterValidRows_throwsIOException() {
        assertThrows(IOException.class, () -> {
            writeCsv("from,to,weight\n" +
                     "Alice,Bob,1.0\n" +
                     "Carol,,2.0\n");
            NetworkLoader.load(networkManager);
        });
    }
}