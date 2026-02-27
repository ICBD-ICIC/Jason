package env;

import jason.asSyntax.*;
import java.util.*;

import jason.asSemantics.Unifier;

public class DefaultKnowledgeManager implements KnowledgeManager {

    private final List<Literal> facts = new ArrayList<>();

    public DefaultKnowledgeManager() {
        load();
    }

    private void load() {
        try {
            // Add your shared facts here
            facts.add(ASSyntax.parseLiteral("some_fact(a, b)"));
            facts.add(ASSyntax.parseLiteral("some_fact(c, d)"));
        } catch (Exception e) {
            throw new RuntimeException("Failed to load knowledge base: " + e.getMessage(), e);
        }
    }

    @Override
    public List<Literal> query(Literal queryLiteral) {
        List<Literal> results = new ArrayList<>();
        for (Literal fact : facts) {
            Unifier u = new Unifier();
            if (u.unifies(queryLiteral, fact)) {
                // Apply unification to get the ground version of the query
                Literal unified = (Literal) queryLiteral.capply(u);
                results.add(unified);
            }
        }
        return results;
    }
}