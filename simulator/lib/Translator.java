package lib;

import jason.asSyntax.*;

import java.util.*;

/**
 * Utility class for translating Jason {@link Term} structures into standard Java types.
 *
 * <p>Provides static methods to convert Jason list terms into Java {@link List} and
 * {@link Map} representations, supporting atoms, strings, variables, numbers, and
 * nested structures.
 *
 * <p>This class is not instantiable.
 */
public final class Translator {

    /**
     * Translates a Jason list term into a {@link List} of topic strings.
     *
     * <p>Each element in the list must be one of:
     * <ul>
     *   <li>A {@link StringTerm} — its string value is used directly.</li>
     *   <li>A {@link VarTerm} — its string representation is used.</li>
     *   <li>A zero-arity {@link Atom} — its functor name is used.</li>
     * </ul>
     *
     * @param t the Jason term, expected to be a {@link ListTerm}
     * @return a list of topic strings in the same order as the input list
     * @throws IllegalArgumentException if {@code t} is not a {@link ListTerm}, or if any
     *                                  element is not an atom, string, or variable
     */
    public static List<String> translateTopics(Term t) {
        if (!(t instanceof ListTerm list)) {
            throw new IllegalArgumentException("Expected a Jason list term");
        }

        List<String> topics = new ArrayList<>();

        for (Term item : list) {
            if (item instanceof StringTerm s) {
                topics.add(s.getString());
            }
            else if (item instanceof VarTerm) {
                topics.add(item.toString());
            }
            else if (item instanceof Atom a && a.getArity() == 0) {
                topics.add(a.getFunctor());
            }
            else {
                throw new IllegalArgumentException(
                    "Topics must be atoms, strings, or vars. Found: " + item
                );
            }
        }

        return topics;
    }


    /**
     * Translates a Jason list term of key-value structures into a nested {@link Map}.
     *
     * <p>Each element in the list must be a Jason structure of the form {@code key(value)}
     * or a multi-argument structure {@code key(field1(v1), field2(v2))} which is translated
     * into a nested map. Keys are taken from functor names; values are resolved recursively
     * via {@link #parseValue(Term)}.
     *
     * <p>Example Jason term: {@code [name("Alice"), age(30), address(city("Rome"), zip("00100"))]}
     * produces: {@code {name=Alice, age=30.0, address={city=Rome, zip=00100}}}
     *
     * @param t the Jason term, expected to be a {@link ListTerm} of structures
     * @return a map of string keys to parsed values ({@link String}, {@link Double},
     *         {@link List}, nested {@link Map}, etc.)
     * @throws IllegalArgumentException if {@code t} is not a {@link ListTerm}, or if any
     *                                  element cannot be parsed as a key-value structure
     */
    public static Map<String, Object> translateVariables(Term t) {
        Map<String, Object> result = new HashMap<>();

        if (t instanceof ListTerm list) {
            for (Term item : list) {
                parseStructure(item, result);
            }
        } else {
            throw new IllegalArgumentException("Expected a Jason list term");
        }

        return result;
    }

    /**
     * Parses a single Jason structure into a map entry and adds it to the given map.
     *
     * <p>If the structure has arity 1, the single argument is parsed as a scalar or
     * complex value via {@link #parseValue(Term)}. If the structure has arity &gt; 1,
     * each argument is itself expected to be a structure and is recursively parsed into
     * a nested map stored under the parent functor's key.
     *
     * @param t   the Jason term to parse, expected to be a {@link Structure}
     * @param map the map to insert the resulting key-value pair into
     * @throws IllegalArgumentException if {@code t} is not a {@link Structure}, or if it
     *                                  has arity 0
     */
    private static void parseStructure(Term t, Map<String, Object> map) {
        if (!(t instanceof Structure s)) {
            throw new IllegalArgumentException("Expected structure like key(value)");
        }

        if (s.getArity() == 0) {
            throw new IllegalArgumentException("Expected at least 1 argument in " + s.getFunctor());
        }

        String key = s.getFunctor();

        if (s.getArity() == 1) {
            map.put(key, parseValue(s.getTerm(0)));
        } else {
            Map<String, Object> nested = new HashMap<>();
            for (int i = 0; i < s.getArity(); i++) {
                parseStructure(s.getTerm(i), nested);
            }
            map.put(key, nested);
        }
    }

    /**
     * Recursively parses a Jason {@link Term} into an equivalent Java value.
     *
     * <p>The following conversions are applied:
     * <ul>
     *   <li>{@link StringTerm} → {@link String}</li>
     *   <li>{@link VarTerm} → {@link String} (the variable's string representation)</li>
     *   <li>Zero-arity {@link Atom} → {@link String} (the functor name)</li>
     *   <li>{@link NumberTerm} → {@link Double} via {@code solve()}, or {@link String}
     *       on failure</li>
     *   <li>{@link ListTerm} → {@link List}{@code <Object>} with elements parsed recursively</li>
     *   <li>Multi-argument {@link Structure} → nested {@link Map}{@code <String, Object>}</li>
     *   <li>Single-argument {@link Structure} → single-entry {@link Map}{@code <String, Object>}</li>
     * </ul>
     *
     * @param t the Jason term to parse
     * @return the corresponding Java object
     * @throws IllegalArgumentException if the term type is not supported
     */
    private static Object parseValue(Term t) {
        if (t instanceof StringTerm s) {
            return s.getString();
        }
        if (t instanceof VarTerm) {
            return t.toString();
        }
        if (t instanceof Atom a && a.getArity() == 0) {
            return a.getFunctor();
        }
        if (t instanceof NumberTerm n) {
            try {
                return n.solve();
            } catch (Exception e) {
                return t.toString();
            }
        }
        if (t instanceof ListTerm list) {
            List<Object> values = new ArrayList<>();
            for (Term item : list) {
                values.add(parseValue(item));
            }
            return values;
        }
        if (t instanceof Structure s && s.getArity() > 1) {
            Map<String, Object> nested = new HashMap<>();
            for (int i = 0; i < s.getArity(); i++) {
                parseStructure(s.getTerm(i), nested);
            }
            return nested;
        }
        if (t instanceof Structure s && s.getArity() == 1) {
            Map<String, Object> nested = new HashMap<>();
            nested.put(s.getFunctor(), parseValue(s.getTerm(0)));
            return nested;
        }
        throw new IllegalArgumentException(
            "Values must be lists, numbers, atoms, strings, vars or nested values. Found: " + t
        );
    }
}
