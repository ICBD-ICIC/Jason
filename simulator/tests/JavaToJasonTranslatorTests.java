import jason.asSyntax.*;
import lib.JavaToJasonTranslator;
import java.util.*;
import org.junit.jupiter.api.Test;
import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertThrows;

public class JavaToJasonTranslatorTests {

    // ---------- translateVariables ----------

    @Test
    void simple_number() throws Exception {
        Map<String, Object> map = new LinkedHashMap<>();
        map.put("a", 1.0);
        Term term = JavaToJasonTranslator.translateVariables(map);
        Term expected = ASSyntax.parseTerm("[a(1)]");
        assertEquals(expected, term);
    }

    @Test
    void simple_string() throws Exception {
        Map<String, Object> map = new LinkedHashMap<>();
        map.put("s", "hello");
        Term term = JavaToJasonTranslator.translateVariables(map);
        Term expected = ASSyntax.parseTerm("[s(\"hello\")]");
        assertEquals(expected, term);
    }

    @Test
    void simple_list() throws Exception {
        Map<String, Object> map = new LinkedHashMap<>();
        map.put("a", List.of(1.0, 2.0, 3.0));
        Term term = JavaToJasonTranslator.translateVariables(map);
        Term expected = ASSyntax.parseTerm("[a([1,2,3])]");
        assertEquals(expected, term);
    }

    @Test
    void multiple_entries() throws Exception {
        Map<String, Object> map = new LinkedHashMap<>();
        map.put("a", 1.0);
        map.put("b", 2.0);
        Term term = JavaToJasonTranslator.translateVariables(map);
        Term expected = ASSyntax.parseTerm("[a(1), b(2)]");
        assertEquals(expected, term);
    }

    @Test
    void nested_structure() throws Exception {
        Map<String, Object> map = new LinkedHashMap<>();
        Map<String, Object> subMap = new LinkedHashMap<>();
        subMap.put("b", 5.0);
        map.put("a", subMap);
        Term term = JavaToJasonTranslator.translateVariables(map);
        Term expected = ASSyntax.parseTerm("[a(b(5))]");
        assertEquals(expected, term);
    }

    @Test
    void multi_arg_structure() throws Exception {
        Map<String, Object> map = new LinkedHashMap<>();
        Map<String, Object> subMap = new LinkedHashMap<>();
        subMap.put("key1", 1.0);
        subMap.put("key2", 2.0);
        map.put("key", subMap);
        Term term = JavaToJasonTranslator.translateVariables(map);
        Term expected = ASSyntax.parseTerm("[key(key1(1), key2(2))]");
        assertEquals(expected, term);
    }

    @Test
    void complex_nested() throws Exception {
        Map<String, Object> subMap = new LinkedHashMap<>();
        subMap.put("x", 10.0);
        subMap.put("y", List.of("a", "b"));
        Map<String, Object> map = new LinkedHashMap<>();
        map.put("root", subMap);
        Term term = JavaToJasonTranslator.translateVariables(map);
        Term expected = ASSyntax.parseTerm("[root(x(10), y([\"a\",\"b\"]))]");
        assertEquals(expected, term);
    }

    @Test
    void empty_map() throws Exception {
        Map<String, Object> map = new LinkedHashMap<>();
        Term term = JavaToJasonTranslator.translateVariables(map);
        Term expected = ASSyntax.parseTerm("[]");
        assertEquals(expected, term);
    }

    @Test
    void null_map() throws Exception {
        Map<String, Object> map = null;
        Term term = JavaToJasonTranslator.translateVariables(map);
        Term expected = ASSyntax.parseTerm("[]");
        assertEquals(expected, term);
    }

    @Test
    void null_value() throws Exception {
        Map<String, Object> map = new LinkedHashMap<>();
        map.put("a", null);
        assertThrows(IllegalArgumentException.class,
                () -> JavaToJasonTranslator.translateVariables(map));
    }
}