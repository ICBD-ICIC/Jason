package lib;

import jason.asSyntax.*;

import java.util.*;

public final class Translator {

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
