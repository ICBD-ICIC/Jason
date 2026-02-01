package lib;

import jason.asSyntax.*;

import java.util.*;

public final class Translator {
    public static List<String> translateTopics(Term t){
        String topics = t.toString();
        topics = topics.trim().substring(1, topics.length() - 1);
        String[] items = topics.split("\\s*,\\s*");
        List<String> list = new ArrayList<>();
        for (String topic : items) {
            list.add(topic);
        }
        return list;
    }

    //TODO: allow different value types
    public static Map<String, String> translateVariables(Term v){
        String variables = v.toString();
        variables = variables.trim().substring(1, variables.length() - 1);
       if (variables.isEmpty()) {
            return new HashMap<>();
        }
        String[] items = variables.split("\\s*,\\s*");
        Map<String, String> map = new HashMap<>();
        for (String item : items) {
            // Assuming format is always key(value)
            int openParen = item.indexOf('(');
            int closeParen = item.lastIndexOf(')');
            String key = item.substring(0, openParen);
            String value = item.substring(openParen + 1, closeParen);
            map.put(key, value);
        }
        return map;
    }
}
