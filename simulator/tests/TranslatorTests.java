import jason.asSyntax.*;
import lib.Translator;
import java.util.*;
import org.junit.jupiter.api.Test;
import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertIterableEquals;
import static org.junit.jupiter.api.Assertions.assertThrows;


public class TranslatorTests {

    // ---------- translateTopics ----------

    @Test
    void topics_atoms() throws Exception {
        Term t = ASSyntax.parseTerm("[a,b,c]");
        List<String> result = Translator.translateTopics(t);
        assertIterableEquals(Arrays.asList("a","b","c"), result);
    }

    @Test
    void topics_strings() throws Exception {
        Term t = ASSyntax.parseTerm("[\"news\",\"sports\"]");
        List<String> result = Translator.translateTopics(t);
        assertIterableEquals(Arrays.asList("news","sports"), result);
    }

    @Test
    void topics_variables() throws Exception {
        Term t = ASSyntax.parseTerm("[Topic1,Topic2]");
        List<String> result = Translator.translateTopics(t);
        assertIterableEquals(Arrays.asList("Topic1","Topic2"), result);
    }

    @Test
    void topics_invalid_type() throws Exception {
        Term t = ASSyntax.parseTerm("[a(1)]");
        assertThrows(IllegalArgumentException.class,
                () -> Translator.translateTopics(t));
    }

    @Test
    void topics_not_list() throws Exception {
        Term t = ASSyntax.parseTerm("a");
        assertThrows(IllegalArgumentException.class,
                () -> Translator.translateTopics(t));
    }

    // ---------- translateVariables ----------

    @Test
    void variables_simple() throws Exception {
        Term t = ASSyntax.parseTerm("[a(1), b(2)]");
        Map<String,Object> map = Translator.translateVariables(t);

        assertEquals(2, map.size());
        assertEquals(1.0, ((Number) map.get("a")).doubleValue());
        assertEquals(2.0, ((Number) map.get("b")).doubleValue());
    }

    @Test
    void variables_list_value() throws Exception {
        Term t = ASSyntax.parseTerm("[a([1,2,3])]");
        Map<String,Object> map = Translator.translateVariables(t);

        List<?> list = (List<?>) map.get("a");
        assertEquals(Arrays.asList(1.0,2.0,3.0), list);
    }

    @Test
    void variables_nested() throws Exception {
        Term t = ASSyntax.parseTerm("[a(b(5))]");
        Map<String,Object> map = Translator.translateVariables(t);

        Map<?,?> nested = (Map<?,?>) map.get("a");
        assertEquals(5.0, ((Number) nested.get("b")).doubleValue());
    }

    @Test
    void variables_strings_atoms_vars() throws Exception {
        Term t = ASSyntax.parseTerm("[v(X),s(\"hello\"), a(atom), v(X)]");
        Map<String,Object> map = Translator.translateVariables(t);
        assertEquals("hello", map.get("s"));
        assertEquals("atom", map.get("a"));
        assertEquals("X", map.get("v"));
    }

    @Test
    void variables_multi_arg_structure() throws Exception {
        Term t = ASSyntax.parseTerm("[key(key1(1), key2(2))]");
        Map<String, Object> map = Translator.translateVariables(t);

        Map<?, ?> nested = (Map<?, ?>) map.get("key");
        assertEquals(2, nested.size());
        assertEquals(1.0, ((Number) nested.get("key1")).doubleValue());
        assertEquals(2.0, ((Number) nested.get("key2")).doubleValue());
    }

    @Test
    void variables_invalid_structure() throws Exception {
        Term t = ASSyntax.parseTerm("[a(1,2)]");
        assertThrows(IllegalArgumentException.class,
                () -> Translator.translateVariables(t));
    }

    @Test
    void variables_not_list() throws Exception {
        Term t = ASSyntax.parseTerm("a");
        assertThrows(IllegalArgumentException.class,
                () -> Translator.translateVariables(t));
    }
}