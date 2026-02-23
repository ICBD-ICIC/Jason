package lib;

import jason.asSyntax.*;
import java.util.*;

/**
 * Utility class for translating Java {@link Map} structures into Jason {@link Term} representations.
 *
 * <p>Provides static methods to convert Java maps into Jason list terms,
 * supporting nested structures, lists, numbers, strings, and atoms.
 *
 * <p>This class is not instantiable.
 */
public final class JavaToJasonTranslator {

    /**
     * Translates a {@link Map} of variables into a Jason list term.
     *
     * <p>Each entry in the map becomes a structure in the list, with the key as the functor
     * and the value converted to the appropriate Jason term.
     *
     * @param map the map to translate
     * @return a Jason list term representing the map
     * @throws IllegalArgumentException if null values are encountered in the map or nested structures.
     */
    public static Term translateVariables(Map<String, Object> map) throws IllegalArgumentException {
        if (map == null) {
            return ASSyntax.createList(new ArrayList<>());
        }
        List<Term> structures = new ArrayList<>();
        for (Map.Entry<String, Object> entry : map.entrySet()) {
            String functor = entry.getKey();
            Object value = entry.getValue();
            Term argTerm = objectToTerm(value);
            Term structure;
            if (argTerm instanceof ListTerm lt) {
                List<Term> terms = lt.getAsList();
                boolean allStructures = terms.stream().allMatch(t -> t instanceof Structure);
                if (allStructures) {
                    // multi-arg structure
                    structure = ASSyntax.createStructure(functor, terms.toArray(new Term[0]));
                } else {
                    // single list arg
                    structure = ASSyntax.createStructure(functor, argTerm);
                }
            } else {
                structure = ASSyntax.createStructure(functor, argTerm);
            }
            structures.add(structure);
        }
        return ASSyntax.createList(structures);
    }

    /**
     * Converts a Java object to a Jason term.
     *
     * @param obj the object to convert
     * @return the corresponding Jason term
     * @throws IllegalArgumentException if the object is null or contains null values in nested structures
     */
    private static Term objectToTerm(Object obj) throws IllegalArgumentException {
        if (obj == null) {
            throw new IllegalArgumentException("Null values are not allowed");
        }
        if (obj instanceof Number) {
            return ASSyntax.createNumber(((Number) obj).doubleValue());
        } else if (obj instanceof String) {
            return new StringTermImpl((String) obj);
        } else if (obj instanceof List) {
            List<?> list = (List<?>) obj;
            List<Term> terms = new ArrayList<>();
            for (Object item : list) {
                terms.add(objectToTerm(item));
            }
            return ASSyntax.createList(terms);
        } else if (obj instanceof Map) {
            Map<?, ?> m = (Map<?, ?>) obj;
            List<Term> terms = new ArrayList<>();
            for (Map.Entry<?, ?> e : m.entrySet()) {
                String key = e.getKey().toString();
                Object val = e.getValue();
                Term arg = objectToTerm(val);
                Term struct = ASSyntax.createStructure(key, arg);
                terms.add(struct);
            }
            return ASSyntax.createList(terms);
        } else {
            return ASSyntax.createAtom(obj.toString());
        }
    }
}