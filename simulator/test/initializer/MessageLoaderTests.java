import initializer.MessageLoader;
import env.ContentManager;
import env.DefaultContentManager;
import env.Message;
import env.Message.Reaction;
import org.junit.jupiter.api.*;
import org.junit.jupiter.api.io.TempDir;

import java.io.*;
import java.nio.file.*;
import java.util.*;

import static org.junit.jupiter.api.Assertions.*;

public class MessageLoaderTests {

    @TempDir
    Path tempDir;

    private ContentManager contentManager;
    private static final String csvFileName = "messages.csv";

    private void writeCsv(String csvContent) throws IOException {
        Path csv = Path.of(csvFileName);
        Files.writeString(csv, csvContent);
    }

    private void assertReaction(List<Message.Reaction> reactions, String author, String expectedReaction) {
    String actual = reactions.stream()
        .filter(r -> r.author().equals(author))
        .map(r -> r.reaction())
        .findFirst()
        .orElseThrow(() -> new AssertionError("No reaction found for author: " + author));
        assertEquals(expectedReaction, actual);
    }

    @BeforeEach
    void setUp() {
        contentManager = new DefaultContentManager(null);
    }

    @AfterEach
    void cleanUp() throws IOException {
        Files.deleteIfExists(Path.of(csvFileName));
    }

    @Test
    void load_singleMessage() throws Exception {
        writeCsv("id,author,content,reactions,original,topics\n" +
                 "1,Alice,Hello world,,,news\n");

        MessageLoader.load(contentManager);

        List<Message> messages = contentManager.feedFilter("test");
        assertEquals(1, messages.size());

        Message msg = messages.get(0);
        assertEquals("Alice", msg.author);
        assertEquals("Hello world", msg.content);
        assertEquals(0, msg.reactions.size());
        assertEquals(Message.EMPTY_REFERENCE, msg.original);
    }

    @Test
    void load_noId() throws Exception {
        writeCsv("id,author,content,reactions,original,topics\n" +
                 ",Alice,Hello world,,,news\n");

        MessageLoader.load(contentManager);

        List<Message> messages = contentManager.feedFilter("test");
        assertEquals(1, messages.size());

        Message msg = messages.get(0);
        assertEquals("Alice", msg.author);
        assertEquals("Hello world", msg.content);
        assertEquals(0, msg.reactions.size());
        assertEquals(Message.EMPTY_REFERENCE, msg.original);
    }

    @Test
    void load_multipleMessages_preservesOrder() throws Exception {
        writeCsv("id,author,content,reactions,original,topics\n" +
                 "1,Alice,First,,, \n" +
                 "2,Bob,Second,,,\n" +
                 "3,Carol,Third,,,\n");

        MessageLoader.load(contentManager);

        List<Message> messages = contentManager.feedFilter("test");
        assertEquals(3, messages.size());
        assertEquals("First",  messages.get(0).content);
        assertEquals("Second", messages.get(1).content);
        assertEquals("Third",  messages.get(2).content);
    }

    @Test
    void load_repost() throws Exception {
        writeCsv("id,author,content,reactions,original,topics\n" +
                 "1,Alice,Original message,,,news\n" +
                 "2,Bob,,,1,\n");

        MessageLoader.load(contentManager);

        List<Message> messages = contentManager.feedFilter("test");
        assertEquals(2, messages.size());
        assertEquals(Message.EMPTY_REFERENCE, messages.get(0).original);
        assertEquals(messages.get(0).id, messages.get(1).original);
        assertEquals(messages.get(0).content, messages.get(1).content);
    }

    @Test
    void load_singleReaction() throws Exception {
        writeCsv("id,author,content,reactions,original,topics\n" +
                 "1,Alice,Hello,Bob: like,,news\n");

        MessageLoader.load(contentManager);

        List<Reaction> reactions = contentManager.feedFilter("test").get(0).reactions;
        assertFalse(reactions.isEmpty());
        assertReaction(reactions, "Bob", "like");
    }

    @Test
    void load_multipleReactions() throws Exception {
        writeCsv("id,author,content,reactions,original,topics\n" +
                 "1,Alice,Hello,\"Bob: like; Carol: love\",,news\n");

        MessageLoader.load(contentManager);

        List<Reaction> reactions = contentManager.feedFilter("test").get(0).reactions;
        assertEquals(2, reactions.size());
        assertReaction(reactions, "Bob", "like");
        assertReaction(reactions, "Carol", "love");
    }

    @Test
    void load_comment() throws Exception {
        writeCsv("id,author,content,reactions,original,topics\n" +
                 "908,Alice,Parent post,,,\n" +
                 "78,Bob,My comment,,908,\n");

        MessageLoader.load(contentManager);

        List<Message> messages = contentManager.feedFilter("test");
        assertEquals(2, messages.size());
        assertEquals(messages.get(0).id, messages.get(1).original);
    }

    @Test
    void load_missingAuthor_throwsIOException() {
        assertThrows(IOException.class, () -> {
            writeCsv("id,author,content,reactions,original,topics\n" +
                     "1,,Hello,,,\n");
            MessageLoader.load(contentManager);
        });
    }

    @Test
    void load_emptyContentAndNoOriginal_throwsIOException() {
        assertThrows(IOException.class, () -> {
            writeCsv("id,author,content,reactions,original,topics\n" +
                     "1,Alice,,,,\n");
            MessageLoader.load(contentManager);
        });
    }

    @Test
    void load_originalReferencesUnknownId_throwsIOException() {
        assertThrows(IOException.class, () -> {
            writeCsv("id,author,content,reactions,original,topics\n" +
                     "1,Alice,Hello,,99,\n");
            MessageLoader.load(contentManager);
        });
    }

    @Test
    void load_originalReferencesForwardId_throwsIOException() {
        assertThrows(IOException.class, () -> {
            writeCsv("id,author,content,reactions,original,topics\n" +
                     "1,Alice,Hello,,2,\n" +
                     "2,Bob,World,,,\n");
            MessageLoader.load(contentManager);
        });
    }

    @Test
    void load_malformedReaction_throwsIOException() {
        assertThrows(IOException.class, () -> {
            writeCsv("id,author,content,reactions,original,topics\n" +
                     "1,Alice,Hello,BadReaction,,\n");
            MessageLoader.load(contentManager);
        });
    }
}