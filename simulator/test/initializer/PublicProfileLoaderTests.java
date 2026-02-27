import initializer.PublicProfileLoader;
import org.junit.jupiter.api.*;

import java.io.*;
import java.nio.file.*;
import java.util.*;

import static org.junit.jupiter.api.Assertions.*;

public class PublicProfileLoaderTests {

    private Map<String, Map<String, String>> publicProfiles;
    private static final String CSV_FILE = "public_profiles.csv";

    private void writeCsv(String content) throws IOException {
        Files.writeString(Path.of(CSV_FILE), content);
    }

    @BeforeEach
    void setUp() {
        publicProfiles = new HashMap<>();
    }

    @AfterEach
    void cleanUp() throws IOException {
        Files.deleteIfExists(Path.of(CSV_FILE));
    }

    @Test
    void load_singleEntry() throws Exception {
        writeCsv("agent,attribute,value\n" +
                 "Alice,age,30\n");

        PublicProfileLoader.load(publicProfiles);

        assertTrue(publicProfiles.containsKey("Alice"));
        assertEquals("30", publicProfiles.get("Alice").get("age"));
    }

    @Test
    void load_multipleAttributesSameAgent() throws Exception {
        writeCsv("agent,attribute,value\n" +
                 "Alice,age,30\n" +
                 "Alice,city,London\n" +
                 "Alice,job,engineer\n");

        PublicProfileLoader.load(publicProfiles);

        Map<String, String> profile = publicProfiles.get("Alice");
        assertEquals(3, profile.size());
        assertEquals("30",       profile.get("age"));
        assertEquals("London",   profile.get("city"));
        assertEquals("engineer", profile.get("job"));
    }

    @Test
    void load_multipleAgents() throws Exception {
        writeCsv("agent,attribute,value\n" +
                 "Alice,age,30\n" +
                 "Bob,age,25\n" +
                 "Carol,city,Paris\n");

        PublicProfileLoader.load(publicProfiles);

        assertEquals(3, publicProfiles.size());
        assertEquals("30",    publicProfiles.get("Alice").get("age"));
        assertEquals("25",    publicProfiles.get("Bob").get("age"));
        assertEquals("Paris", publicProfiles.get("Carol").get("city"));
    }

    @Test
    void load_emptyValue_allowed() throws Exception {
        writeCsv("agent,attribute,value\n" +
                 "Alice,nickname,\n");

        PublicProfileLoader.load(publicProfiles);

        assertTrue(publicProfiles.get("Alice").containsKey("nickname"));
        assertEquals("", publicProfiles.get("Alice").get("nickname"));
    }

    @Test
    void load_duplicateAttribute_lastValueWins() throws Exception {
        writeCsv("agent,attribute,value\n" +
                 "Alice,age,30\n" +
                 "Alice,age,31\n");

        PublicProfileLoader.load(publicProfiles);

        assertEquals("31", publicProfiles.get("Alice").get("age"));
    }

    @Test
    void load_missingAgentColumn_throwsIOException() {
        assertThrows(IOException.class, () -> {
            writeCsv("attribute,value\n" +
                     "age,30\n");
            PublicProfileLoader.load(publicProfiles);
        });
    }

    @Test
    void load_blankAgent_throwsIOException() {
        assertThrows(IOException.class, () -> {
            writeCsv("agent,attribute,value\n" +
                     ",age,30\n");
            PublicProfileLoader.load(publicProfiles);
        });
    }

    @Test
    void load_blankAttribute_throwsIOException() {
        assertThrows(IOException.class, () -> {
            writeCsv("agent,attribute,value\n" +
                     "Alice,age,30\n" +
                     "Bob,,25\n");
            PublicProfileLoader.load(publicProfiles);
        });
    }
}