import jason.asSyntax.*;
import lib.JasonToJavaTranslator;
import java.util.*;
import org.junit.jupiter.api.Test;
import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertIterableEquals;
import static org.junit.jupiter.api.Assertions.assertThrows;


public class JasonToJavaTranslatorTests {

    // ---------- translateTopics ----------

    @Test
    void topics_atoms() throws Exception {
        Term t = ASSyntax.parseTerm("[a,b,c]");
        List<String> result = JasonToJavaTranslator.translateTopics(t);
        assertIterableEquals(Arrays.asList("a","b","c"), result);
    }

    @Test
    void topics_strings() throws Exception {
        Term t = ASSyntax.parseTerm("[\"news\",\"sports\"]");
        List<String> result = JasonToJavaTranslator.translateTopics(t);
        assertIterableEquals(Arrays.asList("news","sports"), result);
    }

    @Test
    void topics_variables() throws Exception {
        Term t = ASSyntax.parseTerm("[Topic1,Topic2]");
        List<String> result = JasonToJavaTranslator.translateTopics(t);
        assertIterableEquals(Arrays.asList("Topic1","Topic2"), result);
    }

    @Test
    void topics_invalid_type() throws Exception {
        Term t = ASSyntax.parseTerm("[a(1)]");
        assertThrows(IllegalArgumentException.class,
                () -> JasonToJavaTranslator.translateTopics(t));
    }

    @Test
    void topics_not_list() throws Exception {
        Term t = ASSyntax.parseTerm("a");
        assertThrows(IllegalArgumentException.class,
                () -> JasonToJavaTranslator.translateTopics(t));
    }

    // ---------- translateVariables ----------

    @Test
    void variables_simple() throws Exception {
        Term t = ASSyntax.parseTerm("[a(1), b(2)]");
        Map<String,Object> map = JasonToJavaTranslator.translateVariables(t);

        assertEquals(2, map.size());
        assertEquals(1.0, ((Number) map.get("a")).doubleValue());
        assertEquals(2.0, ((Number) map.get("b")).doubleValue());
    }

    @Test
    void variables_list_value() throws Exception {
        Term t = ASSyntax.parseTerm("[a([1,2,3])]");
        Map<String,Object> map = JasonToJavaTranslator.translateVariables(t);

        List<?> list = (List<?>) map.get("a");
        assertEquals(Arrays.asList(1.0,2.0,3.0), list);
    }

    @Test
    void variables_nested() throws Exception {
        Term t = ASSyntax.parseTerm("[a(b(5))]");
        Map<String,Object> map = JasonToJavaTranslator.translateVariables(t);

        Map<?,?> nested = (Map<?,?>) map.get("a");
        assertEquals(5.0, ((Number) nested.get("b")).doubleValue());
    }

    @Test
    void variables_strings_atoms_vars() throws Exception {
        Term t = ASSyntax.parseTerm("[s(\"hello\"), a(atom), v(X)]");
        Map<String,Object> map = JasonToJavaTranslator.translateVariables(t);
        assertEquals("hello", map.get("s"));
        assertEquals("atom", map.get("a"));
        assertEquals("X", map.get("v"));
    }

    @Test
    void variables_duplicated_key() throws Exception {
        Term t = ASSyntax.parseTerm("[v(first), v(second)]");
        Map<String,Object> map = JasonToJavaTranslator.translateVariables(t);
        assertEquals("second", map.get("v"));
    }

    @Test
    void variables_multi_arg_structure() throws Exception {
        Term t = ASSyntax.parseTerm("[key(key1(1), key2(2))]");
        Map<String, Object> map = JasonToJavaTranslator.translateVariables(t);

        Map<?, ?> nested = (Map<?, ?>) map.get("key");
        assertEquals(2, nested.size());
        assertEquals(1.0, ((Number) nested.get("key1")).doubleValue());
        assertEquals(2.0, ((Number) nested.get("key2")).doubleValue());
    }

    @Test
    void variables_invalid_structure() throws Exception {
        Term t = ASSyntax.parseTerm("[a(1,2)]");
        assertThrows(IllegalArgumentException.class,
                () -> JasonToJavaTranslator.translateVariables(t));
    }

    @Test
    void variables_not_list() throws Exception {
        Term t = ASSyntax.parseTerm("a");
        assertThrows(IllegalArgumentException.class,
                () -> JasonToJavaTranslator.translateVariables(t));
    }
}